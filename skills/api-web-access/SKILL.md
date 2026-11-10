---
name: api-web-access
description: >-
  调用 Tavily / Exa 官方 API 完成联网文本搜索与网页正文抓取，为 agent 提供比免费元搜索更稳定的可观测备援通道。
  当免费元搜索通道连续失败、超时、空结果或被限流，或用户点名 Tavily / Exa / API 搜索 / API 抓取、
  要求 web search / web fetch 走更稳定的 API 通道时使用；英文触发词包括 Tavily search、Exa search、API web search。
  当用户只需常规免费网页搜索、搜索图片 / 新闻 / 视频、抓取本地或内网地址，或只是询问 key 配置与额度时，不要使用本 skill。
license: MIT
compatibility: uv >= 0.5；需访问 api.tavily.com / api.exa.ai；TAVILY_API_KEY / EXA_API_KEY 至少其一，来自进程环境变量或 skill 根目录 .env（环境变量优先；不接受 CLI 传 key）
allowed-tools: Bash(uv run *) Bash(bash *bin/api-web-search *) Bash(bash *bin/api-web-fetch *)
metadata:
  version: 0.1.1
  category: web
---

# api-web-access：Tavily / Exa 稳定联网访问

给 agent 提供比免费元搜索更稳定的 `web_search` / `web_fetch` 备援：官方 API、明确错误码、自动主备、逐 URL 失败隔离与 15 分钟缓存。免费元搜索通道保留为无密钥存档兜底；本 skill 不替代它处理普通免费搜索，也不自动跨通道切换。

## 调用方法

`<skill_dir>` 为本 skill 目录；命令不依赖当前工作目录。

```bash
bash "<skill_dir>/bin/api-web-search" "<关键字>" -m 5
bash "<skill_dir>/bin/api-web-search" "<关键字>" --provider exa --format json
bash "<skill_dir>/bin/api-web-fetch" "https://example.com" --max-chars 5000
bash "<skill_dir>/bin/api-web-fetch" "<url1>" "<url2>"   # 以 ===== <url> ===== 分隔
```

等价形式：`uv run --project "<skill_dir>" api-web-search ...`；Windows cmd/PowerShell 用同目录 `.cmd` 启动器。

## 纪律

1. **密钥从进程环境变量或 `<skill_dir>/.env` 读取**：`TAVILY_API_KEY` / `EXA_API_KEY`，环境变量优先；`.env` 已 gitignore。不要把 key 粘贴进命令、报告或缓存；本 skill 没有 `--api-key` 参数。
2. **默认 auto，顺序 Tavily → Exa**；显式 `--provider tavily|exa` 时不跨厂商切换。
3. **搜索结果归一**为标题 / URL / 摘要；`--urls` 适合串联批量抓取，`--format json` 是结构化逃生口。
4. **429 读 Retry-After（上限 30s）重试一次**；5xx/网络/协议错误 2s 重试一次；401/403/402/432/433/434 不在同 provider 内重试。auto 模式按矩阵切换，详见 `references/error-matrix.md`。
5. **成功空结果 exit 0 且不切备援**，避免为空查询消耗双份额度。
6. **批量抓取逐 URL 隔离**：成功项照常输出并缓存，失败项才交给备援；仍有失败则 exit 1。
7. **同 URL 15 分钟内不重复请求**；需要新鲜结果时 `--no-cache`，并说明这会消耗额外额度。
8. **输出契约**：stdout 只放结果；stderr 单行输出 provider、cache hit、retry、failover 与错误；退出码 0 成功（含空搜索）、1 运行错误、2 参数错误。
9. **额度是用户资产**：默认 `--max-results 10`；不要为同一 query 反复 `--no-cache`；调试优先用单 provider 和小结果数。

## 故障决策

遇到 HTTP 错误、空结果、批量部分失败或自动切换问题时，读取 `references/error-matrix.md`，按矩阵决定重试、切换、降级到可用的免费网页搜索通道或停止并向用户说明。

## 边界

- 只做文本网页搜索与正文抓取；不做图片/新闻/视频/书籍搜索，不做浏览器自动化。
- 只支持 `http://` / `https://` 公网页面；本地、内网、私有仓库页面不在范围内。
- API 价格、免费额度与限速快速变化；以官方控制台为准，本 skill 不把额度写进运行时逻辑。
- 无任何 key 时 exit 1 并提示改用可用的免费网页搜索通道，不伪装成功、不编造结果。

## 参考文档

- `references/error-matrix.md` — provider 端点映射、错误分类、重试/切换/降级矩阵
- `docs/TESTS.md` — 人工真实场景断言
- `docs/SPEC.md` — 设计决策、安全与测试依据
