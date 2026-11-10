---
name: ds-web-access
description: >-
  调用 DeepSeek 官方 Search / Fetch API 完成联网搜索、搜索结果正文获取与指定网页 Markdown 抓取，
  保留 authority、date 与可引用来源元数据。
  当用户点名 DeepSeek 搜索、DeepSeek 抓取、DS / ds 搜索、DS / ds 抓取、ds-web-search / ds-web-fetch，或明确要求使用
  DeepSeek 付费网页搜索通道时使用；英文触发词包括 DeepSeek search、DeepSeek fetch、DS / ds search、DS / ds fetch。
  当用户需要普通免费搜索、点名其他搜索 API、抓取本地或内网地址、未配置 DEEPSEEK_API_KEY，或仅提到 DS / ds 但语境是
  Nintendo DS、data science、数据集等无关主题时，不要使用本 skill。
license: MIT
compatibility: uv >= 0.5；需访问 api.deepseek.com；DEEPSEEK_API_KEY 必填（进程环境变量或 skill 根 .env，环境变量优先）；DeepSeek Search/Fetch 为付费 API，按成功请求计费
allowed-tools: Bash(uv run *) Bash(bash *bin/ds-web-search *) Bash(bash *bin/ds-web-fetch *)
metadata:
  version: 0.1.1
  category: web
---

# ds-web-access：DeepSeek Search / Fetch

给 agent 提供 DeepSeek 官方网页搜索与网页抓取通道。Search 默认返回模型友好的摘要与来源元数据，可显式请求结果正文；Fetch 返回指定 URL 的 Markdown 正文。两个 API 独立计费，本 skill 不做跨厂商自动切换。

## 调用方法

`<skill_dir>` 为本 skill 目录；命令不依赖当前工作目录。

```bash
bash "<skill_dir>/bin/ds-web-search" "DeepSeek site:github.com lang:zh after:2026" -n 10
bash "<skill_dir>/bin/ds-web-search" "..." --need-content --format json
bash "<skill_dir>/bin/ds-web-fetch" "https://example.com"
bash "<skill_dir>/bin/ds-web-fetch" "https://a.com" "https://b.com" --yes
```

等价形式：`uv run --project "<skill_dir>" ds-web-search ...`；Windows cmd/PowerShell 用同目录 `.cmd` 启动器。

## 纪律

1. **密钥只从进程环境变量或 `<skill_dir>/.env` 读取**：`DEEPSEEK_API_KEY`，环境变量优先；没有 `--api-key`，不要把 key 粘贴进命令、报告或缓存。
2. **这是付费 API**：Search 与 Fetch 各按成功请求计费；默认 `count=10`，不要为同一 query 反复 `--no-cache`。官方计费以 DeepSeek 控制台为准。
3. **Search 默认摘要优先**：`--need-content` 才请求结果正文；正文用 `--max-content-chars` 控制，默认 4000 字符。
4. **多 URL Fetch 必须显式 `--yes`**：每个成功 URL 独立计费；批量前先确认用户接受成本。
5. **query 原样透传官方语法**：支持 `site:`、`-site:`、`"..."`、`lang:`、`after:`、`before:`；不要在 CLI 外重复拼接这些操作符。
6. **错误语义**：401 是 key 无效，402 是余额不足，429 是限流；Fetch 403 是安全策略拒绝，404 是无可用正文。完整重试/退出码规则见 `references/error-matrix.md`。
7. **缓存是本 skill 的本地优化**：Search 非空结果 10 分钟，Fetch 成功正文 15 分钟；`--no-cache` 同时跳过读写。空结果与失败不缓存。
8. **stdout 只放结果**；endpoint/cache/retry/billing 诊断走 stderr；退出码 0 成功（含空搜索）、1 运行错误、2 参数错误。
9. **`localization` 只接受用户显式提供的 IP**，不得自动探测或填写本机 IP。
10. **引用来源**：官方无 `citation` 字段；JSON 输出中的 `citation` 是本 skill 用 `title/url/site_name/date` 派生的结构，不得伪称官方原生字段。

## 故障决策

遇到无效 key、余额不足、限流、Fetch 403/404、网络或协议错误时，读取 `references/error-matrix.md`，按矩阵决定重试、停止或请用户处理。不要切换到其他搜索 skill，除非用户显式要求。

## 边界

- 只做 DeepSeek Search / Fetch；不做其他 provider，不做自动降级，不做图片/视频/新闻独立搜索。
- Fetch 只支持公网 `http://` / `https://` URL，不支持本地、内网、带用户名密码的 URL；一次官方请求只处理一个 URL。
- Search 无分页；`count` 最大 50。需要更多结果时改写 query，而不是假设 offset。
- 不承诺免费额度、SLA、地域可用性或数据驻留；这些未在官方 API 文档中说明。
- 输出中的 `billing=inferred` 是按官方规则做的本地推断，不是官方账单字段。

## 参考文档

- `references/error-matrix.md` — 端点、请求 schema、错误分类、重试与计费矩阵
- `docs/TESTS.md` — 行为断言、真实场景与触发校准
- `docs/SPEC.md` — 设计决策、API 事实与开放问题
