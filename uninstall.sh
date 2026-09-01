#!/usr/bin/env bash
# Uninstall ai-workflows (remove symlinks and references).
# Automatically discovers all installed package directories.
#
# Usage:
#   ./uninstall.sh                                       # remove user-level everything
#   ./uninstall.sh all                                   # same
#   ./uninstall.sh cursor                                # user-level Cursor only
#   ./uninstall.sh cursor --packages bugfix              # user-level Cursor, specific package
#   ./uninstall.sh claude                                # user-level Claude only
#   ./uninstall.sh gemini                                # user-level Gemini only
#   ./uninstall.sh codex                                 # user-level Codex only
#   ./uninstall.sh cursor --project [path]               # project-level Cursor only
#   ./uninstall.sh claude --project [path]               # project-level Claude only
#   ./uninstall.sh gemini --project [path]               # project-level Gemini only
#   ./uninstall.sh codex --project [path]                # project-level Codex only
#   ./uninstall.sh all --project [path]                  # project-level everything
#   ./uninstall.sh --list                                # list available packages

set -e

INSTALL_DIR="${HOME}/.ai-workflows"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- discover all available packages ---
ALL_PACKAGES=()
ALL_PACKAGE_PATHS=()
for skill in "$REPO_DIR"/*/SKILL.md "$REPO_DIR"/skills/*/SKILL.md; do
  [[ -f "$skill" ]] || continue
  package_name="$(basename "$(dirname "$skill")")"
  package_path="$(dirname "${skill#"$REPO_DIR"/}")"
  for existing_name in "${ALL_PACKAGES[@]}"; do
    if [[ "$existing_name" == "$package_name" ]]; then
      echo "Error: duplicate workflow/skill name '$package_name'" >&2
      echo "Package names must be unique across top-level workflows and skills/." >&2
      exit 1
    fi
  done
  ALL_PACKAGES+=("$package_name")
  ALL_PACKAGE_PATHS+=("$package_path")
done

package_dir() {
  local name="$1"
  local index
  for index in "${!ALL_PACKAGES[@]}"; do
    if [[ "${ALL_PACKAGES[$index]}" == "$name" ]]; then
      printf '%s' "${INSTALL_DIR}/${ALL_PACKAGE_PATHS[$index]}"
      return 0
    fi
  done
  return 1
}

# --- handle --list early ---
for arg in "$@"; do
  if [[ "$arg" == "--list" ]]; then
    echo "Available packages:"
    for wf in "${ALL_PACKAGES[@]}"; do
      echo "  $wf"
    done
    exit 0
  fi
done

# --- parse arguments ---
TARGET="${1:-all}"
SCOPE="user"
PROJECT_ROOT=""
SELECTED_PACKAGES=()

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
    --packages|--workflows)
      selector_flag="$1"
      if [[ "$selector_flag" == "--workflows" ]]; then
        echo "Warning: --workflows is deprecated; use --packages." >&2
      fi
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        IFS=',' read -ra _packages <<< "$2"
        SELECTED_PACKAGES+=("${_packages[@]}")
        shift
      else
        echo "Error: ${selector_flag} requires a comma-separated list of package names" >&2
        exit 1
      fi
      ;;
  esac
  shift
done

if [[ "$SCOPE" == "project" && -z "$PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(pwd)"
fi

# --- resolve final package list ---
if [[ ${#SELECTED_PACKAGES[@]} -gt 0 ]]; then
  PACKAGES=()
  for sel in "${SELECTED_PACKAGES[@]}"; do
    found=false
    for avail in "${ALL_PACKAGES[@]}"; do
      if [[ "$sel" == "$avail" ]]; then
        found=true
        break
      fi
    done
    if [[ "$found" == false ]]; then
      echo "Error: unknown package '$sel'" >&2
      echo "Available packages: ${ALL_PACKAGES[*]}" >&2
      exit 1
    fi
    PACKAGES+=("$sel")
  done
else
  PACKAGES=("${ALL_PACKAGES[@]}")
fi

SELECTIVE=$([[ ${#SELECTED_PACKAGES[@]} -gt 0 ]] && echo true || echo false)

# --- helpers ---

uninstall_shared() {
  local target_dir="$1"
  local link="${target_dir}/_shared"
  if [[ -L "$link" ]]; then
    rm -f "$link"
    echo "  Removed $link"
  fi
}

has_remaining_packages() {
  local target_dir="$1"
  [[ -d "$target_dir" ]] || return 1
  for item in "$target_dir"/*/; do
    [[ "$(basename "${item%/}")" == "_shared" ]] && continue
    [[ -L "${item%/}" ]] && return 0
  done
  return 1
}

remove_cursor_commands() {
  local cmds_dir="$1"
  local removed=0

  [[ -d "$cmds_dir" ]] || return 0

  for wf in "${PACKAGES[@]}"; do
    local wf_dir
    wf_dir="$(package_dir "$wf")"
    for cmd_file in "${cmds_dir}/${wf}"-*.md; do
      [[ -f "$cmd_file" ]] || continue
      local base
      base="$(basename "$cmd_file" .md)"
      local suffix="${base#"${wf}-"}"
      if [[ -f "${wf_dir}/commands/${suffix}.md" ]]; then
        rm -f "$cmd_file"
        removed=$((removed + 1))
      fi
    done
  done

  [[ $removed -gt 0 ]] && echo "  Removed ${removed} command(s) from ${cmds_dir}  ($SCOPE)"
  return 0
}

uninstall_cursor() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.cursor/skills"
    CMDS_DIR="${PROJECT_ROOT}/.cursor/commands"
  else
    SKILLS_DIR="${HOME}/.cursor/skills"
    CMDS_DIR="${HOME}/.cursor/commands"
  fi

  remove_cursor_commands "$CMDS_DIR"
  if [[ "$SELECTIVE" == false ]]; then
    uninstall_shared "$SKILLS_DIR"
  fi
  for wf in "${PACKAGES[@]}"; do
    LINK="${SKILLS_DIR}/${wf}"
    if [[ -L "$LINK" ]]; then
      rm -f "$LINK"
      echo "  Removed $LINK"
    elif [[ -e "$LINK" ]]; then
      echo "  Warning: $LINK exists but is not a symlink; skipping" >&2
    fi
  done
  if [[ "$SELECTIVE" == true ]] && ! has_remaining_packages "$SKILLS_DIR"; then
    uninstall_shared "$SKILLS_DIR"
  fi
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

  for wf in "${PACKAGES[@]}"; do
    REMOVE_LINES=()
    local wf_dir
    wf_dir="$(package_dir "$wf")"
    if [[ "$SCOPE" == "project" ]]; then
      REMOVE_LINES+=("For ${wf}, read and follow ${wf_dir}/SKILL.md")
      REMOVE_LINES+=("For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/SKILL.md")
      REMOVE_LINES+=("For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/skills/controller.md")
    else
      REMOVE_LINES+=("For ${wf}, read and follow ~/.ai-workflows/${wf}/SKILL.md")
      REMOVE_LINES+=("For ${wf}, read and follow ~/.ai-workflows/skills/${wf}/SKILL.md")
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

  # Remove skill symlinks
  SKILLS_DIR="$(dirname "$CLAUDE_MD")/skills"
  if [[ "$SELECTIVE" == false ]]; then
    uninstall_shared "$SKILLS_DIR"
  fi
  for wf in "${PACKAGES[@]}"; do
    LINK="${SKILLS_DIR}/${wf}"
    if [[ -L "$LINK" ]]; then
      rm -f "$LINK"
      echo "  Removed $LINK"
    elif [[ -e "$LINK" ]]; then
      echo "  Warning: $LINK exists but is not a symlink; skipping" >&2
    fi
  done
  if [[ "$SELECTIVE" == true ]] && ! has_remaining_packages "$SKILLS_DIR"; then
    uninstall_shared "$SKILLS_DIR"
  fi

  # Remove the marker if no workflow references remain
  if grep -qF "$MARKER" "$CLAUDE_MD" && \
     ! grep -Eq "^For .*( workflows)?, read and follow" "$CLAUDE_MD"; then
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

  if [[ "$SELECTIVE" == false ]]; then
    uninstall_shared "$SKILLS_DIR"
  fi
  for wf in "${PACKAGES[@]}"; do
    LINK="${SKILLS_DIR}/${wf}"
    if [[ -L "$LINK" ]]; then
      rm -f "$LINK"
      echo "  Removed $LINK"
    elif [[ -e "$LINK" ]]; then
      echo "  Warning: $LINK exists but is not a symlink; skipping" >&2
    fi
  done
  if [[ "$SELECTIVE" == true ]] && ! has_remaining_packages "$SKILLS_DIR"; then
    uninstall_shared "$SKILLS_DIR"
  fi
}

uninstall_codex() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.agents/skills"
  else
    SKILLS_DIR="${HOME}/.agents/skills"
  fi

  if [[ "$SELECTIVE" == false ]]; then
    uninstall_shared "$SKILLS_DIR"
  fi
  for wf in "${PACKAGES[@]}"; do
    LINK="${SKILLS_DIR}/${wf}"
    if [[ -L "$LINK" ]]; then
      rm -f "$LINK"
      echo "  Removed $LINK"
    elif [[ -e "$LINK" ]]; then
      echo "  Warning: $LINK exists but is not a symlink; skipping" >&2
    fi
  done
  if [[ "$SELECTIVE" == true ]] && ! has_remaining_packages "$SKILLS_DIR"; then
    uninstall_shared "$SKILLS_DIR"
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
    uninstall_gemini
    uninstall_codex
    if [[ "$SCOPE" == "user" && "$SELECTIVE" == false ]]; then
      if [[ -x "${REPO_DIR}/hack/install-update-timer.sh" ]]; then
        if ! "${REPO_DIR}/hack/install-update-timer.sh" --remove; then
          echo "Warning: failed to remove update notifier; you may need to clean it up manually" >&2
        fi
      fi
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
  codex)
    uninstall_codex
    ;;
  *)
    echo "Usage: $0 <all|cursor|claude|gemini|codex> [--packages name1,name2] [--project [path]]" >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  --packages names      uninstall only the listed packages (comma-separated)" >&2
    echo "                         defaults to all packages" >&2
    echo "  --workflows names     deprecated alias for --packages" >&2
    echo "  --project [path]      project-level (.cursor/skills/, .claude/, .gemini/skills/, .agents/skills/)" >&2
    echo "                         path defaults to current directory" >&2
    echo "  --list                list available workflows and exit" >&2
    exit 1
    ;;
esac

echo "Done."
