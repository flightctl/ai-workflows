#!/usr/bin/env bash
# Pull latest ai-workflows and refresh installs if command wrappers changed.
#
# Usage:
#   aiw-update                  # ff-only pull origin/main (must be on main)
#   aiw-update --checkout-main  # checkout main first, then pull
#   aiw-update --reinstall      # always re-run install.sh for detected targets
#   aiw-update --project PATH   # also reinstall Cursor skills for PATH (repeatable)
#   aiw-update --target NAME    # force install target(s): cursor|claude|gemini|all
#                               # (repeatable; default: auto-detect from ~/.cursor etc.)

set -euo pipefail

INSTALL_DIR="${AI_WORKFLOWS_DIR:-${HOME}/.ai-workflows}"
REPO_DIR="$(readlink -f "$INSTALL_DIR")"
CHECKOUT_MAIN=false
FORCE_REINSTALL=false
PROJECTS=()
FORCED_TARGETS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkout-main) CHECKOUT_MAIN=true ;;
    --reinstall) FORCE_REINSTALL=true ;;
    --project)
      if [[ -z "${2:-}" || "${2:0:1}" == "-" ]]; then
        echo "Error: --project requires a path" >&2
        exit 1
      fi
      PROJECTS+=("$2")
      shift
      ;;
    --target)
      if [[ -z "${2:-}" || "${2:0:1}" == "-" ]]; then
        echo "Error: --target requires cursor|claude|gemini|all" >&2
        exit 1
      fi
      FORCED_TARGETS+=("$2")
      shift
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

detect_install_targets() {
  local targets=()
  if [[ ${#FORCED_TARGETS[@]} -gt 0 ]]; then
    local t
    for t in "${FORCED_TARGETS[@]}"; do
      case "$t" in
        cursor|claude|gemini|all) targets+=("$t") ;;
        *)
          echo "Error: unknown --target '$t' (cursor|claude|gemini|all)" >&2
          exit 1
          ;;
      esac
    done
    printf '%s\n' "${targets[@]}"
    return
  fi

  if [[ -d "${HOME}/.cursor/skills" ]] || [[ -d "${HOME}/.cursor/commands" ]]; then
    targets+=(cursor)
  fi
  if [[ -f "${HOME}/.claude/CLAUDE.md" ]] && grep -qF '# ai-workflows' "${HOME}/.claude/CLAUDE.md" 2>/dev/null; then
    targets+=(claude)
  elif [[ -d "${HOME}/.claude/skills" ]]; then
    # Skills dir present — refresh even if marker line was customized.
    targets+=(claude)
  fi
  if [[ -d "${HOME}/.gemini/skills" ]]; then
    targets+=(gemini)
  fi

  if [[ ${#targets[@]} -eq 0 ]]; then
    targets+=(cursor)
  fi
  printf '%s\n' "${targets[@]}"
}

cd "$REPO_DIR"

CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [[ "$CURRENT_BRANCH" != "main" ]] && ! $CHECKOUT_MAIN; then
  echo "ai-workflows: not on main (branch=${CURRENT_BRANCH:-detached})." >&2
  echo "  Use: aiw-update --checkout-main" >&2
  echo "  Or rebase/merge origin/main into this branch, then retry." >&2
  exit 1
fi

BEFORE_HEAD="$(git rev-parse HEAD)"

if $CHECKOUT_MAIN; then
  git checkout main
fi

git fetch origin main
if ! git pull --ff-only origin main; then
  echo "ai-workflows: fast-forward pull from origin/main failed." >&2
  echo "  Resolve local commits on main, or: git reset --hard origin/main (destructive)." >&2
  exit 1
fi

AFTER_HEAD="$(git rev-parse HEAD)"
rm -f "${INSTALL_DIR}/.update-available"

CHANGED_COMMANDS=false
if [[ "$BEFORE_HEAD" != "$AFTER_HEAD" ]]; then
  if git diff --name-only "$BEFORE_HEAD" "$AFTER_HEAD" -- '*/commands/*.md' '*/SKILL.md' install.sh uninstall.sh | grep -q .; then
    CHANGED_COMMANDS=true
  fi
fi

mapfile -t INSTALL_TARGETS < <(detect_install_targets)

if $FORCE_REINSTALL || $CHANGED_COMMANDS; then
  local_target=""
  for local_target in "${INSTALL_TARGETS[@]}"; do
    echo "Refreshing user-level install (${local_target})..."
    # Avoid re-prompting for the update timer on every refresh.
    "${REPO_DIR}/install.sh" "$local_target" --no-update-timer
  done

  for p in "${PROJECTS[@]}"; do
    if [[ -d "$p" ]]; then
      echo "Reinstalling Cursor skills for $p"
      "${REPO_DIR}/install.sh" cursor --project "$p" --no-update-timer
    else
      echo "Warning: project path not found, skipping: $p" >&2
    fi
  done
else
  echo "Skill content updated via symlink; no command regeneration needed."
fi

echo "Done. Now at $(git rev-parse --short HEAD) ($(git branch --show-current))"
