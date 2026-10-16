---
created: 2026-10-16
updated: 2026-10-16
---

# md2pdf — Markdown 精美 PDF Skill 设计规范

> 实现位置：本 skill 目录（源码即安装目录，经仓库 `scripts/skills-link.sh` junction 分发到各 agent）。
> 2026-10-16 自笔记仓库迁入 agent-skills 仓库（实现源 `.agents/skills/md2pdf/` + 设计文档 `ai/项目/md2pdf/docs/`），旧位置冻结保留不再演进（DECISIONS D15）；本文件随迁移改存于 `docs/SPEC.md`。

一句话定位：把 Markdown 一键转成排版精良的 PDF——两段式渲染（build 出中间 HTML/CSS，print 出 PDF），Agent 能在中间产物上定点修改、闭环迭代；双布局（article 纯正文 / report 报告骨架）× 主题预设（四套）开箱即用，三层调参接口支持按需定制。

## 问题

Markdown 笔记在交付、归档、汇报时需要精美 PDF，现有工具留了三个缺口：多数管线是一段式渲染，Agent 无法介入迭代，只能反复猜参数；中文排版与成体系的设计语言支持弱；主题定制上限低。本 skill 为 Agent 而设计：CLI 幂等、错误信息可自纠、中间产物可读可改。

## 走通路径

用户对 Agent 说「把 xx.md 转成 PDF」→ Agent 运行 `uv run md2pdf build xx.md --layout report --theme kimi`（在输出目录生成中间 HTML+CSS）→（可选：Agent 读改中间产物）→ `uv run md2pdf print`（Playwright + Paged.js 渲染出 PDF）。

MVP 交付判据：一篇含代码块、表格、公式的真实中文笔记，用任选布局与主题一键产出 PDF（report 版含封面、目录、页眉页脚页码），全程离线，且新会话 Agent 仅凭 SKILL.md 能独立完成一次转换。

## 布局与主题（两维正交）

**布局**：
- `article` 纯正文版——无封面、无目录、无页眉、无页脚、无页码，文档题头起排、连续文档流，是「内容本体」的干净转换；
- `report` 报告版——封面整页 + 目录（淡点线 + 真页码回填）+ 页眉页脚页码，正文同为连续文档流。

两布局正文均不强制章节整页分隔，章节靠 hairline + 大间距区分；章首（标题 + 小节标题 + 首段）以 `.keep-head` + `break-inside: avoid` 保护避免孤悬。

**主题预设**（色值全部取自真实调研，色相只作用于标题/三线/hairline/编号点缀，正文统一近黑墨）：

| 预设 | 主色 / 次色 / 底色 | 来源 |
|---|---|---|
| kimi（默认） | `#002F5B` / `#007CFF` / 白 | Kimi 官方品牌手册 |
| deepseek | `#4D6BFE` / `#1A1615` / 白 | DeepSeek 官网设计系统 |
| gemini | `#4285F4` / `#34A853` / 白 | Google 官方四主色 |
| anthropic | `#1A1A1A` / `#CC785C` / `#F4F3EE` | Anthropic 官网色板 |

涨跌红绿语义色（`#B5483C` / `#2E7D5B`）独立于主题固定不随动；代码高亮 = 品牌色关键字 + 灰阶字符串/注释。

## 技术栈（已定）

- uv + Python（≥3.11）；markdown-it-py + mdit-py-plugins 解析；Pygments 代码高亮；KaTeX（本地 JS 文件）公式
- Jinja2 渲染 HTML 骨架；Paged.js 分页（页眉页脚、页码、目录回填都在页面 DOM 内生成，不依赖浏览器打印参数）
- 打印引擎统一为 Playwright：优先 `channel="msedge"` 复用系统 Edge（零额外下载），无可复用浏览器时下载自带 Chromium 兜底；打印前显式等待 Paged.js 分页完成与字体就绪（系统浏览器 headless CLI 方案因打印时序无法与页面握手而废弃，见 DECISIONS D1）
- 字体：正文思源宋体（Noto Serif SC 400/700，回退宋体），辅助元素（表格/页眉页脚/标注）思源黑体（Noto Sans SC 400/600/700，回退微软雅黑），代码中文注释由 mono 栈内 Noto Sans SC 兜底；数字一律 `font-variant-numeric: tabular-nums`；静态字重切片（可变字体会被 Chromium 打印降级为 Type3，见 DECISIONS D10）本地化，清单从各档 CSS 解析（单一事实源），首次由获取脚本下载
- 程序化质量门 check.py：打印后自动断言（无空白页/无孤悬标题/段末孤字告警/字体集须含 Noto 禁 Type3 与系统 CJK 回退/目录页码对齐），FAIL 即止不进视觉验收；金丝雀样张 canary.html 覆盖全部版式元素，管线改动先过金丝雀再动真实文档
- frontmatter 约定：`title / subtitle / date` 进封面与文档题头；主题与布局由 CLI 参数选择

## 两段式与三层调整（核心设计）

```
md → build → 中间 HTML + CSS（落盘，可读可改）→ print → check（程序断言）→ PDF
```

打印全程本地静态资源（字体切片 + Paged.js 内嵌），打印前有字体就绪断言（防静默回落系统字体）、打印后有 check 质量门（DECISIONS D9/D11）；有浏览器工具的 Agent 会话，推荐工作流是先打开 build 产物目检版式、定点修改、再 print——这条写进 SKILL.md。

调参分三层，SKILL.md 里向 Agent 明确这三级用法：

1. CLI 参数（`--layout / --theme / --page / --accent` 等）——覆盖八成常见需求；
2. override.css 覆盖 CSS 变量——主题全用自定义属性书写，换肤不动主题本体；
3. 直接编辑中间 HTML/CSS 后重 print——自由度上限。

## 工作流（用户拍板 2026-10-16）

- **来源三种**：本地路径；远程 URL（md/txt/raw 直链，以及网页 URL——HTML 经 trafilatura 抽正文转 md，失败时回退让用户贴内容）；会话内容（Agent 落盘为 md 后同本地路径）。
- **Human-in-the-loop**：`preview` 子命令对文档出各主题对比图——上行为标准元素样张（标题/表格/涨跌色/代码，保证主题差异可见）、下行为该文档真实首页（所见即所得），横排拼接一张 PNG；Agent 展示给用户选主题，选后 `convert`。
- **任务文件夹产物**（一次转换一个文件夹，config + source 在手可完全复现）：
  ```
  <文档名>-YYMMDD-HHMM/
    source.md            # 原始文档存档（复制/下载/会话生成）
    config.yaml          # 来源、主题、版式、页面参数、时间、内核版本
    preview.png          # 预览对比图（若走过预览流）
    pdf/<文档名>-报告版.pdf
    pdf/<文档名>-正文版.pdf
  ```
- **主题是数据文件**：`themes/<name>.css`（CSS 变量组），新增预设零代码，preview/convert 自动发现。

## 切片

1. ~~双布局×四主题样张原型~~（已完成，v0.3 全部视觉验收通过，DECISIONS D1-D11）。
2. **正式转换管线**（原切片 2+3 合并重写，2026-10-16 与用户对齐）：`uv run md2pdf` CLI 落地于 `.agents/skills/md2pdf/`——markdown-it-py 解析（Pygments 高亮、KaTeX 浏览器端渲染）、模板化（base.css + themes/*.css + Jinja2 布局模板，版式在模板层物化而非事后删节点）、print/check 平移、URL 三种来源（trafilatura 网页转 md）、任务文件夹 + config.yaml；验证：金丝雀 + demo + 真实报告全部经新 CLI 产出且 check 全绿。
3. **预览选择流**：preview 子命令（标准样张 + 文档首页双行 × 全主题 → 拼接 PNG）；验证：Agent 模拟用户走完「预览→选择→转换」全流程。
4. **三层调整 API + SKILL.md**：CLI 参数（--theme/--layout/--page/--accent/--out）全覆盖 CSS 变量；override.css 机制；SKILL.md 写明预览选择流与调参指南。
5. **skill 化交付**：SKILL.md 定稿、仓库级登记（迁移后由 agent-skills 仓库的 README Skills 表 / marketplace.json / skills-link 分发替代原 skills-lock.json 机制）、示例任务文件夹；验证：新会话 Agent 仅凭 SKILL.md 独立完成一次「URL → 预览 → 选择 → 双版式 PDF」全流程。

## 非目标

- 不做 Typst/LaTeX 引擎分支（留接口位，MVP 后按需再议）；
- 不做 mermaid 与数据图表渲染——Agent 先行用 mermaid-cli / matplotlib 生成图片，在 md 里引用；
- 不做 GUI、Web 界面、监听服务；不做批量守护进程（批量转换由 Agent 循环单文件实现）；
- 不做 Word / LaTeX 输入输出；
- MVP 只验证 Windows 环境。
