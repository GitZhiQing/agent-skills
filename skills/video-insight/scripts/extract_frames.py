#!/usr/bin/env python3
"""Extract per-second overview tiles + a subtitle timeline strip.

Every image cell gets its exact timestamp recorded in JSON, taken from
ffmpeg's own showinfo output, so no one has to infer "which second is this
cell" from a grid position.

Usage:
    python extract_frames.py <input> [--output-dir DIR] [--fps 1]
        [--tile 4x2] [--scale-width 360]
        [--strip-crop WxH+X+Y] [--strip-cells 60] [--no-strip]

Outputs:
    evidence/overview/overview_NN.jpg      tile mosaic (default 8 cells each)
    evidence/subtitle-strip/strip_NN.jpg   vertical subtitle timeline
    data/frames_overview.json              per-image cell -> exact pts map
    data/frames_subtitle_strip.json        per-image cell -> exact pts map

Default subtitle strip crop is proportional to the 720x1280 finance template
(y = 71.5% of height, h = 9.4% of height, full width); override with
--strip-crop WxH+X+Y when the layout differs.
"""

from __future__ import annotations

import argparse
import json
import math
import re
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

SHOWINFO_RE = re.compile(r"n:\s*(\d+)\s+pts:\s*\d+\s+pts_time:([\d.]+)")


def parse_showinfo(stderr: str) -> dict[int, float]:
    """Map frame index n -> exact pts_time, straight from ffmpeg."""
    mapping: dict[int, float] = {}
    for match in SHOWINFO_RE.finditer(stderr):
        mapping[int(match.group(1))] = float(match.group(2))
    return mapping


def video_dims(input_path: Path) -> tuple[int, int, float]:
    proc = run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", str(input_path),
        ]
    )
    streams = json.loads(proc.stdout).get("streams", [])
    for stream in streams:
        if stream.get("codec_type") == "video":
            rate = stream.get("avg_frame_rate") or "0/1"
            try:
                num, _, den = rate.partition("/")
                fps = float(num) / float(den or 1) if float(den or 1) else 0.0
            except ValueError:
                fps = 0.0
            return int(stream["width"]), int(stream["height"]), fps
    raise RuntimeError(f"no video stream in {input_path}")


def duration_of(input_path: Path) -> float:
    proc = run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(input_path),
        ]
    )
    try:
        return float(json.loads(proc.stdout)["format"]["duration"])
    except (KeyError, ValueError):
        return 0.0


def parse_crop(spec: str) -> str:
    """Validate 'WxH+X+Y' and return an ffmpeg crop=w:h:x:y expression."""
    match = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", spec.strip())
    if not match:
        raise ValueError(f"--strip-crop must look like 720x120+0+915, got: {spec}")
    return ":".join(match.groups())


def extract_tiles(
    input_path: Path,
    out_dir: Path,
    *,
    fps: float,
    tile: str,
    scale_width: int,
    extra_filter: str | None,
    subdir: str,
    stem: str,
) -> tuple[list[Path], dict[int, float]]:
    """fps-sample -> (optional crop) -> scale -> showinfo -> tile. Returns images + frame timestamps."""
    filters = [f"fps={fps}"]
    if extra_filter:
        filters.append(extra_filter)
    if subdir == "overview":
        filters.append(f"scale={scale_width}:-2:flags=lanczos")
    filters.append("showinfo")
    filters.append(f"tile={tile}")
    graph = ",".join(filters)
    target = out_dir / "evidence" / subdir
    target.mkdir(parents=True, exist_ok=True)
    proc = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-vf", graph, "-y", str(target / f"{stem}_%02d.jpg"),
        ],
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tile extraction failed:\n{proc.stderr[-2000:]}")
    images = sorted(target.glob(f"{stem}_*.jpg"))
    return images, parse_showinfo(proc.stderr)


def cells_for(images: list[Path], stamps: dict[int, float], cells_per_image: int) -> list[dict]:
    """Build per-image cell manifests; missing stamps mark padded cells."""
    result = []
    for image_index, image in enumerate(images):
        cells = []
        for cell in range(cells_per_image):
            g = image_index * cells_per_image + cell
            cells.append(
                {
                    "cell": cell,
                    "frame_index": g,
                    "t_exact": stamps.get(g),  # None => padding after the last frame
                }
            )
        result.append({"file": image.name, "cells": cells})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Video file path")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--fps", type=float, default=1.0, help="Sampling rate (default 1 = one frame per second)")
    parser.add_argument("--tile", default="4x2", help="Tile layout COLSxROWS (default 4x2)")
    parser.add_argument("--scale-width", type=int, default=360, help="Cell width in the mosaic (default 360)")
    parser.add_argument("--strip-crop", default=None,
                        help="Subtitle strip crop 'WxH+X+Y'; default = full width, y=71.5%%h, h=9.4%%h")
    parser.add_argument("--strip-cells", type=int, default=60, help="Cells per strip image (default 60)")
    parser.add_argument("--no-strip", action="store_true", help="Skip the subtitle strip")
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
        width, height, _ = video_dims(input_path)
        duration = duration_of(input_path)
        cols, rows = (int(x) for x in args.tile.split("x"))
        cells_per_image = cols * rows
        n_samples = math.ceil(duration * args.fps) if duration else None

        images, stamps = extract_tiles(
            input_path, out_dir,
            fps=args.fps, tile=args.tile, scale_width=args.scale_width,
            extra_filter=None, subdir="overview", stem="overview",
        )
        overview_manifest = {
            "input": str(input_path),
            "sampling": f"fps={args.fps} (round=near: cell content = source frame closest to t_exact)",
            "tile": args.tile,
            "scale_width": args.scale_width,
            "video": {"width": width, "height": height, "duration_s": duration},
            "expected_images": math.ceil(n_samples / cells_per_image) if n_samples else None,
            "images": cells_for(images, stamps, cells_per_image),
        }

        outputs = list(images)
        data_dir = out_dir / "data"
        overview_json = data_dir / "frames_overview.json"
        write_json(overview_json, overview_manifest)
        outputs.append(overview_json)

        if not args.no_strip:
            if args.strip_crop:
                crop = parse_crop(args.strip_crop)
            else:
                y = int(height * 0.715)
                h = int(height * 0.094)
                crop = f"{width}:{h}:0:{y}"
            strip_images, strip_stamps = extract_tiles(
                input_path, out_dir,
                fps=args.fps, tile=f"1x{args.strip_cells}", scale_width=args.scale_width,
                extra_filter=f"crop={crop}", subdir="subtitle-strip", stem="strip",
            )
            strip_manifest = {
                "input": str(input_path),
                "sampling": f"fps={args.fps} (round=near: cell content = source frame closest to t_exact)",
                "crop": crop,
                "note": "each cell = one second of the subtitle band; read top-to-bottom",
                "images": cells_for(strip_images, strip_stamps, args.strip_cells),
            }
            strip_json = data_dir / "frames_subtitle_strip.json"
            write_json(strip_json, strip_manifest)
            outputs.append(strip_json)
            outputs.extend(strip_images)

        record = update_manifest(
            out_dir, "extract_frames", status="ok", outputs=outputs,
            extra={
                "overview_images": len(images),
                "overview_expected": overview_manifest["expected_images"],
                "strip_images": len(strip_images) if not args.no_strip else 0,
            },
        )
        print(json.dumps({
            "overview_images": len(images),
            "overview_expected": overview_manifest["expected_images"],
            "strip_images": len(strip_images) if not args.no_strip else 0,
            "status": record["status"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "extract_frames", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
