#!/usr/bin/env bash
# Remove the ddgs-web-access links created by scripts/install.sh.
# Safety: only removes links/junctions that point back to THIS repository;
# real copies or links to other locations are left untouched.
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

unlink_skill() {
  local target="$1/$SKILL_NAME"
  if [ ! -L "$target" ] && [ ! -e "$target" ]; then
    return 0
  fi
  local real=""
  if [ -L "$target" ]; then
    real="$(readlink "$target")"
    real="$(command -v cygpath >/dev/null 2>&1 && cygpath -u "$real" || echo "$real")"
    if [ -d "$real" ]; then
      real="$(cd "$real" && pwd)"
    fi
  fi
  if [ "$real" != "$REPO_DIR" ]; then
    echo "skip (not pointing to this repo): $target"
    return 0
  fi
  if is_windows; then
    MSYS2_ARG_CONV_EXCL="*" cmd /c rmdir "$(cygpath -w "$target")"
  else
    rm "$target"
  fi
  echo "removed: $target"
}

for d in "$HOME/.zcode/skills" "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.cursor/skills"; do
  if [ -d "$d" ]; then
    unlink_skill "$d"
  fi
done

echo "done."
