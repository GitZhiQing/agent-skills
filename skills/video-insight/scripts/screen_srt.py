#!/usr/bin/env python3
"""Render transcript.screen.srt from a transcript.screen.json — mechanically.

The frames path of the no-speech branch (references/无口播与批量.md §1 b4) has the model
author transcript.screen.json (per-screen text, readability grades, merges);
this script turns that JSON into the SRT. Generating SRT by hand — especially
via inline `python -c` snippets — breaks on shell quoting of CJK quotes, so
the rendering lives here as a plain data transform. Same schema both ways:
the OCR-side assembler (pipeline.py assemble_screen_transcript) emits the
identical transcript.screen.json, so this script re-renders either path.

Render rules (same as the assembler):
- rows with empty text stay in the JSON only, they get no SRT cue;
- cue numbers run sequentially over the kept rows;
- timestamps HH:MM:SS,mmm via _common.fmt_ts.

Usage:
    python screen_srt.py <transcript.screen.json> [--output-dir DIR]

Output: <output-dir>/transcript.screen.srt (default: next to the input file).

Schema problems (missing/non-list "screens", rows without t_start/t_end)
exit 2; anything else failing exits 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    fail_manifest,
    fmt_ts,
    read_json,
    update_manifest,
)


class SchemaError(ValueError):
    """transcript.screen.json does not match the agreed schema."""


def render_srt(doc: dict) -> tuple[str, int, int]:
    """Return (srt_text, n_cues, n_skipped_empty) for a transcript.screen.json."""
    screens = doc.get("screens")
    if not isinstance(screens, list):
        raise SchemaError("transcript.screen.json has no \"screens\" list")
    blocks: list[str] = []
    skipped = 0
    for row in screens:
        if not isinstance(row, dict) or "t_start" not in row or "t_end" not in row:
            raise SchemaError(f"screen row without t_start/t_end: {row!r}")
        text = (row.get("text") or "").strip()
        if not text:
            skipped += 1
            continue
        blocks.append(
            f"{len(blocks) + 1}\n"
            f"{fmt_ts(float(row['t_start']))} --> {fmt_ts(float(row['t_end']))}\n{text}\n"
        )
    return "\n".join(blocks), len(blocks), skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("doc", help="Path to transcript.screen.json "
                                    "(model-authored or OCR-assembled)")
    parser.add_argument("--output-dir", default=None,
                        help="Directory for transcript.screen.srt and the "
                             "manifest record (default: the input's parent)")
    args = parser.parse_args(argv)

    doc_path = Path(args.doc).expanduser().resolve()
    if not doc_path.exists():
        print(json.dumps({"error": f"input not found: {doc_path}"}))
        return 1
    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else doc_path.parent
    )

    try:
        doc = read_json(doc_path)
    except Exception as exc:
        fail_manifest(out_dir, "screen_srt", exc)
        print(json.dumps({"error": f"unreadable JSON: {exc}"}))
        return 2

    try:
        srt_text, cues, skipped = render_srt(doc)
    except SchemaError as exc:
        fail_manifest(out_dir, "screen_srt", exc)
        print(json.dumps({"error": str(exc)}))
        return 2

    srt_path = out_dir / "transcript.screen.srt"
    try:
        srt_path.write_text(srt_text, encoding="utf-8")
        record = update_manifest(out_dir, "screen_srt", status="ok",
                                 outputs=[srt_path])
        print(json.dumps({
            "cues": cues,
            "skipped_empty": skipped,
            "output": str(srt_path),
            "status": record["status"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "screen_srt", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
