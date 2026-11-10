# ds-web-access 真实场景测试集

| 文档版本 | v1.1 | 日期 | 2026-11-11 | 适用版本 | ds-web-access v0.1.1 | 定位 | 真实 API / 安装场景验证；离线协议断言见 `tests/` 并入 CI |
| --- | --- | --- | --- | --- | --- | --- | --- |

## 1. 运行方式

- 命令在仓库根执行；`▶` 为命令，`=` 为断言。
- 真实场景需 `DEEPSEEK_API_KEY`（进程环境变量或 `skills/ds-web-access/.env`）。key 不得写入命令、文档或输出。
- **付费提醒**：Search 与 Fetch 各按成功请求计费（官方 2026-11-11：5 元 / 1,000 次成功请求）。调试用 `count=3`；多 URL Fetch 必须评估成本。
- 自动化基线：`python -m unittest discover -s skills/ds-web-access/tests`。无 key 时真实 API 用例自动跳过，跳过不算通过。

## 2. 授权与边界（A）

### A-1 缺 key 诚实失败

```
▶ env -u DEEPSEEK_API_KEY DS_WEB_ACCESS_ENV_FILE=skills/ds-web-access/tests/.env.absent \
    uv run --project skills/ds-web-access ds-web-search "Python 3.13" -n 3
```

- = exit 1，stderr 含 `MissingKeyError` 与 `DEEPSEEK_API_KEY`
- = stdout 为空；无 traceback、无伪造结果、无网络请求

### A-2 `.env` 装载与环境变量优先

场景：将 `.env.example` 复制为 `skills/ds-web-access/.env` 并填入有效 key。

```
▶ env -u DEEPSEEK_API_KEY uv run --project skills/ds-web-access ds-web-search "Python 3.13" -n 3
▶ DEEPSEEK_API_KEY=<进程内有效 key> uv run --project skills/ds-web-access ds-web-search "Python 3.13" -n 3
```

- = 第一条读取 `.env` 成功执行
- = 第二条证明进程环境变量优先
- = 输出无 key 明文；`git check-ignore -v skills/ds-web-access/.env` 命中
- = `.env.example` 不被忽略且值为空

### A-3 本地参数错误不发请求

```
▶ uv run --project skills/ds-web-access ds-web-search "" -n 3
▶ uv run --project skills/ds-web-access ds-web-search "x" -n 51
▶ uv run --project skills/ds-web-access ds-web-fetch "file:///etc/hosts"
```

- = 均为本地校验失败，exit 2
- = 不产生计费请求，stdout 为空

## 3. 搜索场景（S）

### S-1 基础搜索与来源元数据

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-search "Python 3.13 release notes" -n 5
```

- = exit 0；stderr 含 `endpoint=search`、`results=N`、`billing=inferred`
- = 每个结果含标题 / URL；有元数据时显示 date、site_name、authority、rerank_score
- = 默认不显示 `content`
- = stdout 无 key、无 JSON 包装

### S-2 JSON schema 与 citation

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-search "Python 3.13" -n 3 --format json
```

- = stdout 为 JSON 数组，每项保留官方字段 `rerank_score/title/url/snippet/summary/content/site_name/site_icon/date/authority`
- = 每项含派生 `citation`，字段来自 `title/url/site_name/date`
- = 不出现官方不存在的 `source` / `references` 伪装字段

### S-3 显式正文与截断

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-search "Python 3.13" --need-content --max-content-chars 300
```

- = 请求 payload 的 `need_content=true`
- = text 输出包含 `content:`；超过 300 字符时提示截断
- = 同等 query 下 `--urls` 每行一个 URL

### S-4 空结果

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-search "zzuuppqq unlikely 261111" -n 3
```

- = 官方返回空数组时 exit 0
- = stdout 为空或 `[]`；stderr 说明空结果不计费
- = 不写缓存；立即复跑仍可发请求（调试时避免反复执行）

## 4. 抓取场景（F）

### F-1 单页 Markdown

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-fetch "https://example.com"
```

- = exit 0；stdout 为 Markdown 正文，可含页面标题
- = stderr 含 `endpoint=fetch`、`billing=inferred`
- = 输出无 key

### F-2 长文分段与 JSON

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-fetch "https://example.com" --max-chars 100
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-fetch "https://example.com" --start 100 --format json
```

- = 第一条截断并提示续读 `--start`
- = 第二条 JSON 含 `url/ok/title/content/truncated/next_start`

### F-3 批量成本确认与失败隔离

```
▶ DEEPSEEK_API_KEY=... uv run --project skills/ds-web-access ds-web-fetch "https://example.com" "https://example.invalid"
```

- = 未加 `--yes` 时 exit 2，并提示每个成功 URL 独立计费
- = 加 `--yes` 后成功项照常输出，失败项有单行错误
- = 全部尝试后仍有失败则 exit 1

## 5. 错误与重试（E）

### E-1 无效 key

```
▶ DEEPSEEK_API_KEY=invalid uv run --project skills/ds-web-access ds-web-search "Python" -n 3
```

- = HTTP 401 时 exit 1，错误类别为 auth
- = 不重试；错误信息无 key 明文

### E-2 余额不足

```
▶ DEEPSEEK_API_KEY=<余额不足 key> uv run --project skills/ds-web-access ds-web-search "Python" -n 3
```

- = HTTP 402 时 exit 1，类别 balance，不当初限流重试

### E-3 限流重试

```
▶ <构造或模拟 HTTP 429 + Retry-After: 3> ds-web-search "Python" -n 3
```

- = stderr 记录一次 retry，延迟按 Retry-After 且不超过 30s
- = 仍失败则 exit 1；成功则 exit 0

### E-4 Fetch 403 / 404

```
▶ <安全策略拒绝 URL> ds-web-fetch "<url>"
▶ <无可用正文 URL> ds-web-fetch "<url>"
```

- = 分别报 security / no_content，均不重试
- = 批量场景其他 URL 继续

## 6. 缓存（C）

### C-1 Search 与 Fetch 缓存隔离

```
▶ uv run --project skills/ds-web-access ds-web-search "cache probe 261111" -n 3 --cache-dir /tmp/ds-cache
▶ <同命令立即复跑>
▶ uv run --project skills/ds-web-access ds-web-fetch "https://example.com" --cache-dir /tmp/ds-cache
```

- = Search 第二次 `cache=hit`
- = Fetch 不复用 Search 缓存
- = `--no-cache` 同时跳过读写
- = 缓存文件不含 key

## 7. 安装分发（I）

```
▶ bash scripts/skills-link.sh ds-web-access && bash scripts/skills-doctor.sh
▶ bash "skills/ds-web-access/bin/ds-web-search" --help
▶ bash "skills/ds-web-access/bin/ds-web-fetch" --help
```

- = doctor 中 ds-web-access 为 linked，无 broken
- = 两个启动器 exit 0，帮助完整，不依赖当前目录

## 8. 触发校准（静态，2026-11-11）

执行方式：静态评审 description 中的能力与近邻反例，未运行多轮模型触发率。

### 应触发

| # | 用户说法 | 期望 | 理由 |
| --- | --- | --- | --- |
| 1 | 用 DeepSeek 搜索一下 Python 3.13 | 触发 | 点名 DeepSeek Search |
| 2 | 用 ds-web-search 查这个关键词 | 触发 | 点名命令 |
| 3 | 用 DeepSeek fetch 这个 URL 的 Markdown | 触发 | 点名 DeepSeek Fetch |
| 4 | 走 DeepSeek 付费通道抓这个网页 | 触发 | 显式接受付费通道 |
| 5 | DeepSeek search 这个问题并给来源日期 | 触发 | 需要 date/authority 元数据 |
| 6 | 用 after:2026 和 site:github.com 做 DeepSeek 搜索 | 触发 | 官方查询语法 |
| 7 | 用 DeepSeek 搜索并直接带每个结果的正文 | 触发 | 对应 `--need-content` |
| 8 | DeepSeek search 这个主题，只要 URL 列表 | 触发 | 对应 `--urls` |
| 9 | 用 ds 搜一下 Python 3.13 | 触发 | 小写 ds + 搜索简写 |
| 10 | DS fetch 这个链接的正文 | 触发 | 大写 DS + fetch 简写 |

### 不应触发

| # | 用户说法 | 期望 | 理由 |
| --- | --- | --- | --- |
| 1 | 普通搜索一下这个关键词 | 不触发 | 未点名 DeepSeek，应走免费通用搜索 |
| 2 | 用 Tavily 搜索 | 不触发 | 点名其他 API |
| 3 | 用 Exa 抓网页 | 不触发 | 点名其他 API |
| 4 | 没配置 key 也先试一下 DeepSeek | 不触发 | 缺 `DEEPSEEK_API_KEY` |
| 5 | 抓取 http://127.0.0.1:8000/docs | 不触发 | 本地 URL 不支持 |
| 6 | 帮我搜索相关图片 | 不触发 | 非网页文本搜索 |
| 7 | 抓取 ftp://example.com/file | 不触发 | 非 http/https |
| 8 | 帮我看这个本地 Markdown 文件 | 不触发 | 本地文件读取，不是网页抓取 |
| 9 | NDS 上怎么运行这个游戏 | 不触发 | Nintendo DS 语境，不是 DeepSeek |
| 10 | ds 课程的数据集怎么清洗 | 不触发 | data science / 数据集语境，不是搜索抓取 |

## 9. 结果记录

| 场景 | 日期 | 环境 | 结果 | 说明 |
| --- | --- | --- | --- | --- |
| 离线单测 | 2026-11-11 | Python 3.13 / Git Bash / uv | 通过 23 条 | `python -I -m unittest discover -s skills/ds-web-access/tests`；1 条真实用例跳过 |
| S-1 / F-1 | 2026-11-11 | 用户提供 key，仅进程环境注入 | 通过 | 1 次 search（count=3）+ 1 次 fetch `https://example.com`；约 0.9s；输出无 key |
| A-2 | 2026-11-11 | `skills/ds-web-access/.env` 已配置 | 通过 | CLI 无进程 key 时可从 `.env` 读取；3 条结果含 citation；输出无 key；`git check-ignore` 命中 |
