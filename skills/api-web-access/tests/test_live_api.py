"""Optional live API tests.

Run with TAVILY_API_KEY and/or EXA_API_KEY exported in the current process.
Tests skip automatically when a provider key is absent; a skip is not a pass.
Keys are never written to files, assertions, or failure messages by these tests.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
import sys

if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import api_web_access as awa  # noqa: E402


def run_main(func, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = func(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def _keys_absent_output() -> str:
    missing = [name for name in (awa.KEY_ENV["tavily"], awa.KEY_ENV["exa"]) if not os.environ.get(name)]
    return "live API keys not set: " + ", ".join(missing) if missing else ""


@unittest.skipUnless(os.environ.get(awa.KEY_ENV["tavily"]), _keys_absent_output())
class TavilyLiveTests(unittest.TestCase):
    def test_search_and_extract(self):
        key = os.environ[awa.KEY_ENV["tavily"]]
        with tempfile.TemporaryDirectory() as cache:
            search = run_main(awa.web_search_main, [
                "Python 3.13 release notes", "--provider", "tavily", "-m", "3",
                "--format", "json", "--cache-dir", cache,
            ])
            fetch = run_main(awa.web_fetch_main, [
                "https://example.com", "--provider", "tavily", "--cache-dir", cache,
            ])
        self.assertEqual(search[0], 0, search[2])
        results = json.loads(search[1])
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 3)
        for item in results:
            self.assertEqual(set(item), {"title", "href", "body"})
        self.assertEqual(fetch[0], 0, fetch[2])
        self.assertTrue(fetch[1].strip())
        for output in (search[1], search[2], fetch[1], fetch[2]):
            self.assertNotIn(key, output)


@unittest.skipUnless(os.environ.get(awa.KEY_ENV["exa"]), _keys_absent_output())
class ExaLiveTests(unittest.TestCase):
    def test_search_and_contents(self):
        key = os.environ[awa.KEY_ENV["exa"]]
        with tempfile.TemporaryDirectory() as cache:
            search = run_main(awa.web_search_main, [
                "Python 3.13 release notes", "--provider", "exa", "-m", "3",
                "--format", "json", "--cache-dir", cache,
            ])
            fetch = run_main(awa.web_fetch_main, [
                "https://example.com", "--provider", "exa", "--cache-dir", cache,
            ])
        self.assertEqual(search[0], 0, search[2])
        results = json.loads(search[1])
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 3)
        self.assertEqual(fetch[0], 0, fetch[2])
        self.assertTrue(fetch[1].strip())
        for output in (search[1], search[2], fetch[1], fetch[2]):
            self.assertNotIn(key, output)


@unittest.skipUnless(os.environ.get(awa.KEY_ENV["exa"]), _keys_absent_output())
class AutoFailoverLiveTests(unittest.TestCase):
    def test_invalid_tavily_key_falls_back_to_exa(self):
        exa_key = os.environ[awa.KEY_ENV["exa"]]
        env = {"TAVILY_API_KEY": "tvly-definitely-invalid", awa.KEY_ENV["exa"]: exa_key}
        with mock.patch.dict(os.environ, env), tempfile.TemporaryDirectory() as cache:
            code, stdout, stderr = run_main(awa.web_search_main, [
                "Python 3.13 release notes", "-m", "3", "--format", "json",
                "--cache-dir", cache,
            ])
        self.assertEqual(code, 0, stderr)
        self.assertIn("provider=tavily failed", stderr)
        self.assertIn("provider=exa", stderr)
        self.assertIsInstance(json.loads(stdout), list)
        self.assertNotIn("tvly-definitely-invalid", stdout + stderr)
        self.assertNotIn(exa_key, stdout + stderr)


if __name__ == "__main__":
    unittest.main()
