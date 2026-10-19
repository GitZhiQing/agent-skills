#!/usr/bin/env python3
"""Transcribe audio/video via the built-in Volcengine Seed ASR client.

asr_volc.py submits the audio to the hosted 录音文件识别大模型 API (pure
standard library) and returns utterances with timestamps; this script
extracts audio from a local video when needed, injects a hotword preset,
writes transcript.srt/.txt/.json and cleans up temporary files.

Usage:
    python transcribe.py <input> [--output-dir DIR]
        [--domain finance|education|tech|none] [--hotwords "extra,words"]
        [--language zh-CN]

Outputs: transcript.srt / transcript.txt / transcript.json in <output-dir>.
The API key resolves via env var or the skill's .env (see .env.example).

A video without an audio track, or an ASR run that completes but produces no
text, is NOT an error: the script records manifest status "no_speech" and
prints {"no_speech": true, "reason": "no_audio_track"|"asr_empty"} — the
caller switches to the screen-text branch (references/无口播与批量.md §1). An API failure
(network/auth/quota) remains fatal.
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
import asr_volc  # noqa: E402

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


def input_kind(input_path: Path) -> str:
    if str(input_path).startswith(("http://", "https://")):
        return "url"
    if input_path.suffix.lower() in VIDEO_EXTS:
        return "video"
    return "audio"


def has_audio_stream(input_path: Path) -> bool | None:
    """True/False for local video files; None when the check does not apply
    (URLs are probed by the ASR itself, audio files are audio by definition)."""
    if input_kind(input_path) != "video":
        return None
    proc = run(
        [
            "ffprobe", "-v", "quiet", "-select_streams", "a",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0",
            str(input_path),
        ],
        check=False,
    )
    if proc.returncode != 0:
        return None  # undeterminable; let audio extraction surface the real error
    return bool(proc.stdout.strip())


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


def _cleanup_dir(tmp_dir: Path) -> None:
    if not tmp_dir.exists():
        return
    for item in sorted(tmp_dir.rglob("*"), reverse=True):
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            item.rmdir()
    tmp_dir.rmdir()


def transcribe(input_path: Path, out_dir: Path, domain: str, extra_words: str | None,
               language: str | None) -> dict:
    kind = input_kind(input_path)
    if has_audio_stream(input_path) is False:
        return {
            "no_speech": True,
            "reason": "no_audio_track",
            "info": {"input_kind": kind},
        }

    cfg = asr_volc.api_config()  # raises with setup guidance when key missing

    preset = load_preset(domain) if domain not in ("none", "") else []
    hotwords = merge_hotwords(preset, extra_words)

    tmp_dir = out_dir / "tmp"
    audio, extracted = prepare_audio(input_path, tmp_dir)

    try:
        asr = asr_volc.transcribe_audio(
            audio, language=language, hotwords=hotwords or None
        )
    except Exception as exc:
        raise RuntimeError(f"ASR transcription failed: {exc}") from exc

    txt = asr["txt"]
    if not txt:
        # ASR completed but found no speech: BGM-only video, not an error.
        _cleanup_dir(tmp_dir)
        return {
            "no_speech": True,
            "reason": "asr_empty",
            "info": {"input_kind": kind},
        }

    chars = sum(
        1
        for ch in txt
        if ch.isalnum()  # CJK chars count, punctuation does not
    )
    suspect_no_speech = chars < 20 and not asr["srt"].strip()

    files = {
        "transcript.srt": (out_dir / "transcript.srt", asr["srt"], None),
        "transcript.txt": (out_dir / "transcript.txt", txt, None),
        "transcript.json": (out_dir / "transcript.json", None, asr["raw"]),
    }
    produced = []
    for _, (target, text, raw) in files.items():
        if text is not None and not text.strip():
            continue  # e.g. no utterances: skip the srt, keep txt+json
        target.parent.mkdir(parents=True, exist_ok=True)
        if raw is not None:
            write_json(target, raw)
        else:
            target.write_text(text, encoding="utf-8")
        produced.append(target)

    # Temporary media is removed only after the final outputs are verified
    # non-empty.
    for target in produced:
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"transcription output missing after write: {target}")
    _cleanup_dir(tmp_dir)

    return {
        "produced": produced,
        "info": {
            "asr_backend": "volc_seedasr",
            "model": cfg["resource_id"],
            "api_base": cfg["api_base"],
            "request_id": asr["request_id"],
            "domain": domain or "none",
            "hotwords": len([w for w in hotwords.split(",") if w]),
            "language": language,
            "audio_extracted": extracted,
            "input_kind": kind,
            "chars": chars,
            "suspect_no_speech": suspect_no_speech,
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
        if result.get("no_speech"):
            reason = result["reason"]
            if reason == "no_audio_track":
                hint = "输入视频无音轨：走无口播分支，用画面文案提取（references/无口播与批量.md §1）"
            elif result["info"].get("input_kind") == "audio":
                hint = "输入为纯音频且 ASR 无文本：无画面可提取文案，请与用户确认输入或检查转写后端配置"
            else:
                hint = "ASR 正常完成但无文本：疑似纯 BGM 无口播；读 overview 拼版确认后走无口播分支（references/无口播与批量.md §1）"
            record = update_manifest(out_dir, "transcribe", status="no_speech",
                                     extra={"no_speech": True, "reason": reason})
            print(json.dumps({"no_speech": True, "reason": reason,
                              "input_kind": result["info"].get("input_kind"),
                              "hint": hint, "status": record["status"]},
                             ensure_ascii=False))
            return 0
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
