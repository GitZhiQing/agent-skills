"""下载排版运行时资源：Noto Serif/Sans SC 静态字重切片 + Paged.js + KaTeX。

用法：uv run python -m md2pdf.fetch_assets  （或 uv run md2pdf fetch）
- 字体：fontsource 静态包（可变字体会被 Chromium 打印降级为 Type3，DECISIONS D10）；
  清单从各档字重 CSS 解析（单一事实源），strip woff1 fallback；
  serif 400/700 + sans 400/600/700，合并生成 assets/fonts/noto-{serif,sans}-sc.css。
- KaTeX：css + js + auto-render（公式浏览器端渲染）。
- 已存在且非空的文件自动跳过。
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import urllib.request

SKILL_ROOT = Path(__file__).resolve().parents[2]
FONTS = SKILL_ROOT / "assets/fonts"
FILES = FONTS / "files"
SPEC = {
    "noto-serif-sc": ("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.3.1", [400, 700]),
    "noto-sans-sc": ("https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5.3.1", [400, 600, 700]),
}
PAGEDJS = "https://cdn.jsdelivr.net/npm/pagedjs@0.4.3/dist/paged.polyfill.js"
KATEX = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist"
UA = {"User-Agent": "Mozilla/5.0"}
WOFF1 = re.compile(r",\s*url\(\./files/[^)]*\.woff\)\s*format\('woff'\)")


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch(job: tuple[str, Path]) -> None:
    url, dest = job
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.write_bytes(get(url))


def main() -> int:
    FILES.mkdir(parents=True, exist_ok=True)
    katex_dir = SKILL_ROOT / "assets/katex"
    katex_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, Path]] = [
        (PAGEDJS, SKILL_ROOT / "assets/paged.polyfill.js"),
        (f"{KATEX}/katex.min.css", katex_dir / "katex.min.css"),
        (f"{KATEX}/katex.min.js", katex_dir / "katex.min.js"),
        (f"{KATEX}/contrib/auto-render.min.js", katex_dir / "auto-render.min.js"),
    ]
    # KaTeX 字体（css 引用 fonts/*.woff2）
    (katex_dir / "fonts").mkdir(parents=True, exist_ok=True)
    for name in re.findall(r"url\(fonts/([^)]+\.woff2)\)", get(f"{KATEX}/katex.min.css").decode("utf-8")):
        jobs.append((f"{KATEX}/fonts/{name}", katex_dir / "fonts" / name))

    for pkg, (base, weights) in SPEC.items():
        merged = []
        for w in weights:
            css = get(f"{base}/{w}.css").decode("utf-8")
            css = WOFF1.sub("", css).replace("url(./files/", "url(files/")
            merged.append(css)
            for name in sorted(set(re.findall(r"url\(files/([^)]+\.woff2)\)", css))):
                jobs.append((f"{base}/files/{name}", FILES / name))
        (FONTS / f"{pkg}.css").write_text("\n".join(merged), encoding="utf-8")

    ok = fail = 0
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(fetch, j): j for j in jobs}
        for fut in as_completed(futs):
            try:
                fut.result()
                ok += 1
            except Exception as e:
                fail += 1
                errors.append(f"{futs[fut][0]} -> {e}")
    print(f"ok={ok} fail={fail} total={len(jobs)} -> {SKILL_ROOT / 'assets'}")
    for e in errors[:10]:
        print(e)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
