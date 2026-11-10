"""api-web-access: stable web search & fetch CLI backed by Tavily and Exa.

Two entry points (see pyproject.toml [project.scripts]):
  api-web-search -> web_search_main()
  api-web-fetch  -> web_fetch_main()

Contract:
  - stdout: results only — compact text blocks, bare URLs, or normalized JSON
  - stderr: one-line notices (provider, retry, failover, cache) and errors
  - exit codes: 0 success (empty search results included), 1 runtime error, 2 usage error

Provider policy (default --provider auto):
  - order: Tavily -> Exa when both API keys are present
  - 401/403/402/432/433/434 switch without an in-provider retry
  - 429 honors Retry-After (capped at 30s); 5xx/network/protocol retry once, then switch
  - 400 (and other 4xx) is a caller bug: no retry, no switch
  - a successful empty search stays exit 0 and does not consume the backup provider

Secrets are read only from TAVILY_API_KEY / EXA_API_KEY. They are never accepted
as CLI arguments, never placed in URLs, and are redacted from diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib import error as urlerror
from urllib import request as urlrequest

# Windows pipes may use a legacy codepage; force UTF-8 so non-ASCII results
# survive both TTY and piped (agent) output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MAX_CHARS_DEFAULT = 5000
CACHE_TTL_SECONDS = 15 * 60
TIMEOUT_DEFAULT = 20
RETRY_DELAY_SECONDS = 2
RETRY_AFTER_CAP_SECONDS = 30
MAX_SEARCH_RESULTS = 20
MAX_FETCH_BATCH = 20

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_CONTENTS_URL = "https://api.exa.ai/contents"

PROVIDERS = ("tavily", "exa")
KEY_ENV = {"tavily": "TAVILY_API_KEY", "exa": "EXA_API_KEY"}
KEY_HELP = {
    "tavily": "set TAVILY_API_KEY in the environment or <skill>/.env (https://app.tavily.com)",
    "exa": "set EXA_API_KEY in the environment or <skill>/.env (https://dashboard.exa.ai)",
}
USER_AGENT = "api-web-access/0.1 (+agent-skills)"
_TIME_RANGE = {"d": "day", "w": "week", "m": "month", "y": "year"}
_TIME_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}
_TAVLY_KEY_RE = re.compile(r"tvly-[A-Za-z0-9_-]+")


@dataclass
class ProviderError(Exception):
    """A provider call failed with a policy-classified error."""

    provider: str
    kind: str  # auth | quota | rate_limit | server | network | protocol | client | fetch_failed
    message: str
    status: int | None = None
    retry_after: int | None = None

    def __str__(self) -> str:
        status = f" HTTP {self.status}" if self.status is not None else ""
        return f"{self.kind}{status}: {self.message}"


@dataclass
class FetchFailure:
    provider: str
    url: str
    kind: str
    message: str


def _notice(prog: str, message: str) -> None:
    print(f"{prog}: {message}", file=sys.stderr)


def _fail(prog: str, exc_type: str, message: str) -> int:
    print(f"{prog}: {exc_type}: {message}", file=sys.stderr)
    return 1


def _sleep(seconds: float) -> None:
    """Separate hook so unit tests can disable wall-clock waiting."""
    time.sleep(seconds)


def _env_file_path() -> Path:
    """Local key file: API_WEB_ACCESS_ENV_FILE overrides <skill>/.env."""
    override = os.environ.get("API_WEB_ACCESS_ENV_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / ".env"


def _load_env_file() -> None:
    """Load provider keys from .env into the process environment.

    Only TAVILY_API_KEY / EXA_API_KEY are accepted. Existing environment
    variables always win, so CI/production secrets are never overwritten by a
    local file. Parsing is deliberately minimal: one KEY=VALUE per line,
    optional `export `, optional surrounding quotes, and # comment lines.
    """
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
        if key not in KEY_ENV.values() or os.environ.get(key):
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value


def _secret_values() -> list[str]:
    _load_env_file()
    return [value for value in (os.environ.get(KEY_ENV[p]) for p in PROVIDERS) if value]


def _redact_text(text: str) -> str:
    redacted = _TAVLY_KEY_RE.sub("tvly-[REDACTED]", text)
    for secret in _secret_values():
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def default_cache_dir() -> Path:
    """Cache lives under the skill root; API_WEB_ACCESS_CACHE overrides it."""
    env = os.environ.get("API_WEB_ACCESS_CACHE")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    if (here / "pyproject.toml").exists():
        return here / ".cache"
    return Path.cwd() / ".cache"


def _cache_key(operation: str, provider: str, identity: str, fmt: str = "") -> str:
    material = f"{operation}\0{provider}\0{identity}\0{fmt}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def cache_get(cache_dir: Path, operation: str, provider: str, identity: str, fmt: str = "") -> bytes | None:
    """Return fresh cached payload, else None. Best-effort and never raises."""
    try:
        path = cache_dir / (_cache_key(operation, provider, identity, fmt) + ".bin")
        if path.stat().st_mtime + CACHE_TTL_SECONDS < time.time():
            return None
        return path.read_bytes()
    except OSError:
        return None


def cache_put(cache_dir: Path, operation: str, provider: str, identity: str, fmt: str, data: bytes) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / (_cache_key(operation, provider, identity, fmt) + ".bin")).write_bytes(data)
    except OSError:
        pass  # caching is an optimization, never a failure mode


def _classify_status(status: int) -> tuple[str, bool, bool]:
    """Map an HTTP status to (kind, retry_within_provider, switch_provider)."""
    if status in (401, 403):
        return "auth", False, True
    if status == 402 or status in (432, 433, 434):
        return "quota", False, True
    if status == 429:
        return "rate_limit", True, True
    if status >= 500:
        return "server", True, True
    return "client", False, False


def _error_message_from_body(body: bytes) -> str:
    if not body:
        return "empty error response"
    text = body[:1024].decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text.strip() or "unreadable error response"
    if isinstance(payload, dict):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return _redact_text(value)
        # Exa-style {"errors": [{"message": ...}]} and arrays of strings.
        for key in ("errors", "error"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, dict):
                    return _redact_text(str(first.get("message") or first))
                return _redact_text(str(first))
    return _redact_text(text.strip())


def _parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        seconds = int(value.strip())
    except ValueError:
        return None  # HTTP-date values are accepted by servers but rare here
    return seconds if seconds > 0 else None


def _opener(proxy: str | None) -> urlrequest.OpenerDirector:
    if proxy:
        handler = urlrequest.ProxyHandler({"http": proxy, "https": proxy})
        return urlrequest.build_opener(handler)
    return urlrequest.build_opener()


def _request_json(
    provider: str,
    url: str,
    payload: dict,
    auth_headers: dict[str, str],
    timeout: int,
    proxy: str | None,
) -> dict:
    """POST JSON and parse a JSON object response; raise policy-classified errors."""
    body = _canonical_json(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        **auth_headers,
    }
    req = urlrequest.Request(url, data=body, headers=headers, method="POST")
    try:
        with _opener(proxy).open(req, timeout=timeout) as response:
            raw = response.read(20 * 1024 * 1024)
    except urlerror.HTTPError as exc:
        detail = _error_message_from_body(exc.read(2048))
        kind, _, _ = _classify_status(exc.code)
        raise ProviderError(provider, kind, _redact_text(detail), exc.code,
                            _parse_retry_after(exc.headers.get("Retry-After"))) from None
    except urlerror.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise ProviderError(provider, "network", _redact_text(str(reason))) from None
    except TimeoutError:
        raise ProviderError(provider, "network", "request timed out") from None
    try:
        parsed = json.loads(raw.decode("utf-8", "replace"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(provider, "protocol", _redact_text(str(exc))) from None
    if not isinstance(parsed, dict):
        raise ProviderError(provider, "protocol", "response is not a JSON object")
    return parsed


def _provider_key(provider: str) -> str | None:
    value = os.environ.get(KEY_ENV[provider])
    return value or None


def _requested_providers(requested: str) -> list[str]:
    if requested != "auto":
        return [requested]
    return [p for p in PROVIDERS if _provider_key(p)]


def _missing_key_error(provider: str) -> ProviderError:
    return ProviderError(provider, "auth", KEY_HELP[provider])


def _retry_delay(exc: ProviderError) -> float:
    if exc.kind == "rate_limit" and exc.retry_after is not None:
        return min(float(exc.retry_after), float(RETRY_AFTER_CAP_SECONDS))
    return float(RETRY_DELAY_SECONDS)


def _retry_allowed(exc: ProviderError) -> bool:
    return exc.kind in ("rate_limit", "server", "network", "protocol")


def _switch_allowed(exc: ProviderError) -> bool:
    return exc.kind != "client"


def _call_with_retry(prog: str, provider: str, func: Callable[[], dict]) -> dict:
    """One in-provider retry for transient classes; auth/quota/client fail fast."""
    for attempt in (1, 2):
        try:
            return func()
        except ProviderError as exc:
            if attempt == 1 and _retry_allowed(exc):
                _notice(prog, f"provider={provider} {exc}; retrying in {_retry_delay(exc):g}s")
                _sleep(_retry_delay(exc))
                continue
            raise


def _published_cutoff(timelimit: str | None) -> str | None:
    if not timelimit:
        return None
    now = datetime.now(timezone.utc) - timedelta(days=_TIME_DAYS[timelimit])
    return now.isoformat(timespec="seconds").replace("+00:00", "Z")


def _search_payload(provider: str, query: str, max_results: int, timelimit: str | None) -> dict:
    if provider == "tavily":
        payload: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        if timelimit:
            payload["time_range"] = _TIME_RANGE[timelimit]
        return payload
    payload = {
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "contents": {"text": True},
    }
    cutoff = _published_cutoff(timelimit)
    if cutoff:
        payload["startPublishedDate"] = cutoff
    return payload


def _auth_headers(provider: str) -> dict[str, str]:
    key = _provider_key(provider)
    if not key:
        raise _missing_key_error(provider)
    if provider == "tavily":
        return {"Authorization": f"Bearer {key}"}
    return {"x-api-key": key}


def _normalize_search(provider: str, payload: dict) -> list[dict]:
    raw = payload.get("results", [])
    if not isinstance(raw, list):
        raise ProviderError(provider, "protocol", "search response 'results' is not a list")
    results: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        href = item.get("url") or item.get("href") or ""
        text = item.get("content") or item.get("text") or item.get("body") or ""
        if href:
            results.append({"title": str(item.get("title") or ""), "href": str(href), "body": str(text)})
    return results


def _search_once(provider: str, args: argparse.Namespace) -> list[dict]:
    headers = _auth_headers(provider)
    endpoint = TAVILY_SEARCH_URL if provider == "tavily" else EXA_SEARCH_URL
    payload = _search_payload(provider, args.query, args.max_results, args.timelimit)
    data = _request_json(provider, endpoint, payload, headers, args.timeout, args.proxy)
    return _normalize_search(provider, data)


def _render_search(results: list[dict], args: argparse.Namespace) -> int:
    if args.urls:
        for result in results:
            print(result.get("href", ""))
        return 0
    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False))
        return 0
    for index, result in enumerate(results, 1):
        print(f"{index}. {result.get('title', '')}")
        print(f"   {result.get('href', '')}")
        print(f"   {result.get('body', '')}")
        if index < len(results):
            print()
    return 0


def web_search_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="api-web-search",
        description="Web search via Tavily/Exa APIs with automatic provider failover.",
    )
    parser.add_argument("query", help="search keywords")
    parser.add_argument("-m", "--max-results", type=int, default=10,
                        help=f"max results, 1-{MAX_SEARCH_RESULTS} (default: 10)")
    parser.add_argument("-t", "--timelimit", choices=("d", "w", "m", "y"),
                        help="publication window: d/w/m/y")
    parser.add_argument("--provider", choices=("auto", *PROVIDERS), default="auto",
                        help="provider pin; auto uses Tavily then Exa (default: auto)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT,
                        help=f"request timeout in seconds (default: {TIMEOUT_DEFAULT})")
    parser.add_argument("--proxy", help="http/https proxy URL (API endpoints; no SOCKS)")
    parser.add_argument("--cache-dir", help="cache directory (default: <skill>/.cache)")
    parser.add_argument("--no-cache", action="store_true", help="bypass search cache read and write")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--format", choices=("text", "json"), default="text",
                        help="output format (default: text)")
    output.add_argument("--urls", action="store_true", help="print result URLs only, one per line")
    args = parser.parse_args(argv)

    if not 1 <= args.max_results <= MAX_SEARCH_RESULTS:
        parser.error(f"--max-results must be between 1 and {MAX_SEARCH_RESULTS}")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.proxy and not args.proxy.startswith(("http://", "https://")):
        parser.error("--provider API requests support http/https proxies only")

    _load_env_file()
    providers = _requested_providers(args.provider)
    if not providers:
        names = " or ".join(KEY_ENV[p] for p in PROVIDERS)
        return _fail(parser.prog, "MissingKeyError",
                     f"no API key found; set {names} or <skill>/.env, or use an available free web-search provider")

    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    failures: list[str] = []
    for provider in providers:
        cache_identity = _canonical_json(
            {"query": args.query, "max": args.max_results, "time": args.timelimit}
        )
        try:
            if not args.no_cache:
                cached = cache_get(cache_dir, "search", provider, cache_identity)
                if cached is not None:
                    results = json.loads(cached.decode("utf-8", "replace"))
                    _notice(parser.prog, f"provider={provider} cache hit")
                    return _render_search(results, args)
            results = _call_with_retry(
                parser.prog, provider,
                lambda p=provider: _search_once(p, args),
            )
        except ProviderError as exc:
            failures.append(f"{provider}: {exc}")
            _notice(parser.prog, f"provider={provider} failed ({exc})")
            if args.provider != "auto" or not _switch_allowed(exc):
                break
            continue
        except Exception as exc:  # keep stdout clean and never leak a traceback
            failures.append(f"{provider}: {type(exc).__name__}: {_redact_text(str(exc))}")
            break

        if not args.no_cache:
            cache_put(cache_dir, "search", provider, cache_identity, "",
                      _canonical_json(results).encode("utf-8"))
        _notice(parser.prog, f"provider={provider}")
        if not results:
            _notice(parser.prog, "no results found.")
        return _render_search(results, args)

    return _fail(parser.prog, "ProviderError", "; ".join(failures) or "all providers failed")


def _fetch_format(api_format: str) -> str:
    return {"text_markdown": "markdown", "text_plain": "text"}[api_format]


def _chunk(urls: list[str], size: int = MAX_FETCH_BATCH) -> list[list[str]]:
    return [urls[i:i + size] for i in range(0, len(urls), size)]


def _fetch_once(provider: str, urls: list[str], args: argparse.Namespace) -> tuple[dict[str, str], list[FetchFailure]]:
    headers = _auth_headers(provider)
    successes: dict[str, str] = {}
    failures: list[FetchFailure] = []
    batches = _chunk(urls)
    for batch in batches:
        if provider == "tavily":
            endpoint, payload = TAVILY_EXTRACT_URL, {"urls": batch, "format": _fetch_format(args.format)}
        else:
            endpoint, payload = EXA_CONTENTS_URL, {"ids": batch, "text": True}
        data = _request_json(provider, endpoint, payload, headers, args.timeout, args.proxy)
        raw_results = data.get("results", [])
        if not isinstance(raw_results, list):
            raise ProviderError(provider, "protocol", "extract response 'results' is not a list")
        found: set[str] = set()
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("id") or ""
            content = item.get("raw_content") if provider == "tavily" else item.get("text")
            if url and content is not None:
                successes[str(url)] = str(content)
                found.add(str(url))
        # Provider-reported per-URL failures (Tavily failed_results; Exa omissions).
        reported: dict[str, str] = {}
        failed = data.get("failed_results", [])
        if isinstance(failed, list):
            for item in failed:
                if isinstance(item, dict):
                    url = str(item.get("url") or item.get("source") or "")
                    reason = str(item.get("error") or item.get("reason") or "provider reported failure")
                    if url:
                        reported[url] = _redact_text(reason)
        for url in batch:
            if url in found:
                continue
            reason = reported.get(url, "provider returned no content")
            failures.append(FetchFailure(provider, url, "fetch_failed", reason))
    return successes, failures


def _emit_fetched(prog: str, url: str, content: str, args: argparse.Namespace, multi: bool) -> None:
    text = content
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
    print(text)


def _valid_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def web_fetch_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="api-web-fetch",
        description="Fetch URL content via Tavily/Exa APIs with per-URL provider failover.",
    )
    parser.add_argument("url", nargs="+", help="http(s) URL(s); duplicates are fetched once")
    parser.add_argument("-f", "--format", choices=("text_markdown", "text_plain"),
                        default="text_markdown", help="content format (default: text_markdown)")
    parser.add_argument("--provider", choices=("auto", *PROVIDERS), default="auto",
                        help="provider pin; auto tries Tavily then Exa for missing URLs")
    parser.add_argument("--max-chars", type=int, default=MAX_CHARS_DEFAULT,
                        help=f"truncate each page to N chars; 0 = no limit (default: {MAX_CHARS_DEFAULT})")
    parser.add_argument("--start", type=int, default=0,
                        help="skip the first N chars; pair with --max-chars for long pages")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT,
                        help=f"request timeout in seconds (default: {TIMEOUT_DEFAULT})")
    parser.add_argument("--proxy", help="http/https proxy URL (API endpoints; no SOCKS)")
    parser.add_argument("--cache-dir", help="cache directory (default: <skill>/.cache)")
    parser.add_argument("--no-cache", action="store_true", help="bypass fetch cache read and write")
    args = parser.parse_args(argv)

    if args.start < 0:
        parser.error("--start must be >= 0")
    if args.max_chars < 0:
        parser.error("--max-chars must be >= 0 (0 = no limit)")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.proxy and not args.proxy.startswith(("http://", "https://")):
        parser.error("--provider API requests support http/https proxies only")
    invalid = [value for value in args.url if not _valid_url(value)]
    if invalid:
        parser.error("URLs must start with http:// or https://")

    _load_env_file()
    providers = _requested_providers(args.provider)
    if not providers:
        names = " or ".join(KEY_ENV[p] for p in PROVIDERS)
        return _fail(parser.prog, "MissingKeyError",
                     f"no API key found; set {names} or <skill>/.env, or use an available free web-search provider")

    urls = list(dict.fromkeys(args.url))
    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    resolved: dict[str, str] = {}
    remaining = list(urls)

    # Cache lookups are provider-specific and never mix Tavily/Exa payloads.
    if not args.no_cache:
        still_missing: list[str] = []
        for url in remaining:
            hit_provider = None
            cached = None
            for provider in providers:
                cached = cache_get(cache_dir, "fetch", provider, url, args.format)
                if cached is not None:
                    hit_provider = provider
                    break
            if hit_provider is not None and cached is not None:
                resolved[url] = cached.decode("utf-8", "replace")
                _notice(parser.prog, f"{url}: provider={hit_provider} cache hit")
            else:
                still_missing.append(url)
        remaining = still_missing

    failures_by_url: dict[str, FetchFailure] = {}
    for index, provider in enumerate(providers):
        if not remaining:
            break
        try:
            successes, reported_failures = _call_with_retry(
                parser.prog, provider,
                lambda p=provider, u=remaining: _fetch_once(p, u, args),
            )
        except ProviderError as exc:
            _notice(parser.prog, f"provider={provider} failed ({exc})")
            for url in remaining:
                failures_by_url[url] = FetchFailure(provider, url, exc.kind, exc.message)
            if args.provider != "auto" or not _switch_allowed(exc) or index + 1 >= len(providers):
                break
            remaining = list(failures_by_url)
            continue
        except Exception as exc:
            message = _redact_text(str(exc))
            _notice(parser.prog, f"provider={provider} failed ({type(exc).__name__}: {message})")
            for url in remaining:
                failures_by_url[url] = FetchFailure(provider, url, "protocol", message)
            break

        for url, content in successes.items():
            resolved[url] = content
            if not args.no_cache:
                cache_put(cache_dir, "fetch", provider, url, args.format, content.encode("utf-8"))
        remaining = [url for url in remaining if url not in successes]
        failures_by_url.update({failure.url: failure for failure in reported_failures})
        if remaining:
            _notice(parser.prog, f"provider={provider}: {len(remaining)} URL(s) missing content")
            if args.provider != "auto" or index + 1 >= len(providers):
                break
        else:
            _notice(parser.prog, f"provider={provider}")

    multi = len(urls) > 1
    for url in urls:
        content = resolved.get(url)
        if content is None:
            continue
        _emit_fetched(parser.prog, url, content, args, multi)

    exit_code = 0
    for url in urls:
        if url in resolved:
            continue
        failure = failures_by_url.get(url)
        detail = f"{failure.kind}: {failure.message}" if failure else "no provider returned content"
        _notice(parser.prog, f"{url}: {detail}")
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    tool = os.path.basename(sys.argv[0]).lower()
    if "fetch" in tool:
        sys.exit(web_fetch_main())
    sys.exit(web_search_main())
