#!/usr/bin/env bash
# Install ai-workflows via symlinks.
# Automatically discovers workflows and simple skills (any supported dir with a SKILL.md).
#
# Scope:
#   User-level (default) — available in all your projects
#   Project-level         — committed / shared with a specific repo
#
# Usage:
#   ./install.sh cursor                                  # user-level, all packages
#   ./install.sh cursor --packages bugfix                # user-level, specific package
#   ./install.sh cursor --packages bugfix,report-bug     # user-level, multiple packages
#   ./install.sh cursor --project [path]                 # project-level, all packages
#   ./install.sh claude                                  # user-level Claude Code reference
#   ./install.sh claude --project [path]                 # project-level Claude Code reference
#   ./install.sh gemini                                  # user-level Gemini CLI skill symlinks
#   ./install.sh gemini --project [path]                 # project-level Gemini CLI skill symlinks
#   ./install.sh codex                                   # user-level Codex skill symlinks
#   ./install.sh codex --project [path]                  # project-level Codex skill symlinks
#   ./install.sh all                                     # user-level, all environments
#   ./install.sh all --project [path]                    # project-level, all environments
#   ./install.sh --list                                  # list available packages
#   ./install.sh cursor --with-update-timer              # also enable daily update notifier
#   ./install.sh cursor --no-update-timer                # skip the update-notifier prompt

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.ai-workflows"
UPDATE_TIMER="ask" # ask | yes | no

# --- discover all available packages ---
ALL_PACKAGES=()
ALL_PACKAGE_PATHS=()
for skill in "$REPO_DIR"/*/SKILL.md "$REPO_DIR"/skills/*/SKILL.md; do
  [[ -f "$skill" ]] || continue
  package_name="$(basename "$(dirname "$skill")")"
  package_path="$(dirname "${skill#"$REPO_DIR"/}")"
  for existing_name in "${ALL_PACKAGES[@]}"; do
    if [[ "$existing_name" == "$package_name" ]]; then
      echo "Error: duplicate package name '$package_name'" >&2
      echo "Package names must be unique across top-level workflows and skills/." >&2
      exit 1
    fi
  done
  ALL_PACKAGES+=("$package_name")
  ALL_PACKAGE_PATHS+=("$package_path")
done

resolve_package_dir() {
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
    for package in "${ALL_PACKAGES[@]}"; do
      echo "  $package"
    done
    exit 0
  fi
done

# --- parse arguments ---
TARGET="${1:-cursor}"
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
    --with-update-timer)
      UPDATE_TIMER="yes"
      ;;
    --no-update-timer)
      UPDATE_TIMER="no"
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

if [[ ${#PACKAGES[@]} -eq 0 ]]; then
  echo "Error: no packages found (directories with SKILL.md)" >&2
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

install_shared() {
  local target_dir="$1"
  if [[ ! -d "${INSTALL_DIR}/_shared" ]]; then
    return
  fi
  if [[ -e "${target_dir}/_shared" && ! -L "${target_dir}/_shared" ]]; then
    echo "  Warning: ${target_dir}/_shared exists and is not a symlink; skipping" >&2
    return
  fi
  ln -sfn "${INSTALL_DIR}/_shared" "${target_dir}/_shared"
  echo "  Linked ${target_dir}/_shared -> ${INSTALL_DIR}/_shared  ($SCOPE)"
}

generate_cursor_commands() {
  local cmds_dir="$1"
  local generated=0

  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    [[ -d "${package_dir}/commands" ]] || continue

    for cmd_file in "${package_dir}"/commands/*.md; do
      [[ -f "$cmd_file" ]] || continue
      local phase
      phase="$(basename "$cmd_file" .md)"
      local cmd_name="${package}-${phase}"

      local description=""
      if head -1 "$cmd_file" | grep -q "^---"; then
        description="$(awk '/^---/{n++; next} n==1 && /^description:/{sub(/^description:[[:space:]]*"?/, ""); sub(/"[[:space:]]*$/, ""); print; exit}' "$cmd_file")"
      fi
      if [[ -z "$description" ]] && [[ -f "${package_dir}/skills/${phase}.md" ]]; then
        description="$(awk '/^---/{n++; next} n==1 && /^description:/{sub(/^description:[[:space:]]*"?/, ""); sub(/"[[:space:]]*$/, ""); print; exit}' "${package_dir}/skills/${phase}.md")"
      fi
      [[ -z "$description" ]] && description="Run the ${phase} phase of the ${package} workflow."
      description="${description//\"/\\\"}"

      cat > "${cmds_dir}/${cmd_name}.md" <<CMD_EOF
---
description: "${description}"
---
# /${phase} (${package})

Read \`${INSTALL_DIR}/${package}/skills/controller.md\` and follow it.

Dispatch the **${phase}** phase. Context:

\$ARGUMENTS
CMD_EOF
      generated=$((generated + 1))
    done
  done

  [[ $generated -gt 0 ]] && echo "  Generated ${generated} command(s) in ${cmds_dir}  ($SCOPE)"
  return 0
}

install_cursor() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.cursor/skills"
    CMDS_DIR="${PROJECT_ROOT}/.cursor/commands"
  else
    SKILLS_DIR="${HOME}/.cursor/skills"
    CMDS_DIR="${HOME}/.cursor/commands"
  fi

  mkdir -p "$SKILLS_DIR" "$CMDS_DIR"
  install_shared "$SKILLS_DIR"
  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    ln -sfn "$package_dir" "${SKILLS_DIR}/${package}"
    echo "  Linked ${SKILLS_DIR}/${package} -> ${package_dir}  ($SCOPE)"
  done
  generate_cursor_commands "$CMDS_DIR"
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

  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    if [[ "$SCOPE" == "project" ]]; then
      LINE="For ${package}, read and follow ${package_dir}/SKILL.md"
    else
      if [[ "$package_dir" == "${INSTALL_DIR}/skills/"* ]]; then
        LINE="For ${package}, read and follow ~/.ai-workflows/skills/${package}/SKILL.md"
      else
        LINE="For ${package}, read and follow ~/.ai-workflows/${package}/SKILL.md"
      fi
    fi

    # Remove stale entries: old controller.md references and the alternate
    # path format (~ vs expanded $HOME) to avoid duplicates when both scopes
    # target the same CLAUDE.md.
    STALE_LINES=(
      "For ${package}, read and follow ${INSTALL_DIR}/${package}/SKILL.md"
      "For ${package}, read and follow ${INSTALL_DIR}/skills/${package}/SKILL.md"
      "For ${package}, read and follow ~/.ai-workflows/${package}/SKILL.md"
      "For ${package}, read and follow ~/.ai-workflows/skills/${package}/SKILL.md"
      "For ${package} workflows, read and follow ${INSTALL_DIR}/${package}/skills/controller.md"
      "For ${package} workflows, read and follow ~/.ai-workflows/${package}/skills/controller.md"
      "For ${package} workflows, read and follow ${INSTALL_DIR}/${package}/SKILL.md"
      "For ${package} workflows, read and follow ~/.ai-workflows/${package}/SKILL.md"
    )
    for stale in "${STALE_LINES[@]}"; do
      [[ "$stale" == "$LINE" ]] && continue
      if grep -qF "$stale" "$CLAUDE_MD"; then
        grep -vF "$stale" "$CLAUDE_MD" > "${CLAUDE_MD}.tmp" && mv "${CLAUDE_MD}.tmp" "$CLAUDE_MD"
        echo "  Replaced outdated $package reference in $CLAUDE_MD"
      fi
    done

    if grep -qF "$LINE" "$CLAUDE_MD"; then
      echo "  Reference for $package already present in $CLAUDE_MD"
    else
      printf '%s\n' "$LINE" >> "$CLAUDE_MD"
      echo "  Added $package reference to $CLAUDE_MD  ($SCOPE)"
    fi
  done

  # Symlink package directories into Claude Code's skills directory so they
  # are discovered as slash commands (Claude Code scans .claude/skills/).
  SKILLS_DIR="${CLAUDE_DIR}/skills"
  mkdir -p "$SKILLS_DIR"
  install_shared "$SKILLS_DIR"
  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    ln -sfn "$package_dir" "${SKILLS_DIR}/${package}"
    echo "  Linked ${SKILLS_DIR}/${package} -> ${package_dir}  ($SCOPE)"
  done

  # Symlink each workflow's commands/ directory into Claude Code's commands
  # directory so individual phases are discoverable as /{workflow}:{command}
  # slash commands (e.g. /bugfix:assess, /cve-fix:patch).
  CMDS_DIR="${CLAUDE_DIR}/commands"
  mkdir -p "$CMDS_DIR"
  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    if [[ -d "${package_dir}/commands" ]]; then
      ln -sfn "${package_dir}/commands" "${CMDS_DIR}/${package}"
      echo "  Linked ${CMDS_DIR}/${package} -> ${package_dir}/commands  ($SCOPE)"
    elif [[ -L "${CMDS_DIR}/${package}" ]]; then
      rm -f "${CMDS_DIR}/${package}"
      echo "  Removed stale commands symlink ${CMDS_DIR}/${package}  ($SCOPE)"
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
  install_shared "$SKILLS_DIR"
  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    ln -sfn "$package_dir" "${SKILLS_DIR}/${package}"
    echo "  Linked ${SKILLS_DIR}/${package} -> ${package_dir}  ($SCOPE)"
  done
}

install_codex() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.agents/skills"
  else
    SKILLS_DIR="${HOME}/.agents/skills"
  fi

  mkdir -p "$SKILLS_DIR"
  install_shared "$SKILLS_DIR"
  for package in "${PACKAGES[@]}"; do
    local package_dir
    package_dir="$(resolve_package_dir "$package")"
    ln -sfn "$package_dir" "${SKILLS_DIR}/${package}"
    echo "  Linked ${SKILLS_DIR}/${package} -> ${package_dir}  ($SCOPE)"
  done
}

# Offer a daily systemd --user notifier (Linux desktop). Default: no.
maybe_offer_update_timer() {
  local installer="${REPO_DIR}/hack/install-update-timer.sh"

  if [[ "$UPDATE_TIMER" == "no" ]]; then
    return 0
  fi
  if [[ ! -x "$installer" ]]; then
    [[ "$UPDATE_TIMER" == "yes" ]] && echo "Update notifier: installer script missing/not executable; skipping." >&2
    return 0
  fi
  # Linux + desktop notification stack only.
  if [[ "$(uname -s)" != "Linux" ]]; then
    [[ "$UPDATE_TIMER" == "yes" ]] && echo "Update notifier requires Linux; --with-update-timer ignored." >&2
    return 0
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    [[ "$UPDATE_TIMER" == "yes" ]] && echo "Update notifier requires systemd; --with-update-timer ignored." >&2
    return 0
  fi
  if ! systemctl --user status >/dev/null 2>&1; then
    [[ "$UPDATE_TIMER" == "yes" ]] && echo "Update notifier requires an active systemd --user session; --with-update-timer ignored." >&2
    return 0
  fi
  if ! command -v notify-send >/dev/null 2>&1; then
    [[ "$UPDATE_TIMER" == "yes" ]] && echo "Update notifier requires notify-send; --with-update-timer ignored." >&2
    return 0
  fi
  # Already enabled — don't re-prompt on every install.
  if systemctl --user is-enabled ai-workflows-update-check.timer >/dev/null 2>&1; then
    echo "Update notifier already enabled (ai-workflows-update-check.timer)."
    return 0
  fi

  local answer="n"
  if [[ "$UPDATE_TIMER" == "yes" ]]; then
    answer="y"
  elif [[ -t 0 ]]; then
    echo
    echo "Optional: enable a daily desktop notification when ai-workflows is behind main?"
    echo "  (Linux/systemd; run 'aiw-update' when notified. Default: No)"
    read -r -p "Enable daily update notifier? [y/N] " answer || true
  elif { : <>/dev/tty; } 2>/dev/null; then
    # stdin may be piped; prompt on the controlling terminal when available.
    echo
    echo "Optional: enable a daily desktop notification when ai-workflows is behind main?"
    echo "  (Linux/systemd; run 'aiw-update' when notified. Default: No)"
    read -r -p "Enable daily update notifier? [y/N] " answer </dev/tty || true
  else
    # Non-interactive: skip unless --with-update-timer was passed.
    return 0
  fi

  case "${answer,,}" in
    y|yes)
      if ! "$installer"; then
        echo "Warning: failed to enable update notifier; retry later with: ${installer}" >&2
      fi
      ;;
    *)
      echo "Skipped update notifier. Enable later with: ${installer}"
      ;;
  esac
}

# --- main ---

echo "Installing ai-workflows ($TARGET, $SCOPE)..."
echo "  Packages: ${PACKAGES[*]}"
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
  codex)
    install_codex
    ;;
  all)
    install_cursor
    install_claude
    install_gemini
    install_codex
    ;;
  *)
    echo "Usage: $0 <cursor|claude|gemini|codex|all> [--packages name1,name2] [--project [path]]" >&2
    echo "" >&2
    echo "Targets:" >&2
    echo "  cursor   Cursor skill symlinks" >&2
    echo "  claude   Claude Code instruction references" >&2
    echo "  gemini   Gemini CLI skill symlinks" >&2
    echo "  codex    Codex skill symlinks" >&2
    echo "  all      Cursor + Claude + Gemini + Codex" >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  --packages names      install only the listed packages (comma-separated)" >&2
    echo "                         defaults to all available packages" >&2
    echo "  --workflows names     deprecated alias for --packages" >&2
    echo "  --project [path]      project-level (.cursor/skills/, .claude/, .gemini/skills/, .agents/skills/)" >&2
    echo "                         path defaults to current directory" >&2
    echo "  --with-update-timer   enable daily Linux update notifier (no prompt)" >&2
    echo "  --no-update-timer     skip the update-notifier prompt" >&2
    echo "  --list                list available packages and exit" >&2
    exit 1
    ;;
esac

maybe_offer_update_timer
if command -v aiw-update >/dev/null 2>&1; then
  echo "Done. Run 'git pull' from $INSTALL_DIR to update (or: aiw-update)."
elif [[ -x "${HOME}/.local/bin/aiw-update" ]]; then
  echo "Done. Run 'git pull' from $INSTALL_DIR to update (or: ${HOME}/.local/bin/aiw-update)."
else
  echo "Done. Run 'git pull' from $INSTALL_DIR to update."
fi
