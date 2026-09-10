# skills — 个人 AI Agent Skills 集合

存放供 AI coding agent（ZCode / Claude Code / Agents 等）使用的 skills。每个一级子目录是一个独立 skill，以 SKILL.md 为入口；通过链接（Windows junction / Unix symlink）分发到本机各 agent 的 skills 目录，做到单一来源、改一处全端生效。

## Skills 一览

| Skill | 版本 | 类型 | 说明 | 分发状态 |
| --- | --- | --- | --- | --- |
| [ddgs-web-access](ddgs-web-access/) | 0.2.0 | Python CLI | 基于 ddgs 的联网搜索与网页抓取工具（`ddgs-web-search` / `ddgs-web-fetch`） | 已链接到 `~/.zcode`、`~/.agents`、`~/.claude` 三个 skills 目录 |
| [theme-commit](theme-commit/) | — | 纯提示词 | 分析混杂变更，按逻辑主题分组提交 git | 仅存于本仓库，未链接 |
| research-with-docs/ | — | — | 空目录，规划中 | — |

## 快速使用

以 ddgs-web-access 为例（需 [uv](https://docs.astral.sh/uv/) >= 0.5，首次调用自动安装依赖）：

```bash
bash ddgs-web-access/bin/ddgs-web-search "python 3.13 asyncio" -m 5
bash ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

各 skill 的调用方法、参数与排障见其目录内的 SKILL.md / README.md。

## 安装与分发

ddgs-web-access 自带安装脚本，把本仓库链接到本机已安装 agent 的 skills 目录（可重复执行，卸载只删链接）：

```bash
bash ddgs-web-access/scripts/install.sh      # 卸载：bash ddgs-web-access/scripts/uninstall.sh
```

纯提示词 skill（如 theme-commit）无安装脚本，需要时手动复制或链接到目标 agent 的 skills 目录。

## 目录结构

```text
skills/
├── AGENTS.md            # AI 会话入口：定位、运行验证、约定、当前状态
├── README.md            # 本文件
├── ddgs-web-access/     # Python CLI skill（含 docs/ 设计文档与测试集、bin/ 启动器、scripts/ 安装脚本）
├── theme-commit/        # 纯提示词 skill
└── research-with-docs/  # 规划中（空）
```

## 开发约定

- 一个 skill 一个目录，SKILL.md 为入口；复杂 skill 另带 README.md 与 docs/。
- ddgs-web-access 的改动按其 [测试集](ddgs-web-access/docs/测试集.md) 回归；搜索/抓取调用间隔 ≥2 秒，避免限流。
- 运行产物（`.venv/`、`.cache/`、`__pycache__/`、`*.egg-info/`）不提交。

## 许可

ddgs-web-access 为 MIT；注意上游 ddgs 声明"仅供教育目的使用"，使用时请遵守目标网站服务条款与 robots 协议。
