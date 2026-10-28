# 维护脚本测试集

版本：v1.6

对象：仓库根 `scripts/` 下 5 个脚本（`lib.sh` 为被 source 的公共库，随各脚本覆盖）。标准与行为定义见 [CONVENTIONS.md](CONVENTIONS.md) §2–§5、§8。涉及临时改动的用例（L-2/L-3/L-5/L-7/L-8/L-9/L-10~L-16、D-2/D-3/D-4、K-6/K-7、N-1~N-5）执行后必须还原，还原后以 L-1 全绿收尾。

## 1. lint 场景（L）

### L-1 全绿基线

场景：仓库处于规范合规状态。

▶ `bash scripts/skills-lint.sh`

- = 输出含每个 skill 的 ok 行，末尾 `lint: N ok, 0 warn, 0 error`
- = exit 0

### L-2 README 目录表漂移检出

场景：README `## Skills` 表临时追加一行虚构 skill（如 `ghost-skill`）。

▶ `bash scripts/skills-lint.sh`

- = ERROR：README 目录表的「ghost-skill」在磁盘上不存在
- = exit 1；还原后 L-1 恢复全绿

### L-3 版本失配检出

场景：临时把 ddgs-web-access frontmatter 的 `metadata.version` 改为 `9.9.9`。

▶ `bash scripts/skills-lint.sh`

- = ERROR：版本不一致：SKILL.md 9.9.9 != pyproject.toml 0.2.2
- = ERROR：plugin.json / marketplace.json 版本与 frontmatter 不一致
- = 如存在本地台账，另报本地台账总览版本与 frontmatter 不一致
- = README Skills 表只有 Skill / 说明 两列，不参与版本校验
- = exit 1；还原后恢复

### L-4 name 失配检出

场景：临时把某 skill frontmatter 的 `name` 改为与目录名不同的值。

▶ `bash scripts/skills-lint.sh`

- = ERROR：frontmatter name 与目录名不一致
- = exit 1；还原后恢复

### L-5 运行产物入库检出

场景：`mkdir -p skills/ddgs-web-access/.venv && touch skills/ddgs-web-access/.venv/x && git add -f skills/ddgs-web-access/.venv/x`。

▶ `bash scripts/skills-lint.sh`

- = ERROR：运行产物已入库：skills/ddgs-web-access/.venv/x
- = exit 1；`git rm --cached` + 删除文件还原后恢复

### L-6 skill 目录越位检出

场景：临时在仓库根建 `mkdir mock-skill && touch mock-skill/SKILL.md`。

▶ `bash scripts/skills-lint.sh`

- = ERROR：skill「mock-skill」不在 skills/ 下
- = exit 1；删除 mock-skill 还原后恢复

### L-7 外部克隆视角（无本地台账）

场景：临时移走 `SKILLS.local.md`（模拟外部克隆，仓库不含该文件）。

▶ `bash scripts/skills-lint.sh`

- = 输出含 `info: 无本地台账（SKILLS.local.md），跳过台账检查`
- = 末尾 `lint: N ok, 0 warn, 0 error`，exit 0；还原后 L-1 恢复全绿

### L-8 本地台账漂移检出

场景：`SKILLS.local.md` 总览表临时追加一行虚构 skill（如 `ghost-skill`）。

▶ `bash scripts/skills-lint.sh`

- = ERROR：本地台账总览的「ghost-skill」在磁盘上不存在（+ 明细缺少小节）
- = exit 1；还原后恢复

### L-9 skill README 缺失检出

场景：临时移走某 skill（如 theme-commit）的 README.md。

▶ `bash scripts/skills-lint.sh`

- = ERROR：theme-commit: 缺少 README.md（规范 §2）
- = exit 1；还原后 L-1 恢复全绿

### L-10 name 官方约束检出

场景：临时建 `skills/Mock_Skill/SKILL.md`（frontmatter `name: Mock_Skill`，补 version/description）。

▶ `bash scripts/skills-lint.sh`

- = ERROR：name 不符合官方字符集（仅小写字母/数字/连字符）
- = 目录名与 name 一致，所以不报 name 失配
- = 删除目录后恢复

### L-11 description 上限与尖括号检出

场景：临时把某 skill 的 description 改为含 `<tag>`；另一次改成超过 1024 字符。

▶ `bash scripts/skills-lint.sh`

- = ERROR：description 含 `<` 或 `>`
- = ERROR：description 超过 1024 字符
- = 还原后恢复

### L-12 plugin.json 缺失与版本漂移检出

场景：临时移走 `skills/md2pdf/.claude-plugin/plugin.json`；还原后把其 `version` 改为 `9.9.9`。

▶ `bash scripts/skills-lint.sh`

- = ERROR：md2pdf: 缺少 .claude-plugin/plugin.json
- = ERROR：md2pdf: plugin.json 版本 9.9.9 与 frontmatter 不一致
- = 还原后恢复

### L-13 marketplace 覆盖与版本检出

场景：把 marketplace 中 video-insight 条目的 `version` 改为 `9.9.9`；另一次临时删除该条目。

▶ `bash scripts/skills-lint.sh`

- = ERROR：marketplace.json 中 video-insight 版本与 frontmatter 不一致
- = ERROR：video-insight 未出现在 marketplace.json
- = 还原后恢复

### L-14 SKILL.md 体积 warn

场景：临时向某 skill 的 SKILL.md 追加 600 行注释。

▶ `bash scripts/skills-lint.sh`

- = warn：SKILL.md 超过 500 行 / 16KB，建议拆分到 references/
- = exit 0（warn 不阻塞）；还原后恢复

### L-15 references 链接缺失检出

场景：临时在 SKILL.md 末尾加 `references/ghost.md`。

▶ `bash scripts/skills-lint.sh`

- = ERROR：SKILL.md 引用的 references/ghost.md 不存在
- = exit 1；还原后恢复

### L-16 测试集缺失 warn

场景：临时移走某 skill 的 `docs/TESTS.md`。

▶ `bash scripts/skills-lint.sh`

- = warn：缺少 docs/TESTS.md（规范 §2）
- = exit 0（warn 不阻塞）；还原后恢复

## 2. doctor 场景（D）

### D-1 健康矩阵

场景：`skills-link.sh --all` 后。

▶ `bash scripts/skills-doctor.sh`

- = 全部现存 agent 目录列均为 linked
- = 末尾 `doctor: N linked, 0 missing, 0 foreign, 0 broken`，exit 0

### D-2 broken 检出

场景：在某个 agent skills 目录手工建一个指向不存在路径的 junction（`cmd /c mklink /J <agent>/skills/<skill> C:\nonexistent\<skill>`）。

▶ `bash scripts/skills-doctor.sh`

- = 该格显示 broken，stderr 有 `ERROR: broken: <skill> @ <dir>`
- = exit 1；删掉该 junction 还原后恢复

### D-3 foreign 识别

场景：在某个 agent skills 目录把某 skill 换成指向其他真实目录的链接（或真实拷贝目录）。

▶ `bash scripts/skills-doctor.sh`

- = 该格显示 foreign，exit 0（warn 不算失败）
- = 还原（删掉后重跑 skills-link.sh）后恢复

### D-4 conf 自定义目标出现在矩阵

场景：仓库根临时写 `agents.local.conf`，新增一行 `mockagent <临时目录>/mockagent-skills`（目录已 mkdir），并 `bash scripts/skills-link.sh --agent mockagent theme-commit`。

▶ `bash scripts/skills-doctor.sh`

- = targets 行含 mockagent，矩阵出现 mockagent 列且 theme-commit 行为 linked
- = 删除 conf、移除临时链接与目录后恢复，L-1 收尾

## 3. link / unlink 场景（K）

### K-1 幂等

▶ `bash scripts/skills-link.sh --all` 连续执行两次

- = 第二次全部 `skip (already linked)`，无新建、无报错
- = 两次均 exit 0

### K-2 指名单链接

▶ `bash scripts/skills-link.sh theme-commit`

- = 只动 theme-commit 相关链接；未安装的 agent 目录自动跳过
- = doctor 中 theme-commit 行全部 linked

### K-3 安全卸载（不误删拷贝）

场景：某 agent skills 目录下放一个该 skill 的**真实拷贝**目录（非链接）。

▶ `bash scripts/skills-unlink.sh --all`

- = 拷贝目录 `skip (not pointing to this repo)`，不被删除
- = 指向本仓库的链接全部 `removed:`

### K-4 未知名称拒绝

▶ `bash scripts/skills-link.sh not-a-skill`

- = stderr `ERROR: 不是本仓库的 skill：not-a-skill`，exit 2，无任何链接动作

### K-5 --agent 过滤指定目标

场景：先 `bash scripts/skills-unlink.sh theme-commit` 造出全端 missing。

▶ `bash scripts/skills-link.sh --agent claude theme-commit`

- = 只有 `~/.claude/skills/theme-commit` 被补链（输出仅一行 linked），其余目录不动
- = 补跑 `bash scripts/skills-link.sh theme-commit` 恢复全端

### K-6 --agent 临时目标（name=path）

场景：`mkdir -p /tmp/mock-skills`。

▶ `bash scripts/skills-link.sh --agent mock=/tmp/mock-skills --all`

- = 当前全部 skill 均链接到 /tmp/mock-skills 下
- = 临时目标不落盘：doctor 矩阵不出现 mock 列
- = 清理 /tmp/mock-skills 下的链接后恢复

### K-7 conf 禁用内置目标

场景：仓库根临时写 `agents.local.conf`，内容一行 `!claude`。

▶ `bash scripts/skills-doctor.sh`

- = targets 行与矩阵均无 claude；link/unlink 同样不操作该目录
- = 删除 conf 后恢复（claude 列回归），L-1 收尾

### K-8 未知分发目标拒绝

▶ `bash scripts/skills-link.sh --agent nope theme-commit`

- = stderr `ERROR: 未知分发目标：nope`（附可用名称列表），exit 2，无任何链接动作

## 4. new 场景（N）

### N-1 骨架合法且触发仓库级校验

▶ `bash scripts/skills-new.sh test-skill` 后 `bash scripts/skills-lint.sh`

- = 生成 `SKILL.md`、`README.md`、`docs/TESTS.md`、`.claude-plugin/plugin.json`
- = test-skill 自身的 frontmatter / version / description / README / plugin / references 检查通过
- = ERROR：README Skills 目录表缺少该 skill 的行（L-readme）
- = ERROR：test-skill 未出现在 marketplace.json（L-plugin）
- = ERROR：本地台账总览缺少该 skill 的行（L-ledger，仅本机存在 SKILLS.local.md 时）
- = 可选 warn：缺少 metadata.category
- = exit 1

### N-1a 骨架描述中的反引号与引号不误报 references

场景：N-1 生成后，SKILL.md 的"按需读取"说明含 `references/` 与"见 references/"这类文字。

▶ `bash scripts/skills-lint.sh`

- = 不出现「SKILL.md 引用的 references/... 不存在」误报
- = 仅报 N-1 列出的仓库级缺失项

### N-2 拒绝重名

▶ 再次 `bash scripts/skills-new.sh test-skill`

- = stderr 报目录已存在，exit 2

### N-3 拒绝非法名称

▶ `bash scripts/skills-new.sh Bad_Name`（及 `foo-`、`-foo`、`foo--bar`、超过 64 字符）

- = stderr 报 kebab-case / 长度约束，exit 2

### N-4 还原

▶ `rm -rf skills/test-skill` 后 `bash scripts/skills-lint.sh`

- = 恢复 L-1 全绿，exit 0

### N-5 设计文档可选生成

▶ `bash scripts/skills-new.sh test-skill --with-design`

- = 额外生成 `docs/SPEC.md`
- = 其余输出与 N-1 一致
- = `rm -rf skills/test-skill` 还原

## 5. 回归执行约定

- 改动 `scripts/` 任一脚本后，按本测试集跑受影响类别的用例；执行结果不做文档留痕，以当次会话或提交说明为准。
- 破坏性用例（临时改动仓库内容或链接）执行后必须还原，还原后以 L-1 全绿收尾。
- D-2/D-3 等涉及手工改链接的用例只在必要时执行。
