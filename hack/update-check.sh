#!/usr/bin/env bash
# Check whether the local ai-workflows clone is behind origin/main.
# If so, write a marker file and send a desktop notification (Fedora/Linux).
#
# Intended to run from a systemd --user timer. Safe to run repeatedly:
# notifies at most once per new origin/main SHA.

set -euo pipefail

INSTALL_DIR="${AI_WORKFLOWS_DIR:-${HOME}/.ai-workflows}"
REMOTE_REF="${AI_WORKFLOWS_REMOTE_REF:-origin/main}"
MARKER="${INSTALL_DIR}/.update-available"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/ai-workflows"
LAST_NOTIFIED="${STATE_DIR}/last-notified-sha"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "ai-workflows: install dir not found: $INSTALL_DIR" >&2
  exit 0
fi

# Resolve through symlink so we operate on the real git clone.
REPO_DIR="$(readlink -f "$INSTALL_DIR")"
if [[ ! -d "${REPO_DIR}/.git" ]] && ! git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "ai-workflows: not a git repo: $REPO_DIR" >&2
  exit 0
fi

mkdir -p "$STATE_DIR"

cd "$REPO_DIR"

# Fetch quietly; network failures should not spam the user.
if ! git fetch --quiet origin main 2>/dev/null; then
  echo "ai-workflows: fetch failed (offline?); skipping check"
  exit 0
fi

if ! git rev-parse --verify "$REMOTE_REF" >/dev/null 2>&1; then
  echo "ai-workflows: missing ref $REMOTE_REF" >&2
  exit 0
fi

REMOTE_SHA="$(git rev-parse "$REMOTE_REF")"
BEHIND="$(git rev-list --count "HEAD..${REMOTE_REF}" 2>/dev/null || echo 0)"
BRANCH="$(git branch --show-current 2>/dev/null || echo detached)"

if [[ "$BEHIND" -eq 0 ]]; then
  rm -f "$MARKER"
  echo "ai-workflows: up to date with ${REMOTE_REF} (branch=${BRANCH})"
  exit 0
fi

SHORT_SHA="$(git rev-parse --short "$REMOTE_SHA")"
SUBJECT="$(git log -1 --format='%s' "$REMOTE_SHA")"

cat > "$MARKER" <<EOF
behind=${BEHIND}
remote_ref=${REMOTE_REF}
remote_sha=${REMOTE_SHA}
branch=${BRANCH}
checked_at=$(date -Iseconds)
latest_subject=${SUBJECT}
update_cmd=aiw-update
EOF

echo "ai-workflows: ${BEHIND} commit(s) behind ${REMOTE_REF} (${SHORT_SHA})"

# Deduplicate notifications for the same remote tip.
if [[ -f "$LAST_NOTIFIED" ]] && [[ "$(cat "$LAST_NOTIFIED")" == "$REMOTE_SHA" ]]; then
  echo "ai-workflows: already notified for ${SHORT_SHA}; skipping toast"
  exit 0
fi

COMMIT_WORD="commits"
[[ "$BEHIND" -eq 1 ]] && COMMIT_WORD="commit"

TITLE="New update for ai-workflows"
BODY="${BEHIND} new ${COMMIT_WORD} on main

Update with:
  aiw-update"

if command -v notify-send >/dev/null 2>&1; then
  # --expire-time in ms; keep it visible long enough to notice during testing.
  if notify-send --app-name="ai-workflows" --urgency=normal --expire-time=20000 \
    "$TITLE" "$BODY"; then
    echo "$REMOTE_SHA" > "$LAST_NOTIFIED"
  else
    echo "ai-workflows: notify-send failed; will retry next check" >&2
  fi
else
  # No desktop notifier — keep the marker file and avoid spamming every run.
  echo "ai-workflows: notify-send not found; wrote marker at $MARKER" >&2
  echo "$REMOTE_SHA" > "$LAST_NOTIFIED"
fi
