#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
IMAGE=ai-workflows-e2e:latest

podman build -t "$IMAGE" -f "$REPO_ROOT/tests/e2e/implement/Containerfile" "$REPO_ROOT/tests/e2e/implement/"

# Mount credential files from the host read-only into a staging directory
# inside the container. The container startup script (running as root) copies
# them to /home/e2e/ and chowns them to the e2e user (UID 1000) before dropping
# to that user for the actual test run. This avoids any permission dance on the
# host and does not require --userns=keep-id.
CREDENTIAL_MOUNTS=()
CREDENTIAL_SETUP=""

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  if [[ -d "$HOME/.claude" ]]; then
    CREDENTIAL_MOUNTS+=(-v "$HOME/.claude:/mnt/creds/claude:ro,z")
    CREDENTIAL_SETUP+='cp -r /mnt/creds/claude /home/e2e/.claude && chown -R 1000:1000 /home/e2e/.claude; '
  fi
  if [[ -f "$HOME/.claude.json" ]]; then
    CREDENTIAL_MOUNTS+=(-v "$HOME/.claude.json:/mnt/creds/claude.json:ro,z")
    CREDENTIAL_SETUP+='cp /mnt/creds/claude.json /home/e2e/.claude.json && chown 1000:1000 /home/e2e/.claude.json; '
  fi
  if [[ -d "$HOME/.config/gcloud" ]]; then
    CREDENTIAL_MOUNTS+=(-v "$HOME/.config/gcloud:/mnt/creds/gcloud:ro,z")
    CREDENTIAL_SETUP+='mkdir -p /home/e2e/.config && cp -r /mnt/creds/gcloud /home/e2e/.config/gcloud && chown -R 1000:1000 /home/e2e/.config/gcloud; '
  fi
fi

# Ensure a GitHub token is available for cloning private repos.
# In CI, GITHUB_TOKEN is injected by the runner. Locally, fall back to the
# token from the gh CLI session (gh auth token) so no manual setup is needed.
if [[ -z "${GITHUB_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
  if command -v gh &>/dev/null; then
    _tok=$(gh auth token 2>/dev/null || true)
    if [[ -n "$_tok" ]]; then
      export GITHUB_TOKEN="$_tok"
    fi
  fi
fi

# Ensure cache directories exist on the host so the mounts are valid.
mkdir -p "$HOME/.cache/e2e-repos"
mkdir -p "$HOME/.cache/e2e-fixture-images"

# Collect ginkgo args. Arguments with spaces (e.g. --focus "full workflow")
# are joined by the IFS separator; the inner sh -c expands $GINKGO_ARGS via
# word-splitting, so multi-word focus patterns must be passed as a single
# shell word using the = form: --focus=<pattern> (no space after --focus).
GINKGO_ARGS="$*"

# The test run proper, executed as the e2e user after credential setup.
TEST_CMD='cp -r /workspace/tests/e2e/implement /tmp/e2e && cd /tmp/e2e && HOME=/home/e2e ginkgo -v --timeout 90m $GINKGO_ARGS'

# If credentials need copying, start as root, do the setup, then drop to e2e.
# Otherwise start as the image default user (e2e, UID 1000) directly.
if [[ -n "$CREDENTIAL_SETUP" ]]; then
  STARTUP="${CREDENTIAL_SETUP}exec su -s /bin/sh e2e -c '${TEST_CMD}'"
  USER_ARG=(--user root)
else
  STARTUP="$TEST_CMD"
  USER_ARG=()
fi

podman run --rm \
  --privileged \
  "${USER_ARG[@]+"${USER_ARG[@]}"}" \
  -v "$REPO_ROOT:/workspace:ro,z" \
  "${CREDENTIAL_MOUNTS[@]+"${CREDENTIAL_MOUNTS[@]}"}" \
  -v "$HOME/.cache/e2e-repos:/tmp/e2e-repos:z" \
  -v "$HOME/.cache/e2e-fixture-images:/tmp/e2e-fixture-images:z" \
  -e AI_WORKFLOWS_ROOT=/workspace \
  -e E2E_REPO_CACHE=/tmp/e2e-repos \
  -e E2E_IMAGES_CACHE=/tmp/e2e-fixture-images \
  -e GINKGO_ARGS \
  -e ANTHROPIC_API_KEY \
  -e CLAUDE_CODE_USE_VERTEX \
  -e ANTHROPIC_VERTEX_PROJECT_ID \
  -e GITHUB_TOKEN \
  -e GH_TOKEN \
  "$IMAGE" \
  sh -c "$STARTUP"
