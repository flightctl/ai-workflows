#!/usr/bin/env bash
# Pull latest ai-workflows and refresh Cursor installs if command wrappers changed.
#
# Usage:
#   aiw-update                  # ff-only pull origin/main into current branch tip
#   aiw-update --checkout-main  # checkout main first, then pull
#   aiw-update --reinstall      # always re-run install.sh (user-level cursor)
#   aiw-update --project PATH   # also reinstall Cursor skills for PATH (repeatable)

set -euo pipefail

INSTALL_DIR="${AI_WORKFLOWS_DIR:-${HOME}/.ai-workflows}"
REPO_DIR="$(readlink -f "$INSTALL_DIR")"
CHECKOUT_MAIN=false
FORCE_REINSTALL=false
PROJECTS=()

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
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

cd "$REPO_DIR"

BEFORE_HEAD="$(git rev-parse HEAD)"

if $CHECKOUT_MAIN; then
  git checkout main
fi

git fetch origin main
git pull --ff-only origin main

AFTER_HEAD="$(git rev-parse HEAD)"
rm -f "${INSTALL_DIR}/.update-available"

CHANGED_COMMANDS=false
if [[ "$BEFORE_HEAD" != "$AFTER_HEAD" ]]; then
  if git diff --name-only "$BEFORE_HEAD" "$AFTER_HEAD" -- '*/commands/*.md' install.sh uninstall.sh | grep -q .; then
    CHANGED_COMMANDS=true
  fi
fi

if $FORCE_REINSTALL || $CHANGED_COMMANDS; then
  echo "Refreshing user-level Cursor install..."
  # Avoid re-prompting for the update timer on every refresh.
  "${REPO_DIR}/install.sh" cursor --no-update-timer

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
