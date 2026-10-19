# AGENTS.md — skills

个人 AI coding agent skills 集合：每个 skill 位于 `skills/` 子目录下，一个 skill 一个目录，通过 junction/软链分发到各 agent 的 skills 目录（目标 = 内置主流清单 ⊕ `agents.local.conf` 本地自定义，目录存在才生效，清单见 `docs/开发与维护规范.md` §6）。

维护标准见 `docs/开发与维护规范.md`（目录结构、frontmatter、版本规则、台账格式、分发与回归流程、Git 提交信息规范见 §10）；执行细则见 `docs/维护脚本测试集.md`。

## 怎么跑起来 / 验证

- 纯提示词 skill（theme-commit、deep-research、zero-coding、session-handoff）：无运行时，直接读 SKILL.md。
- ddgs-web-access 需要 uv >= 0.5，命令不依赖当前工作目录：

```bash
bash skills/ddgs-web-access/bin/ddgs-web-search "smoke test" -m 1
bash skills/ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

- md2pdf 需要 uv >= 0.5 与系统 Edge（Playwright 复用打印，零浏览器下载），首次使用先联网 fetch 一次（字体切片 + Paged.js + KaTeX，~15MB）：

```bash
bash skills/md2pdf/bin/md2pdf --help    # CLI 可用性冒烟（依赖由 uv 首次自动安装）
bash skills/md2pdf/bin/md2pdf fetch     # 首次：下载运行资源
```

- 仓库级维护脚本（纯 bash，零依赖）：

```bash
bash scripts/skills-lint.sh           # 结构/元数据校验：全绿 exit 0
bash scripts/skills-doctor.sh         # 链接健康矩阵
bash scripts/skills-link.sh --all     # 分发（幂等）
```

- 改动 ddgs-web-access 代码后按 `skills/ddgs-web-access/docs/测试集.md` 回归；搜索/抓取调用间隔 ≥2 秒（ddgs 多引擎聚合，过频会限流）。
- 改动 video-insight 代码后按 `skills/video-insight/docs/测试集.md` 回归：`python -m unittest discover -s skills/video-insight/tests`（163 条，含合成视频、无口播文字卡与 pipeline 幂等/组装器/批量/事件锚点并入、分段三模式与 SRT 渲染测试，纯标准库无第三方依赖；真实托管 API 用例需 `VOLC_BIGMODEL_API_KEY` / `PADDLEOCR_ACCESS_TOKEN`，未设置自动跳过）。
- 改动 md2pdf 代码后按 `skills/md2pdf/docs/测试集.md` 回归（核心基线 S-3：canary 双版式转换质量门全绿；fetch/preview/convert 需网络与 Edge）。
- 等价形式：`uv run --project skills/ddgs-web-access <命令>`；Windows 用 `bin/*.cmd`。

## 技术栈

- ddgs-web-access：Python >= 3.10（uv 托管虚拟环境），依赖 ddgs + markdownify，单文件 CLI（`ddgs_web_access.py`）+ `bin/` 位置无关启动器；stdout 结果 / stderr 提示与错误 / 退出码 0-1-2。
- theme-commit：纯 SKILL.md 提示词（git 按主题分组提交），0.1.1。
- deep-research：纯 SKILL.md 提示词（先校准再调研：环境检查（含工作区/输出目录探测）→ 预检索校准 → 选项式澄清 → 调研目标与计划确认门（低/中/高档位，含输出目录候选+推荐与源码获取计划）→ 增量登记落盘所选输出目录下 `<YYMMDD>-<主题>/` → REPORT.md + REFERENCES.md 双文件交付；源码调研先 clone 到 sources/ 并固定 commit SHA，再基于本地源码分析、用 [C#:path:line] 引用），0.5.0。
- zero-coding：纯 SKILL.md 提示词（从零启动个人项目：按会话容量分路——小活一轮对齐直接做，立项走 SPEC 范围契约 + 垂直切片；最小文档集 SPEC/DECISIONS/AGENTS 三个，事实自查、决策问人、说不清的做一次性原型，方案确认尽量委托平台 Plan Mode 与子 Agent，收尾对照走通路径收敛核验后删 SPEC），0.4.0。
- video-insight：拉片级视频分析（L1 文案档 / L2 画面档，开工确认门——交互模式分级判定 + doctor 前置单轮确认 + 确认/调整/显式委托三回应 + L2 拼版检查点，实测/约/推断三档表述；pipeline.py 一键机械采集：幂等推进 + no_speech 自动切无口播分支（帧差逐屏 + 读图/OCR 回退，ocr 路径组装器自动成稿，screen_srt.py 机械渲染 SRT）+ 收尾 branch/stats/ai_next 报告；多视频批量（--batch 清单、批内 slug 去重、失败隔离、批报告落盘、可选 --jobs 并发）；工具层能力开关（screen_segments --mode 三态/统计事实字段/events_in_segment 锚点、grab_frames --range 扫窗、--include-event-anchors）+ memory 经验闭环（失败先检索、收尾写回三问、used≥3 毕业进代码/文档），模型专注确认门、读图、内容分析与重分段决策），Python 脚本纯标准库，外部依赖 ffmpeg/ffprobe（B站下载另需 yt-dlp），转写内置火山 Seed ASR 托管 API 客户端（VOLC_BIGMODEL_API_KEY，env/.env 双通道），OCR 回退可选（PADDLEOCR_ACCESS_TOKEN 接官方托管 API，纯标准库直连），0.7.0。
- session-handoff：纯 SKILL.md 提示词（会话收尾把接手所需上下文打包成一段可粘贴的交接提示词：7 节骨架 + AGENTS.md 未覆盖项条件补充，项目基本面不重复搬运；只输出一个待粘贴代码块，一般 400–1200 字），0.1.0。
- md2pdf：Markdown → 排版精良 PDF（双版式 report/article × 四主题 kimi/deepseek/gemini/anthropic，色值取自 AI 厂商品牌调研；Playwright 复用系统 Edge 打印 + Paged.js 分页 + KaTeX 公式；preview 四主题对比图选主题的 Human-in-the-loop 流；任务文件夹 source.md + config.yaml + pdf/双版式可复现，convert 内置质量门断言空白页/孤悬标题/字体集/目录页码；来源支持本地/远程直链/网页 trafilatura 抽正文/会话内容落盘），uv 托管 Python 包（src 布局）+ `bin/` 位置无关启动器，首次使用需 fetch 下载字体与运行资源（~15MB），0.1.0。
- scripts/：bash + coreutils 维护脚本套件，公共函数在 `scripts/lib.sh`；退出码统一 0-1-2，状态走 stdout、错误走 stderr。

## 目录与约定

- 一个 skill 一个目录，SKILL.md 为入口；frontmatter 需含 `name`（== 目录名）、三段式 `description`、`metadata.version`（semver）；版本权威来源是 frontmatter，pyproject.toml 与本地台账跟随同步，lint 强制；README Skills 表不展示版本号。
- 公开 skill 目录以 README Skills 表为准；维护者个人的台账、分发状态与下一步计划记录在 `SKILLS.local.md`（gitignore `*.local.md`，不入库）。
- 每个 skill 带 README.md（面向人的目录导览：定位、触发、工作方式、安装；lint 强制存在，不写版本号）；复杂 skill 另带 docs/（设计文档、测试集）；测试集编号用「类别前缀-序号」。
- 分发与卸载统一用 `bash scripts/skills-link.sh` / `skills-unlink.sh`（`[--agent <name|name=path>]...` 可限定或临时指定目标；在内置清单 ∪ `agents.local.conf` 的目录建/删指向本仓库的 junction，单一来源）；ddgs-web-access 自带的 `scripts/install.sh` 仅供该 skill 独立拷走时使用。链接变更后跑 `skills-doctor.sh` 并回填本地台账（SKILLS.local.md）"分发状态"列；Agent 代装提示见 `docs/开发与维护规范.md` §6.4。
- 内置目标清单（15 个主流 agent 全局位）的权威实现是 `scripts/lib.sh` 的 `builtin_agent_targets()`，与 ddgs-web-access 独立安装脚本同步维护。
- 运行产物（`.venv/`、`.cache/`、`__pycache__/`、`*.egg-info/`）已 gitignore，不纳入版本管理，lint 会检查。
- `.zcode/`（会话计划产物）在根 .gitignore 中排除。
