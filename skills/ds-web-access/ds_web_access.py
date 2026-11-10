"""ds-web-access: DeepSeek Search & Fetch API CLI.

Two entry points (see pyproject.toml [project.scripts]):
  ds-web-search -> web_search_main()
  ds-web-fetch  -> web_fetch_main()

Contract:
  - stdout: results only — compact text, bare URLs, or JSON
  - stderr: one-line notices (endpoint, cache, retry, billing inference) and errors
  - exit codes: 0 success (empty search results included), 1 runtime error, 2 usage error

DeepSeek facts implemented here (verified 2026-11-11):
  - POST https://api.deepseek.com/v1/tools/search and /v1/tools/fetch
  - Bearer DEEPSEEK_API_KEY
  - Search and Fetch are independently billed per successful request
  - Search: query 1-128 chars, count 1-50, optional need_content/ori_question/localization
  - Fetch: one URL per request; multiple URLs are looped by this CLI
  - 400/422/413: caller error; 401: auth; 402: balance; 429: rate limit
  - Fetch 403: safety policy; Fetch 404: no extractable content

Secrets are read only from DEEPSEEK_API_KEY (process environment or <skill>/.env).
They are never accepted as CLI arguments and are redacted from diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE_URL = "https://api.deepseek.com"
SEARCH_PATH = "/v1/tools/search"
FETCH_PATH = "/v1/tools/fetch"
KEY_ENV = "DEEPSEEK_API_KEY"
KEY_URL = "https://platform.deepseek.com/api_keys"
USER_AGENT = "ds-web-access/0.1 (+agent-skills)"

SEARCH_TIMEOUT_DEFAULT = 30
FETCH_TIMEOUT_DEFAULT = 60
SEARCH_CACHE_TTL = 10 * 60
FETCH_CACHE_TTL = 15 * 60
MAX_COUNT = 50
MAX_QUERY_CHARS = 128
MAX_URL_CHARS = 8192
MAX_CONTENT_CHARS_DEFAULT = 4000
MAX_CHARS_DEFAULT = 5000
RETRY_DELAY_SECONDS = 2.0
RETRY_AFTER_CAP_SECONDS = 30.0
_DEEPSEEK_KEY_RE = re.compile(r"sk-[A-Za-z0-9]{16,}")


class UsageError(Exception):
    """Local argument validation failure; no network request is sent."""


@dataclass
class ApiError(Exception):
    """DeepSeek API failure with policy classification."""

    endpoint: str
    kind: str
    message: str
    status: int | None = None
    retry_after: float | None = None

    def __str__(self) -> str:
        status = f" HTTP {self.status}" if self.status is not None else ""
        return f"{self.kind}{status}: {self.message}"


@dataclass
class FetchFailure:
    url: str
    kind: str
    message: str
    status: int | None = None


def _notice(prog: str, message: str) -> None:
    print(f"{prog}: {message}", file=sys.stderr)


def _fail(prog: str, exc_type: str, message: str) -> int:
    print(f"{prog}: {exc_type}: {message}", file=sys.stderr)
    return 1


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _env_file_path() -> Path:
    override = os.environ.get("DS_WEB_ACCESS_ENV_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / ".env"


def _load_env_file() -> None:
    """Load DEEPSEEK_API_KEY from .env; process environment always wins."""
    try:
        lines = _env_file_path().read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key != KEY_ENV or os.environ.get(key):
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value


def _api_key() -> str | None:
    value = os.environ.get(KEY_ENV)
    return value or None


def _redact_text(text: str) -> str:
    redacted = _DEEPSEEK_KEY_RE.sub("sk-[REDACTED]", text)
    secret = _api_key()
    if secret:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def default_cache_dir() -> Path:
    override = os.environ.get("DS_WEB_ACCESS_CACHE")
    if override:
        return Path(override)
    here = Path(__file__).resolve().parent
    if (here / "pyproject.toml").exists():
        return here / ".cache"
    return Path.cwd() / ".cache"


def _cache_key(endpoint: str, payload: dict, output_format: str) -> str:
    material = f"{endpoint}\0{_canonical_json(payload)}\0{output_format}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _cache_path(cache_dir: Path, endpoint: str, payload: dict, output_format: str) -> Path:
    return cache_dir / (_cache_key(endpoint, payload, output_format) + ".bin")


def cache_get(cache_dir: Path, endpoint: str, payload: dict, output_format: str, ttl: int) -> bytes | None:
    try:
        path = _cache_path(cache_dir, endpoint, payload, output_format)
        if path.stat().st_mtime + ttl < time.time():
            return None
        return path.read_bytes()
    except OSError:
        return None


def cache_put(cache_dir: Path, endpoint: str, payload: dict, output_format: str, data: bytes) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_path(cache_dir, endpoint, payload, output_format).write_bytes(data)
    except OSError:
        pass


def _classify_status(endpoint: str, status: int) -> tuple[str, bool]:
    """Return (error kind, retry within endpoint)."""
    if status in (400, 413, 422):
        return "client", False
    if status == 401:
        return "auth", False
    if status == 402:
        return "balance", False
    if status == 403 and endpoint == FETCH_PATH:
        return "security", False
    if status == 404 and endpoint == FETCH_PATH:
        return "no_content", False
    if status == 408:
        return "timeout", True
    if status == 429:
        return "rate_limit", True
    if status in (500, 503, 504):
        return "server", True
    return "client", False


def _error_message(body: bytes) -> str:
    if not body:
        return "empty error response"
    text = body[:2048].decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text.strip() or "unreadable error response"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            for key in ("message", "code", "type"):
                value = error.get(key)
                if isinstance(value, str) and value:
                    return value
        for key in ("message", "detail", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return text.strip() or "unreadable error response"


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    return seconds if seconds > 0 else None


def _opener(proxy: str | None) -> urlrequest.OpenerDirector:
    if proxy:
        return urlrequest.build_opener(urlrequest.ProxyHandler({"http": proxy, "https": proxy}))
    return urlrequest.build_opener()


def _request_json(endpoint: str, payload: dict, timeout: int, proxy: str | None) -> dict:
    key = _api_key()
    if not key:
        raise ApiError(endpoint, "auth", f"set {KEY_ENV} in the environment or <skill>/.env ({KEY_URL})")
    body = _canonical_json(payload).encode("utf-8")
    request = urlrequest.Request(
        BASE_URL + endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with _opener(proxy).open(request, timeout=timeout) as response:
            raw = response.read(20 * 1024 * 1024)
    except urlerror.HTTPError as exc:
        detail = _redact_text(_error_message(exc.read(2048)))
        kind, retryable = _classify_status(endpoint, exc.code)
        raise ApiError(endpoint, kind, detail, exc.code,
                       _parse_retry_after(exc.headers.get("Retry-After"))) from None
    except urlerror.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise ApiError(endpoint, "network", _redact_text(str(reason))) from None
    except TimeoutError:
        raise ApiError(endpoint, "network", "request timed out") from None
    try:
        parsed = json.loads(raw.decode("utf-8", "replace"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(endpoint, "protocol", _redact_text(str(exc))) from None
    if not isinstance(parsed, dict):
        raise ApiError(endpoint, "protocol", "response is not a JSON object")
    return parsed


def _retry_delay(exc: ApiError) -> float:
    if exc.kind == "rate_limit" and exc.retry_after is not None:
        return min(exc.retry_after, RETRY_AFTER_CAP_SECONDS)
    return RETRY_DELAY_SECONDS


def _retry_allowed(exc: ApiError) -> bool:
    return exc.kind in ("timeout", "rate_limit", "server", "network", "protocol")


def _call_with_retry(prog: str, endpoint: str, func: Callable[[], dict]) -> dict:
    for attempt in (1, 2):
        try:
            return func()
        except ApiError as exc:
            if attempt == 1 and _retry_allowed(exc):
                _notice(prog, f"endpoint={endpoint.removeprefix('/v1/tools/')} {exc}; "
                              f"retrying in {_retry_delay(exc):g}s")
                _sleep(_retry_delay(exc))
                continue
            raise


def _search_payload(args: argparse.Namespace) -> dict:
    payload: dict = {"query": args.query, "count": args.count, "need_content": bool(args.need_content)}
    if args.ori_question:
        payload["ori_question"] = args.ori_question
    if args.localization:
        payload["localization"] = args.localization
    return payload


def _derive_citation(item: dict) -> dict:
    citation: dict = {}
    for key in ("title", "url", "site_name", "date"):
        value = item.get(key)
        if value:
            citation[key] = value
    return citation


def _normalize_search_results(payload: dict) -> list[dict]:
    raw = payload.get("results")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ApiError(SEARCH_PATH, "protocol", "search response 'results' is not a list")
    normalized: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        result = {
            "rerank_score": item.get("rerank_score"),
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("snippet") or ""),
            "summary": str(item.get("summary") or ""),
            "content": str(item.get("content") or ""),
            "site_name": item.get("site_name"),
            "site_icon": item.get("site_icon"),
            "date": item.get("date"),
            "authority": item.get("authority"),
        }
        result["citation"] = _derive_citation(result)
        if result["url"]:
            normalized.append(result)
    return normalized


def _clip(text: str, limit: int) -> tuple[str, int | None]:
    if limit <= 0 or len(text) <= limit:
        return text, None
    return text[:limit], limit


def _render_search_text(results: list[dict], args: argparse.Namespace) -> None:
    for index, item in enumerate(results, 1):
        print(f"{index}. {item.get('title', '')}")
        print(f"   {item.get('url', '')}")
        meta: list[str] = []
        for key in ("date", "site_name"):
            if item.get(key) is not None:
                meta.append(f"{key}={item[key]}")
        if item.get("authority") is not None:
            meta.append(f"authority={item['authority']}")
        if item.get("rerank_score") is not None:
            meta.append(f"rerank_score={item['rerank_score']}")
        if meta:
            print("   " + " ".join(meta))
        summary = item.get("summary") or item.get("snippet") or ""
        if summary:
            print(f"   {summary}")
        if args.need_content and item.get("content"):
            content, truncated = _clip(str(item["content"]), args.max_content_chars)
            print("   content:")
            for line in content.splitlines() or [""]:
                print(f"   {line}")
            if truncated is not None:
                print(f"   [content truncated at {truncated} chars]")
        if index < len(results):
            print()


def _render_search(results: list[dict], args: argparse.Namespace) -> int:
    if args.urls:
        for item in results:
            print(item.get("url", ""))
        return 0
    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False))
        return 0
    _render_search_text(results, args)
    return 0


def _validate_search_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    query = args.query.strip()
    if not query:
        parser.error("query must not be blank")
    if len(args.query) > MAX_QUERY_CHARS:
        parser.error(f"query must be <= {MAX_QUERY_CHARS} Unicode characters")
    if not 1 <= args.count <= MAX_COUNT:
        parser.error(f"--count must be between 1 and {MAX_COUNT}")
    if args.ori_question is not None and len(args.ori_question) > MAX_QUERY_CHARS:
        parser.error(f"--ori-question must be <= {MAX_QUERY_CHARS} Unicode characters")
    if args.max_content_chars < 0:
        parser.error("--max-content-chars must be >= 0 (0 = no limit)")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.localization:
        try:
            ipaddress.ip_address(args.localization)
        except ValueError:
            parser.error("--localization must be an IPv4 or IPv6 address; it is not collected automatically")
    if args.proxy and not args.proxy.startswith(("http://", "https://")):
        parser.error("DeepSeek API requests support http/https proxies only")


def web_search_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ds-web-search",
        description="Web search via DeepSeek Search API. Query syntax supports site:, -site:, lang:, after:, and before:.",
    )
    parser.add_argument("query", help="search query, <=128 Unicode characters")
    parser.add_argument("-n", "--count", type=int, default=10,
                        help=f"result count 1-{MAX_COUNT} (default: 10; does not change request price)")
    parser.add_argument("--need-content", action="store_true",
                        help="request page content in each result (default: summaries only)")
    parser.add_argument("--ori-question", help="original user question, <=128 chars, optional intent hint")
    parser.add_argument("--localization", help="explicit IP address for localized results; never auto-detected")
    parser.add_argument("--max-content-chars", type=int, default=MAX_CONTENT_CHARS_DEFAULT,
                        help=f"truncate each result content when --need-content is used; 0=no limit (default: {MAX_CONTENT_CHARS_DEFAULT})")
    parser.add_argument("--timeout", type=int, default=SEARCH_TIMEOUT_DEFAULT,
                        help=f"request timeout in seconds (default: {SEARCH_TIMEOUT_DEFAULT})")
    parser.add_argument("--proxy", help="http/https proxy URL")
    parser.add_argument("--cache-dir", help="cache directory (default: <skill>/.cache)")
    parser.add_argument("--no-cache", action="store_true", help="bypass cache read and write")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--format", choices=("text", "json"), default="text",
                        help="output format (default: text)")
    output.add_argument("--urls", action="store_true", help="print result URLs only, one per line")
    args = parser.parse_args(argv)
    _validate_search_args(parser, args)

    _load_env_file()
    if not _api_key():
        return _fail(parser.prog, "MissingKeyError",
                     f"set {KEY_ENV} in the environment or <skill>/.env; get a key at {KEY_URL}")

    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    payload = _search_payload(args)
    output_format = "urls" if args.urls else args.format
    if not args.no_cache:
        cached = cache_get(cache_dir, SEARCH_PATH, payload, output_format, SEARCH_CACHE_TTL)
        if cached is not None:
            results = json.loads(cached.decode("utf-8", "replace"))
            _notice(parser.prog, "endpoint=search cache=hit")
            return _render_search(results, args)
    try:
        response = _call_with_retry(parser.prog, SEARCH_PATH,
                                    lambda: _request_json(SEARCH_PATH, payload, args.timeout, args.proxy))
        results = _normalize_search_results(response)
    except ApiError as exc:
        return _fail(parser.prog, type(exc).__name__, str(exc))
    except Exception as exc:
        return _fail(parser.prog, type(exc).__name__, _redact_text(str(exc)))

    billed = "yes" if results else "no"
    _notice(parser.prog, f"endpoint=search count={args.count} results={len(results)} "
                         f"cache=miss billed={billed} billing=inferred")
    if not results:
        _notice(parser.prog, "no results found; empty search results are not billed by DeepSeek")
        return _render_search(results, args)
    if not args.no_cache:
        cache_put(cache_dir, SEARCH_PATH, payload, output_format,
                  _canonical_json(results).encode("utf-8"))
    return _render_search(results, args)


def _validate_fetch_url(value: str) -> None:
    if not 1 <= len(value) <= MAX_URL_CHARS:
        raise UsageError(f"URL length must be 1-{MAX_URL_CHARS}: {value}")
    parsed = urlparse.urlsplit(value)
    if parsed.scheme not in ("http", "https"):
        raise UsageError(f"URL must start with http:// or https://: {value}")
    if not parsed.hostname:
        raise UsageError(f"URL must contain a host: {value}")
    if parsed.username is not None or parsed.password is not None:
        raise UsageError(f"URL must not contain username or password: {value}")


def _fetch_once(url: str, args: argparse.Namespace) -> dict:
    return _request_json(FETCH_PATH, {"url": url}, args.timeout, args.proxy)


def _fetched_page(url: str, payload: dict) -> dict:
    title = str(payload.get("title") or "")
    content = str(payload.get("content") or "")
    return {"url": url, "title": title, "content": content}


def _emit_page_markdown(prog: str, url: str, page: dict, args: argparse.Namespace, multi: bool) -> None:
    text = page["content"]
    start = args.start
    if start >= len(text):
        if start:
            _notice(prog, f"{url}: start {start} is beyond end of content ({len(text)} chars)")
        text = ""
    else:
        text = text[start:]
        if args.max_chars and len(text) > args.max_chars:
            text = text[:args.max_chars]
            _notice(prog, f"{url}: truncated at {args.max_chars} chars "
                          f"(continue with --start {start + args.max_chars})")
    if multi:
        print(f"===== {url} =====")
    if page["title"]:
        print(f"# {page['title']}\n")
    print(text)


def _page_json_entry(url: str, page: dict | None, failure: FetchFailure | None,
                     args: argparse.Namespace) -> dict:
    if page is None:
        assert failure is not None
        return {
            "url": url,
            "ok": False,
            "error": {"kind": failure.kind, "message": failure.message, "status": failure.status},
        }
    content = page["content"]
    start = args.start
    available = max(0, len(content) - start)
    emitted = content[start:] if start < len(content) else ""
    truncated = bool(args.max_chars and len(emitted) > args.max_chars)
    if truncated:
        emitted = emitted[:args.max_chars]
    return {
        "url": url,
        "ok": True,
        "title": page["title"],
        "content": emitted,
        "truncated": truncated,
        "next_start": start + len(emitted) if truncated else None,
    }


def web_fetch_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ds-web-fetch",
        description="Fetch page Markdown via DeepSeek Fetch API. Each successful URL is billed independently.",
    )
    parser.add_argument("url", nargs="+", help="http(s) URL(s); duplicates are fetched once")
    parser.add_argument("--yes", action="store_true",
                        help="confirm a multi-URL batch; every successful URL is billed as one request")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown",
                        help="output format (default: markdown)")
    parser.add_argument("--max-chars", type=int, default=MAX_CHARS_DEFAULT,
                        help=f"truncate each page to N chars; 0=no limit (default: {MAX_CHARS_DEFAULT})")
    parser.add_argument("--start", type=int, default=0,
                        help="skip the first N chars; pair with --max-chars to read long pages")
    parser.add_argument("--timeout", type=int, default=FETCH_TIMEOUT_DEFAULT,
                        help=f"request timeout in seconds (default: {FETCH_TIMEOUT_DEFAULT})")
    parser.add_argument("--proxy", help="http/https proxy URL")
    parser.add_argument("--cache-dir", help="cache directory (default: <skill>/.cache)")
    parser.add_argument("--no-cache", action="store_true", help="bypass cache read and write")
    args = parser.parse_args(argv)

    if args.start < 0:
        parser.error("--start must be >= 0")
    if args.max_chars < 0:
        parser.error("--max-chars must be >= 0 (0 = no limit)")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.proxy and not args.proxy.startswith(("http://", "https://")):
        parser.error("DeepSeek API requests support http/https proxies only")
    for value in args.url:
        try:
            _validate_fetch_url(value)
        except UsageError as exc:
            parser.error(str(exc))

    urls = list(dict.fromkeys(args.url))
    if len(urls) > 1 and not args.yes:
        parser.error(f"multi-URL fetch makes {len(urls)} independently billed requests; rerun with --yes to confirm")

    _load_env_file()
    if not _api_key():
        return _fail(parser.prog, "MissingKeyError",
                     f"set {KEY_ENV} in the environment or <skill>/.env; get a key at {KEY_URL}")

    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    pages: dict[str, dict] = {}
    failures: dict[str, FetchFailure] = {}
    remaining = list(urls)

    if not args.no_cache:
        missing: list[str] = []
        for url in remaining:
            cached = cache_get(cache_dir, FETCH_PATH, {"url": url}, "raw", FETCH_CACHE_TTL)
            if cached is not None:
                pages[url] = json.loads(cached.decode("utf-8", "replace"))
                _notice(parser.prog, f"{url}: endpoint=fetch cache=hit")
            else:
                missing.append(url)
        remaining = missing

    for url in remaining:
        try:
            response = _call_with_retry(parser.prog, FETCH_PATH,
                                        lambda u=url: _fetch_once(u, args))
            page = _fetched_page(url, response)
            if not page["content"]:
                raise ApiError(FETCH_PATH, "no_content", "API returned empty content", 200)
            pages[url] = page
            if not args.no_cache:
                cache_put(cache_dir, FETCH_PATH, {"url": url}, "raw",
                          _canonical_json(page).encode("utf-8"))
            _notice(parser.prog, f"{url}: endpoint=fetch cache=miss billed=yes billing=inferred")
        except ApiError as exc:
            failures[url] = FetchFailure(url, exc.kind, exc.message, exc.status)
            _notice(parser.prog, f"{url}: {exc}")
        except Exception as exc:
            failures[url] = FetchFailure(url, "protocol", _redact_text(str(exc)))
            _notice(parser.prog, f"{url}: {type(exc).__name__}: {_redact_text(str(exc))}")

    if args.format == "json":
        entries = [_page_json_entry(url, pages.get(url), failures.get(url), args) for url in urls]
        print(json.dumps(entries, ensure_ascii=False))
    else:
        multi = len(urls) > 1
        for url in urls:
            page = pages.get(url)
            if page is not None:
                _emit_page_markdown(parser.prog, url, page, args, multi)

    return 1 if failures else 0


if __name__ == "__main__":
    tool = os.path.basename(sys.argv[0]).lower()
    if "fetch" in tool:
        sys.exit(web_fetch_main())
    sys.exit(web_search_main())
