"""Filesystem scanner.

Core behaviours:

* Known cache directories are *leaves*: their size is measured once and their
  children are not itemised (that is what keeps ``node_modules`` and ``.venv``
  from exploding the report).
* Protected system trees are pruned to a small allow-list of interesting paths.
* User profiles get a second classification layer for Desktop/Documents/
  Downloads/AppData, so the report can list "data directories" with advice
  instead of treating them as generic folders.
* Reparse points (junctions/symlinks) are never followed and never selectable.
"""

from __future__ import annotations

import fnmatch
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from disk_cleanup import SCHEMA_VERSION
from disk_cleanup.model import Entry, ScanResult, ScanStats
from disk_cleanup.rules import RuleIndex, load_rules, validate_rules
from disk_cleanup.winutil import (
    display_path,
    drive_type_label,
    fs_path,
    get_volume_info,
    human_size,
    is_admin,
    is_reparse_entry,
    iso_from_timestamp,
    iso_now,
    is_subpath,
    normalize,
    path_depth,
    probe_recycle_bin,
    volume_root,
)


class ScanError(Exception):
    """Business-level scan failure (exit code 1)."""


class UsageError(Exception):
    """Bad arguments / target (exit code 2)."""


@dataclass
class ScanOptions:
    root: str
    output_dir: str = ""
    min_size: int = 50 * 1024 * 1024
    listing_depth: int = 3
    max_entries: int = 1500
    max_seconds: float = 0.0
    exclude: List[str] = field(default_factory=list)
    allow_network: bool = False
    progress: bool = False


_PROFILE_FOLDERS: Dict[str, Dict[str, str]] = {
    "desktop": {
        "title": "桌面",
        "category": "用户数据",
        "description": "当前用户的桌面文件与快捷方式。",
        "action": "保留或由用户自行整理；本工具不建议整体删除。",
        "risk": "用户数据，误删不可恢复。",
        "recommendation": "keep",
    },
    "documents": {
        "title": "文档",
        "category": "用户数据",
        "description": "当前用户的文档目录，常包含工作文件与项目资料。",
        "action": "保留或迁移到其他盘；本工具不建议整体删除。",
        "risk": "用户数据，误删不可恢复。",
        "recommendation": "keep",
    },
    "downloads": {
        "title": "下载",
        "category": "用户数据",
        "description": "浏览器/应用默认的下载目录，常堆积安装包与临时下载。",
        "action": "建议逐项筛选，只删除确认不再需要的文件；不要整体清理。",
        "risk": "用户数据，误删不可恢复。",
        "recommendation": "caution",
    },
    "pictures": {
        "title": "图片",
        "category": "用户数据",
        "description": "当前用户的图片与截图。",
        "action": "保留或迁移；本工具不建议整体删除。",
        "risk": "用户数据，误删不可恢复。",
        "recommendation": "keep",
    },
    "videos": {
        "title": "视频",
        "category": "用户数据",
        "description": "当前用户的视频文件。",
        "action": "保留或迁移；本工具不建议整体删除。",
        "risk": "用户数据，误删不可恢复。",
        "recommendation": "keep",
    },
    "music": {
        "title": "音乐",
        "category": "用户数据",
        "description": "当前用户的音乐文件。",
        "action": "保留或迁移；本工具不建议整体删除。",
        "risk": "用户数据，误删不可恢复。",
        "recommendation": "keep",
    },
    "onedrive": {
        "title": "OneDrive 同步目录",
        "category": "用户数据",
        "description": "OneDrive 同步的本地文件（可能是按需下载的占位文件）。",
        "action": "保留；需要释放空间时用 OneDrive「释放空间」，不要直接删除。",
        "risk": "删除会同时删除云端文件或造成同步冲突。",
        "recommendation": "keep",
    },
    "favorites": {
        "title": "收藏夹",
        "category": "用户数据",
        "description": "浏览器/资源管理器收藏的快捷方式。",
        "action": "保留。",
        "risk": "用户配置，删除会丢失收藏。",
        "recommendation": "keep",
    },
    "links": {
        "title": "链接",
        "category": "用户数据",
        "description": "用户配置目录中的快捷方式。",
        "action": "保留。",
        "risk": "用户配置，通常很小。",
        "recommendation": "keep",
    },
    "contacts": {
        "title": "联系人",
        "category": "用户数据",
        "description": "当前用户的联系人数据。",
        "action": "保留。",
        "risk": "用户数据，删除会丢失联系人。",
        "recommendation": "keep",
    },
    "searches": {
        "title": "搜索文件夹",
        "category": "用户数据",
        "description": "保存的搜索条件。",
        "action": "保留。",
        "risk": "用户配置，通常很小。",
        "recommendation": "keep",
    },
    "saved games": {
        "title": "保存的游戏",
        "category": "用户数据",
        "description": "部分游戏的存档与配置。",
        "action": "保留；删除前确认游戏存档已备份。",
        "risk": "可能包含不可恢复的游戏存档。",
        "recommendation": "keep",
    },
}

_VENDOR_DIRS = {"intel", "amd", "nvidia", "dell", "hp", "lenovo"}

_TOP_LEVEL_PROTECTED = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "users",
    "recovery",
    "boot",
    "system volume information",
    "$recycle.bin",
    "config.msi",
    "msocache",
}


def _now_iso() -> str:
    return iso_now()


def _make_scan_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + os.urandom(2).hex()


def _truncate(text: str, limit: int = 110) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Scanner:
    def __init__(self, options: ScanOptions, rules_data: Optional[Dict[str, Any]] = None):
        self.options = options
        self.root = os.path.abspath(display_path(options.root))
        self.root_display = display_path(self.root)
        self.root_norm = normalize(self.root)
        self.stats = ScanStats()
        self.entries: Dict[str, Entry] = {}
        self._priority: Dict[str, int] = {}
        self.errors: List[Dict[str, str]] = []
        self.notes: List[str] = []
        self.started = time.monotonic()
        self.deadline = (
            self.started + options.max_seconds if options.max_seconds and options.max_seconds > 0 else None
        )
        self.partial = False
        self._last_progress = 0.0
        self._excluded = [self._normalize_exclude(p) for p in options.exclude]
        self.rules_data = rules_data or load_rules()
        errors = validate_rules(self.rules_data)
        if errors:
            raise ScanError("规则库校验失败：" + "；".join(errors[:3]))
        self.index = RuleIndex(self.rules_data.get("rules", []), self.root)
        self.volume = get_volume_info(self.root)

    # -- public ---------------------------------------------------------------

    def scan(self) -> ScanResult:
        self._validate_root()
        scan_id = _make_scan_id()
        started_at = _now_iso()
        self.stats.dirs += 1
        root_rule = self.index.match(self.root, os.path.basename(self.root_display), True)
        if root_rule and root_rule.get("mode") in ("leaf", "skip"):
            stats = self._measure(self.root)
            self._add_rule_entry(self.root, root_rule, stats, depth=0, is_root=True)
        else:
            self._scan_root(root_rule)
        self.stats = self._total_stats()
        self._probe_recycle_bin()
        self._finish_notes()
        self._prune_nested_generic()
        finished_at = _now_iso()
        duration = round(time.monotonic() - self.started, 2)
        entries = sorted(
            self.entries.values(),
            key=lambda e: (-(e.size or 0), e.depth, e.path.lower()),
        )
        return ScanResult(
            schema=SCHEMA_VERSION,
            scan_id=scan_id,
            root=self.root,
            root_display=self.root_display,
            output_dir=self.options.output_dir,
            started_at=started_at,
            finished_at=finished_at,
            duration_s=duration,
            volume=self.volume,
            environment={
                "platform": os.name,
                "admin": is_admin(),
                "python": os.sys.version.split()[0],
                "drive_type": self.volume.get("drive_type", ""),
                "drive_type_label": drive_type_label(self.volume.get("drive_type", "")),
            },
            options={
                "min_size": self.options.min_size,
                "listing_depth": self.options.listing_depth,
                "max_entries": self.options.max_entries,
                "max_seconds": self.options.max_seconds,
                "exclude": list(self.options.exclude),
            },
            stats=self.stats,
            entries=entries,
            notes=self.notes,
            omitted_entries=0,
            rules_version=str(self.rules_data.get("updated", "")),
            errors=list(self.errors),
        )

    # -- root / top-level -----------------------------------------------------

    def _validate_root(self) -> None:
        if not os.path.isdir(self.root):
            raise UsageError(f"扫描目标不是目录或不存在：{self.root_display}")
        kind = self.volume.get("drive_type", "unknown")
        if kind == "cdrom":
            raise UsageError("扫描目标位于光驱/只读介质，无法清理。")
        if kind in ("remote", "unknown") and not self.options.allow_network:
            raise UsageError(
                f"扫描目标是 {drive_type_label(kind)}；如确认要扫描网络位置，请加 --allow-network。"
            )
        if not os.access(self.root, os.R_OK):
            raise ScanError(f"没有读取权限：{self.root_display}")

    def _scan_root(self, root_rule: Optional[Dict[str, Any]]) -> None:
        name = os.path.basename(self.root_display.rstrip("\\")).lower()
        if root_rule and root_rule.get("mode") == "container":
            self._add_rule_entry(self.root, root_rule, None, depth=0, is_root=True)
            if root_rule.get("prune") and not self.index.has_interesting_below(self.root):
                return
            flags = self._flags_for_rule(root_rule, is_root=True)
            stats = self._walk_children(
                self.root, depth=0, prune=bool(root_rule.get("prune")), **flags
            )
            self._update_entry_size(self.root, stats)
            return
        if name == "users":
            cls = self._users_classification()
            self._add_generic_entry(self.root, cls, depth=0, is_root=True)
            stats = self._walk_children(self.root, depth=0, profile_parent=True)
            self._update_entry_size(self.root, stats)
            return
        if self._looks_like_profile(self.root):
            cls = self._profile_root_classification()
            self._add_generic_entry(self.root, cls, depth=0, is_root=True)
            stats = self._walk_children(
                self.root, depth=0, profile_root=True, force_candidates=True
            )
            self._update_entry_size(self.root, stats)
            return
        cls = self._generic_classification(
            self.root,
            os.path.basename(self.root_display.rstrip("\\")) or self.root_display,
            role="overview",
            recommendation="keep",
            title="扫描根目录",
            description="本次扫描的根目录；不会整体删除根目录。",
            action="只清理报告中的子项。",
            risk="删除根目录会移除其下所有内容。",
            selectable=False,
        )
        self._add_generic_entry(self.root, cls, depth=0, is_root=True)
        stats = self._walk_children(self.root, depth=0)
        self._update_entry_size(self.root, stats)

    def _flags_for_rule(self, rule: Dict[str, Any], is_root: bool = False) -> Dict[str, bool]:
        rid = rule.get("id", "")
        if rid == "sys-users":
            return {"profile_parent": True}
        if rid in ("sys-appdata-local", "sys-appdata-roaming", "sys-appdata-locallow"):
            return {"force_candidates": True}
        return {}

    # -- walking --------------------------------------------------------------

    def _walk_children(
        self,
        path: str,
        depth: int,
        prune: bool = False,
        profile_parent: bool = False,
        profile_root: bool = False,
        force_candidates: bool = False,
    ) -> ScanStats:
        stats = ScanStats()
        if self._deadline_reached():
            stats.partial = True
            return stats
        display = display_path(path)
        try:
            with os.scandir(fs_path(path)) as scandir:
                children = list(scandir)
        except OSError as exc:
            self._record_error(display, exc)
            stats.errors += 1
            stats.partial = True
            return stats
        for child in children:
            if self._deadline_reached():
                stats.partial = True
                break
            child_path = display_path(child.path)
            if self._is_excluded(child_path, child.name):
                stats.excluded += 1
                self.stats.excluded += 1
                continue
            try:
                is_dir = child.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if is_dir and is_reparse_entry(child):
                stats.reparse_skipped += 1
                self.stats.reparse_skipped += 1
                self._add_reparse_entry(child_path, depth + 1, is_top_level=(depth == 0))
                continue
            if is_dir:
                child_rule = self.index.match(child_path, child.name, True)
                if prune and child_rule is None and not self.index.is_interesting_prefix(child_path):
                    stats.pruned += 1
                    self.stats.pruned += 1
                    continue
                sub = self._walk_dir(
                    child_path,
                    depth + 1,
                    child_rule,
                    is_top_level=(depth == 0),
                    profile_parent=profile_parent,
                    profile_root=profile_root,
                    force_candidate=force_candidates,
                    prune=prune,
                )
                stats.add(sub)
                if child_rule is None:
                    self._maybe_add_large(
                        child_path, depth + 1, sub, force_candidate=force_candidates
                    )
            else:
                try:
                    size = child.stat(follow_symlinks=False).st_size
                except OSError:
                    size = 0
                stats.files += 1
                stats.bytes += size
                self.stats.files += 1
                self.stats.bytes += size
                self._progress_tick(child_path)
                self._maybe_add_file(
                    child_path, child.name, depth + 1, size, is_top_level=(depth == 0)
                )
        return stats

    def _walk_dir(
        self,
        path: str,
        depth: int,
        rule: Optional[Dict[str, Any]],
        is_top_level: bool,
        profile_parent: bool = False,
        profile_root: bool = False,
        force_candidate: bool = False,
        prune: bool = False,
    ) -> ScanStats:
        name = os.path.basename(display_path(path).rstrip("\\"))
        low = name.lower()
        self.stats.dirs += 1
        self._progress_tick(path)

        if rule is not None:
            mode = str(rule.get("mode", "leaf"))
            if mode == "leaf":
                stats = self._measure(path)
                self._add_rule_entry(path, rule, stats, depth=depth, is_top_level=is_top_level)
                return stats
            if mode == "skip":
                self._add_rule_entry(path, rule, None, depth=depth, is_top_level=is_top_level)
                if (rule.get("prune") or prune) and self.index.has_interesting_below(path):
                    return self._walk_children(path, depth=depth, prune=True)
                return ScanStats()
            if mode == "container":
                self._add_rule_entry(path, rule, None, depth=depth, is_top_level=is_top_level)
                effective_prune = bool(rule.get("prune")) or prune
                if effective_prune and not self.index.has_interesting_below(path):
                    return ScanStats()
                flags = self._flags_for_rule(rule)
                stats = self._walk_children(
                    path, depth=depth, prune=effective_prune, **flags
                )
                self._update_entry_size(path, stats)
                return stats
            # mode == normal: fall through to the generic walk

        if profile_parent:
            cls = self._profile_root_classification()
            self._add_generic_entry(path, cls, depth=depth, is_top_level=is_top_level)
            stats = self._walk_children(
                path, depth=depth, profile_root=True, force_candidates=True
            )
            self._update_entry_size(path, stats)
            return stats

        if profile_root:
            cls = self._profile_folder_classification(low)
            if cls:
                if cls.get("mode") == "container":
                    self._add_generic_entry(path, cls, depth=depth, is_top_level=is_top_level)
                    stats = self._walk_children(path, depth=depth, force_candidates=True)
                    self._update_entry_size(path, stats)
                    return stats
                stats = self._measure(path)
                self._add_generic_entry(path, cls, depth=depth, is_top_level=is_top_level, stats=stats)
                return stats

        if low == "users" and depth <= 2 and not profile_root:
            cls = self._users_classification()
            self._add_generic_entry(path, cls, depth=depth, is_top_level=is_top_level)
            stats = self._walk_children(path, depth=depth, profile_parent=True)
            self._update_entry_size(path, stats)
            return stats

        if is_top_level:
            cls = self._top_level_classification(low)
            if cls:
                if cls.get("mode") == "leaf":
                    stats = self._measure(path)
                    self._add_generic_entry(
                        path, cls, depth=depth, is_top_level=True, stats=stats
                    )
                    return stats
                if cls.get("mode") == "skip":
                    self._add_generic_entry(path, cls, depth=depth, is_top_level=True)
                    return ScanStats()
                self._add_generic_entry(path, cls, depth=depth, is_top_level=True)
                stats = self._walk_children(path, depth=depth, prune=prune)
                self._update_entry_size(path, stats)
                return stats
            cls = self._generic_classification(
                path,
                name,
                role="overview",
                recommendation="review",
                title=name or "顶层目录",
                description="未命中内置规则的顶层目录；请确认用途后再决定是否删除。",
                action="删除前确认目录内容与是否可从别处恢复；建议先备份。",
                risk="可能是用户数据、项目或程序数据，误删不可恢复。",
                selectable=True,
            )
            self._add_generic_entry(path, cls, depth=depth, is_top_level=True)
            stats = self._walk_children(path, depth=depth, prune=prune)
            self._update_entry_size(path, stats)
            return stats

        stats = self._walk_children(
            path,
            depth=depth,
            prune=prune,
            force_candidates=False,
        )
        return stats

    # -- measurements ---------------------------------------------------------

    def _measure(self, path: str) -> ScanStats:
        stats = ScanStats()
        display = display_path(path)
        stack = [fs_path(path)]
        visited = 0
        while stack:
            if self._deadline_reached():
                stats.partial = True
                break
            current = stack.pop()
            try:
                with os.scandir(current) as scandir:
                    entries = list(scandir)
            except OSError as exc:
                self._record_error(display_path(current), exc)
                stats.errors += 1
                stats.partial = True
                continue
            for entry in entries:
                visited += 1
                if visited % 512 == 0 and self._deadline_reached():
                    stats.partial = True
                    stack.clear()
                    break
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if is_reparse_entry(entry):
                            stats.reparse_skipped += 1
                            self.stats.reparse_skipped += 1
                            continue
                        stats.dirs += 1
                        self.stats.dirs += 1
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        stats.bytes += size
                        stats.files += 1
                        self.stats.bytes += size
                        self.stats.files += 1
                        self._progress_tick(display_path(entry.path))
                except OSError:
                    stats.errors += 1
                    stats.partial = True
        return stats

    # -- entries --------------------------------------------------------------

    def _add_rule_entry(
        self,
        path: str,
        rule: Dict[str, Any],
        stats: Optional[ScanStats],
        depth: int,
        is_root: bool = False,
        is_top_level: bool = False,
    ) -> None:
        target = str(rule.get("target", "dir"))
        kind = "file" if target == "file" else "dir"
        mode = str(rule.get("mode", "leaf"))
        recommendation = str(rule.get("recommendation", "caution"))
        selectable = self._rule_selectable(rule)
        if mode in ("skip", "container") or recommendation == "keep":
            role = "overview"
        elif str(rule.get("scope")) == "user" and rule.get("id") == "user-downloads":
            role = "data"
        elif kind == "file":
            role = "file"
        else:
            role = "cleanup"
        entry = Entry(
            path=display_path(path),
            name=os.path.basename(display_path(path).rstrip("\\")),
            kind=kind,
            role=role,
            is_top_level=is_top_level,
            is_root=is_root,
            size=stats.bytes if stats else None,
            files=stats.files if stats else (1 if kind == "file" else None),
            dirs=stats.dirs if stats else (0 if kind == "file" else None),
            partial=bool(stats and stats.partial),
            size_known=stats is not None,
            mtime=self._mtime(path),
            rule_id=str(rule.get("id", "")),
            title=str(rule.get("title", "")),
            category=str(rule.get("category", "其他")),
            scope=str(rule.get("scope", "data")),
            description=str(rule.get("description", "")),
            action=str(rule.get("action", "")),
            risk=str(rule.get("risk", "")),
            recommendation=recommendation,
            selectable=selectable,
            method=str(rule.get("method", "recycle")),
            requires_admin=bool(rule.get("requires_admin", False)),
            depth=depth,
            reparse=False,
            classification="rule:" + str(rule.get("id", "")),
        )
        self._merge_entry(entry, 100)

    def _add_generic_entry(
        self,
        path: str,
        cls: Dict[str, Any],
        depth: int,
        is_root: bool = False,
        is_top_level: bool = False,
        stats: Optional[ScanStats] = None,
    ) -> None:
        entry = Entry(
            path=display_path(path),
            name=os.path.basename(display_path(path).rstrip("\\")),
            kind="dir",
            role=str(cls.get("role", "large")),
            is_top_level=is_top_level,
            is_root=is_root,
            size=stats.bytes if stats else None,
            files=stats.files if stats else None,
            dirs=stats.dirs if stats else None,
            partial=bool(stats and stats.partial),
            size_known=stats is not None,
            mtime=self._mtime(path),
            rule_id=None,
            title=str(cls.get("title", "")),
            category=str(cls.get("category", "其他")),
            scope=str(cls.get("scope", "data")),
            description=str(cls.get("description", "")),
            action=str(cls.get("action", "")),
            risk=str(cls.get("risk", "")),
            recommendation=str(cls.get("recommendation", "review")),
            selectable=bool(cls.get("selectable", True)),
            method=str(cls.get("method", "recycle")),
            requires_admin=bool(cls.get("requires_admin", False)),
            depth=depth,
            reparse=False,
            classification=str(cls.get("classification", "generic")),
        )
        self._merge_entry(entry, int(cls.get("priority", 60)))

    def _add_reparse_entry(self, path: str, depth: int, is_top_level: bool) -> None:
        if not is_top_level:
            name = os.path.basename(display_path(path).rstrip("\\"))
            if self.index.match(path, name, True) is None:
                return
        entry = Entry(
            path=display_path(path),
            name=os.path.basename(display_path(path).rstrip("\\")),
            kind="dir",
            role="overview",
            is_top_level=is_top_level,
            size=None,
            files=None,
            dirs=None,
            size_known=False,
            mtime=None,
            title="符号链接 / 目录联接",
            category="链接（跳过）",
            scope="system",
            description="这是一个 reparse point（符号链接或目录联接），扫描不会跟随，避免重复统计或误删目标。",
            action="保留；如需处理请先确认链接目标。",
            risk="删除链接本身通常安全，但目标目录可能被其他程序使用。",
            recommendation="keep",
            selectable=False,
            method="manual",
            depth=depth,
            reparse=True,
            classification="reparse",
        )
        self._merge_entry(entry, 90)

    def _maybe_add_large(
        self,
        path: str,
        depth: int,
        stats: ScanStats,
        force_candidate: bool = False,
    ) -> None:
        if stats.bytes <= 0 or stats.bytes < self.options.min_size:
            return
        if depth > self.options.listing_depth and not force_candidate:
            return
        key = normalize(path)
        if key in self.entries:
            return
        cls = self._generic_classification(
            path,
            os.path.basename(display_path(path).rstrip("\\")),
            role="large",
            recommendation="review",
            title=os.path.basename(display_path(path).rstrip("\\")) or "大型目录",
            description="未命中内置规则的大型目录，可能是用户数据、项目或应用数据。",
            action="删除前确认目录内容与是否可从别处恢复；建议先备份。",
            risk="可能是用户数据或程序数据，误删不可恢复。",
            selectable=True,
        )
        self._add_generic_entry(path, cls, depth=depth, stats=stats)

    def _maybe_add_file(
        self, path: str, name: str, depth: int, size: int, is_top_level: bool
    ) -> None:
        rule = None
        if self.index.file_hint(name):
            rule = self.index.match_file(path, name)
        if rule is not None:
            stats = ScanStats(bytes=size, files=1, dirs=0)
            self._add_rule_entry(path, rule, stats, depth=depth, is_top_level=is_top_level)
            return
        if is_top_level and size >= self.options.min_size:
            cls = self._generic_classification(
                path,
                name,
                role="file",
                recommendation="review",
                title=name,
                description="顶层大文件，未命中内置规则。",
                action="确认文件用途后再决定；不认识的文件建议先保留。",
                risk="可能是虚拟机磁盘、备份或用户数据，误删不可恢复。",
                selectable=True,
            )
            self._add_generic_entry(path, cls, depth=depth, is_top_level=is_top_level, stats=ScanStats(bytes=size, files=1, dirs=0))

    # -- merging --------------------------------------------------------------

    def _merge_entry(self, entry: Entry, priority: int) -> None:
        key = normalize(entry.path)
        existing = self.entries.get(key)
        if existing is None:
            self.entries[key] = entry
            self._priority[key] = priority
            return
        old_priority = self._priority.get(key, 0)
        if priority > old_priority:
            entry.is_top_level = entry.is_top_level or existing.is_top_level
            entry.is_root = entry.is_root or existing.is_root
            if entry.size is None and existing.size is not None:
                entry.size = existing.size
                entry.files = existing.files
                entry.dirs = existing.dirs
                entry.size_known = existing.size_known
                entry.partial = existing.partial
            self.entries[key] = entry
            self._priority[key] = priority
            return
        # Same or lower priority: keep the more specific classification, but
        # merge facts (size, flags) so a container/top-level pass can fill them.
        existing.is_top_level = existing.is_top_level or entry.is_top_level
        existing.is_root = existing.is_root or entry.is_root
        if entry.size is not None and (existing.size is None or entry.size > existing.size):
            existing.size = entry.size
            existing.files = entry.files
            existing.dirs = entry.dirs
            existing.size_known = entry.size_known
            existing.partial = entry.partial
        if priority == old_priority:
            existing.selectable = existing.selectable and entry.selectable
            severity = {"safe": 0, "caution": 1, "review": 2, "keep": 3}
            if severity.get(entry.recommendation, 9) > severity.get(existing.recommendation, 9):
                existing.recommendation = entry.recommendation

    def _update_entry_size(self, path: str, stats: ScanStats) -> None:
        entry = self.entries.get(normalize(path))
        if entry is None:
            return
        entry.size = stats.bytes
        entry.files = stats.files
        entry.dirs = stats.dirs
        entry.partial = stats.partial
        entry.size_known = True
        if entry.mtime is None:
            entry.mtime = self._mtime(path)

    # -- classifications ------------------------------------------------------

    def _rule_selectable(self, rule: Dict[str, Any]) -> bool:
        if "selectable" in rule:
            return bool(rule["selectable"])
        if rule.get("recommendation") == "keep":
            return False
        if rule.get("mode") in ("skip", "container"):
            return False
        if rule.get("method") == "manual":
            return False
        return True

    def _generic_classification(
        self,
        path: str,
        name: str,
        role: str,
        recommendation: str,
        title: str,
        description: str,
        action: str,
        risk: str,
        selectable: bool,
        category: str = "其他",
        scope: str = "data",
        method: str = "recycle",
        priority: int = 60,
        requires_admin: bool = False,
    ) -> Dict[str, Any]:
        return {
            "role": role,
            "recommendation": recommendation,
            "title": title,
            "description": description,
            "action": action,
            "risk": risk,
            "selectable": selectable,
            "category": category,
            "scope": scope,
            "method": method,
            "priority": priority,
            "requires_admin": requires_admin,
            "mode": "normal",
            "classification": "generic",
        }

    def _users_classification(self) -> Dict[str, Any]:
        return {
            "role": "overview",
            "recommendation": "keep",
            "title": "用户配置文件根目录（Users）",
            "category": "用户数据",
            "scope": "system",
            "description": "所有用户配置文件的根目录；每个子目录对应一个用户。",
            "action": "不要整体删除；只清理用户明确选择的具体目录。",
            "risk": "删除会导致用户账户数据与配置丢失。",
            "selectable": False,
            "method": "manual",
            "priority": 90,
            "classification": "profile-parent",
            "mode": "container",
        }

    def _profile_root_classification(self) -> Dict[str, Any]:
        return {
            "role": "overview",
            "recommendation": "keep",
            "title": "用户配置文件",
            "category": "用户数据",
            "scope": "user",
            "description": "一个用户的桌面、文档、下载、AppData 与个人配置。",
            "action": "不要整体删除；只清理其中明确选择的具体目录。",
            "risk": "删除会导致该用户的数据、配置与登录状态丢失。",
            "selectable": False,
            "method": "manual",
            "priority": 90,
            "classification": "profile-root",
            "mode": "container",
        }

    def _profile_folder_classification(self, low: str) -> Optional[Dict[str, Any]]:
        if low == "appdata":
            return {
                "role": "overview",
                "recommendation": "keep",
                "title": "应用数据（AppData）",
                "category": "用户数据",
                "scope": "user",
                "description": "应用保存配置与缓存的根目录，分为 Local / Roaming / LocalLow。",
                "action": "不要整体删除；只清理其中明确标记的缓存子目录。",
                "risk": "整体删除会导致应用配置、登录状态与数据丢失。",
                "selectable": False,
                "method": "manual",
                "priority": 90,
                "classification": "profile-appdata",
                "mode": "container",
            }
        data = _PROFILE_FOLDERS.get(low)
        if not data:
            return None
        return {
            "role": "data",
            "recommendation": data["recommendation"],
            "title": data["title"],
            "category": data["category"],
            "scope": "user",
            "description": data["description"],
            "action": data["action"],
            "risk": data["risk"],
            "selectable": data["recommendation"] != "keep",
            "method": "recycle",
            "priority": 80,
            "classification": "profile-folder",
            "mode": "leaf",
        }

    def _top_level_classification(self, low: str) -> Optional[Dict[str, Any]]:
        if low in _TOP_LEVEL_PROTECTED:
            return {
                "role": "overview",
                "recommendation": "keep",
                "title": {
                    "windows": "Windows 系统目录",
                    "program files": "程序安装目录（Program Files）",
                    "program files (x86)": "32 位程序安装目录（Program Files (x86)）",
                    "programdata": "共享应用数据（ProgramData）",
                    "users": "用户配置文件根目录（Users）",
                    "recovery": "恢复环境（Recovery）",
                    "boot": "启动目录（Boot）",
                    "system volume information": "系统卷信息",
                    "$recycle.bin": "回收站",
                    "config.msi": "MSI 回滚缓存（Config.Msi）",
                    "msocache": "Office 安装缓存（MSOCache）",
                }.get(low, low),
                "category": "系统组件（保留）",
                "scope": "system",
                "description": "受保护的系统/程序目录；本工具不会删除它。",
                "action": "保留；需要清理时使用对应的系统工具或卸载器。",
                "risk": "直接删除可能导致系统或程序损坏。",
                "selectable": False,
                "method": "manual",
                "priority": 85,
                "classification": "top-level-protected",
                "mode": "skip" if low != "users" else "container",
            }
        if low in ("temp", "tmp"):
            return {
                "role": "overview",
                "recommendation": "caution",
                "title": f"顶层临时目录（{low}）",
                "category": "系统临时文件",
                "scope": "system",
                "description": "磁盘根目录下的自定义临时目录，可能被某些脚本/程序使用。",
                "action": "确认没有程序正在使用后可清理；被占用的文件会跳过。",
                "risk": "可能有程序把重要临时状态放在这里。",
                "selectable": True,
                "method": "recycle",
                "priority": 75,
                "classification": "top-level-temp",
                "mode": "leaf",
            }
        if low == "found.000":
            return {
                "role": "overview",
                "recommendation": "caution",
                "title": "chkdsk 恢复文件（found.000）",
                "category": "其他",
                "scope": "data",
                "description": "磁盘检查恢复出的文件碎片，可能包含丢失的数据。",
                "action": "先打开检查是否包含需要的文件，再决定删除。",
                "risk": "可能包含唯一副本的数据。",
                "selectable": True,
                "method": "recycle",
                "priority": 75,
                "classification": "top-level-found",
                "mode": "leaf",
            }
        if low in _VENDOR_DIRS:
            return {
                "role": "overview",
                "recommendation": "caution",
                "title": f"厂商目录（{low.title()}）",
                "category": "厂商驱动与工具",
                "scope": "system",
                "description": "OEM/显卡厂商的驱动、工具或安装包残留。",
                "action": "只清理确认无用的安装包/日志；不要删除正在使用的驱动组件。",
                "risk": "删除驱动组件可能导致设备异常。",
                "selectable": True,
                "method": "recycle",
                "priority": 70,
                "classification": "top-level-vendor",
                "mode": "normal",
            }
        return None

    def _looks_like_profile(self, path: str) -> bool:
        try:
            with os.scandir(fs_path(path)) as scandir:
                names = {entry.name.lower() for entry in scandir}
        except OSError:
            return False
        return "appdata" in names and ("ntuser.dat" in names or "desktop" in names)

    # -- misc -----------------------------------------------------------------

    def _mtime(self, path: str) -> Optional[str]:
        try:
            return iso_from_timestamp(os.stat(fs_path(path), follow_symlinks=False).st_mtime)
        except OSError:
            return None

    def _deadline_reached(self) -> bool:
        if self.deadline is None:
            return False
        if time.monotonic() >= self.deadline:
            self.partial = True
            return True
        return False

    def _record_error(self, path: str, exc: OSError) -> None:
        if len(self.errors) < 100:
            self.errors.append(
                {"path": display_path(path), "error": f"{type(exc).__name__}: {exc}"}
            )

    def _normalize_exclude(self, pattern: str) -> str:
        p = pattern.replace("/", "\\")
        return p.lower()

    def _is_excluded(self, path: str, name: str) -> bool:
        if not self._excluded:
            return False
        low_path = normalize(path)
        low_name = name.lower()
        for pattern in self._excluded:
            if "\\" in pattern:
                if fnmatch.fnmatchcase(low_path, pattern):
                    return True
                if low_path == pattern.rstrip("\\"):
                    return True
            elif fnmatch.fnmatchcase(low_name, pattern):
                return True
        return False

    def _progress_tick(self, current: str) -> None:
        if not self.options.progress:
            return
        now = time.monotonic()
        if now - self._last_progress < 2.0:
            return
        self._last_progress = now
        print(
            f"扫描中：{self.stats.dirs:,} 个目录 / {self.stats.files:,} 个文件 / "
            f"{human_size(self.stats.bytes)} · {_truncate(display_path(current))}",
            file=os.sys.stderr,
            flush=True,
        )

    def _total_stats(self) -> ScanStats:
        total = ScanStats(
            dirs=self.stats.dirs,
            files=self.stats.files,
            bytes=self.stats.bytes,
            errors=len(self.errors),
            reparse_skipped=self.stats.reparse_skipped,
            excluded=self.stats.excluded,
            pruned=self.stats.pruned,
            partial=self.partial or any(e.partial for e in self.entries.values()),
        )
        return total

    def _probe_recycle_bin(self) -> None:
        root = volume_root(self.root)
        if normalize(self.root) != normalize(root):
            return
        key = None
        for candidate in (root + "$Recycle.Bin", root + "$RECYCLE.BIN"):
            if normalize(candidate) in self.entries:
                key = normalize(candidate)
                break
        if key is None:
            return
        data = probe_recycle_bin(root)
        if not data:
            return
        entry = self.entries[key]
        count = data.get("count")
        size = data.get("size")
        if isinstance(size, int):
            entry.size = size
            entry.size_known = True
        if isinstance(count, int):
            entry.files = count
        entry.title = "回收站（当前用户）"
        entry.category = "回收站"
        entry.description = "当前用户删除的文件先进入这里；清空后才真正释放磁盘空间。"
        entry.action = "右键回收站 → 清空回收站，或 PowerShell Clear-RecycleBin；不要手动删除目录。"
        entry.risk = "清空后无法从回收站恢复文件。"
        entry.recommendation = "caution"
        entry.selectable = False

    def _prune_nested_generic(self) -> None:
        """Keep only the outermost generic large directory.

        Known caches remain individually listed.  Without this, a scan of
        ``AppData\\Local`` would list ``App``, ``App\\Cache`` and
        ``App\\Cache\\Sub`` all at once.
        """
        generic = [
            e
            for e in self.entries.values()
            if e.classification == "generic"
            and not e.is_root
            and e.role in ("overview", "large")
        ]
        if not generic:
            return
        keys = {normalize(entry.path) for entry in generic}
        keep = set()
        for entry in generic:
            parent = os.path.dirname(normalize(entry.path))
            has_ancestor = False
            while parent and parent != entry.path:
                if parent in keys:
                    has_ancestor = True
                    break
                next_parent = os.path.dirname(parent)
                if next_parent == parent:
                    break
                parent = next_parent
            if not has_ancestor:
                keep.add(normalize(entry.path))
        for key in list(self.entries):
            if (
                self.entries[key].classification == "generic"
                and not self.entries[key].is_root
                and key not in keep
            ):
                del self.entries[key]
                self._priority.pop(key, None)

    def _finish_notes(self) -> None:
        if self.partial:
            self.notes.append(
                "扫描达到时间上限或部分目录无法读取，结果不完整；可增大 --max-seconds 或缩小扫描范围。"
            )
        if self.errors:
            self.notes.append(
                f"{len(self.errors)} 个路径因权限/占用/路径过长未能读取；详情见 scan.json 的 errors。"
            )
        if any(e.reparse for e in self.entries.values()):
            self.notes.append("报告中的符号链接/目录联接未被跟随，也不会被选为删除项。")
        if self.options.exclude:
            self.notes.append("已按 --exclude 排除部分路径；排除项不出现在报告中。")
        self.notes.append(
            "大小为逻辑大小，硬链接、压缩、稀疏文件与资源管理器显示可能不同。"
        )
        self.notes.append(
            "系统保护目录（WinSxS/System32/Program Files 等）未深入统计，以免误删与误导。"
        )
