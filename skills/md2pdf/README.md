# md2pdf skill

Markdown → 排版精良的 PDF：双版式（报告版 = 封面 + 目录 + 页眉页脚；正文版 = 纯内容）× 四主题（kimi / deepseek / gemini / anthropic，色值来自 AI 头部厂商品牌调研），Playwright + Paged.js 渲染，打印前后双重质量断言。Agent 优先、Human-in-the-loop——转换前 `preview` 出四主题对比图供用户选。

设计规范与决策记录见 [docs/SPEC.md](docs/SPEC.md)、[docs/DECISIONS.md](docs/DECISIONS.md)；行为协议回归用例见 [docs/TESTS.md](docs/TESTS.md)。

## 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.5（Python >= 3.11，依赖首次调用自动安装）
- 系统装有 Edge：打印引擎 Playwright 复用系统 Edge（`channel="msedge"`），零浏览器下载
- 首次使用需联网执行一次 `fetch`（下载字体切片 + Paged.js + KaTeX，约 15MB）；此后全程离线

## 安装

把这句交给你的 Agent（它会自己安装并验证）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 md2pdf skill：优先 `npx skills add "GitZhiQing/agent-skills/md2pdf"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh md2pdf`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

直接用命令行安装：

```bash
npx skills add GitZhiQing/agent-skills/md2pdf
```

```text
/plugin marketplace add GitZhiQing/agent-skills
/plugin install md2pdf@agent-skills
```

手动分发与卸载见[仓库 README](../../README.md#安装)。

运行时需要 `uv`（首次运行自动拉取渲染依赖）；单独拷贝该目录时无需安装，`uv run --project <目录> md2pdf <子命令>` 即用。

## 用法

`<skill_dir>` 为本 skill 目录（命令不依赖当前工作目录）：

```bash
bash "<skill_dir>/bin/md2pdf" fetch                                # 首次：下载运行资源
bash "<skill_dir>/bin/md2pdf" preview doc.md -o prev.png           # 四主题对比图 → 用户选主题
bash "<skill_dir>/bin/md2pdf" convert doc.md --theme kimi --out ./ # 任务文件夹：source.md + config.yaml + pdf/双版式
bash "<skill_dir>/bin/md2pdf" check out.pdf                        # 独立跑质量门断言
```

来源支持本地路径 / 远程 md·txt 直链 / 网页 URL（trafilatura 抽正文）/ 会话内容（先落盘为 md）；Windows cmd/PowerShell 用 `bin\md2pdf.cmd`。完整工作流与排版约定见 [SKILL.md](SKILL.md)。

## 排障

- **打印报字体未就绪 / 拒绝打印**：先跑一次 `fetch`，确认 `assets/fonts/` 已下载（打印前有字体断言，防静默回落系统字体）。
- **找不到 Edge**：安装系统 Edge；无 Edge 时 Playwright 会尝试下载自带 Chromium 兜底。
- **网页 URL 抽取失败**：trafilatura 对部分动态页无效，改为把内容贴给 Agent 落盘成 md 再转换。
- **convert 报 check FAIL**：按错误列表（空白页 / 孤悬标题 / 字体集 / 目录页码）修复文档或样式后重跑。

## 第三方资源与许可

`fetch` 在运行时下载到 `assets/`（已 gitignore，不随仓库分发），来源均为 jsDelivr：

| 资源 | 版本 | 许可 |
| --- | --- | --- |
| Noto Serif SC / Noto Sans SC（fontsource 静态字重切片） | 5.3.1 | SIL OFL 1.1 |
| Paged.js | 0.4.3 | MIT |
| KaTeX（含字体） | 0.16.11 | MIT |

主题 CSS 与模板为本仓库原创，随根 [LICENSE](../../LICENSE) 以 MIT 发布。
