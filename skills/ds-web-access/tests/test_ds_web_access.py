import contextlib
import email.message
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import error as urlerror

SKILL_DIR = Path(__file__).resolve().parents[1]
import sys

if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import ds_web_access as dsw  # noqa: E402


def run_main(func, argv, env_file: Path | str | None = None):
    """Capture main() output while isolating .env and the default cache."""
    selected = Path(env_file) if env_file is not None else SKILL_DIR / "tests" / ".env.absent"
    stdout, stderr = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as cache, \
            mock.patch.dict(os.environ, {
                "DS_WEB_ACCESS_ENV_FILE": str(selected),
                "DS_WEB_ACCESS_CACHE": cache,
            }), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = func(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class ClassificationTests(unittest.TestCase):
    def test_search_status_matrix(self):
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 400), ("client", False))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 413), ("client", False))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 422), ("client", False))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 401), ("auth", False))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 402), ("balance", False))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 408), ("timeout", True))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 429), ("rate_limit", True))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 500), ("server", True))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 503), ("server", True))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 504), ("server", True))

    def test_fetch_specific_status_matrix(self):
        self.assertEqual(dsw._classify_status(dsw.FETCH_PATH, 403), ("security", False))
        self.assertEqual(dsw._classify_status(dsw.FETCH_PATH, 404), ("no_content", False))
        # Search 403/404 are not documented for Search; treat as unknown client errors.
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 403), ("client", False))
        self.assertEqual(dsw._classify_status(dsw.SEARCH_PATH, 404), ("client", False))

    def test_retry_policy_and_delay(self):
        rate = dsw.ApiError(dsw.SEARCH_PATH, "rate_limit", "slow down", 429, 3)
        auth = dsw.ApiError(dsw.SEARCH_PATH, "auth", "bad key", 401)
        balance = dsw.ApiError(dsw.SEARCH_PATH, "balance", "no funds", 402)
        security = dsw.ApiError(dsw.FETCH_PATH, "security", "blocked", 403)
        self.assertTrue(dsw._retry_allowed(rate))
        self.assertFalse(dsw._retry_allowed(auth))
        self.assertFalse(dsw._retry_allowed(balance))
        self.assertFalse(dsw._retry_allowed(security))
        self.assertEqual(dsw._retry_delay(rate), 3)
        self.assertEqual(dsw._retry_delay(dsw.ApiError(dsw.SEARCH_PATH, "server", "x", 500)), 2)
        capped = dsw.ApiError(dsw.SEARCH_PATH, "rate_limit", "slow", 429, 99)
        self.assertEqual(dsw._retry_delay(capped), 30)


class EnvAndRedactionTests(unittest.TestCase):
    def test_env_file_fills_missing_key_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "# comment\nexport DEEPSEEK_API_KEY='file-key'\nOTHER=x\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "process-key",
                                              "DS_WEB_ACCESS_ENV_FILE": str(env_file)}):
                dsw._load_env_file()
                self.assertEqual(dsw._api_key(), "process-key")
            with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "",
                                              "DS_WEB_ACCESS_ENV_FILE": str(env_file)}):
                dsw._load_env_file()
                self.assertEqual(dsw._api_key(), "file-key")
                self.assertIsNone(os.environ.get("OTHER"))

    def test_malformed_env_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("DEEPSEEK_API_KEY\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "",
                                              "DS_WEB_ACCESS_ENV_FILE": str(env_file)}):
                dsw._load_env_file()
                self.assertIsNone(dsw._api_key())

    def test_redacts_current_and_patterned_keys(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-secret-1234567890"}):
            text = "failed key=sk-test-secret-1234567890 pattern=sk-abcdef1234567890abcdef"
            redacted = dsw._redact_text(text)
        self.assertNotIn("sk-test-secret-1234567890", redacted)
        self.assertNotIn("sk-abcdef1234567890abcdef", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_missing_key_fails_without_request(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}), \
                mock.patch.object(dsw, "_request_json") as request:
            code, stdout, stderr = run_main(dsw.web_search_main, ["Python"])
        self.assertEqual(code, 1)
        request.assert_not_called()
        self.assertIn("MissingKeyError", stderr)
        self.assertIn("DEEPSEEK_API_KEY", stderr)
        self.assertEqual(stdout, "")


class SearchTests(unittest.TestCase):
    @staticmethod
    def response():
        return {"results": [{
            "rerank_score": 2.2,
            "title": "Python 3.13",
            "url": "https://example.com/python",
            "snippet": "short",
            "summary": "long summary",
            "content": "",
            "site_name": "Example",
            "site_icon": None,
            "date": "2026-01-01T00:00:00+00:00",
            "authority": 3,
        }]}

    def test_search_payload_and_success(self):
        response = self.response()
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response) as request:
            code, stdout, stderr = run_main(dsw.web_search_main, [
                "Python site:example.com lang:zh after:2026", "-n", "5",
                "--ori-question", "What is Python?", "--format", "json",
                "--cache-dir", cache,
            ])
        self.assertEqual(code, 0)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], dsw.SEARCH_PATH)
        payload = request.call_args.args[1]
        self.assertEqual(payload["query"], "Python site:example.com lang:zh after:2026")
        self.assertEqual(payload["count"], 5)
        self.assertFalse(payload["need_content"])
        self.assertEqual(payload["ori_question"], "What is Python?")
        self.assertNotIn("localization", payload)
        results = json.loads(stdout)
        self.assertEqual(results[0]["citation"], {
            "title": "Python 3.13",
            "url": "https://example.com/python",
            "site_name": "Example",
            "date": "2026-01-01T00:00:00+00:00",
        })
        self.assertIn("billing=inferred", stderr)

    def test_search_text_default_has_no_content(self):
        response = self.response()
        argv = ["Python", "-n", "3", "--format", "text"]
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response):
            code, stdout, stderr = run_main(dsw.web_search_main, argv)
        self.assertEqual(code, 0)
        self.assertIn("Python 3.13", stdout)
        self.assertIn("https://example.com/python", stdout)
        self.assertIn("authority=3", stdout)
        self.assertIn("long summary", stdout)
        self.assertNotIn("content:", stdout)

    def test_need_content_and_truncation(self):
        response = self.response()
        response["results"][0]["content"] = "x" * 500
        argv = ["Python", "--need-content", "--max-content-chars", "100", "--format", "text"]
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response) as request:
            code, stdout, stderr = run_main(dsw.web_search_main, argv)
        self.assertEqual(code, 0)
        self.assertTrue(request.call_args.args[1]["need_content"])
        self.assertIn("content:", stdout)
        self.assertIn("   " + "x" * 100, stdout)
        self.assertIn("[content truncated at 100 chars]", stdout)
        self.assertNotIn("x" * 101, stdout)

    def test_urls_output_and_cache_hit(self):
        response = self.response()
        argv = ["Python", "-n", "3", "--urls"]
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response) as request:
            first = run_main(dsw.web_search_main, argv + ["--cache-dir", cache])
            second = run_main(dsw.web_search_main, argv + ["--cache-dir", cache])
        self.assertEqual((first[0], second[0]), (0, 0))
        self.assertEqual(request.call_count, 1)
        self.assertEqual(first[1].strip(), "https://example.com/python")
        self.assertIn("cache=hit", second[2])

    def test_empty_results_exit_zero_and_no_cache(self):
        argv = ["Python", "-n", "3", "--format", "json"]
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value={"results": []}) as request:
            first = run_main(dsw.web_search_main, argv + ["--cache-dir", cache])
            second = run_main(dsw.web_search_main, argv + ["--cache-dir", cache])
        self.assertEqual((first[0], second[0]), (0, 0))
        self.assertEqual(request.call_count, 2)
        self.assertEqual(first[1].strip(), "[]")
        self.assertIn("not billed", first[2])

    def test_429_retries_once(self):
        response = self.response()
        error = dsw.ApiError(dsw.SEARCH_PATH, "rate_limit", "slow down", 429, 4)
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", side_effect=[error, response]) as request, \
                mock.patch.object(dsw, "_sleep") as sleep:
            code, stdout, _ = run_main(dsw.web_search_main, ["Python", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(4)

    def test_400_does_not_retry(self):
        error = dsw.ApiError(dsw.SEARCH_PATH, "client", "count invalid", 400)
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", side_effect=error) as request, \
                mock.patch.object(dsw, "_sleep") as sleep:
            code, stdout, stderr = run_main(dsw.web_search_main, ["Python"])
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()
        self.assertIn("client HTTP 400", stderr)
        self.assertEqual(stdout, "")

    def test_local_validation(self):
        cases = [
            ["", "-n", "3"],
            ["x", "-n", "51"],
            ["x", "--ori-question", "y" * 129],
            ["x", "--localization", "not-an-ip"],
            ["x", "--proxy", "socks5://127.0.0.1:1080"],
        ]
        for argv in cases:
            with self.assertRaises(SystemExit) as ctx:
                dsw.web_search_main(argv)
            self.assertEqual(ctx.exception.code, 2)


class FetchTests(unittest.TestCase):
    @staticmethod
    def side_effect(endpoint, payload, timeout, proxy):
        if payload["url"] == "https://example.com":
            return {"title": "Example", "content": "# Example\n\nBody"}
        raise dsw.ApiError(endpoint, "no_content", "no extractable content", 404)

    def test_single_fetch_markdown_and_cache(self):
        response = {"title": "Example", "content": "# Example\n\nBody"}
        argv = ["https://example.com", "--max-chars", "10"]
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response) as request:
            first = run_main(dsw.web_fetch_main, argv + ["--cache-dir", cache])
            second = run_main(dsw.web_fetch_main, argv + ["--cache-dir", cache])
        self.assertEqual((first[0], second[0]), (0, 0))
        self.assertEqual(request.call_count, 1)
        self.assertIn("# Example", first[1])
        self.assertIn("truncated at 10 chars", first[2])
        self.assertIn("cache=hit", second[2])

    def test_multi_url_requires_yes_and_partial_failure_is_isolated(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            with self.assertRaises(SystemExit) as ctx:
                dsw.web_fetch_main(["https://a.com", "https://b.com"])
        self.assertEqual(ctx.exception.code, 2)

        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", side_effect=self.side_effect) as request:
            code, stdout, stderr = run_main(dsw.web_fetch_main, [
                "https://example.com", "https://example.invalid", "--yes",
                "--cache-dir", cache, "--format", "json",
            ])
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 2)
        entries = json.loads(stdout)
        self.assertTrue(entries[0]["ok"])
        self.assertFalse(entries[1]["ok"])
        self.assertEqual(entries[1]["error"]["kind"], "no_content")

    def test_fetch_403_no_retry_and_batch_continues(self):
        def fail_then_succeed(endpoint, payload, timeout, proxy):
            if payload["url"] == "https://blocked.com":
                raise dsw.ApiError(endpoint, "security", "blocked by policy", 403)
            return {"title": "OK", "content": "Body"}

        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", side_effect=fail_then_succeed) as request, \
                mock.patch.object(dsw, "_sleep") as sleep:
            code, stdout, stderr = run_main(dsw.web_fetch_main, [
                "https://blocked.com", "https://example.com", "--yes", "--cache-dir", cache,
            ])
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 2)
        sleep.assert_not_called()
        self.assertIn("security HTTP 403", stderr)
        self.assertIn("Body", stdout)

    def test_fetch_empty_content_is_no_content_and_not_cached(self):
        response = {"title": "Empty", "content": ""}
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response) as request:
            first = run_main(dsw.web_fetch_main, ["https://example.com", "--cache-dir", cache])
            second = run_main(dsw.web_fetch_main, ["https://example.com", "--cache-dir", cache])
        self.assertEqual((first[0], second[0]), (1, 1))
        self.assertEqual(request.call_count, 2)
        self.assertIn("no_content", first[2])

    def test_fetch_json_pagination_fields(self):
        response = {"title": "Long", "content": "x" * 100}
        argv = ["https://example.com", "--start", "10", "--max-chars", "20", "--format", "json"]
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_request_json", return_value=response):
            code, stdout, _ = run_main(dsw.web_fetch_main, argv)
        self.assertEqual(code, 0)
        entry = json.loads(stdout)[0]
        self.assertTrue(entry["ok"])
        self.assertEqual(len(entry["content"]), 20)
        self.assertTrue(entry["truncated"])
        self.assertEqual(entry["next_start"], 30)

    def test_fetch_local_url_validation(self):
        for url in ("file:///etc/hosts", "ftp://example.com", "http://user:pass@example.com", "http://"):
            with self.assertRaises(SystemExit) as ctx:
                dsw.web_fetch_main([url])
            self.assertEqual(ctx.exception.code, 2)


class RequestJsonTests(unittest.TestCase):
    def test_request_uses_bearer_json_and_official_path(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *_args):
                return b'{"ok":true}'

        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-secret-1234567890"}), \
                mock.patch.object(dsw, "_opener") as opener:
            opener.return_value.open.return_value = Response()
            data = dsw._request_json(dsw.SEARCH_PATH, {"query": "x"}, 10, None)
        self.assertEqual(data, {"ok": True})
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, dsw.BASE_URL + dsw.SEARCH_PATH)
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test-secret-1234567890")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.data, dsw._canonical_json({"query": "x"}).encode())

    def test_http_error_message_and_retry_after(self):
        headers = email.message.Message()
        headers["Retry-After"] = "7"
        body = io.BytesIO(json.dumps({
            "error": {"message": "Insufficient balance", "type": "insufficient_balance"}
        }).encode())
        http_error = urlerror.HTTPError(
            dsw.BASE_URL + dsw.SEARCH_PATH, 402, "Payment Required", headers, body
        )
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}), \
                mock.patch.object(dsw, "_opener") as opener:
            opener.return_value.open.side_effect = http_error
            with self.assertRaises(dsw.ApiError) as ctx:
                dsw._request_json(dsw.SEARCH_PATH, {"query": "x"}, 10, None)
        self.assertEqual(ctx.exception.kind, "balance")
        self.assertEqual(ctx.exception.status, 402)
        self.assertEqual(ctx.exception.message, "Insufficient balance")


if __name__ == "__main__":
    unittest.main()
