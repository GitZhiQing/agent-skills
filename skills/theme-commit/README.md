# theme-commit

工作区混杂多轮、多主题变更时，先给提交计划预览，再按逻辑主题分批提交。每个提交只承载一个主题；提交信息遵循项目规范（本仓库为 `type(scope): 摘要` + 列表式 body）；提交前做快速检查，提交后核对，不推送、不改写历史。

## 何时触发

- 用户要求"提交一下""把改动分开提交""整理提交历史"，且变更涉及多个互不相关的主题；
- 单主题常规提交可不用本 skill；用户调用时仍按同一套格式与检查执行；
- 不触发：只查看 diff、询问变更内容、要求改写历史或推送。

## 工作方式

| 阶段 | 做什么 |
| --- | --- |
| 0 预检 | 看分支 / 进行中操作 / staged / unstaged / untracked；已有 staged 改动先询问；检查敏感文件、大文件、生成物；读取项目提交规范与检查命令 |
| 1 分组与计划 | 按逻辑主题分组，生成 `type(scope)` + body + 文件路径 + 检查项；默认先展示计划，再用宿主结构化提问工具确认（无工具时纯文本），支持确认 / 调整 / 取消；用户说直接提交可跳过 |
| 2 逐主题提交 | 显式 `git add -- <路径>`；复核 `git diff --cached`；空提交守卫；快速检查；`git commit -F -` 写入完整消息；hook 失败不绕过 |
| 3 收尾 | 跑完整测试 / 构建；`git status` 检查剩余；`git log` + `git show` 核对；汇报 hash / subject / files / checks |

计划展示后，skill 会调用当前宿主可用的结构化提问 / 选择工具询问"是否按以上计划提交？"，选项为确认提交 / 调整计划 / 取消；宿主没有该工具时退回纯文本提问。用户此前明确说"直接提交"时跳过预览与提问。

## 提交信息

默认遵循 Conventional Commits；项目有 commitlint / 模板时以其为准。本仓库规范见 [docs/开发与维护规范.md](../../docs/开发与维护规范.md) §10。

- **Subject**：`type(scope): 摘要`，ASCII 冒号；`type` 取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `build`（项目另有 `perf` / `ci` / `style` / `revert` 等时按项目规范）；scope 用 skill / 模块 / 目录，跨模块用 `repo`。
- 摘要中文声明式动词开头，≤50 字，不加句号，不写版本号。
- **Body**：空行后用 `- ` 列表逐条说明；每条一个变更；版本变更写 body。
- 可选 footer：`BREAKING CHANGE:`、`Closes #123`、`Refs: #123`。

```text
feat(deep-research): 增加源码调研协议

- 阶段 1 识别源码调研，确认门列出源码获取计划
- 阶段 4 clone 到 sources/ 并固定完整 commit SHA
- 版本升至 0.4.0
```

## 边界

- 不推送、不 PR；不 amend / rebase / reset / force push，不改写历史。
- 不使用 `git add -A` / `git add .`、`--no-verify`、hunk 级拆分（单文件多主题整文件归主主题，body 说明）。
- 合并 / 变基 / cherry-pick / 冲突 / detached HEAD、已有 staged 改动、敏感 / 大文件、主题归属不明：先停下询问或报告。
- 纯提示词只能做最佳努力检查；可靠拦截依赖项目的 hook / CI / secret scanning。

## 安装

随仓库任一方式安装（skills CLI / Claude Code 插件市场 / 手动链接），见[仓库 README](../../README.md#安装)。纯提示词 skill，无运行时依赖，链接后 agent 依据 SKILL.md 的 description 自动触发。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 设计依据、关键取舍与风险
- [docs/测试集.md](docs/测试集.md) — 行为断言

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
