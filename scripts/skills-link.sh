#!/usr/bin/env bash
# skills-link.sh — 把 skill 链接分发到本机已发现的 agent skills 目录
# （Windows junction / Unix symlink，单一来源：agent 始终经链接读本仓库）。
#
# 目标清单 = 内置主流 agent 清单 ⊕ agents.local.conf 本地自定义
# （docs/开发与维护规范.md §6），目录存在才生效。
#
# usage: skills-link.sh [--agent <name|name=path>]... <skill-name>... | --all
# --agent：name 只分发到该目标（可重复）；name=path 临时指定/覆盖目标目录。
# 幂等：已存在的条目 skip；已链接的跳过，异常条目（foreign/broken）skip 并
# 提示用 skills-doctor.sh 查看。反向操作：skills-unlink.sh（参数相同）。
# 退出码：0 完成 / 1 有链接创建失败 / 2 用法错误。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

orig_args="$*"
agent_flags=()
rest=()
while [ $# -gt 0 ]; do
  case "$1" in
    --agent)
      [ $# -ge 2 ] || { echo "ERROR: --agent 缺参数（name 或 name=path）" >&2; exit 2; }
      agent_flags+=("$2"); shift 2 ;;
    *)
      rest+=("$1"); shift ;;
  esac
done
[ ${#rest[@]} -ge 1 ] || { echo "usage: skills-link.sh [--agent <name|name=path>]... <skill-name>... | --all" >&2; exit 2; }
skills="$(resolve_skills "${rest[@]}")"
targets="$(resolve_agent_targets ${agent_flags[@]+"${agent_flags[@]}"})"

fail=0
while IFS= read -r skill; do
  while IFS=$'\t' read -r _ d; do
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
  done <<<"$targets"
done <<<"$skills"

echo
[ "$fail" -eq 0 ] || exit 1
echo "done. 巡检：bash scripts/skills-doctor.sh；卸载：bash scripts/skills-unlink.sh $orig_args"
