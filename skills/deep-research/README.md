# deep-research

先校准、再消耗调研资源的深度调研 skill：开始检索前，调研目标、调研计划与输出目录必须经用户确认。产出双文件——**REPORT.md**（调研报告，结论层）+ **REFERENCES.md**（素材登记簿，证据层），落盘于所选输出根目录下的 `<YYMMDD>-<主题>/`。需要研究源码时，先把仓库 clone 到该目录的 `sources/` 并固定 commit SHA，再基于本地源码分析并给出文件:行号证据。

## 何时触发

- 触发词："帮我调研""深入研究""全面了解""对比分析""查清楚…的现状""research" "deep research"等；
- 或问题术语有歧义、领域冷门、表述模糊时主动使用；
- 不触发：一次搜索可答的单点查询、只需阅读已给出的代码片段或单点调试、用户明确要求不联网且不涉及源码分析。

## 工作方式

三个阶段门：校准（歧义 / 冷门 / 模糊时才预检索）→ 选项式澄清（≤3 轮）→ 目标与计划确认门（执行环境、工具组合、调研目标、输出目录候选、调研计划、档位建议一次呈现，等待确认）。确认后进入执行与交付：普通调研按来源分层与增量登记执行，源码调研先 clone 到 `sources/` 并固定 commit SHA；交付 `<OUT>/<YYMMDD>-<主题>/REPORT.md` + `REFERENCES.md`，报告头部记录经用户确认的执行环境（Agent + LLM）。

- 完整协议（阶段模板、档位表、确认门措辞）见 [SKILL.md](SKILL.md)。
- 源码调研六步、来源分层与安全细则见 [references/执行纪律.md](references/执行纪律.md)。
- 报告与登记簿模板见 [references/交付模板.md](references/交付模板.md)。

## 源码调研

- **识别**：实现原理 / 架构 / 调用链 / 行为溯源 / 源码对比，或答案必须靠代码行为验证时启用；建议不低于中档。
- **获取与固定**：确认后 clone 到 `<OUT>/<YYMMDD>-<主题>/sources/<repo>/`，记录完整 commit SHA；已有本地仓库 HEAD 与所需 ref 一致才原地复用。
- **本地分析**：只读，不执行仓库内安装 / 构建 / 测试脚本；代码结论用 `[C#:path:line]` 引用，区分源码实证 / 文档说明 / 推断。

## 输出目录

阶段 0 只读探测工作区，阶段 3 给出 2~3 个输出根目录候选并标推荐项；回复「确认」采用推荐，回复编号或路径即改选。推荐规则：

- 已有 `research/` → 沿用；
- 代码仓且无 `research/` → 优先仓外目录（如 `~/research/` 或工作区同级 `research/`），避免调研产物污染代码库；
- 文档 / 笔记仓 → 仓内 `research/` 或 `docs/research/`；
- 无法判断 → 工作区 `research/`。

最终调研目录为 `<OUT>/<YYMMDD>-<主题>/`；输出目录在确认前不创建，确认后不再变更（用户中途改需求除外）。

## 目录命名

`<OUT>/<YYMMDD>-<主题>/`（如 `<OUT>/261018-国产开源数据库格局/`）：`YYMMDD` 取创建当天（跨日不改名）；主题 slug 简短可读，中文关键词可用；同日同主题重复调研追加 `-2`、`-3`；报告与登记簿内日期用 `YYYY-MM-DD`。

## 依赖

宿主须具备 web 搜索 / 抓取能力：原生 WebSearch / WebFetch 类工具，或已安装的搜索 skill（如 [ddgs-web-access](../ddgs-web-access/)）。源码调研另需 git；无 git 时可退回官方源码包。web 工具缺失但 git 可用时，可降级为仅本地源码调研并声明未做外部资料交叉验证。

## 安装

随仓库任一方式安装（skills CLI / Claude Code 插件市场 / 手动链接），见[仓库 README](../../README.md#安装)。纯提示词 skill，无运行时依赖，链接后 agent 依据 SKILL.md 的 description 自动触发。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源，含档位参数表、确认门模板）
- [references/执行纪律.md](references/执行纪律.md) — 源码调研六步、增量登记、来源分层、安全细则
- [references/交付模板.md](references/交付模板.md) — REPORT.md 结构、REFERENCES.md 模板
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 设计与决策依据
- [docs/测试集.md](docs/测试集.md) — 验证场景

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
