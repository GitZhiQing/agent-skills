# agent-skills

个人 AI Coding 过程中沉淀的 Agent Skills 集合，遵循 [Agent Skills 开放规范](https://agentskills.io/specification)，可被 Claude Code、Codex、ZCode、DeepSeek Harness 等支持该格式的 Agent 加载和使用。

## Skills

| Skill | 说明 |
| --- | --- |
| [ddgs-web-access](skills/ddgs-web-access/) | 免费无密钥元搜索与网页抓取（冻结维护，不影响既有命令） |
| [ds-web-access](skills/ds-web-access/) | 基于 DeepSeek Search / Fetch API 的联网搜索与网页 Markdown 抓取，带付费成本防护与本地缓存 |
| [deep-research](skills/deep-research/) | 先校准再调研：目标、计划与输出目录经用户确认后执行，无法确认则停止；交付 REPORT + REFERENCES + META，支持源码调研 |
| [theme-commit](skills/theme-commit/) | 先计划预览并用提问工具确认，再按主题分组提交 |
| [zero-coding](skills/zero-coding/) | 从零启动个人项目的轻量工作流 |
| [session-handoff](skills/session-handoff/) | 生成跨会话交接提示词 |
| [video-insight](skills/video-insight/) | 拉片级视频内容与画面分析 |
| [md2pdf](skills/md2pdf/) | Markdown 转精美 PDF |
| [windows-disk-cleanup](skills/windows-disk-cleanup/) | Windows 磁盘/文件夹扫描、离线可勾选 HTML 报告与安全删除 |

各 skill 的用法、外部环境要求与可选协作见其目录内的 `README.md` / `SKILL.md`；版本号以 `SKILL.md` frontmatter 为准。每个 skill 均可独立安装和使用。

## 安装

把这句交给你的 Agent（安装全部 skill）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的全部 skill：优先 `npx skills add "GitZhiQing/agent-skills"`；不可用则 clone 后执行 `bash scripts/skills-link.sh --all`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

只装一个时，把「全部 skill」换成 skill 名，`--all` 换成同一个名字（如 `windows-disk-cleanup`）。

### skills CLI

```bash
npx skills add GitZhiQing/agent-skills                       # 全部
npx skills add GitZhiQing/agent-skills/windows-disk-cleanup  # 单个
```

### Claude Code 插件市场

```text
/plugin marketplace add GitZhiQing/agent-skills
/plugin install windows-disk-cleanup@agent-skills
```

### 手动分发

clone 后把 skill 链接到本机 agent 目录（Windows junction / Unix symlink，单一来源，`git pull` 后全端生效）：

```bash
git clone https://github.com/GitZhiQing/agent-skills.git
cd agent-skills
bash scripts/skills-link.sh --all              # 全部；单个换成 skill 名
bash scripts/skills-doctor.sh                  # 链接健康检查
```

卸载：`bash scripts/skills-unlink.sh --all`（单个同样换成 skill 名）。

## 快速使用

安装后直接对 Agent 描述任务即可：

- “帮我调研一下 X，最好带源码证据”
- “把这次改动按主题分开提交”
- “分析这条视频的文案和画面节奏”
- “把这份 Markdown 转成 PDF，用 kimi 主题”
- “清理一下 C 盘，先扫描出报告让我勾选”

具体用法见各 skill 目录的 `README.md`。

## 可选组合

每个 skill 独立安装、独立触发；以下是可选工作流示例，不是安装前置、运行依赖或固定调用顺序。

- **调研交付**：`deep-research` 可使用宿主原生 web 工具或任一已安装搜索 skill 完成调研；如需排版，可再调用 `md2pdf`。
- **项目启动**：`zero-coding` 可独立完成立项与切片；如需分主题提交或换会话交接，可分别配合 `theme-commit`、`session-handoff`。
- **内容复盘**：`video-insight` 可独立产出分析；如需 PDF 归档，可再调用 `md2pdf`。
- **磁盘清理**：`windows-disk-cleanup` 独立完成扫描、勾选报告、预演与安全删除。

## 文档

| 文档 | 读者 | 用途 |
| --- | --- | --- |
| [AGENTS.md](AGENTS.md) | AI 会话 | 运行、验证、完成定义 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献者 | 最短上手路径与自检清单 |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | 维护者 | 目录结构、frontmatter、版本、分发、脚本规则、提交规范 |
| [docs/SCRIPT-TESTS.md](docs/SCRIPT-TESTS.md) | 维护者 | `scripts/` 回归用例 |
| [spec/agent-skills-spec.md](spec/agent-skills-spec.md) | 维护者 | 官方规范指针与本仓库加严项 |
| [template/](template/) | 维护者 | 新 skill 骨架 |
| 各 skill 目录内的 `README.md` / `docs/` | 使用者 | 用法、设计与测试集 |

## 许可与安全

- 本仓库以 [MIT](LICENSE) 发布；每个 skill 目录内另附同版 MIT 许可，便于单独拷走使用。
- **skill 含可执行代码**（`skills/*/bin/`、`skills/*/scripts/`），安装前请自行审阅。
- ddgs-web-access 依赖的上游 ddgs 声明"仅供教育目的使用"，使用时请遵守目标网站服务条款与 robots 协议。
- md2pdf 首次 `fetch` 会在运行时下载字体切片、Paged.js 与 KaTeX，许可与来源见该 skill 的 `README.md`。
