# ds-web-access 错误与降级矩阵

按需读取：CLI 返回非 0、stderr 出现 retry / billed、需要解释 DeepSeek 错误或决定是否重试时读本文。官方资料核验日期：2026-11-11。

## 1. 端点与请求

| 能力 | 端点 | 请求 | 说明 |
| --- | --- | --- | --- |
| Search | `POST https://api.deepseek.com/v1/tools/search` | `query` 必填 1–128 Unicode 字符；`count` 1–50 默认 10；`need_content` 默认 false；可选 `ori_question`、`localization` | 支持官方查询语法 `site:`、`-site:`、`"..."`、`lang:`、`after:`、`before:`；无分页 |
| Fetch | `POST https://api.deepseek.com/v1/tools/fetch` | `url` 必填，1–8192 字符，http/https、有 host、无用户名密码 | 一次一个 URL；CLI 多 URL 会循环请求，每个成功 URL 独立计费 |

鉴权：`Authorization: Bearer <DEEPSEEK_API_KEY>`；`Content-Type: application/json`。key 只进请求头，绝不进 URL、CLI 参数、stdout、stderr 或缓存。

## 2. 计费事实与本地推断

| 事实 | 官方规则 |
| --- | --- |
| Search 单价 | 5 元 / 1,000 次成功请求 |
| Fetch 单价 | 5 元 / 1,000 次成功请求 |
| Search 计费条件 | HTTP 200 且 `results` 非空 |
| Fetch 计费条件 | HTTP 200 且返回网页正文 |
| 不计费 | 失败、超时、Search 空结果 |
| `count` | 不影响单次请求价格 |
| token | Search/Fetch 不按模型 token 计费，也不返回 usage |

stderr 的 `billing=inferred` 规则：

- Search：非空结果 → `yes`；空结果 → `no`。
- Fetch：成功且正文非空 → `yes`。
- 该字段仅为本地成本可观测性，不是官方响应字段，不能替代控制台账单。

## 3. HTTP / 运行错误矩阵

| 情况 | 分类 | 同 endpoint 重试 | 退出码 | 动作 |
| --- | --- | --- | --- | --- |
| 本地 query/count/URL 非法 | usage | 否，不发请求 | 2 | 修正参数 |
| 400 / 422 | client | 否 | 1 | 输出官方 message；通常请求字段或取值错误 |
| 413 | client | 否 | 1 | 请求体过大；缩小请求 |
| 401 | auth | 否 | 1 | 检查 `DEEPSEEK_API_KEY`；不是余额问题 |
| 402 | balance | 否 | 1 | 充值后再试；不得当限流重试 |
| Fetch 403 | security | 否 | 1，批量继续 | DeepSeek 安全策略拒绝该 URL |
| Fetch 404 | no_content | 否 | 1，批量继续 | URL 不可用、被站点阻止、类型不支持或无可抽取 Markdown |
| 408 | timeout | 是，一次 | 1 | 退避后重试 |
| 429 | rate_limit | 是，一次 | 1 | 有 `Retry-After` 则读取，无则 2s；上限 30s |
| 500 / 503 / 504 | server | 是，一次 | 1 | 2s 后重试 |
| DNS / TLS / 网络 / 客户端超时 | network | 是，一次 | 1 | 2s 后重试 |
| 非 JSON / 结构异常 | protocol | 是，一次 | 1 | 2s 后重试 |
| Search 200 + 空数组 | empty | 否 | 0 | stderr 说明空结果；不缓存 |
| Fetch 200 + 空 content | no_content | 否 | 1 | 视为无可抽取正文，不缓存 |
| 未知 4xx | client | 否 | 1 | 保留官方 message；可能 API 变更 |

注意：

- Search 的 403/404 未在官方 Search 指南中列出；本 skill 按未知 4xx 处理，不重试。
- Fetch 可能还有目标域名级 QPS 限制，同样返回 429；批量抓取保持串行并遵守重试矩阵。
- 官方文档未保证 429 带 `Retry-After`；本 skill 有则读，无则固定 2s。

## 4. 缓存

| 操作 | 缓存条件 | TTL | 键 |
| --- | --- | --- | --- |
| Search | HTTP 200 且 `results` 非空，归一化后仍有 URL | 10 分钟 | endpoint + 规范化请求体 + 输出格式 |
| Fetch | HTTP 200 且 `content` 非空 | 15 分钟 | endpoint + `{"url":...}` + `raw` |

- `--no-cache` 同时跳过读和写。
- 空结果、错误、空正文不缓存。
- 缓存目录默认 `<skill>/.cache`，`DS_WEB_ACCESS_CACHE` 或 `--cache-dir` 可覆盖。
- 缓存内容不含 API key 与请求头。

## 5. 降级到其他通道

本 skill 是单 provider，不自动跨 skill 切换。若 DeepSeek 出现 auth/balance/长期网络不可用：

1. 如实报告错误类别与官方 message；
2. 停止当前请求，不重试 401/402；
3. 用户显式要求时，才由调用方选择其他已安装搜索通道；
4. 不得假定其他 skill 存在，也不得引用其内部文件。
