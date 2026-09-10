#!/usr/bin/env bash
# lib.sh — 仓库级 skills 维护脚本的公共函数库。
# 被 scripts/ 下的 skills-lint.sh / skills-doctor.sh / skills-link.sh /
# skills-unlink.sh / skills-new.sh source，自身不可直接执行。
# 依赖：bash + coreutils（awk / sed / stat；cygpath 与 cmd 仅 Windows 分支使用）。

[ "${BASH_SOURCE[0]}" != "$0" ] || { echo "lib.sh: meant to be sourced, not executed" >&2; exit 2; }

# 仓库根：从本库自身位置（scripts/..）解析，不依赖调用方工作目录。
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Skills 台账；格式标准见 docs/开发与维护规范.md §5。
LEDGER="$REPO_ROOT/SKILLS.md"

is_windows() {
  case "${OSTYPE:-}" in
    msys|cygwin) return 0 ;;
    *) command -v uname >/dev/null 2>&1 && uname -s | grep -qi mingw && return 0 ;;
  esac
  return 1
}

# 接收链接的 agent skills 目录清单（与 ddgs-web-access/scripts/install.sh 保持一致）。
agent_skills_dirs() {
  printf '%s\n' \
    "$HOME/.zcode/skills" \
    "$HOME/.agents/skills" \
    "$HOME/.claude/skills" \
    "$HOME/.cursor/skills"
}

# skill 的定义：含 SKILL.md 的一级子目录（glob 自动跳过 .git/.zcode 等隐藏目录；
# docs/、scripts/ 无 SKILL.md，天然排除）。
list_skills() {
  local d
  for d in "$REPO_ROOT"/*/; do
    [ -f "${d}SKILL.md" ] || continue
    basename "$d"
  done
}

# --- SKILL.md frontmatter 提取（受控格式的轻量解析，非通用 YAML） -----------

# fm_exists <skill> — SKILL.md 存在合法 frontmatter 块（首行 --- 起，有闭合 ---）。
fm_exists() {
  local f="$REPO_ROOT/$1/SKILL.md"
  [ -f "$f" ] || return 1
  head -n 1 "$f" | grep -q '^---[[:space:]]*$' || return 1
  awk 'NR > 1 && /^---[[:space:]]*$/ { ok = 1; exit } END { exit(ok ? 0 : 1) }' "$f"
}

# fm_value <skill> <key> — 顶层标量值（如 name）。
fm_value() {
  awk -v key="$2" '
    NR == 1 { if ($0 !~ /^---[[:space:]]*$/) exit; fm = 1; next }
    fm && /^---[[:space:]]*$/ { exit }
    fm && index($0, key ":") == 1 {
      v = substr($0, length(key) + 2)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
      gsub(/^"|"$/, "", v)
      print v
      exit
    }
  ' "$REPO_ROOT/$1/SKILL.md"
}

# fm_subvalue <skill> <parent> <key> — 二级标量值，如 fm_subvalue <skill> metadata version。
# 按本仓库受控缩进（父键顶格、子键两个空格）解析。
fm_subvalue() {
  awk -v parent="$2" -v key="$3" '
    NR == 1 { if ($0 !~ /^---[[:space:]]*$/) exit; fm = 1; next }
    fm && /^---[[:space:]]*$/ { exit }
    fm && $0 == parent ":" { inp = 1; next }
    fm && /^[A-Za-z0-9_-]+:/ { inp = 0 }
    inp && $0 ~ "^  " key ":" {
      v = $0
      sub("^  " key ":[[:space:]]*", "", v)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
      gsub(/^"|"$/, "", v)
      print v
      exit
    }
  ' "$REPO_ROOT/$1/SKILL.md"
}

# fm_description_chars <skill> — description 内容的字符数（行内值或折叠块累加），
# 供 lint 判断是否过短。
fm_description_chars() {
  awk '
    NR == 1 { if ($0 !~ /^---[[:space:]]*$/) exit; fm = 1; next }
    fm && /^---[[:space:]]*$/ { exit }
    fm && index($0, "description:") == 1 {
      ind = 1
      line = $0; sub(/^description:[[:space:]]*/, "", line)
      n += length(line)
      next
    }
    fm && /^[A-Za-z0-9_-]+:/ { if (ind) exit }
    ind { n += length($0) }
    END { print n + 0 }
  ' "$REPO_ROOT/$1/SKILL.md"
}

# --- 链接管理（junction / symlink 统一抽象） ---------------------------------

# create_link <skills_dir> <skill> — 建链接：Windows 用 junction（免管理员），
# Unix 用 symlink。失败返回非零。
create_link() {
  local target="$1/$2"
  if is_windows; then
    # /c 用单斜杠：MSYS2_ARG_CONV_EXCL="*" 下双斜杠会原样传入 "//c"，
    # 使 cmd 掉进交互模式（ddgs-web-access 设计文档 v0.5 勘误）。
    MSYS2_ARG_CONV_EXCL="*" cmd /c mklink /J "$(cygpath -w "$target")" "$(cygpath -w "$REPO_ROOT/$2")" >/dev/null
  else
    ln -s "$REPO_ROOT/$2" "$target"
  fi
}

# remove_link <skills_dir> <skill> — 只删链接本身，不递归删内容
# （Windows junction 用 rmdir，恰好只删重解析点）。
remove_link() {
  local target="$1/$2"
  if is_windows; then
    MSYS2_ARG_CONV_EXCL="*" cmd /c rmdir "$(cygpath -w "$target")" >/dev/null
  else
    rm "$target"
  fi
}

# link_state <skills_dir> <skill> — 输出四种状态之一：
#   linked   指向本仓库对应 skill 目录（按文件身份判定，junction/symlink 通用）
#   foreign  可读但为真实拷贝或指向别处
#   broken   条目存在但经它读不到 SKILL.md（含悬空链接）
#   missing  无条目
link_state() {
  local target="$1/$2" tgt_id src_id
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then echo missing; return 0; fi
  if [ ! -f "$target/SKILL.md" ]; then echo broken; return 0; fi
  tgt_id="$(stat -Lc '%d:%i' "$target" 2>/dev/null)" || { echo broken; return 0; }
  src_id="$(stat -Lc '%d:%i' "$REPO_ROOT/$2" 2>/dev/null)" || { echo broken; return 0; }
  if [ "$tgt_id" = "$src_id" ]; then echo linked; else echo foreign; fi
}

# link_points_to_repo <skills_dir> <skill> — 条目是链接且记录的指向是本仓库
# 对应 skill 目录（即使已悬空也算），供 unlink 安全删除判定。
link_points_to_repo() {
  local target="$1/$2" real
  [ -L "$target" ] || return 1
  real="$(readlink "$target")" || return 1
  if command -v cygpath >/dev/null 2>&1; then
    real="$(cygpath -u "$real" 2>/dev/null || printf '%s' "$real")"
  fi
  [ -d "$real" ] && real="$(cd "$real" && pwd)"
  [ "$real" = "$REPO_ROOT/$2" ]
}

# resolve_skills <args...> — 把命令行参数解析为 skill 名清单输出：
# --all = 全部 skill；否则逐名校验。用法错误时 stderr 报错并返回 2。
resolve_skills() {
  if [ "${1:-}" = "--all" ]; then
    [ $# -eq 1 ] || { echo "ERROR: --all 不能与具体 skill 名混用" >&2; return 2; }
    list_skills
    return 0
  fi
  local known name
  known="$(list_skills | tr '\n' ' ')"
  for name in "$@"; do
    case " $known " in
      *" $name "*) printf '%s\n' "$name" ;;
      *) echo "ERROR: 不是本仓库的 skill：$name" >&2; return 2 ;;
    esac
  done
}
