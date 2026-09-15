#!/usr/bin/env python3
"""Region-mode color extraction from one frame.

Reads the cropped region as raw RGB, counts exact colors, then greedily
merges near-identical colors and reports dominant clusters. The mean luma of
the region doubles as a cheap "how much is drawn here" fill-progress proxy.

Usage:
    python palette.py <input> --at 15.4 --crop 500x500+110+230
        [--min-sat 40] [--min-share 0.005] [--top 8] [--merge 16] [--output-dir DIR]

Writes data/palette.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    default_output_dir,
    fail_manifest,
    run_bytes,
    update_manifest,
    write_json,
)

CROP_RE = re.compile(r"(\d+)x(\d+)\+(\d+)\+(\d+)")


def parse_crop(spec: str) -> tuple[int, int, int, int]:
    match = CROP_RE.fullmatch(spec.strip())
    if not match:
        raise ValueError(f"--crop must look like 500x500+110+230, got: {spec}")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def read_region(input_path: Path, t: float, w: int, h: int, x: int, y: int) -> bytes:
    raw = run_bytes(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-ss", f"{t:.3f}",
            "-i", str(input_path), "-frames:v", "1",
            "-vf", f"crop={w}:{h}:{x}:{y}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]
    )
    expected = w * h * 3
    if len(raw) < expected:
        raise RuntimeError(
            f"raw region short read: got {len(raw)} bytes, expected {expected}"
        )
    return raw[:expected]


def cluster_colors(counter: Counter, merge_dist: int) -> list[dict]:
    """Greedy clustering: biggest color absorbs all unclaimed colors within
    Chebyshev distance <= merge_dist; cluster representative = its mode color."""
    ordered = sorted(counter.items(), key=lambda kv: -kv[1])
    claimed: set[int] = set()
    clusters = []
    for (r, g, b), count in ordered:
        key = (r << 16) | (g << 8) | b
        if key in claimed:
            continue
        claimed.add(key)  # claim the representative before scanning, or it double-counts
        total = count
        best = (count, (r, g, b))
        for (r2, g2, b2), count2 in ordered:
            if (r2 << 16) | (g2 << 8) | b2 in claimed:
                continue
            if max(abs(r2 - r), abs(g2 - g), abs(b2 - b)) <= merge_dist:
                claimed.add((r2 << 16) | (g2 << 8) | b2)
                total += count2
                if count2 > best[0]:
                    best = (count2, (r2, g2, b2))
        clusters.append({"rgb": best[1], "pixels": total})
    clusters.sort(key=lambda c: -c["pixels"])
    return clusters


def analyze(input_path: Path, t: float, crop: tuple[int, int, int, int],
            min_sat: int, min_share: float, top: int, merge_dist: int) -> dict:
    w, h, x, y = crop
    raw = read_region(input_path, t, w, h, x, y)
    pixels = len(raw) // 3
    counter = Counter(
        (raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)
    )
    total_px = sum(counter.values()) or 1
    mean_rgb = tuple(
        round(sum(color[i] * n for color, n in counter.items()) / total_px, 1)
        for i in range(3)
    )
    mean_luma = round(
        0.299 * mean_rgb[0] + 0.587 * mean_rgb[1] + 0.114 * mean_rgb[2], 1
    )

    clusters = cluster_colors(counter, merge_dist)

    def entry(cluster: dict) -> dict:
        r, g, b = cluster["rgb"]
        return {
            "hex": f"#{r:02X}{g:02X}{b:02X}",
            "rgb": [r, g, b],
            "pixels": cluster["pixels"],
            "share": round(cluster["pixels"] / total_px, 4),
            "saturation": max(r, g, b) - min(r, g, b),
        }

    dominant_all = [entry(c) for c in clusters[:3]]
    saturated = [
        entry(c)
        for c in clusters
        if (max(c["rgb"]) - min(c["rgb"])) >= min_sat
        and c["pixels"] / total_px >= min_share
    ][:top]

    return {
        "input": str(input_path),
        "t": t,
        "crop": {"w": w, "h": h, "x": x, "y": y},
        "method": (
            f"exact-color histogram over the {w}x{h} region, greedy merge within "
            f"Chebyshev distance {merge_dist}; 1x1 sampling is banned because a "
            f"single pixel reports misleading colors"
        ),
        "region": {
            "mean_rgb": list(mean_rgb),
            "mean_luma_0_255": mean_luma,
            "luma_note": "higher = emptier/whiter panel; a fill-progress proxy",
        },
        "dominant_any": dominant_all,
        "saturated": saturated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input")
    parser.add_argument("--at", type=float, required=True, help="Timestamp in seconds")
    parser.add_argument("--crop", required=True, help="Region WxH+X+Y (required; whole-frame is not a region)")
    parser.add_argument("--min-sat", type=int, default=40,
                        help="Min saturation (max-min channel, 0-255) to count as a 'color' (default 40)")
    parser.add_argument("--min-share", type=float, default=0.005,
                        help="Min pixel share of the region (default 0.005)")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--merge", type=int, default=16, help="Merge distance per channel (default 16)")
    parser.add_argument("--output-dir", default=None)
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
        crop = parse_crop(args.crop)
        payload = analyze(input_path, args.at, crop, args.min_sat, args.min_share,
                          args.top, args.merge)
        palette_path = out_dir / "data" / "palette.json"
        write_json(palette_path, payload)
        update_manifest(out_dir, "palette", status="ok", outputs=[palette_path])
        print(json.dumps({
            "dominant_any": payload["dominant_any"][:2],
            "saturated": payload["saturated"][:4],
            "mean_luma_0_255": payload["region"]["mean_luma_0_255"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "palette", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
