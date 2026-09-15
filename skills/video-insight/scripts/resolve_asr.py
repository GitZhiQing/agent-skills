#!/usr/bin/env python3
"""Locate the upstream ASR helper without copying it.

Resolution order:
1. $VIDEO_INSIGHT_ASR_SCRIPT (explicit path)
2. <skills-root>/video-to-subtitle-summary/scripts/transcribe_volcengine_bigmodel.py
   (the sibling skill that owns transcription)
3. <this-skill>/scripts/transcribe_volcengine_bigmodel.py (user-placed copy)

Also reports whether VOLC_BIGMODEL_API_KEY is discoverable (env var, upstream
skill .env, or this skill's .env). Prints JSON; exit 0 when resolved, 1 with
guidance otherwise.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
SKILLS_ROOT = SKILL_DIR.parent
ASR_FILENAME = "transcribe_volcengine_bigmodel.py"
UPSTREAM_RELATIVE = Path("video-to-subtitle-summary") / "scripts" / ASR_FILENAME
ENV_KEYS = ("VOLC_BIGMODEL_API_KEY",)


def _candidates() -> list[tuple[str, Path]]:
    env_path = os.environ.get("VIDEO_INSIGHT_ASR_SCRIPT", "").strip()
    out = []
    if env_path:
        out.append(("env:VIDEO_INSIGHT_ASR_SCRIPT", Path(env_path).expanduser()))
    out.append(("sibling-skill", SKILLS_ROOT / UPSTREAM_RELATIVE))
    out.append(("local-copy", SCRIPTS_DIR / ASR_FILENAME))
    return out


def _find_api_key(asr_script: Path) -> dict:
    """Look for a non-empty VOLC_BIGMODEL_API_KEY in env or nearby .env files."""
    env_value = os.environ.get("VOLC_BIGMODEL_API_KEY", "").strip()
    if env_value:
        return {"configured": True, "source": "environment variable"}
    # asr script lives in <skill>/scripts/; its skill dir .env is authoritative
    asr_env = asr_script.parents[1] / ".env"
    for env_file in (asr_env, SKILL_DIR / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("VOLC_BIGMODEL_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return {"configured": True, "source": str(env_file)}
    return {"configured": False, "source": None}


def resolve_asr() -> dict:
    for source, path in _candidates():
        if path.is_file():
            key = _find_api_key(path.resolve())
            return {
                "ok": True,
                "source": source,
                "asr_script": str(path.resolve()),
                "asr_skill_dir": str(path.resolve().parents[1]),
                "api_key": key,
            }
    return {
        "ok": False,
        "source": None,
        "asr_script": None,
        "candidates": [
            {"source": s, "path": str(p)} for s, p in _candidates()
        ],
        "hint": (
            "Set VIDEO_INSIGHT_ASR_SCRIPT to transcribe_volcengine_bigmodel.py, "
            "install the video-to-subtitle-summary skill next to video-insight, "
            "or drop a copy of the script into "
            f"{SCRIPTS_DIR}"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    result = resolve_asr()
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
