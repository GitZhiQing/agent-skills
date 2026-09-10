---
name: ddgs-web-access
description: >-
  联网搜索与网页抓取工具（基于 ddgs 多引擎元搜索：DuckDuckGo / Bing / Brave / Wikipedia 等）。
  当用户需要搜索最新资料、查找代码、文档或新闻、验证事实、或抓取某个网页的正文内容时使用；
  触发词包括"搜索""查一下""web search""找资料""联网查证""抓取网页""网页正文""fetch 这个页面"等。
  当用户只是讨论本地文件内容、或已有完整文本无需再抓取网页时，不要使用本 skill。
license: MIT
compatibility: 需要 uv >= 0.5 与网络访问；首次调用联网安装 ddgs 依赖（约 30-60 秒）；代理经 --proxy 或环境变量传入
allowed-tools: Bash(uv run *) Bash(bash *bin/ddgs-web-search *) Bash(bash *bin/ddgs-web-fetch *)
metadata:
  version: 0.2.1
  category: web
---

# ddgs-web-access：Web 搜索与网页抓取

基于 [ddgs](https://github.com/deedy5/ddgs) 的极简封装，只做文本搜索与网页抓取（图片 / 新闻 / 视频搜索不在范围内）：

| 命令 | 用途 |
| --- | --- |
| `ddgs-web-search` | 按关键字搜索网页，返回 标题 / URL / 摘要 |
| `ddgs-web-fetch` | 抓取指定 URL 的正文（默认转 Markdown，支持批量） |

对应原生工具的用法迁移：`WebSearch` ≈ `ddgs-web-search`（域名限定在关键字中加 `site:example.com`）；`WebFetch` ≈ `ddgs-web-fetch`（没有 prompt 参数——正文已是 Markdown，从中自行提取答案，长文用 `--start` 分段读）。

## 调用方法

标准形式（`<skill_dir>` 为本 skill 目录；命令不依赖当前工作目录）：

```bash
bash "<skill_dir>/bin/ddgs-web-search" "<关键字>" -m 5
bash "<skill_dir>/bin/ddgs-web-fetch" "<url>"
bash "<skill_dir>/bin/ddgs-web-fetch" "<url1>" "<url2>"   # 批量抓取，以 ===== <url> ===== 分隔
```

等价形式：`uv run --project "<skill_dir>" ddgs-web-search ...`；Windows cmd/PowerShell 用同目录 `.cmd` 变体。全量参数见 `--help`。

## 常用参数

- 搜索：`-m` 结果数（默认 10，5-10 够用即可）；`-t d/w/m/y` 时效过滤；`-b bing|brave|duckduckgo|wikipedia` 指定引擎；`--urls` 只输出链接、每行一个（适合串联批量抓取）；`--format json` 结构化输出。
- 抓取：`--max-chars` 截断长度（默认 5000，长文按需调大，0 为不限）；`--start N` 跳过前 N 字符，与 `--max-chars` 配合分段读长文；`--no-cache` 绕过 15 分钟抓取缓存；`--curl` 强制用系统 curl 抓取（默认模式失败时已会自动回退到 curl，一般无需手动指定）。

## 输出解读

搜索结果每项为 3 行块：序号+标题 / URL / 摘要，结果之间空行分隔。无结果时 stdout 为空、stderr 提示 `no results found.`、退出码为 0。stderr 出现 `cache hit`（缓存命中）、`retrying`（自动重试）、`truncated ... (continue with --start N)`（截断续读）均属正常提示，不是错误。引用来源时**带上 href 链接**；抓取到的正文默认是 Markdown，其中的链接与标题可直接引用。

## 稳定性与纪律

已内置：抓取失败自动改用系统 curl 重试（404/410 死链除外）；搜索遇瞬时异常自动重试一次（间隔 2s）。

仍需遵守（ddgs 是多引擎聚合，请求过频会被限流，表现为"连续空结果"）：

1. 连续两次调用之间至少间隔 2 秒；
2. 连续 2 次空结果或报错：等待 10-30 秒重试一次，仍失败则向用户说明网络/代理问题；
3. 同一 URL 不要重复抓取，优先复用已获取的内容。

## 代理

需要代理时加 `--proxy "http://127.0.0.1:7890"`；未指定时依次回退 `DDGS_PROXY` → `HTTPS_PROXY` → `HTTP_PROXY` 环境变量。

## 故障排查

- 首次调用耗时 30-60 秒是正常的（uv 正在安装依赖），后续调用会快很多；
- `HTTP 404`：页面不存在；`TimeoutException`：网络慢，可加 `--timeout 15` 重试；
- 反复空结果：先检查网络与代理，再按限流退避处理；
- 安装、卸载与多 agent 分发见仓库 `README.md`。
