# agent-skills

个人 AI coding agent skills 集合，遵循 [Agent Skills 开放规范](https://agentskills.io/specification)：一个 skill 一个目录，`SKILL.md` 为入口，可被 Claude Code、Codex、Cursor 等支持该格式的 agent 加载。

## Skills

| Skill | 类型 | 说明 |
| --- | --- | --- |
| [ddgs-web-access](skills/ddgs-web-access/) | Python CLI | 联网搜索与网页抓取 |
| [theme-commit](skills/theme-commit/) | 纯提示词 | 按主题分组、分批提交 |
| [deep-research](skills/deep-research/) | 纯提示词 | 先校准再调研，交付 REPORT + REFERENCES；支持源码调研 |
| [zero-coding](skills/zero-coding/) | 纯提示词 | 从零启动个人项目的轻量工作流 |
| [video-insight](skills/video-insight/) | Python 脚本 | 拉片级视频内容与画面分析 |
| [session-handoff](skills/session-handoff/) | 纯提示词 | 生成跨会话交接提示词 |
| [md2pdf](skills/md2pdf/) | Python CLI | Markdown 转精美 PDF |

各 skill 的用法、参数与排障见其目录内的 `README.md` / `SKILL.md`；版本号以各 skill 的 `SKILL.md` frontmatter 为准，本表不展示。

## 安装

四种方式任选其一：

- **skills CLI**：`npx skills add GitZhiQing/agent-skills`（单个 skill 用 `npx skills add GitZhiQing/agent-skills/<name>`）
- **Claude Code marketplace**：`/plugin marketplace add GitZhiQing/agent-skills`，再 `/plugin install <name>@agent-skills`
- **手动**：克隆后执行 `bash scripts/skills-link.sh --all`，再 `bash scripts/skills-doctor.sh` 巡检

**让 Agent 代装**：把下面这段发给 agent：

```text
Run `npx skills add "https://github.com/GitZhiQing/agent-skills"` and follow the generated instructions now. Read its complete output, redirecting it to a temporary file first if necessary. Resolve relative paths from the supporting-files directory it provides.
```

分发目标、`agents.local.conf` 与脚本用法见 [docs/开发与维护规范.md](docs/开发与维护规范.md) §6。

## 快速使用

以 ddgs-web-access 为例（需 [uv](https://docs.astral.sh/uv/) >= 0.5）：

```bash
npx skills add GitZhiQing/agent-skills/ddgs-web-access
bash ~/.claude/skills/ddgs-web-access/bin/ddgs-web-search "python 3.13 asyncio" -m 5
bash ~/.claude/skills/ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

## 文档

- [AGENTS.md](AGENTS.md) — 面向 agent 的入口：运行、验证、技术栈与目录约定
- [docs/开发与维护规范.md](docs/开发与维护规范.md) — 目录结构、版本、分发、提交信息规范
- [docs/维护脚本测试集.md](docs/维护脚本测试集.md) — 维护脚本测试用例
- 各 skill 目录内的 `README.md` / `docs/` — 用法、设计与测试集

## 许可与安全

- 本仓库以 [MIT](LICENSE) 发布（ddgs-web-access 目录内另附一份，供单独拷走使用）。
- **skill 含可执行代码**（`skills/*/bin/`、`skills/*/scripts/`），安装前请自行审阅。
- ddgs-web-access 依赖的上游 ddgs 声明"仅供教育目的使用"，使用时请遵守目标网站服务条款与 robots 协议。
