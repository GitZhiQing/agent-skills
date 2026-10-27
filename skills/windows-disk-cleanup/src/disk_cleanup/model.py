"""Shared data model and user-facing labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RECOMMENDATIONS = ("safe", "caution", "review", "keep")
RULE_MODES = ("leaf", "skip", "container", "normal")
METHODS = ("recycle", "permanent", "manual")
TARGETS = ("dir", "file", "any")
ROLES = ("overview", "cleanup", "data", "large", "file")

RECOMMENDATION_LABELS = {
    "safe": "安全清理",
    "caution": "谨慎清理",
    "review": "待确认",
    "keep": "保留",
}

RECOMMENDATION_SHORT = {
    "safe": "可删",
    "caution": "慎删",
    "review": "确认",
    "keep": "保留",
}

ROLE_LABELS = {
    "overview": "目录总览",
    "cleanup": "已知清理项",
    "data": "用户数据",
    "large": "大型目录",
    "file": "文件",
}

SCOPE_LABELS = {
    "system": "系统",
    "user": "用户",
    "app": "应用",
    "dev": "开发",
    "project": "项目",
    "data": "数据",
    "virtual": "虚拟机/容器",
}


@dataclass
class Entry:
    path: str
    name: str
    kind: str = "dir"
    role: str = "cleanup"
    is_top_level: bool = False
    is_root: bool = False
    size: Optional[int] = None
    files: Optional[int] = None
    dirs: Optional[int] = None
    partial: bool = False
    size_known: bool = True
    mtime: Optional[str] = None
    rule_id: Optional[str] = None
    title: str = ""
    category: str = "其他"
    scope: str = "data"
    description: str = ""
    action: str = ""
    risk: str = ""
    recommendation: str = "review"
    selectable: bool = True
    method: str = "recycle"
    requires_admin: bool = False
    depth: int = 1
    reparse: bool = False
    classification: str = "generic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "role": self.role,
            "is_top_level": self.is_top_level,
            "is_root": self.is_root,
            "size": self.size,
            "files": self.files,
            "dirs": self.dirs,
            "partial": self.partial,
            "size_known": self.size_known,
            "mtime": self.mtime,
            "rule_id": self.rule_id,
            "title": self.title,
            "category": self.category,
            "scope": self.scope,
            "description": self.description,
            "action": self.action,
            "risk": self.risk,
            "recommendation": self.recommendation,
            "selectable": self.selectable,
            "method": self.method,
            "requires_admin": self.requires_admin,
            "depth": self.depth,
            "reparse": self.reparse,
            "classification": self.classification,
        }


@dataclass
class ScanStats:
    dirs: int = 0
    files: int = 0
    bytes: int = 0
    errors: int = 0
    reparse_skipped: int = 0
    excluded: int = 0
    pruned: int = 0
    partial: bool = False

    def add(self, other: "ScanStats") -> None:
        self.dirs += other.dirs
        self.files += other.files
        self.bytes += other.bytes
        self.errors += other.errors
        self.reparse_skipped += other.reparse_skipped
        self.excluded += other.excluded
        self.pruned += other.pruned
        self.partial = self.partial or other.partial

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dirs": self.dirs,
            "files": self.files,
            "bytes": self.bytes,
            "errors": self.errors,
            "reparse_skipped": self.reparse_skipped,
            "excluded": self.excluded,
            "pruned": self.pruned,
            "partial": self.partial,
        }


@dataclass
class ScanResult:
    schema: int
    scan_id: str
    root: str
    root_display: str
    output_dir: str
    started_at: str
    finished_at: str
    duration_s: float
    volume: Dict[str, Any]
    environment: Dict[str, Any]
    options: Dict[str, Any]
    stats: ScanStats
    entries: List[Entry]
    notes: List[str] = field(default_factory=list)
    omitted_entries: int = 0
    rules_version: str = ""
    errors: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "scan_id": self.scan_id,
            "root": self.root,
            "root_display": self.root_display,
            "output_dir": self.output_dir,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "volume": self.volume,
            "environment": self.environment,
            "options": self.options,
            "stats": self.stats.to_dict(),
            "entries": [e.to_dict() for e in self.entries],
            "notes": self.notes,
            "omitted_entries": self.omitted_entries,
            "rules_version": self.rules_version,
            "errors": self.errors,
        }


@dataclass
class DeleteItem:
    path: str
    title: str = ""
    category: str = ""
    recommendation: str = ""
    size: Optional[int] = None
    status: str = "pending"
    freed: int = 0
    error: str = ""
    covered_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "category": self.category,
            "recommendation": self.recommendation,
            "size": self.size,
            "status": self.status,
            "freed": self.freed,
            "error": self.error,
            "covered_by": self.covered_by,
        }


@dataclass
class DeleteResult:
    schema: int
    scan_id: str
    root: str
    mode: str
    started_at: str
    finished_at: str
    duration_s: float
    dry_run: bool
    confirmed: bool
    volume_before: Dict[str, Any]
    volume_after: Dict[str, Any]
    items: List[DeleteItem]
    notes: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        deleted = sum(1 for i in self.items if i.status in ("deleted", "moved_to_recycle_bin"))
        partial = sum(1 for i in self.items if i.status == "partial")
        failed = sum(1 for i in self.items if i.status == "failed")
        skipped = sum(1 for i in self.items if i.status.startswith("skipped"))
        moved = sum(i.freed for i in self.items)
        before_free = self.volume_before.get("free")
        after_free = self.volume_after.get("free")
        volume_freed = None
        if isinstance(before_free, int) and isinstance(after_free, int):
            volume_freed = max(0, after_free - before_free)
        return {
            "selected": len(self.items),
            "deleted": deleted,
            "partial": partial,
            "failed": failed,
            "skipped": skipped,
            "moved_bytes": moved,
            "volume_freed": volume_freed,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "scan_id": self.scan_id,
            "root": self.root,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "dry_run": self.dry_run,
            "confirmed": self.confirmed,
            "volume_before": self.volume_before,
            "volume_after": self.volume_after,
            "summary": self.summary(),
            "items": [i.to_dict() for i in self.items],
            "notes": self.notes,
        }
