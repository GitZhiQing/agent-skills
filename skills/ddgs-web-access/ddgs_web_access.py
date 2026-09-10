"""ddgs-web-access: minimal web search & web fetch CLI for AI coding agents.

Two entry points (see pyproject.toml [project.scripts]):
  ddgs-web-search  -> web_search_main()
  ddgs-web-fetch   -> web_fetch_main()

Contract (see docs/需求与设计文档.md):
  - stdout: results only — compact plain text blocks, or JSON with --format json
  - stderr: errors and notices, one line each
  - exit codes: 0 success (empty results included), 1 runtime error, 2 usage error

Stability (mirrors the "one call just works" feel of native web tools):
  - search retries once after a transient error; empty results stay exit 0
  - fetch falls back to the system curl when ddgs extract fails (except 404/410)
  - --start paginates long pages alongside --max-chars
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import markdownify
from bs4 import BeautifulSoup
from ddgs import DDGS
from ddgs.exceptions import DDGSException, TimeoutException

# Windows pipes may use a legacy codepage; force UTF-8 so non-ASCII results
# survive both TTY and piped (agent) output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Truncation default follows the MCP fetch server (5000 chars) so models can
# read long pages in chunks; 0 disables it. The fetch cache mirrors the
# 15-minute window of the harness WebFetch tool.
MAX_CHARS_DEFAULT = 5000
CACHE_TTL_SECONDS = 15 * 60

# Patient defaults: 5s cut off slow-but-alive engines/sites, while the native
# WebSearch/WebFetch tools tolerate similar latencies without failing.
TIMEOUT_DEFAULT = 10
# One automatic retry after a transient search error, honoring the ddgs
# >=2s inter-request discipline.
RETRY_DELAY_SECONDS = 2

# --curl mode: some sites block the impersonated client or reject non-200
# handling; the system curl fallback sends a regular browser UA.
CURL_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_CHARSET_RE = re.compile(rb'charset\s*=\s*["\']?([\w-]+)', re.IGNORECASE)


class CurlError(Exception):
    """Raised when the system curl fallback fails."""


def resolve_proxy(cli_proxy: str | None) -> str | None:
    """Order: --proxy > DDGS_PROXY > HTTPS_PROXY > HTTP_PROXY.

    ddgs only reads DDGS_PROXY itself, so translate the common proxy env
    vars here; the ddgs "tb" alias (Tor) is expanded for the curl path too.
    """
    proxy = cli_proxy or next(
        (os.environ[n] for n in ("DDGS_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")
         if os.environ.get(n)),
        None,
    )
    if proxy == "tb":
        return "socks5h://127.0.0.1:9150"
    return proxy


def default_cache_dir() -> Path:
    """Cache lives under the project root; DDGS_WEB_ACCESS_CACHE overrides it."""
    env = os.environ.get("DDGS_WEB_ACCESS_CACHE")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    if (here / "pyproject.toml").exists():  # project root (editable install)
        return here / ".cache"
    return Path.cwd() / ".cache"


def _cache_key(mode: str, url: str, fmt: str) -> str:
    # mode in the key so ddgs-extract and curl results never mix.
    return hashlib.sha256(f"{mode}\x00{fmt}\x00{url}".encode("utf-8")).hexdigest()


def cache_get(cache_dir: Path, mode: str, url: str, fmt: str) -> bytes | None:
    """Return the cached payload if fresh, else None. Best-effort, never raises."""
    try:
        path = cache_dir / (_cache_key(mode, url, fmt) + ".bin")
        if path.stat().st_mtime + CACHE_TTL_SECONDS < time.time():
            return None
        return path.read_bytes()
    except OSError:
        return None


def cache_put(cache_dir: Path, mode: str, url: str, fmt: str, data: bytes) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / (_cache_key(mode, url, fmt) + ".bin")).write_bytes(data)
    except OSError:
        pass  # the cache is best-effort; never break the fetch


def _fail(prog: str, exc_type: str, message: str) -> int:
    print(f"{prog}: {exc_type}: {message}", file=sys.stderr)
    return 1


def _retrying(prog: str, exc: Exception) -> None:
    """Announce the single automatic retry after a transient search error."""
    print(f"{prog}: {type(exc).__name__}: {exc}; retrying in {RETRY_DELAY_SECONDS}s", file=sys.stderr)
    time.sleep(RETRY_DELAY_SECONDS)


def _is_dead_page(exc: Exception) -> bool:
    """True for 404/410 — the page is gone and the curl fallback cannot help."""
    message = str(exc)
    return "HTTP 404" in message or "HTTP 410" in message


def _print_no_results(prog: str) -> int:
    print(f"{prog}: no results found. (repeated empties may mean rate limiting — "
          f"wait 10-30s before retrying)", file=sys.stderr)
    return 0


def web_search_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ddgs-web-search",
        description="Web search via ddgs multi-engine metasearch (DuckDuckGo, Bing, Brave, ...).",
    )
    parser.add_argument("query", help="search keywords")
    parser.add_argument("-r", "--region", default="us-en",
                        help="region code, e.g. us-en, uk-en, ru-ru, wt-wt (default: us-en)")
    parser.add_argument("-s", "--safesearch", default="moderate", choices=("on", "moderate", "off"))
    parser.add_argument("-t", "--timelimit", choices=("d", "w", "m", "y"),
                        help="time filter: d/w/m/y (day/week/month/year)")
    parser.add_argument("-m", "--max-results", type=int, default=10,
                        help="max results, 1-50 (default: 10)")
    parser.add_argument("-b", "--backend", default="auto",
                        help="engine(s): auto, bing, brave, duckduckgo, wikipedia, ... (default: auto)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT,
                        help=f"request timeout in seconds (default: {TIMEOUT_DEFAULT})")
    parser.add_argument("--proxy", help="http/https/socks5 proxy URL (overrides env)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--format", choices=("text", "json"), default="text",
                        help="output format (default: text)")
    output.add_argument("--urls", action="store_true",
                        help="print bare result URLs, one per line")
    args = parser.parse_args(argv)

    if not 1 <= args.max_results <= 50:
        parser.error("--max-results must be between 1 and 50")

    ddgs = DDGS(proxy=resolve_proxy(args.proxy), timeout=args.timeout)
    results: list[dict] | None = None
    for attempt in (1, 2):  # one automatic retry on transient errors
        try:
            results = ddgs.text(
                args.query,
                region=args.region,
                safesearch=args.safesearch,
                timelimit=args.timelimit,
                max_results=args.max_results,
                backend=args.backend,
            )
            break
        except DDGSException as exc:
            if "No results found." in str(exc):
                return _print_no_results(parser.prog)
            if attempt == 1:
                _retrying(parser.prog, exc)
                continue
            return _fail(parser.prog, type(exc).__name__, str(exc))
        except Exception as exc:  # keep the exit-code contract stable whatever ddgs throws
            if attempt == 1:
                _retrying(parser.prog, exc)
                continue
            return _fail(parser.prog, type(exc).__name__, str(exc))

    if not results:
        return _print_no_results(parser.prog)

    if args.urls:
        for result in results:
            print(result.get("href", ""))
        return 0

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False))
        return 0

    for i, result in enumerate(results, 1):
        print(f"{i}. {result.get('title', '')}")
        print(f"   {result.get('href', '')}")
        print(f"   {result.get('body', '')}")
        if i < len(results):
            print()
    return 0


# Boilerplate tags removed before conversion (both markdownify and bs4 paths):
# forms/iframes/svg/noscript are noise for readers, and nav/header/footer/
# aside are the usual site-chrome offenders (same heuristic as readability).
_CURL_STRIP_TAGS = ("script", "style", "noscript", "form", "iframe", "svg",
                    "nav", "header", "footer", "aside")
# class/id hints for boilerplate blocks that use divs instead of semantic
# tags, e.g. Sphinx breadcrumbs (<div class="related">), site headers/footers.
_CURL_STRIP_HINTS = ("breadcrumb", "related", "navbar", "main-menu", "sidebar",
                     "cookie", "consent", "advert", "share", "pagination",
                     "site-footer", "site-header", "page-footer")


def _drop_boilerplate(soup: BeautifulSoup) -> None:
    for tag in soup(list(_CURL_STRIP_TAGS)):
        tag.decompose()
    for el in soup.find_all(True):
        attrs = el.attrs
        if not attrs:  # doctype nodes have attrs=None; valueless tags have {}
            continue
        markup = f"{attrs.get('id', '')} {' '.join(attrs.get('class', []))}".lower()
        if any(hint in markup for hint in _CURL_STRIP_HINTS):
            el.decompose()


def _markdown_text(raw: bytes) -> str:
    """HTML -> Markdown via markdownify, with boilerplate removed first.

    markdownify's `strip` option keeps tag text, so unsightly blocks are
    decomposed via BeautifulSoup before conversion; script/style content is
    dropped by markdownify itself.
    """
    soup = BeautifulSoup(_decode_html(raw), "html.parser")
    _drop_boilerplate(soup)
    return markdownify.markdownify(str(soup), heading_style="ATX", bullets="-")


def _plain_text(raw: bytes) -> str:
    """HTML -> plain text via BeautifulSoup (text with block-level line breaks)."""
    soup = BeautifulSoup(_decode_html(raw), "html.parser")
    _drop_boilerplate(soup)
    for tag in soup(["head"]):
        tag.decompose()
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in soup.get_text("\n").splitlines()]
    out: list[str] = []
    blank = 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip() + "\n"


def _decode_html(raw: bytes) -> str:
    """Decode page bytes using its declared charset, else utf-8/gbk/latin-1."""
    match = _CHARSET_RE.search(raw[:4096])
    if match:
        try:
            return raw.decode(match.group(1).decode("ascii", "replace"), errors="replace")
        except LookupError:
            pass
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _curl_fetch(url: str, timeout: int, proxy: str | None) -> bytes:
    """Fetch raw bytes with the system curl; -f maps non-2xx to a nonzero exit."""
    curl = shutil.which("curl")
    if not curl:
        raise CurlError("curl not found on PATH (Windows 10+ ships curl.exe; macOS/Linux bundle it)")
    cmd = [curl, "-sS", "-f", "-L", "--compressed", "--max-time", str(timeout),
           "-A", CURL_USER_AGENT]
    if proxy:
        cmd += ["-x", proxy]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        # curl prefixes its own exit message with "curl: (NN) "; drop it.
        detail = proc.stderr.decode("utf-8", "replace").strip()
        detail = re.sub(r"^curl: \(\d+\) ", "", detail)
        raise CurlError(f"exit {proc.returncode}: {detail or 'unknown error'}")
    return proc.stdout


def _curl_content(raw: bytes, fmt: str) -> str | bytes:
    if fmt == "content":
        return raw
    if fmt == "text":
        return _decode_html(raw)
    return _plain_text(raw) if fmt == "text_plain" else _markdown_text(raw)


def _emit(prog: str, url: str, content: object, args: argparse.Namespace, multi: bool) -> None:
    """Write one fetched page to stdout; pagination/truncation notices go to stderr."""
    if args.format == "content":
        fd, path = tempfile.mkstemp(prefix="ddgs-fetch-", suffix=".bin")
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        print(path)
        return
    text = content if isinstance(content, str) else content.decode("utf-8", "replace")
    start = args.start
    if start >= len(text):
        if start:
            print(f"{prog}: {url}: start {start} is beyond end of content ({len(text)} chars)",
                  file=sys.stderr)
        text = ""
    else:
        text = text[start:]
        if args.max_chars and len(text) > args.max_chars:
            text = text[: args.max_chars]
            print(f"{prog}: {url}: truncated at {args.max_chars} chars "
                  f"(continue with --start {start + args.max_chars})", file=sys.stderr)
    if multi:
        print(f"===== {url} =====")
    print(text)


def web_fetch_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ddgs-web-fetch",
        description="Fetch URL(s) and print their content (ddgs extract, automatic curl fallback).",
    )
    parser.add_argument("url", nargs="+", help="target URL(s); multiple URLs are fetched in one run")
    parser.add_argument("-f", "--format", default="text_markdown",
                        choices=("text_markdown", "text_plain", "text_rich", "text", "content"),
                        help="content format (default: text_markdown); 'content' writes raw bytes to a file")
    parser.add_argument("--max-chars", type=int, default=MAX_CHARS_DEFAULT,
                        help=f"truncate text output to N chars; 0 = no limit (default: {MAX_CHARS_DEFAULT})")
    parser.add_argument("--start", type=int, default=0,
                        help="skip the first N chars; pair with --max-chars to read long pages in chunks")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT,
                        help=f"request timeout in seconds (default: {TIMEOUT_DEFAULT})")
    parser.add_argument("--proxy", help="http/https/socks5 proxy URL (overrides env)")
    parser.add_argument("--cache-dir", help="fetch cache directory (default: <project>/.cache)")
    parser.add_argument("--no-cache", action="store_true", help="bypass the fetch cache")
    parser.add_argument("--curl", action="store_true",
                        help="force the system curl fetcher, skipping ddgs extract entirely")
    args = parser.parse_args(argv)

    if args.start < 0:
        parser.error("--start must be >= 0")
    if args.max_chars < 0:
        parser.error("--max-chars must be >= 0 (0 = no limit)")

    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    proxy = resolve_proxy(args.proxy)
    ddgs = DDGS(proxy=proxy, timeout=args.timeout)
    multi = len(args.url) > 1
    exit_code = 0
    for url in args.url:
        store_mode = "curl" if args.curl else "ddgs"
        if not args.no_cache:
            cached = cache_get(cache_dir, store_mode, url, args.format)
            if cached is None and store_mode == "ddgs":
                # a previous run may have succeeded via the curl fallback
                cached = cache_get(cache_dir, "curl", url, args.format)
                if cached is not None:
                    store_mode = "curl"
            if cached is not None:
                print(f"{parser.prog}: {url}: cache hit", file=sys.stderr)
                _emit(parser.prog, url, cached, args, multi)
                continue
        try:
            if args.curl:
                content = _curl_content(_curl_fetch(url, args.timeout, proxy), args.format)
            else:
                try:
                    content = ddgs.extract(url, fmt=args.format).get("content")
                except Exception as exc:
                    if _is_dead_page(exc):
                        raise  # curl would report the same 404/410
                    print(f"{parser.prog}: {url}: {type(exc).__name__}: {exc}; retrying with curl",
                          file=sys.stderr)
                    store_mode = "curl"
                    content = _curl_content(_curl_fetch(url, args.timeout, proxy), args.format)
        except TimeoutException as exc:
            print(f"{parser.prog}: {url}: TimeoutException: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        except CurlError as exc:
            print(f"{parser.prog}: {url}: curl: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        except DDGSException as exc:
            print(f"{parser.prog}: {url}: DDGSException: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        except Exception as exc:
            print(f"{parser.prog}: {url}: {type(exc).__name__}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8", "replace")
        if not args.no_cache:
            cache_put(cache_dir, store_mode, url, args.format, raw)
        _emit(parser.prog, url, content, args, multi)
    return exit_code


if __name__ == "__main__":
    # Fallback when the console scripts are unavailable, e.g.
    # `uv run --project . python ddgs_web_access.py ...`.
    tool = os.path.basename(sys.argv[0]).lower()
    if "fetch" in tool:
        sys.exit(web_fetch_main())
    sys.exit(web_search_main())
