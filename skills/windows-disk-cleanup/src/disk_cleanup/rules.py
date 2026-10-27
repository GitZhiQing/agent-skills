"""Rule loading, path matching, and the "is it a cache or a data directory" logic.

Rule JSON is the source of truth (``assets/rules.json``).  The matcher is
deliberately small and explicit: exact paths, path suffixes, name patterns,
globs, and prefixes.  It never evaluates arbitrary code from the rule file.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from disk_cleanup.model import RECOMMENDATIONS, RULE_MODES, TARGETS
from disk_cleanup.winutil import (
    display_path,
    is_subpath,
    normalize,
    volume_root,
)

_ENV_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_()]*)%")


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def asset_dir() -> Path:
    """Locate ``assets/`` in both the source tree and an installed wheel."""
    env = os.environ.get("WINDOWS_DISK_CLEANUP_HOME") or os.environ.get(
        "DISK_CLEANUP_HOME"
    )
    candidates: List[Path] = []
    if env:
        candidates.append(Path(env).expanduser() / "assets")
    candidates.append(Path(__file__).resolve().parent / "assets")
    candidates.append(_skill_root() / "assets")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def asset_file(relative: str) -> Path:
    return asset_dir() / relative


def _expand_env(text: str) -> str:
    """Expand ``%VAR%`` on any host (os.path.expandvars is POSIX-only)."""

    def repl(match: "re.Match[str]") -> str:
        name = match.group(1)
        return os.environ.get(name, match.group(0))

    return _ENV_RE.sub(repl, text)


def _normalize_pattern(pattern: str) -> str:
    p = _expand_env(pattern).replace("/", "\\")
    while "\\\\" in p and not p.startswith("\\\\"):
        p = p.replace("\\\\", "\\")
    if len(p) > 3 and p.endswith("\\"):
        p = p.rstrip("\\")
    return p


def _is_absolute_pattern(pattern: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:\\", pattern)) or pattern.startswith("\\\\")


def _last_literal_component(pattern: str) -> Tuple[str, bool]:
    """Return (lookup key, has_wildcard) for the final path component."""
    comp = pattern.replace("/", "\\").rstrip("\\").split("\\")[-1]
    if "*" in comp or "?" in comp:
        literal = re.split(r"[*?]", comp, maxsplit=1)[0]
        return literal.lower(), True
    return comp.lower(), False


def _system_drive() -> str:
    drive = os.environ.get("SystemDrive", "C:")
    return drive.rstrip("\\") + "\\"


def _protected_app_prefixes(scan_root: str) -> List[str]:
    prefixes: List[str] = []
    for name in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData"):
        value = os.environ.get(name)
        if value:
            prefixes.append(normalize(value))
    root = volume_root(scan_root)
    if root and not root.startswith("\\\\"):
        for name in ("Windows", "Program Files", "Program Files (x86)", "ProgramData"):
            prefixes.append(normalize(os.path.join(root, name)))
    # Keep the list unique and non-empty.
    return sorted({p for p in prefixes if p})


class RuleIndex:
    """Match filesystem paths against the bundled rule catalog."""

    def __init__(self, rules: Sequence[Dict[str, Any]], scan_root: str = "C:\\"):
        self.rules = list(rules)
        self.scan_root = scan_root
        self.system_drive = _system_drive()
        self.protected_app_prefixes = _protected_app_prefixes(scan_root)
        self._exact_dir: Dict[str, Dict[str, Any]] = {}
        self._exact_file: Dict[str, Dict[str, Any]] = {}
        self._literal_by_leaf: Dict[str, List[Tuple[Dict[str, Any], str, str, str]]] = defaultdict(list)
        self._wildcard_rules: List[Tuple[Dict[str, Any], str, str, str]] = []
        self._regex_rules: List[Tuple["re.Pattern[str]", Dict[str, Any]]] = []
        self._dir_names_cache: Dict[str, set] = {}
        self._interesting: List[str] = []
        self._file_hints: set = set()
        self._file_suffix_hints: set = set()
        self._build()

    # -- construction ---------------------------------------------------------

    def _build(self) -> None:
        for rule in self.rules:
            match = rule.get("match") or {}
            kind = str(match.get("type", ""))
            raw_pattern = str(match.get("pattern", ""))
            # Regex patterns must keep their backslashes; path patterns are
            # normalized to Windows separators.
            pattern = _expand_env(raw_pattern) if kind == "regex" else _normalize_pattern(raw_pattern)
            target = str(rule.get("target", "dir"))
            priority = int(rule.get("priority", self._default_priority(kind)))
            rule["_compiled_pattern"] = pattern
            rule["_compiled_priority"] = priority
            if kind == "exact":
                table = self._exact_file if target == "file" else self._exact_dir
                key = normalize(pattern)
                previous = table.get(key)
                if previous is None or priority > int(previous.get("_compiled_priority", 0)):
                    table[key] = rule
            elif kind == "regex":
                try:
                    self._regex_rules.append((re.compile(pattern, re.IGNORECASE), rule))
                except re.error:
                    continue
            elif kind in ("basename", "suffix", "glob", "prefix"):
                lookup, wildcard = _last_literal_component(pattern)
                item = (rule, kind, pattern, target)
                if wildcard:
                    self._wildcard_rules.append(item)
                else:
                    self._literal_by_leaf[lookup].append(item)
            if target == "file":
                self._collect_file_hint(pattern)
            self._collect_interesting(rule, kind, pattern, target)
        for items in self._literal_by_leaf.values():
            items.sort(key=self._sort_key)
        self._wildcard_rules.sort(key=self._sort_key)
        self._interesting.sort(key=len, reverse=True)

    @staticmethod
    def _default_priority(kind: str) -> int:
        return {
            "exact": 100,
            "prefix": 90,
            "suffix": 80,
            "glob": 70,
            "regex": 65,
            "basename": 60,
        }.get(kind, 50)

    @staticmethod
    def _sort_key(item: Tuple[Dict[str, Any], str, str, str]) -> Tuple[int, int]:
        rule, _kind, pattern, _target = item
        return (
            int(rule.get("_compiled_priority", 0)),
            len(pattern),
        )

    def _collect_file_hint(self, pattern: str) -> None:
        comp = pattern.replace("/", "\\").rstrip("\\").split("\\")[-1].lower()
        if "*" in comp or "?" in comp:
            suffix = re.split(r"[*?]", comp)[-1]
            if suffix:
                self._file_suffix_hints.add(suffix)
        elif comp:
            self._file_hints.add(comp)

    def file_hint(self, name: str) -> bool:
        """Cheap pre-filter before calling :meth:`match_file` on every file."""
        low = name.lower()
        if low in self._file_hints:
            return True
        return any(low.endswith(suffix) for suffix in self._file_suffix_hints)

    def _collect_interesting(
        self, rule: Dict[str, Any], kind: str, pattern: str, target: str
    ) -> None:
        if target != "dir":
            return
        if str(rule.get("mode", "leaf")) == "container":
            return
        raw = pattern
        if kind in ("suffix", "prefix", "glob") and "*" in raw:
            raw = re.split(r"[*?]", raw, maxsplit=1)[0]
        if not raw:
            return
        if kind == "basename" or "\\" not in raw:
            return
        if _is_absolute_pattern(raw):
            self._interesting.append(normalize(raw))
        elif raw.startswith("\\"):
            low = raw.lower()
            if low.startswith(("\\windows", "\\programdata", "\\program files")):
                self._interesting.append(normalize(self.system_drive.rstrip("\\") + raw))

    # -- matching -------------------------------------------------------------

    def _dir_names(self, path: str) -> set:
        key = normalize(path)
        cached = self._dir_names_cache.get(key)
        if cached is not None:
            return cached
        names: set = set()
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    names.add(entry.name.lower())
        except OSError:
            pass
        self._dir_names_cache[key] = names
        return names

    def _requirements_met(self, rule: Dict[str, Any], path: str) -> bool:
        match = rule.get("match") or {}
        inside = match.get("requires_inside") or []
        if inside:
            names = self._dir_names(path)
            if not any(
                any(fnmatch.fnmatchcase(name, pat.lower()) for name in names)
                for pat in inside
            ):
                return False
        sibling_any = match.get("requires_sibling_any") or []
        if sibling_any:
            parent = os.path.dirname(path.rstrip("\\"))
            names = self._dir_names(parent)
            if not any(
                any(fnmatch.fnmatchcase(name, pat.lower()) for name in names)
                for pat in sibling_any
            ):
                return False
        return True

    def _candidate_ok(
        self,
        rule: Dict[str, Any],
        kind: str,
        pattern: str,
        target: str,
        path: str,
        name: str,
        is_dir: bool,
    ) -> bool:
        if target == "file" and is_dir:
            return False
        if target == "dir" and not is_dir:
            return False
        low_path = normalize(path)
        low_name = name.lower()
        low_pattern = pattern.lower()
        if kind == "basename":
            if not fnmatch.fnmatchcase(low_name, low_pattern):
                return False
            # Project caches inside Program Files / Windows are app internals,
            # not user-reclaimable project artifacts.
            if str(rule.get("context", "project")) == "project":
                if any(is_subpath(path, prefix) for prefix in self.protected_app_prefixes):
                    return False
        elif kind == "suffix":
            if _is_absolute_pattern(pattern):
                if low_path != low_pattern:
                    return False
            else:
                if not low_path.endswith(low_pattern) and low_path != low_pattern.lstrip("\\"):
                    return False
        elif kind == "glob":
            if not fnmatch.fnmatchcase(low_path, low_pattern):
                return False
        elif kind == "prefix":
            if _is_absolute_pattern(pattern):
                if not (low_path == low_pattern or low_path.startswith(low_pattern + "\\")):
                    return False
            else:
                if low_pattern not in low_path:
                    return False
        return self._requirements_met(rule, path)

    def _choose(self, candidates: Iterable[Tuple[Dict[str, Any], str, str, str]]) -> Optional[Dict[str, Any]]:
        best: Optional[Dict[str, Any]] = None
        best_key = (-1, -1)
        for rule, kind, pattern, target in candidates:
            key = (int(rule.get("_compiled_priority", 0)), len(pattern))
            if key > best_key:
                best, best_key = rule, key
        return best

    def match(
        self, path: str, name: Optional[str] = None, is_dir: bool = True
    ) -> Optional[Dict[str, Any]]:
        name = name or os.path.basename(display_path(path).rstrip("\\"))
        low_path = normalize(path)
        exact = self._exact_dir.get(low_path)
        candidates: List[Tuple[Dict[str, Any], str, str, str]] = []
        if exact is not None:
            candidates.append((exact, "exact", str(exact.get("_compiled_pattern", "")), "dir"))
        lookup = name.lower()
        for item in self._literal_by_leaf.get(lookup, []):
            rule, kind, pattern, target = item
            if target == "file":
                continue
            if self._candidate_ok(rule, kind, pattern, target, path, name, is_dir):
                candidates.append(item)
        for item in self._wildcard_rules:
            rule, kind, pattern, target = item
            if target == "file":
                continue
            if self._candidate_ok(rule, kind, pattern, target, path, name, is_dir):
                candidates.append(item)
        for regex, rule in self._regex_rules:
            target = str(rule.get("target", "dir"))
            if target == "file" and is_dir:
                continue
            if target == "dir" and not is_dir:
                continue
            if regex.search(low_path):
                candidates.append((rule, "regex", str(rule.get("_compiled_pattern", "")), target))
        return self._choose(candidates)

    def match_file(self, path: str, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        name = name or os.path.basename(display_path(path))
        low_path = normalize(path)
        candidates: List[Tuple[Dict[str, Any], str, str, str]] = []
        exact = self._exact_file.get(low_path)
        if exact is not None:
            candidates.append((exact, "exact", str(exact.get("_compiled_pattern", "")), "file"))
        for item in self._literal_by_leaf.get(name.lower(), []):
            rule, kind, pattern, target = item
            if target == "dir":
                continue
            if self._candidate_ok(rule, kind, pattern, target, path, name, False):
                candidates.append(item)
        for item in self._wildcard_rules:
            rule, kind, pattern, target = item
            if target == "dir":
                continue
            if self._candidate_ok(rule, kind, pattern, target, path, name, False):
                candidates.append(item)
        for regex, rule in self._regex_rules:
            if str(rule.get("target", "dir")) != "file":
                continue
            if regex.search(low_path):
                candidates.append((rule, "regex", str(rule.get("_compiled_pattern", "")), "file"))
        return self._choose(candidates)

    # -- pruning --------------------------------------------------------------

    def has_interesting_descendant(self, path: str) -> bool:
        """True when an interesting path is inside *path* (or is *path*)."""
        if not self._interesting:
            return False
        return any(is_subpath(item, path) for item in self._interesting)

    def has_interesting_below(self, path: str) -> bool:
        """True only when an interesting path is strictly below *path*.

        This distinction matters for skip rules: ``WinSxS`` and
        ``DriverStore`` are themselves interesting, but must not be descended
        into.
        """
        if not self._interesting:
            return False
        key = normalize(path)
        return any(
            is_subpath(item, path) and normalize(item) != key
            for item in self._interesting
        )

    def is_interesting_prefix(self, path: str) -> bool:
        if not self._interesting:
            return False
        return any(is_subpath(item, path) for item in self._interesting)


def expand_rule_pattern(pattern: str) -> str:
    return _normalize_pattern(pattern)


def load_rules(path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path) if path else asset_file("rules.json")
    with open(target, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data["_source"] = str(target)
    return data


def validate_rules(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        return ["rules 必须是非空数组"]
    seen = set()
    for index, rule in enumerate(rules):
        prefix = f"rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{prefix}: 不是对象")
            continue
        rid = rule.get("id")
        if not rid or not isinstance(rid, str):
            errors.append(f"{prefix}: 缺少 id")
        elif rid in seen:
            errors.append(f"{prefix}: id 重复（{rid}）")
        else:
            seen.add(rid)
        for key in ("title", "category", "description", "action"):
            if not str(rule.get(key, "")).strip():
                errors.append(f"{prefix}: {key} 为空")
        if rule.get("mode", "leaf") not in RULE_MODES:
            errors.append(f"{prefix}: mode 非法")
        if rule.get("recommendation") not in RECOMMENDATIONS:
            errors.append(f"{prefix}: recommendation 非法")
        if rule.get("method", "recycle") not in ("recycle", "permanent", "manual"):
            errors.append(f"{prefix}: method 非法")
        if rule.get("target", "dir") not in TARGETS:
            errors.append(f"{prefix}: target 非法")
        match = rule.get("match")
        if not isinstance(match, dict):
            errors.append(f"{prefix}: match 缺失")
            continue
        kind = match.get("type")
        if kind not in ("exact", "suffix", "basename", "glob", "prefix", "regex"):
            errors.append(f"{prefix}: match.type 非法（{kind}）")
        if not str(match.get("pattern", "")).strip():
            errors.append(f"{prefix}: match.pattern 为空")
        if kind == "basename" and "\\" in str(match.get("pattern", "")):
            errors.append(f"{prefix}: basename 模式不能含路径分隔符")
        if kind == "regex":
            try:
                re.compile(str(match.get("pattern", "")))
            except re.error as exc:
                errors.append(f"{prefix}: regex 无法编译（{exc}）")
    return errors
