# Agent Skills 规范指针

格式规范以官方为准：<https://agentskills.io/specification>。本仓库不复制、不改写官方字段定义，只在其上追加约定。

## 优先级

1. **官方规范**：目录形态、frontmatter 必填字段（`name` / `description`）、可选字段（`license` / `compatibility` / `metadata` / `allowed-tools`）及其约束、三级渐进披露模型。
2. **本仓库增量约定**：[docs/开发与维护规范.md](../docs/开发与维护规范.md) §2–§5——三段式 description、`metadata.version` / `metadata.category`、per-skill README、测试集、版本同步、分发。
3. **冲突裁决**：格式字段以官方为准；本仓库附加要求只做加严，不降低官方约束。

## 本仓库的加严项

- `description` 固定三段式：定位 / 正向触发 / 反向不触发。
- 每个 skill 必须有 `README.md` 与 `.claude-plugin/plugin.json`，并出现在 `.claude-plugin/marketplace.json`；`docs/测试集.md` 应有（缺失 lint warn）。
- 每个 skill 必须标 `metadata.version`（semver）；建议标 `metadata.category`。
- `SKILL.md` 目标 ≤500 行 / ≤16KB；条件分支、模板与长清单放 `references/`，距入口一层。
