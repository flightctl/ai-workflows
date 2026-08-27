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
#   ./install.sh cursor --with-update-timer              # also enable daily update notifier
#   ./install.sh cursor --no-update-timer                # skip the update-notifier prompt

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.ai-workflows"
UPDATE_TIMER="ask" # ask | yes | no

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

UXD_REPO="https://github.com/rh-uxd/ai-helpers.git"
UXD_SHA="ad44b9c92c89730da5191487d0ff82af09b41366"
UXD_DIR="${HOME}/.uxd-ai-skills"
UXD_PLUGINS=(uxd-workshop)

# Install UXD AI Skills via git clone + symlinks (AI-agnostic; works for all
# tools). Called at the end of each install target when ux-design is in scope.
install_uxd_skills() {
  local skills_dir="$1"

  # Only install if ux-design is in the workflow set being installed
  local has_ux_design=false
  for wf in "${WORKFLOWS[@]}"; do
    [[ "$wf" == "ux-design" ]] && has_ux_design=true
  done
  "$has_ux_design" || return 0

  if [[ ! -d "$UXD_DIR" ]]; then
    echo "  Cloning UXD AI Skills repo (${UXD_SHA:0:7})..."
    git clone "$UXD_REPO" "$UXD_DIR" 2>/dev/null || {
      echo "  Error: could not clone UXD AI Skills repo — ux-design workflow requires it" >&2
      echo "  Check network access to github.com and re-run install." >&2
      return 1
    }
    git -C "$UXD_DIR" checkout "$UXD_SHA" 2>/dev/null || {
      echo "  Error: could not check out UXD AI Skills commit ${UXD_SHA:0:7}" >&2
      return 1
    }
  else
    # Existing install: make sure it is on the pinned SHA. Fetch first in case
    # the local clone predates the pinned commit; a fetch failure is non-fatal
    # only when the commit is already present locally.
    if ! git -C "$UXD_DIR" cat-file -e "${UXD_SHA}^{commit}" 2>/dev/null; then
      echo "  Fetching UXD AI Skills updates (${UXD_SHA:0:7})..."
      git -C "$UXD_DIR" fetch origin 2>/dev/null || {
        echo "  Error: could not fetch UXD AI Skills commit ${UXD_SHA:0:7}" >&2
        echo "  Check network access to github.com and re-run install." >&2
        return 1
      }
    fi
    git -C "$UXD_DIR" checkout "$UXD_SHA" 2>/dev/null || {
      echo "  Error: could not check out UXD AI Skills commit ${UXD_SHA:0:7}" >&2
      return 1
    }
  fi

  for plugin in "${UXD_PLUGINS[@]}"; do
    local plugin_skills="${UXD_DIR}/plugins/${plugin}/skills"
    [[ -d "$plugin_skills" ]] || continue
    for skill_dir in "${plugin_skills}"/*/; do
      [[ -d "$skill_dir" ]] || continue
      local skill_name
      skill_name="$(basename "$skill_dir")"
      local target="${skills_dir}/${skill_name}"
      if [[ -e "$target" && ! -L "$target" ]]; then
        echo "  Warning: ${target} exists and is not a symlink; skipping" >&2
        continue
      fi
      ln -sfn "$skill_dir" "$target"
      echo "  Linked ${target} -> ${skill_dir}  (uxd)"
    done
  done
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

  for wf in "${WORKFLOWS[@]}"; do
    local wf_dir="${INSTALL_DIR}/${wf}"
    [[ -d "${wf_dir}/commands" ]] || continue

    for cmd_file in "${wf_dir}"/commands/*.md; do
      [[ -f "$cmd_file" ]] || continue
      local phase
      phase="$(basename "$cmd_file" .md)"
      local cmd_name="${wf}-${phase}"

      local description=""
      if head -1 "$cmd_file" | grep -q "^---"; then
        description="$(awk '/^---/{n++; next} n==1 && /^description:/{sub(/^description:[[:space:]]*"?/, ""); sub(/"[[:space:]]*$/, ""); print; exit}' "$cmd_file")"
      fi
      if [[ -z "$description" ]] && [[ -f "${wf_dir}/skills/${phase}.md" ]]; then
        description="$(awk '/^---/{n++; next} n==1 && /^description:/{sub(/^description:[[:space:]]*"?/, ""); sub(/"[[:space:]]*$/, ""); print; exit}' "${wf_dir}/skills/${phase}.md")"
      fi
      [[ -z "$description" ]] && description="Run the ${phase} phase of the ${wf} workflow."
      description="${description//\"/\\\"}"

      cat > "${cmds_dir}/${cmd_name}.md" <<CMD_EOF
---
description: "${description}"
---
# /${phase} (${wf})

Read \`${INSTALL_DIR}/${wf}/skills/controller.md\` and follow it.

Dispatch the **${phase}** phase. Context:

\$ARGUMENTS
CMD_EOF
      generated=$((generated + 1))
    done
  done

  [[ $generated -gt 0 ]] && echo "  Generated ${generated} command(s) in ${cmds_dir}  ($SCOPE)"
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
  for wf in "${WORKFLOWS[@]}"; do
    ln -sfn "${INSTALL_DIR}/${wf}" "${SKILLS_DIR}/${wf}"
    echo "  Linked ${SKILLS_DIR}/${wf} -> ${INSTALL_DIR}/${wf}  ($SCOPE)"
  done
  generate_cursor_commands "$CMDS_DIR"
  install_uxd_skills "$SKILLS_DIR"
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
    if [[ "$SCOPE" == "project" ]]; then
      LINE="For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/SKILL.md"
    else
      LINE="For ${wf} workflows, read and follow ~/.ai-workflows/${wf}/SKILL.md"
    fi

    # Remove stale entries: old controller.md references and the alternate
    # path format (~ vs expanded $HOME) to avoid duplicates when both scopes
    # target the same CLAUDE.md.
    STALE_LINES=(
      "For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/skills/controller.md"
      "For ${wf} workflows, read and follow ~/.ai-workflows/${wf}/skills/controller.md"
      "For ${wf} workflows, read and follow ${INSTALL_DIR}/${wf}/SKILL.md"
      "For ${wf} workflows, read and follow ~/.ai-workflows/${wf}/SKILL.md"
    )
    for stale in "${STALE_LINES[@]}"; do
      [[ "$stale" == "$LINE" ]] && continue
      if grep -qF "$stale" "$CLAUDE_MD"; then
        grep -vF "$stale" "$CLAUDE_MD" > "${CLAUDE_MD}.tmp" && mv "${CLAUDE_MD}.tmp" "$CLAUDE_MD"
        echo "  Replaced outdated $wf reference in $CLAUDE_MD"
      fi
    done

    if grep -qF "$LINE" "$CLAUDE_MD"; then
      echo "  Reference for $wf already present in $CLAUDE_MD"
    else
      printf '%s\n' "$LINE" >> "$CLAUDE_MD"
      echo "  Added $wf reference to $CLAUDE_MD  ($SCOPE)"
    fi
  done

  # Symlink workflow directories into Claude Code's skills directory so they
  # are discovered as slash commands (Claude Code scans .claude/skills/).
  SKILLS_DIR="${CLAUDE_DIR}/skills"
  mkdir -p "$SKILLS_DIR"
  install_shared "$SKILLS_DIR"
  for wf in "${WORKFLOWS[@]}"; do
    ln -sfn "${INSTALL_DIR}/${wf}" "${SKILLS_DIR}/${wf}"
    echo "  Linked ${SKILLS_DIR}/${wf} -> ${INSTALL_DIR}/${wf}  ($SCOPE)"
  done

  # Symlink each workflow's commands/ directory into Claude Code's commands
  # directory so individual phases are discoverable as /{workflow}:{command}
  # slash commands (e.g. /bugfix:assess, /cve-fix:patch).
  CMDS_DIR="${CLAUDE_DIR}/commands"
  mkdir -p "$CMDS_DIR"
  for wf in "${WORKFLOWS[@]}"; do
    if [[ -d "${INSTALL_DIR}/${wf}/commands" ]]; then
      ln -sfn "${INSTALL_DIR}/${wf}/commands" "${CMDS_DIR}/${wf}"
      echo "  Linked ${CMDS_DIR}/${wf} -> ${INSTALL_DIR}/${wf}/commands  ($SCOPE)"
    elif [[ -L "${CMDS_DIR}/${wf}" ]]; then
      rm -f "${CMDS_DIR}/${wf}"
      echo "  Removed stale commands symlink ${CMDS_DIR}/${wf}  ($SCOPE)"
    fi
  done
  install_uxd_skills "$SKILLS_DIR"
}

install_gemini() {
  if [[ "$SCOPE" == "project" ]]; then
    SKILLS_DIR="${PROJECT_ROOT}/.gemini/skills"
  else
    SKILLS_DIR="${HOME}/.gemini/skills"
  fi

  mkdir -p "$SKILLS_DIR"
  install_shared "$SKILLS_DIR"
  for wf in "${WORKFLOWS[@]}"; do
    ln -sfn "${INSTALL_DIR}/${wf}" "${SKILLS_DIR}/${wf}"
    echo "  Linked ${SKILLS_DIR}/${wf} -> ${INSTALL_DIR}/${wf}  ($SCOPE)"
  done
  install_uxd_skills "$SKILLS_DIR"
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
    echo "  --with-update-timer   enable daily Linux update notifier (no prompt)" >&2
    echo "  --no-update-timer     skip the update-notifier prompt" >&2
    echo "  --list                list available workflows and exit" >&2
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
