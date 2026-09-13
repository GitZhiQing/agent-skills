#!/usr/bin/env bash
# skills-doctor.sh — 各 agent skills 目录的链接健康巡检。
#
# 输出 skill × agent 状态矩阵（状态定义见 lib.sh link_state）：
#   linked / missing（无链接，info）/ foreign（拷贝或指向别处，warn）/
#   broken（链接存在但读不到 SKILL.md，error）
#
# 坏链接在 agent 侧不会报错，所以任何链接变更后都应跑一次本脚本，
# 并据结果回填本地台账 SKILLS.local.md 的"分发状态"列（规范 §6）。
# 退出码：0 健康 / 1 存在 broken / 2 用法错误。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

[ $# -eq 0 ] || { echo "usage: skills-doctor.sh" >&2; exit 2; }

# 目标清单 = 内置主流 agent 清单 ⊕ agents.local.conf 本地自定义（规范 §6）；
# 只为本机实际存在的目录生成列，列名即清单 name。
targets="$(agent_targets)"
dirs=()
labels=()
absent=()
while IFS=$'\t' read -r name d; do
  if [ -d "$d" ]; then
    dirs+=("$d")
    labels+=("$name")
  else
    absent+=("$name")
  fi
done <<<"$targets"

[ "${#dirs[@]}" -gt 0 ] || { echo "ERROR: 未发现任何 agent skills 目录（内置清单见 docs/开发与维护规范.md §6，自定义见 agents.local.conf）" >&2; exit 1; }

if [ "${#absent[@]}" -gt 0 ]; then
  printf 'targets: %s（未检测到: %s）\n' \
    "$(printf '%s\n' "${labels[@]}" | paste -sd, -)" \
    "$(printf '%s\n' "${absent[@]}" | paste -sd, -)"
else
  printf 'targets: %s\n' "$(printf '%s\n' "${labels[@]}" | paste -sd, -)"
fi

n_linked=0 n_missing=0 n_foreign=0 n_broken=0
broken_details=()

printf '%-17s' "skill"
for lb in "${labels[@]}"; do printf '%-9s' "$lb"; done
printf '\n'

while IFS= read -r skill; do
  printf '%-17s' "$skill"
  for d in "${dirs[@]}"; do
    state="$(link_state "$d" "$skill")"
    case "$state" in
      linked)  n_linked=$((n_linked + 1)) ;;
      missing) n_missing=$((n_missing + 1)) ;;
      foreign) n_foreign=$((n_foreign + 1)) ;;
      broken)  n_broken=$((n_broken + 1)); broken_details+=("$skill @ $d") ;;
    esac
    printf '%-9s' "$state"
  done
  printf '\n'
done < <(list_skills)

printf '\ndoctor: %d linked, %d missing, %d foreign, %d broken\n' \
  "$n_linked" "$n_missing" "$n_foreign" "$n_broken"
[ "$n_missing" -eq 0 ] || printf 'hint: missing 可补链 bash scripts/skills-link.sh <name>（或 --all）\n'
[ "$n_foreign" -eq 0 ] || printf 'hint: foreign 为真实拷贝或指向别处的链接，本仓库脚本不会改动它\n'
if [ "$n_broken" -gt 0 ]; then
  for t in "${broken_details[@]}"; do printf 'ERROR: broken: %s\n' "$t" >&2; done
  printf 'hint: broken 先用 bash scripts/skills-unlink.sh <name> 清理，再重新链接\n' >&2
  exit 1
fi
exit 0
