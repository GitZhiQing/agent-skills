# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown-it-py>=3.0"]
# ///
"""find-my-xp 可选 HTML 渲染器：XP 报告 Markdown → 单文件离线私密档案风 HTML。

预设模板（assets/report.template.html）+ 占位符替换，模型每次只跑一条命令：
    uv run "<skill_dir>/scripts/render_report.py" <XP-元地图.md> [XP-原型-A.md ...] [-o out.html]

单份输入渲染单份；多份输入合成一份档案（左侧文件→节导航）。
不联网、不启动浏览器、不重写 HTML；渲染后过程序化质量门。
退出码：0 成功 / 1 渲染或质量门失败 / 2 用法错误。stdout 单行 JSON，诊断走 stderr。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "report.template.html"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
DOSSIER_TITLE = "XP 画像档案"


def die(msg: str, code: int = 1) -> None:
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    print(f"render_report: {msg}", file=sys.stderr)
    sys.exit(code)


def slugify(text: str, seen: dict[str, int]) -> str:
    """GitHub 风格锚点：保留中文/字母/数字，空格转连字符，重名追加序号。"""
    s = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", text.lower().strip())
    s = re.sub(r"\s+", "-", s).strip("-") or "sec"
    seen[s] = seen.get(s, 0) + 1
    return s if seen[s] == 1 else f"{s}-{seen[s]}"


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def parse_markdown(text: str, prefix: str = ""):
    """渲染正文，提取 h1 标题与 h2/h3 目录；h1 移出正文（页头/分节标题单独展示）。"""
    from markdown_it import MarkdownIt

    text = strip_frontmatter(text)
    md = MarkdownIt("gfm-like", {"html": False, "linkify": False})
    toc: list[dict] = []
    seen: dict[str, int] = {}

    title = None
    m = re.search(r"(?m)^#[ \t]+(.+?)[ \t]*$", text)
    if m:
        title = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]

    def heading_open(tokens, idx, options, env):
        tag = tokens[idx].tag
        inline = tokens[idx + 1]
        content = inline.content if inline.type == "inline" else ""
        if tag in ("h2", "h3"):
            anchor = prefix + slugify(content, seen)
            toc.append({"level": tag, "id": anchor, "text": content})
            return f'<{tag} id="{anchor}">'
        return f"<{tag}>"

    def fence(tokens, idx, options, env):
        tok = tokens[idx]
        info = (tok.info or "").strip()
        lang = info.split()[0] if info else ""
        cls = f' class="language-{html.escape(lang)}"' if lang else ""
        return f"<pre><code{cls}>{html.escape(tok.content)}</code></pre>\n"

    md.renderer.rules["heading_open"] = heading_open
    md.renderer.rules["fence"] = fence
    body = md.render(text)
    return body, toc, title


def add_confidence_badges(body: str) -> str:
    """（置信：高/中/低）渲染为分级徽章。"""
    def sub(m):
        level = m.group(1)
        cls = {"高": "conf-high", "中": "conf-mid", "低": "conf-low"}[level]
        return f'<span class="conf {cls}">置信：{level}</span>'
    return re.sub(r"[（(]置信：(高|中|低)[）)]", sub, body)


def add_source_badges(body: str) -> str:
    """（语料：作品·角色·条目）渲染为来源标签；支持条目内一层嵌套括号。"""
    def sub(m):
        return f'<span class="src-tag">语料：{html.escape(m.group(1).strip())}</span>'
    return re.sub(r"[（(]语料：((?:[^（）()]|[（(][^（）()]*[）)])+)[）)]", sub, body)


class BalanceChecker(HTMLParser):
    """标签闭合检查（void 标签除外）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"多余闭合标签 </{tag}>")
        elif self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"未闭合标签 <{self.stack.pop()}>")
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"不匹配的闭合标签 </{tag}>")


def quality_gate(html_text: str, body: str) -> list[str]:
    """程序化质量门：占位符 / 外部资源 / 残留 markdown / 标签闭合。"""
    problems: list[str] = []
    if re.search(r"__[A-Z_]+__", html_text):
        problems.append("模板占位符残留")
    if re.search(r'<link[^>]+href=["\']https?://|<script[^>]+src=|@import\s+url|url\(\s*["\']?https?://', html_text):
        problems.append("含外部资源引用（违反单文件离线约束）")
    stripped = re.sub(r"<pre\b.*?</pre>|<code\b.*?</code>", "", body, flags=re.S)
    if re.search(r"(?m)^#{1,6}\s|\*\*[^*]+\*\*", stripped):
        problems.append("疑似未渲染的 markdown 标记")
    checker = BalanceChecker()
    checker.feed(html_text)
    checker.close()
    if checker.stack:
        problems.append(f"未闭合标签：{checker.stack}")
    problems.extend(checker.errors)
    return problems


def build_nav(files: list[dict]) -> str:
    """单份：h2/h3 目录；多份：文件 → 节两级导航。"""
    items: list[str] = []
    multi = len(files) > 1
    for f in files:
        if multi:
            items.append(f'<li class="nav-file"><a href="#{f["id"]}">{html.escape(f["title"])}</a>')
            if f["toc"]:
                items.append('<ul>')
        for entry in f["toc"]:
            cls = "toc-h3" if entry["level"] == "h3" else "toc-h2"
            items.append(f'<li class="{cls}"><a href="#{entry["id"]}">{html.escape(entry["text"])}</a></li>')
        if multi:
            if f["toc"]:
                items.append('</ul>')
            items.append('</li>')
    return "\n".join(items)


def render(inputs: list[Path], out_path: Path, check_only: bool = False) -> dict:
    if not TEMPLATE.is_file():
        die(f"模板缺失：{TEMPLATE}", 1)
    for p in inputs:
        if not p.is_file():
            die(f"输入文件不存在：{p}", 2)

    files: list[dict] = []
    bodies: list[str] = []
    multi = len(inputs) > 1
    for i, p in enumerate(inputs):
        prefix = f"p{i}-" if multi else ""
        body, toc, h1 = parse_markdown(p.read_text(encoding="utf-8"), prefix)
        title = h1 or p.stem
        body = add_confidence_badges(body)
        body = add_source_badges(body)
        fid = f"profile-{i}" if multi else "top"
        files.append({"id": fid, "title": title, "toc": toc})
        if multi:
            bodies.append(f'<section class="profile" id="{fid}"><h1 class="profile-title">{html.escape(title)}</h1>{body}</section>')
        else:
            bodies.append(body)

    page_title = DOSSIER_TITLE if multi else files[0]["title"]
    content = "\n".join(bodies)
    template = TEMPLATE.read_text(encoding="utf-8")
    html_text = (
        template.replace("__TITLE__", html.escape(page_title))
        .replace("__NAV_ITEMS__", build_nav(files))
        .replace("__CONTENT__", content)
    )
    problems = quality_gate(html_text, content)
    if problems:
        die("质量门未通过：" + "；".join(problems), 1)
    if not check_only:
        out_path.write_text(html_text, encoding="utf-8")
    return {
        "ok": True,
        "html": str(out_path.resolve()),
        "title": page_title,
        "files": len(inputs),
        "toc_entries": sum(len(f["toc"]) for f in files),
        "check_only": check_only,
        "bytes": len(html_text.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="find-my-xp XP 报告 Markdown → 单文件离线私密档案风 HTML（预设模板渲染，不联网、不启动浏览器）。",
        epilog="退出码：0 成功 / 1 渲染或质量门失败 / 2 用法错误。stdout 单行 JSON，诊断走 stderr。",
    )
    parser.add_argument("inputs", nargs="+", help="XP 报告 Markdown 路径（多份合成一份档案）")
    parser.add_argument("-o", "--output", help="输出 HTML 路径（单份默认同名 .html；多份默认首文件目录下 XP-档案.html）")
    parser.add_argument("--check-only", action="store_true", help="只渲染并跑质量门，不落盘")
    parser.add_argument("--json", action="store_true", help="兼容标记：stdout 始终为单行 JSON")
    args = parser.parse_args()

    inputs = [Path(p).expanduser().resolve() for p in args.inputs]
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    elif len(inputs) == 1:
        out_path = inputs[0].with_suffix(".html")
    else:
        out_path = inputs[0].parent / "XP-档案.html"
    result = render(inputs, out_path, args.check_only)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())