# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown-it-py>=3.0"]
# ///
"""deep-research 可选 HTML 渲染器：REPORT.md → 单文件离线 REPORT.html。

预设模板（assets/report.template.html）+ 占位符替换，模型每次只跑一条命令：
    uv run "<skill_dir>/scripts/render_report.py" <REPORT.md> [--theme default|dark|sepia]

不联网调研、不启动浏览器、不重写 HTML；渲染后过程序化质量门。
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
THEMES = ("default", "dark", "sepia")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


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


def parse_markdown(text: str):
    """渲染正文，提取 h1 标题与 h2/h3 目录；不自动加章号（保护 §x.x 审计引用）。"""
    from markdown_it import MarkdownIt

    md = MarkdownIt("gfm-like", {"html": True, "linkify": False})
    toc: list[dict] = []
    seen: dict[str, int] = {}
    # 标题取首个 h1 并从正文移除（模板头部单独展示，避免重复）
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
            anchor = slugify(content, seen)
            toc.append({"level": tag, "id": anchor, "text": content})
            return f'<{tag} id="{anchor}">'
        return f"<{tag}>"

    md.renderer.rules["heading_open"] = heading_open
    body = md.render(text)
    return body, toc, title


def rewrite_citations(body: str) -> tuple[str, list[str]]:
    """上标引用改指来源表锚点（保留 S# 编号）；来源表行加锚点与回链。"""
    problems: list[str] = []
    first_cite: dict[str, str] = {}
    counter: dict[str, int] = {}

    def sup_sub(m):
        inner = m.group(1)

        def a_sub(am):
            title, sid = am.group(1), am.group(2)
            counter[sid] = counter.get(sid, 0) + 1
            aid = f"cite-{sid}-{counter[sid]}"
            first_cite.setdefault(sid, aid)
            title_attr = f' title="{title}"' if title else ""
            return f'<a class="cite" href="#src-{sid}" id="{aid}"{title_attr}>{sid}</a>'

        inner = re.sub(r'<a href="[^"]*"(?: title="([^"]*)")?[^>]*>(S\d+)</a>', a_sub, inner)
        return f"<sup>{inner}</sup>"

    body = re.sub(r"<sup>(.*?)</sup>", sup_sub, body, flags=re.S)

    seen_rows: set[str] = set()

    def row_sub(m):
        sid = m.group(1)
        if sid in seen_rows:
            problems.append(f"来源表锚点重复：{sid}（同一编号出现在多个表首列）")
        seen_rows.add(sid)
        back = first_cite.get(sid)
        link = f'<a class="backref" href="#{back}" title="回到正文首次引用">↩</a>' if back else ""
        return f'<tr id="src-{sid}"><td class="src-id">{sid}{link}</td>'

    body, n_rows = re.subn(r"<tr>\s*<td>(S\d+)</td>", row_sub, body)
    cited = set(counter)
    anchored = set(re.findall(r'<tr id="src-(S\d+)">', body))
    for sid in sorted(cited - anchored, key=lambda x: int(x[1:])):
        problems.append(f"引用 {sid} 在来源表中无对应行")
    return body, problems


def add_badges(body: str) -> str:
    """来源表类型列与置信标记渲染为徽章。"""
    badge_map = {
        "官方": "b-official", "官方仓库": "b-official", "官方（厂商博客）": "b-official",
        "官方（作者）": "b-official", "官方（频道）": "b-official",
        "官方一手（访谈转录）": "b-firsthand", "官方人员一手表态": "b-firsthand",
        "权威媒体": "b-media", "权威社区（专家）": "b-media", "权威社区（从业者）": "b-media",
        "社区观点": "b-community", "社区": "b-community",
        "社区观点（逆向）": "b-community", "社区观点（官方提示词存档）": "b-community",
        "社区镜像（官方人员表态）": "b-community", "社区二手": "b-community",
        "社区二手（转述）": "b-community",
    }

    def cell_sub(m):
        cell = m.group(1).strip()
        cls = badge_map.get(cell)
        if cls:
            return f'<td><span class="badge {cls}">{html.escape(cell)}</span></td>'
        return m.group(0)

    body = re.sub(r"<td>([^<]{2,24})</td>", cell_sub, body)
    body = re.sub(r"（单源）", '<span class="badge b-single">单源</span>', body)
    body = re.sub(r"（推断）", '<span class="badge b-infer">推断</span>', body)
    return body


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
    """程序化质量门：占位符 / 外部资源 / 引用解析 / 标签闭合 / 残留 markdown。"""
    problems: list[str] = []
    if re.search(r"__[A-Z_]+__", html_text):
        problems.append("模板占位符残留")
    if re.search(r'<link[^>]+href=["\']https?://|<script[^>]+src=|@import\s+url|url\(\s*["\']?https?://', html_text):
        problems.append("含外部资源引用（违反单文件离线约束）")
    stripped = re.sub(r"<pre\b.*?</pre>|<code\b.*?</code>", "", body, flags=re.S)
    if re.search(r"\[S\d+\]:", stripped):
        problems.append("链接定义行泄漏进正文")
    if re.search(r"(?m)^#{1,6}\s|\*\*[^*]+\*\*", stripped):
        problems.append("疑似未渲染的 markdown 标记")
    cited = set(re.findall(r'href="#src-(S\d+)"', body))
    anchored = set(re.findall(r'id="src-(S\d+)"', body))
    if cited - anchored:
        problems.append(f"上标引用无来源表锚点：{sorted(cited - anchored)}")
    unresolved = set()
    for sup in re.findall(r"<sup>(.*?)</sup>", body, re.S):
        unresolved.update(re.findall(r"\[(S\d+)\]", sup))
    if unresolved:
        problems.append(f"上标引用未解析（缺链接定义）：{sorted(unresolved, key=lambda x: int(x[1:]))}")
    checker = BalanceChecker()
    checker.feed(html_text)
    checker.close()
    if checker.stack:
        problems.append(f"未闭合标签：{checker.stack}")
    problems.extend(checker.errors)
    return problems


def build_toc(toc: list[dict]) -> str:
    if not toc:
        return ""
    items = []
    for entry in toc:
        cls = "toc-h3" if entry["level"] == "h3" else "toc-h2"
        items.append(f'<li class="{cls}"><a href="#{entry["id"]}">{html.escape(entry["text"])}</a></li>')
    return "\n".join(items)


def render(report_path: Path, out_path: Path, theme: str, check_only: bool = False) -> dict:
    if theme not in THEMES:
        die(f"未知主题 {theme}，可选：{', '.join(THEMES)}", 2)
    if not report_path.is_file():
        die(f"输入文件不存在：{report_path}", 2)
    if not TEMPLATE.is_file():
        die(f"模板缺失：{TEMPLATE}", 1)
    text = report_path.read_text(encoding="utf-8")
    if text.startswith("---"):  # 可选 frontmatter（笔记仓惯例）
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2].lstrip("\n")

    body, toc, h1 = parse_markdown(text)
    title = h1 or report_path.stem
    body, cite_problems = rewrite_citations(body)
    body = add_badges(body)

    template = TEMPLATE.read_text(encoding="utf-8")
    theme_attr = f' data-theme="{theme}"' if theme != "default" else ""
    html_text = (
        template.replace("__TITLE__", html.escape(title))
        .replace("__THEME_ATTR__", theme_attr)
        .replace("__TOC_ITEMS__", build_toc(toc))
        .replace("__CONTENT__", body)
    )
    problems = cite_problems + quality_gate(html_text, body)
    if problems:
        die("质量门未通过：" + "；".join(problems), 1)
    if not check_only:
        out_path.write_text(html_text, encoding="utf-8")
    return {
        "ok": True,
        "html": str(out_path.resolve()),
        "theme": theme,
        "title": title,
        "toc_entries": len(toc),
        "citations": len(set(re.findall(r'href="#src-(S\d+)"', body))),
        "check_only": check_only,
        "bytes": len(html_text.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="deep-research REPORT.md → 单文件离线 HTML（预设模板渲染，不联网、不启动浏览器）。",
        epilog="退出码：0 成功 / 1 渲染或质量门失败 / 2 用法错误。stdout 单行 JSON，诊断走 stderr。",
    )
    parser.add_argument("input", help="REPORT.md 路径")
    parser.add_argument("-o", "--output", help="输出 HTML 路径（默认与输入同目录同名 .html）")
    parser.add_argument("--theme", choices=THEMES, default="default",
                        help="主题：default 跟随系统明暗 / dark 强制暗色 / sepia 暖纸色（默认 default）")
    parser.add_argument("--check-only", action="store_true", help="只渲染并跑质量门，不落盘")
    parser.add_argument("--json", action="store_true", help="兼容标记：stdout 始终为单行 JSON")
    args = parser.parse_args()

    report_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve() if args.output else report_path.with_suffix(".html")
    result = render(report_path, out_path, args.theme, args.check_only)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
