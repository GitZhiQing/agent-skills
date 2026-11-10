# api-web-access 错误与降级矩阵

按需读取：CLI 返回非 0、stderr 出现 retry/failover、auto 主备行为需要解释，或调用方决定是否降级到可用的免费网页搜索通道时读本文。

## 1. Provider 端点与鉴权

| Provider | 搜索 | 抓取 | 鉴权 | 备注 |
| --- | --- | --- | --- | --- |
| Tavily | `POST https://api.tavily.com/search` | `POST https://api.tavily.com/extract` | `Authorization: Bearer <TAVILY_API_KEY>` | search 默认 basic；extract 支持 markdown/text；批量 ≤20 URL；HTTP 432/433/434 表示计划/用量/容量限制 |
| Exa | `POST https://api.exa.ai/search` | `POST https://api.exa.ai/contents` | `x-api-key: <EXA_API_KEY>` | 搜索 `type=auto` 并请求 text；contents 以 URL 作为 id；402 表示额度/预算耗尽 |

密钥来源为进程环境变量或 `<skill>/.env`（环境变量优先；`API_WEB_ACCESS_ENV_FILE` 可指定测试用文件）。密钥只进请求头，绝不进 URL、CLI 参数、stdout、stderr 或缓存。错误响应体最多取 1024 字节并先做环境/`.env` key 脱敏再输出。

## 2. HTTP / 运行错误矩阵

| 类别 | 触发 | 同 provider 重试 | auto 切备援 | 显式 provider | 建议动作 |
| --- | --- | --- | --- | --- | --- |
| auth | 401 / 403，或环境变量缺失 | 否 | 是 | 立即 exit 1，提示变量名 | 检查 key；auto 会尝试下一 provider |
| quota | 402，或 Tavily 432 / 433 / 434 | 否 | 是 | 立即 exit 1 | 等待额度重置 / 升级计划 / 换 provider |
| rate_limit | 429 | 是：读 `Retry-After`，缺省 2s，上限 30s，仅一次 | 重试仍失败则切换 | 重试后 exit 1 | 等待后再试；不要连续 `--no-cache` |
| server | 5xx | 是：2s 一次 | 仍失败则切换 | 重试后 exit 1 | 可稍后重试 |
| network | DNS / TLS / 超时 / 代理失败 | 是：2s 一次 | 仍失败则切换 | 重试后 exit 1 | 检查网络或 `--proxy` |
| protocol | 非 JSON、结构异常 | 是：2s 一次 | 仍失败则切换 | 重试后 exit 1 | 升级 skill / 检查 API 变更 |
| client | 400 及其他 4xx | 否 | 否 | 立即 exit 1 | 修正调用参数；这是调用方/API 契约错误 |
| fetch_failed | provider 对单个 URL 返回无内容/失败 | 否（该 provider 内不重试） | 是：仅失败 URL 交给下一 provider | 该 URL exit 1，其余照常输出 | 换 provider 或改用免费网页搜索通道 |

## 3. 搜索空结果

- 成功响应但 `results=[]`：**exit 0**，stderr 输出 `no results found.`。
- auto 不为空结果切换 provider，避免同一 query 消耗双份额度。
- 需要第二意见时由调用方显式改 `--provider <other>`，并在调研台账登记两次查询。

## 4. 批量抓取与缓存

- URL 去重并保持输入顺序；每个 provider 每批 ≤20。
- 成功项立即输出并写入该 provider 的缓存；失败项才进入下一 provider。
- 全部 provider 结束后仍有失败：成功项已输出，进程 exit 1，stderr 逐 URL 给出失败类别。
- 缓存键含 provider、操作、请求参数与格式；Tavily/Exa 结果不串用。TTL 15 分钟；`--no-cache` 同时跳过读和写。

## 5. 何时降级到免费网页搜索通道

满足其一且任务仍需继续时，向用户/调用方建议存档兜底：

1. 两个 provider 都返回 auth/quota，且无法立即修复 key 或额度；
2. API 网络长期不可达，而普通公网仍可访问；
3. 任务只需免费元搜索，结果稳定性要求让位于零成本。

降级不是自动跨通道执行：本 skill exit 1 并给出原因，由调用方选择可用的免费网页搜索通道。切换动作与原因必须写入调研/执行台账，不静默替换。
