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

**方式一（推荐，多 agent 共享）**：运行安装脚本，自动在本机已安装的主流 agent skills 全局位（ZCode / Claude Code / Cursor / Codex / Copilot / Gemini CLI / opencode / Windsurf / Cline / Roo / Qwen / Kilo / Junie / Trae 及跨端通用目录 `~/.agents/skills`）下创建指向本 skill 目录的链接（Windows 用 junction，免管理员权限；Unix 用符号链接）：

```bash
bash scripts/install.sh                    # 卸载：bash scripts/uninstall.sh
bash scripts/install.sh <skills-dir> ...   # 仅链接指定目录（如某项目的 .agents/skills）
```

- 单一来源：所有 agent 指向同一个目录，代码更新（如 git pull）后全端生效；
- 抓取缓存（目录 `.cache/`）跨 agent、跨项目共享；
- 幂等可重复执行；卸载只删除指向本仓库的链接。

**方式二（手动）**：把本目录复制到目标 agent 的 skills 目录，如 `~/.claude/skills/ddgs-web-access/`。

**方式三（仅命令行）**：把 `bin/` 加入 PATH 后全局可用，无需 agent 集成：

```bash
export PATH="$PWD/bin:$PATH"
ddgs-web-search "python 3.13" -m 3
```

命令行验证（任意目录下执行）：

```bash
bash <仓库路径>/bin/ddgs-web-search --help
```

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

稳定性行为（v0.2.0 起，向原生 WebSearch/WebFetch 的"一次调用就成功"看齐）：

- 搜索遇瞬时异常（超时等）自动重试一次（间隔 2s）；空结果仍为 exit 0；
- 抓取失败自动改用系统 curl 重试（404/410 死链除外，此时 curl 结果相同没有意义）；`--curl` 保留为强制模式；
- 超时默认 10s（原 5s，偏激进）；`--start N` 与 `--max-chars` 配合可分段读长文，截断提示会给出续读参数。

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
