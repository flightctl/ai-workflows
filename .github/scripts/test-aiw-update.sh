#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="$(mktemp -d)"
TEST_HOME="${TEST_ROOT}/home"
TEST_PROJECT="${TEST_ROOT}/project"
ORIGIN_REPO="${TEST_ROOT}/origin.git"
WORKFLOWS_REPO="${TEST_ROOT}/ai-workflows"
INSTALL_LOG="${TEST_ROOT}/install.log"
trap 'rm -rf "$TEST_ROOT"' EXIT

mkdir -p "$TEST_HOME/.agents/skills" "$TEST_PROJECT/.agents/skills" "$WORKFLOWS_REPO/hack"
git init --bare -q "$ORIGIN_REPO"
git init -q -b main "$WORKFLOWS_REPO"

cp "$REPO_ROOT/hack/aiw-update.sh" "${WORKFLOWS_REPO}/hack/aiw-update.sh"
cat > "${WORKFLOWS_REPO}/install.sh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$INSTALL_LOG"
EOF
chmod +x "${WORKFLOWS_REPO}/install.sh"

git -C "$WORKFLOWS_REPO" remote add origin "$ORIGIN_REPO"
git -C "$WORKFLOWS_REPO" add hack/aiw-update.sh install.sh
git -C "$WORKFLOWS_REPO" -c user.name='Test User' -c user.email='test@example.com' commit -q -m 'test fixture'
git -C "$WORKFLOWS_REPO" push -q origin main

ln -s "$WORKFLOWS_REPO" "${TEST_HOME}/.ai-workflows"
HOME="$TEST_HOME" AI_WORKFLOWS_DIR="${TEST_HOME}/.ai-workflows" INSTALL_LOG="$INSTALL_LOG" \
  "${WORKFLOWS_REPO}/hack/aiw-update.sh" --reinstall --project "$TEST_PROJECT"

grep -Fx 'codex --no-update-timer' "$INSTALL_LOG"
grep -Fx "codex --project $TEST_PROJECT --no-update-timer" "$INSTALL_LOG"

if grep -Ev '^(codex --no-update-timer|codex --project .* --no-update-timer)$' "$INSTALL_LOG" | grep -q .; then
  echo 'aiw-update refreshed an unexpected target' >&2
  exit 1
fi

rm -f "$INSTALL_LOG"
HOME="$TEST_HOME" AI_WORKFLOWS_DIR="${TEST_HOME}/.ai-workflows" INSTALL_LOG="$INSTALL_LOG" \
  "${WORKFLOWS_REPO}/hack/aiw-update.sh" --reinstall --target codex --project "$TEST_PROJECT"

grep -Fx 'codex --no-update-timer' "$INSTALL_LOG"
grep -Fx "codex --project $TEST_PROJECT --no-update-timer" "$INSTALL_LOG"
