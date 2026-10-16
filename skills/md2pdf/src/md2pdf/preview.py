"""预览选择流：全主题 × 双行样本 → 横排拼接 PNG。

上行 = 标准元素样张（主题差异可见性），下行 = 文档真实内容摘要（所见即所得）。
"""
from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image

from .builder import available_themes, build_html
from .convert_md import parse
from .printer import print_pdf

SPEC_MD = """# 标准样张

段落正文：**粗体强调**与「全角标点」混排，数字 1234567890 对齐，语义色 <span class="pos">+5.2% 上涨</span> 与 <span class="neg">−3.1% 下跌</span>。

| 指标 | 权重 | 变动 |
| --- | --- | --- |
| 权益 | 38% | +4 pct |
| 利率债 | 27% | +3 pct |
| 黄金 | 17% | +1 pct |

```python
def solve(x: float) -> float:
    \"\"\"代码高亮：关键字用主题色。\"\"\"
    return x * 1.5 + 0.25
```

$$S = \\dfrac{E[R_p] - R_f}{\\sigma_p}$$
"""


def _doc_digest(md_text: str, limit: int = 1400) -> str:
    """截文档摘要到段落边界，供预览下半行。"""
    text = md_text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("\n\n## ", "\n\n# ", "\n\n"):
        pos = cut.rfind(sep)
        if pos > limit // 2:
            return cut[:pos]
    return cut


def make_preview(md_text: str, out_png: Path, *, base_dir: Path | None = None, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    digest = _doc_digest(md_text)
    previews: list[tuple[str, Path]] = []
    for theme in available_themes():
        spec_parsed = parse(SPEC_MD)
        doc_parsed = parse(digest, base_dir=base_dir)
        # 两段文档拼接渲染：样张在上、文档摘要在下（各自独立 h1 章节）
        merged = parse(
            SPEC_MD + "\n\n---\n\n" + digest + "\n\n*(以上下半部分为本文档内容节选)*\n",
            base_dir=base_dir,
        )
        html = build_html(
            merged,
            theme=theme,
            layout="article",
            title="主题预览",
            kicker="THEME PREVIEW",
            meta=theme,
            out_path=workdir / f"preview-{theme}.html",
        )
        pdf = workdir / f"preview-{theme}.pdf"
        print_pdf(html, pdf)
        previews.append((theme, pdf))

    # 取每个主题 PDF 的第 1 页 → 横排拼接
    images: list[Image.Image] = []
    theme_names: list[str] = []
    for theme, pdf in previews:
        doc = pymupdf.open(pdf)
        pix = doc[0].get_pixmap(dpi=96)
        img_path = workdir / f"preview-{theme}.png"
        pix.save(img_path)
        images.append(Image.open(img_path))
        theme_names.append(theme)
        doc.close()

    h = max(im.height for im in images)
    total_w = sum(im.width for im in images) + 8 * (len(images) - 1)
    board = Image.new("RGB", (total_w, h), "#faf9f5")
    x = 0
    for im in images:
        board.paste(im, (x, 0))
        x += im.width + 8
    board.save(out_png)
    print(f"[preview] {out_png}  主题顺序（左→右）：{' | '.join(theme_names)}")
    return out_png
