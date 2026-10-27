# 贡献指南

面向要修改本仓库的人。维护标准以 [docs/开发与维护规范.md](docs/开发与维护规范.md) 为准；本文只给最短路径与自检清单。

## 5 分钟上手

```bash
git clone <repo> && cd skills
bash scripts/skills-lint.sh      # 结构/元数据校验，应 exit 0
bash scripts/skills-link.sh --all # 分发到本机已存在的 agent 目录
bash scripts/skills-doctor.sh    # 链接健康矩阵，应全部 linked
```

脚本为纯 bash + coreutils，零外部依赖；退出码统一 0 成功 / 1 失败 / 2 用法。

## 文档地图

| 文档 | 读者 | 用途 |
| --- | --- | --- |
| [README.md](README.md) | 使用者 | skill 目录、安装、快速使用 |
| [AGENTS.md](AGENTS.md) | AI 会话 | 运行/验证命令与完成定义 |
| [docs/开发与维护规范.md](docs/开发与维护规范.md) | 维护者 | 目录、frontmatter、版本、分发、脚本规则、提交规范 |
| [docs/维护脚本测试集.md](docs/维护脚本测试集.md) | 维护者 | `scripts/` 的回归用例 |
| [spec/agent-skills-spec.md](spec/agent-skills-spec.md) | 维护者 | 官方规范指针与本仓库加严项 |
| [template/](template/) | 维护者 | 新 skill 骨架 |

## 改动流程

### 修改现有 skill

1. 读该 skill 的 `SKILL.md`、`README.md`、`docs/测试集.md`。
2. 只改必要文件；行为语义变化时按规范 §4 升版本，并同步 `pyproject.toml`（若有）、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`。
3. 按该 skill 的测试集回归；`video-insight` 另跑 `python -m unittest discover -s skills/video-insight/tests`；`windows-disk-cleanup` 另跑 `python -m unittest discover -s skills/windows-disk-cleanup/tests` 与 `python skills/windows-disk-cleanup/scripts/memory.py check --json`。
4. `bash scripts/skills-lint.sh` 全绿。

### 新增 skill

```bash
bash scripts/skills-new.sh my-skill            # 生成 SKILL/README/测试集/plugin.json
bash scripts/skills-new.sh my-skill --with-design  # 另生成设计文档
```

然后：

1. 填写 `SKILL.md` 的三段式 description、正文与"按需读取"表；条件分支放 `references/`。
2. 按规范 §2 判定是否补 `docs/测试集.md`（默认已生成）与设计文档。
3. 在根 `README.md` 的 `## Skills` 表补一行（不写版本号）。
4. 在 `.claude-plugin/marketplace.json` 补一个 plugin 条目。
5. 本机维护者另在 `SKILLS.local.md` 补总览一行 + 明细一节。
6. 代码型 skill 在 `.github/workflows/ci.yml` 增加对应测试 job（Windows-only 用 `windows-latest`）；纯提示词 skill 仍按测试集人工回归。
7. `bash scripts/skills-lint.sh` → `bash scripts/skills-link.sh my-skill` → `bash scripts/skills-doctor.sh`。

### 修改维护脚本

1. 改 `scripts/` 下脚本或 `scripts/lib.sh`。
2. 按 [docs/维护脚本测试集.md](docs/维护脚本测试集.md) 跑受影响类别（L-/D-/K-/N-）。
3. 破坏性用例执行后必须还原，并以 L-1 全绿收尾。

## 完成定义

- `bash scripts/skills-lint.sh` exit 0，0 error（新增 warn 需有理由）。
- 受影响的 skill 测试集已回归；代码型 skill 的自动化测试通过。
- 链接变更后 `bash scripts/skills-doctor.sh` 无 broken，并回填本地台账。
- 版本在 `SKILL.md` / `pyproject.toml` / `plugin.json` / `marketplace.json` / 台账间一致。

## 提交信息

遵循 [docs/开发与维护规范.md](docs/开发与维护规范.md) §10：`type(scope): 摘要` + 空行 + `- ` 列表式 body；不写版本号到 subject，不写零信息摘要。多主题变更用 `theme-commit` skill 分批。

## 自检清单

- [ ] description 仍是三段式，含正向触发与反向不触发
- [ ] 新分支写进了 `references/` 而不是继续堆 SKILL.md
- [ ] README 没有复制 SKILL.md 全文，也没有版本号
- [ ] 版本已在所有机器可读位置同步
- [ ] 没有把运行产物（`.venv/`、`__pycache__/`、`.env`）加入版本管理
- [ ] 未推送、未改写历史（除非用户明确要求）
