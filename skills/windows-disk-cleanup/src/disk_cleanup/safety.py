"""Independent deletion guard.

The scan report already marks protected items as non-selectable, but the
cleaner re-checks every path against this module.  A forged/edited scan.json
therefore still cannot delete Windows, Program Files, user profiles, credential
directories, or a drive root.
"""

from __future__ import annotations

import os
from typing import List, Optional

from disk_cleanup.winutil import is_subpath, normalize, volume_root

_PROTECTED_BASENAMES = {
    ".git",
    ".ssh",
    ".gnupg",
    ".aws",
    ".azure",
    ".kube",
    ".docker",
}

_SYSTEM_FILES = {
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    "dumpstack.log.tmp",
}

_USER_DATA_NAMES = {
    "desktop",
    "documents",
    "pictures",
    "videos",
    "music",
    "onedrive",
    "favorites",
    "saved games",
    "contacts",
    "links",
    "searches",
}


def _env(name: str, fallback: str) -> str:
    value = os.environ.get(name)
    return value if value else fallback


def _systemdrive() -> str:
    return _env("SystemDrive", "C:").rstrip("\\") + "\\"


def _windir() -> str:
    return _env("WINDIR", os.path.join(_systemdrive(), "Windows"))


def _programdata() -> str:
    return _env("ProgramData", os.path.join(_systemdrive(), "ProgramData"))


def _program_files() -> List[str]:
    values = []
    for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        value = os.environ.get(name)
        if value:
            values.append(value)
    values.append(os.path.join(_systemdrive(), "Program Files"))
    values.append(os.path.join(_systemdrive(), "Program Files (x86)"))
    return values


def windows_allowlist() -> List[str]:
    windir = _windir()
    return [
        os.path.join(windir, "Temp"),
        os.path.join(windir, "SystemTemp"),
        os.path.join(windir, "SoftwareDistribution", "Download"),
        os.path.join(windir, "Logs"),
        os.path.join(windir, "Panther"),
        os.path.join(windir, "LiveKernelReports"),
        os.path.join(windir, "Minidump"),
        os.path.join(windir, "MEMORY.DMP"),
        os.path.join(windir, "System32", "LogFiles"),
        os.path.join(
            windir,
            "ServiceProfiles",
            "LocalService",
            "AppData",
            "Local",
            "FontCache",
        ),
    ]


def programdata_allowlist() -> List[str]:
    programdata = _programdata()
    return [
        os.path.join(programdata, "Microsoft", "Windows", "WER"),
        os.path.join(programdata, "Microsoft", "Network", "Downloader"),
        os.path.join(programdata, "Microsoft", "Windows", "RetailDemo"),
        os.path.join(programdata, "NVIDIA Corporation", "Downloader"),
    ]


def _is_drive_root(path: str) -> bool:
    p = normalize(path)
    if p.startswith("\\\\"):
        parts = [x for x in p.split("\\") if x]
        return len(parts) <= 2
    drive, rest = os.path.splitdrive(p)
    return bool(drive) and rest.strip("\\") == ""


def _top_component(path: str) -> str:
    p = normalize(path)
    _drive, rest = os.path.splitdrive(p)
    parts = [x for x in rest.split("\\") if x]
    return parts[0].lower() if parts else ""


def _basename(path: str) -> str:
    return os.path.basename(normalize(path).rstrip("\\")).lower()


def _parent(path: str) -> str:
    return os.path.dirname(normalize(path).rstrip("\\"))


def _has_user_component(path: str) -> bool:
    parts = [p for p in normalize(path).split("\\") if p]
    return "users" in parts


def protected_reason(path: str) -> Optional[str]:
    """Return a human-readable reason, or None when deletion may proceed."""
    p = normalize(path)
    if _is_drive_root(p):
        return "磁盘/共享根目录不能删除"
    base = _basename(p)
    if base in _PROTECTED_BASENAMES:
        return "版本库/凭据/配置文件目录，不能删除"
    if base in _SYSTEM_FILES:
        return "系统托管文件，不能直接删除"

    windir = normalize(_windir())
    if p == windir:
        return "Windows 系统目录不能整体删除"
    if is_subpath(p, windir):
        if any(is_subpath(p, normalize(item)) for item in windows_allowlist()):
            return None
        return "Windows 系统目录（不在可清理白名单内）"

    for pf in _program_files():
        if is_subpath(p, normalize(pf)):
            return "程序安装目录不能删除；请用卸载器"

    programdata = normalize(_programdata())
    if p == programdata:
        return "共享应用数据根目录不能整体删除"
    if is_subpath(p, programdata):
        if any(is_subpath(p, normalize(item)) for item in programdata_allowlist()):
            return None
        for blocked in (
            os.path.join(_programdata(), "Package Cache"),
            os.path.join(_programdata(), "Microsoft", "Windows Defender"),
            os.path.join(_programdata(), "Microsoft", "Search"),
        ):
            if is_subpath(p, normalize(blocked)):
                return "安装器/Defender/搜索索引目录，不能删除"
        return "ProgramData 下的共享数据（不在可清理白名单内）"

    # Any drive's top-level system-looking folder is protected.  A backup copy
    # nested deeper (e.g. D:\Backup\Windows) is still data and may be selected.
    if _top_component(p) in ("windows", "program files", "program files (x86)", "programdata"):
        return "系统/程序目录不能删除"

    # User profiles on any drive: profile root, standard folders and AppData
    # roots are always protected.  Downloads is intentionally allowed.
    if _has_user_component(p):
        if base == "users":
            return "用户配置文件根目录不能删除"
        parent = _parent(p)
        if _basename(parent) == "users":
            return "用户配置文件根目录不能删除"
        if base in _USER_DATA_NAMES:
            return "用户数据目录不能整体删除"
        if base == "appdata":
            return "AppData 根目录不能整体删除"
        if base in ("local", "roaming", "locallow") and _basename(parent) == "appdata":
            return "AppData 子根目录不能整体删除"
        if base == "packages" and normalize(parent).endswith("\\appdata\\local"):
            return "UWP 应用数据根目录不能整体删除"
        if base == "programs" and normalize(parent).endswith("\\appdata\\local"):
            return "用户级程序安装目录不能删除"
        if base == "windowsapps" and normalize(parent).endswith(
            "\\appdata\\local\\microsoft"
        ):
            return "应用执行别名目录不能删除"

    for name in ("Recovery", "Boot", "System Volume Information", "$Recycle.Bin", "Config.Msi"):
        candidate = normalize(os.path.join(volume_root(path), name))
        if is_subpath(p, candidate):
            return f"{name} 是系统托管目录，不能删除"

    if p.endswith("\\system volume information"):
        return "System Volume Information 是系统托管目录，不能删除"
    if p.endswith("\\$recycle.bin"):
        return "回收站目录不能整体删除；请清空回收站"
    return None
