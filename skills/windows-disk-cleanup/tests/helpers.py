from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

SKILL_ROOT = Path(__file__).resolve().parents[1]
SRC = SKILL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def setup_env() -> None:
    os.environ.setdefault("SystemDrive", "C:")
    os.environ.setdefault("WINDIR", r"C:\Windows")
    os.environ.setdefault("SystemRoot", r"C:\Windows")
    os.environ.setdefault("ProgramData", r"C:\ProgramData")
    os.environ.setdefault("ProgramFiles", r"C:\Program Files")
    os.environ.setdefault("ProgramFiles(x86)", r"C:\Program Files (x86)")
    os.environ.setdefault("USERPROFILE", r"C:\Users\test")
    os.environ.setdefault("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    os.environ.setdefault("APPDATA", r"C:\Users\test\AppData\Roaming")


def make_fixture(root: Path) -> Path:
    files = {
        "Users/alice/AppData/Local/Temp/a.txt": 100,
        "Users/alice/AppData/Local/pip/Cache/b.bin": 200,
        "Users/alice/Downloads/d.bin": 300,
        "Users/alice/Documents/doc.txt": 400,
        "Users/alice/Desktop/x.txt": 50,
        "proj/node_modules/pkg/index.js": 500,
        "proj/src/main.py": 10,
        "proj/.venv/pyvenv.cfg": 30,
        "big/old.bin": 2 * 1024 * 1024,
    }
    for rel, size in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return root


def scan_fixture(
    root: Path,
    output_dir: Optional[Path] = None,
    min_size: int = 1,
    listing_depth: int = 3,
    exclude: Optional[Iterable[str]] = None,
):
    from disk_cleanup.scanner import ScanOptions, Scanner

    options = ScanOptions(
        root=str(root),
        output_dir=str(output_dir or (root.parent / (root.name + "-out"))),
        min_size=min_size,
        listing_depth=listing_depth,
        max_entries=1500,
        exclude=list(exclude or []),
    )
    return Scanner(options).scan()


def write_scan(scan, output_dir: Path) -> Dict[str, str]:
    from disk_cleanup.report import write_scan_outputs

    return write_scan_outputs(scan, str(output_dir), max_entries=1500)


def write_selection(
    output_dir: Path,
    scan: Dict[str, Any],
    paths: Iterable[str],
    mode: str = "permanent",
    confirmed: bool = True,
    name: str = "selection.json",
) -> Path:
    data = {
        "skill": "windows-disk-cleanup",
        "schema": 1,
        "scan_id": scan["scan_id"],
        "scan_file": str((output_dir / "scan.json").resolve()),
        "root": scan["root"],
        "mode": mode,
        "confirmed": confirmed,
        "paths": list(paths),
    }
    path = output_dir / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def entry_by_suffix(scan: Dict[str, Any], suffix: str) -> Dict[str, Any]:
    for entry in scan.get("entries", []):
        if str(entry.get("path", "")).lower().endswith(suffix.lower()):
            return entry
    raise KeyError(suffix)
