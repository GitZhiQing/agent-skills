# __NAME__

<一句话定位：面向人的导览，不复制 SKILL.md 正文。>

## 何时触发

- <正向场景与触发词>
- 不触发：<反向场景>

## 工作方式

<3–5 行概要：核心流程与边界；完整协议见 SKILL.md，条件分支见 references/。>

## 安装

随仓库统一分发：`bash scripts/skills-link.sh __NAME__`，见[仓库 README](../../README.md#安装)。纯提示词 skill 无运行时依赖；有代码的 skill 在此列环境要求。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- `references/` — 条件分支与清单（按需加载；无则删除）
- [docs/测试集.md](docs/测试集.md) — 行为断言
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 设计与决策依据（可选）

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
