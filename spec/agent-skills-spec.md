# Agent Skills 规范指针

格式规范以官方为准：<https://agentskills.io/specification>。本仓库不复制、不改写官方字段定义，只在其上追加约定。官方字段与渐进披露语义于 2026-11-11 复核。

## 优先级

1. **官方规范**：目录形态、frontmatter 必填字段（`name` / `description`）、可选字段（`license` / `compatibility` / `metadata` / `allowed-tools`）及其约束、渐进披露模型。
2. **本仓库增量约定**：[docs/CONVENTIONS.md](../docs/CONVENTIONS.md) §2–§5——三段式 description、`metadata.version` / `metadata.category`、per-skill README/LICENSE、测试集、版本同步、独立可选协作、分发。
3. **冲突裁决**：格式字段以官方为准；本仓库附加要求只做加严，不降低官方约束；客户端专有扩展不得写入共享 skill。

## 官方字段与加载要点

- 启动时常驻上下文主要是 `name` + `description`；description 是宿主 agent 判断是否加载的主要输入，官方硬上限 1024 字符。本仓库目标 ≤500 字符。
- `SKILL.md` 正文在触发时整体加载；官方建议 <500 行并控制 token 预算，本仓库上限为 ≤500 行 / ≤16KB。
- `references/`、`scripts/`、`assets/` 按需加载；文件引用使用 skill 根相对路径并保持一层深。
- `compatibility` 是 ≤500 字符的标量字符串；`metadata` 是 string→string 映射；`allowed-tools` 是实验性预批准字段，不是安全沙箱。
- `metadata.version` 不是官方运行时接口；它是本仓库用于维护、分发与测试同步的加严元数据。

## 本仓库的加严项

- frontmatter 顶层字段封闭为官方 6 字段。
- `description` 固定三段式：定位 / 正向触发 / 反向不触发；面向 agent 触发判断，不写用户宣传文案或流程摘要。
- 每个 skill 必须有 `README.md`、`LICENSE` 与 `.claude-plugin/plugin.json`，并出现在 `.claude-plugin/marketplace.json`；`docs/TESTS.md` 应有（缺失 lint warn）。
- 每个 skill 必须标 `metadata.version`（semver）；建议标 `metadata.category`；版本同步规则见 CONVENTIONS §4。
- skill 之间只做可选协作：不硬依赖、不引用对方内部路径、缺失可降级；仓库根组合说明不是安装前置。
- `SKILL.md` 目标 ≤500 行 / ≤16KB；条件分支、模板与长清单放 `references/`，距入口一层。
