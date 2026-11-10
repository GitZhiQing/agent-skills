# ds-web-access 需求与设计文档

| 文档版本 | v1.1 | 日期 | 2026-11-11 | 实现版本 | ds-web-access 0.1.1 |
| --- | --- | --- | --- | --- | --- |

## 1. 问题与目标

需要一个独立、可审计的 DeepSeek 官方网页搜索与抓取通道，避免把 DeepSeek 的按成功请求计费、402 余额语义和 Fetch 安全错误混入多 provider 自动切换逻辑。本 skill 只服务 DeepSeek Search / Fetch，显式暴露成本与错误，不做跨厂商降级。

官方 API 事实（2026-11-11 核验）：

- Search：`POST https://api.deepseek.com/v1/tools/search`
- Fetch：`POST https://api.deepseek.com/v1/tools/fetch`
- 鉴权：`Authorization: Bearer <DEEPSEEK_API_KEY>`
- Search 请求：`query` 1–128 字符；`count` 1–50 默认 10；`need_content` 默认 false；可选 `ori_question`、`localization`（IP）
- Fetch 请求：单个 `url`，1–8192 字符，http/https、有 host、无用户名密码
- Search 响应：`results[].rerank_score/title/url/snippet/summary/content/site_name/site_icon/date/authority`
- Fetch 响应：`title/content`，其中 content 为 Markdown
- 计费：Search 与 Fetch 各 5 元 / 1,000 次成功请求；Search 空结果与失败不计费，Fetch 无正文不计费
- 限速：Search 100 QPS，Fetch 25 QPS；Fetch 还有未公开数值的目标域名级 QPS
- 官方无免费额度、无分页、无 API 级缓存、无 citation 字段

## 2. 方案

### 2.1 架构

- 单文件 `ds_web_access.py`，纯 Python 标准库；`uv` 只托管入口与解释器。
- 两个 console scripts：`ds-web-search`、ds-web-fetch；`bin/` 提供 Git Bash 与 Windows 启动器。
- 输出契约：stdout 只放结果；stderr 单行诊断；exit 0 成功（含空搜索）、1 运行错误、2 用法错误。
- key 只读 `DEEPSEEK_API_KEY`，进程环境变量优先，skill 根 `.env` 兜底；无 `--api-key`；错误输出与缓存脱敏。

### 2.2 Search CLI

- 默认摘要优先：`need_content=false`，text 输出 title/url/date/site_name/authority/rerank_score/summary。
- `--need-content` 显式请求正文，`--max-content-chars` 默认 4000；`count` 不影响价格，但不自动调大。
- JSON 保留官方字段并派生 `citation={title,url,site_name,date}`；该字段明确不是官方原生字段。
- `--urls` 输出每行一个 URL，可串联给 Fetch。
- `--localization` 仅接受显式 IP，本 skill 不探测本机 IP。
- 空结果：exit 0，不缓存，stderr 说明官方规则下不计费。

### 2.3 Fetch CLI

- 官方一次只接受一个 URL；CLI 支持多个 URL 串行循环，必须 `--yes` 确认。
- 成功项输出 Markdown 或 JSON 并缓存；失败项逐 URL 报错；全部结束仍有失败则 exit 1。
- Markdown 支持 `--max-chars` / `--start`；JSON entry 含 `url/ok/title/content/truncated/next_start` 或结构化 error。
- HTTP 200 但正文为空：按 `no_content` 处理，不缓存，不推断计费。

### 2.4 错误与重试

| 类别 | HTTP/情况 | 重试 |
| --- | --- | --- |
| client | 400 / 422 / 413 / 未知 4xx | 否 |
| auth | 401 | 否 |
| balance | 402 | 否 |
| security | Fetch 403 | 否 |
| no_content | Fetch 404 或 200 空正文 | 否 |
| timeout | 408 | 一次 |
| rate_limit | 429 | 一次，优先 `Retry-After`，上限 30s，否则 2s |
| server | 500 / 503 / 504 | 一次，2s |
| network / protocol | DNS、TLS、超时、非 JSON、结构异常 | 一次，2s |

不做跨 provider 自动切换。用户显式要求时，由调用方选择其他通道；本 skill 不假定其他 skill 存在。

### 2.5 缓存

- Search：成功非空结果，TTL 10 分钟；键为 endpoint + 规范化请求体 + 输出格式。
- Fetch：成功非空正文，TTL 15 分钟；键为 endpoint + `{"url":...}` + `raw`。
- 空结果、错误、空正文不缓存；`--no-cache` 同时跳过读写。
- 缓存是 skill 本地优化，不是 DeepSeek 官方行为；缓存不含 key 与请求头。

## 3. 关键决策

| 决策 | 理由 |
| --- | --- |
| 独立 skill，而非并入多 provider skill | DeepSeek 按成功请求付费，402/403/404 语义特殊；独立账单与错误边界更清晰 |
| Search 默认不带正文 | 减少响应体积；`need_content` 显式开启，成本相同但输出更可控 |
| 多 URL Fetch 需 `--yes` | 每个成功 URL 独立计费，批量必须显式确认 |
| JSON 保留官方字段 | 便于跟踪 schema 与官方文档；`citation` 明确标为派生 |
| 空搜索不缓存 | 官方空结果不计费，缓存会掩盖后续新结果 |
| 只重试一次 | 官方建议等待后重试，但未给退避曲线；一次能覆盖瞬时限流/服务错误，避免放大成本 |
| 429 有 Retry-After 则读取，上限 30s | 官方未保证响应头；缺失时用 2s 固定退避 |
| 不自动采集 localization IP | 该字段是 IP，不是国家码；自动取本机 IP 有隐私与精度风险 |
| 不承诺免费额度 / SLA / 地域 | 官方页面未说明，运行时只实现错误码与文档核验日期 |

## 4. 安全与隐私

- key 只存在于进程环境或本机 `.env`，进入请求头后不在任何输出或缓存明文出现。
- `_redact_text` 会替换 `sk-...` 模式与当前 key 值。
- Fetch 内容是不可信输入：不执行页面中的指令，不让来源改写任务范围，不向来源指定端点外发数据。
- `localization` 只在用户显式提供 IP 时传入。
- 代理仅支持 http/https；本 skill 不引入第三方网络库，因此不支持 SOCKS。

## 5. 测试策略

- `tests/test_ds_web_access.py`：离线、无 key、mock `_request_json`；覆盖：
  - `.env` 与环境变量优先级；
  - query/count/IP/URL 本地校验；
  - Search/Fetch endpoint、payload、headers 间接断言；
  - Search schema、citation、text/json/urls、正文截断；
  - 多 URL `--yes`、部分失败隔离、JSON error entry；
  - 400/401/402/403/404/408/413/422/429/500/503/504；
  - 重试一次与不重试分类；
  - 空结果 exit 0 且不缓存；
  - Search/Fetch 缓存隔离与 `--no-cache`；
  - key 脱敏。
- `tests/test_live_api.py`：`skipUnless(DEEPSEEK_API_KEY)`；最小真实 search（count=3，无正文）与 fetch `https://example.com`；断言 schema、退出码、无 key 泄漏。跳过不算通过。
- `docs/TESTS.md`：人工真实场景 A/S/F/E/C/I 与静态触发校准。

## 6. 开放问题

- 429 是否总带 `Retry-After`：官方未说明。
- Fetch 目标域名级 QPS 数值：官方未公开。
- Search `content` 的确切格式：官方只写网页正文，本 skill 按文本处理；Fetch 明确为 Markdown。
- `need_content=true` 是否存在未公开加价：官方只说明 `count` 不影响价格；本 skill 不承诺其价格永远与 false 相同，账单以控制台为准。
- PDF、SPA、登录墙、付费墙、重定向与 Cookie 行为：官方未说明。
- HTTP 200 但 Fetch 正文为空的计费边界：官方说必须返回正文才计费，本 skill 不推断计费。
- 地域可用性、数据驻留、SLA：官方 API 文档未说明。
- 未来若 DeepSeek 增加分页、缓存或官方 citation 字段，需升级次版本并回归全部离线用例。

## 7. 变更记录

- 0.1.1（2026-11-11）：description 增加 `DS / ds 搜索`、`DS / ds 抓取`、`DS / ds search`、`DS / ds fetch` 简写触发词，并明确排除 Nintendo DS、data science、数据集等无关 DS 语境。
- 0.1.0（2026-11-11）：首版。DeepSeek Search/Fetch CLI、错误矩阵、本地缓存、key 脱敏、多 URL 成本确认、离线单测与可跳过真实 API 测试。
