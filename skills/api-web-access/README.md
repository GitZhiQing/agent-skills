# api-web-access

基于 [Tavily](https://www.tavily.com/) 与 [Exa](https://exa.ai/) 官方 API 的联网搜索与网页抓取 CLI，为 AI coding agent 提供比免费元搜索更稳定的备援通道：自动主备、错误分类、限流退避、逐 URL 失败隔离与 15 分钟缓存。

| 工具 | 命令 | Provider |
| --- | --- | --- |
| `api-web-search` | `api-web-search` | Tavily `/search` → Exa `/search` |
| `api-web-fetch` | `api-web-fetch` | Tavily `/extract` → Exa `/contents` |

## 何时触发

- 点名 Tavily / Exa / API 搜索，或要求稳定可观测的 `web_search` / `web_fetch`；
- 免费元搜索通道连续超时 / 空结果或被限流，且已配置 API key；
- 不触发：未配置 key 的普通免费搜索（改用可用的免费搜索通道）、本地/内网页面、图片/新闻/视频搜索。

## 工作方式

- `--provider auto`（默认）顺序 Tavily → Exa；显式 provider 不跨厂商切换。
- 搜索结果归一为标题 / URL / 摘要；抓取输出 Markdown 或纯文本，支持 `--max-chars` 与 `--start` 分段。
- stdout 只放结果，stderr 单行记录 provider / retry / failover / cache，退出码 0/1/2。
- 完整错误与降级矩阵见 [references/error-matrix.md](references/error-matrix.md)。

## 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.5（Python >= 3.10 由 uv 托管；CLI 本体纯标准库）
- 可访问 `api.tavily.com` / `api.exa.ai`
- API key 至少其一：`TAVILY_API_KEY`、`EXA_API_KEY`
  - 推荐复制 `.env.example` 为同目录 `.env` 并填入 key；`.env` 已 gitignore
  - 进程环境变量优先于 `.env`；没有 `--api-key` 参数，key 不进入命令行
  - `API_WEB_ACCESS_ENV_FILE` 可指定另一个 env 文件路径（测试/隔离用）
  - Tavily key：<https://app.tavily.com>；Exa key：<https://dashboard.exa.ai>
  - 免费额度、价格与限速以官方控制台为准（快速变化，不做长期承诺）

## 安装

**让 Agent 代装（推荐）**：把下面这段原样发给你的 Agent。

```text
安装 https://github.com/GitZhiQing/agent-skills 仓库中的 api-web-access skill：
1) 先执行 `npx skills add "GitZhiQing/agent-skills/api-web-access"`，按输出完成安装；
2) 该方式不可用时，克隆仓库后执行 `bash scripts/skills-link.sh api-web-access`，再跑 `bash scripts/skills-doctor.sh` 确认链接健康；
3) 汇报安装位置与验证结果；失败时说明原因，不要跳过验证。
```

**Claude Code 插件市场**：`/plugin marketplace add GitZhiQing/agent-skills`，然后 `/plugin install api-web-access@agent-skills`。

**仓库内手动分发**：`bash scripts/skills-link.sh api-web-access`（卸载 `scripts/skills-unlink.sh api-web-access`），再跑 `bash scripts/skills-doctor.sh`。

## 使用

`<skill_dir>` 为本 skill 目录；命令不依赖当前工作目录。

```bash
# 搜索（默认 auto：Tavily -> Exa；启动器形式 / uv run 形式）
bash "<skill_dir>/bin/api-web-search" "python 3.13 asyncio" -m 5
uv run --project "<skill_dir>" api-web-search "python 3.13 asyncio" -m 5

# 固定 provider / JSON / 只输出 URL
uv run --project "<skill_dir>" api-web-search "..." --provider exa --format json
uv run --project "<skill_dir>" api-web-search "..." --provider tavily --urls

# 抓取正文（默认 Markdown，默认截断 5000 字符）
uv run --project "<skill_dir>" api-web-fetch "https://example.com"

# 长文分段读与批量抓取
uv run --project "<skill_dir>" api-web-fetch "https://example.com/long" --start 5000
uv run --project "<skill_dir>" api-web-fetch "https://a.com" "https://b.com"

# 绕过 15 分钟缓存（会消耗额外 API 额度）
uv run --project "<skill_dir>" api-web-search "..." --no-cache
```

PowerShell / cmd 可直接用 `bin/api-web-search.cmd` 与 `bin/api-web-fetch.cmd`。

## 稳定性与成本

- 429 读取 `Retry-After`（上限 30s）后重试一次；5xx/网络/协议错误 2s 重试一次；之后 auto 切换 provider。
- 401/403/402/432/433/434 不在同 provider 内重试；auto 直接尝试备援。
- 成功空结果 exit 0 且不切备援，避免双倍消耗。
- 批量抓取逐 URL 隔离：成功照常输出，失败项才给备援。
- 搜索与抓取缓存 15 分钟；`API_WEB_ACCESS_CACHE` 可改缓存目录，`--no-cache` 同时跳过读写。
- API 代理仅支持 http/https（`--proxy`）；CLI 本体不依赖第三方库。

## 与免费元搜索通道的关系

免费元搜索通道保留为存档 / 无密钥兜底。两个 provider 均 auth/quota 失败或 API 网络不可达时，本 skill exit 1 并说明原因；调用方可显式改用可用的免费网页搜索通道，不自动跨通道切换。

## 开发与测试

```bash
python -m unittest discover -s skills/api-web-access/tests   # 无网络、无 key
uv run --project skills/api-web-access api-web-search --help
uv run --project skills/api-web-access api-web-fetch --help
```

真实 API 用例读取 `TAVILY_API_KEY` / `EXA_API_KEY`，未设置自动跳过（跳过不算通过）。人工场景见 [docs/TESTS.md](docs/TESTS.md)。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [references/error-matrix.md](references/error-matrix.md) — 错误、重试、切换与降级矩阵
- [docs/TESTS.md](docs/TESTS.md) — 真实场景断言
- [docs/SPEC.md](docs/SPEC.md) — 设计决策与安全依据

许可：MIT（[LICENSE](LICENSE)）。使用 Tavily / Exa API 时遵守其服务条款与额度政策。
