"""轻量 CLI 单测：不渲染 PDF、不联网、不下载运行资源。

运行（仓库根或 skill 目录均可）：
  uv run --project <skill_dir> python -m unittest discover -s <skill_dir>/tests -v
无 uv 环境时也可设置 PYTHONPATH=<skill_dir>/src 后用系统 Python 运行。
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
SRC = SKILL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import md2pdf  # noqa: E402
from md2pdf import cli  # noqa: E402


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """运行 CLI 并捕获输出；argparse 的 --help 以 SystemExit(0) 结束。"""
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()


@contextlib.contextmanager
def mocked_convert(version: str | None = None):
    """替换来源读取、解析、构建、打印与质量门，隔离渲染与网络。"""
    patches = [
        mock.patch.object(
            cli, "load_source", return_value=("# Title\n\nBody\n", "local: doc.md", None)
        ),
        mock.patch.object(
            cli,
            "parse",
            return_value=SimpleNamespace(front={}, doc_h1="Title", chapters=[]),
        ),
        mock.patch.object(cli, "build_html", return_value=Path("build.html")),
        mock.patch.object(cli, "print_pdf"),
        mock.patch.object(cli.checker, "check_pdf", return_value=([], None)),
    ]
    if version is not None:
        patches.append(mock.patch.object(cli, "__version__", version))
    with contextlib.ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        yield


class HelpTests(unittest.TestCase):
    def test_top_level_help_parses(self):
        code, stdout, stderr = run_main(["--help"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("Markdown", stdout)
        for name in ("fetch", "preview", "convert", "check"):
            self.assertIn(name, stdout)

    def test_subcommands_exist(self):
        for name in ("fetch", "preview", "convert", "check"):
            with self.subTest(cmd=name):
                code, stdout, stderr = run_main([name, "--help"])
                self.assertEqual(code, 0, stderr)
                self.assertIn(name, stdout)


class ConvertTests(unittest.TestCase):
    def test_unknown_theme_rejected_before_reading_source(self):
        with tempfile.TemporaryDirectory(prefix="md2pdf-test-") as tmp:
            source = Path(tmp) / "doc.md"
            source.write_text("# Title\n", encoding="utf-8")
            with mock.patch.object(cli, "load_source") as load_source, mock.patch.object(
                cli, "build_html"
            ) as build_html, mock.patch.object(cli, "print_pdf") as print_pdf:
                with self.assertRaises(SystemExit) as raised:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                        io.StringIO()
                    ):
                        cli.main(
                            ["convert", str(source), "--theme", "nosuch", "--out", tmp]
                        )
            message = str(raised.exception)
            self.assertIn("未知主题", message)
            self.assertIn("kimi", message)
            load_source.assert_not_called()
            build_html.assert_not_called()
            print_pdf.assert_not_called()
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["doc.md"])

    def test_engine_field_uses_package_version(self):
        with tempfile.TemporaryDirectory(prefix="md2pdf-test-") as tmp:
            with mocked_convert():
                with contextlib.redirect_stdout(io.StringIO()):
                    code = cli.main(
                        ["convert", "doc.md", "--theme", "kimi", "--layout", "article", "--out", tmp]
                    )
            self.assertEqual(code, 0)
            task = next(Path(tmp).glob("doc-*"))
            config = (task / "config.yaml").read_text(encoding="utf-8")
            self.assertIn(
                f"engine: md2pdf {md2pdf.__version__} (playwright+paged.js)", config
            )

    def test_engine_field_reads_version_dynamically(self):
        with tempfile.TemporaryDirectory(prefix="md2pdf-test-") as tmp:
            with mocked_convert(version="9.9.9"):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = cli.main(
                        ["convert", "doc.md", "--theme", "kimi", "--layout", "article", "--out", tmp]
                    )
            self.assertEqual(code, 0)
            task = next(Path(tmp).glob("doc-*"))
            config = (task / "config.yaml").read_text(encoding="utf-8")
            self.assertIn("engine: md2pdf 9.9.9 (playwright+paged.js)", config)


if __name__ == "__main__":
    unittest.main()
