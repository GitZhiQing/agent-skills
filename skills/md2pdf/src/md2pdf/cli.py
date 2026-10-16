"""md2pdf CLI：fetch / preview / convert / check。

工作流（Agent 优先，Human-in-the-loop）：
  1. md2pdf preview <source> -o task/preview.png   → 用户选主题
  2. md2pdf convert <source> --theme X --out task/  → 任务文件夹（source.md + config.yaml + pdf/双版式）
来源三态：本地路径 / 远程 md·txt·raw 直链 / 网页 URL（trafilatura 抽正文转 md）。
会话内容：Agent 先落盘为 md 再走本地路径。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
import urllib.request
from pathlib import Path

import yaml

from . import checker, fetch_assets
from .builder import available_themes, build_html
from .convert_md import parse
from .printer import print_pdf

UA = {"User-Agent": "Mozilla/5.0"}


def load_source(src: str) -> tuple[str, str, Path | None]:
    """返回 (md_text, 来源描述, base_dir)。base_dir 用于解析本地相对图片。"""
    if re.match(r"^https?://", src):
        req = urllib.request.Request(src, headers=UA)
        raw = urllib.request.urlopen(req, timeout=60).read()
        head = raw[:2048].lstrip().lower()
        if head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<html" in head:
            import trafilatura

            md = trafilatura.extract(raw.decode("utf-8", "ignore"), output_format="markdown")
            if not md:
                raise SystemExit(f"网页正文抽取失败：{src}\n请改为提供 md 直链，或把内容贴给 Agent 落盘。")
            return md, f"url-web: {src}", None
        return raw.decode("utf-8", "ignore"), f"url-text: {src}", None
    p = Path(src)
    if not p.exists():
        raise SystemExit(f"文件不存在：{p}")
    return p.read_text(encoding="utf-8"), f"local: {p}", p.parent


def doc_title(parsed, fallback: str) -> str:
    if parsed.front.get("title"):
        return str(parsed.front["title"])
    if parsed.doc_h1:
        return parsed.doc_h1
    if parsed.chapters:
        return parsed.chapters[0]["title"]
    return fallback


def cmd_fetch(args) -> int:
    return fetch_assets.main()


def cmd_check(args) -> int:
    total = 0
    for pdf in args.pdf:
        fails, _ = checker.check_pdf(pdf)
        total += len(fails)
    return 1 if total else 0


def cmd_preview(args) -> int:
    from .preview import make_preview

    md_text, src_desc, base_dir = load_source(args.source)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    make_preview(md_text, out, base_dir=base_dir, workdir=out.parent / "_preview_tmp")
    print(f"[hint] 把 {out} 展示给用户选择主题；可用主题：{available_themes()}")
    return 0


def cmd_convert(args) -> int:
    if args.theme not in available_themes():
        raise SystemExit(f"未知主题 {args.theme!r}，可用：{available_themes()}")
    md_text, src_desc, base_dir = load_source(args.source)
    stem = re.sub(r"[\\/:*?\"<>|\s]+", "-", Path(args.source).stem or "doc")[:40]
    stamp = _dt.datetime.now().strftime("%y%m%d-%H%M")
    task = Path(args.out or ".").resolve() / f"{stem}-{stamp}"
    task.mkdir(parents=True, exist_ok=True)
    (task / "source.md").write_text(md_text, encoding="utf-8")

    parsed = parse(md_text, base_dir=base_dir)
    title = doc_title(parsed, stem)
    subtitle = str(parsed.front.get("subtitle", ""))
    meta = str(parsed.front.get("date", "")) or _dt.date.today().isoformat()
    kicker = str(parsed.front.get("kicker", "DOCUMENT"))
    org = str(parsed.front.get("org", ""))
    abstract = str(parsed.front.get("abstract", ""))
    brand_zh = str(parsed.front.get("brand", org or "文档"))
    brand_en = str(parsed.front.get("brand-en", kicker or "DOCUMENT"))

    layouts = [args.layout] if args.layout != "both" else ["report", "article"]
    config = {
        "source": src_desc,
        "theme": args.theme,
        "layouts": layouts,
        "title": title,
        "subtitle": subtitle,
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "engine": "md2pdf 0.1.0 (playwright+paged.js)",
    }
    (task / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    pdf_dir = task / "pdf"
    failed = []
    for layout in layouts:
        html = build_html(
            parsed,
            theme=args.theme,
            layout=layout,
            title=title,
            subtitle=subtitle,
            kicker=kicker,
            meta=meta,
            org=org,
            abstract=abstract,
            brand_zh=brand_zh,
            brand_en=brand_en,
            header_label=title,
            out_path=task / f"build-{layout}.html",
        )
        suffix = "报告版" if layout == "report" else "正文版"
        pdf = pdf_dir / f"{stem}-{suffix}.pdf"
        pdf.parent.mkdir(exist_ok=True)
        print_pdf(html, pdf)
        fails, _ = checker.check_pdf(str(pdf))
        failed += fails
    if failed:
        print(f"\n[convert] 完成但有 {len(failed)} 项 check 未过：", file=sys.stderr)
        for f in failed:
            print("  " + f, file=sys.stderr)
        return 1
    print(f"[convert] 任务文件夹：{task}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="md2pdf", description="Markdown → 精美 PDF（双版式 × 多主题）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fetch", help="下载字体/Paged.js/KaTeX 运行时资源").set_defaults(func=cmd_fetch)

    p_prev = sub.add_parser("preview", help="各主题对比图（标准样张+文档摘要）")
    p_prev.add_argument("source", help="md/URL/网页")
    p_prev.add_argument("-o", "--out", default="preview.png")
    p_prev.set_defaults(func=cmd_preview)

    p_conv = sub.add_parser("convert", help="转换 → 任务文件夹（source.md + config.yaml + pdf/）")
    p_conv.add_argument("source", help="md/URL/网页")
    p_conv.add_argument("--theme", default="kimi", help="主题名（fetch themes 目录）")
    p_conv.add_argument("--layout", default="both", choices=["report", "article", "both"])
    p_conv.add_argument("--out", default=".", help="任务文件夹父目录")
    p_conv.set_defaults(func=cmd_convert)

    p_chk = sub.add_parser("check", help="对 PDF 跑质量门断言")
    p_chk.add_argument("pdf", nargs="+")
    p_chk.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
