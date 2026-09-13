#!/usr/bin/env bash
# lib.sh — 仓库级 skills 维护脚本的公共函数库。
# 被 scripts/ 下的 skills-lint.sh / skills-doctor.sh / skills-link.sh /
# skills-unlink.sh / skills-new.sh source，自身不可直接执行。
# 依赖：bash + coreutils（awk / sed / stat；cygpath 与 cmd 仅 Windows 分支使用）。

[ "${BASH_SOURCE[0]}" != "$0" ] || { echo "lib.sh: meant to be sourced, not executed" >&2; exit 2; }

# 仓库根：从本库自身位置（scripts/..）解析，不依赖调用方工作目录。
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 维护者本地台账（不入库）；公开 skill 目录表在 README.md。格式标准见
# docs/开发与维护规范.md §5；本地台账存在时 lint 才校验。
LEDGER="$REPO_ROOT/SKILLS.local.md"
README_FILE="$REPO_ROOT/README.md"
# Skills 目录：全部 skill 位于 skills/ 下，一个 skill 一个子目录（规范 §2）。
SKILLS_DIR="$REPO_ROOT/skills"

# skill_dir <name> — skill 目录绝对路径的唯一定义点。
skill_dir() {
  printf '%s\n' "$SKILLS_DIR/$1"
}

is_windows() {
  case "${OSTYPE:-}" in
    msys|cygwin) return 0 ;;
    *) command -v uname >/dev/null 2>&1 && uname -s | grep -qi mingw && return 0 ;;
  esac
  return 1
}

# --- 分发目标（agent skills 目录）清单 ---------------------------------------
# 目标 = 内置主流清单 ⊕ agents.local.conf 本地自定义（可选，不入库，见下）；
# 目录存在才生效（消费方按存在性跳过）。

# 本地自定义清单：仓库根 agents.local.conf，每行一条，# 为注释：
#   <name> <路径>   新增/覆盖同名内置目标（路径以 ~ 或 / 开头，可含空格）
#   !<name>         禁用同名内置目标
AGENT_CONF="$REPO_ROOT/agents.local.conf"

# 内置清单：name<TAB>全局 skills 目录，每 agent 一行。
# 入表标准：官方支持 Agent Skills（agentskills.io 格式）且全局目录固定；
# 只读 ~/.agents/skills 的 agent（Codex 新版/Zed/Goose/Amp/Crush 等）由
# agents 行覆盖，不单列原生位。清单依据与说明见 docs/开发与维护规范.md §6；
# 与 skills/ddgs-web-access/scripts/install.sh 的默认清单保持一致。
builtin_agent_targets() {
  printf '%s\t%s\n' \
    zcode     "$HOME/.zcode/skills" \
    agents    "$HOME/.agents/skills" \
    claude    "$HOME/.claude/skills" \
    cursor    "$HOME/.cursor/skills" \
    codex     "$HOME/.codex/skills" \
    copilot   "$HOME/.copilot/skills" \
    gemini    "$HOME/.gemini/skills" \
    opencode  "$HOME/.config/opencode/skills" \
    windsurf  "$HOME/.codeium/windsurf/skills" \
    cline     "$HOME/.cline/skills" \
    roo       "$HOME/.roo/skills" \
    qwen      "$HOME/.qwen/skills" \
    kilo      "$HOME/.kilo/skills" \
    junie     "$HOME/.junie/skills" \
    trae      "$HOME/.trae/skills"
}

# agent_targets — 解析后的完整目标清单，输出 name<TAB>path 每行一条。
# agents.local.conf 有语法错误时 stderr 报文件与行号并返回 2（fail-fast）；
# 禁用未知名仅 warn。同路径去重保留首个。
agent_targets() {
  builtin_agent_targets | awk -F'\t' -v conf="$AGENT_CONF" -v home="$HOME" '
    BEGIN { ni = 0 }
    { n[ni] = $1; p[ni] = $2; ix[$1] = ni; ni++ }
    END {
      err = 0
      if (conf != "") {
        ln = 0
        while ((getline line < conf) > 0) {
          ln++
          sub(/\r$/, "", line)
          sub(/^[[:space:]]+/, "", line)
          if (line ~ /^#/ || line == "") continue
          if (line ~ /^!/) {
            name = substr(line, 2)
            gsub(/[[:space:]]/, "", name)
            if (name in ix) off[name] = 1
            else printf "warn: %s:%d 禁用了未知目标 %s\n", conf, ln, name > "/dev/stderr"
            continue
          }
          nf = split(line, f, /[[:space:]]+/)
          path = f[2]; for (j = 3; j <= nf; j++) path = path " " f[j]
          if (nf < 2 || f[1] !~ /^[a-z0-9][a-z0-9-]*$/ || path !~ /^[~\/]/) {
            printf "ERROR: %s:%d 无法解析：%s\n", conf, ln, line > "/dev/stderr"
            err = 1
            continue
          }
          if (substr(path, 1, 2) == "~/") path = home substr(path, 2)
          if (f[1] in ix) { p[ix[f[1]]] = path; off[f[1]] = 0 }
          else { n[ni] = f[1]; p[ni] = path; ix[f[1]] = ni; ni++ }
        }
        close(conf)
      }
      if (err) exit 2
      for (i = 0; i < ni; i++) {
        if (off[n[i]]) continue
        if (dup[p[i]]++) continue
        print n[i] "\t" p[i]
      }
    }'
}

# resolve_agent_targets <过滤器...> — 无过滤器时输出全部目标（name<TAB>path）；
# 过滤器为目标名（只保留该目标）或 name=path（临时目标，覆盖同名，路径可为
# 任意绝对目录——含链接进其他项目 .agents/skills 的一次性场景）。同名重复
# 出现以首个为准；未知名 stderr 报错并列出可用名称，返回 2。
resolve_agent_targets() {
  local all line name path out=""
  all="$(agent_targets)" || return $?
  if [ $# -eq 0 ]; then printf '%s\n' "$all"; return 0; fi
  for line in "$@"; do
    case "$line" in
      *=*)
        name="${line%%=*}"; path="${line#*=}"
        if ! printf '%s' "$name" | grep -Eq '^[a-z0-9][a-z0-9-]*$' || [ -z "$path" ]; then
          echo "ERROR: 无法解析的分发目标：$line（应为 name 或 name=path）" >&2
          return 2
        fi
        out+="$name"$'\t'"$path"$'\n'
        ;;
      *)
        if ! printf '%s\n' "$all" | awk -F'\t' -v t="$line" '$1 == t { found = 1; exit } END { exit(found ? 0 : 1) }'; then
          echo "ERROR: 未知分发目标：$line（可用：$(printf '%s\n' "$all" | cut -f1 | paste -sd' ' -)）" >&2
          return 2
        fi
        out+="$(printf '%s\n' "$all" | awk -F'\t' -v t="$line" '$1 == t { print; exit }')"$'\n'
        ;;
    esac
  done
  printf '%s' "$out" | awk -F'\t' '!seen[$1]++'
}

# skill 的定义：skills/ 下含 SKILL.md 的子目录。
list_skills() {
  local d
  for d in "$SKILLS_DIR"/*/; do
    [ -f "${d}SKILL.md" ] || continue
    basename "$d"
  done
}

# --- SKILL.md frontmatter 提取（受控格式的轻量解析，非通用 YAML） -----------

# fm_exists <skill> — SKILL.md 存在合法 frontmatter 块（首行 --- 起，有闭合 ---）。
fm_exists() {
  local f="$SKILLS_DIR/$1/SKILL.md"
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
  ' "$SKILLS_DIR/$1/SKILL.md"
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
  ' "$SKILLS_DIR/$1/SKILL.md"
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
  ' "$SKILLS_DIR/$1/SKILL.md"
}

# --- 链接管理（junction / symlink 统一抽象） ---------------------------------

# create_link <skills_dir> <skill> — 建链接：Windows 用 junction（免管理员），
# Unix 用 symlink。失败返回非零。
create_link() {
  local target="$1/$2"
  if is_windows; then
    # /c 用单斜杠：MSYS2_ARG_CONV_EXCL="*" 下双斜杠会原样传入 "//c"，
    # 使 cmd 掉进交互模式（ddgs-web-access 设计文档 v0.5 勘误）。
    MSYS2_ARG_CONV_EXCL="*" cmd /c mklink /J "$(cygpath -w "$target")" "$(cygpath -w "$SKILLS_DIR/$2")" >/dev/null
  else
    ln -s "$SKILLS_DIR/$2" "$target"
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
  src_id="$(stat -Lc '%d:%i' "$SKILLS_DIR/$2" 2>/dev/null)" || { echo broken; return 0; }
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
  [ "$real" = "$SKILLS_DIR/$2" ]
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
