# ds-web-access

基于 [DeepSeek Search / Fetch API](https://api-docs.deepseek.com/zh-cn/guides/search) 的联网搜索与网页 Markdown 抓取 CLI。Search 默认返回摘要与 `date / site_name / authority` 等来源元数据，可显式请求结果正文；Fetch 用于指定 URL 的正文抽取。

## 何时触发

- 用户点名 DeepSeek 搜索 / 抓取、**DS / ds 搜索、DS / ds 抓取、DS / ds search、DS / ds fetch**、`ds-web-search` / `ds-web-fetch`，或明确接受 DeepSeek 付费通道；
- 需要 DeepSeek 结果中的 `authority`、`rerank_score`、`date` 与来源元数据；
- 不触发：普通免费搜索、点名其他搜索 API、本地或内网 URL、未配置 key；仅说 DS / ds 但语境是 Nintendo DS、data science、数据集等无关主题。

## 工作方式

- 两个命令：`ds-web-search` 与 `ds-web-fetch`；stdout 只放结果，诊断走 stderr，退出码 0/1/2。
- Search 官方限制：query ≤128 字符、count 1–50、无分页；支持 `site:`、`-site:`、`"..."`、`lang:`、`after:`、`before:`。
- Fetch 一次一个官方请求；CLI 多 URL 需 `--yes`，每个成功 URL 独立计费。
- 401/402/429 与 Fetch 403/404 分开分类；仅 408/429/5xx/网络/协议错误重试一次。
- Search 非空结果缓存 10 分钟，Fetch 成功正文缓存 15 分钟；`--no-cache` 跳过读写。

## 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.5（Python >= 3.10）
- 可访问 `https://api.deepseek.com`
- `DEEPSEEK_API_KEY` 必填：
  - 推荐复制 `.env.example` 为同目录 `.env` 并填入 key；`.env` 已 gitignore；
  - 进程环境变量优先于 `.env`；
  - 没有 `--api-key` 参数，key 不进入命令行；
  - 获取 key：<https://platform.deepseek.com/api_keys>

**计费提醒（官方文档，2026-11-11 核验）**：Search 与 Fetch 分别按成功请求计费，各 5 元 / 1,000 次；Search 空结果与失败请求不计费，Fetch 只有返回正文才计费。`count` 不影响价格。实际账单以 DeepSeek 控制台为准。

## 安装

把下面这段原样发给你的 Agent：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 ds-web-access skill：优先执行 `npx skills add "GitZhiQing/agent-skills/ds-web-access"`；不可用则克隆仓库后执行 `bash scripts/skills-link.sh ds-web-access`，再跑 `bash scripts/skills-doctor.sh` 验证并汇报结果。
```

其他分发方式见仓库根 README；本 skill 可独立安装和使用，不要求同时安装其他 skill。

## 使用

`<skill_dir>` 为本 skill 目录；命令不依赖当前工作目录。

```bash
# 搜索（默认 count=10，不带正文）
bash "<skill_dir>/bin/ds-web-search" "DeepSeek site:github.com lang:zh after:2026" -n 10

# JSON 与只输出 URL
uv run --project "<skill_dir>" ds-web-search "Python 3.13" -n 5 --format json
uv run --project "<skill_dir>" ds-web-search "Python 3.13" -n 5 --urls

# 显式请求搜索结果正文，并限制输出
uv run --project "<skill_dir>" ds-web-search "Python 3.13" --need-content --max-content-chars 4000

# 抓取单页 Markdown
uv run --project "<skill_dir>" ds-web-fetch "https://example.com"

# 长文续读
uv run --project "<skill_dir>" ds-web-fetch "https://example.com/long" --start 5000

# 批量抓取（每个成功 URL 独立计费，必须 --yes）
uv run --project "<skill_dir>" ds-web-fetch "https://a.com" "https://b.com" --yes
```

JSON Search 输出保留官方字段，并附加 skill 派生的 `citation` 对象；`citation` 不是 DeepSeek 官方字段。

## 排障

- `MissingKeyError`：设置 `DEEPSEEK_API_KEY` 或配置 `<skill>/.env`。
- HTTP 401：key 无效；不要反复重试。
- HTTP 402：余额不足；充值后再试。
- HTTP 429：限流；CLI 会按 `Retry-After` 或 2 秒退避重试一次。
- Fetch 403：安全策略拒绝；404：无可抽取正文；均不重试。
- 完整矩阵见 [references/error-matrix.md](references/error-matrix.md)。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [references/error-matrix.md](references/error-matrix.md) — 错误、重试、缓存与计费
- [docs/TESTS.md](docs/TESTS.md) — 行为断言与真实场景
- [docs/SPEC.md](docs/SPEC.md) — 设计决策、API 事实与开放问题
- [LICENSE](LICENSE) — MIT

许可：MIT。使用 DeepSeek API 时遵守其服务条款与计费政策。
