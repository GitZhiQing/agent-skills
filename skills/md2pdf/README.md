# md2pdf

把 Markdown 转成排版精良的 PDF：双版式（报告版 = 封面 + 目录 + 页眉页脚；正文版 = 纯内容）× 四主题（kimi / deepseek / gemini / anthropic，色值来自 AI 头部厂商品牌调研），Playwright + Paged.js 渲染，打印前后双重质量断言。面向 Agent 使用，转换前可用 `preview` 出四主题对比图供人选择。

## 何时使用

- 用户说「转 PDF」「导出报告」「出一版 PDF」「把这个文档排个版」「生成精美 PDF」；
- 要把本地 Markdown、远程 md/txt 直链、普通网页（自动抽正文）或会话内容排版成 PDF；
- 指定了 kimi / deepseek / gemini / anthropic 主题，或要求报告版 / 正文版。

不触发 / 不适用：

- 只要 Markdown 转纯文本、要 LaTeX/学术论文排版，或输入是已有 PDF / Word 只想改内容；
- 要求 GUI、批量监听、mermaid / 数据图表渲染，或通过 CLI 直接指定页面尺寸 / 强调色（当前未实现，见「边界」）。

## 工作方式

1. `preview` 生成四主题对比图（上行标准样张、下行文档首页），供用户选主题；
2. `convert` 两段式执行：Markdown → 中间 HTML/CSS（落盘可改）→ 打印 PDF → 质量门断言（空白页 / 孤悬标题 / 字体集 / 目录页码）；
3. 每次转换产出独立任务文件夹：`source.md` + `config.yaml` + `build-*.html` + `pdf/` 双版式；改中间 HTML 后可单独重打印。

来源支持本地路径、md/txt/raw 直链、网页 URL（trafilatura 抽正文）与会话内容（先落盘为 md）。完整流程与排版约定见 [SKILL.md](SKILL.md)。

## 安装

把这句交给你的 Agent（只装 md2pdf）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 md2pdf skill：优先 `npx skills add "GitZhiQing/agent-skills/md2pdf"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh md2pdf`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

安装后可用 `uv run --project <skill_dir> md2pdf <子命令>` 调用（`<skill_dir>` 为本 skill 目录，命令不依赖当前工作目录）；Git Bash 下 `bash "<skill_dir>/bin/md2pdf" <子命令>` 等价，Windows cmd/PowerShell 用 `bin\md2pdf.cmd`。

## 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.5（Python >= 3.11，依赖首次调用自动安装）；
- 打印优先复用系统 Edge（Playwright `channel="msedge"`，零浏览器下载）；未安装 Edge 时回退 Playwright Chromium，需已安装（可用 `uv run --project <skill_dir> playwright install chromium`）；
- 首次使用需联网执行一次 `fetch`（字体切片 + Paged.js + KaTeX，约 15MB），此后转换可离线；
- 当前只在 Windows 验证；Linux / macOS 未验证。

## 使用示例

```bash
# 首次：下载运行资源
uv run --project "<skill_dir>" md2pdf fetch

# 预览：四主题对比图 → 用户选主题
uv run --project "<skill_dir>" md2pdf preview doc.md -o preview.png

# 转换：任务文件夹含 source.md + config.yaml + pdf/双版式
uv run --project "<skill_dir>" md2pdf convert doc.md --theme kimi --out ./out

# 只出正文版
uv run --project "<skill_dir>" md2pdf convert doc.md --theme anthropic --layout article --out ./out

# 对已有 PDF 独立跑质量门
uv run --project "<skill_dir>" md2pdf check out.pdf
```

## 边界

- 只接受 Markdown / 远程文本 / 网页抽正文 / 会话落盘内容；不做 Word、LaTeX 或 PDF 输入输出；
- CLI 支持 `--theme`、`--layout report|article|both`、`--out`；`--page` / `--accent` 等页面与强调色参数未实现，需改 `templates/base.css`、`themes/<name>.css` 或任务文件夹内的 `build-*.html`；
- 全文唯一 `# h1` 视为文档标题（进封面/题头，不进正文），`##` 升格为章节；自带「一、」等编号的章节不叠加自动章号；
- 单美元 `$` 公式与货币符号可能误判，必要时转义 `\$`；
- 不做 GUI、监听服务、批量守护进程与 mermaid / 数据图表渲染。

## 文档

- [SKILL.md](SKILL.md) — Agent 入口：调用方式、标准工作流、排版约定
- [docs/SPEC.md](docs/SPEC.md) — 设计规范、布局主题、技术栈与变更记录
- [docs/DECISIONS.md](docs/DECISIONS.md) — 关键决策记录
- [docs/TESTS.md](docs/TESTS.md) — 行为协议回归与轻量自动化测试、触发校准
- [LICENSE](LICENSE) — 本 skill 的 MIT 许可全文

## 第三方资源与许可

`fetch` 在运行时下载到 `assets/`（已 gitignore，不随仓库分发），来源均为 jsDelivr：

| 资源 | 版本 | 许可 |
| --- | --- | --- |
| Noto Serif SC / Noto Sans SC（fontsource 静态字重切片） | 5.3.1 | SIL OFL 1.1 |
| Paged.js | 0.4.3 | MIT |
| KaTeX（含字体） | 0.16.11 | MIT |

主题 CSS 与模板为本仓库原创，随本目录 [LICENSE](LICENSE) 以 MIT 发布。
