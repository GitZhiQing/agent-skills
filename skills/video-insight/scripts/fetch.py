#!/usr/bin/env python3
"""Fetch a video by URL into <output-dir>/video.mp4 (thin yt-dlp dispatcher).

Support policy: only platform paths that are both reliably documented and
verified usable are supported. Everything else fails fast with the reason and
manual-download guidance — there are no flaky fallbacks.

Support matrix (verified 2026-09-14 with yt-dlp 2026.08.19 on Windows):
  bilibili.com / b23.tv      supported    no cookies needed (1080P60 is premium-gated)
  douyin.com / v.douyin.com  unsupported  fresh-cookies error persists even with
                                          browser cookies (yt-dlp issues #9557/#12669/#16803)
  xiaohongshu.com            unsupported  extractor broken by the Rednote rebrand (#16519)
  kuaishou.com               unsupported  absent from yt-dlp's supported sites
  视频号                      unsupported  closed platform, only local-proxy tools

Re-adding a platform requires a reliable official document plus a passing
live test.

Usage:
    python fetch.py <url> [--output-dir DIR] [--ytdl-format "bv*+ba/b"]
        [--cookies-from-browser chrome|edge|firefox]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import fail_manifest, run, update_manifest  # noqa: E402

SUPPORTED_HOSTS = {
    "bilibili": ("bilibili.com", "b23.tv"),
}

DROPPED = {
    "douyin": (
        "yt-dlp 提取器实测不可用：无 cookies 与带浏览器 cookies 均报 fresh cookies 错"
        "（yt-dlp issues #9557/#12669/#16803）；专用工具文档与可持续性不达标，未采用"
    ),
    "xiaohongshu": (
        "yt-dlp 提取器因平台改名 Rednote 损坏（issue #16519）；专用工具仅 README 级文档，未验证"
    ),
    "kuaishou": "yt-dlp 官方支持清单无快手；专用工具文档不可靠，未验证",
    "channels": "微信视频号无链接解析方案（平台封闭，仅存在本地代理+注入类工具，需人工操作）",
}

DROPPED_HOSTS = {
    "douyin": ("douyin.com", "v.douyin.com", "iesdouyin.com"),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com", "rednote.com"),
    "kuaishou": ("kuaishou.com", "v.kuaishou.com", "chenzhongtech.com"),
    "channels": ("channels.weixin.qq.com",),
}


def classify(url: str) -> tuple[str, str]:
    """Return (platform, host); platform is a SUPPORTED/DROPPED key or 'unknown'."""
    host = (urlparse(url).netloc or url).lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    for platform, suffixes in {**SUPPORTED_HOSTS, **DROPPED_HOSTS}.items():
        if any(host == s or host.endswith("." + s) for s in suffixes):
            return platform, host
    return "unknown", host


def yt_dlp_cmd() -> list[str] | None:
    path = shutil.which("yt-dlp")
    if path:
        return [path]
    if shutil.which("uvx"):
        return ["uvx", "yt-dlp"]
    return None


def build_cmd(url: str, target: Path, ytdl_format: str,
              cookies_from_browser: str | None) -> list[str]:
    base = yt_dlp_cmd()
    cmd = base + [
        "-f", ytdl_format,
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-o", str(target),
    ]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    cmd.append(url)
    return cmd


def verify_playable(path: Path) -> float:
    proc = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)]
    )
    duration = float(proc.stdout.strip())
    if duration <= 0:
        raise RuntimeError(f"downloaded file has zero duration: {path}")
    return duration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--ytdl-format", default="bv*+ba/b",
                        help="yt-dlp format selector (default best video+audio)")
    parser.add_argument("--cookies-from-browser", default=None,
                        help="Forwarded to yt-dlp for premium/gated content")
    args = parser.parse_args(argv)

    platform, host = classify(args.url)
    if platform not in SUPPORTED_HOSTS:
        reason = DROPPED.get(platform, "未收录平台：无可靠文档的下载路径，不做猜测性支持")
        result = {
            "error": f"unsupported platform: {host}",
            "platform": platform,
            "reason": reason,
            "guidance": (
                "请手动下载视频（浏览器/平台客户端/本地工具），保存后用本地文件路径"
                "继续 video-insight 分析链路"
            ),
            "supported": list(SUPPORTED_HOSTS),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 2

    if yt_dlp_cmd() is None:
        print(json.dumps({"error": "yt-dlp not found (install yt-dlp or uvx)"}))
        return 1

    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else Path.cwd() / "video-insight" / "fetch"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "video.mp4"

    try:
        cmd = build_cmd(args.url, target, args.ytdl_format, args.cookies_from_browser)
        proc = run(cmd, check=False, timeout=1800)
        if proc.returncode != 0 or not target.exists():
            raise RuntimeError(f"yt-dlp failed:\n{proc.stderr[-2000:]}")
        duration = verify_playable(target)
        record = update_manifest(
            out_dir, "fetch", status="ok", outputs=[target],
            extra={"platform": platform, "url": args.url,
                   "duration_s": round(duration, 3)},
        )
        print(json.dumps({
            "platform": platform, "file": str(target),
            "bytes": target.stat().st_size,
            "duration_s": round(duration, 3),
            "status": record["status"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "fetch", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
