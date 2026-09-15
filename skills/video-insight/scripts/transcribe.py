#!/usr/bin/env python3
"""Transcribe via the upstream ASR helper with domain hotwords.

Wraps video-to-subtitle-summary's transcribe_volcengine_bigmodel.py:
extracts audio from a local video when needed, injects a hotword preset,
renames the outputs to transcript.* and cleans up temporary files.

Usage:
    python transcribe.py <input> [--output-dir DIR]
        [--domain finance|education|tech|none] [--hotwords "extra,words"]
        [--language zh-CN]

Outputs: transcript.srt / transcript.txt / transcript.json in <output-dir>.
The API key is read by the upstream script from its own .env (discovered
automatically); see .env.example if that is not configured.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _common import (  # noqa: E402
    default_output_dir,
    fail_manifest,
    run,
    update_manifest,
    write_json,
)
from resolve_asr import resolve_asr  # noqa: E402

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".flv", ".ts", ".m4v", ".wmv"}


def load_preset(domain: str) -> list[str]:
    path = SKILL_DIR / "presets" / "hotwords" / f"{domain}.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"unknown hotword preset '{domain}' (expected file: {path})"
        )
    words = [w.strip() for w in path.read_text(encoding="utf-8").split(",") if w.strip()]
    return words


def merge_hotwords(preset: list[str], extra: str | None) -> str:
    merged = list(preset)
    if extra:
        for word in extra.split(","):
            word = word.strip()
            if word and word not in merged:
                merged.append(word)
    return ",".join(merged)


def prepare_audio(input_path: Path, tmp_dir: Path) -> tuple[Path, bool]:
    """Return (audio file for ASR, whether it is a temporary extraction)."""
    text = str(input_path)
    if text.startswith(("http://", "https://")):
        return input_path, False  # public audio URL: the ASR handles it directly
    suffix = input_path.suffix.lower()
    if suffix in VIDEO_EXTS:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        audio = tmp_dir / "audio.mp3"
        run(
            [
                "ffmpeg", "-loglevel", "error", "-i", str(input_path),
                "-q:a", "0", "-map", "a", "-y", str(audio),
            ]
        )
        return audio, True
    return input_path, False


def transcribe(input_path: Path, out_dir: Path, domain: str, extra_words: str | None,
               language: str | None) -> dict:
    resolution = resolve_asr()
    if not resolution["ok"]:
        raise RuntimeError(resolution.get("hint", "ASR helper not found"))
    asr_script = Path(resolution["asr_script"])

    preset = load_preset(domain) if domain not in ("none", "") else []
    hotwords = merge_hotwords(preset, extra_words)

    tmp_dir = out_dir / "tmp"
    audio, extracted = prepare_audio(input_path, tmp_dir)

    asr_out = tmp_dir / "asr"
    cmd = [
        sys.executable, str(asr_script), str(audio),
        "--output-dir", str(asr_out),
    ]
    if language:
        cmd += ["--language", language]
    if hotwords:
        cmd += ["--hotwords", hotwords]
    proc = run(cmd, check=False, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"ASR script failed:\n{proc.stderr[-2000:]}")

    renames = {
        "subtitle.srt": out_dir / "transcript.srt",
        "text.txt": out_dir / "transcript.txt",
        "result.json": out_dir / "transcript.json",
    }
    produced = []
    for src_name, target in renames.items():
        src = asr_out / src_name
        if src.exists() and src.stat().st_size > 0:
            target.write_bytes(src.read_bytes())
            produced.append(target)
    if not any(p.suffix == ".txt" for p in produced):
        raise RuntimeError("ASR produced no text output")

    chars = sum(
        1
        for ch in next(p for p in produced if p.suffix == ".txt").read_text(encoding="utf-8")
        if ch.isalnum()  # CJK chars count, punctuation does not
    )

    # Temporary media and raw ASR outputs are removed only after the renamed
    # copies are verified non-empty.
    for target in produced:
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"transcription output missing after copy: {target}")
    if tmp_dir.exists():
        for item in sorted(tmp_dir.rglob("*"), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        tmp_dir.rmdir()

    return {
        "produced": produced,
        "info": {
            "asr_script": str(asr_script),
            "domain": domain or "none",
            "hotwords": len([w for w in hotwords.split(",") if w]),
            "language": language,
            "audio_extracted": extracted,
            "chars": chars,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Local video/audio file or public audio URL")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--domain", default="none",
                        help="Hotword preset: finance / education / tech / none")
    parser.add_argument("--hotwords", default=None, help="Extra comma-separated hotwords")
    parser.add_argument("--language", default="zh-CN",
                        help="Language hint (default zh-CN; pass '' for auto)")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser()
    if "://" not in str(input_path):
        input_path = input_path.resolve()
        if not input_path.exists():
            print(json.dumps({"error": f"input not found: {input_path}"}))
            return 1
    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_output_dir(str(input_path))
    )

    try:
        result = transcribe(input_path, out_dir, args.domain, args.hotwords,
                            args.language or None)
        record = update_manifest(out_dir, "transcribe", status="ok",
                                 outputs=result["produced"], extra=result["info"])
        print(json.dumps({**result["info"], "status": record["status"],
                          "outputs": [str(p) for p in result["produced"]]},
                         ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "transcribe", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
