"""deep-research 可选 HTML 渲染器测试。

运行：uv run --with markdown-it-py python -m unittest discover -s skills/deep-research/tests
markdown-it-py 缺失时真实渲染用例自动跳过（--help / 用法错误 / 质量门单元用例仍可跑）。
"""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "render_report.py"
CANARY = Path(__file__).resolve().parent / "fixtures" / "report-canary.md"

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
        self.assertIn("--theme", proc.stdout)
        self.assertIn("退出码", proc.stdout)

    def test_missing_input_exit2(self):
        proc = run_cli(str(SKILL_ROOT / "tests" / "no-such-file.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["ok"])

    def test_bad_theme_exit2(self):
        proc = run_cli(str(CANARY), "--theme", "neon")
        self.assertEqual(proc.returncode, 2)


class TestUnits(unittest.TestCase):
    def test_slugify_chinese_and_dedupe(self):
        seen = {}
        self.assertEqual(rr.slugify("一、机制分析", seen), "一机制分析")
        self.assertEqual(rr.slugify("一、机制分析", seen), "一机制分析-2")
        self.assertEqual(rr.slugify("!!!", {}), "sec")

    def test_quality_gate_passes_clean_html(self):
        clean = "<html><body><p>ok</p></body></html>"
        self.assertEqual(rr.quality_gate(clean, "<p>ok</p>"), [])

    def test_quality_gate_catches_problems(self):
        bad = '<html><link href="https://cdn.example/x.css"><p>__TITLE__</p><div></html>'
        problems = rr.quality_gate(bad, "<p>[S1]: x</p>")
        joined = "；".join(problems)
        self.assertIn("占位符", joined)
        self.assertIn("外部资源", joined)
        self.assertIn("定义行泄漏", joined)
        self.assertIn("未闭合", joined)

    def test_balance_checker_void_tags(self):
        checker = rr.BalanceChecker()
        checker.feed("<p>a<br>b<img src='x'></p>")
        checker.close()
        self.assertEqual(checker.errors, [])
        self.assertEqual(checker.stack, [])


@unittest.skipUnless(HAS_MDIT, "markdown-it-py 未安装（用 uv run --with markdown-it-py 跑真实渲染用例）")
class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "REPORT.html"
        self.addCleanup(self.tmp.cleanup)

    def render_canary(self, *extra):
        proc = run_cli(str(CANARY), "-o", str(self.out), *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout), self.out.read_text(encoding="utf-8")

    def test_canary_full(self):
        result, html_text = self.render_canary()
        self.assertTrue(result["ok"])
        self.assertEqual(result["title"], "中文标题 · 机制对标调研报告")
        self.assertGreaterEqual(result["toc_entries"], 4)
        self.assertEqual(result["citations"], 3)
        # 单文件离线：无外部资源、无占位符残留
        self.assertNotRegex(html_text, r'<link[^>]+href="https?://|<script[^>]+src=')
        self.assertNotRegex(html_text, r"__[A-Z_]+__")
        # 主题变量与三套主题
        self.assertIn("--brand:", html_text)
        self.assertIn('data-theme="sepia"', html_text)
        # TOC 侧栏与移动端折叠
        self.assertIn('<nav id="toc"', html_text)
        self.assertIn('<details id="toc-mobile"', html_text)
        # 上标引用改指来源表锚点，编号保留
        self.assertIn('href="#src-S1"', html_text)
        self.assertIn('id="src-S1"', html_text)
        self.assertIn('class="cite"', html_text)
        # 来源表行锚点 + 回链
        self.assertIn('class="backref"', html_text)
        # 徽章：类型 + 置信标记
        self.assertIn('b-official', html_text)
        self.assertIn('b-community', html_text)
        self.assertIn('b-single', html_text)
        self.assertIn('b-infer', html_text)
        # 不自动加章号：原标题文本保留
        self.assertIn("一、机制分析", html_text)
        # h1 标题只在模板头部出现一次，不泄漏进正文
        content = html_text.split("</header>", 1)[1].split("<footer>", 1)[0]
        self.assertNotIn("中文标题", content)
        # 定义区不泄漏
        self.assertNotIn("[S1]:", html_text)
        # 打印样式
        self.assertIn("@media print", html_text)
        self.assertIn("@page", html_text)

    def test_theme_dark(self):
        _, html_text = self.render_canary("--theme", "dark")
        self.assertIn('<html lang="zh-CN" data-theme="dark">', html_text)

    def test_check_only_no_write(self):
        proc = run_cli(str(CANARY), "-o", str(self.out), "--check-only")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["check_only"])
        self.assertFalse(self.out.exists())

    def test_default_output_same_dir(self):
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "REPORT.md"
            copy.write_text(CANARY.read_text(encoding="utf-8"), encoding="utf-8")
            proc = run_cli(str(copy))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((Path(td) / "REPORT.html").is_file())

    def test_broken_citation_fails_gate(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "REPORT.md"
            text = CANARY.read_text(encoding="utf-8").replace("<sup>[S3]</sup>", "<sup>[S99]</sup>")
            bad.write_text(text, encoding="utf-8")
            proc = run_cli(str(bad), "-o", str(self.out))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("S99", proc.stderr)

    def test_meta_footer_optional(self):
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "REPORT.md"
            copy.write_text(CANARY.read_text(encoding="utf-8"), encoding="utf-8")
            (Path(td) / "META.md").write_text(
                "# META\n\n- **档位**：中\n- **日期**：2026-11-17\n", encoding="utf-8")
            proc = run_cli(str(copy))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            html_text = (Path(td) / "REPORT.html").read_text(encoding="utf-8")
            self.assertIn("档位：中", html_text)


if __name__ == "__main__":
    unittest.main()
