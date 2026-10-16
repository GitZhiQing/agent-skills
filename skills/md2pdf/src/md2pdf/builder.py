"""组装自包含打印 HTML：md 解析结果 + base.css + 主题 + 字体/KaTeX/Paged.js 全内联。

资源路径一律改写为绝对 file:// URI（HTML 可落盘在任意任务目录）。
"""
from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from .convert_md import ParsedDoc

SKILL_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = SKILL_ROOT / "templates"
THEMES = SKILL_ROOT / "themes"
ASSETS = SKILL_ROOT / "assets"

_env = Environment(undefined=StrictUndefined, autoescape=False)


def _rewrite_urls(css: str, base: Path) -> str:
    """css 内 url(files/..|fonts/..) → 绝对 file:// URI。"""
    def repl(m: re.Match) -> str:
        return f"url({(base / m.group(1)).resolve().as_uri()})"
    return re.sub(r"url\((files/[^)]+|fonts/[^)]+)\)", repl, css)


def available_themes() -> list[str]:
    return sorted(p.stem for p in THEMES.glob("*.css"))


def build_html(
    parsed: ParsedDoc,
    *,
    theme: str,
    layout: str,  # report | article
    title: str,
    subtitle: str = "",
    kicker: str = "DOCUMENT",
    meta: str = "",
    org: str = "",
    abstract: str = "",
    brand_zh: str = "文档",
    brand_en: str = "DOCUMENT",
    header_label: str = "",
    out_path: Path,
) -> Path:
    theme_file = THEMES / f"{theme}.css"
    if not theme_file.exists():
        raise SystemExit(f"未知主题 {theme!r}，可用：{available_themes()}")

    base_css = (TEMPLATES / "base.css").read_text(encoding="utf-8")
    base_css = base_css.replace("__HEADER_LABEL__", header_label or title)
    theme_vars = theme_file.read_text(encoding="utf-8")
    font_css = (
        _rewrite_urls((ASSETS / "fonts/noto-serif-sc.css").read_text(encoding="utf-8"), ASSETS / "fonts")
        + "\n"
        + _rewrite_urls((ASSETS / "fonts/noto-sans-sc.css").read_text(encoding="utf-8"), ASSETS / "fonts")
    )
    katex_dir = ASSETS / "katex"
    katex_css = _rewrite_urls((katex_dir / "katex.min.css").read_text(encoding="utf-8"), katex_dir)

    tpl = _env.from_string((TEMPLATES / "doc.html.j2").read_text(encoding="utf-8"))
    cover_title = title.replace("，", "，\n") if len(title) > 18 else title
    html = tpl.render(
        base_css=base_css,
        theme_vars=theme_vars,
        font_css=font_css,
        katex_css=katex_css,
        katex_js=(katex_dir / "katex.min.js").read_text(encoding="utf-8"),
        katex_auto=(katex_dir / "auto-render.min.js").read_text(encoding="utf-8"),
        paged_js=(ASSETS / "paged.polyfill.js").read_text(encoding="utf-8"),
        theme=theme,
        layout=layout,
        title=title,
        subtitle=subtitle,
        kicker=kicker,
        meta=meta,
        org=org,
        abstract=abstract,
        brand_zh=brand_zh,
        brand_en=brand_en,
        cover_title=cover_title,
        header_label=header_label,
        chapters=parsed.chapters,
        body_html=parsed.body_html,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
