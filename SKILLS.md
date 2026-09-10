# Skills 台账

本项目全部 skill 的元信息记录：简介、依赖、分发链接、文档索引与状态。新增或变更 skill 后同步维护本表；格式标准与更新时机见 [docs/开发与维护规范.md](docs/开发与维护规范.md) §5。信息核实日期：2026-09-10。

## 总览

| Skill | 版本 | 类型 | 简介 | 斜杠调用 | 分发状态 |
| --- | --- | --- | --- | --- | --- |
| [ddgs-web-access](ddgs-web-access/) | 0.2.0 | Python CLI | 基于 ddgs 的联网搜索与网页抓取（`ddgs-web-search` / `ddgs-web-fetch`） | `/ddgs-web-access` | 已链接三端 |
| [theme-commit](theme-commit/) | 0.1.0 | 纯提示词 | 工作区混杂多主题变更时，按逻辑主题分组、分批 git 提交 | `/theme-commit`（链接后） | 已链接三端 |
| [deep-research](deep-research/) | 0.1.0 | 纯提示词 | 先校准问题再消耗调研资源，产出调研报告 + 素材登记簿双文档 | `/deep-research`（链接后） | 已链接三端 |

## 明细

### ddgs-web-access

| 项 | 值 |
| --- | --- |
| 目录 / name | `ddgs-web-access/`（目录名与 frontmatter `name` 一致） |
| 版本 | 0.2.0（2026-09-10 由 0.1.0 升级：稳定性内置 + SKILL.md 精简） |
| 类型 / 分类 | Python CLI，category: web |
| 依赖 | uv >= 0.5（托管 Python >= 3.10）；ddgs >= 9.15,<10 + markdownify；网络访问，首次调用联网装依赖约 30-60 秒 |
| 命令入口 | `bin/ddgs-web-search`、`bin/ddgs-web-fetch`（Windows 用 `.cmd` 变体；等价 `uv run --project` ） |
| 安装链接 | junction 指向本仓库：`~/.zcode/skills/`、`~/.agents/skills/`、`~/.claude/skills/` 三处，2026-09-10 验证生效；管理脚本 `scripts/install.sh` / `uninstall.sh`（本仓库内分发统一用根 `scripts/skills-link.sh`） |
| 文档 | [SKILL.md](ddgs-web-access/SKILL.md)、[README.md](ddgs-web-access/README.md)、[需求与设计文档 v0.6](ddgs-web-access/docs/需求与设计文档.md)、[测试集 v1.1](ddgs-web-access/docs/测试集.md) |
| git | 已入库（`52eef5f`，运行产物由自带 .gitignore 排除） |
| 许可 | MIT（上游 ddgs 声明仅供教育目的，遵守目标站 ToS 与 robots） |
| 状态 | 稳定，三端可用 |

### theme-commit

| 项 | 值 |
| --- | --- |
| 目录 / name | `theme-commit/`（目录名与 frontmatter `name` 一致，2026-09-10 规范化，原 `thematic_commit`） |
| 版本 | 0.1.0（2026-09-10 补 `metadata.version` 与测试集，纳入统一规范） |
| 类型 / 分类 | 纯提示词（无运行时、无依赖），category: git |
| 触发 | 用户要求"提交一下""把改动分开提交""整理提交历史"且变更混杂多主题时 |
| 安装链接 | 已链接三端（`~/.zcode/skills/`、`~/.agents/skills/`、`~/.claude/skills/`），2026-09-10 由 `scripts/skills-link.sh` 建立 |
| 文档 | [SKILL.md](theme-commit/SKILL.md)（自身即主要内容）、[测试集 v1.0](theme-commit/docs/测试集.md) |
| git | 已入库（`f3be3d0`） |
| 许可 | MIT（仓库根 [LICENSE](LICENSE)） |
| 状态 | 可用，三端已分发 |

### deep-research

| 项 | 值 |
| --- | --- |
| 目录 / name | `deep-research/`（目录名与 frontmatter `name` 一致） |
| 版本 | 0.1.0（2026-09-10 首版实现，同日补 `metadata.version`） |
| 类型 / 分类 | 纯提示词（无运行时、无依赖），category: research |
| 触发 | 用户提出需联网多源交叉验证的调研需求，或术语歧义 / 领域冷门 / 表述模糊时 |
| 依赖 | 宿主须具备 web 搜索 / 抓取能力（原生工具或 ddgs-web-access）；具体工具由阶段 0 运行时探测确认，不硬绑 |
| 安装链接 | 已链接三端（`~/.zcode/skills/`、`~/.agents/skills/`、`~/.claude/skills/`），2026-09-10 由 `scripts/skills-link.sh` 建立 |
| 文档 | [SKILL.md](deep-research/SKILL.md)、[需求与设计文档 v0.2](deep-research/docs/需求与设计文档.md)、[竞品调研 v0.1](deep-research/docs/竞品调研.md)、[测试集 v1.0](deep-research/docs/测试集.md)、灵感源 [ZERO.md](deep-research/docs/ZERO.md) |
| git | 待入库 |
| 许可 | MIT（仓库根 [LICENSE](LICENSE)） |
| 状态 | 已实现，待首轮真实调研验证与档位取值校准（设计文档开放问题 O2） |

## 维护约定

标准、格式与流程见 [docs/开发与维护规范.md](docs/开发与维护规范.md)（新增 skill 流程见其 §9）；机器可校验项由 `bash scripts/skills-lint.sh` 强制，链接健康由 `bash scripts/skills-doctor.sh` 巡检。
