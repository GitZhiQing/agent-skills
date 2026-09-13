#!/usr/bin/env bash
# Install ddgs-web-access as a skill for every agent tool found on this machine.
#
# Creates a junction (Windows, no admin needed) or symlink (Unix) from each
# agent's skills directory to THIS repository, so:
#   - all agents share one source of truth (updates propagate to all),
#   - the fetch cache (.cache/ in the repo) is shared across agents/projects,
#   - SKILL.md and bin/ launchers stay location-independent.
#
# Idempotent: existing links are skipped. Remove with scripts/uninstall.sh.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_NAME="ddgs-web-access"

is_windows() {
  case "${OSTYPE:-}" in
    msys|cygwin) return 0 ;;
    *) command -v uname >/dev/null 2>&1 && uname -s | grep -qi mingw && return 0 ;;
  esac
  return 1
}

link_skill() {
  local skills_dir="$1"
  local target="$skills_dir/$SKILL_NAME"
  if [ ! -d "$skills_dir" ]; then
    echo "skip (agent skills dir not found): $skills_dir"
    return 0
  fi
  if [ -e "$target" ] || [ -L "$target" ]; then
    echo "skip (already exists): $target"
    return 0
  fi
  if is_windows; then
    # ARG_CONV_EXCL keeps /c and the Windows paths untouched, so use a
    # single slash here (a double slash would survive as "//c" and make
    # cmd drop into interactive mode).
    MSYS2_ARG_CONV_EXCL="*" cmd /c mklink /J "$(cygpath -w "$target")" "$(cygpath -w "$REPO_DIR")"
  else
    ln -s "$REPO_DIR" "$target"
  fi
  if [ ! -e "$target" ]; then
    echo "ERROR: link was not created: $target" >&2
    exit 1
  fi
  echo "linked: $target -> $REPO_DIR"
}

# Default agent skills directories: mainstream agents that adopted the Agent
# Skills format, probed by existence (keep in sync with scripts/lib.sh
# builtin_agent_targets; rationale and full table in the repo's
# docs/开发与维护规范.md §6).
default_skill_dirs() {
  printf '%s\n' \
    "$HOME/.zcode/skills" \
    "$HOME/.agents/skills" \
    "$HOME/.claude/skills" \
    "$HOME/.cursor/skills" \
    "$HOME/.codex/skills" \
    "$HOME/.copilot/skills" \
    "$HOME/.gemini/skills" \
    "$HOME/.config/opencode/skills" \
    "$HOME/.codeium/windsurf/skills" \
    "$HOME/.cline/skills" \
    "$HOME/.roo/skills" \
    "$HOME/.qwen/skills" \
    "$HOME/.kilo/skills" \
    "$HOME/.junie/skills" \
    "$HOME/.trae/skills"
}

# usage: install.sh [skills-dir ...] — no args = default list above; pass
# directories to link only into those (e.g. a project-level .agents/skills).
if [ $# -gt 0 ]; then
  for d in "$@"; do link_skill "$d"; done
else
  while IFS= read -r d; do link_skill "$d"; done < <(default_skill_dirs)
fi

echo
echo "done. 验证（任意目录下执行）:"
echo "  bash \"$REPO_DIR/bin/ddgs-web-search\" \"test\" -m 1"
echo "卸载: bash \"$REPO_DIR/scripts/uninstall.sh\""
