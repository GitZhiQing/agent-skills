#!/usr/bin/env bash
# skills-new.sh — 从 template/ 生成新 skill 骨架，标准见 docs/CONVENTIONS.md §2/§9。
#
# usage: skills-new.sh <name> [--with-design]
#   <name> 为 kebab-case，与 frontmatter name 一致
#   --with-design 额外生成 docs/SPEC.md
# 退出码：0 创建成功 / 2 用法错误（非法名称 / 目录已存在 / 缺少模板）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

usage() {
  echo "usage: skills-new.sh <name> [--with-design]" >&2
  exit 2
}

[ $# -ge 1 ] && [ $# -le 2 ] || usage
name="$1"
with_design=0
if [ $# -eq 2 ]; then
  [ "$2" = "--with-design" ] || usage
  with_design=1
fi

name_re='^[a-z0-9]+(-[a-z0-9]+)*$'
if ! printf '%s' "$name" | grep -Eq "$name_re"; then
  echo "ERROR: name 须为 kebab-case（小写字母/数字/连字符，不以连字符开头或结尾，无连续连字符）：$name" >&2
  exit 2
fi
if [ "${#name}" -gt 64 ]; then
  echo "ERROR: name 超过官方上限 64 字符：$name" >&2
  exit 2
fi

template_dir="$REPO_ROOT/template"
[ -d "$template_dir" ] || { echo "ERROR: 缺少模板目录：$template_dir" >&2; exit 2; }

dir="$(skill_dir "$name")"
[ ! -e "$dir" ] || { echo "ERROR: 目录已存在：$dir" >&2; exit 2; }

mkdir -p "$dir/docs" "$dir/.claude-plugin"

copy_tpl() {
  local src="$1" dst="$2"
  sed "s|__NAME__|$name|g" "$src" > "$dst"
}

copy_tpl "$template_dir/SKILL.md" "$dir/SKILL.md"
copy_tpl "$template_dir/README.md" "$dir/README.md"
copy_tpl "$template_dir/docs/TESTS.md" "$dir/docs/TESTS.md"
copy_tpl "$template_dir/.claude-plugin/plugin.json" "$dir/.claude-plugin/plugin.json"
if [ "$with_design" -eq 1 ]; then
  copy_tpl "$template_dir/docs/SPEC.md" "$dir/docs/SPEC.md"
fi

echo "created: $dir"
echo
echo "后续步骤（规范 §9）："
echo "  1. 填写 SKILL.md 的三段式 description 与正文；条件分支放 references/"
echo "  2. 在 README Skills 表补一行（不写版本号）"
echo "  3. 在 .claude-plugin/marketplace.json 补一个 plugin 条目"
echo "  4. 本机维护者另在 SKILLS.local.md 补总览一行 + 明细一节"
echo "  5. bash scripts/skills-lint.sh    # 应全绿"
echo "  6. bash scripts/skills-link.sh $name && bash scripts/skills-doctor.sh"
