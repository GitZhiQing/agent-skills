"""Command-line interface.

Exit codes: 0 success, 1 business failure, 2 usage/selection error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from disk_cleanup import __version__
from disk_cleanup.cleaner import CleanupError, execute_cleanup
from disk_cleanup.report import summarize_entries, write_scan_outputs
from disk_cleanup.rules import asset_file, load_rules, validate_rules
from disk_cleanup.scanner import ScanError, ScanOptions, Scanner, UsageError
from disk_cleanup.selection import (
    SelectionError,
    load_scan,
    load_selection,
    resolve_scan_file,
    validate_selection,
)
from disk_cleanup.winutil import (
    drive_type_label,
    ensure_utf8_stdio,
    get_drive_type,
    get_volume_info,
    human_size,
    is_admin,
    iso_now,
)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def _default_output_dir() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path.home() / "disk-cleanup" / stamp
    if base.exists():
        base = base.with_name(stamp + "-" + os.urandom(2).hex())
    return str(base)


def _ensure_output_dir(path: str) -> None:
    out = Path(path)
    if out.exists() and not out.is_dir():
        raise UsageError(f"输出路径不是目录：{path}")
    if out.exists():
        for name in ("scan.json", "report.html", "cleanup.json", "cleanup-report.html"):
            if (out / name).exists():
                raise UsageError(
                    f"输出目录已有报告文件：{out / name}；请换一个 --output-dir，避免覆盖。"
                )


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def _print_error(exc: BaseException, as_json: bool, kind: str = "failure") -> None:
    if as_json:
        _print_json({"ok": False, "error": {"type": kind, "message": str(exc)}})
    else:
        print(f"ERROR: {exc}", file=sys.stderr)


def _top_entries(entries: Sequence[Any], limit: int = 8) -> List[Dict[str, Any]]:
    items = sorted(
        (e for e in entries if e.selectable and e.size),
        key=lambda e: -(e.size or 0),
    )[:limit]
    return [
        {
            "path": e.path,
            "title": e.title,
            "size": e.size,
            "size_h": human_size(e.size),
            "recommendation": e.recommendation,
        }
        for e in items
    ]


# -- commands -----------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.root or os.getcwd())
    checks: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str, level: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "level": level})

    check("windows", os.name == "nt", "Windows" if os.name == "nt" else f"当前系统：{os.name}")
    py_ok = sys.version_info >= (3, 9)
    check("python", py_ok, f"Python {sys.version.split()[0]}（需要 >= 3.9）")
    uv_path = shutil.which("uv")
    check("uv", bool(uv_path), uv_path or "未找到 uv（可选；也可直接用 python 运行）", "warn")
    ps_path = shutil.which("powershell") or shutil.which("pwsh")
    check(
        "powershell",
        bool(ps_path),
        ps_path or "未找到 PowerShell；回收站模式不可用，只能 --mode permanent",
        "warn",
    )
    check("admin", is_admin(), "管理员" if is_admin() else "普通用户（系统级目录可能失败）", "warn")
    root_ok = os.path.isdir(root)
    check("root", root_ok, root if root_ok else f"目录不存在：{root}")
    drive_type = get_drive_type(root) if root_ok else "unknown"
    check("drive_type", drive_type not in ("cdrom",), drive_type_label(drive_type), "error")
    volume = get_volume_info(root) if root_ok else {}
    writable = os.access(root, os.W_OK) if root_ok else False
    check("writable", writable, "根目录可写" if writable else "根目录不可写（删除会失败）", "warn")
    hard_ok = all(c["ok"] for c in checks if c["level"] == "error")
    data = {
        "ok": hard_ok,
        "version": __version__,
        "root": root,
        "checks": checks,
        "volume": volume,
        "rules": {"path": str(asset_file("rules.json")), "exists": asset_file("rules.json").exists()},
        "ai_next": (
            "环境可用：运行 scan。"
            if hard_ok
            else "先修复 error 级检查项（Windows 目标目录/Python 版本），再运行 scan。"
        ),
    }
    if args.json:
        _print_json(data)
    else:
        print(f"windows-disk-cleanup {__version__}")
        for c in checks:
            mark = "ok" if c["ok"] else ("warn" if c["level"] == "warn" else "ERROR")
            print(f"  [{mark}] {c['name']}: {c['detail']}")
        print(f"rules: {data['rules']['path']} ({'存在' if data['rules']['exists'] else '缺失'})")
        if volume:
            print(
                f"volume: {volume.get('label') or ''} {volume.get('filesystem') or ''} "
                f"{human_size(volume.get('free'))} free / {human_size(volume.get('total'))}"
            )
        print(data["ai_next"])
    return EXIT_OK if hard_ok else EXIT_FAIL


def cmd_scan(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise UsageError("windows-disk-cleanup 仅支持 Windows 10/11。")
    if args.min_size < 0:
        raise UsageError("--min-size 不能为负数")
    if args.listing_depth < 0:
        raise UsageError("--listing-depth 不能为负数")
    if args.max_entries < 1:
        raise UsageError("--max-entries 至少为 1")
    if args.max_seconds < 0:
        raise UsageError("--max-seconds 不能为负数")
    output_dir = os.path.abspath(args.output_dir or _default_output_dir())
    _ensure_output_dir(output_dir)
    rules_data = load_rules(Path(args.rules)) if args.rules else load_rules()
    errors = validate_rules(rules_data)
    if errors:
        raise ScanError("规则库校验失败：" + "；".join(errors[:5]))
    progress = (not args.quiet) and (args.progress or sys.stderr.isatty())
    options = ScanOptions(
        root=args.root,
        output_dir=output_dir,
        min_size=int(args.min_size) * 1024 * 1024,
        listing_depth=int(args.listing_depth),
        max_entries=int(args.max_entries),
        max_seconds=float(args.max_seconds),
        exclude=list(args.exclude or []),
        allow_network=bool(args.allow_network),
        progress=progress,
    )
    scanner = Scanner(options, rules_data=rules_data)
    result = scanner.scan()
    outputs = write_scan_outputs(result, output_dir, max_entries=args.max_entries)
    summary = summarize_entries(result.entries)
    payload = {
        "ok": True,
        "scan_id": result.scan_id,
        "root": result.root_display,
        "output_dir": os.path.abspath(output_dir),
        "report": outputs["report_html"],
        "scan_json": outputs["scan_json"],
        "stats": result.stats.to_dict(),
        "summary": {
            "safe": summary["safe_count"],
            "caution": summary["caution_count"],
            "review": summary["review_count"],
            "keep": summary["keep_count"],
            "selectable": summary["selectable"],
            "safe_bytes": summary["safe_bytes"],
            "caution_bytes": summary["caution_bytes"],
            "review_bytes": summary["review_bytes"],
            "entries": len(result.entries),
            "omitted": result.omitted_entries,
        },
        "top": _top_entries(result.entries),
        "notes": result.notes,
        "ai_next": (
            "让用户在浏览器打开 report.html，勾选条目后点击「复制选中路径」，"
            "把 JSON 粘贴回来；收到后先运行 delete --selection <file> --dry-run --json。"
        ),
    }
    if args.json:
        _print_json(payload)
    else:
        print(f"扫描完成：{result.root_display}")
        print(
            f"  目录 {result.stats.dirs:,} / 文件 {result.stats.files:,} / "
            f"{human_size(result.stats.bytes)} · 耗时 {result.duration_s:.1f}s"
        )
        print(
            f"  安全 {summary['safe_count']} · 谨慎 {summary['caution_count']} · "
            f"待确认 {summary['review_count']} · 保留 {summary['keep_count']}"
        )
        print(f"  报告：{outputs['report_html']}")
        print(f"  数据：{outputs['scan_json']}")
        if result.omitted_entries:
            print(f"  报告省略 {result.omitted_entries} 条较小条目（完整数据在 scan.json）")
        print()
        print("下一步：打开报告页勾选 → 复制选中路径 → 粘贴回 Agent。")
    return EXIT_OK


def cmd_delete(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise UsageError("windows-disk-cleanup 仅支持 Windows 10/11。")
    if args.dry_run and args.yes:
        raise UsageError("--dry-run 与 --yes 不能同时使用")
    selection = load_selection(args.selection)
    scan_file = resolve_scan_file(selection, args.selection, args.scan)
    scan = load_scan(scan_file)
    validation = validate_selection(scan, selection, args.mode)
    confirmed = bool(validation.confirmed or args.confirm)
    plan = {
        "ok": not validation.invalid,
        "dry_run": True,
        "scan_id": validation.scan_id,
        "root": validation.root,
        "mode": validation.mode,
        "confirmed": confirmed,
        "selected": len(validation.paths),
        "planned": validation.planned,
        "covered": validation.covered,
        "invalid": validation.invalid,
        "missing": validation.missing,
        "review": validation.review,
        "caution": validation.caution,
        "estimated_bytes": validation.estimated_bytes,
        "estimated_h": human_size(validation.estimated_bytes),
        "requires_allow_review": validation.requires_allow_review,
        "requires_confirm": not confirmed,
        "requires_yes": True,
        "ai_next": (
            "先处理 invalid（如有），确认 confirmed 为 true；执行时加 --yes。"
            "若 requires_allow_review 为 true，还需 --allow-review。"
        ),
    }
    if not args.yes:
        if args.json:
            _print_json(plan)
        else:
            print(f"预演（未删除）：{validation.root}")
            print(f"  方式：{validation.mode} · 计划 {len(validation.planned)} 项 · 约 {human_size(validation.estimated_bytes)}")
            if validation.invalid:
                print("  无效路径：", file=sys.stderr)
                for item in validation.invalid:
                    print(f"    - {item['path']}（{item['reason']}）", file=sys.stderr)
            for item in validation.planned:
                print(f"  + {item['path']}  [{item.get('recommendation', '')}]")
            if validation.covered:
                print(f"  父子重叠被覆盖：{len(validation.covered)} 项")
            if validation.missing:
                print(f"  已不存在：{len(validation.missing)} 项")
            if validation.requires_allow_review:
                print("  包含待确认项：执行时需 --allow-review")
            if not confirmed:
                print("  选择未确认：请在报告页勾选确认，或执行时加 --confirm")
        return EXIT_OK if not validation.invalid else EXIT_USAGE

    if validation.invalid:
        raise SelectionError(
            "选择中有无效路径，已拒绝执行："
            + "；".join(f"{i['path']}（{i['reason']}）" for i in validation.invalid[:5])
        )
    if not confirmed:
        raise SelectionError(
            "选择尚未确认。请在报告页勾选确认框后重新复制，或在聊天中明确确认后加 --confirm。"
        )
    if validation.requires_allow_review and not args.allow_review:
        raise SelectionError(
            "选择包含待确认目录（recommendation=review），执行需加 --allow-review。"
            f"涉及：{'; '.join(validation.review[:5])}"
        )
    if not validation.planned:
        raise SelectionError("没有可执行的条目（可能全部被覆盖或已不存在）。")
    output_dir = str(scan.get("output_dir") or Path(scan_file).resolve().parent)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    result, outputs = execute_cleanup(
        scan,
        validation,
        output_dir,
        confirmed,
        rules_version=str(scan.get("rules_version", "")),
    )
    data = result.to_dict()
    data.update(
        {
            "ok": result.summary().get("failed", 0) == 0
            and result.summary().get("partial", 0) == 0,
            "cleanup_report": outputs["cleanup_html"],
            "cleanup_json": outputs["cleanup_json"],
            "notes": result.notes,
            "ai_next": (
                "打开 cleanup-report.html；如 failed/partial > 0，按错误列处理（关闭占用程序/管理员重试）。"
            ),
        }
    )
    if args.json:
        _print_json(data)
    else:
        summary = result.summary()
        print(f"清理完成：{result.root}")
        print(
            f"  选中 {summary['selected']} · 成功 {summary['deleted']} · "
            f"失败/部分 {summary['failed'] + summary['partial']} · 跳过 {summary['skipped']}"
        )
        print(f"  释放/移入：{human_size(summary['moved_bytes'])} · 实际可用变化：{human_size(summary['volume_freed'])}")
        print(f"  报告：{outputs['cleanup_html']}")
        for item in result.items:
            if item.status in ("failed", "partial"):
                print(f"  ! {item.path}：{item.error}", file=sys.stderr)
        print()
        print("下一步：查看清理报告；回收站模式需清空回收站才会真正释放空间。")
    return EXIT_OK if data["ok"] else EXIT_FAIL


def cmd_rules(args: argparse.Namespace) -> int:
    data = load_rules(Path(args.rules)) if args.rules else load_rules()
    errors = validate_rules(data)
    if args.check:
        payload = {
            "ok": not errors,
            "count": len(data.get("rules", [])),
            "updated": data.get("updated", ""),
            "source": data.get("_source", ""),
            "errors": errors,
        }
        if args.json:
            _print_json(payload)
        else:
            print(f"rules: {payload['count']} 条 · updated {payload['updated']}")
            print(f"source: {payload['source']}")
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_OK if not errors else EXIT_FAIL
    if args.json:
        _print_json(data)
    else:
        print(f"rules: {len(data.get('rules', []))} 条 · updated {data.get('updated', '')}")
        print(f"source: {data.get('_source', '')}")
    return EXIT_OK


# -- parser -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="windows-disk-cleanup",
        description=(
            "扫描 Windows 磁盘/文件夹，生成可勾选的 HTML 报告；"
            "用户确认后安全删除并生成清理报告。"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="检查 Windows/Python/PowerShell/管理员/目标盘环境")
    doctor.add_argument("--root", default="", help="要检查的目标路径（默认当前目录）")
    doctor.add_argument("--json", action="store_true", help="输出单行 JSON")

    scan = sub.add_parser("scan", help="只读扫描并生成 report.html + scan.json")
    scan.add_argument("--root", required=True, help="盘符（如 C:\\）或文件夹")
    scan.add_argument("--output-dir", default="", help="输出目录（默认 ~/disk-cleanup/<时间戳>/）")
    scan.add_argument("--min-size", type=int, default=50, metavar="MB", help="通用大目录阈值，默认 50MB")
    scan.add_argument("--listing-depth", type=int, default=3, help="通用大目录列出深度，默认 3")
    scan.add_argument("--max-entries", type=int, default=1500, help="HTML 报告最多嵌入条目，默认 1500")
    scan.add_argument("--max-seconds", type=float, default=0, help="扫描时间上限（秒），0 表示不限")
    scan.add_argument("--exclude", action="append", default=[], metavar="PATTERN", help="排除路径或名称（可重复）")
    scan.add_argument("--allow-network", action="store_true", help="允许扫描网络/未知类型驱动器")
    scan.add_argument("--rules", default="", help="自定义 rules.json（调试/维护）")
    scan.add_argument("--progress", action="store_true", help="强制在 stderr 输出进度")
    scan.add_argument("--quiet", action="store_true", help="不输出进度")
    scan.add_argument("--json", action="store_true", help="输出单行 JSON")

    delete = sub.add_parser("delete", help="校验选择并删除（默认只预演，--yes 才执行）")
    delete.add_argument("--selection", required=True, help="从报告页复制的选择 JSON 文件")
    delete.add_argument("--scan", default=None, help="scan.json 路径（默认从选择 JSON/同目录推断）")
    delete.add_argument("--mode", choices=["recycle", "permanent"], default=None, help="覆盖选择 JSON 的删除方式")
    delete.add_argument("--dry-run", action="store_true", help="只校验与预演（默认行为）")
    delete.add_argument("--yes", action="store_true", help="确认执行删除")
    delete.add_argument("--confirm", action="store_true", help="用户已在聊天中明确确认（替代报告页确认框）")
    delete.add_argument("--allow-review", action="store_true", help="允许删除 recommendation=review 的待确认项")
    delete.add_argument("--json", action="store_true", help="输出单行 JSON")

    rules = sub.add_parser("rules", help="查看/校验内置规则库")
    rules.add_argument("--rules", default="", help="自定义 rules.json")
    rules.add_argument("--check", action="store_true", help="校验规则字段与 id 唯一性")
    rules.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = bool(getattr(args, "json", False))
    try:
        if args.command == "doctor":
            return cmd_doctor(args)
        if args.command == "scan":
            return cmd_scan(args)
        if args.command == "delete":
            return cmd_delete(args)
        if args.command == "rules":
            return cmd_rules(args)
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    except UsageError as exc:
        _print_error(exc, as_json, "usage")
        return EXIT_USAGE
    except SelectionError as exc:
        _print_error(exc, as_json, "selection")
        return EXIT_USAGE
    except ScanError as exc:
        _print_error(exc, as_json, "scan")
        return EXIT_FAIL
    except CleanupError as exc:
        _print_error(exc, as_json, "cleanup")
        return EXIT_FAIL
    except KeyboardInterrupt:
        _print_error(RuntimeError("用户中断"), as_json, "interrupted")
        return 130
    except OSError as exc:
        _print_error(exc, as_json, "io")
        return EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
