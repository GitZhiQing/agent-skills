#!/usr/bin/env bash
# skills-lint.sh — 仓库结构与元数据一致性校验。
#
# 检查项（标准见 docs/开发与维护规范.md）：
#   L-frontmatter  每个 skill 有 SKILL.md + 合法 frontmatter，name 与目录名
#                  一致，description 非空（过短仅 warn）
#   L-readme-file  每个 skill 目录含 README.md（面向人的导览，规范 §2）
#   L-version      metadata.version 必须存在且为 semver；若 skill 带
#                  pyproject.toml 则两处一致；与 README 目录表版本列一致
#   L-readme       README Skills 目录表 ↔ 磁盘双向一致
#   L-ledger       本机存在 SKILLS.local.md 时：本地台账总览 ↔ 磁盘双向一致，
#                  总览每行有对应明细小节，明细无孤儿小节；无本地台账则跳过
#                  （外部克隆视角全绿）
#   L-layout       skill 必须位于 skills/ 子目录（skills/<name>/SKILL.md），
#                  根级不允许出现 skill 目录
#   L-artifacts    运行产物（.venv/ .cache/ __pycache__/ *.egg-info/）未入库
#
# 退出码：0 全部通过 / 1 存在失配 / 2 用法错误。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

[ $# -eq 0 ] || { echo "usage: skills-lint.sh" >&2; exit 2; }

oks=0 warns=0 errors=0
ok()   { printf 'ok: %s\n' "$*"; oks=$((oks + 1)); }
warn() { printf 'warn: %s\n' "$*"; warns=$((warns + 1)); }
err()  { printf 'ERROR: %s\n' "$*" >&2; errors=$((errors + 1)); }

semver_re='^[0-9]+\.[0-9]+\.[0-9]+$'

# --- 目录表解析（README Skills 表 / 本地台账总览，两者同构） ------------------

# catalog_rows <file> <section-regex>：目录表每行输出 "name<TAB>version"。
# 列位置固定 $2=Skill、$3=版本；Skill 列可为 [name](link) 或裸目录名。
catalog_rows() {
  awk -F'|' -v sec="$2" '
    /^## / { in_ov = ($0 ~ sec) }
    in_ov && /^\|/ && NF >= 4 {
      s = $2; v = $3
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
      if (s ~ /^[-: ]+$/ || s == "Skill") next
      if (s ~ /^\[/) { sub(/^\[/, "", s); sub(/\].*$/, "", s) }
      else { sub(/\/$/, "", s) }
      print s "\t" v
    }
  ' "$1"
}

# readme_rows：README `## Skills` 公开目录表，lint 强制。
readme_rows() { catalog_rows "$README_FILE" '^## Skills'; }

# ledger_rows / ledger_details：维护者本地台账，存在时才校验。
ledger_rows() { catalog_rows "$LEDGER" '^## 总览'; }
ledger_details() {
  awk '/^## / { in_det = ($0 ~ /^## 明细/) }
       in_det && /^### / { s = $2; sub(/\/$/, "", s); print s }' "$LEDGER"
}

readme_name_list="$(readme_rows | cut -f1)"

# --- 逐 skill 检查 -----------------------------------------------------------

skills_list="$(list_skills)"
if [ -z "$skills_list" ]; then
  err "未发现任何 skill（每个 skill 需为 skills/ 下含 SKILL.md 的子目录）"
fi

for skill in $skills_list; do
  if fm_exists "$skill"; then
    ok "$skill: frontmatter 完整"
  else
    err "$skill: SKILL.md 缺少 YAML frontmatter（首行 --- 起始，存在闭合 ---）"
    continue
  fi

  fm_name="$(fm_value "$skill" name)"
  if [ -z "$fm_name" ]; then
    err "$skill: frontmatter 缺少 name"
  elif [ "$fm_name" != "$skill" ]; then
    err "$skill: frontmatter name「$fm_name」与目录名不一致"
  else
    ok "$skill: name 与目录名一致"
  fi

  desc_chars="$(fm_description_chars "$skill")"
  if [ "$desc_chars" -eq 0 ]; then
    err "$skill: description 为空"
  elif [ "$desc_chars" -lt 30 ]; then
    warn "$skill: description 仅 ${desc_chars} 字符，难以承载正向触发 + 反向不触发（规范 §3）"
  else
    ok "$skill: description 非空（${desc_chars} 字符）"
  fi

  if [ -f "$SKILLS_DIR/$skill/README.md" ]; then
    ok "$skill: README.md 存在"
  else
    err "$skill: 缺少 README.md（规范 §2：面向人的目录导览，全部 skill 必备）"
  fi

  ver="$(fm_subvalue "$skill" metadata version)"
  if [ -z "$ver" ]; then
    err "$skill: frontmatter 缺少 metadata.version（规范 §3：全部 skill 必须标注）"
  elif ! printf '%s' "$ver" | grep -Eq "$semver_re"; then
    err "$skill: metadata.version「$ver」不是 semver（X.Y.Z）"
  else
    ok "$skill: metadata.version $ver"
  fi

  if [ -f "$SKILLS_DIR/$skill/pyproject.toml" ]; then
    pp_ver="$(awk -F'"' '/^version[[:space:]]*=/ { print $2; exit }' "$SKILLS_DIR/$skill/pyproject.toml")"
    if [ -n "$ver" ] && [ -n "$pp_ver" ] && [ "$ver" != "$pp_ver" ]; then
      err "$skill: 版本不一致：SKILL.md $ver != pyproject.toml $pp_ver"
    else
      ok "$skill: pyproject.toml 版本一致（$pp_ver）"
    fi
  fi

  if printf '%s\n' "$readme_name_list" | grep -qx "$skill"; then
    # frontmatter 版本本身有问题时跳过比对，避免重复报错
    if [ -n "$ver" ] && printf '%s' "$ver" | grep -Eq "$semver_re"; then
      row_ver="$(readme_rows | awk -F'\t' -v s="$skill" '$1 == s { print $2; exit }')"
      if [ "$row_ver" != "$ver" ]; then
        err "$skill: README 目录表版本「$row_ver」与 frontmatter「$ver」不一致"
      else
        ok "$skill: README 目录表版本一致（$ver）"
      fi
    fi
  else
    err "$skill: README Skills 目录表缺少该 skill 的行"
  fi
done

# --- README 目录表 ↔ 磁盘，双向一致 -------------------------------------------

for name in $readme_name_list; do
  if ! printf '%s\n' "$skills_list" | grep -qx "$name"; then
    err "README 目录表的「$name」在磁盘上不存在（目录缺失或无 SKILL.md）"
  fi
done

# --- 本地台账（可选）：存在时校验，外部克隆视角跳过 ---------------------------

if [ -f "$LEDGER" ]; then
  ledger_name_list="$(ledger_rows | cut -f1)"
  ledger_detail_list="$(ledger_details)"

  for skill in $skills_list; do
    if printf '%s\n' "$ledger_name_list" | grep -qx "$skill"; then
      ver="$(fm_subvalue "$skill" metadata version)"
      if [ -n "$ver" ] && printf '%s' "$ver" | grep -Eq "$semver_re"; then
        row_ver="$(ledger_rows | awk -F'\t' -v s="$skill" '$1 == s { print $2; exit }')"
        if [ "$row_ver" != "$ver" ]; then
          err "$skill: 本地台账总览版本「$row_ver」与 frontmatter「$ver」不一致"
        else
          ok "$skill: 本地台账总览版本一致（$ver）"
        fi
      fi
    else
      err "$skill: 本地台账总览缺少该 skill 的行（SKILLS.local.md）"
    fi
  done

  for name in $ledger_name_list; do
    if ! printf '%s\n' "$skills_list" | grep -qx "$name"; then
      err "本地台账总览的「$name」在磁盘上不存在（目录缺失或无 SKILL.md）"
    fi
    if ! printf '%s\n' "$ledger_detail_list" | grep -qx "$name"; then
      err "本地台账明细缺少「$name」小节（### $name）"
    fi
  done
  for name in $ledger_detail_list; do
    if ! printf '%s\n' "$ledger_name_list" | grep -qx "$name"; then
      err "本地台账明细的「$name」小节没有对应总览行"
    fi
  done
else
  printf 'info: 无本地台账（%s），跳过台账检查\n' "$(basename "$LEDGER")"
fi

# --- 目录布局：skill 必须在 skills/ 下，根级仅允许仓库级目录 ------------------

for d in "$REPO_ROOT"/*/; do
  name="$(basename "$d")"
  if [ -f "${d}SKILL.md" ]; then
    err "skill「$name」不在 skills/ 下（规范 §2）"
  elif [ "$name" = docs ] || [ "$name" = scripts ] || [ "$name" = skills ]; then
    :
  else
    printf 'info: 非技能目录（无 SKILL.md）：%s\n' "$name"
  fi
done

# --- 运行产物未入库 -----------------------------------------------------------

tracked_bad="$(git -C "$REPO_ROOT" ls-files 2>/dev/null | grep -E '(^|/)(\.venv|\.cache|__pycache__)/|\.egg-info/' || true)"
if [ -n "$tracked_bad" ]; then
  while IFS= read -r line; do
    err "运行产物已入库：$line"
  done <<< "$tracked_bad"
else
  ok "无运行产物入库（.venv/.cache/__pycache__/*.egg-info）"
fi

# --- 汇总 ----------------------------------------------------------------------

printf '\nlint: %d ok, %d warn, %d error\n' "$oks" "$warns" "$errors"
[ "$errors" -eq 0 ] || exit 1
exit 0
