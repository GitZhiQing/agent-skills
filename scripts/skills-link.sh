#!/usr/bin/env bash
# skills-link.sh — 把 skill 链接分发到本机所有已发现的 agent skills 目录
# （Windows junction / Unix symlink，单一来源：agent 始终经链接读本仓库）。
#
# usage: skills-link.sh <skill-name>... | --all
# 幂等：已存在的条目 skip；已链接的跳过，异常条目（foreign/broken）skip 并
# 提示用 skills-doctor.sh 查看。反向操作：skills-unlink.sh。
# 退出码：0 完成 / 1 有链接创建失败 / 2 用法错误。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

[ $# -ge 1 ] || { echo "usage: skills-link.sh <skill-name>... | --all" >&2; exit 2; }
targets="$(resolve_skills "$@")"

fail=0
while IFS= read -r skill; do
  while IFS= read -r d; do
    [ -d "$d" ] || continue
    target="$d/$skill"
    if [ -e "$target" ] || [ -L "$target" ]; then
      state="$(link_state "$d" "$skill")"
      if [ "$state" = "linked" ]; then
        echo "skip (already linked): $target"
      else
        echo "skip (already exists, state=$state — 见 scripts/skills-doctor.sh): $target"
      fi
      continue
    fi
    if ! create_link "$d" "$skill"; then
      echo "ERROR: 链接创建失败：$target" >&2
      fail=1
      continue
    fi
    if [ ! -f "$target/SKILL.md" ]; then
      echo "ERROR: 已链接但经链接读不到 SKILL.md：$target" >&2
      fail=1
      continue
    fi
    echo "linked: $target -> $(skill_dir "$skill")"
  done < <(agent_skills_dirs)
done < <(printf '%s\n' "$targets")

echo
[ "$fail" -eq 0 ] || exit 1
echo "done. 巡检：bash scripts/skills-doctor.sh；卸载：bash scripts/skills-unlink.sh $*"
