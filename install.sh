#!/usr/bin/env bash
# Install ai-workflows via symlinks.
# Automatically discovers all workflow directories (any dir with a SKILL.md).
#
# Scope:
#   User-level (default) — available in all your projects
#   Project-level         — committed / shared with a specific repo
#
# Usage:
#   ./install.sh cursor                       # user-level Cursor skills
#   ./install.sh cursor --project [path]      # project-level Cursor skills
#   ./install.sh claude                       # user-level Claude Code reference
#   ./install.sh claude --project [path]      # project-level Claude Code reference
#   ./install.sh all                          # user-level Cursor + Claude
#   ./install.sh all --project [path]         # project-level Cursor + Claude

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.ai-workflows"

# --- parse arguments ---
TARGET="${1:-cursor}"
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

if [[ ${#WORKFLOWS[@]} -eq 0 ]]; then
  echo "Error: no workflows found (directories with SKILL.md)" >&2
  exit 1
fi

# --- helpers ---

ensure_repo_linked() {
  if [[ "$(readlink -f "$REPO_DIR")" == "$(readlink -f "$INSTALL_DIR" 2>/dev/null)" ]]; then
    return
  fi

  if [[ -e "$INSTALL_DIR" ]]; then
    echo "Warning: $INSTALL_DIR already exists and points elsewhere." >&2
    echo "  Current target: $(readlink -f "$INSTALL_DIR" 2>/dev/null || echo "$INSTALL_DIR")" >&2
    echo "  This repo:      $REPO_DIR" >&2
    echo "  Remove it first: rm -rf $INSTALL_DIR" >&2
    exit 1
  fi

  ln -sfn "$REPO_DIR" "$INSTALL_DIR"
  echo "  Linked $INSTALL_DIR -> $REPO_DIR"
}

install_cursor() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.cursor/skills"
  else
    SKILLS_DIR="${HOME}/.cursor/skills"
  fi

  mkdir -p "$SKILLS_DIR"
  for wf in "${WORKFLOWS[@]}"; do
    ln -sfn "${INSTALL_DIR}/${wf}" "${SKILLS_DIR}/${wf}"
    echo "  Linked ${SKILLS_DIR}/${wf} -> ${INSTALL_DIR}/${wf}  ($SCOPE)"
  done
}

install_claude() {
  if [[ "$SCOPE" == "project" ]]; then
    CLAUDE_DIR="${PROJECT_ROOT}/.claude"
  else
    CLAUDE_DIR="${HOME}/.claude"
  fi

  CLAUDE_MD="${CLAUDE_DIR}/CLAUDE.md"
  MARKER="# ai-workflows"

  mkdir -p "$CLAUDE_DIR"

  if [[ -f "$CLAUDE_MD" ]] && grep -qF "$MARKER" "$CLAUDE_MD"; then
    echo "  Reference already present in $CLAUDE_MD"
    return
  fi

  {
    printf '\n%s\n' "$MARKER"
    for wf in "${WORKFLOWS[@]}"; do
      printf 'For %s workflows, read and follow ~/.ai-workflows/%s/skills/controller.md\n' "$wf" "$wf"
    done
  } >> "$CLAUDE_MD"
  echo "  Added reference to $CLAUDE_MD  ($SCOPE)"
}

# --- main ---

echo "Installing ai-workflows ($TARGET, $SCOPE)..."
echo "  Workflows: ${WORKFLOWS[*]}"
ensure_repo_linked

case "$TARGET" in
  cursor)
    install_cursor
    ;;
  claude)
    install_claude
    ;;
  all)
    install_cursor
    install_claude
    ;;
  *)
    echo "Usage: $0 <cursor|claude|all> [--project [path]]" >&2
    echo "" >&2
    echo "Targets:" >&2
    echo "  cursor   Cursor skill symlinks" >&2
    echo "  claude   Claude Code instruction references" >&2
    echo "  all      Cursor + Claude" >&2
    echo "" >&2
    echo "Scopes:" >&2
    echo "  (default)           user-level  (~/.cursor/skills/, ~/.claude/)" >&2
    echo "  --project [path]    project-level (.cursor/skills/, .claude/)" >&2
    echo "                      path defaults to current directory" >&2
    exit 1
    ;;
esac

echo "Done. Run 'git pull' from $INSTALL_DIR to update."
