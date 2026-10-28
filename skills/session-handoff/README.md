# session-handoff

会话收尾时把整个会话打包成一段可粘贴的交接提示词：回顾任务、变更、决策与踩过的坑，产出精炼的自包含文档——用户原样粘贴进新会话开头，接手的 Coding Agent 无需任何历史上下文即可恢复状态、制定计划、继续开发。

## 何时触发

- 用户在会话收尾时要求"交接一下""生成交接提示词""换会话继续""把这次会话交接出去""session handoff"等；
- 用户只要本会话的总结 / 复盘（不打算换会话继续）时不经过本 skill，按普通总结作答。

## 工作方式

1. **生成前核对**：通读会话，并用 `git status` / `git diff --stat` / `git log` 核对分支与变更（非 git 项目跳过），不凭记忆；
2. **按骨架成文**：7 节必含（任务与目标、当前进度、关键变更、关键决策与原因、待办与下一步、已知问题与风险、开工指引）+ 第 8 节“AGENTS.md 未覆盖”条件保留；
3. **面向 AGENTS.md 取舍**：接手方会读到自动注入的 AGENTS.md，项目背景 / 运行命令 / 目录地图 / 通用约定不重复不搬运；项目无 AGENTS.md 时回退补全；
4. **只输出一个代码块**：交接提示词放单个 markdown 代码块内、块外零输出；一般 400–1200 字，要求具体可验证、区分（待验证）/（未决）、敏感信息用 `<占位符>`。

## 边界

- 只产出交接提示词文本，不落盘文件、不自动提交、不改动项目代码；
- 默认接手方所在会话会自动注入 AGENTS.md；已知不会注入时，环境与运行方式、文件地图在第 8 节补回。

## 安装

**让 Agent 代装（推荐）**：把下面这段原样发给你的 Agent。

```text
安装 https://github.com/GitZhiQing/agent-skills 仓库中的 session-handoff skill：
1) 先执行 `npx skills add "GitZhiQing/agent-skills/session-handoff"`，按输出完成安装；
2) 该方式不可用时，克隆仓库后执行 `bash scripts/skills-link.sh session-handoff`，再跑 `bash scripts/skills-doctor.sh` 确认链接健康；
3) 汇报安装位置与验证结果；失败时说明原因，不要跳过验证。
```

**Claude Code 插件市场**：`/plugin marketplace add GitZhiQing/agent-skills`，然后 `/plugin install session-handoff@agent-skills`。

**仓库内手动分发**（Windows junction / Unix symlink，单一来源，`git pull` 后全端生效）：

```bash
git clone https://github.com/GitZhiQing/agent-skills.git
cd agent-skills
bash scripts/skills-link.sh session-handoff    # 全部 skill 用 --all；卸载用 scripts/skills-unlink.sh session-handoff
bash scripts/skills-doctor.sh
```

纯提示词 skill，无运行时依赖；链接完成后，Agent 依据 `SKILL.md` 的 description 自动触发。


## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [docs/测试集.md](docs/测试集.md) — 行为断言（人工会话执行）

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
