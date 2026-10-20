# agent-skills

个人 AI coding agent skills 集合，遵循 [Agent Skills 开放规范](https://agentskills.io/specification)：一个 skill 一个目录，`SKILL.md` 为入口，可被 Claude Code、Codex、Cursor、ZCode 等支持该格式的 agent 加载。

## Skills

| Skill | 类型 | 说明 |
| --- | --- | --- |
| [ddgs-web-access](skills/ddgs-web-access/) | Python CLI | 联网搜索与网页抓取 |
| [deep-research](skills/deep-research/) | 纯提示词 | 先校准再调研（人类交互确认，自主模式不适用），交付 REPORT + REFERENCES + META；支持源码调研 |
| [theme-commit](skills/theme-commit/) | 纯提示词 | 先计划预览并用提问工具确认，再按主题分组提交 |
| [zero-coding](skills/zero-coding/) | 纯提示词 | 从零启动个人项目的轻量工作流 |
| [session-handoff](skills/session-handoff/) | 纯提示词 | 生成跨会话交接提示词 |
| [video-insight](skills/video-insight/) | Python 脚本 | 拉片级视频内容与画面分析 |
| [md2pdf](skills/md2pdf/) | Python CLI | Markdown 转精美 PDF |

各 skill 的用法、依赖与排障见其目录内的 `README.md` / `SKILL.md`；版本号以 `SKILL.md` frontmatter 为准。

## 安装

三种方式任选其一：

- **skills CLI**：`npx skills add GitZhiQing/agent-skills`（单个 skill 用 `npx skills add GitZhiQing/agent-skills/<name>`）
- **Claude Code marketplace**：`/plugin marketplace add GitZhiQing/agent-skills`，再 `/plugin install <name>@agent-skills`
- **手动**：克隆后执行 `bash scripts/skills-link.sh --all`，再 `bash scripts/skills-doctor.sh` 巡检

**让 Agent 代装**：把下面这段发给 agent：

```text
Run `npx skills add "https://github.com/GitZhiQing/agent-skills"` and follow the generated instructions now. Read its complete output, redirecting it to a temporary file first if necessary. Resolve relative paths from the supporting-files directory it provides.
```

## 快速使用

安装后直接对 Agent 描述任务即可：

- “帮我调研一下 X，最好带源码证据”
- “把这次改动按主题分开提交”
- “分析这条视频的文案和画面节奏”
- “把这份 Markdown 转成 PDF，用 kimi 主题”

具体用法见各 skill 目录的 `README.md`。

## 典型组合

- **调研交付**：`deep-research` 检索与源码分析 → `md2pdf` 排版成 PDF；搜索工具缺失时由 `ddgs-web-access` 补位。
- **项目启动**：`zero-coding` 立项与切片 → `theme-commit` 按主题提交 → `session-handoff` 换会话继续。
- **内容复盘**：`video-insight` 产出分析报告 → `md2pdf` 排版归档。

## 文档

| 文档 | 读者 | 用途 |
| --- | --- | --- |
| [AGENTS.md](AGENTS.md) | AI 会话 | 运行、验证、完成定义 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献者 | 最短上手路径与自检清单 |
| [docs/开发与维护规范.md](docs/开发与维护规范.md) | 维护者 | 目录结构、frontmatter、版本、分发、脚本规则、提交规范 |
| [docs/维护脚本测试集.md](docs/维护脚本测试集.md) | 维护者 | `scripts/` 回归用例 |
| [spec/agent-skills-spec.md](spec/agent-skills-spec.md) | 维护者 | 官方规范指针与本仓库加严项 |
| [template/](template/) | 维护者 | 新 skill 骨架 |
| 各 skill 目录内的 `README.md` / `docs/` | 使用者 | 用法、设计与测试集 |

## 许可与安全

- 本仓库以 [MIT](LICENSE) 发布（ddgs-web-access 目录内另附一份，供单独拷走使用）。
- **skill 含可执行代码**（`skills/*/bin/`、`skills/*/scripts/`），安装前请自行审阅。
- ddgs-web-access 依赖的上游 ddgs 声明"仅供教育目的使用"，使用时请遵守目标网站服务条款与 robots 协议。
- md2pdf 首次 `fetch` 会在运行时下载字体切片、Paged.js 与 KaTeX，许可与来源见该 skill 的 `README.md`。
