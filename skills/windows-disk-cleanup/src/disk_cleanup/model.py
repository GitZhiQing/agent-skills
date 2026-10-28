"""Shared data model and user-facing labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RECOMMENDATIONS = ("suggest", "safe", "caution", "keep", "review")
RULE_MODES = ("leaf", "skip", "container", "normal")
METHODS = ("recycle", "permanent", "manual")
TARGETS = ("dir", "file", "any")
ROLES = ("overview", "cleanup", "data", "large", "file")
LANGUAGES = (
    "nodejs", "python", "rust", "go", "java", "dotnet", "php", "ruby",
    "swift", "cpp", "dart", "docker", "vscode", "jetbrains", "git", "ai", "tools",
)
# AI 深化分析（enrichment）允许写入的参考建议档：高置信时可提升 review 档。
ADVICE_LEVELS = ("safe", "caution", "keep")
CONFIDENCE_LEVELS = ("high", "medium", "low")
# 档位来源：空 = 规则/通用分类；ai = 由高置信 AI 判定提升。
TIER_SOURCES = ("", "ai")

ADVICE_LABELS = {
    "safe": "AI 参考 · 安全",
    "caution": "AI 参考 · 谨慎",
    "keep": "AI 参考 · 保留",
}

# --- 分类词表（三维正交，筛选的唯一依据）--------------------------------------
# 归属：这些东西属于谁。用户的心智模型是「我要清理 Chrome / npm / 系统」。
GROUPS = ("system", "app", "dev", "user", "virtual")
GROUP_LABELS = {
    "system": "系统",
    "app": "应用",
    "dev": "开发工具",
    "user": "用户文件",
    "virtual": "虚拟机",
}
# 性质：这是什么东西。与归属正交——Chrome 有缓存，npm 也有缓存。
NATURES = ("cache", "log", "build", "installer", "temp", "content", "config", "other")
NATURE_LABELS = {
    "cache": "缓存",
    "log": "日志与转储",
    "build": "构建产物",
    "installer": "安装包与更新残留",
    "temp": "临时文件",
    "content": "用户内容",
    "config": "配置与凭据",
    "other": "未识别",
}
# 规则库既有 category -> 性质。规则库是自由文本，此处收敛为受控值；
# AI 写入的新 category 走「其他」，不污染词表。
CATEGORY_NATURES = {
    "应用缓存": "cache",
    "开发工具缓存": "cache",
    "包管理器缓存": "cache",
    "浏览器缓存": "cache",
    "系统性能缓存": "cache",
    "AI/模型缓存": "cache",
    "系统日志与转储": "log",
    "项目构建产物": "build",
    "系统升级残留": "installer",
    "Windows 更新": "installer",
    "系统临时文件": "temp",
    "用户临时文件": "temp",
    "用户数据": "content",
    "凭据/配置（保留）": "config",
    "项目配置（保留）": "config",
    "系统组件（保留）": "config",
    "系统托管": "config",
    "游戏平台": "content",
    "回收站": "temp",
    "虚拟机/容器": "content",
    "其他": "other",
}
# scope -> 归属默认值；category 可覆盖（如 scope=user 的浏览器缓存仍属「应用」）。
SCOPE_GROUPS = {
    "system": "system",
    "app": "app",
    "dev": "dev",
    "project": "dev",
    "virtual": "virtual",
    "user": "user",
    "data": "user",
}
# 开发/项目类之外的这些类别，实际归属是应用或用户文件。
CATEGORY_GROUPS = {
    "浏览器缓存": "app",
    "浏览器数据": "app",
    "应用缓存": "app",
    "应用数据（含用户内容）": "app",
    "安装包缓存": "app",
    "网盘同步缓存": "app",
    "AI 应用数据": "app",
    "系统与应用支撑目录": "system",
    "用户数据": "user",
    "用户临时文件": "user",
    "凭据/配置（保留）": "user",
}

RECOMMENDATION_LABELS = {
    "suggest": "建议清理",
    "safe": "安全清理",
    "caution": "谨慎清理",
    "keep": "建议保留",
    "review": "待定",
}

RECOMMENDATION_SHORT = {
    "suggest": "建议",
    "safe": "可删",
    "caution": "慎删",
    "keep": "保留",
    "review": "待定",
}

ROLE_LABELS = {    "overview": "目录总览",
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


def classify_group(category: str, scope: str) -> str:
    """归属：category 更具体，优先；否则回落到 scope。"""
    group = CATEGORY_GROUPS.get(str(category or ""))
    if group:
        return group
    return SCOPE_GROUPS.get(str(scope or ""), "user")


def classify_nature(category: str) -> str:
    """性质：受控词表；未收录的自由文本归「其他」。"""
    return CATEGORY_NATURES.get(str(category or ""), "other")


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
    language: str = ""
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
    # 分类三维（筛选依据）：归属 / 性质 / 生态
    group: str = ""
    nature: str = ""
    # AI 深化分析（enrichment）合并进来的展示字段；删除安全属性只允许被收紧。
    enriched: bool = False
    advice: str = ""
    confidence: str = ""
    tier_source: str = ""
    evidence: List[str] = field(default_factory=list)

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
            "language": self.language,
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
            "group": self.group,
            "nature": self.nature,
            "enriched": self.enriched,
            "advice": self.advice,
            "confidence": self.confidence,
            "tier_source": self.tier_source,
            "evidence": list(self.evidence),
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
    mode: str = "recycle"
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
            "mode": self.mode,
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
