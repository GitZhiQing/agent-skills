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


def run_main(func, argv, env_file: Path | str | None = None):
    """Capture a main() call and return (exit_code, stdout, stderr).

    Offline tests point API_WEB_ACCESS_ENV_FILE at a nonexistent file so the
    maintainer's real <skill>/.env never changes provider selection or mocking.
    Pass env_file explicitly for .env-parser tests.
    """
    selected_env = Path(env_file) if env_file is not None else SKILL_DIR / "tests" / ".env.absent"
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"API_WEB_ACCESS_ENV_FILE": str(selected_env)}), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = func(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class ClassificationTests(unittest.TestCase):
    def test_status_matrix(self):
        self.assertEqual(awa._classify_status(401), ("auth", False, True))
        self.assertEqual(awa._classify_status(403), ("auth", False, True))
        self.assertEqual(awa._classify_status(402), ("quota", False, True))
        self.assertEqual(awa._classify_status(432), ("quota", False, True))
        self.assertEqual(awa._classify_status(434), ("quota", False, True))
        self.assertEqual(awa._classify_status(429), ("rate_limit", True, True))
        self.assertEqual(awa._classify_status(500), ("server", True, True))
        self.assertEqual(awa._classify_status(400), ("client", False, False))
        self.assertEqual(awa._classify_status(404), ("client", False, False))

    def test_retry_and_switch_policy(self):
        rate = awa.ProviderError("tavily", "rate_limit", "slow down", 429, 3)
        client = awa.ProviderError("tavily", "client", "bad request", 400)
        fetch = awa.ProviderError("tavily", "fetch_failed", "missing")
        self.assertTrue(awa._retry_allowed(rate))
        self.assertFalse(awa._retry_allowed(client))
        self.assertTrue(awa._switch_allowed(rate))
        self.assertTrue(awa._switch_allowed(fetch))
        self.assertFalse(awa._switch_allowed(client))
        self.assertEqual(awa._retry_delay(rate), 3)


class RedactionTests(unittest.TestCase):
    def test_redacts_known_key_and_tavly_pattern(self):
        secret = "super-secret-tavly-value"
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": secret}):
            text = f"failed key={secret} leaked=tvly-ABC123_-"
            redacted = awa._redact_text(text)
        self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("tvly-[REDACTED]", redacted)

    def test_error_message_extracts_detail(self):
        body = json.dumps({"detail": "Invalid API key"}).encode()
        self.assertEqual(awa._error_message_from_body(body), "Invalid API key")

    def test_error_message_redaction(self):
        secret = "super-secret-exa-value"
        body = f'{{"message":"bad {secret}"}}'.encode()
        with mock.patch.dict(os.environ, {"EXA_API_KEY": secret}):
            self.assertNotIn(secret, awa._error_message_from_body(body))


class EnvFileTests(unittest.TestCase):
    def test_env_file_fills_absent_keys_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "# comment\n"
                "export TAVILY_API_KEY='file-tavly'\n"
                'EXA_API_KEY="file-exa"\n'
                "OTHER_SECRET=ignored\n",
                encoding="utf-8",
            )
            env = {"TAVILY_API_KEY": "process-tavly", "API_WEB_ACCESS_ENV_FILE": str(env_file)}
            with mock.patch.dict(os.environ, env):
                awa._load_env_file()
                self.assertEqual(awa._provider_key("tavily"), "process-tavly")
                self.assertEqual(awa._provider_key("exa"), "file-exa")
                self.assertIsNone(os.environ.get("OTHER_SECRET"))

    def test_env_file_is_ignored_when_absent_or_malformed(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.env"
            malformed = Path(directory) / ".env"
            malformed.write_text("TAVILY_API_KEY\nEXA_API_KEY=valid-exa\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {
                "TAVILY_API_KEY": "", "EXA_API_KEY": "", "API_WEB_ACCESS_ENV_FILE": str(missing),
            }):
                awa._load_env_file()
                self.assertIsNone(awa._provider_key("tavily"))
                self.assertIsNone(awa._provider_key("exa"))
            with mock.patch.dict(os.environ, {
                "TAVILY_API_KEY": "", "EXA_API_KEY": "", "API_WEB_ACCESS_ENV_FILE": str(malformed),
            }):
                awa._load_env_file()
                self.assertIsNone(awa._provider_key("tavily"))
                self.assertEqual(awa._provider_key("exa"), "valid-exa")

    def test_cli_reads_provider_key_from_env_file(self):
        response = {"results": [{"title": "File", "url": "https://example.com", "content": "body"}]}
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("TAVILY_API_KEY=file-tavly\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"TAVILY_API_KEY": ""}), \
                    mock.patch.object(awa, "_request_json", return_value=response) as request:
                code, _, stderr = run_main(
                    awa.web_search_main,
                    ["env file", "--provider", "tavily", "--cache-dir", directory, "--format", "json"],
                    env_file=env_file,
                )
        self.assertEqual(code, 0)
        self.assertEqual(request.call_args.args[3]["Authorization"], "Bearer file-tavly")
        self.assertIn("provider=tavily", stderr)

    def test_secret_redaction_includes_env_file_values(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("EXA_API_KEY=file-exa-secret\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "", "API_WEB_ACCESS_ENV_FILE": str(env_file)}):
                self.assertNotIn("file-exa-secret", awa._redact_text("leak file-exa-secret"))


class SearchTests(unittest.TestCase):
    def test_explicit_tavily_success_normalizes_results(self):
        env = {"TAVILY_API_KEY": "tvly-test"}
        response = {"results": [
            {"title": "Python", "url": "https://python.org", "content": "Release notes"},
            {"title": "No URL", "url": "", "content": "ignored"},
        ]}
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", return_value=response) as request:
            code, stdout, stderr = run_main(
                awa.web_search_main,
                ["python 3.13", "--provider", "tavily", "-m", "2", "--cache-dir", cache, "--format", "json"],
            )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload, [{"title": "Python", "href": "https://python.org", "body": "Release notes"}])
        self.assertIn("provider=tavily", stderr)
        args = request.call_args.args
        self.assertEqual(args[1], awa.TAVILY_SEARCH_URL)
        self.assertEqual(args[3]["Authorization"], "Bearer tvly-test")
        self.assertEqual(args[2]["max_results"], 2)

    def test_auto_switches_from_auth_failure_to_exa(self):
        env = {"TAVILY_API_KEY": "bad", "EXA_API_KEY": "good"}
        responses = [
            awa.ProviderError("tavily", "auth", "Invalid API key", 401),
            {"results": [{"title": "Exa", "url": "https://exa.ai", "text": "result"}]},
        ]
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", side_effect=responses) as request:
            code, stdout, stderr = run_main(
                awa.web_search_main,
                ["python", "--cache-dir", cache, "--format", "json"],
            )
        self.assertEqual(code, 0)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[0].args[1], awa.TAVILY_SEARCH_URL)
        self.assertEqual(request.call_args_list[1].args[1], awa.EXA_SEARCH_URL)
        self.assertEqual(request.call_args_list[1].args[3]["x-api-key"], "good")
        self.assertIn("provider=tavily failed", stderr)
        self.assertIn("provider=exa", stderr)
        self.assertIn("Exa", stdout)

    def test_429_retries_once_within_provider(self):
        env = {"TAVILY_API_KEY": "tvly-test"}
        responses = [
            awa.ProviderError("tavily", "rate_limit", "slow down", 429, 4),
            {"results": [{"title": "OK", "url": "https://example.com", "content": "text"}]},
        ]
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", side_effect=responses) as request, \
                mock.patch.object(awa, "_sleep") as sleep:
            code, stdout, stderr = run_main(
                awa.web_search_main,
                ["retry probe", "--provider", "tavily", "--cache-dir", cache, "--urls"],
            )
        self.assertEqual(code, 0)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(4.0)
        self.assertIn("retrying in 4s", stderr)
        self.assertEqual(stdout.strip(), "https://example.com")

    def test_400_does_not_switch_or_retry(self):
        env = {"TAVILY_API_KEY": "bad", "EXA_API_KEY": "good"}
        error = awa.ProviderError("tavily", "client", "Invalid request", 400)
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", side_effect=error) as request, \
                mock.patch.object(awa, "_sleep") as sleep:
            code, stdout, stderr = run_main(
                awa.web_search_main, ["bad request", "--cache-dir", cache]
            )
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(stdout, "")
        self.assertIn("client HTTP 400", stderr)
        self.assertNotIn("provider=exa\n", stderr)

    def test_successful_empty_results_do_not_switch(self):
        env = {"TAVILY_API_KEY": "tvly", "EXA_API_KEY": "exa"}
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", return_value={"results": []}) as request:
            code, stdout, stderr = run_main(
                awa.web_search_main,
                ["unlikely query", "--cache-dir", cache, "--format", "json"],
            )
        self.assertEqual(code, 0)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(stdout.strip(), "[]")
        self.assertIn("no results found.", stderr)
        self.assertNotIn("provider=exa", stderr)

    def test_missing_keys_fail_without_request(self):
        env = {"TAVILY_API_KEY": "", "EXA_API_KEY": ""}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json") as request:
            # run_main points API_WEB_ACCESS_ENV_FILE at a nonexistent file.
            code, stdout, stderr = run_main(awa.web_search_main, ["anything"])
        self.assertEqual(code, 1)
        request.assert_not_called()
        self.assertIn("MissingKeyError", stderr)
        self.assertIn(".env", stderr)
        self.assertIn("an available free web-search provider", stderr)
        self.assertEqual(stdout, "")

    def test_invalid_max_results_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            awa.web_search_main(["query", "--max-results", "0"])
        self.assertEqual(ctx.exception.code, 2)

    def test_search_cache_is_provider_scoped(self):
        env = {"TAVILY_API_KEY": "tvly", "EXA_API_KEY": "exa"}
        response = {"results": [{"title": "Cached", "url": "https://example.com", "content": "body"}]}
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", return_value=response) as request:
            first = run_main(awa.web_search_main, ["cache", "--provider", "tavily", "--cache-dir", cache, "--format", "json"])
            second = run_main(awa.web_search_main, ["cache", "--provider", "tavily", "--cache-dir", cache, "--format", "json"])
            third = run_main(awa.web_search_main, ["cache", "--provider", "exa", "--cache-dir", cache, "--format", "json"])
        self.assertEqual((first[0], second[0], third[0]), (0, 0, 0))
        self.assertEqual(request.call_count, 2)
        self.assertIn("cache hit", second[2])
        self.assertNotIn("cache hit", third[2])


class FetchTests(unittest.TestCase):
    @staticmethod
    def tavily_then_exa(provider, url, payload, headers, timeout, proxy):
        if url == awa.TAVILY_EXTRACT_URL:
            return {"results": [{"url": "https://example.com", "raw_content": "Example Markdown"}],
                    "failed_results": [{"url": "https://example.invalid", "error": "fetch failed"}]}
        return {"results": [{"id": "https://example.invalid", "text": "Recovered by Exa"}]}

    def test_auto_fetch_recovers_only_failed_url(self):
        env = {"TAVILY_API_KEY": "tvly", "EXA_API_KEY": "exa"}
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", side_effect=self.tavily_then_exa) as request:
            code, stdout, stderr = run_main(
                awa.web_fetch_main,
                ["https://example.com", "https://example.invalid", "--cache-dir", cache],
            )
        self.assertEqual(code, 0)
        self.assertIn("Example Markdown", stdout)
        self.assertIn("Recovered by Exa", stdout)
        self.assertIn("https://example.com", stdout)
        self.assertEqual(request.call_count, 2)
        self.assertIn("1 URL(s) missing content", stderr)
        self.assertIn("provider=exa", stderr)

    def test_explicit_provider_does_not_recover_failed_url(self):
        env = {"TAVILY_API_KEY": "tvly"}
        response = {"results": [{"url": "https://example.com", "raw_content": "Example Markdown"}],
                    "failed_results": [{"url": "https://example.invalid", "error": "gone"}]}
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", return_value=response) as request:
            code, stdout, stderr = run_main(
                awa.web_fetch_main,
                ["https://example.com", "https://example.invalid", "--provider", "tavily", "--cache-dir", cache],
            )
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 1)
        self.assertIn("Example Markdown", stdout)
        self.assertIn("fetch_failed: gone", stderr)

    def test_fetch_pagination_notice(self):
        env = {"TAVILY_API_KEY": "tvly"}
        response = {"results": [{"url": "https://example.com", "raw_content": "x" * 30}]}
        argv = ["https://example.com", "--provider", "tavily", "--start", "10", "--max-chars", "5"]
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", return_value=response):
            code, stdout, stderr = run_main(awa.web_fetch_main, argv + ["--cache-dir", cache])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "x" * 5 + "\n")
        self.assertIn("continue with --start 15", stderr)

    def test_fetch_rejects_non_http_url(self):
        with self.assertRaises(SystemExit) as ctx:
            awa.web_fetch_main(["file:///etc/hosts"])
        self.assertEqual(ctx.exception.code, 2)

    def test_fetch_cache_is_provider_and_format_scoped(self):
        env = {"TAVILY_API_KEY": "tvly"}
        response = {"results": [{"url": "https://example.com", "raw_content": "content"}]}
        common = ["https://example.com", "--provider", "tavily"]
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ, env), \
                mock.patch.object(awa, "_request_json", return_value=response) as request:
            first = run_main(awa.web_fetch_main, common + ["--cache-dir", cache])
            second = run_main(awa.web_fetch_main, common + ["--cache-dir", cache])
            other_format = run_main(
                awa.web_fetch_main, common + ["-f", "text_plain", "--cache-dir", cache]
            )
        self.assertEqual((first[0], second[0], other_format[0]), (0, 0, 0))
        self.assertEqual(request.call_count, 2)
        self.assertIn("cache hit", second[2])
        self.assertNotIn("cache hit", other_format[2])


if __name__ == "__main__":
    unittest.main()
