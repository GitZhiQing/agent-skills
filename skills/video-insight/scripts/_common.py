"""Shared helpers for video-insight scripts.

Conventions enforced here:
- Scripts emit structured JSON; ffmpeg stderr is never parsed by eye.
- No /tmp: the default workdir is <cwd>/video-insight/<slug>/, overridable
  with --output-dir (/tmp has no reliable meaning on Windows Git Bash).
- Every run records itself in <output-dir>/manifest.json and stat-checks its
  outputs, so a broken archive shows up immediately rather than silently.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# Windows consoles may default to a legacy codepage; force UTF-8 so printing
# JSON with Chinese filenames never crashes.
try:  # pragma: no cover - environment dependent
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WORKDIR_NAME = "video-insight"


def run(
    cmd: Sequence[str | Path], *, check: bool = True, timeout: int = 900
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture stdout/stderr as text (encoding-tolerant)."""
    argv = [str(c) for c in cmd]
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed (exit {proc.returncode}): {' '.join(argv)}\n"
            f"--- stderr (tail) ---\n{stderr[-4000:]}"
        )
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def run_bytes(
    cmd: Sequence[str | Path], *, check: bool = True, timeout: int = 900
) -> bytes:
    """Run a command and capture raw stdout bytes (for rawvideo/palette reads)."""
    argv = [str(c) for c in cmd]
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed (exit {proc.returncode}): {' '.join(argv)}\n"
            f"--- stderr (tail) ---\n{proc.stderr.decode('utf-8', 'replace')[-4000:]}"
        )
    return proc.stdout


def slugify(name: str) -> str:
    """Filesystem-safe slug from a filename; keeps CJK word characters."""
    stem = Path(name).stem or "video"
    slug = re.sub(r"[^\w]+", "_", stem, flags=re.UNICODE).strip("_")
    return slug[:60] or "video"


def default_output_dir(source: str | Path) -> Path:
    return Path.cwd() / WORKDIR_NAME / slugify(str(source))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def update_manifest(
    output_dir: Path,
    script: str,
    *,
    status: str,
    outputs: Iterable[Path] = (),
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict:
    """Record one script run into <output_dir>/manifest.json.

    Every listed output is stat-checked: a missing/empty file flips the record
    status to "missing_files" so archive failures are visible right away.
    """
    manifest_path = Path(output_dir) / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
        except Exception:
            manifest = {}
    entries = []
    missing = []
    for out in outputs:
        out = Path(out)
        if out.exists() and out.stat().st_size > 0:
            entries.append(
                {"file": out.name, "path": str(out), "bytes": out.stat().st_size}
            )
        else:
            missing.append(str(out))
    record: dict[str, Any] = {
        "status": status if not missing else "missing_files",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outputs": entries,
    }
    if missing:
        record["missing"] = missing
    if error:
        record["error"] = error
    if extra:
        record.update(extra)
    manifest.setdefault("scripts", {})[script] = record
    write_json(manifest_path, manifest)
    return record


def fail_manifest(output_dir: Path, script: str, exc: Exception) -> None:
    """Best-effort manifest record when a script dies mid-run."""
    try:
        update_manifest(
            Path(output_dir), script, status="failed", error=str(exc)[:2000]
        )
    except Exception:
        pass
