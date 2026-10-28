"""AI 深化分析（enrichment）的校验、合并与重新渲染。

Agent 在 scan 之后对未命中规则的条目做受限的只读探索，把结论写成
``enrichment.json``；本模块校验该文件、把展示字段合并回扫描条目并重新
渲染报告。安全边界：enrichment 只允许写展示信息（category/title/
description/language）与参考建议（advice），绝不触碰 selectable /
recommendation / method 等删除安全属性。
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from disk_cleanup.model import (
    ADVICE_LEVELS,
    CONFIDENCE_LEVELS,
    GROUPS,
    LANGUAGES,
    NATURES,
    Entry,
    ScanResult,
    ScanStats,
    classify_group,
    classify_nature,
)
from disk_cleanup.report import write_scan_outputs
from disk_cleanup.winutil import normalize

ENRICHMENT_SCHEMA = 1
ENRICHABLE_FIELDS = ("category", "title", "description", "language", "advice", "group", "nature")


class EnrichError(Exception):
    """Invalid or unusable enrichment (exit code 2)."""


def load_enrichment(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise EnrichError(f"深化分析文件不存在：{path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnrichError(f"读取 enrichment.json 失败：{exc}") from exc
    if not isinstance(data, dict):
        raise EnrichError("enrichment.json 顶层必须是对象。")
    if str(data.get("skill", "windows-disk-cleanup")) not in ("", "windows-disk-cleanup"):
        raise EnrichError("enrichment.json 来自其他工具，拒绝执行。")
    try:
        schema = int(data.get("schema", ENRICHMENT_SCHEMA) or ENRICHMENT_SCHEMA)
    except (TypeError, ValueError):
        raise EnrichError("enrichment.json 的 schema 不是整数。")
    if schema != ENRICHMENT_SCHEMA:
        raise EnrichError(f"不支持的 enrichment schema：{schema}（当前支持 {ENRICHMENT_SCHEMA}）。")
    if not data.get("scan_id"):
        raise EnrichError("enrichment.json 缺少 scan_id。")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise EnrichError("enrichment.json 的 entries 为空；没有分析结论就无需应用。")
    return data


def validate_enrichment(
    enrichment: Dict[str, Any], scan: Dict[str, Any]
) -> List[str]:
    errors: List[str] = []
    if str(enrichment.get("scan_id")) != str(scan.get("scan_id")):
        errors.append(f"scan_id 不一致（enrichment={enrichment.get('scan_id')!r}，scan={scan.get('scan_id')!r}）")
    scan_paths = {normalize(str(e.get("path", ""))) for e in scan.get("entries", []) if isinstance(e, dict)}
    for index, item in enumerate(enrichment.get("entries", [])):
        prefix = f"entries[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: 不是对象")
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            errors.append(f"{prefix}: 缺少 path")
            continue
        if normalize(path) not in scan_paths:
            errors.append(f"{prefix}: path 不在扫描结果中（{path}）")
        if not any(str(item.get(f, "") or "").strip() for f in ENRICHABLE_FIELDS):
            errors.append(f"{prefix}: 至少要填一个展示字段（category/title/description/language/advice）")
        language = str(item.get("language", "") or "")
        if language and language not in LANGUAGES:
            errors.append(f"{prefix}: language 非法（{language}）")
        group = str(item.get("group", "") or "")
        if group and group not in GROUPS:
            errors.append(f"{prefix}: group 非法（{group}）")
        nature = str(item.get("nature", "") or "")
        if nature and nature not in NATURES:
            errors.append(f"{prefix}: nature 非法（{nature}）")
        advice = str(item.get("advice", "") or "")
        if advice and advice not in ADVICE_LEVELS:
            errors.append(f"{prefix}: advice 非法（{advice}；只支持 safe/caution/keep）")
        confidence = str(item.get("confidence", "") or "")
        if confidence and confidence not in CONFIDENCE_LEVELS:
            errors.append(f"{prefix}: confidence 非法（{confidence}）")
        evidence = item.get("evidence", [])
        if evidence is not None and (not isinstance(evidence, list) or any(not isinstance(x, str) for x in evidence)):
            errors.append(f"{prefix}: evidence 必须是字符串数组")
    return errors


def _entry_from_dict(data: Dict[str, Any]) -> Entry:
    fields = {f.name for f in dataclasses.fields(Entry)}
    return Entry(**{k: v for k, v in data.items() if k in fields})


def _scan_result_from_dict(scan: Dict[str, Any]) -> ScanResult:
    stats_fields = {f.name for f in dataclasses.fields(ScanStats)}
    stats_raw = scan.get("stats", {}) or {}
    entries = [_entry_from_dict(e) for e in scan.get("entries", []) if isinstance(e, dict)]
    for entry in entries:
        # 兼容 0.4.x 的 scan.json：尚无分类三维时按 category/scope 补算。
        if not entry.group:
            entry.group = classify_group(entry.category, entry.scope)
        if not entry.nature:
            entry.nature = classify_nature(entry.category)
    return ScanResult(
        schema=scan.get("schema", 1),
        scan_id=str(scan.get("scan_id", "")),
        root=str(scan.get("root", "")),
        root_display=str(scan.get("root_display") or scan.get("root", "")),
        output_dir=str(scan.get("output_dir", "")),
        started_at=str(scan.get("started_at", "")),
        finished_at=str(scan.get("finished_at", "")),
        duration_s=float(scan.get("duration_s", 0) or 0),
        volume=scan.get("volume", {}) or {},
        environment=scan.get("environment", {}) or {},
        options=scan.get("options", {}) or {},
        stats=ScanStats(**{k: stats_raw[k] for k in stats_fields if stats_raw.get(k) is not None}),
        entries=entries,
        notes=list(scan.get("notes", []) or []),
        rules_version=str(scan.get("rules_version", "")),
        errors=list(scan.get("errors", []) or []),
    )


def apply_enrichment(
    scan: Dict[str, Any], enrichment: Dict[str, Any]
) -> Tuple[ScanResult, int, int]:
    """Merge display fields into scan entries and return the rebuilt ScanResult.

    Tier rules (the only place AI may touch a deletion-related field):
    - Only ``review`` entries can be re-tiered, and only with ``confidence=high``.
    - ``advice=keep`` makes the entry non-selectable (narrowing is always safe).
    - Everything else stays rule-decided; AI can never widen what is deletable.
    """
    by_path = {normalize(str(e.get("path", ""))): e for e in scan.get("entries", []) if isinstance(e, dict)}
    applied = 0
    retiered = 0
    for item in enrichment.get("entries", []):
        if not isinstance(item, dict):
            continue
        target = by_path.get(normalize(str(item.get("path", ""))))
        if target is None:
            continue
        for field in ENRICHABLE_FIELDS:
            value = str(item.get(field, "") or "").strip()
            if value:
                target[field] = value
        evidence = item.get("evidence")
        if isinstance(evidence, list):
            target["evidence"] = [str(x) for x in evidence if str(x).strip()]
        confidence = str(item.get("confidence", "") or "")
        target["confidence"] = confidence
        target["enriched"] = True
        advice = str(item.get("advice", "") or "").strip()
        if advice and confidence == "high" and target.get("recommendation") == "review":
            target["recommendation"] = advice
            target["tier_source"] = "ai"
            if advice == "keep":
                target["selectable"] = False
            retiered += 1
        applied += 1
    result = _scan_result_from_dict(scan)
    note = f"已应用 AI 深化分析：{applied} 条补充了分类与说明"
    if retiered:
        note += f"，其中 {retiered} 条高置信判定将「待定」提升为明确档位（不再需要 --allow-review）"
    result.notes.append(note + "。")
    return result, applied, retiered


def write_enriched_outputs(
    scan: Dict[str, Any],
    enrichment: Dict[str, Any],
    output_dir: str,
    max_entries: int = 1500,
    enrichment_source: str = "",
) -> Dict[str, Any]:
    result, applied, retiered = apply_enrichment(scan, enrichment)
    outputs = write_scan_outputs(result, output_dir, max_entries=max_entries)
    # 溯源：notes 带摘要，enrichment.json 原样留一份在输出目录供审计。
    if enrichment_source:
        copy = Path(output_dir) / "enrichment.json"
        try:
            copy.write_text(json.dumps(enrichment, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
    return {
        "applied": applied,
        "retiered": retiered,
        "scan_json": outputs["scan_json"],
        "report_html": outputs["report_html"],
        "enrichment_json": enrichment_source,
    }
