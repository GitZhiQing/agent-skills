# agent-skills

A collection of [Agent Skills](https://agentskills.io)（SKILL.md 开放格式）for AI coding agents —— 个人 AI coding agent skills 集合。

全部 skill 遵循 [Agent Skills 开放规范](https://agentskills.io/specification)：一个 skill 一个目录，`SKILL.md` 为唯一入口；可被 Claude Code、Codex、Cursor 等支持该格式的 agent 加载。

## Skills


| Skill                                      | 版本  | 类型       | 说明                                                                                                                |
| -------------------------------------------- | ------- | ------------ | --------------------------------------------------------------------------------------------------------------------- |
| [ddgs-web-access](skills/ddgs-web-access/) | 0.2.2 | Python CLI | 基于[ddgs](https://github.com/deedy5/ddgs) 的联网搜索与网页抓取（`ddgs-web-search` / `ddgs-web-fetch`）             |
| [theme-commit](skills/theme-commit/)       | 0.1.1 | 纯提示词   | 工作区混杂多主题变更时，按逻辑主题分组、分批 git 提交                                                               |
| [deep-research](skills/deep-research/)     | 0.2.0 | 纯提示词   | 先校准问题再调研：环境检查→理解确认→档位推荐→确认门→research/ 目录交付 REPORT.md + REFERENCES.md 双文件         |
| [zero-coding](skills/zero-coding/)         | 0.2.0 | 纯提示词   | 从零启动个人项目并维持稳定开发：最小文档集（ZERO/SPEC/DECISIONS/AGENTS/README），按"捕获→固化→骨架→稳定开发"推进 |

各 skill 的调用方法、参数与排障见其目录内的 SKILL.md / README.md。

## 安装

四种方式任选其一：

**skills CLI**（跨 agent，支持 20+ 平台，自动 symlink）：

```bash
npx skills add GitZhiQing/agent-skills              # 全部 skill
npx skills add GitZhiQing/agent-skills/theme-commit # 单个 skill
```

**Claude Code plugin marketplace**（托管安装，随版本更新）：

```
/plugin marketplace add GitZhiQing/agent-skills
/plugin install ddgs-web-access@agent-skills         # 或 theme-commit / deep-research / zero-coding
```

**手动**（clone 后用仓库自带脚本链接到本机各 agent 的 skills 目录，Windows junction / Unix symlink，单一来源改一处全端生效）：

```bash
git clone https://github.com/GitZhiQing/agent-skills.git
cd agent-skills
bash scripts/skills-link.sh --all      # 卸载：bash scripts/skills-unlink.sh --all
bash scripts/skills-doctor.sh          # 巡检链接健康
```

默认覆盖本机已安装的主流 agent（目录存在才生效）：zcode、agents（Codex 新版 / Zed / Goose / Amp 等跨端通用目录）、claude、cursor、codex、copilot、gemini、opencode、windsurf、cline、roo、qwen、kilo、junie、trae。增删目标：仓库根写 `agents.local.conf`（每行「名称 路径」新增/覆盖、「!名称」禁用）；或一次性指定 `--agent <name>` / `--agent <name>=<path>`（任意目录，含其他项目的 `.agents/skills`）。详见 [docs/开发与维护规范.md](docs/开发与维护规范.md) §6。

**让 Agent 代装**（把下面这段发给任意支持 Agent Skills 的 coding agent，它会替你完成克隆、链接与验证）：

```text
帮我安装 GitHub 仓库 GitZhiQing/agent-skills 的全部 skills：
1. 把 https://github.com/GitZhiQing/agent-skills.git 克隆到本地并记住位置
2. 进入仓库根目录执行 bash scripts/skills-link.sh --all（链接到你所在 agent 的 skills 目录，幂等可重跑）
3. 执行 bash scripts/skills-doctor.sh 确认各 skill 显示 linked
```

## 快速使用

以 ddgs-web-access 为例（需 [uv](https://docs.astral.sh/uv/) >= 0.5，首次调用自动安装依赖）：

```bash
npx skills add GitZhiQing/agent-skills/ddgs-web-access
bash ~/.claude/skills/ddgs-web-access/bin/ddgs-web-search "python 3.13 asyncio" -m 5
bash ~/.claude/skills/ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

## 仓库维护（面向贡献者/维护者）

- 仓库结构、frontmatter 标准、版本与台账规则见 [docs/开发与维护规范.md](docs/开发与维护规范.md)。
- 改动后跑 `bash scripts/skills-lint.sh` 校验；维护脚本自身的测试用例见 [docs/维护脚本测试集.md](docs/维护脚本测试集.md)。
- 新增 skill：`bash scripts/skills-new.sh my-skill` 生成规范骨架。

## 许可与安全

- 本仓库以 [MIT](LICENSE) 发布（ddgs-web-access 目录内另附一份，供单独拷走使用）。
- **skill 含可执行代码**（`skills/*/bin/`、`skills/*/scripts/`），安装前请自行审阅。
- ddgs-web-access 依赖的上游 ddgs 声明"仅供教育目的使用"，使用时请遵守目标网站服务条款与 robots 协议。
