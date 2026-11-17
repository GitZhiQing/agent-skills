# deep-research

先校准、再消耗调研资源的深度调研 skill：环境确认与研究计划两屏经用户确认后自主执行。产出两文件——**REPORT.md**（正文 + 附录 A 来源与证据 + 附录 B 调研元信息）+ **REPORT.html**（可选渲染），落盘于所选输出根目录下的 `<YYMMDD>-<主题>/`。需要研究源码时文档优先，确需代码行为验证才把仓库 clone 到该目录的 `sources/` 并固定 commit SHA，再基于本地源码分析给出文件:行号证据。

## 何时触发

- 触发词："帮我调研""深入研究""全面了解""对比分析""查清楚…的现状""research" "deep research"等；
- 或问题术语有歧义、领域冷门、表述模糊时主动使用；
- 不触发：一次搜索可答的单点查询、只需阅读已给出的代码片段或单点调试、用户明确要求不联网且不涉及源码分析。
- 不适用：无人值守 / 批量自动化调研——两屏确认必须由用户回应，无人确认就不执行。
- 前置条件：用户能在场的交互会话；宿主声明自主执行时先验证提问工具，无法确认即停止，不降级执行。

## 工作方式

固定两屏确认：

1. **环境确认屏（第 1 轮，先于一切联网）**：只读探测后呈现标准模型 ID（去供应商前缀）、Agent 平台、web_search/web_fetch（内置优先）、提问工具可用性、git；用户确认或纠正，纠正值优先。
2. **校准与计划确认屏（第 2 轮）**：歧义/冷门/模糊时先 ≤3 次判向预检索；呈现调研目标（候选方向+推荐）+ TODO 计划 + 投入预估 + 输出目录候选。确认→执行；调整/换方向→重建计划直接执行（无第三屏）；取消/无回应→停。

确认后按 TODO 自主执行（宿主任务清单工具优先），投入按复杂度自判（无档位问题）；广度型独立子主题可选并行子代理调研（宿主支持时），否则单线程；报告写作永远主代理一次性。仅重大矛盾/范围变化/需新源码快照/工具失败改变可行性时回用户。执行期增量登记 LEDGER.md，交付时并入附录后删除。

- 交付闸门：附录 B 确认来源为"未确认"时，不创建/交付输出目录、LEDGER.md 与 REPORT.md。
- 报告可读性：摘要为带引用的结论清单（BLUF，只读摘要也能拿走核心结论）；外部来源用上标参考式链接 `<sup>[S#]</sup>`（文末附录 A 分层来源表 + 隐藏定义区，报告自包含）；段落短、结论前置、单源/推断显式标记；交付前过可读性自查。
- 完整协议见 [SKILL.md](SKILL.md)。
- 环境探测细则见 [references/environment.md](references/environment.md)；执行纪律与源码六步见 [references/execution-discipline.md](references/execution-discipline.md)；并行协议见 [references/parallel-research.md](references/parallel-research.md)。
- 报告与附录、LEDGER 模板见 [references/delivery-template.md](references/delivery-template.md)。

## 源码调研

- **识别（docs-first）**：优先文档；实现原理 / 架构 / 调用链 / 行为溯源 / 源码对比，或答案必须靠代码行为验证时才 clone；无档位范围限制。
- **获取与固定**：确认后 clone 到 `<OUT>/<YYMMDD>-<主题>/sources/<repo>/`，记录完整 commit SHA；已有本地仓库 HEAD 与所需 ref 一致才原地复用。
- **本地分析**：只读，不执行仓库内安装 / 构建 / 测试脚本；代码结论用 `[C#:path:line]` 引用，报告中渲染为固定 SHA 永久链接（点开即落在分析版本的对应行），区分源码实证 / 文档说明 / 推断。

## 输出目录

阶段 0 只读探测工作区，第 2 屏给出 2~3 个输出根目录候选并标推荐项；确认采用推荐（点选推荐项或回复「确认」），选择编号 / 自定义路径即改选。推荐规则：

- 已有 `research/` → 沿用；
- 代码仓且无 `research/` → 优先仓外目录（如 `~/research/` 或工作区同级 `research/`），避免调研产物污染代码库；
- 文档 / 笔记仓 → 仓内 `research/` 或 `docs/research/`；
- 无法判断 → 工作区 `research/`。

最终调研目录为 `<OUT>/<YYMMDD>-<主题>/`；输出目录在确认前不创建，确认后不再变更（用户中途改需求除外）。

## 目录命名

`<OUT>/<YYMMDD>-<主题>/`（如 `<OUT>/261018-国产开源数据库格局/`）：`YYMMDD` 取创建当天（跨日不改名）；主题 slug 简短可读，中文关键词可用；同日同主题重复调研追加 `-2`、`-3`；报告内日期用 `YYYY-MM-DD`。

## 环境前提与可选协作

- **环境前提**：宿主具备 web 搜索 / 抓取能力——原生 WebSearch / WebFetch 类工具，或任一已安装的 web 搜索 / 抓取 skill。阶段 0 探测模型 / 平台 / 工具 / 提问工具 / 任务清单 / 子代理 / git。
- **可选 HTML 渲染**：REPORT.md 交付后默认渲染同目录 REPORT.html（预设精美模板：TOC 侧栏、明暗主题、来源徽章、可打印；单文件离线零 CDN；页脚元信息来自附录 B）。需 uv >= 0.5，首次自动装一个轻量包；uv 缺失或渲染失败自动跳过，不影响 Markdown 交付。用法见 [references/html-render.md](references/html-render.md)。
- **可选并行**：宿主有子代理类工具且子主题独立时并行调研，否则单线程；写作永远单代理。
- **可选协作**：具体用哪个搜索工具由阶段 0 探测决定，本 skill 不绑定实现；无论选用哪种通道，都按 SKILL.md 内联纪律执行（调用间隔 ≥2 秒、限流退避重试、同 URL 不重复抓取）。
- **源码调研**：另需 git；无 git 时可退回官方源码包。web 工具缺失但 git 可用时，可降级为仅本地源码调研并声明未做外部资料交叉验证。

## 安装

把这句交给你的 Agent（它会自己安装并验证）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 deep-research skill：优先 `npx skills add "GitZhiQing/agent-skills/deep-research"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh deep-research`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

直接用命令行安装：

```bash
npx skills add GitZhiQing/agent-skills/deep-research
```

```text
/plugin marketplace add GitZhiQing/agent-skills
/plugin install deep-research@agent-skills
```

手动分发与卸载见[仓库 README](../../README.md#安装)。

核心路径纯提示词、无运行时依赖；可选 HTML 渲染需 uv，缺失自动跳过。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源，含两屏模板与投入启发式）
- [references/environment.md](references/environment.md) — 模型/平台/工具探测与文本编号降级
- [references/execution-discipline.md](references/execution-discipline.md) — 执行节奏、增量登记、源码六步、安全
- [references/parallel-research.md](references/parallel-research.md) — 可选并行子代理协议
- [references/delivery-template.md](references/delivery-template.md) — REPORT 结构、引用、附录 A/B 与 LEDGER 模板
- [references/html-render.md](references/html-render.md) — HTML 渲染调用、主题、质量门与降级
- [docs/SPEC.md](docs/SPEC.md) — 设计与决策依据
- [docs/TESTS.md](docs/TESTS.md) — 验证场景

许可：MIT（[LICENSE](LICENSE)）。