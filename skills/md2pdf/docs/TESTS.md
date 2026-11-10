# md2pdf 测试集

| 文档版本 | v0.1.3 | 日期 | 2026-11-11 | 适用版本 | md2pdf 0.1.3 |
| --- | --- | --- | --- | --- | --- |

行为协议断言人工会话执行；代码层另有轻量自动化单测（§0）。
编号采用「类别前缀-序号」（S 冒烟 / P 协议 / F 功能），新场景追加不重排。

前置条件：uv >= 0.5、联网；打印优先复用系统 Edge，未安装时需已准备 Playwright Chromium；
`<skill_dir>` 为本 skill 目录（仓库内 `skills/md2pdf/` 或经 junction 分发后的任意 agent skills 目录，
命令不依赖当前工作目录）。首次执行前先完成 S-2（fetch 下载运行资源）。

## 0. 轻量自动化测试（不联网 / 不渲染）

▶ `uv run --project <skill_dir> python -m unittest discover -s "<skill_dir>/tests" -v`

- = 5 条用例全部通过（`OK`），耗时约 0.1s；不渲染 PDF、不联网、不下载资源
- = 覆盖：`--help` 可解析；fetch / preview / convert / check 四个子命令存在；convert 在读取来源前拒绝未知主题且不产生任务文件夹；config.yaml 的 `engine` 字段取自包内 `__version__`（动态替换版本后仍生效）
- = 无 uv 时：`PYTHONPATH="<skill_dir>/src" python -m unittest discover -s "<skill_dir>/tests"`（依赖需已安装）

## 1. 冒烟（S）

### S-1 CLI 可用性

场景：环境就绪（uv 已装），未做任何转换。

▶ `bash "<skill_dir>/bin/md2pdf" --help`

- = 退出码 0，stdout 列出 fetch / preview / convert / check 四个子命令

### S-2 资源获取

场景：`assets/` 二进制资源不存在（新机器 / 新位置首次使用）。

▶ `bash "<skill_dir>/bin/md2pdf" fetch`

- = 退出码 0，`assets/` 下生成字体切片、paged.polyfill.js、katex/
- = 重复执行不报错（幂等，已就绪资源跳过）

### S-3 金丝雀转换全绿（核心回归）

场景：资源已 fetch。任何管线 / 模板 / 主题改动后必须先过本用例（DECISIONS D11/D13）。

▶ `bash "<skill_dir>/bin/md2pdf" convert "<skill_dir>/examples/canary.md" --theme kimi --out <临时目录>/`

- = 退出码 0，任务文件夹含 source.md、config.yaml、pdf/ 下双版式 PDF
- = 质量门无 FAIL 输出（空白页 / 孤悬标题 / 字体集 / 目录页码四类断言全过）
- = 报告版含封面 + 目录 + 页眉页脚页码；正文版无封面无页码
- = config.yaml 记录 source / theme / layouts / engine（engine 版本与包内 `__version__` 一致）

### S-4 预览图生成

场景：资源已 fetch。

▶ `bash "<skill_dir>/bin/md2pdf" preview "<skill_dir>/examples/canary.md" -o <临时目录>/preview.png`

- = 生成 PNG：四主题横排、上下两行（上行标准样张、下行该文档节选）
- = stdout 提示把图展示给用户选主题，并列出可用主题

## 2. 协议（P）

### P-1 正向触发 + Human-in-the-loop

场景：用户说「把这个 md 转成 PDF」，未指定主题（交互模式）。

▶ Agent 先跑 `preview` 并把对比图展示给用户

- = 用户选主题前不执行 convert
- = 会话无图输出能力时，改以文字列出四主题色值与观感供选择，仍需用户拍板

### P-2 主题已定直接转换

场景：用户明确「用 anthropic 主题出 PDF」。

▶ Agent 直接 `convert --theme anthropic`，跳过 preview

- = 不额外追问主题

### P-3 反向不触发

场景：用户只要 md 转纯文本、或要求 LaTeX/学术论文排版、或已有排版好的 PDF/Word 只想改内容。

- = 不调用本 skill（纯文本用读取命令；LaTeX 走相应排版工具链）

### P-4 会话内容来源

场景：用户把文档内容贴在对话里要出 PDF。

▶ Agent 先落盘为 md（frontmatter 可写 title/subtitle/date/abstract/kicker/brand），再走本地路径 convert

- = 任务文件夹内 source.md 即落盘内容，config.yaml 可复现

## 3. 功能（F）

### F-1 远程 md 直链（需网络）

场景：来源为 https 直链的 md/txt 文档。

▶ `convert https://.../doc.md --theme kimi --out <目录>/`

- = 下载并转换成功，config.yaml 的 source 记为 `url-text: <url>`

### F-2 网页 URL 抽正文（需网络）

场景：来源为普通网页 URL。

▶ `convert https://example.com/post --out <目录>/`

- = trafilatura 抽正文转 md 后正常转换
- = 抽取失败时明确报错提示改贴内容，不静默产出空/半空文档

### F-3 未知主题拒绝

场景：`--theme` 传入不存在的主题名。

▶ `convert doc.md --theme nosuch`

- = 报错并列出可用主题，退出码非 0，不产出任务文件夹半成品

### F-4 单版式参数

场景：只要正文版。

▶ `convert doc.md --layout article --out <目录>/`

- = 任务文件夹 pdf/ 下只有正文版 PDF，config.yaml layouts 仅记 article

### F-5 check 独立子命令

场景：对任一历史产物 PDF 独立跑质量门。

▶ `bash "<skill_dir>/bin/md2pdf" check <pdf路径>`

- = 全绿时退出码 0 且无输出；有 FAIL 时列出并退出码 1

## 附录 A. 触发校准（静态评审）

日期：2026-11-11；适用版本：md2pdf 0.1.3。
方式：按 [SKILL.md](../SKILL.md) 的 description 三段式与近邻 skill 边界逐条**静态评审**，不新开会话、不统计触发率；结果为评审预期，后续 description 变更时再按仓库规范做会话级复测。

### A.1 应触发（8 条，静态判定 8/8）

| # | 用户说法 | 判定依据 |
| --- | --- | --- |
| 1 | 把这个 md 转成 PDF | 正向触发词「转 PDF」+ 本地 md 来源 |
| 2 | 帮我导出报告，用 deepseek 主题 | 「导出报告」+ 指定主题，直接 convert |
| 3 | 出一版 PDF，排得好看点 | 「出一版 PDF」+ 排版诉求 |
| 4 | 这份 Markdown 排个版 | 「排个版」+ Markdown 来源 |
| 5 | 生成一份精美 PDF | description 中的「精美 PDF」 |
| 6 | 把这篇文章 https://… 转成 PDF | 远程网页 URL 来源属明确适用场景 |
| 7 | 把这次会话的内容整理成 PDF | 会话内容落盘后转换，属来源三态之一 |
| 8 | 用 anthropic 主题出一版报告 PDF | 主题名 + 「报告 PDF」，直接 convert |

### A.2 近邻不触发（8 条，静态判定 8/8）

| # | 用户说法 | 判定依据 |
| --- | --- | --- |
| 1 | 把这个 PDF 转成 Markdown | 反向格式转换，不是 md → PDF |
| 2 | 把这个 Word 文档转成 PDF | 输入为 Word；本 skill 只接受 Markdown / URL / 会话内容 |
| 3 | 帮我把它转成纯文本 | 纯文本转换，description 明确不触发 |
| 4 | 用 LaTeX 排一篇学术论文 | 要求 LaTeX 排版，走对应工具链 |
| 5 | 读出这个 PDF 里的文字 | PDF 内容读取，无排版输出 |
| 6 | 给这个 md 文件加个目录 | Markdown 内容编辑，不产出 PDF |
| 7 | 把网页保存成 HTML | 网页存档，不是 PDF 排版 |
| 8 | 把这张图片转成 PDF | 图片转 PDF，无 Markdown 来源与排版流程 |

结论：8 条应触发均命中 description 的正向场景与来源三态；8 条近邻反例均落在反向不触发或能力边界外，未发现需要改写的歧义。本次为静态评审，不替代会话级触发率统计。
