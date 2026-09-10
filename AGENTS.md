# AGENTS.md — ~/agent-skills

个人 AI coding agent skills 集合：每个一级子目录是一个独立 skill，通过 junction/软链分发到本机各 agent 的 skills 目录（`~/.zcode/skills`、`~/.agents/skills`、`~/.claude/skills`）。

## 怎么跑起来 / 验证

- 纯提示词 skill（theme-commit 等）：无运行时，直接读 SKILL.md。
- ddgs-web-access 需要 uv >= 0.5，命令不依赖当前工作目录：

```bash
bash ddgs-web-access/bin/ddgs-web-search "smoke test" -m 1
bash ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

- 改动 ddgs-web-access 代码后按 `ddgs-web-access/docs/测试集.md` 回归；搜索/抓取调用间隔 ≥2 秒（ddgs 多引擎聚合，过频会限流）。
- 等价形式：`uv run --project ddgs-web-access <命令>`；Windows 用 `bin/*.cmd`。

## 技术栈

- ddgs-web-access：Python >= 3.10（uv 托管虚拟环境），依赖 ddgs + markdownify，单文件 CLI（`ddgs_web_access.py`）+ `bin/` 位置无关启动器；stdout 结果 / stderr 提示与错误 / 退出码 0-1-2。
- theme-commit：纯 SKILL.md 提示词（git 按主题分组提交）。

## 目录与约定

- 一个 skill 一个目录，SKILL.md 为入口；复杂 skill 另带 README.md 与 docs/（设计文档、测试集）。
- 分发与卸载：`bash ddgs-web-access/scripts/install.sh` / `uninstall.sh`，在三个 agent 目录下建/删指向本仓库的 junction，单一来源。
- 运行产物（`.venv/`、`.cache/`、`__pycache__/`、`*.egg-info/`）已 gitignore，不纳入版本管理。
- `.zcode/`（会话计划产物）在根 .gitignore 中排除。

## 当前状态与下一步

- git 仓库已初始化（main 分支，2026-09-10），尚未配置远端。
- ddgs-web-access v0.2.0 已定稿：设计文档 v0.6、测试集 v1.1，三个 agent 目录的链接已验证生效。
- theme-commit 仅存于本仓库，未链接到任何 agent。
- `research-with-docs/` 为空目录，用途待定。
