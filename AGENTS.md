# AGENTS.md — skills

个人 AI coding agent skills 集合：每个 skill 位于 `skills/` 下一个目录，通过 junction/软链分发到各 agent 的 skills 目录（目标 = 内置主流清单 ⊕ `agents.local.conf`，目录存在才生效，清单见 `docs/CONVENTIONS.md` §6）。

## 改前必读

1. [docs/CONVENTIONS.md](docs/CONVENTIONS.md) — 目录、frontmatter、版本、分发、脚本规则、提交信息。
2. [spec/agent-skills-spec.md](spec/agent-skills-spec.md) — 官方规范指针与本仓库加严项。
3. 目标 skill 的 `README.md` 与 `docs/TESTS.md`；新增 skill 先用 `template/` 或 `scripts/skills-new.sh`。

## 怎么跑起来 / 验证

纯提示词 skill（deep-research、theme-commit、zero-coding、session-handoff）无运行时，直接读 `SKILL.md` 并按 `docs/TESTS.md` 人工回归。

```bash
# 仓库级校验（纯 bash，零依赖；退出码 0/1/2）
bash scripts/skills-lint.sh           # 结构/元数据：全绿 exit 0
bash scripts/skills-doctor.sh         # 链接健康矩阵
bash scripts/skills-link.sh --all     # 分发（幂等）

# ddgs-web-access（uv >= 0.5；调用间隔 >=2 秒）
bash skills/ddgs-web-access/bin/ddgs-web-search "smoke test" -m 1
bash skills/ddgs-web-access/bin/ddgs-web-fetch "https://example.com"

# md2pdf（uv >= 0.5 + 系统 Edge；首次 fetch 约 15MB）
bash skills/md2pdf/bin/md2pdf --help
bash skills/md2pdf/bin/md2pdf fetch

# video-insight（纯标准库；外部依赖 ffmpeg/ffprobe）
python -m unittest discover -s skills/video-insight/tests

# windows-disk-cleanup（纯标准库 + PowerShell 辅助；uv 可选）
python -m unittest discover -s skills/windows-disk-cleanup/tests
python skills/windows-disk-cleanup/scripts/memory.py check --json
bash skills/windows-disk-cleanup/bin/windows-disk-cleanup doctor --root . --json
```

视频单测 163 条，真实托管 API 用例需 `VOLC_BIGMODEL_API_KEY` / `PADDLEOCR_ACCESS_TOKEN`，未设置自动跳过。windows-disk-cleanup 单测 42 条，真实扫描/回收站用例需在 Windows 人工执行。md2pdf 改动按 `skills/md2pdf/docs/TESTS.md` 回归，核心质量门为 S-3 canary 双版式。

## skill 矩阵

| Skill | 形态 | 入口 | 验证 |
| --- | --- | --- | --- |
| ddgs-web-access | Python CLI（uv） | `skills/ddgs-web-access/SKILL.md` | 两个 bin 冒烟 + `docs/TESTS.md` |
| deep-research | 纯提示词 | `skills/deep-research/SKILL.md` | `docs/TESTS.md`（人工会话） |
| theme-commit | 纯提示词 | `skills/theme-commit/SKILL.md` | `docs/TESTS.md`（人工会话） |
| zero-coding | 纯提示词 | `skills/zero-coding/SKILL.md` | `docs/TESTS.md`（人工会话） |
| session-handoff | 纯提示词 | `skills/session-handoff/SKILL.md` | `docs/TESTS.md`（人工会话） |
| video-insight | Python 脚本（标准库） | `skills/video-insight/SKILL.md` | unittest + `docs/TESTS.md` |
| md2pdf | Python CLI（uv） | `skills/md2pdf/SKILL.md` | `--help` + canary S-3 + `docs/TESTS.md` |
| windows-disk-cleanup | Python CLI（标准库 + PowerShell） | `skills/windows-disk-cleanup/SKILL.md` | unittest + memory check + `docs/TESTS.md` |

架构与依赖细节写在各 skill 的 `README.md` / `docs/SPEC.md`（md2pdf 为 `docs/SPEC.md` + `docs/DECISIONS.md`），本文不重复。

## 目录与约定

- 一个 skill 一个目录，`SKILL.md` 为入口；frontmatter 需含 `name`（== 目录名）、三段式 `description`、`metadata.version`（semver，版本唯一权威）与 `metadata.category`（建议）。
- 每个 skill 必须有 `README.md` 与 `.claude-plugin/plugin.json`，并在 `.claude-plugin/marketplace.json` 有对应条目；应带 `docs/TESTS.md`（缺失 lint warn）。
- 详细条件分支、模板、长清单放 `references/`（距 `SKILL.md` 一层）；`SKILL.md` 目标 ≤500 行 / ≤16KB，只留核心流程与"何时读哪个文件"。
- README 的 `## Skills` 表是唯一公开目录，列固定 `Skill | 说明`，不展示类型与版本号。
- 维护者个人的台账、分发状态与下一步计划记录在 `SKILLS.local.md`（gitignore `*.local.md`，不入库）。
- 分发与卸载统一用 `bash scripts/skills-link.sh` / `skills-unlink.sh`；链接变更后跑 doctor 并回填台账。内置目标清单的权威实现是 `scripts/lib.sh` 的 `builtin_agent_targets()`。
- 运行产物（`.venv/`、`.cache/`、`__pycache__/`、`*.egg-info/`）已 gitignore，lint 检查不得入库；`.zcode/` 同样排除。
- 不改写 Git 历史、不推送；提交信息遵循规范 §10（`type(scope): 摘要` + 列表式 body）。

## 完成定义

`skills-lint.sh` exit 0 且 0 error；受影响 skill 的测试集已回归（代码型另跑自动化测试）；链接变更后 doctor 无 broken；版本在 `SKILL.md` / `pyproject.toml` / `plugin.json` / `marketplace.json` / 台账间一致。
