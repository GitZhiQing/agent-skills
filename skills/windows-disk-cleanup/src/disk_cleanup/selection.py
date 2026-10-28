"""Parse and validate the selection JSON copied from the HTML report."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from disk_cleanup.safety import protected_reason
from disk_cleanup.winutil import (
    display_path,
    is_reparse_path,
    is_subpath,
    normalize,
)


class SelectionError(Exception):
    """Invalid or unusable selection (exit code 2)."""


MODES = {"recycle", "permanent"}
SELECTION_SCHEMAS = (1, 2)
_MODE_ALIASES = {
    "回收站": "recycle",
    "移入回收站": "recycle",
    "recycle": "recycle",
    "彻底删除": "permanent",
    "永久删除": "permanent",
    "permanent": "permanent",
}


@dataclass
class Selection:
    scan_id: str
    paths: List[str]
    mode: str = "recycle"
    modes: Dict[str, str] = field(default_factory=dict)
    confirmed: bool = False
    scan_file: str = ""
    root: str = ""
    skill: str = "windows-disk-cleanup"
    schema: int = 1
    source: str = ""


@dataclass
class ValidationResult:
    scan_id: str
    root: str
    mode: str
    confirmed: bool
    paths: List[str]
    planned: List[Dict[str, Any]] = field(default_factory=list)
    covered: List[Dict[str, str]] = field(default_factory=list)
    invalid: List[Dict[str, str]] = field(default_factory=list)
    missing: List[Dict[str, str]] = field(default_factory=list)
    review: List[str] = field(default_factory=list)
    caution: List[str] = field(default_factory=list)
    estimated_bytes: int = 0

    @property
    def requires_allow_review(self) -> bool:
        return bool(self.review)

    @property
    def mode_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in self.planned:
            mode = str(item.get("mode", "recycle"))
            counts[mode] = counts.get(mode, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "root": self.root,
            "mode": self.mode,
            "confirmed": self.confirmed,
            "selected": len(self.paths),
            "planned": self.planned,
            "covered": self.covered,
            "invalid": self.invalid,
            "missing": self.missing,
            "review": self.review,
            "caution": self.caution,
            "estimated_bytes": self.estimated_bytes,
            "requires_allow_review": self.requires_allow_review,
        }


def extract_json(text: str) -> Dict[str, Any]:
    """Extract the first JSON object that contains a ``paths`` key."""
    if not text or not text.strip():
        raise SelectionError("选择内容为空。请从报告页点击「复制选中路径」后再粘贴。")
    cleaned = text.lstrip("\ufeff").strip()
    decoder = json.JSONDecoder()
    candidates: List[Any] = []
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            candidates.append(json.loads(fenced.group(1)))
        except json.JSONDecodeError:
            pass
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        candidates.append(obj)
    for candidate in candidates:
        if isinstance(candidate, dict) and "paths" in candidate:
            return candidate
    raise SelectionError(
        "没有识别到选择 JSON。请在报告页勾选后点击「复制选中路径」，"
        "把完整的代码块粘贴回来（不要只粘贴路径列表）。"
    )


def load_selection(path: str) -> Selection:
    p = Path(path)
    if not p.exists():
        raise SelectionError(f"选择文件不存在：{path}")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SelectionError(f"读取选择文件失败：{exc}") from exc
    data = extract_json(text)
    skill = str(data.get("skill", "windows-disk-cleanup"))
    if skill not in ("", "windows-disk-cleanup"):
        raise SelectionError(f"选择 JSON 来自其他工具（{skill}），拒绝执行。")
    try:
        schema = int(data.get("schema", 1) or 1)
    except (TypeError, ValueError):
        raise SelectionError("选择 JSON 的 schema 不是整数。")
    if schema not in SELECTION_SCHEMAS:
        raise SelectionError(
            f"不支持的选择 schema：{schema}（当前支持 {'/'.join(str(s) for s in SELECTION_SCHEMAS)}）。"
        )
    scan_id = str(data.get("scan_id", "")).strip()
    if not scan_id:
        raise SelectionError("选择 JSON 缺少 scan_id；请重新从报告页复制。")
    raw_paths = data.get("paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise SelectionError("选择 JSON 的 paths 为空；请至少勾选一个条目。")
    paths: List[str] = []
    seen = set()
    for item in raw_paths:
        if not isinstance(item, str) or not item.strip():
            raise SelectionError("paths 中存在非字符串或空路径。")
        text_path = item.strip().strip('"')
        key = normalize(text_path)
        if key in seen:
            continue
        seen.add(key)
        paths.append(text_path)
    if len(paths) > 5000:
        raise SelectionError("选择条目超过 5000 条；请分批处理。")
    mode_raw = str(data.get("mode", "recycle")).strip().lower()
    mode = _MODE_ALIASES.get(mode_raw, _MODE_ALIASES.get(str(data.get("mode", "")).strip(), "recycle"))
    if mode not in MODES:
        raise SelectionError(f"删除方式非法：{data.get('mode')!r}（只支持 recycle / permanent）。")
    modes: Dict[str, str] = {}
    if schema >= 2 and data.get("modes") is not None:
        raw_modes = data.get("modes")
        if not isinstance(raw_modes, dict):
            raise SelectionError("modes 必须是「路径 -> 删除方式」的对象。")
        for raw_path, raw_mode in raw_modes.items():
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise SelectionError("modes 中存在非法路径键。")
            normalized_mode = _MODE_ALIASES.get(str(raw_mode).strip().lower(), str(raw_mode).strip())
            if normalized_mode not in MODES:
                raise SelectionError(
                    f"删除方式非法：{raw_mode!r}（只支持 recycle / permanent）。"
                )
            # paths 之外的键无害，直接忽略。
            modes[normalize(raw_path.strip().strip('"'))] = normalized_mode
    confirmed_raw = data.get("confirmed", False)
    confirmed = confirmed_raw is True or str(confirmed_raw).strip().lower() in ("1", "true", "yes")
    return Selection(
        scan_id=scan_id,
        paths=paths,
        mode=mode,
        modes=modes,
        confirmed=confirmed,
        scan_file=str(data.get("scan_file", "") or ""),
        root=str(data.get("root", "") or ""),
        skill=skill or "windows-disk-cleanup",
        schema=schema,
        source=str(p),
    )


def load_scan(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise SelectionError(f"扫描结果不存在：{path}。请重新扫描或指定 --scan。")
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectionError(f"读取 scan.json 失败：{exc}") from exc
    if not isinstance(data, dict):
        raise SelectionError("scan.json 格式非法：顶层不是对象。")
    try:
        schema = int(data.get("schema", 0) or 0)
    except (TypeError, ValueError):
        schema = 0
    if schema != 1:
        raise SelectionError("scan.json schema 不是 1；请用当前版本重新扫描。")
    if not data.get("scan_id") or not data.get("root") or not isinstance(data.get("entries"), list):
        raise SelectionError("scan.json 缺少 scan_id/root/entries。")
    return data


def resolve_scan_file(
    selection: Selection, selection_file: str, explicit_scan: Optional[str] = None
) -> str:
    if explicit_scan:
        candidate = Path(explicit_scan)
    elif selection.scan_file:
        candidate = Path(selection.scan_file)
        if not candidate.is_absolute():
            candidate = Path(selection_file).resolve().parent / candidate
    else:
        candidate = Path(selection_file).resolve().parent / "scan.json"
    return str(candidate)


def _entry_map(scan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for entry in scan.get("entries", []):
        if isinstance(entry, dict) and entry.get("path"):
            result[normalize(str(entry["path"]))] = entry
    return result


def validate_selection(
    scan: Dict[str, Any],
    selection: Selection,
    mode_override: Optional[str] = None,
) -> ValidationResult:
    if str(scan.get("scan_id")) != selection.scan_id:
        raise SelectionError(
            "选择与扫描结果不匹配（scan_id 不一致）。"
            "请重新打开本次扫描的 report.html，勾选后重新复制。"
        )
    root = str(scan.get("root", ""))
    if not root:
        raise SelectionError("scan.json 缺少 root。")
    mode = mode_override or selection.mode
    if mode not in MODES:
        raise SelectionError(f"删除方式非法：{mode}")
    result = ValidationResult(
        scan_id=selection.scan_id,
        root=root,
        mode=mode,
        confirmed=selection.confirmed,
        paths=list(selection.paths),
    )
    entries = _entry_map(scan)
    accepted_paths: List[str] = []
    for raw in selection.paths:
        if not os.path.isabs(raw):
            result.invalid.append({"path": raw, "reason": "不是绝对路径"})
            continue
        path = display_path(os.path.abspath(raw))
        if not is_subpath(path, root):
            result.invalid.append({"path": path, "reason": "不在本次扫描根目录内"})
            continue
        entry = entries.get(normalize(path))
        if entry is None:
            result.invalid.append(
                {"path": path, "reason": "不在本次扫描结果中（路径写错、扫描过期或已被移动）"}
            )
            continue
        if not entry.get("selectable", False):
            result.invalid.append(
                {
                    "path": path,
                    "reason": f"报告标记为不可删除（{entry.get('recommendation', 'keep')}）",
                }
            )
            continue
        if entry.get("recommendation") == "keep":
            result.invalid.append({"path": path, "reason": "报告建议保留"})
            continue
        reason = protected_reason(path)
        if reason:
            result.invalid.append({"path": path, "reason": reason})
            continue
        if is_reparse_path(path):
            result.invalid.append({"path": path, "reason": "符号链接/目录联接，不能删除"})
            continue
        # A parent selection covers its children; only delete the parent.
        ancestor = None
        for existing in accepted_paths:
            if is_subpath(path, existing):
                ancestor = existing
                break
        if ancestor:
            result.covered.append({"path": path, "covered_by": ancestor})
            continue
        # If a newly accepted path is a parent of an earlier one (defensive),
        # drop the children from the plan.
        children = [p for p in accepted_paths if is_subpath(p, path)]
        if children:
            for child in children:
                result.covered.append({"path": child, "covered_by": path})
            result.planned = [
                item for item in result.planned if normalize(item["path"]) not in {normalize(c) for c in children}
            ]
            accepted_paths = [p for p in accepted_paths if normalize(p) not in {normalize(c) for c in children}]
        accepted_paths.append(path)
        # Per-path mode: an explicit --mode override beats everything,
        # then the selection's per-path overrides, then the global default.
        if mode_override:
            item_mode = mode_override
        else:
            item_mode = selection.modes.get(normalize(path), mode)
        result.planned.append(
            {
                "path": path,
                "title": entry.get("title", ""),
                "category": entry.get("category", ""),
                "recommendation": entry.get("recommendation", ""),
                "size": entry.get("size"),
                "selectable": True,
                "mode": item_mode,
            }
        )
        if entry.get("recommendation") == "review":
            result.review.append(path)
        elif entry.get("recommendation") == "caution":
            result.caution.append(path)
        if not os.path.exists(path):
            result.missing.append({"path": path, "reason": "当前已不存在（可能已被手动删除）"})
    covered_paths = {normalize(item["path"]) for item in result.covered}
    result.planned = [
        item for item in result.planned if normalize(item["path"]) not in covered_paths
    ]
    result.missing = [
        item for item in result.missing if normalize(item["path"]) not in covered_paths
    ]
    result.review = [p for p in result.review if normalize(p) not in covered_paths]
    result.caution = [p for p in result.caution if normalize(p) not in covered_paths]
    result.estimated_bytes = sum(
        int(item.get("size") or 0)
        for item in result.planned
        if os.path.exists(item["path"])
    )
    return result
