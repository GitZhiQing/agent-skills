"""Markdown → HTML body：markdown-it-py 标准渲染 + 两步后处理。

约定（与 base.css 配合）：
- h1 → 章节结构：<div class="keep-head"><h1 class="chapter" id="chN">
  <span class="ch-no">0N</span>标题</h1> + 首个后续块 + </div>（章首孤悬保护，DECISIONS D3）
- ul → ul.points、ol → ol.num；代码块 → Pygments class（.k/.s 由 base.css 映射主题色）
- 图片相对路径改写为绝对 file:// URI（相对 md 源目录解析）
- 公式 $..$ / $$..$$ 原样保留，由页面端 KaTeX auto-render 渲染（打印前等待）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from markdown_it import MarkdownIt
from pygments import highlight as _pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
H1_RE = re.compile(r"<h1>(.*?)</h1>", re.S)
H2_RE = re.compile(r"<h2>(.*?)</h2>", re.S)
BLOCK_AFTER_H1 = re.compile(
    r'(<div class="keep-head">.*?</h1>)\s*(<(?:p|h2|blockquote|table|pre|ul|ol)\b.*?</(?:p|h2|blockquote|table|pre|ul|ol)>)',
    re.S,
)
# 自带编号的标题（一、/（一）/1./1.1 等）不叠加自动章号
SELF_NUMBERED = re.compile(r"^[（(]?[一二三四五六七八九十\d]+[）)、.．]\s*")


@dataclass
class ParsedDoc:
    front: dict = field(default_factory=dict)
    body_html: str = ""
    chapters: list[dict] = field(default_factory=list)  # [{no, title, id}]
    doc_h1: str = ""  # 全文唯一 h1 → 文档标题（不进正文）


def _code_block(code: str, lang: str, lang_attrs: str = "") -> str:
    try:
        lexer = get_lexer_by_name(lang, stripall=True) if lang else get_lexer_by_name("text", stripall=True)
    except ClassNotFound:
        lexer = None
    if lexer is None:
        return f'<pre class="code"><code>{code}</code></pre>'
    return f'<pre class="code"><code class="hl">{_pyg_highlight(code, lexer, HtmlFormatter(nowrap=True))}</code></pre>'


def parse(md_text: str, base_dir: Path | None = None) -> ParsedDoc:
    doc = ParsedDoc()
    text = md_text

    m = FM_RE.match(text)
    if m:
        try:
            doc.front = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            doc.front = {}
        text = text[m.end():]

    md = MarkdownIt("gfm-like", {"html": True, "linkify": True, "highlight": _code_block})
    default_image = md.renderer.rules.get("image")
    default_bullet = md.renderer.rules.get("bullet_list_open")
    default_ordered = md.renderer.rules.get("ordered_list_open")

    def render_image(self_r, tokens, idx, options, env):
        if default_image and base_dir:
            src = tokens[idx].attrGet("src") or ""
            if src and not re.match(r"^[a-z][a-z0-9+.-]*://|^data:", src):
                tokens[idx].attrSet("src", (base_dir / src).resolve().as_uri())
        if default_image:
            return default_image(tokens, idx, options, env)
        return md.renderer.renderToken(tokens, idx, options, env)

    def bullet_open(self_r, tokens, idx, options, env):
        tokens[idx].attrJoin("class", "points")
        if default_bullet:
            return default_bullet(tokens, idx, options, env)
        return md.renderer.renderToken(tokens, idx, options, env)

    def ordered_open(self_r, tokens, idx, options, env):
        tokens[idx].attrJoin("class", "num")
        if default_ordered:
            return default_ordered(tokens, idx, options, env)
        return md.renderer.renderToken(tokens, idx, options, env)

    md.add_render_rule("image", render_image)
    md.add_render_rule("bullet_list_open", bullet_open)
    md.add_render_rule("ordered_list_open", ordered_open)

    body = md.render(text)

    # 标题层级归一：全文唯一 h1 → 文档标题（从正文移除，h2 升格为章节层）
    h1s = list(H1_RE.finditer(body))
    chapter_tag = "h1"
    if len(h1s) == 1:
        m = h1s[0]
        doc.doc_h1 = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        body = body[: m.start()] + body[m.end():]
        chapter_tag = "h2"
        heading_re = H2_RE
    else:
        heading_re = H1_RE

    # 章节收集与改写（自带编号的标题不加自动章号）
    for i, m in enumerate(heading_re.finditer(body), 1):
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        no = "" if SELF_NUMBERED.match(m.group(1).lstrip()) else f"{i:02d}"
        doc.chapters.append({"no": no, "title": title, "id": f"ch{i}"})

    counter = [0]

    def chapter_repl(m: re.Match) -> str:
        counter[0] += 1
        i = counter[0]
        no = "" if SELF_NUMBERED.match(m.group(1).lstrip()) else f'<span class="ch-no">{i:02d}</span>'
        return (
            f'<div class="keep-head"><h1 class="chapter" id="ch{i}">'
            f"{no}{m.group(1)}</h1>"
        )

    body = heading_re.sub(chapter_repl, body)
    # h2 升格场景：更深层级整体上移一级（h3→h2、h4→h3），保持层级连续
    if chapter_tag == "h2":
        body = body.replace("<h3>", "<h2>").replace("</h3>", "</h2>")
        body = body.replace("<h4>", "<h3>").replace("</h4>", "</h3>")
    body = BLOCK_AFTER_H1.sub(r"\1\2</div>", body)
    body = re.sub(r'(</h1>)(?!</div>)(\s*)$', r"\1</div>\2", body)

    doc.body_html = body
    return doc
