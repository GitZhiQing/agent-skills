---
name: md2pdf
description: >-
  把 Markdown 转成排版精良的 PDF：双版式（报告版=封面+目录+页眉页脚；正文版=纯内容）× 多主题（kimi/deepseek/gemini/anthropic，色值来自 AI 头部厂商真实调研），Playwright+Paged.js 渲染，打印前后双重质量断言。
  当用户说「转 PDF」「导出报告」「出一版 PDF」「把这个文档排个版」，或要把本地 md、远程 URL（含网页转 md）、会话内容排版成 PDF 时使用；触发词包括「转 PDF」「导出报告」「出一版 PDF」「排个版」「精美 PDF」等。
  当用户只要纯文本转换、已有排版好的 PDF/Word 无需重排、或要求 LaTeX/学术论文排版时，不要使用本 skill。
license: MIT
compatibility: 需要 uv >= 0.5、Python >= 3.11 与系统 Edge（Playwright channel=msedge 打印，零浏览器下载）；首次使用需联网 fetch 一次下载字体切片 + Paged.js + KaTeX（~15MB）；网页来源经 trafilatura 抽正文
allowed-tools: Bash(uv run *) Bash(bash *bin/md2pdf *)
metadata:
  version: 0.1.2
  category: document
---

# md2pdf：Markdown → 精美 PDF

通用转换内核 + 主题预设，Agent 优先、Human-in-the-loop（转换前用户选主题）。

## 调用方法

标准形式（`<skill_dir>` 为本 skill 目录；命令不依赖当前工作目录，经 junction 分发后同样可用）：

```bash
bash "<skill_dir>/bin/md2pdf" <子命令> [参数]
```

等价形式：`uv run --project "<skill_dir>" md2pdf <子命令> [参数]`；Windows cmd/PowerShell 用 `bin\md2pdf.cmd`。

## 标准工作流（三步）

```bash
# ① 预览：四主题对比图（上行标准样张、下行该文档内容节选）
bash "<skill_dir>/bin/md2pdf" preview <source.md|URL> -o <task>/preview.png
```

把 preview.png 展示给用户选主题（左→右顺序见命令输出）。用户已指定主题时跳过此步。

```bash
# ② 转换：产出任务文件夹（默认 kimi 主题、双版式）
bash "<skill_dir>/bin/md2pdf" convert <source> --theme <选定的主题> --out <task>/

# ③ 结果在任务文件夹（source.md + config.yaml + pdf/报告版&正文版）
```

convert 内置质量门（空白页/孤悬标题/字体集/目录页码断言），FAIL 会报错列出——按提示修复后重跑；PASS 无输出即通过。

## 来源三态

- 本地路径：`convert notes.md`
- 远程直链：`convert https://.../doc.md`（md/txt/raw 文本）
- 网页 URL：`convert https://example.com/post`（trafilatura 抽正文转 md；抽取失败会提示改贴内容）
- 会话内容：先把内容落盘为 md（frontmatter 可写 title/subtitle/date/abstract/kicker/brand），再走本地路径

## 主题

kimi（默认，深蓝+亮蓝）· deepseek（电光蓝）· gemini（蓝绿双色）· anthropic（墨色+陶土+暖纸底）。
新增主题：在 `themes/` 加一个 css 文件（三行变量：--brand/--brand-2/--paper），preview/convert 自动发现，零代码。

## 精细调整（三层）

1. CLI 参数：`--theme` / `--layout report|article|both` / `--out`
2. 改 `templates/base.css` 的变量或主题文件色值
3. 直接改任务文件夹里的 `build-*.html` 后手动打印：
   `uv run --project "<skill_dir>" python -m md2pdf.printer <build-xx.html> <out.pdf>`

## 首次使用 / 环境缺资源

```bash
bash "<skill_dir>/bin/md2pdf" fetch    # 下载字体切片 + Paged.js + KaTeX（~15MB，一次即可）
```

打印用系统 Edge（Playwright channel="msedge"，零浏览器下载）；打印前有字体就绪断言，字体未就绪会拒绝打印（防静默回落系统字体）。

## 排版约定（写文档时可直接用）

- 语义色：`<span class="pos">+5.2%</span>` 涨/红、`<span class="neg">−3.1%</span>` 跌/绿
- 公式：`$行内$` / `$$独立$$`（KaTeX 渲染）
- 表格直接用 md 表格；代码块标语言（Pygments 高亮，关键字用主题色）
- frontmatter：title/subtitle/date/abstract/kicker/brand/brand-en/org

## 已知边界

- 全文唯一 `# h1` 视为文档标题（进封面/题头，不进正文），`##` 升格为章节；自带「一、」等编号的章节不叠加自动章号
- 布局变体在模板层物化（非 CSS 显隐）——Paged.js 的 display:none 分页冲突教训（DECISIONS D2）
- 单美元 `$` 公式与货币符号可能误判，必要时转义 `\$`

## 参考文档

- [docs/SPEC.md](docs/SPEC.md) — 设计规范
- [docs/DECISIONS.md](docs/DECISIONS.md) — 决策记录
- [docs/TESTS.md](docs/TESTS.md) — 行为协议回归用例
- [README.md](README.md) — 安装、用法、排障与第三方资源许可
