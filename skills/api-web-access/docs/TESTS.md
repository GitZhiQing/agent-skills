# api-web-access 真实场景测试集

| 文档版本 | v1.1 | 日期 | 2026-11-11 | 适用版本 | api-web-access v0.1.1 | 定位 | 真实 API 与真实安装场景下的可用性验证；无网络协议断言见 `tests/` 并入 CI |
| --- | --- | --- | --- | --- | --- | --- | --- |

## 1. 运行方式

- 命令在仓库根执行；`▶` 为命令，`=` 为断言。真实 API 场景需 `TAVILY_API_KEY` / `EXA_API_KEY` 至少其一：可导出为当前进程环境变量，也可写入 `skills/api-web-access/.env`（gitignore；进程环境变量优先）。
- 需要构造“无 key”场景时，除 `env -u` 两个变量外，还要 `API_WEB_ACCESS_ENV_FILE=skills/api-web-access/tests/.env.absent`，避免读取维护者本机 `.env`。
- API 价格/额度快速变化：每轮回归前查看官方控制台，控制结果数；默认 `--max-results 10`，调试用 `-m 3`。
- 退出码：0 成功（含空搜索）、1 运行错误、2 参数错误；stdout 与 stderr 必须分开观察。
- 自动化基线：`python -m unittest discover -s skills/api-web-access/tests`；未设置 key 时真实 API 用例自动跳过，跳过不算通过。

## 2. 授权与边界（A）

### A-1 缺 key 时诚实失败

```
▶ env -u TAVILY_API_KEY -u EXA_API_KEY API_WEB_ACCESS_ENV_FILE=skills/api-web-access/tests/.env.absent \
    uv run --project skills/api-web-access api-web-search "python 3.13" -m 3
```

- = exit 1，stderr 含 `MissingKeyError`、`TAVILY_API_KEY`、`EXA_API_KEY`
- = stderr 提示改用可用的免费网页搜索通道（`an available free web-search provider`）
- = stdout 为空；无 traceback、无伪造结果

### A-2 显式 provider 的 key 缺失

```
▶ env -u EXA_API_KEY API_WEB_ACCESS_ENV_FILE=skills/api-web-access/tests/.env.absent \
    uv run --project skills/api-web-access api-web-search "python 3.13" --provider exa -m 3
```

- = exit 1，错误只指向 `EXA_API_KEY`，不提示 auto 切换成功
- = 无网络请求副作用，stdout 为空

### A-3 非公网 URL 拒绝

```
▶ uv run --project skills/api-web-access api-web-fetch "file:///etc/hosts"
```

- = exit 2，argparse 报 URL 必须 `http://` 或 `https://`
- = 不发起 API 请求

### A-4 `.env` 配置与环境变量优先

场景：`skills/api-web-access/.env` 已按 `.env.example` 填入至少一个有效 key。

```
▶ env -u TAVILY_API_KEY -u EXA_API_KEY uv run --project skills/api-web-access api-web-search "python 3.13" -m 3
▶ TAVILY_API_KEY=<进程内有效 key> env -u EXA_API_KEY uv run --project skills/api-web-access api-web-search "python 3.13" -m 3
```

- = 第一条读取 `.env` 成功执行，stderr 只含 provider/cache 诊断，不输出 key
- = 第二条证明进程环境变量优先于 `.env`（可将 `.env` 中同名 key 故意置为无效，仍应成功）
- = `git check-ignore -v skills/api-web-access/.env` 能命中 skill `.gitignore`
- = `git status --short` 不显示 `.env`；`.env.example` 入库且值为空

## 3. 搜索场景（S）

### S-1 Tavily 基础搜索

```
▶ TAVILY_API_KEY=... uv run --project skills/api-web-access api-web-search "python 3.13 what's new" --provider tavily -m 5
```

- = exit 0；stderr 一行含 `provider=tavily`
- = stdout ≥3 个结果块，每块标题 / URL / 摘要三行
- = 至少 1 个 python.org / docs.python.org 结果
- = 输出不含 API key

### S-2 Exa 基础搜索与 JSON

```
▶ EXA_API_KEY=... uv run --project skills/api-web-access api-web-search "python 3.13 what's new" --provider exa -m 5 --format json
```

- = exit 0；stdout 为 JSON 数组，每项恰含 `title` / `href` / `body`
- = stderr 一行含 `provider=exa`
- = `--urls` 变体每行一个 URL，无标题/序号

### S-3 空结果不切备援

```
▶ <两 key 均设置> uv run --project skills/api-web-access api-web-search "zzuuppqq unlikely query 261110" -m 3
```

- = 若 provider 成功返回空：exit 0，stdout 为空或 `[]`，stderr 含 `no results found.`
- = stderr 不出现 `switching` / 第二个 provider 成功输出
- = 不为空结果消耗第二份额度

## 4. 抓取场景（F）

### F-1 Tavily 单页抓取与分段

```
▶ TAVILY_API_KEY=... uv run --project skills/api-web-access api-web-fetch "https://example.com" --provider tavily
▶ TAVILY_API_KEY=... uv run --project skills/api-web-access api-web-fetch "https://example.com" --provider tavily --start 20 --max-chars 100
```

- = exit 0，stdout 为 Markdown 正文，无 JSON 包装
- = 第二条按偏移截断；stderr 如截断则给出续读 `--start`
- = 输出不含 API key

### F-2 Exa 抓取与纯文本

```
▶ EXA_API_KEY=... uv run --project skills/api-web-access api-web-fetch "https://example.com" --provider exa -f text_plain
```

- = exit 0，stdout 非空，无 HTML 标签泛滥
- = stderr 一行 provider 通知，无请求头/响应体 dump

### F-3 批量部分失败隔离

```
▶ <两 key 均设置> uv run --project skills/api-web-access api-web-fetch "https://example.com" "https://example.invalid" --cache-dir /tmp/api-web-cache
```

- = `https://example.com` 内容照常输出并缓存
- = 失败 URL 有单行错误；auto 尝试备援时 stderr 有 provider 失败/缺失记录
- = 全链路仍有失败则 exit 1；已成功内容不被吞掉

## 5. 主备与缓存（P/C）

### P-1 auto：Tavily 故障切换 Exa

```
▶ TAVILY_API_KEY=<故意无效> EXA_API_KEY=<有效> uv run --project skills/api-web-access api-web-search "python 3.13" -m 3
```

- = 最终结果来自 Exa，exit 0；stderr 记录 Tavily 失败与后续 provider=exa
- = 无 key 字面量出现在 stdout/stderr
- = 显式 `--provider tavily` 时同输入 exit 1，不切 Exa

### P-2 400 不切换

```
▶ <用测试桩或构造的非法请求> api-web-search ... --provider auto
```

- = provider 返回 400 时无 retry/failover，exit 1
- = stderr 保留官方 `detail/message`，且已脱敏

### C-1 缓存命中与隔离

```
▶ uv run --project skills/api-web-access api-web-search "cache probe 261110" -m 3 --cache-dir /tmp/api-web-cache
▶ <同命令立即复跑>
```

- = 第二次 stderr 含 `cache hit`，结果与第一次一致
- = `--no-cache` 复跑不读不写缓存
- = 缓存目录中搜索缓存文件不含 key；Tavily/Exa 键不混用

## 6. 安装分发（I）

### I-1 启动器与链接

```
▶ bash scripts/skills-link.sh api-web-access && bash scripts/skills-doctor.sh
▶ bash "skills/api-web-access/bin/api-web-search" --help
▶ bash "skills/api-web-access/bin/api-web-fetch" --help
```

- = doctor 中 api-web-access 在已存在目标下为 linked，无 broken
- = 两个启动器 exit 0，帮助完整，不依赖当前目录
- = 既有免费网页搜索 skill 的链接仍为 linked，旧命令不受影响

## 7. 结果记录

| 场景 | 日期 | 环境（provider/key 状态） | 结果（通过/偏离/跳过） | 偏离断言与说明 |
| --- | --- | --- | --- | --- |
| A-1 | 2026-11-10 | ZCode / Git Bash / uv，两 key 均未设置 | 通过 | exit 1、MissingKeyError、无请求、无 traceback |
| A-4 | 2026-11-10 | `skills/api-web-access/.env` 已配置两 key，进程环境未设置 | 通过 | CLI 读取 `.env` 成功；`git check-ignore` 命中；输出无 key |
| S-1 | 2026-11-10 | Tavily key 已设置（仅进程环境） | 通过 | `tests/test_live_api.py` 真实 search，3 结果内，JSON 三字段 |
| S-2 | 2026-11-10 | Exa key 已设置（仅进程环境） | 通过 | 真实 search + contents；JSON/文本契约通过 |
| F-1 | 2026-11-10 | Tavily key 已设置（仅进程环境） | 通过 | example.com 抓取非空；输出无 key |
| F-2 | 2026-11-10 | Exa key 已设置（仅进程环境） | 通过 | example.com 抓取非空；输出无 key |
| P-1 | 2026-11-10 | 无效 Tavily key + 有效 Exa key（仅进程环境） | 通过 | 自动切 Exa 成功；stderr 留痕；无 key 泄漏 |
| C-1 | 2026-11-10 | 无网络 mock 单测 | 通过 | 缓存命中、provider/format 隔离由 `test_api_web_access.py` 覆盖 |

## 8. 触发校准（静态评审）

日期：2026-11-11。方法：仅对照 `SKILL.md` 的 description 逐条做静态判定，**未发起新会话、不统计触发率**；真实触发率待后续会话回填。判定口径：命中“免费元搜索通道连续失败 / 限流”或“点名 Tavily / Exa / API 通道”为应触发；只涉及常规免费搜索、非文本搜索、本地/内网、配置咨询等近邻场景为不应触发。

### 8.1 应触发（8 条，静态判定）

| # | 查询 | 判定 |
| --- | --- | --- |
| 1 | 帮我用 Tavily 搜一下 Python 3.13 的新特性 | 应触发（点名 Tavily） |
| 2 | 用 Exa 搜一下最新的向量数据库评测 | 应触发（点名 Exa） |
| 3 | 免费搜索连续超时了，换一个更稳定的 API 通道再查一次 | 应触发（免费通道连续失败） |
| 4 | 普通元搜索一直空结果，帮我换 API 搜索通道 | 应触发（连续空结果） |
| 5 | 这个查询被限流了，用 Tavily API 重试 | 应触发（限流 + 点名 API） |
| 6 | web search 走 API 通道，结果要 JSON | 应触发（要求 API 通道） |
| 7 | 用 Exa API 抓取这个页面的正文 | 应触发（点名 Exa API 抓取） |
| 8 | 帮我用 Tavily 的 extract 抓取这篇文档 | 应触发（点名 Tavily） |

### 8.2 不应触发（8 条，近邻反例）

| # | 查询 | 判定 |
| --- | --- | --- |
| 1 | 帮我搜一下今天的天气 | 不应触发（常规免费搜索即可） |
| 2 | 搜索 Python 相关的图片、新闻或视频 | 不应触发（非文本搜索） |
| 3 | 抓取 http://192.168.1.10/admin 这个内网页面 | 不应触发（本地 / 内网地址） |
| 4 | 怎么配置 TAVILY_API_KEY？额度还剩多少？ | 不应触发（只问配置与额度） |
| 5 | 把这段本地 Markdown 总结一下 | 不应触发（无联网需求） |
| 6 | 帮我打开浏览器登录这个网站并截图 | 不应触发（浏览器自动化） |
| 7 | 用 curl 下载这个文件 | 不应触发（普通下载） |
| 8 | 帮我比较两个本地目录的文件差异 | 不应触发（本地操作） |
