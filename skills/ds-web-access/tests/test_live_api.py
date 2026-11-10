"""Optional live DeepSeek API tests.

Run with DEEPSEEK_API_KEY exported in the current process. Tests skip when
the key is absent; a skip is not a pass. These tests intentionally spend at
most two successful requests: one search and one fetch.
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

import ds_web_access as dsw  # noqa: E402


def run_main(func, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = func(argv)
    return code, stdout.getvalue(), stderr.getvalue()


@unittest.skipUnless(os.environ.get(dsw.KEY_ENV), f"{dsw.KEY_ENV} is not set; live test skipped")
class DeepSeekLiveTests(unittest.TestCase):
    def test_search_and_fetch(self):
        key = os.environ[dsw.KEY_ENV]
        with tempfile.TemporaryDirectory() as cache:
            search = run_main(dsw.web_search_main, [
                "Python 3.13 release notes", "-n", "3", "--format", "json",
                "--cache-dir", cache, "--no-cache",
            ])
            fetch = run_main(dsw.web_fetch_main, [
                "https://example.com", "--cache-dir", cache, "--no-cache",
            ])
        self.assertEqual(search[0], 0, search[2])
        results = json.loads(search[1])
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 3)
        for item in results:
            self.assertIn("url", item)
            self.assertIn("title", item)
            self.assertIn("citation", item)
        self.assertEqual(fetch[0], 0, fetch[2])
        self.assertTrue(fetch[1].strip())
        for output in (search[1], search[2], fetch[1], fetch[2]):
            self.assertNotIn(key, output)


if __name__ == "__main__":
    unittest.main()
