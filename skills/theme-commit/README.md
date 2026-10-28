# theme-commit

工作区混杂多轮、多主题变更时，先给提交计划预览，再按逻辑主题分批提交。每个提交只承载一个主题；提交信息遵循项目规范（本仓库为 `type(scope): 摘要` + 列表式 body）；提交前做快速检查，提交后核对，不推送、不改写历史。

## 何时触发

- 用户要求"提交一下""把改动分开提交""整理提交历史"，且变更涉及多个互不相关的主题；
- 单主题常规提交可不用本 skill；用户调用时仍按同一套格式与检查执行；
- 不触发：只查看 diff、询问变更内容、要求改写历史或推送。

## 工作方式

四步：预检（分支 / 进行中操作 / staged / 敏感文件）→ 分组与计划（先预览，再用宿主结构化提问工具确认）→ 逐主题提交（显式暂存、复核、快速检查、hook 不绕过）→ 收尾（完整测试、status / log 核对、汇报未推送）。完整协议见 [SKILL.md](SKILL.md)。

- 提交信息完整规范（scope、footer、`BREAKING CHANGE`、示例）：[references/提交信息规范.md](references/提交信息规范.md)
- 异常与失败处理表：[references/失败处理.md](references/失败处理.md)

## 提交信息

默认遵循 Conventional Commits：`type(scope): 摘要` + 空行 + `- ` 列表式 body；摘要中文声明式动词开头、≤50 字、不写版本号；版本变更写 body。项目有 commitlint / 模板 / hook 时以其为准；本仓库规范见 [docs/开发与维护规范.md](../../docs/开发与维护规范.md) §10。

## 边界

- 不推送、不 PR；不 amend / rebase / reset / force push，不改写历史。
- 不使用 `git add -A` / `git add .`、`--no-verify`、hunk 级拆分；遇到合并中、敏感文件、主题归属不明等情况先停下询问或报告。

## 安装

把这句交给你的 Agent（它会自己安装并验证）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 theme-commit skill：优先 `npx skills add "GitZhiQing/agent-skills/theme-commit"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh theme-commit`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

插件市场与手动分发方式见[仓库 README](../../README.md#安装)。

纯提示词 skill，无运行时依赖。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [references/提交信息规范.md](references/提交信息规范.md) — 完整提交信息规范
- [references/失败处理.md](references/失败处理.md) — 失败场景处理表
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 设计依据、关键取舍与风险
- [docs/测试集.md](docs/测试集.md) — 行为断言

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
