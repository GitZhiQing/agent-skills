#!/usr/bin/env python3
"""Three-layer audio probing: pauses, loudness, noise floor + spectrogram.

No single measurement proves "no BGM" — silencedetect (pauses), loudnorm
(LUFS/TP/LRA), astats (noise floor, per-pause RMS) and the spectrogram must
agree. This script only produces data; the verdict is written by the analyst
after cross-checking the layers.

Usage:
    python audio_probe.py <input> [--output-dir DIR] [--noise-db -30]
        [--min-pause 0.2] [--range 11:21]

Writes data/audio.json, evidence/audio/spectrogram_full.png and, with
--range, evidence/audio/spectrogram_<start>-<end>s.png.
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


def detect_pauses(input_path: Path, noise_db: str, min_pause: float) -> list[dict]:
    proc = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-af", f"silencedetect=noise={noise_db}dB:d={min_pause}",
            "-f", "null", "-",
        ],
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"silencedetect failed:\n{proc.stderr[-1500:]}")
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", proc.stderr)]
    pauses = []
    for i, start in enumerate(starts):
        end = ends[i] if i < len(ends) else None
        pauses.append(
            {
                "start": round(start, 2),
                "end": round(end, 2) if end is not None else None,
                "duration_s": round(end - start, 2) if end is not None else None,
            }
        )
    return pauses


def loudness(input_path: Path) -> dict:
    proc = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-af", "loudnorm=print_format=json", "-f", "null", "-",
        ],
        check=False,
    )
    blocks = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if not blocks:
        raise RuntimeError("loudnorm produced no JSON (analysis pass failed)")
    data = json.loads(blocks[-1])

    def _num(key: str) -> float | None:
        try:
            return float(data.get(key))
        except (TypeError, ValueError):
            return None

    return {
        "lufs": _num("input_i"),
        "true_peak_dbtp": _num("input_tp"),
        "lra": _num("input_lra"),
        "threshold": _num("input_thresh"),
    }


def _astats_overall(stderr: str, keys: tuple[str, ...]) -> dict:
    """Pull requested keys from the 'Overall' section of astats output."""
    result: dict = {}
    section = None
    for line in stderr.splitlines():
        if "Overall" in line:
            section = "overall"
            continue
        if "Channel layout" in line:
            section = "channel"
            continue
        if section != "overall":
            continue
        for key in keys:
            match = re.search(rf"{re.escape(key)}:\s*(-?[\d.]+|-inf)", line)
            if match:
                value = match.group(1)
                result[key] = float(value) if value != "-inf" else float("-inf")
    return result


def overall_stats(input_path: Path) -> dict:
    proc = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-af", "astats", "-f", "null", "-",
        ],
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"astats failed:\n{proc.stderr[-1500:]}")
    return _astats_overall(
        proc.stderr, ("RMS level dB", "Peak level dB", "Noise floor dB")
    )


def pause_rms(input_path: Path, pause: dict) -> float | None:
    if pause["end"] is None:
        return None
    proc = run(
        [
            "ffmpeg", "-hide_banner", "-nostats",
            "-ss", str(pause["start"]), "-t", str(pause["duration_s"]),
            "-i", str(input_path),
            "-af", "astats", "-f", "null", "-",
        ],
        check=False,
    )
    if proc.returncode != 0:
        return None
    stats = _astats_overall(proc.stderr, ("RMS level dB",))
    return stats.get("RMS level dB")


def spectrogram(input_path: Path, target: Path, start: float | None, end: float | None) -> bool:
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", str(start), "-t", str((end or 0) - start)]
    cmd += [
        "-i", str(input_path),
        "-lavfi", "showspectrumpic=s=1600x900:legend=1",
        "-y", str(target),
    ]
    proc = run(cmd, check=False)
    return proc.returncode == 0 and target.exists() and target.stat().st_size > 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--noise-db", default="-30", help="silencedetect noise floor (default -30)")
    parser.add_argument("--min-pause", type=float, default=0.2, help="Minimum pause length (default 0.2s)")
    parser.add_argument("--range", default=None,
                        help="Extra zoomed spectrogram as START:END seconds, e.g. 11:21")
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
        audio_dir = out_dir / "evidence" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        pauses = detect_pauses(input_path, args.noise_db, args.min_pause)
        for pause in pauses:
            rms = pause_rms(input_path, pause)
            pause["rms_db"] = round(rms, 1) if rms is not None else None
        levels = loudness(input_path)
        stats = overall_stats(input_path)

        spectrograms = []
        full = audio_dir / "spectrogram_full.png"
        if spectrogram(input_path, full, None, None):
            spectrograms.append({"file": str(full), "range_s": [0.0, None]})
        if args.range:
            try:
                start_s, end_s = (float(x) for x in args.range.split(":", 1))
                zoom = audio_dir / f"spectrogram_{start_s:g}-{end_s:g}s.png"
                if spectrogram(input_path, zoom, start_s, end_s):
                    spectrograms.append({"file": str(zoom), "range_s": [start_s, end_s]})
            except ValueError:
                pass

        payload = {
            "input": str(input_path),
            "params": {"noise_db": args.noise_db, "min_pause_s": args.min_pause},
            "loudness": levels,
            "overall": {
                "rms_db": stats.get("RMS level dB"),
                "peak_db": stats.get("Peak level dB"),
                "noise_floor_db": stats.get("Noise floor dB"),
            },
            "pauses": pauses,
            "spectrograms": spectrograms,
            "reading_guide": (
                "dry voice only: noise floor very low (<-70dB or ≈-53 with room tone), "
                "pause RMS ≈ overall RMS - 20dB or lower, spectrogram shows energy only "
                "in speech band; a BGM layer keeps pauses well above the noise floor "
                "and adds sustained tonal energy below 500Hz."
            ),
        }
        audio_path = out_dir / "data" / "audio.json"
        write_json(audio_path, payload)
        outputs = [audio_path] + [Path(s["file"]) for s in spectrograms]
        record = update_manifest(out_dir, "audio_probe", status="ok", outputs=outputs,
                                 extra={"pauses": len(pauses), "spectrograms": len(spectrograms)})
        print(json.dumps({
            "loudness": levels,
            "overall": payload["overall"],
            "pauses": len(pauses),
            "spectrograms": len(spectrograms),
            "status": record["status"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "audio_probe", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
