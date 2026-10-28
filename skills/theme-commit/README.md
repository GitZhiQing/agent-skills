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

**让 Agent 代装（推荐）**：把下面这段原样发给你的 Agent。

```text
安装 https://github.com/GitZhiQing/agent-skills 仓库中的 theme-commit skill：
1) 先执行 `npx skills add "GitZhiQing/agent-skills/theme-commit"`，按输出完成安装；
2) 该方式不可用时，克隆仓库后执行 `bash scripts/skills-link.sh theme-commit`，再跑 `bash scripts/skills-doctor.sh` 确认链接健康；
3) 汇报安装位置与验证结果；失败时说明原因，不要跳过验证。
```

**Claude Code 插件市场**：`/plugin marketplace add GitZhiQing/agent-skills`，然后 `/plugin install theme-commit@agent-skills`。

**仓库内手动分发**（Windows junction / Unix symlink，单一来源，`git pull` 后全端生效）：

```bash
git clone https://github.com/GitZhiQing/agent-skills.git
cd agent-skills
bash scripts/skills-link.sh theme-commit    # 全部 skill 用 --all；卸载用 scripts/skills-unlink.sh theme-commit
bash scripts/skills-doctor.sh
```

纯提示词 skill，无运行时依赖；链接完成后，Agent 依据 `SKILL.md` 的 description 自动触发。


## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [references/提交信息规范.md](references/提交信息规范.md) — 完整提交信息规范
- [references/失败处理.md](references/失败处理.md) — 失败场景处理表
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 设计依据、关键取舍与风险
- [docs/测试集.md](docs/测试集.md) — 行为断言

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
