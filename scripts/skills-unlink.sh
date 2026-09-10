#!/usr/bin/env bash
# skills-unlink.sh — 从 agent skills 目录删除本仓库的链接。
#
# usage: skills-unlink.sh <skill-name>... | --all
# 安全性：只删确认指向本仓库对应 skill 目录的条目（含已悬空但指向本仓库的）；
# 真实拷贝或指向别处的链接一律 skip，不会误删。
# 退出码：0 完成 / 1 有删除失败 / 2 用法错误。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

[ $# -ge 1 ] || { echo "usage: skills-unlink.sh <skill-name>... | --all" >&2; exit 2; }
targets="$(resolve_skills "$@")"

fail=0
while IFS= read -r skill; do
  while IFS= read -r d; do
    [ -d "$d" ] || continue
    target="$d/$skill"
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
      continue
    fi
    if [ "$(link_state "$d" "$skill")" = "linked" ] || link_points_to_repo "$d" "$skill"; then
      if ! remove_link "$d" "$skill"; then
        echo "ERROR: 删除失败：$target" >&2
        fail=1
        continue
      fi
      echo "removed: $target"
    else
      echo "skip (not pointing to this repo): $target"
    fi
  done < <(agent_skills_dirs)
done < <(printf '%s\n' "$targets")

echo
[ "$fail" -eq 0 ] || exit 1
echo "done."
