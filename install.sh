#!/usr/bin/env bash
# Install ai-workflows via symlinks.
# Automatically discovers all workflow directories (any dir with a SKILL.md).
#
# Scope:
#   User-level (default) — available in all your projects
#   Project-level         — committed / shared with a specific repo
#
# Usage:
#   ./install.sh cursor                                  # user-level, all workflows
#   ./install.sh cursor --workflows bugfix               # user-level, specific workflow
#   ./install.sh cursor --workflows bugfix,docs-writer   # user-level, multiple workflows
#   ./install.sh cursor --project [path]                 # project-level, all workflows
#   ./install.sh claude                                  # user-level Claude Code reference
#   ./install.sh claude --project [path]                 # project-level Claude Code reference
#   ./install.sh gemini                                  # user-level Gemini CLI skill symlinks
#   ./install.sh gemini --project [path]                 # project-level Gemini CLI skill symlinks
#   ./install.sh all                                     # user-level Cursor + Claude + Gemini
#   ./install.sh all --project [path]                    # project-level Cursor + Claude + Gemini
#   ./install.sh --list                                  # list available workflows

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.ai-workflows"

# --- discover all available workflows ---
ALL_WORKFLOWS=()
for skill in "$REPO_DIR"/*/SKILL.md; do
  [[ -f "$skill" ]] || continue
  ALL_WORKFLOWS+=("$(basename "$(dirname "$skill")")")
done

# --- handle --list early ---
for arg in "$@"; do
  if [[ "$arg" == "--list" ]]; then
    echo "Available workflows:"
    for wf in "${ALL_WORKFLOWS[@]}"; do
      echo "  $wf"
    done
    exit 0
  fi
done

# --- parse arguments ---
TARGET="${1:-cursor}"
SCOPE="user"
PROJECT_ROOT=""
SELECTED_WORKFLOWS=()

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
    --workflows)
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        IFS=',' read -ra _wfs <<< "$2"
        SELECTED_WORKFLOWS+=("${_wfs[@]}")
        shift
      else
        echo "Error: --workflows requires a comma-separated list of workflow names" >&2
        exit 1
      fi
      ;;
  esac
  shift
done

if [[ "$SCOPE" == "project" && -z "$PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(pwd)"
fi

# --- resolve final workflow list ---
if [[ ${#SELECTED_WORKFLOWS[@]} -gt 0 ]]; then
  WORKFLOWS=()
  for sel in "${SELECTED_WORKFLOWS[@]}"; do
    found=false
    for avail in "${ALL_WORKFLOWS[@]}"; do
      if [[ "$sel" == "$avail" ]]; then
        found=true
        break
      fi
    done
    if [[ "$found" == false ]]; then
      echo "Error: unknown workflow '$sel'" >&2
      echo "Available workflows: ${ALL_WORKFLOWS[*]}" >&2
      exit 1
    fi
    WORKFLOWS+=("$sel")
  done
else
  WORKFLOWS=("${ALL_WORKFLOWS[@]}")
fi

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

  if ! [[ -f "$CLAUDE_MD" ]] || ! grep -qF "$MARKER" "$CLAUDE_MD"; then
    printf '\n%s\n' "$MARKER" >> "$CLAUDE_MD"
  fi

  for wf in "${WORKFLOWS[@]}"; do
    LINE="For ${wf} workflows, read and follow ~/.ai-workflows/${wf}/skills/controller.md"
    if grep -qF "$LINE" "$CLAUDE_MD"; then
      echo "  Reference for $wf already present in $CLAUDE_MD"
    else
      printf '%s\n' "$LINE" >> "$CLAUDE_MD"
      echo "  Added $wf reference to $CLAUDE_MD  ($SCOPE)"
    fi
  done
}

install_gemini() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.gemini/skills"
  else
    SKILLS_DIR="${HOME}/.gemini/skills"
  fi

  mkdir -p "$SKILLS_DIR"
  for wf in "${WORKFLOWS[@]}"; do
    ln -sfn "${INSTALL_DIR}/${wf}" "${SKILLS_DIR}/${wf}"
    echo "  Linked ${SKILLS_DIR}/${wf} -> ${INSTALL_DIR}/${wf}  ($SCOPE)"
  done
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
  gemini)
    install_gemini
    ;;
  all)
    install_cursor
    install_claude
    install_gemini
    ;;
  *)
    echo "Usage: $0 <cursor|claude|gemini|all> [--workflows wf1,wf2] [--project [path]]" >&2
    echo "" >&2
    echo "Targets:" >&2
    echo "  cursor   Cursor skill symlinks" >&2
    echo "  claude   Claude Code instruction references" >&2
    echo "  gemini   Gemini CLI skill symlinks" >&2
    echo "  all      Cursor + Claude + Gemini" >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  --workflows wf1,wf2   install only the listed workflows (comma-separated)" >&2
    echo "                         defaults to all available workflows" >&2
    echo "  --project [path]      project-level (.cursor/skills/, .claude/, .gemini/skills/)" >&2
    echo "                         path defaults to current directory" >&2
    echo "  --list                list available workflows and exit" >&2
    exit 1
    ;;
esac

echo "Done. Run 'git pull' from $INSTALL_DIR to update."