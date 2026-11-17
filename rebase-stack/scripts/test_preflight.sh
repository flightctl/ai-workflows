#!/usr/bin/env bash
# Regression tests for rebase-stack preflight repository topology handling.
#
# Uses a disposable git repository and a mocked gh CLI. Never contacts GitHub
# or modifies a real stack.
#
# Usage:
#   bash rebase-stack/scripts/test_preflight.sh

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d "${TMPDIR:-/tmp}/rebase-stack-preflight-test.XXXXXX")

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

pass() {
  printf 'PASS: %s\n' "$1"
}

git init --quiet --initial-branch=main --bare "$TEST_DIR/remote.git"
git init --quiet --initial-branch=main "$TEST_DIR/repo"
(
  cd "$TEST_DIR/repo"
  git config user.email "preflight-test@example.com"
  git config user.name "Preflight Test"
  git remote add origin "$TEST_DIR/remote.git"
  git checkout -b story-1 >/dev/null 2>&1
  git commit --allow-empty -m "fixture" >/dev/null
)

cd "$TEST_DIR/repo"

mkdir "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [ "${1:-}" = "stack" ] && [ "${2:-}" = "--version" ]; then
  printf '1.0.0\n'
  exit 0
fi
if [ "${1:-}" = "stack" ] && [ "${2:-}" = "view" ]; then
  printf '%s' '{"trunk":"main","currentBranch":"story-1","branches":[{"name":"story-1","needsRebase":false},{"name":"story-2","needsRebase":false}]}'
  exit 0
fi
if [ "${1:-}" = "repo" ] && [ "${2:-}" = "view" ]; then
  cat "$REBASE_STACK_TEST_REPO_JSON"
  exit 0
fi
exit 1
STUB
chmod +x "$TEST_DIR/bin/gh"

run_case() {
  local label="$1"
  local repo_json="$2"
  local expected_rc="$3"
  local expected_parent="$4"
  local rc actual_parent

  printf '%s' "$repo_json" > "$TEST_DIR/repo.json"

  if REBASE_STACK_TEST_REPO_JSON="$TEST_DIR/repo.json" \
     PATH="$TEST_DIR/bin:$PATH" \
     bash "$SCRIPTS_DIR/preflight.sh" \
     > "$TEST_DIR/stdout" 2> "$TEST_DIR/stderr"; then
    rc=0
  else
    rc=$?
  fi

  if [ "$rc" -ne "$expected_rc" ]; then
    printf 'FAIL: %s exited %s, expected %s\n' "$label" "$rc" "$expected_rc" >&2
    cat "$TEST_DIR/stderr" >&2
    return 1
  fi

  if [ "$expected_rc" -eq 0 ]; then
    actual_parent=$(jq -r 'if .parentRepo == null then "<null>" else .parentRepo end' \
      "$TEST_DIR/stdout")
    if [ "$actual_parent" != "$expected_parent" ]; then
      printf 'FAIL: %s emitted parentRepo=%s, expected %s\n' \
        "$label" "$actual_parent" "$expected_parent" >&2
      return 1
    fi
  elif ! grep -q 'incomplete repository topology' "$TEST_DIR/stderr"; then
    printf 'FAIL: %s did not report incomplete repository topology\n' "$label" >&2
    cat "$TEST_DIR/stderr" >&2
    return 1
  fi

  pass "$label"
}

run_case \
  "legacy fork parent shape" \
  '{"isFork":true,"nameWithOwner":"myuser/repo","owner":{"login":"myuser"},"parent":{"nameWithOwner":"upstream/repo"}}' \
  0 \
  "upstream/repo"

run_case \
  "current fork parent shape" \
  '{"isFork":true,"nameWithOwner":"myuser/repo","owner":{"login":"myuser"},"parent":{"name":"repo","owner":{"login":"upstream"}}}' \
  0 \
  "upstream/repo"

run_case \
  "incomplete fork parent shape" \
  '{"isFork":true,"nameWithOwner":"myuser/repo","owner":{"login":"myuser"},"parent":{}}' \
  4 \
  ""

run_case \
  "direct repository" \
  '{"isFork":false,"nameWithOwner":"owner/repo","owner":{"login":"owner"}}' \
  0 \
  "<null>"
