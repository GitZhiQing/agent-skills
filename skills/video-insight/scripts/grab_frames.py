#!/usr/bin/env python3
"""Grab exact frames by timestamp, optionally cropped & zoomed.

Any timeline assertion you are about to write down must survive one of these
grabs — "looked right in the mosaic" is not evidence.

Usage:
    python grab_frames.py <input> --at "5.0,10.5" [--output-dir DIR] [--label NAME]
    python grab_frames.py <input> --at "20.5" --crop 720x80+0+930 --zoom 6
        [--flags neighbor|lanczos] [--output-dir DIR]

Outputs:
    evidence/keyframes/<label>_<t>s.jpg    full-resolution frame (default)
    evidence/crops/<label>_<t>s_<WxH>_x<zoom>.png   when --crop is given
    data/grabs.json                        what was grabbed, where, with what params
"""

from __future__ import annotations

import argparse
import json
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

CROP_RE = re.compile(r"(\d+)x(\d+)\+(\d+)\+(\d+)")


def parse_crop(spec: str) -> tuple[int, int, int, int]:
    match = CROP_RE.fullmatch(spec.strip())
    if not match:
        raise ValueError(f"crop must look like 720x120+0+915, got: {spec}")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def grab(
    input_path: Path,
    t: float,
    target: Path,
    *,
    crop: tuple[int, int, int, int] | None,
    zoom: int,
    flags: str,
) -> dict:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{t:.3f}", "-i", str(input_path)]
    if crop:
        w, h, x, y = crop
        cmd += [
            "-frames:v", "1",
            "-vf", f"crop={w}:{h}:{x}:{y},scale=iw*{zoom}:ih*{zoom}:flags={flags}",
            "-y", str(target),
        ]
        kind = "crop"
    else:
        cmd += ["-frames:v", "1", "-q:v", "2", "-y", str(target)]
        kind = "keyframe"
    run(cmd)
    return {
        "type": kind,
        "t": t,
        "file": str(target),
        "crop": "x".join(map(str, crop[:2])) + "+" + "+".join(map(str, crop[2:])) if crop else None,
        "zoom": zoom if crop else None,
        "flags": flags if crop else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input")
    parser.add_argument("--at", required=True,
                        help="Comma-separated timestamps in seconds, e.g. \"5.0,10.5,20.37\"")
    parser.add_argument("--crop", default=None, help="Region crop WxH+X+Y; switches to crop mode")
    parser.add_argument("--zoom", type=int, default=4, help="Crop upscale factor (default 4; 4-8 recommended)")
    parser.add_argument("--flags", choices=("neighbor", "lanczos"), default="neighbor",
                        help="Upscale interpolation: neighbor for text/pixels, lanczos for photos")
    parser.add_argument("--label", default=None, help="Filename prefix (default: input slug)")
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
    from _common import slugify

    label = args.label or slugify(str(input_path))
    crop = parse_crop(args.crop) if args.crop else None
    subdir = "crops" if crop else "keyframes"
    target_dir = out_dir / "evidence" / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        times = [float(x) for x in args.at.split(",") if x.strip()]
    except ValueError:
        print(json.dumps({"error": f"bad --at list: {args.at}"}))
        return 1

    records = []
    outputs = []
    try:
        for t in times:
            if crop:
                w, h, _, _ = crop
                name = f"{label}_{t:g}s_{w}x{h}_x{args.zoom}.png"
            else:
                name = f"{label}_{t:g}s.jpg"
            target = target_dir / name
            records.append(grab(input_path, t, target, crop=crop, zoom=args.zoom, flags=args.flags))
            outputs.append(target)
        payload = {
            "input": str(input_path),
            "seek": "input seek + decode (accurate frame at requested t)",
            "grabs": records,
        }
        grabs_path = out_dir / "data" / "grabs.json"
        write_json(grabs_path, payload)
        outputs.append(grabs_path)
        record = update_manifest(out_dir, "grab_frames", status="ok", outputs=outputs,
                                 extra={"grabs": len(records)})
        print(json.dumps({"grabbed": len(records), "status": record["status"]}, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "grab_frames", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
