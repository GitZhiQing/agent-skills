"""HTML/JSON report rendering."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from disk_cleanup.model import (
    ADVICE_LABELS,
    GROUP_LABELS,
    NATURE_LABELS,
    RECOMMENDATION_LABELS,
    RECOMMENDATION_SHORT,
    ROLE_LABELS,
    SCOPE_LABELS,
    DeleteResult,
    Entry,
    ScanResult,
)
from disk_cleanup.rules import asset_file
from disk_cleanup.winutil import (
    display_time,
    human_count,
    human_size,
    iso_now,
    normalize,
)

STATUS_LABELS = {
    "pending": "待处理",
    "deleted": "已删除",
    "moved_to_recycle_bin": "已移入回收站",
    "partial": "部分删除",
    "failed": "失败",
    "skipped_missing": "已不存在",
    "skipped_covered": "被父目录覆盖",
    "skipped_reparse": "链接已跳过",
    "dry_run": "仅预演",
}

STATUS_CLASS = {
    "deleted": "ok",
    "moved_to_recycle_bin": "ok",
    "partial": "warn",
    "failed": "bad",
    "skipped_missing": "muted",
    "skipped_covered": "muted",
    "skipped_reparse": "muted",
    "pending": "muted",
    "dry_run": "muted",
}


def _entry_sort_key(entry: Entry) -> Tuple[int, int, int, str]:
    return (
        0 if entry.is_root else (1 if entry.is_top_level else 2),
        0 if entry.role in ("data", "cleanup", "file") else 1,
        -(entry.size or 0),
        entry.path.lower(),
    )


def select_report_entries(entries: List[Entry], max_entries: int) -> Tuple[List[Entry], int]:
    """Pick the entries embedded in the HTML, keeping the page small.

    The full list stays in ``scan.json``.  Mandatory entries are top-level
    directories, user-data folders and every known safe/caution item; remaining
    slots go to the largest review/keep entries.
    """
    base: List[Entry] = []
    actionable: List[Entry] = []
    optional: List[Entry] = []
    seen = set()
    for entry in entries:
        key = entry.path.lower()
        if key in seen:
            continue
        seen.add(key)
        if entry.is_root or entry.is_top_level or entry.role == "data":
            base.append(entry)
        elif entry.recommendation in ("suggest", "safe", "caution"):
            actionable.append(entry)
        else:
            optional.append(entry)
    base.sort(key=_entry_sort_key)
    actionable.sort(key=lambda e: (-(e.size or 0), e.path.lower()))
    optional.sort(key=lambda e: (-(e.size or 0), e.path.lower()))
    selected = base + actionable + optional
    if len(selected) > max_entries:
        selected = selected[:max_entries]
    selected.sort(key=_entry_sort_key)
    return selected, max(0, len(entries) - len(selected))


def _deepest_selectable(entries: List[Entry]) -> List[Entry]:
    """Drop selected parents that contain another selectable entry.

    This keeps the dashboard from counting ``project/`` and
    ``project/node_modules/`` as two separate wins.
    """
    candidates = [e for e in entries if e.selectable and e.size]
    keys = {normalize(e.path) for e in candidates}
    has_descendant = set()
    for entry in candidates:
        parent = os.path.dirname(normalize(entry.path))
        while parent:
            if parent in keys:
                has_descendant.add(parent)
            next_parent = os.path.dirname(parent)
            if next_parent == parent:
                break
            parent = next_parent
    return [e for e in candidates if normalize(e.path) not in has_descendant]


def summarize_entries(entries: Iterable[Entry]) -> Dict[str, Any]:
    all_entries = list(entries)
    counts = {key: 0 for key in RECOMMENDATION_LABELS}
    byte_counts = {key: 0 for key in RECOMMENDATION_LABELS}
    selectable = 0
    known_actionable = 0
    for entry in all_entries:
        rec = entry.recommendation
        counts[rec] = counts.get(rec, 0) + 1
        if entry.selectable:
            selectable += 1
            if entry.role in ("cleanup", "data", "file"):
                known_actionable += 1
    for entry in _deepest_selectable(all_entries):
        rec = entry.recommendation
        byte_counts[rec] = byte_counts.get(rec, 0) + (entry.size or 0)
    largest = sorted(
        _deepest_selectable(all_entries),
        key=lambda e: -(e.size or 0),
    )[:8]
    return {
        "counts": counts,
        "bytes": byte_counts,
        "selectable": selectable,
        "known_actionable": known_actionable,
        "suggest_bytes": byte_counts.get("suggest", 0),
        "safe_bytes": byte_counts.get("safe", 0),
        "caution_bytes": byte_counts.get("caution", 0),
        "review_bytes": byte_counts.get("review", 0),
        "suggest_count": counts.get("suggest", 0),
        "safe_count": counts.get("safe", 0),
        "caution_count": counts.get("caution", 0),
        "review_count": counts.get("review", 0),
        "keep_count": counts.get("keep", 0),
        "largest": [
            {
                "path": e.path,
                "title": e.title,
                "size_h": human_size(e.size),
                "recommendation": e.recommendation,
            }
            for e in largest
        ],
    }


def _entry_for_js(entry: Entry) -> Dict[str, Any]:
    data = entry.to_dict()
    data.update(
        {
            "size_h": human_size(entry.size),
            "files_h": human_count(entry.files),
            "mtime_display": display_time(entry.mtime),
            "recommendation_label": RECOMMENDATION_LABELS.get(
                entry.recommendation, entry.recommendation
            ),
            "recommendation_short": RECOMMENDATION_SHORT.get(
                entry.recommendation, entry.recommendation
            ),
            "role_label": ROLE_LABELS.get(entry.role, entry.role),
            "scope_label": SCOPE_LABELS.get(entry.scope, entry.scope),
            "group_label": GROUP_LABELS.get(entry.group, ""),
            "nature_label": NATURE_LABELS.get(entry.nature, ""),
            "advice_label": ADVICE_LABELS.get(entry.advice, ""),
            "is_actionable": entry.selectable
            and entry.recommendation in ("suggest", "safe", "caution", "review"),
        }
    )
    return data


def _volume_for_js(volume: Dict[str, Any]) -> Dict[str, Any]:
    total = volume.get("total")
    free = volume.get("free")
    used = volume.get("used")
    pct = None
    if isinstance(total, int) and total > 0 and isinstance(used, int):
        pct = round(used * 100.0 / total, 1)
    return {
        **volume,
        "total_h": human_size(total if isinstance(total, int) else None),
        "free_h": human_size(free if isinstance(free, int) else None),
        "used_h": human_size(used if isinstance(used, int) else None),
        "used_pct": pct,
    }


def _safe_json(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # Avoid breaking out of the inline <script> element.
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _render(template_name: str, title: str, data: Dict[str, Any], output: Path) -> None:
    template_path = asset_file(template_name)
    with open(template_path, "r", encoding="utf-8") as handle:
        template = handle.read()
    html = (
        template.replace("__TITLE__", _html_escape(title))
        .replace("/*__WINDOWS_DISK_CLEANUP_DATA__*/", _safe_json(data))
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_scan_outputs(
    scan: ScanResult, output_dir: str, max_entries: int = 1500
) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    scan.output_dir = str(out)
    scan_json = out / "scan.json"
    report_entries, omitted = select_report_entries(scan.entries, max_entries)
    scan.omitted_entries = omitted
    with open(scan_json, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(scan.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    summary = summarize_entries(scan.entries)
    report_html = out / "report.html"
    data = {
        "kind": "scan",
        "generated_at": iso_now(),
        "meta": {
            "scan_id": scan.scan_id,
            "root": scan.root,
            "root_display": scan.root_display,
            "started_at": scan.started_at,
            "finished_at": scan.finished_at,
            "duration_s": scan.duration_s,
            "volume": _volume_for_js(scan.volume),
            "environment": scan.environment,
            "stats": scan.stats.to_dict(),
            "notes": list(scan.notes)
            + ["摘要卡片按最深可清理项合计，避免父子目录重复计数；表格仍逐条列出。"],
            "errors": scan.errors[:50],
            "rules_version": scan.rules_version,
            "omitted_entries": omitted,
            "entry_count": len(scan.entries),
            "scan_file": str(scan_json),
            "report_file": str(report_html),
        },
        "summary": summary,
        "entries": [_entry_for_js(e) for e in report_entries],
    }
    _render("report.template.html", f"磁盘扫描报告 · {scan.root_display}", data, report_html)
    return {"scan_json": str(scan_json), "report_html": str(report_html)}


def write_cleanup_outputs(
    result: DeleteResult,
    output_dir: str,
    scan_display: str,
    rules_version: str = "",
) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cleanup_json = out / "cleanup.json"
    with open(cleanup_json, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    data = result.to_dict()
    data["generated_at"] = iso_now()
    data["root_display"] = scan_display
    data["rules_version"] = rules_version
    data["volume_before"] = _volume_for_js(result.volume_before)
    data["volume_after"] = _volume_for_js(result.volume_after)
    for item in data["items"]:
        item["size_h"] = human_size(item.get("size"))
        item["freed_h"] = human_size(item.get("freed"))
        item["status_label"] = STATUS_LABELS.get(item.get("status", ""), item.get("status", ""))
        item["status_class"] = STATUS_CLASS.get(item.get("status", ""), "muted")
        item["recommendation_label"] = RECOMMENDATION_LABELS.get(
            item.get("recommendation", ""), item.get("recommendation", "")
        )
    data["summary"]["moved_bytes_h"] = human_size(data["summary"].get("moved_bytes"))
    data["summary"]["volume_freed_h"] = human_size(data["summary"].get("volume_freed"))
    cleanup_html = out / "cleanup-report.html"
    _render(
        "cleanup.template.html",
        f"清理报告 · {scan_display}",
        data,
        cleanup_html,
    )
    return {"cleanup_json": str(cleanup_json), "cleanup_html": str(cleanup_html)}
