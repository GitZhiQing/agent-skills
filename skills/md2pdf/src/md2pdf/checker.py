"""md2pdf 程序化质量门：打印后自动断言，失败即 fail，不进视觉验收。

用法：uv run --with pymupdf python check.py <a.pdf> [b.pdf ...]

断言（FAIL，退出码 1）：
  F1 无空白页（整页无文本块）
  F2 页尾无孤悬标题/编号（末内容块短且无句末标点，排除页码）
  F3 字体集：含 Noto、无 Type3、无未预期系统中文字体
  F4 目录页码与章节实际首现页一致
警告（WARN，不致败）：
  W1 段末行孤字（< 4 字符的 CJK 末行）
"""
from __future__ import annotations

import re
import sys

import pymupdf

# 设计内允许的字体（除 Noto 外均为 Latin/mono/楷体引用，系统 CJK 字体出现即视为回退）
FONT_ALLOW = re.compile(
    r"^(Noto.*|Georgia.*|SegoeUI.*|Consolas.*|TimesNewRoman.*|CambriaMath.*|KaTeX_.*|KaiTi.*)$"
)
FONT_CJK_BAD = re.compile(r"SimSun|MicrosoftYaHei|SimHei|DengXian|KaiTi_GB2312|FangSong", re.I)
PAGE_NO = re.compile(r"^—\s*\d+\s*—$")
DATE_LINE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$")
SENT_END = "。；：！？）】”』》…."
TOC_LINE = re.compile(r"^(\d{2})\s+(.+?)\s+(\d+)$")


def page_blocks(page: pymupdf.Page):
    blocks = [b for b in page.get_text("blocks") if b[4].strip()]
    blocks.sort(key=lambda b: b[1])
    return blocks


def check_pdf(path: str) -> tuple[list[str], list[str]]:
    fails: list[str] = []
    warns: list[str] = []
    doc = pymupdf.open(path)
    fonts: set[str] = set()
    type3 = 0

    # ---- F1 空白页 & F2 页尾孤悬 & W1 孤字 ----
    for i, page in enumerate(doc):
        fonts.update(x[3] for x in page.get_fonts())
        type3 += sum(1 for x in page.get_fonts() if x[2] == "Type3")
        raw_text = page.get_text()
        has_page_no = bool(PAGE_NO.search(raw_text))
        blocks = [b for b in page_blocks(page) if not PAGE_NO.match(b[4].strip())]
        if not blocks:
            fails.append(f"F1 p{i+1}: 空白页")
            continue
        # 封面/题头页（无页码的第一页）的页尾 meta 行属合法设计，跳过 F2
        if has_page_no:
            tail = blocks[-1][4].strip().replace("\n", " ")
            is_date = DATE_LINE.search(tail)
            is_src = tail.startswith("——") or tail.startswith("--")
            # 孤悬标题仅指标题级字号（≥11pt），排除表格行/小字注记
            sizes = [s["size"] for b2 in page.get_text("dict")["blocks"] if b2 == blocks[-1]
                     for l in b2.get("lines", []) for s in l["spans"]]
            tail_size = max(sizes) if sizes else 0
            if (not is_date and not is_src and tail_size >= 11
                    and len(tail) < 30 and tail[-1:] not in SENT_END
                    and not re.search(r"[\d%）)]$", tail)):
                fails.append(f"F2 p{i+1}: 页尾疑似孤悬标题/编号 {tail!r}")
        # W1：多行块的末行孤字（单行块为独立短句/标题，不算）
        for b in blocks:
            lines = [l for l in b[4].split("\n") if l.strip()]
            if len(lines) >= 2 and len(lines[-2].strip()) > 10:
                last = lines[-1].strip()
                cjk = sum(1 for c in last if "\u4e00" <= c <= "\u9fff")
                if 0 < len(last) < 4 and cjk:
                    warns.append(f"W1 p{i+1}: 段末孤字 {last!r}")

    # ---- F3 字体集 ----
    noto = [f for f in fonts if f and "Noto" in f]
    if not noto:
        fails.append("F3 未检测到 Noto 字体（嵌入缺失）")
    if type3:
        fails.append(f"F3 Type3 字形 {type3} 处（可变字体/渲染回退）")
    for f in sorted(fonts):
        name = (f or "").split("+")[-1]
        if name and not FONT_ALLOW.match(name):
            fails.append(f"F3 未预期字体: {name!r}")
        elif name and FONT_CJK_BAD.search(name):
            fails.append(f"F3 系统中文字体回退: {name!r}")

    # ---- F4 目录页码 ----
    toc_entries: list[tuple[str, int]] = []
    for i, page in enumerate(doc[:4]):
        for raw in page.get_text().split("\n"):
            m = TOC_LINE.match(raw.strip())
            if m:
                toc_entries.append((m.group(2), int(m.group(3)), i + 1))
    if toc_entries:
        toc_page = toc_entries[0][2]
        for title, claimed, _ in toc_entries:
            hits = [
                j + 1
                for j in range(toc_page, len(doc))
                for b in page_blocks(doc[j])
                if title in b[4].replace("\n", "") and len(b[4].strip()) < 60
            ]
            first = hits[0] if hits else None
            if first != claimed:
                fails.append(f"F4 目录「{title}」标注 {claimed} 页，实际首现 {first} 页")

    for w in warns:
        print(f"  WARN {w}")
    for f in fails:
        print(f"  FAIL {f}")
    print(f"[{'PASS' if not fails else 'FAIL'}] {path} ({len(doc)}p, fonts={len(fonts)})")
    return fails, warns


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    all_fails = 0
    for p in sys.argv[1:]:
        fails, _ = check_pdf(p)
        all_fails += len(fails)
    return 1 if all_fails else 0


if __name__ == "__main__":
    sys.exit(main())
