# api-web-access 需求与设计文档

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.1 |
| 日期 | 2026-11-11 |
| 状态 | 已实现（v0.1.1） |
| 适用范围 | `api-web-search` / `api-web-fetch` 两个 CLI 与 skill 协议 |
| 资料基线 | Tavily / Exa 官方 docs 与 pricing 页，2026-11-09 核验；价格与额度快速变化，本文不作为长期承诺 |

## 1. 问题与目标

现有免费元搜索通道依赖多引擎聚合，在真实调研中出现连续超时与空结果（2026-11-09 一次 15 query 会话中 8 轮失败/空结果）。该通道继续保留为无密钥存档兜底；本 skill 用官方 API 解决稳定性：

1. 明确错误码与重试语义，替代字符串猜测；
2. Tavily → Exa 自动主备，避免单一 SaaS 故障阻塞任务；
3. 批量抓取逐 URL 失败隔离，部分成功不被整体失败吞掉；
4. 密钥只走环境变量与请求头，输出与缓存全程脱敏；
5. 保持 `stdout=结果 / stderr=诊断 / exit 0-1-2` 契约，便于 agent 直接替换调用习惯。

## 2. 方案

### 2.1 架构

- 单文件 `api_web_access.py`，纯 Python 标准库（`urllib.request` + `json`），无第三方依赖；`uv` 只负责托管解释器与入口。
- 两个 console scripts：`api-web-search`、`api-web-fetch`；`bin/` 提供 Git Bash 与 Windows cmd/PowerShell 自定位启动器。
- 搜索结果统一归一 `{title, href, body}`；抓取统一为 Markdown/纯文本字符串，复用通用的紧凑输出与 `--start/--max-chars` 分段语义。

### 2.2 Provider 映射

| 能力 | Tavily | Exa |
| --- | --- | --- |
| 搜索 | `/search`，`search_depth=basic`，可选 `time_range` | `/search`，`type=auto`，`contents.text=true`，日期窗口映射为 `startPublishedDate` |
| 抓取 | `/extract`，`format=markdown|text`，批量 ≤20 | `/contents`，URL 作为 `ids`，`text=true`，批量 ≤20 |
| 鉴权 | `Authorization: Bearer` | `x-api-key` |
| 额度/计划错误 | 402、432、433、434 | 402 |
| 限速 | 429 + `Retry-After` | 429 + `Retry-After` |

### 2.3 重试与主备

- 同 provider 内只对 `rate_limit/server/network/protocol` 重试一次；429 优先读 `Retry-After`，上限 30s，其余 2s。
- `auth/quota/client` 不做同 provider 重试。auto 模式下 `auth/quota/rate_limit/server/network/protocol/fetch_failed` 可切下一 provider；`client` 不切换。
- 成功空结果 exit 0，不自动切换，避免双倍消耗；需要第二意见由调用方显式指定 provider。
- 批量抓取先按 provider 分批，成功项缓存并输出；仅失败 URL 进入备援。全链路结束后仍有失败则 exit 1。

### 2.4 缓存

- 搜索与抓取均缓存 15 分钟，键 = SHA256(operation + provider + 请求参数/URL + format)，provider 结果不串用。
- `--no-cache` 同时跳过读写；`API_WEB_ACCESS_CACHE` / `--cache-dir` 指定目录；缓存只写成功 payload，不写错误与请求头。

### 2.5 代理

- API 请求支持 http/https 代理（`--proxy`），走 `urllib.ProxyHandler`。
- 不支持 SOCKS：本 skill 不引入第三方网络库；需要 SOCKS 的免费网页抓取场景改用支持 SOCKS 的免费通道。

## 3. 关键决策

| 决策 | 理由 |
| --- | --- |
| 新增独立 skill，不取代现有免费元搜索通道 | 保留无密钥兜底与旧命令；避免破坏现有分发链接与触发语义 |
| 纯标准库 HTTP | 零新增依赖、供应链面最小；Tavily/Exa 都是简单 JSON POST |
| key 来自环境变量或 skill 根 `.env` | 进程环境变量优先，便于 CI/生产注入；`.env` 满足本机长期配置且被 gitignore；无 `--api-key`，避免进入 shell history 与进程列表 |
| auto 默认 Tavily → Exa | 2026-11-09 官方政策：Tavily 每月 1000 credits、无需信用卡，错误语义与本需求贴合；Exa 免费额度更大但计费维度更多 |
| 空结果不切换 | 控制成本；“第二意见”应由调用方显式请求并登记 |
| 400 不切换 | 多为调用契约错误，切换会掩盖缺陷并浪费额度 |
| 显式 provider 不跨厂商切换 | 用户点名 provider 时语义必须可预测；备援只属于 auto |
| 抓取失败项单独切换 | 批量页面可用性差异大，整体重试会浪费已成功内容与额度 |
| 额度不写进运行时 | 官方价格/额度快速变化；运行时只依赖错误码 |

## 4. 安全与隐私

- 密钥只进入进程环境变量（可由 `<skill>/.env` 预填充）与请求头；进入错误文本前用 `_redact_text` 替换环境/`.env` 中的 key 值与 `tvly-*` 模式。
- `.env` 仅接受 `TAVILY_API_KEY` / `EXA_API_KEY` 两行，进程环境变量优先；`.env` 与 `.env.*` 均被 skill `.gitignore` 排除，`.env.example` 只入库空模板。
- 不提供 key CLI 参数，不把 key 放 URL 或缓存键。
- HTTP 错误响应体最多取 1024/2048 字节，仅提取 `detail/message/error/errors`，输出前脱敏。
- stdout 只放搜索/正文结果；provider、重试、切换、缓存和错误全部走 stderr 单行。
- 本 skill 只访问 Tavily/Exa 官方域名；不执行网页内容中的指令，网页正文只是待分析数据。

## 5. 测试策略

- `tests/test_api_web_access.py`：无网络、无 key，mock `_request_json`；覆盖 `.env` 优先级与解析、归一化、错误分类、429/5xx 重试、auto 切换、400 不切换、空结果不切换、批量部分失败、缓存隔离、key 脱敏、参数错误。单测通过 `API_WEB_ACCESS_ENV_FILE` 指向不存在文件，隔离维护者真实 `.env`。
- `tests/test_live_api.py`：按进程环境变量 `skipUnless`；有 key 时每 provider 各一次 search/extract，验证真实契约并扫描输出不泄漏 key。CLI 的 `.env` 通道由无网络单测与人工 A-4 覆盖。
- `docs/TESTS.md`：人工真实场景，覆盖授权、搜索、抓取、主备、缓存与安装分发。
- CI 只跑无网络单测；真实 API 测试由维护者手动执行，跳过不算通过。

## 6. 开放问题

- Exa `/contents` 的失败结构若官方后续扩展 `statuses` 语义，需更新 `_fetch_once` 解析与单测。
- Tavily `/extract` advanced 模式、Exa highlights/summary 暂不暴露，避免增加计费维度；有需求先评估再升级次版本。
- 免费额度与限速需在每次真实回归时查看官方控制台；文档只保留核验日期。
- 若未来需要 SOCKS 代理或并发批量，应评估引入网络库的供应链成本，另开决策记录。

## 7. 变更记录

- v0.1.0（2026-11-10）：首版。Tavily/Exa search+fetch、auto 主备、错误矩阵、15 分钟缓存、环境变量与 `.env` 双通道 key、key 脱敏、无网络单测与可选真实 API 测试。
- v0.1.1（2026-11-11）：触发描述与文档去耦，统一使用“免费元搜索通道 / 可用免费网页搜索通道”表述；缺 key 错误改为 `use an available free web-search provider`；补充静态触发校准附录；同步版本。
