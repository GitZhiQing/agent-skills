"""Windows-specific helpers kept in one place.

The modules in this package are deliberately standard-library only.  PowerShell
is used for two things Python does poorly: reading the shell Recycle Bin size
and moving folders to the Recycle Bin through the shell APIs.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DRIVE_TYPES = {
    0: "unknown",
    1: "no_root",
    2: "removable",
    3: "fixed",
    4: "remote",
    5: "cdrom",
    6: "ramdisk",
}

_DRIVE_TYPE_LABELS = {
    "unknown": "未知",
    "no_root": "无根目录",
    "removable": "可移动磁盘",
    "fixed": "本地磁盘",
    "remote": "网络驱动器",
    "cdrom": "光驱",
    "ramdisk": "内存盘",
}


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def display_path(path: str) -> str:
    """Strip the extended-length prefix before showing a path to humans."""
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def fs_path(path: str) -> str:
    """Return a path that can be passed to the Win32 file APIs.

    Long paths need the extended-length prefix when LongPathsEnabled is off.
    We only add it when needed so ordinary paths stay readable in logs.
    """
    if not is_windows():
        return path
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    if len(p) >= 248:
        return "\\\\?\\" + p
    return p


def normalize(path: str) -> str:
    """Case-insensitive comparison key (Windows semantics on any host for tests)."""
    p = display_path(os.path.abspath(path))
    p = os.path.normpath(p)
    if len(p) > 3 and p.endswith("\\"):
        p = p.rstrip("\\")
    return p.replace("/", "\\").lower()


def volume_root(path: str) -> str:
    """Return the drive/UNC root that owns *path*."""
    p = os.path.abspath(display_path(path))
    if p.startswith("\\\\"):
        parts = p.split("\\")
        if len(parts) >= 4:
            return "\\\\" + parts[2] + "\\" + parts[3] + "\\"
        return p
    drive, _ = os.path.splitdrive(p)
    return (drive + "\\") if drive else p


def path_depth(path: str) -> int:
    p = display_path(normalize(path))
    if p.startswith("\\\\"):
        parts = [x for x in p.split("\\") if x]
        return max(0, len(parts) - 2)
    drive, rest = os.path.splitdrive(p)
    return len([x for x in rest.split("\\") if x])


def is_subpath(child: str, parent: str) -> bool:
    """True when *child* is *parent* or lives below it (case-insensitive)."""
    c = normalize(child)
    p = normalize(parent)
    if c == p:
        return True
    return c.startswith(p.rstrip("\\") + "\\")


def is_reparse_entry(entry: os.DirEntry) -> bool:
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        attrs = getattr(st, "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def is_reparse_path(path: str) -> bool:
    if not is_windows():
        return os.path.islink(path)
    try:
        if os.path.islink(path):
            return True
        st = os.stat(fs_path(path), follow_symlinks=False)
        attrs = getattr(st, "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def get_drive_type(path: str) -> str:
    if not is_windows():
        return "fixed"
    try:
        root = volume_root(path)
        code = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
        return DRIVE_TYPES.get(int(code), "unknown")
    except Exception:
        return "unknown"


def drive_type_label(kind: str) -> str:
    return _DRIVE_TYPE_LABELS.get(kind, kind)


def get_volume_info(path: str) -> Dict[str, Any]:
    root = volume_root(path)
    info: Dict[str, Any] = {
        "root": root,
        "total": None,
        "used": None,
        "free": None,
        "label": "",
        "filesystem": "",
        "drive_type": get_drive_type(path),
    }
    try:
        usage = shutil.disk_usage(root)
        info.update({"total": usage.total, "used": usage.used, "free": usage.free})
    except OSError:
        pass
    if is_windows():
        try:
            label = ctypes.create_unicode_buffer(261)
            fsbuf = ctypes.create_unicode_buffer(261)
            serial = ctypes.c_uint()
            maxlen = ctypes.c_uint()
            flags = ctypes.c_uint()
            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root),
                label,
                261,
                ctypes.byref(serial),
                ctypes.byref(maxlen),
                ctypes.byref(flags),
                fsbuf,
                261,
            )
            if ok:
                info["label"] = label.value
                info["filesystem"] = fsbuf.value
        except Exception:
            pass
    return info


def human_size(value: Optional[int]) -> str:
    if value is None:
        return "未统计"
    n = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def human_count(value: Optional[int]) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def iso_from_timestamp(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")
    except (OSError, OverflowError, ValueError):
        return None


def display_time(iso: Optional[str], fallback: str = "—") -> str:
    if not iso:
        return fallback
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso


def run_powershell(
    script: Path,
    args: Sequence[str],
    timeout: int = 600,
) -> Tuple[int, str, str]:
    """Run a PowerShell script file and return (code, stdout, stderr)."""
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        return 127, "", "PowerShell 不可用（找不到 powershell 或 pwsh）"
    cmd: List[str] = [
        executable,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    cmd.extend(str(a) for a in args)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"PowerShell 超时（{timeout}s）"
    except OSError as exc:
        return 126, "", f"PowerShell 启动失败：{exc}"


def parse_json_output(text: str) -> Optional[Any]:
    """PowerShell may emit BOM/blank lines; find the first JSON value."""
    if not text:
        return None
    cleaned = text.strip().lstrip("\ufeff")
    if not cleaned:
        return None
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    for end in range(len(cleaned), start, -1):
        chunk = cleaned[start:end]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    return None


def probe_recycle_bin(drive_root: str) -> Optional[Dict[str, Any]]:
    from disk_cleanup.rules import asset_file

    script = asset_file("ps/probe.ps1")
    if not script or not script.exists():
        return None
    code, out, _err = run_powershell(
        script, ["-Action", "recyclebin", "-Path", drive_root], timeout=30
    )
    if code != 0:
        return None
    data = parse_json_output(out)
    if isinstance(data, dict) and data.get("ok"):
        return data
    return None


def ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def iter_ancestors(path: str) -> Iterable[str]:
    p = display_path(os.path.abspath(path))
    drive, _ = os.path.splitdrive(p)
    current = p
    while True:
        yield current
        parent = os.path.dirname(current)
        if not parent or parent == current:
            break
        if drive and parent == drive:
            yield drive + "\\"
            break
        current = parent
