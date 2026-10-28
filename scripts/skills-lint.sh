#!/usr/bin/env bash
# skills-lint.sh — 仓库结构与元数据一致性校验。
#
# 检查项（标准见 docs/开发与维护规范.md）：
#   L-frontmatter  每个 skill 有 SKILL.md + 合法 frontmatter
#   L-spec         name 符合官方约束（字符集 / 长度 / 连字符）且与目录名一致
#   L-description  description 非空、<=1024 字符、不含 <>；过短（<30）warn
#   L-category     metadata.category 缺失时 warn
#   L-readme-file  每个 skill 目录含 README.md（面向人的导览，规范 §2）
#   L-version      metadata.version 必须存在且为 semver；与 pyproject.toml、
#                  .claude-plugin/plugin.json、marketplace.json、本地台账一致
#   L-plugin       每个 skill 有 plugin.json，且被 marketplace 收录、source 正确
#   L-readme       README Skills 目录表 <-> 磁盘双向一致（不校验版本列）
#   L-ledger       本机存在 SKILLS.local.md 时：总览 <-> 磁盘双向一致，
#                  总览每行有对应明细小节，明细无孤儿小节；无本地台账则跳过
#   L-size         SKILL.md 超过 500 行或 16KB 时 warn（规范 §2.1）
#   L-refs         SKILL.md 引用的 references/ 路径必须存在
#   L-docs         缺少 docs/测试集.md 时 warn
#   L-layout       skill 必须位于 skills/ 子目录（skills/<name>/SKILL.md）
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
name_re='^[a-z0-9]+(-[a-z0-9]+)*$'
MARKETPLACE="$REPO_ROOT/.claude-plugin/marketplace.json"

# --- 目录表解析（本地台账总览 / README Skills 表） ----------------------------

# catalog_rows <file> <section-regex>：目录表每行输出 "name<TAB>version"。
# 列位置固定 $2=Skill、$3=版本；用于本地台账总览。
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

# readme_names：README `## Skills` 公开目录表，只取 Skill 列（不展示版本号）。
readme_names() {
  awk -F'|' '
    /^## / { in_ov = ($0 ~ /^## Skills/) }
    in_ov && /^\|/ && NF >= 4 {
      s = $2
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      if (s ~ /^[-: ]+$/ || s == "Skill") next
      if (s ~ /^\[/) { sub(/^\[/, "", s); sub(/\].*$/, "", s) }
      else { sub(/\/$/, "", s) }
      print s
    }
  ' "$README_FILE"
}

# marketplace_rows：marketplace.json 每个 plugin 输出 "name<TAB>version<TAB>source"。
# 依赖当前 2 空格缩进的受控格式；author 内的 name 会被下一个 plugin 的 name 覆盖。
marketplace_rows() {
  [ -f "$MARKETPLACE" ] || return 0
  awk -F'"' '
    /^[[:space:]]*"name":[[:space:]]*"/ { name = $4 }
    /^[[:space:]]*"source":[[:space:]]*"/ { src = $4 }
    /^[[:space:]]*"version":[[:space:]]*"/ {
      if (name != "") print name "\t" $4 "\t" src
    }
  ' "$MARKETPLACE"
}

marketplace_row_for() {
  printf '%s\n' "$marketplace_list" | awk -F'\t' -v s="$1" '$1 == s { print; exit }'
}

# plugin_field <skill> <name|version>：读取 skill 的 plugin.json 顶层字段。
plugin_field() {
  local f="$SKILLS_DIR/$1/.claude-plugin/plugin.json" key="$2"
  [ -f "$f" ] || return 1
  awk -F'"' -v k="$key" '
    $0 ~ "^[[:space:]]*\"" k "\":[[:space:]]*\"" { print $4; exit }
  ' "$f"
}

# ledger_rows / ledger_details：维护者本地台账，存在时才校验。
ledger_rows() { catalog_rows "$LEDGER" '^## 总览'; }
ledger_details() {
  awk '/^## / { in_det = ($0 ~ /^## 明细/) }
       in_det && /^### / { s = $2; sub(/\/$/, "", s); print s }' "$LEDGER"
}

readme_name_list="$(readme_names)"
marketplace_list="$(marketplace_rows || true)"
marketplace_name_list="$(printf '%s\n' "$marketplace_list" | cut -f1 | sed '/^$/d')"

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
  name_ok=1
  if [ -z "$fm_name" ]; then
    err "$skill: frontmatter 缺少 name"
    name_ok=0
  elif [ "$fm_name" != "$skill" ]; then
    err "$skill: frontmatter name「$fm_name」与目录名不一致"
    name_ok=0
  fi
  if [ -n "$fm_name" ]; then
    if [ "${#fm_name}" -gt 64 ]; then
      err "$skill: name 超过 64 字符（官方规范）"
      name_ok=0
    fi
    if ! printf '%s' "$fm_name" | grep -Eq "$name_re"; then
      err "$skill: name「$fm_name」不符合官方字符集 / 连字符规则（$name_re）"
      name_ok=0
    fi
  fi
  if [ "$name_ok" -eq 1 ]; then
    ok "$skill: name 合法且与目录名一致"
  fi

  desc_text="$(fm_description_text "$skill")"
  desc_chars="$(fm_description_chars "$skill")"
  desc_ok=1
  if [ "$desc_chars" -eq 0 ]; then
    err "$skill: description 为空"
    desc_ok=0
  fi
  if [ "$desc_chars" -gt 0 ] && [ "$desc_chars" -lt 30 ]; then
    warn "$skill: description 仅 ${desc_chars} 字符，难以承载正向触发 + 反向不触发（规范 §3.1）"
  fi
  if [ "$desc_chars" -gt 1024 ]; then
    err "$skill: description ${desc_chars} 字符，超过官方上限 1024"
    desc_ok=0
  fi
  if printf '%s' "$desc_text" | grep -q '[<>]'; then
    err "$skill: description 含 < 或 >（官方规范禁止 XML 标签 / 尖括号）"
    desc_ok=0
  fi
  if [ "$desc_ok" -eq 1 ]; then
    ok "$skill: description 非空（${desc_chars} 字符）"
  fi

  catv="$(fm_subvalue "$skill" metadata category)"
  if [ -z "$catv" ]; then
    warn "$skill: 缺少 metadata.category（规范 §3，建议填写领域标签）"
  else
    ok "$skill: metadata.category $catv"
  fi

  if [ -f "$SKILLS_DIR/$skill/README.md" ]; then
    ok "$skill: README.md 存在"
  else
    err "$skill: 缺少 README.md（规范 §2：面向人的目录导览，全部 skill 必备）"
  fi

  ver="$(fm_subvalue "$skill" metadata version)"
  ver_ok=1
  if [ -z "$ver" ]; then
    err "$skill: frontmatter 缺少 metadata.version（规范 §3：全部 skill 必须标注）"
    ver_ok=0
  elif ! printf '%s' "$ver" | grep -Eq "$semver_re"; then
    err "$skill: metadata.version「$ver」不是 semver（X.Y.Z）"
    ver_ok=0
  fi
  if [ "$ver_ok" -eq 1 ]; then
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

  # 包内 __version__ 是 CLI --version 与经验记录的版本来源，必须同步。
  init_file="$SKILLS_DIR/$skill/src/${skill//-/_}/__init__.py"
  if [ -f "$init_file" ]; then
    init_ver="$(awk -F'"' '/^__version__[[:space:]]*=/ { print $2; exit }' "$init_file")"
    if [ -n "$ver" ] && [ -n "$init_ver" ] && [ "$ver" != "$init_ver" ]; then
      err "$skill: 版本不一致：SKILL.md $ver != __init__.py __version__ $init_ver"
    else
      ok "$skill: __init__.py 版本一致（$init_ver）"
    fi
  fi

  plugin_file="$SKILLS_DIR/$skill/.claude-plugin/plugin.json"
  if [ ! -f "$plugin_file" ]; then
    err "$skill: 缺少 .claude-plugin/plugin.json（规范 §2）"
  else
    p_name="$(plugin_field "$skill" name || true)"
    p_ver="$(plugin_field "$skill" version || true)"
    if [ "$p_name" != "$skill" ]; then
      err "$skill: plugin.json name「$p_name」与目录名不一致"
    else
      ok "$skill: plugin.json 存在且 name 一致"
    fi
    if [ -n "$ver" ] && [ "$p_ver" != "$ver" ]; then
      err "$skill: plugin.json 版本「$p_ver」与 frontmatter「$ver」不一致"
    fi
  fi

  m_row="$(marketplace_row_for "$skill")"
  if [ -z "$m_row" ]; then
    err "$skill: 未出现在 .claude-plugin/marketplace.json（规范 §2）"
  else
    m_ver="$(printf '%s' "$m_row" | cut -f2)"
    m_src="$(printf '%s' "$m_row" | cut -f3)"
    m_ok=1
    if [ "$m_src" != "./skills/$skill" ]; then
      err "$skill: marketplace source「$m_src」应为「./skills/$skill」"
      m_ok=0
    fi
    if [ -n "$ver" ] && [ "$m_ver" != "$ver" ]; then
      err "$skill: marketplace 版本「$m_ver」与 frontmatter「$ver」不一致"
      m_ok=0
    fi
    if [ "$m_ok" -eq 1 ]; then
      ok "$skill: marketplace 条目与版本一致"
    fi
  fi

  sk_lines="$(wc -l < "$SKILLS_DIR/$skill/SKILL.md" | tr -d ' ')"
  sk_bytes="$(wc -c < "$SKILLS_DIR/$skill/SKILL.md" | tr -d ' ')"
  if [ "$sk_lines" -gt 500 ] || [ "$sk_bytes" -gt 16384 ]; then
    warn "$skill: SKILL.md ${sk_lines} 行 / ${sk_bytes} 字节，超过 500 行 / 16KB 预算，建议拆分到 references/（规范 §2.1）"
  else
    ok "$skill: SKILL.md 体积 ${sk_lines} 行 / ${sk_bytes} 字节"
  fi

  refs="$(grep -oE "references/[^ \`\"'()<>，。；：、）]+" "$SKILLS_DIR/$skill/SKILL.md" | sort -u || true)"
  if [ -n "$refs" ]; then
    refs_ok=1
    while IFS= read -r ref; do
      [ -n "$ref" ] || continue
      if [ ! -e "$SKILLS_DIR/$skill/$ref" ]; then
        err "$skill: SKILL.md 引用的 $ref 不存在"
        refs_ok=0
      fi
    done <<< "$refs"
    if [ "$refs_ok" -eq 1 ]; then
      ok "$skill: references 链接可达"
    fi
  fi

  if [ -f "$SKILLS_DIR/$skill/docs/测试集.md" ]; then
    ok "$skill: docs/测试集.md 存在"
  else
    warn "$skill: 缺少 docs/测试集.md（规范 §2）"
  fi

  if printf '%s\n' "$readme_name_list" | grep -qx "$skill"; then
    ok "$skill: README Skills 目录表包含该 skill"
  else
    err "$skill: README Skills 目录表缺少该 skill 的行"
  fi
done

# --- README 目录表 <-> 磁盘，双向一致 ----------------------------------------

for name in $readme_name_list; do
  if ! printf '%s\n' "$skills_list" | grep -qx "$name"; then
    err "README 目录表的「$name」在磁盘上不存在（目录缺失或无 SKILL.md）"
  fi
done

# --- marketplace <-> 磁盘，双向一致 ------------------------------------------

for name in $marketplace_name_list; do
  if ! printf '%s\n' "$skills_list" | grep -qx "$name"; then
    err "marketplace.json 的「$name」在磁盘上不存在（目录缺失或无 SKILL.md）"
  fi
done
m_dups="$(printf '%s\n' "$marketplace_name_list" | sort | uniq -d)"
if [ -n "$m_dups" ]; then
  while IFS= read -r name; do
    err "marketplace.json 条目重复：$name"
  done <<< "$m_dups"
fi

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
  if [ "$name" = template ]; then
    :  # template/SKILL.md 是骨架，不是 skill
  elif [ -f "${d}SKILL.md" ]; then
    err "skill「$name」不在 skills/ 下（规范 §2）"
  elif [ "$name" = docs ] || [ "$name" = scripts ] || [ "$name" = skills ] || [ "$name" = spec ]; then
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

# --- 汇总 ---------------------------------------------------------------------

printf '\nlint: %d ok, %d warn, %d error\n' "$oks" "$warns" "$errors"
[ "$errors" -eq 0 ] || exit 1
exit 0
