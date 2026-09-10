#!/usr/bin/env bash
# skills-new.sh — 按规范生成新 skill 骨架（SKILL.md 标准三段式 frontmatter
# + docs/测试集.md 编号模板），标准见 docs/开发与维护规范.md §3/§9。
#
# usage: skills-new.sh <name>    name 为 kebab-case，与 frontmatter name 一致
# 退出码：0 创建成功 / 2 用法错误（非法名称 / 目录已存在）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

[ $# -eq 1 ] || { echo "usage: skills-new.sh <name>" >&2; exit 2; }
name="$1"
printf '%s' "$name" | grep -Eq '^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$' || {
  echo "ERROR: name 须为 kebab-case（小写字母/数字/连字符，不以连字符结尾）：$name" >&2
  exit 2
}
dir="$(skill_dir "$name")"
[ ! -e "$dir" ] || { echo "ERROR: 目录已存在：$dir" >&2; exit 2; }

mkdir -p "$dir/docs"

cat > "$dir/SKILL.md" <<EOF
---
name: $name
description: >-
  （一句话定位：这个 skill 为 agent 解决什么问题。）
  当用户<正向触发场景；触发词如"…""…">时使用。
  当用户<反向不触发场景：什么情况下明确不用>时，不要使用本 skill。
metadata:
  version: 0.1.0
  # category: <领域标签，建议填写；开放值集见 docs/开发与维护规范.md §3>
---

# $name：<一句话标题>

<正文：工作流程、规则、边界。有可断言行为协议的 skill 必须配 docs/测试集.md；
决策较多的 skill 另建 docs/需求与设计文档.md；规范见仓库根 docs/开发与维护规范.md。>
EOF

cat > "$dir/docs/测试集.md" <<EOF
# $name 测试集

版本：v0.1.0（随 skill 首版创建）。行为协议断言，人工会话执行；
编号采用「类别前缀-序号」（示例前缀 X），新场景追加不重排。

## 1. <类别>场景（X）

### X-1 <场景标题>

场景：<前置条件与输入>。

▶ <触发方式：用户如何调用 / 命令行>

- = <断言：期望行为>
- = <断言：明确禁止出现的行为>
EOF

echo "created: $dir"
echo
echo "后续步骤（规范 §9）："
echo "  1. 填写 SKILL.md 的 description 三段式与正文，按需补 docs/ 文档"
echo "  2. 在 SKILLS.md 补总览一行 + 明细一节（版本 0.1.0）"
echo "  3. bash scripts/skills-lint.sh    # 应全绿"
echo "  4. bash scripts/skills-link.sh $name && bash scripts/skills-doctor.sh"
