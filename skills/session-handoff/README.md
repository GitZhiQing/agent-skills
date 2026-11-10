# session-handoff

会话收尾时把整个会话打包成一段可粘贴的交接提示词：回顾任务、变更、决策与踩过的坑，产出精炼的自包含文档——用户原样粘贴进新会话开头，接手的 Coding Agent 无需任何历史上下文即可恢复状态、制定计划、继续开发。

## 何时触发

- 用户在会话收尾时要求"交接一下""生成交接提示词""换会话继续""把这次会话交接出去""session handoff"等；
- 用户只要本会话的总结 / 复盘（不打算换会话继续）时不经过本 skill，按普通总结作答。

## 工作方式

先用 git 命令核对事实，再按 [SKILL.md](SKILL.md) 的交接骨架成文（任务与目标、进度、变更、决策、待办、风险、开工指引），只输出一个可整体复制的代码块。完整骨架、AGENTS.md 取舍与写作要求见 SKILL.md。

## 边界

- 只产出交接提示词文本，不落盘文件、不自动提交、不改动项目代码；
- 默认接手方所在会话会自动注入 AGENTS.md；已知不会注入时，环境与运行方式、文件地图在第 8 节补回。

## 安装

把这句交给你的 Agent（它会自己安装并验证）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 session-handoff skill：优先 `npx skills add "GitZhiQing/agent-skills/session-handoff"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh session-handoff`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

直接用命令行安装：

```bash
npx skills add GitZhiQing/agent-skills/session-handoff
```

```text
/plugin marketplace add GitZhiQing/agent-skills
/plugin install session-handoff@agent-skills
```

手动分发与卸载见[仓库 README](../../README.md#安装)。

纯提示词 skill，无运行时依赖。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [docs/TESTS.md](docs/TESTS.md) — 行为断言（人工会话执行）

许可：MIT（[LICENSE](LICENSE)）。
