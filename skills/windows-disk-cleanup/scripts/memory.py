#!/usr/bin/env python3
"""Local experience store for windows-disk-cleanup.

Two layers:

* ``memory/lessons/*.json`` + ``memory/INDEX.md``: public, sanitised lessons
  that can be committed and shared.
* ``memory/local/lessons/*.json`` + ``memory/local/INDEX.md``: machine-private
  lessons (full paths allowed), gitignored.

JSON files are authoritative; INDEX.md is generated from them.

Usage:
  python scripts/memory.py search --query "appdata timeout" --json
  python scripts/memory.py record --kind failure --scope delete \
    --trigger "access denied" --finding "..." --action "..." --json
  python scripts/memory.py used L-001 --json
  python scripts/memory.py graduate L-001 --to "rules.json#win-temp" --json
  python scripts/memory.py check --json

Exit codes: 0 success / 1 memory failure / 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = 1
KINDS = ("success", "failure", "preference")
SCOPES = ("scan", "delete", "report", "rule", "general")
STATUSES = ("active", "candidate", "graduated", "retired")
PRIVACY = ("public", "local")
PREFIX = {"public": "L", "local": "P"}
ID_RE = re.compile(r"^(L|P)-(\d{3})$")
USER_PATH_RE = re.compile(r"(?i)([a-z]:[\\/]+users[\\/]+)(?!<user>)[^\\/\s]+")
SECRET_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)"
    r"\s*[:=]\s*[^\s,;]+"
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


class MemoryStoreError(Exception):
    """Business-level memory failure (exit code 1)."""


class MemoryUsageError(Exception):
    """Bad arguments (exit code 2)."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 with LF regardless of host newline translation."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def skill_version() -> str:
    init = Path(__file__).resolve().parents[1] / "src" / "disk_cleanup" / "__init__.py"
    try:
        text = init.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        return match.group(1) if match else "unknown"
    except OSError:
        return "unknown"


def default_memory_root() -> Path:
    return Path(__file__).resolve().parents[1] / "memory"


def lesson_dir(root: Path, privacy: str) -> Path:
    base = root / "local" if privacy == "local" else root
    return base / "lessons"


def index_path(root: Path, privacy: str) -> Path:
    base = root / "local" if privacy == "local" else root
    return base / "INDEX.md"


def ensure_dirs(root: Path, privacy: str) -> None:
    lesson_dir(root, privacy).mkdir(parents=True, exist_ok=True)


def _slug(text: str, fallback: str = "lesson") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return slug or fallback


def _redact_env(text: str) -> str:
    for name in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        value = os.environ.get(name)
        if value:
            text = re.sub(re.escape(value), f"%{name}%", text, flags=re.IGNORECASE)
    return text


def sanitize_text(text: Any, privacy: str) -> Any:
    if not isinstance(text, str):
        return text
    if privacy == "public":
        return USER_PATH_RE.sub(r"\1<user>", _redact_env(text))
    # local 层是本机私有、gitignored；保留完整路径便于定位。
    return text


def _assert_no_secret(text: str, where: str) -> None:
    if SECRET_RE.search(text) or PRIVATE_KEY_RE.search(text):
        raise MemoryStoreError(
            f"{where} 看起来包含密码/Token/私钥；经验库禁止记录凭据。"
            "请改用“凭据目录被跳过”之类不含值的描述。"
        )


def _clean_payload(data: Dict[str, Any], privacy: str) -> Dict[str, Any]:
    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return sanitize_text(value, privacy)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {str(key): walk(item) for key, item in value.items()}
        return value

    cleaned = walk(data)
    _assert_no_secret(json.dumps(cleaned, ensure_ascii=False), "经验内容")
    return cleaned


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_lessons(root: Path, privacy: str = "all") -> List[Dict[str, Any]]:
    layers = PRIVACY if privacy == "all" else (privacy,)
    lessons: List[Dict[str, Any]] = []
    for layer in layers:
        directory = lesson_dir(root, layer)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            data = _read_json(path)
            if data is None:
                continue
            data["_file"] = path.name
            data["_path"] = str(path)
            lessons.append(data)
    lessons.sort(key=lambda item: str(item.get("id", "")))
    return lessons


def next_id(root: Path, privacy: str) -> str:
    prefix = PREFIX[privacy]
    highest = 0
    directory = lesson_dir(root, privacy)
    if directory.exists():
        for path in directory.glob("*.json"):
            match = re.match(rf"^{prefix}-(\d{{3}})", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"{prefix}-{highest + 1:03d}"


def rebuild_index(root: Path, privacy: str) -> Path:
    lessons = load_lessons(root, privacy)
    lines: List[str] = []
    title = "public（可提交）" if privacy == "public" else "local（本机私有，gitignored）"
    lines.append(f"# windows-disk-cleanup 经验索引 — {title}")
    lines.append("")
    lines.append("> 本文件由 `scripts/memory.py` 生成；`lessons/*.json` 是权威数据，不要手工改表。")
    if privacy == "public":
        lines.append("> public 条目不得包含完整用户路径、用户名、凭据或用户文件名；本机详情请用 `--privacy local`。")
    else:
        lines.append("> 本机私有层可以保存完整路径；`memory/local/` 已 gitignore，不要提交。")
    lines.append("> 检索：`python scripts/memory.py search --query \"<关键词>\" --json`；毕业：`memory.py graduate <ID> --to <目标>`。")
    lines.append("")
    counts = {status: 0 for status in STATUSES}
    for item in lessons:
        status = str(item.get("status", "active"))
        counts[status] = counts.get(status, 0) + 1
    lines.append(
        "共 {} 条：active {} / candidate {} / graduated {} / retired {}".format(
            len(lessons), counts.get("active", 0), counts.get("candidate", 0),
            counts.get("graduated", 0), counts.get("retired", 0),
        )
    )
    lines.append("")
    if not lessons:
        lines.append("（暂无）")
    else:
        lines.append("| ID | 类型 | 范围 | 触发 | 摘要 | used | 状态 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for item in lessons:
            file_name = str(item.get("_file", ""))
            link = f"[{item.get('id', '?')}](lessons/{file_name})" if file_name else str(item.get("id", "?"))
            trigger = ", ".join(str(t) for t in item.get("trigger", []))
            title_text = str(item.get("title", "")).replace("|", "\\|")
            trigger = trigger.replace("|", "\\|")
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} |".format(
                    link, item.get("kind", ""), item.get("scope", ""), trigger,
                    title_text, item.get("used", 0), item.get("status", ""),
                )
            )
    target = index_path(root, privacy)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_text(target, "\n".join(lines) + "\n")
    return target


def _coerce_options(values: Sequence[str]) -> Dict[str, str]:
    options: Dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise MemoryUsageError(f"--option 需要 key=value：{value}")
        key, item = value.split("=", 1)
        key = key.strip()
        if not key:
            raise MemoryUsageError(f"--option 的 key 不能为空：{value}")
        options[key] = item.strip()
    return options


def record(
    root: Path,
    kind: str,
    scope: str,
    triggers: Sequence[str],
    finding: str,
    action: str,
    title: str = "",
    privacy: str = "public",
    rule_ids: Sequence[str] = (),
    error_types: Sequence[str] = (),
    option_values: Sequence[str] = (),
    evidence_notes: str = "",
) -> Dict[str, Any]:
    if kind not in KINDS:
        raise MemoryUsageError(f"kind 非法：{kind}")
    if scope not in SCOPES:
        raise MemoryUsageError(f"scope 非法：{scope}")
    if privacy not in PRIVACY:
        raise MemoryUsageError(f"privacy 非法：{privacy}")
    finding = str(finding).strip()
    action = str(action).strip()
    if not finding or not action:
        raise MemoryUsageError("finding 与 action 不能为空")
    trigger_list = [str(t).strip() for t in triggers if str(t).strip()]
    if not trigger_list:
        raise MemoryUsageError("至少需要一个 --trigger")
    title_text = str(title).strip() or finding.splitlines()[0][:60]
    options = _coerce_options(option_values)
    ensure_dirs(root, privacy)
    lesson = {
        "schema": SCHEMA,
        "id": next_id(root, privacy),
        "title": title_text,
        "kind": kind,
        "scope": scope,
        "trigger": trigger_list,
        "finding": finding,
        "action": action,
        "evidence": {
            "rule_ids": [str(x) for x in rule_ids if str(x).strip()],
            "error_types": [str(x) for x in error_types if str(x).strip()],
            "options": options,
            "notes": evidence_notes,
        },
        "used": 0,
        "status": "active",
        "privacy": privacy,
        "skill_version": skill_version(),
        "created_at": now_iso(),
        "last_used_at": None,
        "graduated_at": None,
        "graduated_to": None,
    }
    lesson = _clean_payload(lesson, privacy)
    file_name = f"{lesson['id']}-{_slug(lesson['title'])}.json"
    target = lesson_dir(root, privacy) / file_name
    _write_text(target, json.dumps(lesson, ensure_ascii=False, indent=2) + "\n")
    rebuild_index(root, privacy)
    lesson["_file"] = file_name
    return lesson


def _find(root: Path, lesson_id: str) -> Tuple[Dict[str, Any], str, Path]:
    lesson_id = lesson_id.strip().upper()
    for layer in PRIVACY:
        for item in load_lessons(root, layer):
            if str(item.get("id", "")).upper() == lesson_id:
                path = Path(item["_path"])
                return item, layer, path
    raise MemoryStoreError(f"未找到经验：{lesson_id}")


def _save(item: Dict[str, Any], path: Path, layer: str) -> None:
    data = {key: value for key, value in item.items() if not key.startswith("_")}
    data = _clean_payload(data, layer)
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def mark_used(root: Path, lesson_id: str) -> Dict[str, Any]:
    item, layer, path = _find(root, lesson_id)
    if item.get("status") in ("graduated", "retired"):
        raise MemoryStoreError(f"{lesson_id} 状态为 {item.get('status')}，不再累计 used。")
    item["used"] = int(item.get("used", 0) or 0) + 1
    item["last_used_at"] = now_iso()
    if item["used"] >= 3 and item.get("status") == "active":
        item["status"] = "candidate"
    _save(item, path, layer)
    rebuild_index(root, layer)
    return item


def graduate(root: Path, lesson_id: str, target: str, note: str = "") -> Dict[str, Any]:
    item, layer, path = _find(root, lesson_id)
    if item.get("status") in ("graduated", "retired"):
        raise MemoryStoreError(f"{lesson_id} 已经是 {item.get('status')}，不能重复毕业。")
    if not str(target).strip():
        raise MemoryUsageError("graduate 需要 --to（写入哪个规则/文档）")
    item["status"] = "graduated"
    item["graduated_at"] = now_iso()
    item["graduated_to"] = str(target).strip()
    item["graduation_note"] = str(note).strip()
    _save(item, path, layer)
    rebuild_index(root, layer)
    return item


def retire(root: Path, lesson_id: str, reason: str = "") -> Dict[str, Any]:
    item, layer, path = _find(root, lesson_id)
    if item.get("status") == "retired":
        return item
    item["status"] = "retired"
    item["retired_at"] = now_iso()
    item["retire_reason"] = str(reason).strip()
    _save(item, path, layer)
    rebuild_index(root, layer)
    return item


def _score(item: Dict[str, Any], tokens: Sequence[str]) -> float:
    title = str(item.get("title", "")).lower()
    trigger = " ".join(str(t) for t in item.get("trigger", [])).lower()
    finding = str(item.get("finding", "")).lower()
    action = str(item.get("action", "")).lower()
    evidence = item.get("evidence") or {}
    rules = " ".join(str(x) for x in evidence.get("rule_ids", [])).lower()
    errors = " ".join(str(x) for x in evidence.get("error_types", [])).lower()
    options = json.dumps(evidence.get("options", {}), ensure_ascii=False).lower()
    score = 0.0
    for token in tokens:
        if token in title or token in trigger:
            score += 5
        if token in rules or token in errors or token in options:
            score += 3
        if token in finding or token in action:
            score += 1
    return score


def search(
    root: Path,
    query: str = "",
    scope: Optional[str] = None,
    kind: Optional[str] = None,
    privacy: str = "all",
    limit: int = 5,
    all_status: bool = False,
) -> List[Dict[str, Any]]:
    if privacy not in ("all",) + PRIVACY:
        raise MemoryUsageError(f"privacy 非法：{privacy}")
    tokens = [token.lower() for token in re.split(r"[\s,;，；、]+", query.strip()) if token]
    results: List[Dict[str, Any]] = []
    for item in load_lessons(root, privacy):
        status = str(item.get("status", "active"))
        if not all_status and status not in ("active", "candidate"):
            continue
        if scope and item.get("scope") != scope:
            continue
        if kind and item.get("kind") != kind:
            continue
        match_score = _score(item, tokens)
        if tokens and match_score <= 0:
            continue
        score = match_score + min(int(item.get("used", 0) or 0), 5) * 0.5
        results.append({**item, "_score": score, "_match": match_score})
    results.sort(
        key=lambda item: (
            -float(item.get("_score", 0)),
            -int(item.get("used", 0) or 0),
            str(item.get("created_at", "")),
        )
    )
    for item in results:
        item.pop("_path", None)
    return results[: max(1, limit)]


def list_lessons(
    root: Path, privacy: str = "all", status: Optional[str] = None
) -> List[Dict[str, Any]]:
    items = load_lessons(root, privacy)
    if status:
        items = [item for item in items if item.get("status") == status]
    for item in items:
        item.pop("_path", None)
    return items


def validate(root: Path) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    seen: Dict[str, str] = {}
    counts = {"public": 0, "local": 0}
    for layer in PRIVACY:
        directory = lesson_dir(root, layer)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            counts[layer] += 1
            data = _read_json(path)
            if data is None:
                errors.append(f"{path}: JSON 无法解析")
                continue
            prefix = ""
            lesson_id = str(data.get("id", ""))
            match = ID_RE.match(lesson_id)
            if not match:
                errors.append(f"{path}: id 非法（{lesson_id}）")
            else:
                prefix = match.group(1)
                if prefix != PREFIX[layer]:
                    errors.append(f"{path}: id 前缀 {prefix} 与目录 {layer} 不匹配")
            if lesson_id in seen:
                errors.append(f"{path}: id 重复（也出现在 {seen[lesson_id]}）")
            else:
                seen[lesson_id] = str(path)
            if data.get("schema") != SCHEMA:
                errors.append(f"{path}: schema 不是 {SCHEMA}")
            for key in ("title", "finding", "action"):
                if not isinstance(data.get(key), str) or not data.get(key).strip():
                    errors.append(f"{path}: {key} 为空")
            if data.get("kind") not in KINDS:
                errors.append(f"{path}: kind 非法")
            if data.get("scope") not in SCOPES:
                errors.append(f"{path}: scope 非法")
            if data.get("status") not in STATUSES:
                errors.append(f"{path}: status 非法")
            if data.get("privacy") != layer:
                errors.append(f"{path}: privacy 与目录不一致")
            if not isinstance(data.get("trigger"), list) or not data.get("trigger"):
                errors.append(f"{path}: trigger 必须是非空数组")
            if not isinstance(data.get("used"), int) or data.get("used", 0) < 0:
                errors.append(f"{path}: used 必须是非负整数")
            if not isinstance(data.get("evidence"), dict):
                errors.append(f"{path}: evidence 必须是对象")
            text = json.dumps(data, ensure_ascii=False)
            try:
                _assert_no_secret(text, str(path))
            except MemoryStoreError as exc:
                errors.append(str(exc))
            if layer == "public":
                if USER_PATH_RE.search(text):
                    errors.append(f"{path}: public 经验包含未脱敏的用户路径")
            if path.name.startswith(lesson_id) is False and lesson_id:
                warnings.append(f"{path}: 文件名未以 id 开头")
        idx = index_path(root, layer)
        if counts[layer] and not idx.exists():
            warnings.append(f"{idx}: 经验存在但 INDEX.md 缺失")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "ids": sorted(seen),
    }


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def _print_search(results: Sequence[Dict[str, Any]]) -> None:
    if not results:
        print("（没有匹配的经验）")
        return
    for item in results:
        print(
            "[{}] {} used={} {} / {}".format(
                item.get("id"), item.get("status"), item.get("used", 0),
                item.get("kind"), item.get("scope"),
            )
        )
        print(f"  {item.get('title')}")
        print(f"  做法：{item.get('action')}")
        if item.get("graduated_to"):
            print(f"  已毕业：{item.get('graduated_to')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory.py",
        description="windows-disk-cleanup 经验库：检索、写回、used、毕业与校验。",
    )
    parser.add_argument("--memory-root", default=str(default_memory_root()), help="经验库根目录（默认 skill/memory）")
    parser.add_argument("--version", action="version", version=f"windows-disk-cleanup memory {skill_version()}")
    sub = parser.add_subparsers(dest="command", required=True)

    search_cmd = sub.add_parser("search", help="检索经验（默认只返回 active/candidate）")
    search_cmd.add_argument("--query", default="", help="关键词，空格分隔")
    search_cmd.add_argument("--scope", choices=SCOPES, default=None)
    search_cmd.add_argument("--kind", choices=KINDS, default=None)
    search_cmd.add_argument("--privacy", choices=("all",) + PRIVACY, default="all")
    search_cmd.add_argument("--limit", type=int, default=5)
    search_cmd.add_argument("--all-status", action="store_true", help="包含 graduated/retired")
    search_cmd.add_argument("--json", action="store_true")

    record_cmd = sub.add_parser("record", help="写回一条经验")
    record_cmd.add_argument("--kind", choices=KINDS, required=True)
    record_cmd.add_argument("--scope", choices=SCOPES, default="general")
    record_cmd.add_argument("--trigger", action="append", default=[], metavar="TEXT")
    record_cmd.add_argument("--title", default="")
    record_cmd.add_argument("--finding", required=True)
    record_cmd.add_argument("--action", required=True)
    record_cmd.add_argument("--rule-id", action="append", default=[])
    record_cmd.add_argument("--error-type", action="append", default=[])
    record_cmd.add_argument("--option", action="append", default=[], metavar="KEY=VALUE")
    record_cmd.add_argument("--evidence-notes", default="")
    record_cmd.add_argument("--privacy", choices=PRIVACY, default="public")
    record_cmd.add_argument("--json", action="store_true")

    used_cmd = sub.add_parser("used", help="经验实际改变动作后 used+1")
    used_cmd.add_argument("lesson_id")
    used_cmd.add_argument("--json", action="store_true")

    graduate_cmd = sub.add_parser("graduate", help="标记经验已写入规则/文档")
    graduate_cmd.add_argument("lesson_id")
    graduate_cmd.add_argument("--to", required=True, help="写入位置，如 rules.json#win-temp")
    graduate_cmd.add_argument("--note", default="")
    graduate_cmd.add_argument("--json", action="store_true")

    retire_cmd = sub.add_parser("retire", help="标记经验不再适用")
    retire_cmd.add_argument("lesson_id")
    retire_cmd.add_argument("--reason", default="")
    retire_cmd.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list", help="列出经验")
    list_cmd.add_argument("--privacy", choices=("all",) + PRIVACY, default="all")
    list_cmd.add_argument("--status", choices=STATUSES, default=None)
    list_cmd.add_argument("--json", action="store_true")

    check_cmd = sub.add_parser("check", help="校验经验库结构/隐私/重复 ID")
    check_cmd.add_argument("--json", action="store_true")

    index_cmd = sub.add_parser("index", help="从 JSON 重建 INDEX.md")
    index_cmd.add_argument("--privacy", choices=("all",) + PRIVACY, default="all")
    index_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.memory_root).expanduser().resolve()
    try:
        if args.command == "search":
            results = search(
                root, args.query, args.scope, args.kind, args.privacy,
                args.limit, args.all_status,
            )
            if args.json:
                _print_json({"ok": True, "count": len(results), "lessons": results})
            else:
                _print_search(results)
            return 0
        if args.command == "record":
            lesson = record(
                root, args.kind, args.scope, args.trigger, args.finding,
                args.action, args.title, args.privacy, args.rule_id,
                args.error_type, args.option, args.evidence_notes,
            )
            if args.json:
                _print_json({"ok": True, "lesson": lesson})
            else:
                print(f"recorded: {lesson['id']} ({lesson['privacy']}/{lesson['kind']}/{lesson['scope']})")
                print(f"  {lesson['title']}")
            return 0
        if args.command == "used":
            lesson = mark_used(root, args.lesson_id)
            if args.json:
                _print_json({"ok": True, "lesson": lesson})
            else:
                print(f"used: {lesson['id']} used={lesson['used']} status={lesson['status']}")
            return 0
        if args.command == "graduate":
            lesson = graduate(root, args.lesson_id, args.to, args.note)
            if args.json:
                _print_json({"ok": True, "lesson": lesson})
            else:
                print(f"graduated: {lesson['id']} -> {lesson['graduated_to']}")
            return 0
        if args.command == "retire":
            lesson = retire(root, args.lesson_id, args.reason)
            if args.json:
                _print_json({"ok": True, "lesson": lesson})
            else:
                print(f"retired: {lesson['id']}")
            return 0
        if args.command == "list":
            items = list_lessons(root, args.privacy, args.status)
            if args.json:
                _print_json({"ok": True, "count": len(items), "lessons": items})
            else:
                _print_search(items)
            return 0
        if args.command == "check":
            result = validate(root)
            if args.json:
                _print_json(result)
            else:
                print(
                    "memory: {} public / {} local · ok={}".format(
                        result["counts"]["public"], result["counts"]["local"], result["ok"]
                    )
                )
                for warning in result["warnings"]:
                    print(f"warn: {warning}", file=sys.stderr)
                for error in result["errors"]:
                    print(f"ERROR: {error}", file=sys.stderr)
            return 0 if result["ok"] else 1
        if args.command == "index":
            layers = PRIVACY if args.privacy == "all" else (args.privacy,)
            paths = [str(rebuild_index(root, layer)) for layer in layers]
            if args.json:
                _print_json({"ok": True, "indexes": paths})
            else:
                for path in paths:
                    print(f"index: {path}")
            return 0
        parser.print_help(sys.stderr)
        return 2
    except MemoryUsageError as exc:
        if getattr(args, "json", False):
            _print_json({"ok": False, "error": {"type": "usage", "message": str(exc)}})
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except MemoryStoreError as exc:
        if getattr(args, "json", False):
            _print_json({"ok": False, "error": {"type": "memory", "message": str(exc)}})
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        if getattr(args, "json", False):
            _print_json({"ok": False, "error": {"type": "io", "message": str(exc)}})
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
