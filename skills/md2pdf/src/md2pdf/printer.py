"""Playwright 打印：字体断言 → KaTeX/Paged.js 分页等待 → page.pdf。

- 优先 channel="msedge" 复用系统 Edge，回落自带 Chromium（DECISIONS D1）
- 打印前断言字体真正可用（防静默回落系统字体）
- 等待：fonts loaded → KaTeX 渲染稳定 → .pagedjs_pages 页数稳定 600ms
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--allow-file-access-from-files"]

CHECK_FONTS = """
() => {
  const bad = [];
  document.fonts.forEach(f => { if (f.status === 'error') bad.push(f.family); });
  const serifOk = document.fonts.check('12pt "Noto Serif SC"', '汉字测试');
  const sansOk  = document.fonts.check('12pt "Noto Sans SC"', '汉字测试');
  return { errorFaces: [...new Set(bad)], serifOk, sansOk };
}
"""

WAIT_PAGED = """
() => new Promise(resolve => {
  const find = () => document.querySelector('.pagedjs_pages');
  const poll = setInterval(() => {
    const cur = find();
    if (!cur) return;
    clearInterval(poll);
    let n = cur.children.length, t0 = performance.now();
    const timer = setInterval(() => {
      const c = find().children.length;
      if (c === n && performance.now() - t0 > 600) { clearInterval(timer); resolve(true); }
      else if (c !== n) { n = c; t0 = performance.now(); }
    }, 200);
  }, 100);
})
"""


def print_pdf(html: Path, out: Path) -> str:
    """打印并返回所用引擎名；字体未就绪抛 SystemExit。"""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", args=ARGS)
            engine = "msedge(channel)"
        except Exception:
            browser = p.chromium.launch(args=ARGS)
            engine = "chromium(bundled)"
        page = browser.new_page()
        page.goto(html.resolve().as_uri(), wait_until="load")
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=60000)
        font_check = page.evaluate(CHECK_FONTS)
        if font_check["errorFaces"] or not (font_check["serifOk"] and font_check["sansOk"]):
            browser.close()
            raise SystemExit(f"字体未就绪，拒绝打印（防静默回落系统字体）：{font_check}")
        page.wait_for_function(WAIT_PAGED, timeout=90000)
        page.pdf(
            path=str(out),
            prefer_css_page_size=True,
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()
    print(f"[print] engine={engine} {out.name} ({out.stat().st_size / 1024:.0f} KB)")
    return engine


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pdf")
    print_pdf(src, dst)
