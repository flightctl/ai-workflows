#!/usr/bin/env bash
# Uninstall ai-workflows (remove symlinks and references).
# Automatically discovers all installed workflow directories.
#
# Usage:
#   ./uninstall.sh                                       # remove user-level everything
#   ./uninstall.sh all                                   # same
#   ./uninstall.sh cursor                                # user-level Cursor only
#   ./uninstall.sh cursor --workflows bugfix             # user-level Cursor, specific workflow
#   ./uninstall.sh claude                                # user-level Claude only
#   ./uninstall.sh gemini                                # user-level Gemini only
#   ./uninstall.sh cursor --project [path]               # project-level Cursor only
#   ./uninstall.sh claude --project [path]               # project-level Claude only
#   ./uninstall.sh gemini --project [path]               # project-level Gemini only
#   ./uninstall.sh all --project [path]                  # project-level everything
#   ./uninstall.sh --list                                # list available workflows

set -e

INSTALL_DIR="${HOME}/.ai-workflows"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
TARGET="${1:-all}"
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

SELECTIVE=$([[ ${#SELECTED_WORKFLOWS[@]} -gt 0 ]] && echo true || echo false)

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

  if [[ ! -f "$CLAUDE_MD" ]]; then
    return
  fi

  MARKER="# ai-workflows"

  for wf in "${WORKFLOWS[@]}"; do
    REMOVE_LINES=()
    if [[ "$SCOPE" == "project" ]]; then
      REMOVE_LINES+=("For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/SKILL.md")
      REMOVE_LINES+=("For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/skills/controller.md")
    else
      REMOVE_LINES+=("For ${wf} workflows, read and follow ~/.ai-workflows/${wf}/SKILL.md")
      REMOVE_LINES+=("For ${wf} workflows, read and follow ~/.ai-workflows/${wf}/skills/controller.md")
    fi
    for candidate in "${REMOVE_LINES[@]}"; do
      if grep -qF "$candidate" "$CLAUDE_MD"; then
        grep -vF "$candidate" "$CLAUDE_MD" > "${CLAUDE_MD}.tmp" && mv "${CLAUDE_MD}.tmp" "$CLAUDE_MD"
        echo "  Removed $wf reference from $CLAUDE_MD"
      fi
    done
  done

  # Remove the marker if no workflow references remain
  if grep -qF "$MARKER" "$CLAUDE_MD" && ! grep -q "^For .* workflows, read and follow" "$CLAUDE_MD"; then
    grep -vF "$MARKER" "$CLAUDE_MD" > "${CLAUDE_MD}.tmp" && mv "${CLAUDE_MD}.tmp" "$CLAUDE_MD"
    # strip trailing blank lines (portable -- no GNU sed -i)
    awk '{lines[NR]=$0} END{e=NR; while(e>0&&lines[e]=="") e--; for(i=1;i<=e;i++) print lines[i]}' \
      "$CLAUDE_MD" > "${CLAUDE_MD}.tmp" && mv "${CLAUDE_MD}.tmp" "$CLAUDE_MD"
    echo "  Removed ai-workflows marker from $CLAUDE_MD"
  fi
}

uninstall_gemini() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.gemini/skills"
  else
    SKILLS_DIR="${HOME}/.gemini/skills"
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
    uninstall_gemini
    if [[ "$SCOPE" == "user" && "$SELECTIVE" == false ]]; then
      uninstall_link
    fi
    ;;
  cursor)
    uninstall_cursor
    ;;
  claude)
    uninstall_claude
    ;;
  gemini)
    uninstall_gemini
    ;;
  *)
    echo "Usage: $0 <all|cursor|claude|gemini> [--workflows wf1,wf2] [--project [path]]" >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  --workflows wf1,wf2   uninstall only the listed workflows (comma-separated)" >&2
    echo "                         defaults to all workflows" >&2
    echo "  --project [path]      project-level (.cursor/skills/, .claude/, .gemini/skills/)" >&2
    echo "                         path defaults to current directory" >&2
    echo "  --list                list available workflows and exit" >&2
    exit 1
    ;;
esac

echo "Done."
