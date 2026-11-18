# find-my-xp 可选 HTML 渲染

按需加载：阶段 9 交付 Markdown 后，用户要 HTML 时读取本文件。

## 目录

- [1. 调用与成本纪律](#1-调用与成本纪律)
- [2. 视觉：私密档案风](#2-视觉私密档案风)
- [3. 质量门](#3-质量门)
- [4. 降级规则](#4-降级规则)
- [5. 模板维护](#5-模板维护)

## 1. 调用与成本纪律

Markdown 交付后，**用户要 HTML 时**跑一条命令（默认不自动渲染，尊重私密性）：

```bash
# 单份
uv run "<skill_dir>/scripts/render_report.py" "<OUT>/XP-原型-<代号>.md"
# 多份合成一份档案（元地图 + 全部原型）
uv run "<skill_dir>/scripts/render_report.py" "<OUT>/XP-元地图.md" "<OUT>/XP-原型-A.md" "<OUT>/XP-原型-B.md" -o "<OUT>/XP-档案.html"
```

- 参数：`-o <path>`（单份默认同目录同名 `.html`；多份默认首文件目录下 `XP-档案.html`）、`--check-only`（只跑质量门不落盘）。
- stdout 单行 JSON（`ok / html / title / files / toc_entries / bytes / check_only`），诊断走 stderr；退出码 0 成功 / 1 渲染或质量门失败 / 2 用法错误。
- 成功后向用户报告 HTML 绝对路径。

**成本纪律（硬约束）**：

- 模型每次只跑这一条命令，**不手写 HTML、不改模板、不逐节设计排版**——视觉全部由预设模板承担。
- 渲染器不联网、不启动浏览器、不下载字体；单文件输出，CSS 全内联，零 CDN，离线可打开、可打印。
- 首次运行 uv 自动装 `markdown-it-py`（纯 Python，秒级）；此后命中缓存。
- 渲染失败不是访谈失败：按 §4 降级，Markdown 交付不受影响。
- 延续交互更新报告后**重渲染**（同一条命令），保证 Markdown 与 HTML 不脱节。

## 2. 视觉：私密档案风

- **暗色暖灰底**（#1a1816 系），暖白正文（#ece6dd），克制黄铜点缀（#c9a86a）；不用蓝调深色、不用粉嫩玄学装饰。
- **衬线标题**（Noto Serif SC / Songti SC / Source Han Serif / Georgia 回退）+ **等宽标签**（Cascadia Code / JetBrains Mono / Consolas + CJK 黑体回退）；系统字体不下载。
- 页头档案标记："XP 画像档案 · 私密 · 仅供本人阅读"。
- **用户原话**（blockquote）渲染为原话卡片（左侧黄铜竖线 + 暖灰底）。
- **置信度徽章**：`（置信：高/中/低）` 渲染为分级徽章（高=黄铜、中=暖灰、低=虚线）。
- 多份合成时左侧档案导航（文件 → 节），当前节高亮；移动端折叠。
- 打印强制浅色、隐藏导航、原话卡片保留竖线。
- 改配色只改模板 CSS 变量，不改渲染器。

## 3. 质量门

渲染器内置程序化断言，任一不过 exit 1 并 stderr 说明：

1. 模板占位符零残留（`__TITLE__` / `__NAV_ITEMS__` / `__CONTENT__`）。
2. 无外部资源引用（`<link href=http` / `<script src=` / 远程 `url()` / `@import`）。
3. 无未渲染 markdown 标记（检查前剥离 `<pre>`/`<code>`，避免代码示例误报）。
4. HTML 标签闭合（void 标签除外）。

标题取 h1，不自动加章号；多份合成时每份 h1 作为档案分节标题。

## 4. 降级规则

以下任一情况，**如实说明并跳过 HTML**，Markdown 交付照常完成，不阻塞、不重试纠缠：

- 宿主无 uv（或 uv 首次装包失败 / 无网络）；
- 渲染器 exit 1（质量门未过）或 exit 2（用法错误）；
- 模板文件缺失（skill 目录不完整）。

措辞示例："HTML 渲染跳过（原因：…）；Markdown 已交付，可用 VS Code / Obsidian 阅读。" 不伪造 HTML 产出，不手写 HTML 兜底。

## 5. 模板维护

- 模板：`assets/report.template.html`（占位符 `__TITLE__` / `__NAV_ITEMS__` / `__CONTENT__`）。
- 视觉变更只改模板与渲染器，**不改报告 Markdown 规范**（见 `report-template.md`）；改完跑 `uv run --with markdown-it-py python -m unittest discover -s skills/find-my-xp/tests` 回归。
- 报告 Markdown 侧的受控格式（h1/h2/h3、blockquote 原话、置信度徽章、表格、XP 链箭头）见 `report-template.md`，渲染器依赖该格式。