#!/usr/bin/env python3
"""Quantify per-frame visual change via tblend difference.

Pipeline: tblend=all_mode=difference -> signalstats -> metadata=print YAVG.
Frame-to-frame YAVG is the mean absolute luma difference; values above
--threshold count as "the picture changed". Turns "looks slow" into a
checkable timeline of change events + still segments.

Usage:
    python detect_changes.py <input> [--output-dir DIR]
        [--threshold 0.55] [--merge-gap 0.15] [--still-threshold 0.1]
        [--min-still 1.0]

Writes data/changes.json and prints a compact event list to stdout.
The 0.55 default is calibrated on 720x1280 K-line shorts; raise it for busier
footage (camera motion, live action).
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


def collect_frames(input_path: Path) -> list[dict]:
    proc = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-vf",
            "tblend=all_mode=difference,signalstats,"
            "metadata=print:key=lavfi.signalstats.YAVG:file=-",
            "-f", "null", "-",
        ],
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"frame-diff pass failed:\n{proc.stderr[-2000:]}")
    frames: list[dict] = []
    pending_t: float | None = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "pts_time:" in line:
            try:
                pending_t = float(line.split("pts_time:")[1].split()[0])
            except (IndexError, ValueError):
                pending_t = None
        elif "lavfi.signalstats.YAVG=" in line and pending_t is not None:
            try:
                value = float(line.split("=")[1])
            except (IndexError, ValueError):
                continue
            frames.append({"t": pending_t, "v": value})
            pending_t = None
    return frames


def merge_events(
    frames: list[dict], threshold: float, merge_gap: float
) -> list[dict]:
    """Group above-threshold frames separated by <= merge_gap seconds."""
    events: list[dict] = []
    current: list[dict] = []
    for frame in frames:
        if frame["v"] > threshold:
            if current and frame["t"] - current[-1]["t"] > merge_gap:
                events.append(_finalize(current))
                current = []
            current.append(frame)
    if current:
        events.append(_finalize(current))
    return events


def _finalize(group: list[dict]) -> dict:
    peak = max(group, key=lambda f: f["v"])
    return {
        "t_start": group[0]["t"],
        "t_end": group[-1]["t"],
        "peak": peak["v"],
        "peak_t": peak["t"],
        "frames": len(group),
    }


def find_stills(frames: list[dict], still_threshold: float, min_still: float) -> list[dict]:
    """Runs of consecutive below-threshold frames lasting >= min_still seconds."""
    stills: list[dict] = []
    current: list[dict] = []
    for frame in frames:
        if frame["v"] < still_threshold:
            current.append(frame)
        else:
            if current and current[-1]["t"] - current[0]["t"] >= min_still:
                stills.append(
                    {
                        "t_start": current[0]["t"],
                        "t_end": current[-1]["t"],
                        "duration_s": round(current[-1]["t"] - current[0]["t"], 2),
                    }
                )
            current = []
    if current and current[-1]["t"] - current[0]["t"] >= min_still:
        stills.append(
            {
                "t_start": current[0]["t"],
                "t_end": current[-1]["t"],
                "duration_s": round(current[-1]["t"] - current[0]["t"], 2),
            }
        )
    return stills


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--threshold", type=float, default=0.55)
    parser.add_argument("--merge-gap", type=float, default=0.15,
                        help="Merge above-threshold frames <= this many seconds apart into one event")
    parser.add_argument("--still-threshold", type=float, default=0.1)
    parser.add_argument("--min-still", type=float, default=1.0)
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
        frames = collect_frames(input_path)
        if not frames:
            raise RuntimeError("no frame-diff values parsed from ffmpeg output")
        values = [f["v"] for f in frames]
        duration = frames[-1]["t"]
        events = merge_events(frames, args.threshold, args.merge_gap)
        stills = find_stills(frames, args.still_threshold, args.min_still)
        payload = {
            "input": str(input_path),
            "method": "tblend difference + signalstats YAVG (per-frame mean luma diff)",
            "params": {
                "threshold": args.threshold,
                "merge_gap_s": args.merge_gap,
                "still_threshold": args.still_threshold,
                "min_still_s": args.min_still,
            },
            "n_frames": len(frames),
            "duration_s": round(duration, 3),
            "stats": {
                "min": min(values),
                "mean": round(sum(values) / len(values), 4),
                "max": max(values),
            },
            "events": [
                {**e, "t_start": round(e["t_start"], 2), "t_end": round(e["t_end"], 2),
                 "peak": round(e["peak"], 2), "peak_t": round(e["peak_t"], 2)}
                for e in events
            ],
            "stills": stills,
            "summary": {
                "n_events": len(events),
                "events_per_sec": round(len(events) / duration, 3) if duration else None,
                "max_peak": round(max(values), 2),
                "longest_still_s": max((s["duration_s"] for s in stills), default=0.0),
            },
        }
        changes_path = out_dir / "data" / "changes.json"
        write_json(changes_path, payload)
        update_manifest(out_dir, "detect_changes", status="ok", outputs=[changes_path])
        print(json.dumps({
            "n_events": payload["summary"]["n_events"],
            "events_per_sec": payload["summary"]["events_per_sec"],
            "events": [
                f"{e['t_start']}({e['peak']})" for e in payload["events"]
            ],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "detect_changes", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
