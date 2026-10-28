# ddgs-web-access

极简的 Web 搜索与网页抓取工具集，为 AI coding agent 设计，封装 [ddgs](https://github.com/deedy5/ddgs)（DuckDuckGo 多引擎元搜索库，MIT 许可）。

| 工具 | 命令 | 底层 API |
| --- | --- | --- |
| `ddgs_web_search` | `ddgs-web-search` | `DDGS().text()` |
| `ddgs_web_fetch` | `ddgs-web-fetch` | `DDGS().extract()` |

设计原则：极简（单文件 CLI）、少依赖（ddgs + markdownify）、`uv run` 调用、支持 HTTP/HTTPS/SOCKS5 代理、纯文本输出节约 token。完整设计见 [docs/需求与设计文档.md](docs/需求与设计文档.md)。

## 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.5（Python >= 3.10 由 uv 自动托管）
- 网络访问（首次调用从 PyPI 安装 ddgs）

## 安装

把这句交给你的 Agent（它会自己安装并验证）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 ddgs-web-access skill：优先 `npx skills add "GitZhiQing/agent-skills/ddgs-web-access"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh ddgs-web-access`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

插件市场与手动分发方式见[仓库 README](../../README.md#安装)。

仅命令行使用（不需要 agent 集成）：`export PATH="$PWD/bin:$PATH"` 后直接跑 `ddgs-web-search`。skill 自带的 `scripts/install.sh` 可把本 skill 单独链接到本机 14 个常见 agent 目录，用法见脚本头注释。

## 使用

所有命令不依赖当前工作目录，两种等价写法（`<skill_dir>` 为 skill 目录；`bin/` 为自带启动器，自动定位 skill 目录）：

```bash
# 搜索（启动器形式 / uv run 形式）
bash "<skill_dir>/bin/ddgs-web-search" "python 3.13 asyncio" -m 5 -t m
uv run --project "<skill_dir>" ddgs-web-search "python 3.13 asyncio" -m 5 -t m

# 抓取网页（默认 Markdown，默认截断 5000 字符）
uv run --project "<skill_dir>" ddgs-web-fetch "https://docs.python.org/3/whatsnew/3.13.html"

# 长文分段读：跳过前 5000 字符继续读下一段（与 --max-chars 配合）
uv run --project "<skill_dir>" ddgs-web-fetch "https://docs.python.org/3/whatsnew/3.13.html" --start 5000

# 批量抓取多个页面（一次进程开销，以 ===== <url> ===== 分隔）
uv run --project "<skill_dir>" ddgs-web-fetch "https://a.com" "https://b.com"

# 只取链接，每行一个（串联批量抓取）
uv run --project "<skill_dir>" ddgs-web-search "..." --urls

# 强制用系统 curl 抓取（默认模式失败时已自动回退到 curl，一般无需手动指定）
uv run --project "<skill_dir>" ddgs-web-fetch "https://example.com" --curl

# 走代理
uv run --project "<skill_dir>" ddgs-web-search "..." --proxy "http://127.0.0.1:7890"
```

约定：结果只写 stdout（纯文本块，或 `--format json`），错误写 stderr；退出码 `0` 成功（含空结果）、`1` 运行错误、`2` 参数错误。

稳定性行为（向原生 WebSearch/WebFetch 的"一次调用就成功"看齐）：

- 搜索遇瞬时异常（超时等）自动重试一次（间隔 2s）；空结果仍为 exit 0；
- 抓取失败自动改用系统 curl 重试（404/410 死链除外，此时 curl 结果相同没有意义）；`--curl` 保留为强制模式；
- 超时默认 10s；`--start N` 与 `--max-chars` 配合可分段读长文，截断提示会给出续读参数。

## 代理

优先级：`--proxy` 参数 > 环境变量 `DDGS_PROXY` > `HTTPS_PROXY` > `HTTP_PROXY`。支持 http / https / socks5 协议。

## 抓取缓存

`ddgs-web-fetch` 的抓取结果缓存在项目 `.cache/` 目录（TTL 15 分钟，与常见 agent 内置 WebFetch 一致），重复抓取同一 URL 直接命中缓存；`--no-cache` 可绕过，`DDGS_WEB_ACCESS_CACHE` 环境变量可改缓存目录。

## 网络受限环境

PyPI 不可达时通过环境变量指定镜像源（不硬编码进项目）：

```bash
export UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
```

## 开发与测试

```bash
uv run --project "<skill_dir>" ddgs-web-search "smoke test" -m 1
uv run --project "<skill_dir>" ddgs-web-fetch "https://example.com"
```

冒烟用例清单见设计文档 §9。

## 许可

MIT。注意：上游 ddgs 声明其库"仅供教育目的使用"，请遵守目标网站的服务条款与 robots 协议。
