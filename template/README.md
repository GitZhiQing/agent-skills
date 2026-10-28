# __NAME__

<一句话定位：面向人的导览，不复制 SKILL.md 正文。>

## 何时触发

- <正向场景与触发词>
- 不触发：<反向场景>

## 工作方式

<3–5 行概要：核心流程与边界；完整协议见 SKILL.md，条件分支见 references/。>

## 安装

**让 Agent 代装（推荐）**：把下面这段原样发给你的 Agent。

```text
安装 https://github.com/GitZhiQing/agent-skills 仓库中的 __NAME__ skill：
1) 先执行 `npx skills add "GitZhiQing/agent-skills/__NAME__"`，按输出完成安装；
2) 该方式不可用时，克隆仓库后执行 `bash scripts/skills-link.sh __NAME__`，再跑 `bash scripts/skills-doctor.sh` 确认链接健康；
3) 汇报安装位置与验证结果；失败时说明原因，不要跳过验证。
```

**Claude Code 插件市场**：`/plugin marketplace add GitZhiQing/agent-skills`，然后 `/plugin install __NAME__@agent-skills`。

**仓库内手动分发**：`bash scripts/skills-link.sh __NAME__`（卸载 `scripts/skills-unlink.sh __NAME__`），再跑 `bash scripts/skills-doctor.sh`。

纯提示词 skill 无运行时依赖；有代码的 skill 在此列环境要求。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- `references/` — 条件分支与清单（按需加载；无则删除）
- [docs/TESTS.md](docs/TESTS.md) — 行为断言
- [docs/SPEC.md](docs/SPEC.md) — 设计与决策依据（可选）

许可：MIT（仓库根 [LICENSE](../LICENSE)）。
