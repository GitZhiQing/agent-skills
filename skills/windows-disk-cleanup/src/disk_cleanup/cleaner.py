"""Deletion executor.

Only paths that passed :mod:`disk_cleanup.selection` validation reach this
module.  The executor never follows reparse points, never deletes a parent to
"fix" a locked child, and reports partial/failed deletions honestly.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from disk_cleanup import SCHEMA_VERSION
from disk_cleanup.model import DeleteItem, DeleteResult
from disk_cleanup.report import write_cleanup_outputs
from disk_cleanup.rules import asset_file
from disk_cleanup.selection import ValidationResult
from disk_cleanup.winutil import (
    display_path,
    fs_path,
    get_volume_info,
    is_reparse_entry,
    is_reparse_path,
    iso_now,
    normalize,
    parse_json_output,
    run_powershell,
)

_MAX_REPORTED_ERRORS = 30


class CleanupError(Exception):
    """Deletion could not be carried out (exit code 1)."""


def _as_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _remove_link(path: str) -> None:
    try:
        os.rmdir(path)
    except OSError:
        os.unlink(path)


def _remove_file(path: str) -> None:
    try:
        os.remove(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def _remove_dir(path: str) -> None:
    try:
        os.rmdir(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        os.rmdir(path)


def delete_file(path: str) -> Optional[str]:
    target = fs_path(path)
    try:
        _remove_file(target)
        return None
    except OSError as exc:
        return _as_error(exc)


def delete_tree(path: str) -> List[Tuple[str, str]]:
    """Delete a directory tree without following junctions/symlinks."""
    errors: List[Tuple[str, str]] = []
    root = fs_path(path)
    if is_reparse_path(path):
        try:
            _remove_link(root)
            return errors
        except OSError as exc:
            errors.append((display_path(path), _as_error(exc)))
            return errors
    stack: List[Tuple[str, bool]] = [(root, False)]
    while stack:
        current, visited = stack.pop()
        try:
            if is_reparse_path(display_path(current)):
                _remove_link(current)
                continue
            if visited:
                _remove_dir(current)
                continue
            with os.scandir(current) as scandir:
                children = list(scandir)
        except OSError as exc:
            if len(errors) < _MAX_REPORTED_ERRORS:
                errors.append((display_path(current), _as_error(exc)))
            continue
        stack.append((current, True))
        for entry in children:
            child = entry.path
            try:
                if entry.is_dir(follow_symlinks=False):
                    if is_reparse_entry(entry):
                        _remove_link(child)
                    else:
                        stack.append((child, False))
                else:
                    _remove_file(child)
            except OSError as exc:
                if len(errors) < _MAX_REPORTED_ERRORS:
                    errors.append((display_path(child), _as_error(exc)))
    return errors


def measure_size(path: str) -> int:
    if is_reparse_path(path):
        return 0
    try:
        st = os.stat(fs_path(path), follow_symlinks=False)
    except OSError:
        return 0
    if stat.S_ISREG(st.st_mode):
        return int(st.st_size)
    if not stat.S_ISDIR(st.st_mode):
        return 0
    total = 0
    stack = [fs_path(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as scandir:
                entries = list(scandir)
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not is_reparse_entry(entry):
                        stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def _summarize_errors(errors: Sequence[Tuple[str, str]]) -> str:
    if not errors:
        return ""
    head = "；".join(f"{path}: {message}" for path, message in errors[:3])
    if len(errors) > 3:
        head += f"（另有 {len(errors) - 3} 个错误）"
    return head


def recycle_paths(paths: List[str]) -> List[Dict[str, Any]]:
    """Move paths to the Recycle Bin via Windows PowerShell."""
    script = asset_file("ps/recycle.ps1")
    if not script.exists():
        raise CleanupError("缺少 PowerShell 回收站脚本 assets/ps/recycle.ps1。")
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="wdc-recycle-", delete=False, encoding="utf-8"
    )
    temp_name = handle.name
    try:
        json.dump({"paths": paths}, handle, ensure_ascii=False)
        handle.close()
        code, out, err = run_powershell(script, ["-InputFile", temp_name], timeout=1800)
        if code == 127:
            raise CleanupError("找不到 PowerShell；请改用 --mode permanent，或安装 Windows PowerShell 5.1。")
        if code != 0:
            detail = (err or out or "").strip()
            raise CleanupError(f"PowerShell 回收站操作失败（exit {code}）：{detail[:500]}")
        data = parse_json_output(out)
        if not isinstance(data, dict):
            raise CleanupError("无法解析 PowerShell 回收站结果。")
        results = data.get("results")
        if isinstance(results, dict):
            results = [results]
        if not isinstance(results, list):
            raise CleanupError("PowerShell 回收站结果缺少 results 数组。")
        return [r for r in results if isinstance(r, dict)]
    finally:
        try:
            handle.close()
        except Exception:
            pass
        try:
            os.unlink(temp_name)
        except OSError:
            pass


def _prepare_items(
    validation: ValidationResult,
) -> Tuple[List[DeleteItem], Dict[str, str]]:
    items: List[DeleteItem] = []
    missing_reasons = {normalize(m["path"]): m["reason"] for m in validation.missing}
    for plan in validation.planned:
        path = str(plan.get("path", ""))
        item = DeleteItem(
            path=path,
            title=str(plan.get("title", "")),
            category=str(plan.get("category", "")),
            recommendation=str(plan.get("recommendation", "")),
            size=plan.get("size") if isinstance(plan.get("size"), int) else None,
        )
        key = normalize(path)
        if key in missing_reasons:
            item.status = "skipped_missing"
            item.error = missing_reasons[key]
        elif is_reparse_path(path):
            item.status = "skipped_reparse"
            item.error = "符号链接/目录联接，执行时再次跳过"
        elif not os.path.exists(fs_path(path)):
            item.status = "skipped_missing"
            item.error = "执行前已不存在"
        else:
            item.status = "pending"
            if item.size is None:
                item.size = measure_size(path)
        items.append(item)
    for covered in validation.covered:
        items.append(
            DeleteItem(
                path=str(covered.get("path", "")),
                status="skipped_covered",
                covered_by=str(covered.get("covered_by", "")),
                error="被已选中的父目录覆盖，不重复删除",
            )
        )
    return items, missing_reasons


def _execute_permanent(items: List[DeleteItem]) -> None:
    for item in items:
        if item.status != "pending":
            continue
        path = item.path
        before = item.size if item.size is not None else measure_size(path)
        if not os.path.exists(fs_path(path)):
            item.status = "skipped_missing"
            item.error = "执行时已不存在"
            continue
        if is_reparse_path(path):
            item.status = "skipped_reparse"
            item.error = "符号链接/目录联接，执行时再次跳过"
            continue
        if os.path.isdir(fs_path(path)):
            errors = delete_tree(path)
            error_text = _summarize_errors(errors)
        else:
            error = delete_file(path)
            errors = [(path, error)] if error else []
            error_text = error or ""
        exists = os.path.exists(fs_path(path))
        if not exists:
            item.status = "deleted"
            item.freed = int(before or 0)
            item.error = ""
            continue
        remaining = measure_size(path)
        item.freed = max(0, int(before or 0) - int(remaining or 0))
        item.status = "partial" if item.freed > 0 else "failed"
        item.error = error_text or "目录仍存在（可能被占用、权限不足或路径过长）"


def _execute_recycle(items: List[DeleteItem]) -> None:
    pending = [i for i in items if i.status == "pending"]
    if not pending:
        return
    try:
        results = recycle_paths([i.path for i in pending])
    except CleanupError as exc:
        for item in pending:
            item.status = "failed"
            item.error = str(exc)
        return
    by_path = {normalize(str(r.get("path", ""))): r for r in results}
    for item in pending:
        result = by_path.get(normalize(item.path))
        if result is None:
            item.status = "failed"
            item.error = "PowerShell 未返回该条目的结果"
            continue
        if result.get("ok"):
            item.status = "moved_to_recycle_bin"
            item.freed = int(item.size or 0)
            item.error = ""
        else:
            message = str(result.get("error") or "移入回收站失败")
            if "no longer exists" in message.lower():
                item.status = "skipped_missing"
            else:
                item.status = "failed"
            item.error = message


def execute_cleanup(
    scan: Dict[str, Any],
    validation: ValidationResult,
    output_dir: str,
    confirmed: bool,
    rules_version: str = "",
) -> Tuple[DeleteResult, Dict[str, str]]:
    if not confirmed:
        raise CleanupError("选择尚未确认；请勾选报告页的确认框，或在聊天中明确确认后使用 --confirm。")
    if validation.invalid:
        raise CleanupError(
            "选择中有无效路径，已拒绝执行："
            + "；".join(f"{i['path']}（{i['reason']}）" for i in validation.invalid[:5])
        )
    started_at = iso_now()
    t0 = time.monotonic()
    volume_before = get_volume_info(str(scan.get("root", "")))
    items, _missing = _prepare_items(validation)
    if validation.mode == "recycle":
        _execute_recycle(items)
    else:
        _execute_permanent(items)
    volume_after = get_volume_info(str(scan.get("root", "")))
    finished_at = iso_now()
    duration = round(time.monotonic() - t0, 2)
    notes: List[str] = []
    if validation.mode == "recycle":
        notes.append("文件已移入回收站；清空回收站后才会真正释放磁盘空间。")
    else:
        notes.append("已按彻底删除模式执行；删除后不可恢复。")
    failed = sum(1 for i in items if i.status in ("failed", "partial"))
    if failed:
        notes.append(
            f"{failed} 个条目失败/部分删除：请查看错误，关闭占用程序或以管理员身份重试。"
        )
    missing = sum(1 for i in items if i.status == "skipped_missing")
    if missing:
        notes.append(f"{missing} 个条目在执行前已不存在，已跳过。")
    covered = sum(1 for i in items if i.status == "skipped_covered")
    if covered:
        notes.append(f"{covered} 个条目因父子重叠被父目录覆盖，未重复删除。")
    notes.append("已释放空间按删除前逻辑大小统计，硬链接/压缩/稀疏文件可能造成差异。")
    result = DeleteResult(
        schema=SCHEMA_VERSION,
        scan_id=str(scan.get("scan_id", "")),
        root=str(scan.get("root", "")),
        mode=validation.mode,
        started_at=started_at,
        finished_at=finished_at,
        duration_s=duration,
        dry_run=False,
        confirmed=confirmed,
        volume_before=volume_before,
        volume_after=volume_after,
        items=items,
        notes=notes,
    )
    outputs = write_cleanup_outputs(
        result, output_dir, str(scan.get("root_display") or scan.get("root") or ""), rules_version
    )
    return result, outputs
