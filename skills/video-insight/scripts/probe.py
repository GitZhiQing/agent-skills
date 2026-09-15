#!/usr/bin/env python3
"""ffprobe a media file into meta.json (duration / resolution / fps / codecs).

Usage:
    python probe.py <input> [--output-dir DIR]

Writes <output-dir>/meta.json and prints a compact JSON summary to stdout.
Default output dir: <cwd>/video-insight/<slug>/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    default_output_dir,
    fail_manifest,
    run,
    update_manifest,
    write_json,
)


def eval_rate(rate: str | None) -> float | None:
    """'30000/1001' -> 29.97; '0/0' or missing -> None."""
    if not rate:
        return None
    try:
        num, _, den = rate.partition("/")
        num_f = float(num)
        den_f = float(den) if den else 1.0
        if den_f == 0:
            return None
        return round(num_f / den_f, 3)
    except ValueError:
        return None


def probe(input_path: Path) -> dict:
    proc = run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(input_path),
        ]
    )
    raw = json.loads(proc.stdout)
    fmt = raw.get("format", {})

    def _f(name: str) -> float | None:
        try:
            return round(float(fmt.get(name)), 3)
        except (TypeError, ValueError):
            return None

    video = {}
    audio = {}
    for stream in raw.get("streams", []):
        if stream.get("codec_type") == "video" and not video:
            video = {
                "codec": stream.get("codec_name"),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "fps": eval_rate(
                    stream.get("avg_frame_rate") or stream.get("r_frame_rate")
                ),
                "nb_frames": int(stream["nb_frames"])
                if str(stream.get("nb_frames", "")).isdigit()
                else None,
                "bitrate_kbps": _stream_kbps(stream),
                "duration_s": _stream_duration(stream),
            }
        elif stream.get("codec_type") == "audio" and not audio:
            audio = {
                "codec": stream.get("codec_name"),
                "sample_rate": int(stream["sample_rate"])
                if str(stream.get("sample_rate", "")).isdigit()
                else None,
                "channels": stream.get("channels"),
                "duration_s": _stream_duration(stream),
            }

    meta = {
        "input": str(input_path),
        "container": fmt.get("format_name"),
        "duration_s": _f("duration"),
        "bitrate_kbps": _f("bit_rate") and round(_f("bit_rate") / 1000, 1),
        "size_bytes": int(fmt.get("size")) if str(fmt.get("size", "")).isdigit() else None,
        "video": video,
        "audio": audio,
        "ffprobe_raw": raw,
    }
    return meta


def _stream_kbps(stream: dict) -> float | None:
    try:
        return round(int(stream["bit_rate"]) / 1000, 1)
    except (KeyError, TypeError, ValueError):
        return None


def _stream_duration(stream: dict) -> float | None:
    for key in ("duration", "duration_ts"):
        try:
            return round(float(stream[key]), 3)
        except (KeyError, TypeError, ValueError):
            continue
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Video or audio file path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(json.dumps({"error": f"input not found: {input_path}"}))
        return 1
    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_output_dir(input_path)
    )

    try:
        meta = probe(input_path)
        meta_path = out_dir / "meta.json"
        write_json(meta_path, meta)
        update_manifest(out_dir, "probe", status="ok", outputs=[meta_path])
        summary = {k: meta[k] for k in ("duration_s", "video", "audio")}
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "probe", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
