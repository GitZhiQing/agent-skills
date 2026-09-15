#!/usr/bin/env python3
"""Turn frame-diff events/stills into per-screen intervals for screen text.

Input is data/changes.json from detect_changes.py — burned-in text videos
(text cards switching over BGM) leave exactly the signature stills + events
produce: each card is a stable still, each switch is an event burst. This
script turns that signature into candidate "one screen of text" intervals,
each with a grab_at timestamp to frame-check with grab_frames.py or
screen_ocr.py. No ffmpeg here: pure JSON transform, so it is fully testable.

Segmentation rules (candidates, the model verifies by reading frames):
- stills are the anchors: one still = one screen, grab_at = still midpoint;
- the boundary between two adjacent screens is the first event AFTER the
  earlier still ends (the picture starts changing away from it), falling
  back to the gap midpoint when no event separates them;
- event clusters fully before the first / after the last still (>=
  --min-screen-gap long) become their own screens (animated intro/outro),
  grab_at = cluster end (content most complete);
- no stills at all: event clusters anchor the screens; no events either:
  uniform sampling (--uniform-interval), timestamps only "约" precision;
- more anchors than --max-screens: fall back to uniform sampling so
  coverage is kept while the frame budget is not blown.
  Splitting errs on the generous side — adjacent screens with identical text
  are merged by the model when reading, missed content is not recoverable.

Usage:
    python screen_segments.py <changes.json> --output-dir DIR
        [--min-screen-gap 2.0] [--uniform-interval 2.0] [--max-screens 60]

Writes data/screen_segments.json; prints a compact segment list to stdout.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    default_output_dir,
    fail_manifest,
    read_json,
    update_manifest,
    write_json,
)


def _r2(value: float) -> float:
    return round(float(value), 2)


def cluster_events(events: list[dict], min_screen_gap: float) -> list[dict]:
    """Merge events whose gap to the previous one is < min_screen_gap.

    A typewriter/fade build-up emits a dense burst of small events — one
    screen forming — while consecutive screens are separated by the still
    in between (>= min-still seconds, default 1.0)."""
    clusters: list[dict] = []
    for event in events:
        if clusters and event["t_start"] - clusters[-1]["t_end"] < min_screen_gap:
            clusters[-1]["t_end"] = max(clusters[-1]["t_end"], event["t_end"])
            clusters[-1]["n_events"] += 1
        else:
            clusters.append({
                "t_start": event["t_start"],
                "t_end": event["t_end"],
                "n_events": 1,
            })
    return clusters


def _boundary(prev: dict, nxt: dict, events: list[dict]) -> float:
    """Screen boundary between two anchors: the departure change after prev
    ends; when none separates them, an event-anchored next screen starts at
    its own first change, otherwise fall back to the gap midpoint."""
    for event in events:
        if prev["t_end"] < event["t_start"] < nxt["t_start"]:
            return event["t_start"]
    if nxt.get("basis") == "event_settle":
        return nxt["t_start"]
    return (prev["t_end"] + nxt["t_start"]) / 2


def _uniform_segments(duration: float, interval: float, max_screens: int) -> list[dict]:
    n = max(1, min(max_screens, math.ceil(duration / interval)))
    cuts = [_r2(k * duration / n) for k in range(n + 1)]
    return [
        {
            "t_start": cuts[k],
            "t_end": cuts[k + 1],
            "grab_at": _r2((cuts[k] + cuts[k + 1]) / 2),
            "basis": "sample",
            "still_s": None,
        }
        for k in range(n)
    ]


def build_segments(
    changes: dict,
    *,
    min_screen_gap: float = 2.0,
    uniform_interval: float = 2.0,
    max_screens: int = 60,
) -> dict:
    duration = _r2(changes.get("duration_s") or 0)
    if duration <= 0:
        raise ValueError("changes.json has no positive duration_s")
    events = sorted(changes.get("events") or [], key=lambda e: e["t_start"])
    stills = sorted(changes.get("stills") or [], key=lambda s: s["t_start"])

    mode = "uniform"
    fallback_reason: str | None = None
    anchors: list[dict] = []

    if stills:
        mode = "event"
        clusters = cluster_events(events, min_screen_gap)
        leading = [c for c in clusters if c["t_end"] <= stills[0]["t_start"]]
        trailing = [c for c in clusters if c["t_start"] >= stills[-1]["t_end"]]
        for cluster in leading:
            if cluster["t_end"] - cluster["t_start"] >= min_screen_gap or cluster["n_events"] > 1:
                anchors.append({**cluster, "basis": "event_settle"})
        for still in stills:
            anchors.append({
                "t_start": still["t_start"],
                "t_end": still["t_end"],
                "basis": "still_mid",
                "still_s": still.get("duration_s"),
            })
        for cluster in trailing:
            if cluster["t_end"] - cluster["t_start"] >= min_screen_gap or cluster["n_events"] > 1:
                anchors.append({**cluster, "basis": "event_settle"})
        if len(anchors) > max_screens:
            mode = "uniform"
            fallback_reason = (
                f"{len(anchors)} anchors exceed --max-screens {max_screens}; "
                "uniform sampling keeps coverage within the frame budget"
            )
            anchors = []
    elif events:
        mode = "event"
        anchors = [
            {**cluster, "basis": "event_settle"}
            for cluster in cluster_events(events, min_screen_gap)
        ]
        if len(anchors) > max_screens:
            mode = "uniform"
            fallback_reason = (
                f"{len(anchors)} event clusters exceed --max-screens {max_screens}; "
                "uniform sampling keeps coverage within the frame budget"
            )
            anchors = []
    if mode == "uniform" and not anchors:
        anchors = [
            {**segment, "n_events": None}
            for segment in _uniform_segments(duration, uniform_interval, max_screens)
        ]
        if fallback_reason is None:
            fallback_reason = (
                "no stable stills found (continuous animation); "
                "uniform sampling, timestamps at 约 precision"
            )

    segments: list[dict] = []
    for idx, anchor in enumerate(anchors):
        if idx == 0:
            t_start = 0.0
        else:
            t_start = _boundary(anchors[idx - 1], anchor, events)
        if idx == len(anchors) - 1:
            t_end = duration
        else:
            t_end = _boundary(anchor, anchors[idx + 1], events)
        t_start, t_end = _r2(t_start), _r2(t_end)
        if t_end <= t_start:
            t_end = _r2(t_start + 0.01)
        if anchor["basis"] == "still_mid":
            grab_at = _r2((anchor["t_start"] + anchor["t_end"]) / 2)
        else:  # event_settle / sample already carry a usable moment
            grab_at = _r2(anchor.get("grab_at", anchor["t_end"]))
        segments.append({
            "i": idx + 1,
            "t_start": t_start,
            "t_end": t_end,
            "grab_at": min(max(grab_at, t_start), t_end),
            "basis": anchor["basis"],
            "still_s": anchor.get("still_s"),
        })

    return {
        "mode": mode,
        "fallback_reason": fallback_reason,
        "params": {
            "min_screen_gap_s": min_screen_gap,
            "uniform_interval_s": uniform_interval,
            "max_screens": max_screens,
        },
        "duration_s": duration,
        "segments": segments,
        "summary": {
            "n_screens": len(segments),
            "mode": mode,
            "bases": sorted({s["basis"] for s in segments}),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("changes", help="Path to data/changes.json (detect_changes.py output)")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--min-screen-gap", type=float, default=2.0,
                        help="Event bursts closer than this merge into one screen (default 2.0)")
    parser.add_argument("--uniform-interval", type=float, default=2.0,
                        help="Sampling interval for the uniform fallback (default 2.0)")
    parser.add_argument("--max-screens", type=int, default=60,
                        help="Frame-budget cap; more anchors fall back to uniform sampling")
    args = parser.parse_args(argv)

    changes_path = Path(args.changes).expanduser().resolve()
    if not changes_path.exists():
        print(json.dumps({"error": f"input not found: {changes_path}"}))
        return 1
    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_output_dir(changes_path)
    )

    try:
        changes = read_json(changes_path)
        payload = {
            "input": str(changes_path),
            **build_segments(
                changes,
                min_screen_gap=args.min_screen_gap,
                uniform_interval=args.uniform_interval,
                max_screens=args.max_screens,
            ),
        }
        segments_path = out_dir / "data" / "screen_segments.json"
        write_json(segments_path, payload)
        record = update_manifest(out_dir, "screen_segments", status="ok",
                                 outputs=[segments_path])
        print(json.dumps({
            "n_screens": payload["summary"]["n_screens"],
            "mode": payload["mode"],
            "fallback_reason": payload["fallback_reason"],
            "status": record["status"],
            "segments": [
                f"{s['t_start']}-{s['t_end']}(grab@{s['grab_at']})"
                for s in payload["segments"]
            ],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "screen_segments", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
