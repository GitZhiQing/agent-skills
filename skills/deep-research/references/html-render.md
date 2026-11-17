# deep-research 可选 HTML 渲染

按需加载：阶段 5 两文件交付后渲染 REPORT.html 时读取本文件。

## 目录

- [1. 调用与成本纪律](#1-调用与成本纪律)
- [2. 主题](#2-主题)
- [3. 质量门](#3-质量门)
- [4. 降级规则](#4-降级规则)
- [5. 模板维护](#5-模板维护)

## 1. 调用与成本纪律

REPORT.md 交付后，**默认自动**跑一条命令产出同目录 `REPORT.html`：

```bash
uv run "<skill_dir>/scripts/render_report.py" "<OUT>/<YYMMDD>-<主题>/REPORT.md"
```

- 可选参数：`--theme default|dark|sepia`（默认 default 跟随系统明暗）、`-o <path>`（默认同目录同名 .html）、`--check-only`（只跑质量门不落盘）。
- stdout 单行 JSON（`ok / html / theme / title / toc_entries / citations / bytes`），诊断走 stderr；退出码 0 成功 / 1 渲染或质量门失败 / 2 用法错误。
- 成功后向用户报告 HTML 绝对路径；不占确认屏轮次，不额外询问。
- 延续交互更新报告后**重渲染**（同一条命令），保证 REPORT.md 与 REPORT.html 不脱节。

**成本纪律（硬约束）**：

- 模型每次只跑这一条命令，**不手写 HTML、不改模板、不逐节设计排版**——视觉全部由预设模板承担。
- 渲染器不联网调研、不启动浏览器、不下载字体；单文件输出，CSS/JS 全内联，零 CDN，离线可打开、可打印。
- 首次运行 uv 自动安装 `markdown-it-py`（轻量纯 Python 包，秒级）；此后命中缓存。
- 渲染失败不是调研失败：按 §4 降级，Markdown 交付不受影响。

## 2. 主题

| 主题 | 效果 |
| --- | --- |
| default | 跟随系统 `prefers-color-scheme` 自动明暗 |
| dark | 强制暗色 |
| sepia | 暖纸色（长时间阅读） |

页面右上角为四段图标开关（自动/浅色/深色/暖纸，选中段浮起 + 主题色，记忆选择）。目录侧栏用虚线主轴 + h2/h3 嵌套虚线呈现层级；当前节高亮由滚动位置实时计算（取最后一个越过阅读线的标题，长段落中间不熄灭）。打印时强制浅色、隐藏侧栏与开关、外链展开 URL。

**配色纪律**：主题色 **#1a88ff**（用户指定）——暗色直接用原值；亮色/打印用同色相加深档 #0b6fd8（#1a88ff 白底约 3.5:1 不达 AA，加深后 ≥4.5:1，保"加强对比度"要求）。除主题色（链接/引用/TOC 高亮/粗体）外，表面/文字/线条/徽章一律中性灰阶；暗色为纯黑灰底（#121212 系），不用蓝调深色背景。正文高对比（#111/白、#f5f5f5/#121212；次级 #525252/#b0b0b0）。改配色只改模板 CSS 变量，不改渲染器。

**排版纪律**：正文 16px / 行高 1.9 / 段距 1.1em（中文长文舒适区）；字体栈 Segoe UI Variable Text → Segoe UI → system-ui → PingFang SC → Microsoft YaHei → Noto Sans CJK SC（系统字体，不下载）；粗体用主题色突出结论；滚动条细轨圆角随主题（Firefox scrollbar-width + WebKit 双套）。

## 3. 质量门

渲染器内置程序化断言，任一不过 exit 1 并 stderr 说明：

1. 模板占位符零残留。
2. 无外部资源引用（`<link href=http` / `<script src=` / 远程 `url()` / `@import`）。
3. 链接定义行不泄漏进正文；无未渲染 markdown 标记（检查前剥离 `<pre>`/`<code>` 内容，避免代码示例中的字面 `**`/`[S#]:` 误报）。
4. 每个上标引用 `[S#]` 都解析为链接且来源表有对应锚点行；缺定义的引用（如 `[S99]`）直接报错；同一 S# 在多个表首列重复 → 报错（附录合并形状错误）。
5. HTML 标签闭合（void 标签除外）。

另：标题取 h1，**不自动加章号**（保护附录 A 反向索引的 §x.x 引用）；**页脚仅一行免责声明**（指向附录 A / B），不重复附录 B 已有的日期/模型/平台/工具组合等元信息——附录已在报告内，页脚再列一遍是冗余。旧版（0.12.x）报告同样正常渲染。

## 4. 降级规则

以下任一情况，**如实说明并跳过 HTML**，Markdown 交付照常完成，不阻塞、不重试纠缠：

- 宿主无 uv（或 uv 首次装包失败 / 无网络）；
- 渲染器 exit 1（质量门未过）或 exit 2（用法错误）；
- 模板文件缺失（skill 目录不完整）。

措辞示例："HTML 渲染跳过（原因：…）；Markdown 已交付，可用 VS Code / Obsidian 阅读。" 不伪造 HTML 产出，不手写 HTML 兜底。

## 5. 模板维护

- 模板：`assets/report.template.html`（占位符 `__TITLE__` / `__THEME_ATTR__` / `__TOC_ITEMS__` / `__CONTENT__`）。
- 视觉变更只改模板与渲染器，**不改报告 Markdown 规范**；改完跑 `uv run --with markdown-it-py python -m unittest discover -s skills/deep-research/tests` 回归（canary 样张覆盖全部受控语法）。
- 报告 Markdown 侧的引用形态（上标参考式链接 + 来源表 + 定义区）与附录形状见 `references/delivery-template.md` §2.1 / §3，渲染器依赖该受控格式。