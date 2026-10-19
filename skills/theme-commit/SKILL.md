---
name: theme-commit
description: >-
  工作区混杂多轮、多主题变更时，先给提交计划预览，再用宿主可用的结构化提问工具确认，
  按逻辑主题分批提交；提交信息遵循仓库的 Conventional Commits 规范（type(scope): 摘要 + 列表式 body），
  显式暂存路径、提交前检查、提交后验证，不改写历史、不推送。
  当用户要求"提交一下""把改动分开提交""整理提交历史"且变更涉及多个主题时使用；
  单主题常规提交可不用本 skill，用户明确要求直接提交时可跳过计划预览，
  但消息格式与检查仍适用。明确要求改写历史、推送或只查看 diff 时不要使用本 skill。
license: MIT
metadata:
  version: 0.2.0
  category: git
---

# theme-commit：先计划，再按主题提交

多轮开发后的工作区常混杂互不相关的变更。目标不是"尽量多拆"，而是让每个提交：

- 只承载一个逻辑主题；
- 提交信息符合仓库规范（本仓库见 `docs/开发与维护规范.md` §10）；
- 提交前经过可用的快速检查，提交后可核对；
- 不推送、不改写已发布历史。

## 阶段 0 · 预检

1. 确认仓库根、当前分支与最近提交风格：`git rev-parse --show-toplevel`、`git status --short --branch`、`git log -8 --oneline`。
2. 检查进行中的操作：合并 / 变基 / cherry-pick / 冲突 / detached HEAD。命中任一项即停止并报告，不在半完成状态上提交。
3. 盘点全部变更：`git diff`（未暂存）、`git diff --cached`（已暂存）、`git status --short`（untracked / 删除 / 重命名）。untracked 文本文件直接读内容，不按文件名猜主题；二进制 / 大文件不按文本读，按路径和大小归类并询问。
4. **已有 staged 改动不静默混入**：`git diff --cached --name-status` 非空时，逐项列出并询问——纳入某个主题、由用户自行处理，或经同意后 `git restore --staged -- <paths>`。不要擅自丢弃用户的暂存状态；用户选择自行处理时暂停本批次，不带着 staged 改动提交其他主题。
5. 读取项目规范与检查命令：`AGENTS.md`、`CONTRIBUTING`、`README`、`docs/开发与维护规范.md`、`package.json` / `pyproject.toml` / CI 配置。项目有 commitlint / 模板 / hook 时以其为准；没有时使用下方默认格式。检查命令只使用项目文档写明的，不自行发明。
6. 安全预检（最佳努力）：不要 stage ignored 文件；对 `.env`、`*.pem`、`*.key`、`id_rsa`、credentials、token 等敏感文件名先询问；对 >5MB 文件先询问，>50MB 默认不提交；生成物 / 缓存 / 构建目录（`dist/`、`build/`、`node_modules/`、`coverage/` 等）默认不入库，除非项目明确要求。

## 阶段 1 · 分组与计划

按逻辑主题分组，而不是按文件类型或提交时间机械切分：

- 测试随对应功能 / 修复；纯补测试可单独 `test`。
- 纯格式化 / 空白改动尽量独立；同一文件内混入多主题时，整文件归主主题并在 body 说明，**不做 hunk 级拆分**（项目 §10；`git add -p` 对 agent 不可靠）。
- 重构与功能 / 修复尽量分开；依赖锁文件随依赖变更，或单独 `build` / `chore`。
- 文档随对应功能；纯文档清理用 `docs`。
- 共享文件 / 配置归入需要它的主题；确实跨主题时单独 `chore` 并在 body 说明。
- 版本变更与行为变更同一提交；按项目规则同步 `pyproject.toml` / `plugin.json` / marketplace / 台账，版本号写 body。
- 提交顺序按依赖：构建 / 依赖 → 重构 → 功能 / 修复 → 文档 / 测试；顺序会影响中间状态可构建性时在计划中说明。

为每个主题准备：`type(scope): 摘要`、body 列表、显式文件路径（含删除 / 重命名）、快速检查、版本变更。

**默认先给计划，再用宿主的结构化提问工具确认**（用户已明确说"直接提交 / 不用确认"则跳过）：

```
提交计划（N 个）
1. feat(scope): 摘要
   - files: <显式路径>
   - body:
     - <变更点 1>
     - <变更点 2>
   - checks: <命令>
2. docs(scope): 摘要
   ...
未纳入：<ignored / 生成物 / 用户保留 / 待确认>
```

计划展示后，调用当前宿主可用的结构化提问 / 选择工具（如 AskUserQuestion、request_user_input、elicitation，以实际可用为准）询问是否按计划提交：

> 是否按以上计划提交？
> - 确认提交
> - 调整计划
> - 取消

- 只调用当前环境实际存在的工具；宿主没有结构化提问工具时，退回纯文本提问，列出同样选项并等待回复；不要假设或伪造某个具体工具调用。
- 一次计划只问一次，不在每个提交前重复询问。
- **确认提交**：按计划执行。
- **调整计划**：修改分组 / 消息 / 检查项后按新计划执行（涉及删除、重置、敏感文件时仍需确认）。
- **取消**：停止，不落盘。
- 用户此前已明确说"直接提交"：跳过预览与提问，但仍执行消息格式、显式暂存、检查与收尾。

计划阶段不 dump 全量 diff。

## 阶段 2 · 逐主题提交

1. `git add -- <显式路径>`。禁止 `git add -A` / `git add .`；删除用 `git add -- <路径>` 暂存删除，重命名把旧、新路径都列出。
2. `git diff --cached --stat` + `git diff --cached` 复核，确认只包含本主题；发现夹带立即停止。
3. 空提交守卫：`git diff --cached --quiet` 命中则跳过该主题并说明原因。
4. 快速检查：`git diff --cached --check`；再运行项目文档中的 lint / format / typecheck（只跑与改动相关的快速项）。检查失败停止，报告命令与错误摘要；修复属于本次范围且明确时，修复后重新暂存并重跑。
5. 提交信息用临时文件或 `git commit -F -` 写入完整 subject + body；不要把 body 压成一行。不要传 `--no-verify`，让 hook 正常执行。
6. hook 失败：停止并报告，不绕过；commit-msg hook 因消息格式拒绝时，按项目规范修正 message 后重试；pre-commit hook 失败按检查失败处理；hook 修改了文件：重新暂存并重试本次提交，不自动 amend。
7. 提交后 `git show --stat --oneline HEAD` 核对文件集合；与计划不符时停止并报告。

## 阶段 3 · 收尾

- 全部提交后运行一次项目完整测试 / 构建（项目文档有命令时）；没有则说明未运行。
- 完整测试 / 构建失败：报告失败摘要与已提交内容；不自动 reset / amend，不推送。
- `git status --short` 确认剩余变更，逐条解释（ignored、生成物、用户保留、未纳入主题）。
- `git log --oneline -N` 与每个提交的 `git show --stat` 核对提交数、消息、文件集合。
- 向用户汇报：hash / subject / files / checks；明确"未推送"。
- 中途失败：报告已成功提交、剩余主题、index / worktree 状态；不做 `reset --hard`、amend 等自动修复。

## 提交信息规范

默认格式；项目有更具体规范时以项目为准：

- **Subject**：`type(scope): 摘要`，ASCII 冒号。`type` 取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `build`（项目另有 `perf` / `ci` / `style` / `revert` 等时按项目规范）；`scope` 用 skill / 模块 / 目录，跨模块用 `repo`。
- 摘要用中文声明式动词开头，≤50 字，不加句号，**不写版本号**。
- **Body**：subject 后空一行，用 `- ` 列表逐条说明，每条一个变更；写清做了什么、为什么，版本变更放 body。
- 可选 footer：`BREAKING CHANGE: <说明>`、`Closes #123`、`Refs: #123`。不自动添加 `Co-authored-by`。
- 破坏性变更：subject 加 `!` 或 body / footer 写 `BREAKING CHANGE:`，并按项目版本规则升 major。
- 禁止"更新代码""修复问题"这类零信息摘要。

示例：

```text
feat(deep-research): 增加源码调研协议

- 阶段 1 识别源码调研，确认门列出源码获取计划
- 阶段 4 clone 到 sources/ 并固定完整 commit SHA
- 版本升至 0.4.0
```

## 边界与失败处理

- **不推送、不 PR**；不 amend / rebase / reset / force push，不改写已发布历史。
- 不使用 `git add -A` / `git add .`、`--no-verify`、hunk 级拆分。
- 合并 / 变基 / cherry-pick / 冲突 / detached HEAD：停止。
- 已有 staged 改动、敏感文件、大文件、生成物、主题归属不明：先问，不猜。
- 检查 / hook / 提交失败：停止并报告；不自动回滚或改写历史。
- 纯提示词只能"建议"安全扫描与检查；可靠拦截仍需项目的 hook / CI / secret scanning。

## 失败处理表

| 场景 | 处理 |
| --- | --- |
| 已有 staged 改动 | 列出并询问；未处理前暂停，不静默混入 |
| 主题为空 | `git diff --cached --quiet` 命中，跳过并说明 |
| 快速检查失败 | 停止；修复后重新暂存并重跑 |
| hook 失败 | 停止；commit-msg 格式问题按规范修正后重试；不使用 `--no-verify` |
| hook 修改文件 | 重新暂存并重试本次提交 |
| 提交中途失败 | 报告已提交 / 剩余 / index 状态；不自动 reset / amend |
| 批次后完整测试失败 | 报告失败摘要与已提交内容；不自动改写历史 |
| 敏感 / 大文件 | 停止并询问；不强行提交 |
| 合并 / 变基 / 冲突 / detached HEAD | 停止并报告 |
