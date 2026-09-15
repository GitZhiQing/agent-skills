#!/usr/bin/env python3
"""Environment self-check for video-insight.

One JSON verdict covering ffmpeg / ffprobe / python / ASR key / disk /
required filters / OCR fallback, so callers never hand-roll probes.
Exit 0 when nothing required is missing; exit 1 otherwise. A missing ASR
key or OCR token is only a warning: the no-speech branch, pre-existing
transcripts and L2 all work without them.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _common import get_config  # noqa: E402

# L2 needs these filters; missing ones are warnings (L1 still works) but
# anything in CORE_FILTERS missing means the pipeline is broken.
CORE_FILTERS = ("tblend", "signalstats", "metadata", "tile", "crop", "scale", "fps", "showinfo")
EXTRA_FILTERS = ("showspectrumpic", "loudnorm", "silencedetect", "astats")

OCR_TOKEN_ENV = "PADDLEOCR_ACCESS_TOKEN"
ASR_KEY_ENV = "VOLC_BIGMODEL_API_KEY"


def _version_of(binary: str) -> tuple[str | None, str | None]:
    path = shutil.which(binary)
    if not path:
        return None, None
    try:
        proc = subprocess.run(
            [binary, "-version"], capture_output=True, timeout=30
        )
        first = proc.stdout.decode("utf-8", "replace").splitlines()[0]
    except Exception as exc:
        return path, f"<error: {exc}>"
    match = re.search(r"version\s+(\S+)", first)
    return path, (match.group(1) if match else first.strip()[:40])


def _filter_report() -> tuple[list[str], list[str]]:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, timeout=60
        )
        text = proc.stdout.decode("utf-8", "replace")
    except Exception:
        return [], []
    names = set()
    for line in text.splitlines():
        parts = line.split()
        # filter rows look like: " TSC name  caps  description"; the flags
        # column only ever contains '.', 'T', 'S', 'C'.
        if len(parts) >= 3 and parts[0] and set(parts[0]) <= {".", "T", "S", "C"}:
            names.add(parts[1])
    missing_core = [f for f in CORE_FILTERS if f not in names]
    missing_extra = [f for f in EXTRA_FILTERS if f not in names]
    return missing_core, missing_extra


def _ocr_fallback_report() -> dict:
    """OCR capability for agents without image reading (screen_ocr.py):
    hosted PaddleOCR API via token, or a local paddleocr install."""
    info: dict = {
        "api_token": bool(get_config(OCR_TOKEN_ENV)),
        "paddleocr_local": False,
        "uv": bool(shutil.which("uv")),
        "usable": False,
        "how": None,
    }
    try:
        import paddleocr  # noqa: F401

        info["paddleocr_local"] = True
    except Exception:
        pass
    if info["api_token"]:
        info["usable"] = True
        info["how"] = f"hosted PaddleOCR API (${OCR_TOKEN_ENV} is set)"
    elif info["paddleocr_local"]:
        info["usable"] = True
        info["how"] = "local paddleocr install"
    elif info["uv"]:
        info["usable"] = True
        info["how"] = "uv run --with paddleocr --with paddlepaddle (first run downloads ~1-2 GB)"
    return info


def check(workdir: str = ".") -> dict:
    report: dict = {"ok": True, "missing": [], "warn": []}

    report["python"] = ".".join(map(str, sys.version_info[:3]))

    ffmpeg_path, ffmpeg_ver = _version_of("ffmpeg")
    ffprobe_path, ffprobe_ver = _version_of("ffprobe")
    report["ffmpeg"] = ffmpeg_ver
    report["ffprobe"] = ffprobe_ver
    if not ffmpeg_path:
        report["missing"].append("ffmpeg")
    if not ffprobe_path:
        report["missing"].append("ffprobe")

    # Transcription is a hosted API (asr_volc.py); a missing key only
    # disables the transcription step — the no-speech branch, pre-existing
    # transcripts and L2 all work without it, so warn instead of missing.
    asr_key = bool(get_config(ASR_KEY_ENV))
    report["asr"] = {
        "api_key": asr_key,
        "resource_id": get_config("VOLC_BIGMODEL_RESOURCE_ID", "volc.seedasr.auc"),
        "api_base": get_config("VOLC_BIGMODEL_API_BASE", "https://openspeech.bytedance.com"),
    }
    report["api_key_configured"] = asr_key
    if not asr_key:
        report["warn"].append(
            "转写弱可用：VOLC_BIGMODEL_API_KEY 未配置（火山控制台 > API Key 管理 "
            "https://console.volcengine.com/speech/new/setting/apikeys，"
            "设为环境变量或复制 .env.example 为 .env）；"
            "口播视频 L1 转写需要它，无口播分支 / 已有转写稿 / L2 画面档不受影响"
        )

    if ffmpeg_path:
        missing_core, missing_extra = _filter_report()
        if missing_core:
            report["warn"].append(f"missing core filters: {', '.join(missing_core)}")
        if missing_extra:
            report["warn"].append(f"missing optional filters: {', '.join(missing_extra)}")

    # yt-dlp is only needed for URL input (fetch.py); local-file analysis works without it
    ytdlp_version = None
    for candidate in ("yt-dlp", "uvx"):
        if shutil.which(candidate):
            try:
                proc = subprocess.run(
                    [candidate, "yt-dlp", "--version"] if candidate == "uvx" else ["yt-dlp", "--version"],
                    capture_output=True, timeout=120,
                )
                ytdlp_version = proc.stdout.decode("utf-8", "replace").strip() or None
            except Exception:
                ytdlp_version = None
        if ytdlp_version:
            break
    report["ytdlp"] = ytdlp_version
    if not ytdlp_version:
        report["warn"].append("yt-dlp not found: URL 输入(fetch.py)不可用；本地文件分析不受影响")

    ocr = _ocr_fallback_report()
    report["ocr_fallback"] = ocr
    if not ocr["api_token"] and not ocr["paddleocr_local"]:
        report["warn"].append(
            "OCR 回退弱可用：设置 PADDLEOCR_ACCESS_TOKEN（星河社区访问令牌页免费获取，"
            "接官方托管 API）或本地安装 paddleocr 后，无读图能力的 agent 才能对无口播视频提取画面文案；"
            "多模态 agent 不受影响"
        )

    try:
        workdir_path = Path(workdir).expanduser()
        workdir_path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(workdir_path.resolve())
        free_gb = round(usage.free / 1024**3, 1)
        report["disk_free_gb"] = free_gb
        if free_gb < 2:
            report["warn"].append(f"low disk space on {workdir}: {free_gb} GB free")
    except Exception as exc:
        report["warn"].append(f"disk check failed: {exc}")

    report["ok"] = not report["missing"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workdir", default=".",
        help="Directory where outputs will be written (for the disk check).",
    )
    args = parser.parse_args(argv)
    report = check(args.workdir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
