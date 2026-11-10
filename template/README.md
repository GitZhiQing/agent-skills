# __NAME__

<一句话定位：面向人的导览，不复制 SKILL.md 协议正文。>

## 何时触发

- <正向场景与触发词>
- 不触发：<近邻反例>

## 工作方式

<3–5 行概要：核心流程、外部环境要求与边界；完整协议见 SKILL.md，条件分支见 references/。>

## 安装

把下面这段原样发给你的 Agent：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 __NAME__ skill：优先执行 `npx skills add "GitZhiQing/agent-skills/__NAME__"`；不可用则克隆仓库后执行 `bash scripts/skills-link.sh __NAME__`，再跑 `bash scripts/skills-doctor.sh` 验证并汇报结果。
```

其他分发方式见仓库根 README；本 skill 可独立安装和使用，不要求同时安装其他 skill。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- `references/` — 条件分支与清单（按需加载；无则删除）
- [docs/TESTS.md](docs/TESTS.md) — 行为断言
- [docs/SPEC.md](docs/SPEC.md) — 设计决策与依据（可选）
- [LICENSE](LICENSE) — MIT

许可：MIT。
