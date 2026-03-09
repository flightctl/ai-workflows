#!/usr/bin/env bash
# Uninstall ai-workflows (remove symlinks and references).
# Automatically discovers all installed workflow directories.
#
# Usage:
#   ./uninstall.sh                            # remove user-level everything
#   ./uninstall.sh all                        # same
#   ./uninstall.sh cursor                     # user-level Cursor only
#   ./uninstall.sh claude                     # user-level Claude only
#   ./uninstall.sh cursor --project [path]    # project-level Cursor only
#   ./uninstall.sh claude --project [path]    # project-level Claude only
#   ./uninstall.sh all --project [path]       # project-level everything

set -e

INSTALL_DIR="${HOME}/.ai-workflows"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- parse arguments ---
TARGET="${1:-all}"
SCOPE="user"
PROJECT_ROOT=""

shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      SCOPE="project"
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        PROJECT_ROOT="$2"
        shift
      fi
      ;;
  esac
  shift
done

if [[ "$SCOPE" == "project" && -z "$PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(pwd)"
fi

# --- discover workflows ---
WORKFLOWS=()
for skill in "$REPO_DIR"/*/SKILL.md; do
  [[ -f "$skill" ]] || continue
  WORKFLOWS+=("$(basename "$(dirname "$skill")")")
done

# --- helpers ---

uninstall_cursor() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.cursor/skills"
  else
    SKILLS_DIR="${HOME}/.cursor/skills"
  fi

  for wf in "${WORKFLOWS[@]}"; do
    LINK="${SKILLS_DIR}/${wf}"
    if [[ -L "$LINK" ]]; then
      rm -f "$LINK"
      echo "  Removed $LINK"
    elif [[ -e "$LINK" ]]; then
      echo "  Warning: $LINK exists but is not a symlink; skipping" >&2
    fi
  done
}

uninstall_claude() {
  if [[ "$SCOPE" == "project" ]]; then
    CLAUDE_MD="${PROJECT_ROOT}/.claude/CLAUDE.md"
  else
    CLAUDE_MD="${HOME}/.claude/CLAUDE.md"
  fi

  MARKER="# ai-workflows"
  if [[ -f "$CLAUDE_MD" ]] && grep -qF "$MARKER" "$CLAUDE_MD"; then
    # Remove the marker line and all workflow reference lines that follow it
    sed -i "/$MARKER/,/^$/d" "$CLAUDE_MD"
    sed -i -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$CLAUDE_MD"
    echo "  Removed ai-workflows references from $CLAUDE_MD"
  fi
}

uninstall_link() {
  if [[ -L "$INSTALL_DIR" ]]; then
    rm -f "$INSTALL_DIR"
    echo "  Removed symlink $INSTALL_DIR"
  fi
}

# --- main ---

echo "Uninstalling ai-workflows ($TARGET, $SCOPE)..."

case "$TARGET" in
  all)
    uninstall_cursor
    uninstall_claude
    if [[ "$SCOPE" == "user" ]]; then
      uninstall_link
    fi
    ;;
  cursor)
    uninstall_cursor
    ;;
  claude)
    uninstall_claude
    ;;
  *)
    echo "Usage: $0 <all|cursor|claude> [--project [path]]" >&2
    exit 1
    ;;
esac

echo "Done."
