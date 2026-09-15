# AGENTS.md — skills

个人 AI coding agent skills 集合：每个 skill 位于 `skills/` 子目录下，一个 skill 一个目录，通过 junction/软链分发到各 agent 的 skills 目录（目标 = 内置主流清单 ⊕ `agents.local.conf` 本地自定义，目录存在才生效，清单见 `docs/开发与维护规范.md` §6）。

维护标准见 `docs/开发与维护规范.md`（目录结构、frontmatter、版本规则、台账格式、分发与回归流程）；执行细则见 `docs/维护脚本测试集.md`。

## 怎么跑起来 / 验证

- 纯提示词 skill（theme-commit、deep-research、zero-coding）：无运行时，直接读 SKILL.md。
- ddgs-web-access 需要 uv >= 0.5，命令不依赖当前工作目录：

```bash
bash skills/ddgs-web-access/bin/ddgs-web-search "smoke test" -m 1
bash skills/ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

- 仓库级维护脚本（纯 bash，零依赖）：

```bash
bash scripts/skills-lint.sh           # 结构/元数据校验：全绿 exit 0
bash scripts/skills-doctor.sh         # 链接健康矩阵
bash scripts/skills-link.sh --all     # 分发（幂等）
```

- 改动 ddgs-web-access 代码后按 `skills/ddgs-web-access/docs/测试集.md` 回归；搜索/抓取调用间隔 ≥2 秒（ddgs 多引擎聚合，过频会限流）。
- 改动 video-insight 代码后按 `skills/video-insight/docs/测试集.md` 回归：`python -m unittest discover -s skills/video-insight/tests`（49 条，含合成视频集成测试，纯标准库无第三方依赖）。
- 等价形式：`uv run --project skills/ddgs-web-access <命令>`；Windows 用 `bin/*.cmd`。

## 技术栈

- ddgs-web-access：Python >= 3.10（uv 托管虚拟环境），依赖 ddgs + markdownify，单文件 CLI（`ddgs_web_access.py`）+ `bin/` 位置无关启动器；stdout 结果 / stderr 提示与错误 / 退出码 0-1-2。
- theme-commit：纯 SKILL.md 提示词（git 按主题分组提交），0.1.1。
- deep-research：纯 SKILL.md 提示词（先校准再调研：环境检查 → 预检索校准 → 选项式澄清 → 档位推荐 → 强制确认门 → 增量登记落盘 research/ 目录 → REPORT.md + REFERENCES.md 双文件交付），0.2.0。
- zero-coding：纯 SKILL.md 提示词（从零启动个人项目：最小文档集 ZERO/SPEC/DECISIONS/AGENTS/README，按"捕获 → 固化 → 骨架 → 稳定开发"推进，产物快照式书写——零历史、新读者测试；首次触发以 3~5 句开局说明交代全程），0.2.0。
- video-insight：拉片级视频分析（L1 文案档 / L2 画面档，档位确认门 + 实测/约/推断三档表述），Python 脚本纯标准库，外部依赖 ffmpeg/ffprobe（B站下载另需 yt-dlp），转写复用上游 video-to-subtitle-summary，0.1.0。
- scripts/：bash + coreutils 维护脚本套件，公共函数在 `scripts/lib.sh`；退出码统一 0-1-2，状态走 stdout、错误走 stderr。

## 目录与约定

- 一个 skill 一个目录，SKILL.md 为入口；frontmatter 需含 `name`（== 目录名）、三段式 `description`、`metadata.version`（semver）；版本权威来源是 frontmatter，pyproject.toml 与 README Skills 表跟随同步，lint 强制。
- 公开 skill 目录以 README Skills 表为准；维护者个人的台账、分发状态与下一步计划记录在 `SKILLS.local.md`（gitignore `*.local.md`，不入库）。
- 每个 skill 带 README.md（面向人的目录导览：定位、触发、工作方式、安装；lint 强制存在，不写版本号）；复杂 skill 另带 docs/（设计文档、测试集）；测试集编号用「类别前缀-序号」。
- 分发与卸载统一用 `bash scripts/skills-link.sh` / `skills-unlink.sh`（`[--agent <name|name=path>]...` 可限定或临时指定目标；在内置清单 ∪ `agents.local.conf` 的目录建/删指向本仓库的 junction，单一来源）；ddgs-web-access 自带的 `scripts/install.sh` 仅供该 skill 独立拷走时使用。链接变更后跑 `skills-doctor.sh` 并回填本地台账（SKILLS.local.md）"分发状态"列。
- 内置目标清单（15 个主流 agent 全局位）的权威实现是 `scripts/lib.sh` 的 `builtin_agent_targets()`，与 ddgs-web-access 独立安装脚本同步维护。
- 运行产物（`.venv/`、`.cache/`、`__pycache__/`、`*.egg-info/`）已 gitignore，不纳入版本管理，lint 会检查。
- `.zcode/`（会话计划产物）在根 .gitignore 中排除。
