"""find-my-xp 可选 HTML 渲染器测试。

运行：uv run --with markdown-it-py python -m unittest discover -s skills/find-my-xp/tests
markdown-it-py 缺失时真实渲染用例自动跳过（--help / 用法错误 / 质量门单元用例仍可跑）。
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "render_report.py"
PROTO = Path(__file__).resolve().parent / "fixtures" / "prototype-canary.md"
META = Path(__file__).resolve().parent / "fixtures" / "meta-canary.md"

spec = importlib.util.spec_from_file_location("render_report", SCRIPT)
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

try:
    import markdown_it  # noqa: F401
    HAS_MDIT = True
except ImportError:
    HAS_MDIT = False


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")


class TestCliContract(unittest.TestCase):
    """不依赖 markdown-it-py 的接口契约。"""

    def test_help(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("inputs", proc.stdout)
        self.assertIn("退出码", proc.stdout)

    def test_missing_input_exit2(self):
        proc = run_cli(str(SKILL_ROOT / "tests" / "no-such-file.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["ok"])


class TestUnits(unittest.TestCase):
    def test_slugify_chinese_and_dedupe(self):
        seen = {}
        self.assertEqual(rr.slugify("表面层 · 眼睛吃的", seen), "表面层-眼睛吃的")
        self.assertEqual(rr.slugify("表面层 · 眼睛吃的", seen), "表面层-眼睛吃的-2")
        self.assertEqual(rr.slugify("!!!", {}), "sec")

    def test_quality_gate_passes_clean_html(self):
        clean = "<html><body><p>ok</p></body></html>"
        self.assertEqual(rr.quality_gate(clean, "<p>ok</p>"), [])

    def test_quality_gate_catches_problems(self):
        bad = '<html><link href="https://cdn.example/x.css"><p>__TITLE__</p><div></html>'
        problems = rr.quality_gate(bad, "<p>**real**</p>")
        joined = "；".join(problems)
        self.assertIn("占位符", joined)
        self.assertIn("外部资源", joined)
        self.assertIn("未渲染", joined)
        self.assertIn("未闭合", joined)

    def test_balance_checker_void_tags(self):
        checker = rr.BalanceChecker()
        checker.feed("<p>a<br>b<img src='x'></p>")
        checker.close()
        self.assertEqual(checker.errors, [])
        self.assertEqual(checker.stack, [])

    def test_code_span_markdown_not_flagged(self):
        body = "<p><code>**x**</code></p><pre># y</pre>"
        html_text = f"<html><body>{body}</body></html>"
        self.assertEqual(rr.quality_gate(html_text, body), [])
        flagged = rr.quality_gate("<html><p>**real**</p></html>", "<p>**real**</p>")
        self.assertTrue(any("未渲染" in p for p in flagged))

    def test_confidence_badges(self):
        body = "<p>真实审美（置信：高）投射（置信：中）重复（置信：低）</p>"
        out = rr.add_confidence_badges(body)
        self.assertIn('class="conf conf-high"', out)
        self.assertIn('class="conf conf-mid"', out)
        self.assertIn('class="conf conf-low"', out)
        self.assertNotIn("（置信：", out)

    def test_source_badges(self):
        body = "<blockquote><p>两弯似蹙非蹙罥烟眉。</p><p>（语料：红楼梦·林黛玉·出场）</p></blockquote>"
        out = rr.add_source_badges(body)
        self.assertIn('class="src-tag"', out)
        self.assertIn("语料：红楼梦·林黛玉·出场", out)
        self.assertNotIn("（语料：", out)

    def test_source_badges_nested_parens(self):
        body = "<p>（语料：鸣潮·莉莉·角色外形（立绘注））</p>"
        out = rr.add_source_badges(body)
        self.assertIn('class="src-tag"', out)
        self.assertIn("角色外形（立绘注）", out)
        self.assertNotIn("（语料：", out)

    def test_strip_frontmatter(self):
        self.assertEqual(rr.strip_frontmatter("---\na: 1\n---\n# T\n"), "# T\n")
        self.assertEqual(rr.strip_frontmatter("# T\n"), "# T\n")


@unittest.skipUnless(HAS_MDIT, "markdown-it-py 未安装（用 uv run --with markdown-it-py 跑真实渲染用例）")
class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "XP.html"
        self.addCleanup(self.tmp.cleanup)

    def render(self, *inputs, extra=()):
        proc = run_cli(*[str(p) for p in inputs], "-o", str(self.out), *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout), self.out.read_text(encoding="utf-8")

    def test_single_canary_full(self):
        result, html_text = self.render(PROTO)
        self.assertTrue(result["ok"])
        self.assertEqual(result["title"], "XP 原型 · 高冷破例")
        self.assertEqual(result["files"], 1)
        self.assertGreaterEqual(result["toc_entries"], 6)
        # 单文件离线：无外部资源、无占位符残留
        self.assertNotRegex(html_text, r'<link[^>]+href="https?://|<script[^>]+src=')
        self.assertNotRegex(html_text, r"__[A-Z_]+__")
        # 私密档案风变量与打印样式
        self.assertIn("--brass:", html_text)
        self.assertIn("@media print", html_text)
        self.assertIn("@page", html_text)
        # 导航与移动端折叠
        self.assertIn('<nav id="toc"', html_text)
        self.assertIn('id="nav-toggle"', html_text)
        # 置信度徽章
        self.assertIn('conf-high', html_text)
        self.assertIn('conf-mid', html_text)
        self.assertIn('conf-low', html_text)
        # 语料来源徽章（sourced 描写）
        self.assertIn('src-tag', html_text)
        self.assertIn("语料：红楼梦·林黛玉·出场", html_text)
        # 原话卡片（blockquote）与表格
        self.assertIn("<blockquote>", html_text)
        self.assertIn("<table>", html_text)
        # XP 链箭头保留
        self.assertIn("→", html_text)
        # 单份：h1 只在页头一次，无分节标题
        self.assertNotIn('class="profile-title"', html_text)
        content = html_text.split("</header>", 1)[1].split("<footer>", 1)[0]
        self.assertNotIn("XP 原型 · 高冷破例", content)
        # 页脚免责声明
        footer = html_text.split("<footer>", 1)[1].split("</footer>", 1)[0]
        self.assertIn("假设地图", footer)

    def test_multi_dossier(self):
        result, html_text = self.render(META, PROTO)
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 2)
        self.assertEqual(result["title"], "XP 画像档案")
        # 两个分节 + 分节标题
        self.assertEqual(html_text.count('class="profile"'), 2)
        self.assertIn('class="profile-title"', html_text)
        self.assertIn("XP 元地图", html_text)
        self.assertIn("XP 原型 · 高冷破例", html_text)
        # 文件级导航
        self.assertIn('class="nav-file"', html_text)
        self.assertIn('href="#profile-0"', html_text)
        self.assertIn('href="#profile-1"', html_text)
        # 锚点带文件前缀避免冲突
        self.assertIn('id="p0-', html_text)
        self.assertIn('id="p1-', html_text)

    def test_check_only_no_write(self):
        proc = run_cli(str(PROTO), "-o", str(self.out), "--check-only")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["check_only"])
        self.assertFalse(self.out.exists())

    def test_default_output_same_dir(self):
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "XP-原型-A.md"
            copy.write_text(PROTO.read_text(encoding="utf-8"), encoding="utf-8")
            proc = run_cli(str(copy))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((Path(td) / "XP-原型-A.html").is_file())

    def test_multi_default_output_name(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "XP-元地图.md"
            b = Path(td) / "XP-原型-A.md"
            a.write_text(META.read_text(encoding="utf-8"), encoding="utf-8")
            b.write_text(PROTO.read_text(encoding="utf-8"), encoding="utf-8")
            proc = run_cli(str(a), str(b))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((Path(td) / "XP-档案.html").is_file())

    def test_empty_input_renders(self):
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty.md"
            empty.write_text("", encoding="utf-8")
            proc = run_cli(str(empty))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            res = json.loads(proc.stdout)
            self.assertEqual(res["title"], "empty")
            self.assertEqual(res["toc_entries"], 0)

    def test_no_h1_uses_stem(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "nohead.md"
            f.write_text("## 只有二级\n\n正文。\n", encoding="utf-8")
            proc = run_cli(str(f))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["title"], "nohead")


if __name__ == "__main__":
    unittest.main()