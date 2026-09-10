# AGENTS.md — skills

个人 AI coding agent skills 集合：每个一级子目录是一个独立 skill，通过 junction/软链分发到本机各 agent 的 skills 目录（`~/.zcode/skills`、`~/.agents/skills`、`~/.claude/skills`、`~/.cursor/skills`）。

维护标准见 `docs/开发与维护规范.md`（目录结构、frontmatter、版本规则、台账格式、分发与回归流程）；执行细则见 `docs/维护脚本测试集.md`。

## 怎么跑起来 / 验证

- 纯提示词 skill（theme-commit、deep-research）：无运行时，直接读 SKILL.md。
- ddgs-web-access 需要 uv >= 0.5，命令不依赖当前工作目录：

```bash
bash ddgs-web-access/bin/ddgs-web-search "smoke test" -m 1
bash ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

- 仓库级维护脚本（纯 bash，零依赖）：

```bash
bash scripts/skills-lint.sh           # 结构/元数据校验：全绿 exit 0
bash scripts/skills-doctor.sh         # 链接健康矩阵
bash scripts/skills-link.sh --all     # 分发（幂等）
```

- 改动 ddgs-web-access 代码后按 `ddgs-web-access/docs/测试集.md` 回归；搜索/抓取调用间隔 ≥2 秒（ddgs 多引擎聚合，过频会限流）。
- 等价形式：`uv run --project ddgs-web-access <命令>`；Windows 用 `bin/*.cmd`。

## 技术栈

- ddgs-web-access：Python >= 3.10（uv 托管虚拟环境），依赖 ddgs + markdownify，单文件 CLI（`ddgs_web_access.py`）+ `bin/` 位置无关启动器；stdout 结果 / stderr 提示与错误 / 退出码 0-1-2。
- theme-commit：纯 SKILL.md 提示词（git 按主题分组提交），0.1.0。
- deep-research：纯 SKILL.md 提示词（先校准再调研：环境检查 → 预检索校准 → 选项式澄清 → 档位推荐 → 增量登记 → 双文档交付），0.1.0。
- scripts/：bash + coreutils 维护脚本套件，公共函数在 `scripts/lib.sh`；退出码统一 0-1-2，状态走 stdout、错误走 stderr。

## 目录与约定

- 一个 skill 一个目录，SKILL.md 为入口；frontmatter 需含 `name`（== 目录名）、三段式 `description`、`metadata.version`（semver）；版本权威来源是 frontmatter，pyproject.toml 与 SKILLS.md 台账跟随同步，lint 强制。
- 复杂 skill 另带 README.md 与 docs/（设计文档、测试集）；测试集编号用「类别前缀-序号」。
- 分发与卸载统一用 `bash scripts/skills-link.sh` / `skills-unlink.sh`（在四个 agent 目录建/删指向本仓库的 junction，单一来源）；ddgs-web-access 自带的 `scripts/install.sh` 仅供该 skill 独立拷走时使用。链接变更后跑 `skills-doctor.sh` 并回填台账"分发状态"列。
- 运行产物（`.venv/`、`.cache/`、`__pycache__/`、`*.egg-info/`）已 gitignore，不纳入版本管理，lint 会检查。
- `.zcode/`（会话计划产物）在根 .gitignore 中排除。

## 当前状态与下一步

- git 仓库已初始化（main 分支，2026-09-10），尚未配置远端。
- 仓库级维护脚本已就位：`scripts/`（lib / lint / doctor / link / unlink / new），规范与测试集在 `docs/`；改动脚本后按 `docs/维护脚本测试集.md` 回归。
- ddgs-web-access v0.2.0 已定稿：设计文档 v0.6、测试集 v1.1，三端链接验证生效。
- theme-commit v0.1.0：已补 `metadata.version` 与 `docs/测试集.md`，已链接三端。
- deep-research v0.1.0 已实现（SKILL.md + 需求与设计文档 v0.2 + 竞品调研 v0.1 + 测试集 v1.0），已链接三端；下一步：按测试集 V-1~V-14 跑首轮真实调研，回填档位取值（设计文档 O2）。
