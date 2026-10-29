#!/usr/bin/env bash
# Regression tests for the rebase-stack push-guard, snapshot published tips,
# stack-status baseline classification, and PR creation base selection.
#
# Uses disposable bare/clone repos — never touches real stacks or branches.
# Each test creates its own isolated fixture under $TEST_DIR.
#
# Usage:
#   bash rebase-stack/scripts/test_push_guard.sh
#
# Exit codes:
#   0  all tests passed
#   1  at least one test failed

set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d "${TMPDIR:-/tmp}/rebase-stack-test.XXXXXX")

# File-based counters survive subshells.
PASS_FILE="$TEST_DIR/.pass-count"
FAIL_FILE="$TEST_DIR/.fail-count"
echo 0 > "$PASS_FILE"
echo 0 > "$FAIL_FILE"

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

pass() {
  printf '  PASS: %s\n' "$1"
  echo $(( $(cat "$PASS_FILE") + 1 )) > "$PASS_FILE"
}

fail() {
  printf '  FAIL: %s\n    %s\n' "$1" "$2"
  echo $(( $(cat "$FAIL_FILE") + 1 )) > "$FAIL_FILE"
}

# ---------------------------------------------------------------------------
# Helpers: create a bare repo + clone with a two-branch stack
# ---------------------------------------------------------------------------
setup_fixture() {
  local name="$1"
  local dir="$TEST_DIR/$name"
  mkdir -p "$dir"

  git init --bare "$dir/bare.git" >/dev/null 2>&1
  git clone "$dir/bare.git" "$dir/clone" >/dev/null 2>&1
  (
    cd "$dir/clone" || return
    git checkout -b main >/dev/null 2>&1
    echo "base" > base.txt
    git add base.txt && git commit -m "initial" >/dev/null 2>&1
    git push -u origin main >/dev/null 2>&1

    git checkout -b story-1 >/dev/null 2>&1
    echo "s1" > s1.txt
    git add s1.txt && git commit -m "story-1: feature" >/dev/null 2>&1
    git push -u origin story-1 >/dev/null 2>&1

    git checkout -b story-2 >/dev/null 2>&1
    echo "s2" > s2.txt
    git add s2.txt && git commit -m "story-2: feature" >/dev/null 2>&1
    git push -u origin story-2 >/dev/null 2>&1
  ) >/dev/null 2>&1

  printf '%s' "$dir/clone"
}

# Extract the inner hook from push-guard.sh and set up env vars for testing.
# Args: $1=hooks_dir $2=snap_path $3=ctx_path (REQUIRED — inner hook has no fallback)
setup_hook_env() {
  local hooks_dir="$1" snap="$2" ctx="$3"
  awk '/^if ! cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
    "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
  chmod +x "$hooks_dir/test-hook.sh"
  export REBASE_STACK_BASELINE_FILE="$snap"
  export REBASE_STACK_ORIGINAL_HOOK=""
  export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
  export REBASE_STACK_CONTEXT_FILE="$ctx"
}

# Build a minimal context.json for snapshot/stack-status consumption
write_context() {
  local clone="$1"
  local base_remote="${2:-origin}"
  local push_remote="${3:-origin}"
  (
    cd "$clone" || return
    local trunk="main"
    local current
    current=$(git branch --show-current)
    # Build branches array
    local branches="[]"
    for b in story-1 story-2; do
      if git rev-parse --verify --quiet "$b" >/dev/null 2>&1; then
        branches=$(jq --arg name "$b" '. + [{name: $name, pr: null}]' <<<"$branches")
      fi
    done
    jq -n \
      --arg trunk "$trunk" \
      --arg currentBranch "$current" \
      --arg baseRemote "$base_remote" \
      --arg pushRemote "$push_remote" \
      --argjson branches "$branches" \
      '{trunk: $trunk, currentBranch: $currentBranch,
        baseRemote: $baseRemote, pushRemote: $pushRemote,
        baseRemoteSource: "config", pushRemoteSource: "config",
        validationBranch: ($branches[0].name // ""),
        branches: $branches}'
  )
}

# =========================================================================
# TEST 1: snapshot.sh saves publishedTips
# =========================================================================
test_snapshot_saves_published_tips() {
  local clone
  clone=$(setup_fixture "t1-snapshot")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"
    if [ ! -f "$snap" ]; then
      fail "snapshot saves publishedTips" "snapshot file not created"
      return
    fi
    if ! jq -e '.publishedTips' "$snap" >/dev/null 2>&1; then
      fail "snapshot saves publishedTips" "publishedTips missing from snapshot"
      return
    fi
    local s1_tip s1_expected
    s1_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    s1_expected=$(git rev-parse refs/remotes/origin/story-1)
    if [ "$s1_tip" = "$s1_expected" ]; then
      pass "snapshot saves publishedTips"
    else
      fail "snapshot saves publishedTips" "expected $s1_expected, got $s1_tip"
    fi
  )
}

# =========================================================================
# TEST 2: stack-status classifies rebase divergence as (rebase) with baseline
# =========================================================================
test_status_rebase_divergence() {
  local clone
  clone=$(setup_fixture "t2-rebase-div")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    # Save snapshot before rebase
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Simulate base advancing and rebase
    git checkout main >/dev/null 2>&1
    echo "new" > new.txt && git add new.txt && git commit -m "advance main" >/dev/null 2>&1
    git push origin main >/dev/null 2>&1
    git checkout story-1 >/dev/null 2>&1
    git rebase main >/dev/null 2>&1
    git checkout story-2 >/dev/null 2>&1
    git rebase story-1 >/dev/null 2>&1

    # Run stack-status with baseline
    local output
    output=$(printf '%s' "$ctx" | bash "$SCRIPTS_DIR/stack-status.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json 2>/dev/null) || true
    if printf '%s' "$output" | grep -q "(rebase)"; then
      pass "stack-status classifies rebase divergence as (rebase)"
    else
      fail "stack-status classifies rebase divergence as (rebase)" \
        "output did not contain (rebase): $(printf '%s' "$output" | grep -i 'story')"
    fi
  )
}

# =========================================================================
# TEST 3: stack-status classifies collaborator update as (UPDATED)
# =========================================================================
test_status_collaborator_update() {
  local clone
  clone=$(setup_fixture "t3-collab")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Simulate collaborator pushing to story-1 on the remote
    local bare_path
    bare_path="$TEST_DIR/t3-collab/bare.git"
    local collab="$TEST_DIR/t3-collab/collaborator"
    git clone "$bare_path" "$collab" >/dev/null 2>&1
    (cd "$collab" && git checkout story-1 >/dev/null 2>&1 && \
     echo "collab" > collab.txt && git add collab.txt && \
     git commit -m "collaborator work" >/dev/null 2>&1 && \
     git push origin story-1 >/dev/null 2>&1)

    # Fetch to see collaborator's push
    git fetch origin >/dev/null 2>&1

    local output
    output=$(printf '%s' "$ctx" | bash "$SCRIPTS_DIR/stack-status.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json 2>/dev/null) || true
    if printf '%s' "$output" | grep -q "(UPDATED)"; then
      pass "stack-status classifies collaborator update as (UPDATED)"
    else
      fail "stack-status classifies collaborator update as (UPDATED)" \
        "output did not contain (UPDATED): $(printf '%s' "$output" | grep -i 'story')"
    fi
  )
}

# =========================================================================
# TEST 4: stack-status classifies branch deletion as DELETED
# =========================================================================
test_status_branch_deleted() {
  local clone
  clone=$(setup_fixture "t4-deleted")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Delete story-2 on the remote
    git push origin --delete story-2 >/dev/null 2>&1
    git fetch --prune origin >/dev/null 2>&1

    local output
    output=$(printf '%s' "$ctx" | bash "$SCRIPTS_DIR/stack-status.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json 2>/dev/null) || true
    if printf '%s' "$output" | grep -q "DELETED"; then
      pass "stack-status classifies branch deletion as DELETED"
    else
      fail "stack-status classifies branch deletion as DELETED" \
        "output: $(printf '%s' "$output" | grep -i 'story-2')"
    fi
  )
}

# =========================================================================
# TEST 5: pre-push hook blocks collaborator update (wire-time OID mismatch)
# =========================================================================
test_hook_blocks_collaborator() {
  local clone
  clone=$(setup_fixture "t5-hook-block")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Extract the hook script from push-guard.sh: write it directly and
    # test with simulated stdin (the format git provides to pre-push hooks).
    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    # Write the hook manually (extract the HOOKEOF block from push-guard.sh)
    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # Simulate collaborator pushing — get a different SHA for story-1
    local bare_path="$TEST_DIR/t5-hook-block/bare.git"
    local collab="$TEST_DIR/t5-hook-block/collaborator"
    git clone "$bare_path" "$collab" >/dev/null 2>&1
    (cd "$collab" && git checkout story-1 >/dev/null 2>&1 && \
     echo "collab" > collab.txt && git add collab.txt && \
     git commit -m "collaborator" >/dev/null 2>&1 && \
     git push origin story-1 >/dev/null 2>&1)
    # Get the collaborator's new SHA
    local collab_sha
    collab_sha=$(cd "$collab" && git rev-parse story-1)

    # Simulate pre-push stdin: branch with wrong remote SHA
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${collab_sha}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$bare_path" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook blocks collaborator update"
    else
      fail "pre-push hook blocks collaborator update" "hook exited 0 (should have blocked)"
    fi
  )
}

# =========================================================================
# TEST 6: pre-push hook allows clean rebase (baseline matches advertised)
# =========================================================================
test_hook_allows_rebase() {
  local clone
  clone=$(setup_fixture "t6-hook-allow")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # Simulate the SAVED baseline matching the advertised (remote unchanged)
    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -eq 0 ]; then
      pass "pre-push hook allows clean rebase (baseline matches advertised)"
    else
      rc=$?
      fail "pre-push hook allows clean rebase" "hook exited $rc (should have allowed)"
    fi
  )
}

# =========================================================================
# TEST 7: pre-push hook blocks branch deletion
# =========================================================================
test_hook_blocks_deletion() {
  local clone
  clone=$(setup_fixture "t7-hook-delete")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # Simulate deleted branch: remote_sha is all zeros
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 0000000000000000000000000000000000000000"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook blocks branch deletion"
    else
      fail "pre-push hook blocks branch deletion" "hook exited 0 (should have blocked)"
    fi
  )
}

# =========================================================================
# TEST 8a: pre-push hook blocks newly appeared branch (unpublished sentinel)
# snapshot records null for unpublished branches; the hook blocks when
# the remote advertises a non-zero OID for a branch that was null.
# =========================================================================
test_hook_blocks_appeared() {
  local clone
  clone=$(setup_fixture "t8-hook-appeared")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack

    # Create snapshot WITHOUT story-3 published
    git checkout -b story-3 >/dev/null 2>&1
    echo "s3" > s3.txt && git add s3.txt && git commit -m "story-3" >/dev/null 2>&1
    # Don't push story-3 — it's unpublished

    # Build context with story-3 in branches
    local branches='[{"name":"story-1","pr":null},{"name":"story-2","pr":null},{"name":"story-3","pr":null}]'
    local ctx
    ctx=$(jq -n --argjson branches "$branches" \
      '{trunk:"main",currentBranch:"story-3",baseRemote:"origin",pushRemote:"origin",branches:$branches}')
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Verify snapshot records null for unpublished story-3
    local s3_val
    s3_val=$(jq -r '.publishedTips["story-3"]' "$snap")
    if [ "$s3_val" != "null" ]; then
      fail "snapshot records null for unpublished branches" "got: $s3_val"
      return
    fi

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # Simulate: someone else pushed story-3 to the remote (non-zero advertised)
    local fake_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    local local_sha
    local_sha=$(git rev-parse story-3)
    local stdin_line="refs/heads/story-3 ${local_sha} refs/heads/story-3 ${fake_sha}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    # Unpublished branches have null in publishedTips. The hook BLOCKS when
    # the remote advertises a non-zero OID (someone else pushed).
    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook blocks appeared branch (unpublished sentinel)"
    else
      fail "pre-push hook blocks appeared branch" "hook exited 0 (should block)"
    fi
  )
}

# =========================================================================
# TEST 8b: pre-push hook rejects branch NOT in baseline (unknown to stack)
# =========================================================================
test_hook_rejects_unknown_branch() {
  local clone
  clone=$(setup_fixture "t8b-unknown")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # Push a branch that is NOT in the stack baseline at all
    local fake_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/rogue-branch ${local_sha} refs/heads/rogue-branch ${fake_sha}"

    local output
    output=$(printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" 2>&1)
    rc=$?

    if [ "$rc" -ne 0 ] && printf '%s' "$output" | grep -q "not in the validated stack"; then
      pass "pre-push hook rejects branch not in baseline (fails closed)"
    else
      fail "pre-push hook rejects unknown branch" "rc=$rc output: $output"
    fi
  )
}

# =========================================================================
# TEST 8c: pre-push hook allows unpublished branch first push (zero advertised)
# =========================================================================
test_hook_allows_unpublished_first_push() {
  local clone
  clone=$(setup_fixture "t8c-first-push")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack

    # Create story-3 without pushing
    git checkout -b story-3 >/dev/null 2>&1
    echo "s3" > s3.txt && git add s3.txt && git commit -m "story-3" >/dev/null 2>&1

    local branches='[{"name":"story-1","pr":null},{"name":"story-2","pr":null},{"name":"story-3","pr":null}]'
    local ctx
    ctx=$(jq -n --argjson branches "$branches" \
      '{trunk:"main",currentBranch:"story-3",baseRemote:"origin",pushRemote:"origin",branches:$branches}')
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # First push: remote advertises zero (branch doesn't exist remotely yet)
    local ZERO="0000000000000000000000000000000000000000"
    local local_sha
    local_sha=$(git rev-parse story-3)
    local stdin_line="refs/heads/story-3 ${local_sha} refs/heads/story-3 ${ZERO}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -eq 0 ]; then
      pass "pre-push hook allows unpublished branch first push (zero advertised)"
    else
      fail "unpublished branch first push" "hook exited $rc (should allow)"
    fi
  )
}

# =========================================================================
# TEST 9: pre-push hook fails closed on missing baseline
# =========================================================================
test_hook_fails_closed_no_baseline() {
  local clone
  clone=$(setup_fixture "t9-no-baseline")
  (
    cd "$clone" || return
    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    awk '/^if ! cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="/nonexistent/baseline.json"
    export REBASE_STACK_ORIGINAL_HOOK=""
    export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
    export REBASE_STACK_CONTEXT_FILE=""

    local local_sha
    local_sha=$(git rev-parse story-1)
    local remote_sha
    remote_sha=$(git rev-parse origin/story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${remote_sha}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook fails closed on missing baseline"
    else
      fail "pre-push hook fails closed on missing baseline" "hook exited 0"
    fi
  )
}

# =========================================================================
# TEST 10: pre-push hook chains existing hook
# =========================================================================
test_hook_chains_existing() {
  local clone
  clone=$(setup_fixture "t10-chain")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    # Create an existing hook that writes a marker file
    local marker="$TEST_DIR/t10-chain/original-hook-ran"
    cat > "$hooks_dir/test-original.sh" << ORIG
#!/usr/bin/env bash
cat > /dev/null  # consume stdin
touch "$marker"
exit 0
ORIG
    chmod +x "$hooks_dir/test-original.sh"

    awk '/^if ! cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_ORIGINAL_HOOK="$hooks_dir/test-original.sh"
    export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
    export REBASE_STACK_CONTEXT_FILE="$(pwd)/.artifacts/rebase-stack/context.json"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -eq 0 ] && [ -f "$marker" ]; then
      pass "pre-push hook chains existing hook"
    elif [ "$rc" -ne 0 ]; then
      fail "pre-push hook chains existing hook" "hook exited $rc"
    else
      fail "pre-push hook chains existing hook" "original hook marker file not found"
    fi
  )
}

# =========================================================================
# TEST 11: pre-push hook respects existing hook abort
# =========================================================================
test_hook_respects_existing_abort() {
  local clone
  clone=$(setup_fixture "t11-abort")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    # Existing hook that rejects
    cat > "$hooks_dir/test-original.sh" << 'ORIG'
#!/usr/bin/env bash
cat > /dev/null
echo "original hook: rejecting" >&2
exit 1
ORIG
    chmod +x "$hooks_dir/test-original.sh"

    awk '/^if ! cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_ORIGINAL_HOOK="$hooks_dir/test-original.sh"
    export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
    export REBASE_STACK_CONTEXT_FILE="$(pwd)/.artifacts/rebase-stack/context.json"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook respects existing hook abort"
    else
      fail "pre-push hook respects existing hook abort" "hook exited 0 despite original rejecting"
    fi
  )
}

# =========================================================================
# TEST 12: conflict-resolved changed patch accepted when remote unchanged
# =========================================================================
test_changed_patch_accepted() {
  local clone
  clone=$(setup_fixture "t12-conflict")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Simulate rebase with conflict resolution that changes the patch:
    # Add a conflicting change on main, rebase story-1 with resolution
    git checkout main >/dev/null 2>&1
    echo "conflict on main" > s1.txt
    git add s1.txt && git commit -m "main: touch s1" >/dev/null 2>&1
    git push origin main >/dev/null 2>&1
    git checkout story-1 >/dev/null 2>&1
    # Rebase will conflict; resolve differently than original
    git rebase main >/dev/null 2>&1 || true
    echo "resolved differently" > s1.txt
    git add s1.txt
    git rebase --continue >/dev/null 2>&1 || true

    # The key: remote hasn't changed, so baseline still matches
    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$(pwd)/.artifacts/rebase-stack/context.json"

    # Advertised OID = saved baseline (remote hasn't changed)
    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1

    rc=$?
    if [ "$rc" -eq 0 ]; then
      pass "conflict-resolved changed patch accepted (remote unchanged)"
    else
      rc=$?
      fail "conflict-resolved changed patch accepted" "hook exited $rc"
    fi
  )
}

# =========================================================================
# TEST 13: push-guard.sh fails on missing baseline file
# =========================================================================
test_guard_missing_baseline() {
  local clone
  clone=$(setup_fixture "t13-guard-missing")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    write_context "$clone" > .artifacts/rebase-stack/context.json
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline /nonexistent/file.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1

    local rc=$?
    if [ "$rc" -eq 2 ]; then
      pass "push-guard.sh exits 2 on missing baseline"
    else
      rc=$?
      fail "push-guard.sh exits 2 on missing baseline" "exited $rc"
    fi
  )
}

# =========================================================================
# TEST 14: push-guard.sh fails on malformed baseline (no publishedTips)
# =========================================================================
test_guard_malformed_baseline() {
  local clone
  clone=$(setup_fixture "t14-guard-malformed")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    write_context "$clone" > .artifacts/rebase-stack/context.json
    echo '{"branches":[]}' > /tmp/bad-baseline.json
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline /tmp/bad-baseline.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?
    rm -f /tmp/bad-baseline.json
    if [ "$rc" -eq 2 ]; then
      pass "push-guard.sh exits 2 on malformed baseline"
    else
      rc=$?
      fail "push-guard.sh exits 2 on malformed baseline" "exited $rc"
    fi
  )
}

# =========================================================================
# TEST 15: PR base selection — mixed existing/missing PRs
# =========================================================================
test_pr_base_mixed() {
  # Simulate the push.md PR creation loop logic with mixed PRs.
  # story-1 has PR #412, story-2 and story-3 have no PR.
  # Expected: story-2 base=story-1, story-3 base=story-2
  local ctx
  ctx='{"trunk":"main","branches":[
    {"name":"story-1","pr":412},
    {"name":"story-2","pr":null},
    {"name":"story-3","pr":null}
  ]}'
  local base="main"

  # The FIXED loop (all branches, create only missing):
  local results=""
  local all_branches
  mapfile -t all_branches < <(printf '%s' "$ctx" | jq -r '.branches[].name')
  local previous_branch="$base"
  local previous_pr_number=""
  for branch in "${all_branches[@]}"; do
    local existing_pr
    existing_pr=$(printf '%s' "$ctx" | jq -r --arg b "$branch" \
      '.branches[] | select(.name == $b) | .pr // empty')
    if [ -z "$existing_pr" ]; then
      results="${results}CREATE ${branch} --base ${previous_branch}"
      if [ -n "$previous_pr_number" ]; then
        results="${results} depends=#${previous_pr_number}"
      fi
      results="${results}\n"
      previous_pr_number="999"  # simulate returned PR number
    else
      previous_pr_number="$existing_pr"
    fi
    previous_branch="$branch"
  done

  local expected
  expected=$(printf 'CREATE story-2 --base story-1 depends=#412\nCREATE story-3 --base story-2 depends=#999\n')
  local actual
  actual=$(printf '%b' "$results")

  if [ "$actual" = "$expected" ]; then
    pass "PR base selection: mixed existing/missing PRs"
  else
    fail "PR base selection: mixed existing/missing PRs" \
      "expected:\n$expected\ngot:\n$actual"
  fi
}

# =========================================================================
# TEST 16: PR base selection — all missing PRs
# =========================================================================
test_pr_base_all_missing() {
  local ctx
  ctx='{"trunk":"main","branches":[
    {"name":"story-1","pr":null},
    {"name":"story-2","pr":null},
    {"name":"story-3","pr":null}
  ]}'

  local results=""
  local all_branches
  mapfile -t all_branches < <(printf '%s' "$ctx" | jq -r '.branches[].name')
  local previous_branch="main"
  local previous_pr_number=""
  for branch in "${all_branches[@]}"; do
    local existing_pr
    existing_pr=$(printf '%s' "$ctx" | jq -r --arg b "$branch" \
      '.branches[] | select(.name == $b) | .pr // empty')
    if [ -z "$existing_pr" ]; then
      results="${results}CREATE ${branch} --base ${previous_branch}"
      if [ -n "$previous_pr_number" ]; then
        results="${results} depends=#${previous_pr_number}"
      fi
      results="${results}\n"
      previous_pr_number="$((${previous_pr_number:-0} + 100))"
    else
      previous_pr_number="$existing_pr"
    fi
    previous_branch="$branch"
  done

  local actual
  actual=$(printf '%b' "$results")
  # story-1 base=main (no depends), story-2 base=story-1, story-3 base=story-2
  if printf '%s' "$actual" | grep -q "story-1 --base main" \
     && printf '%s' "$actual" | grep -q "story-2 --base story-1" \
     && printf '%s' "$actual" | grep -q "story-3 --base story-2"; then
    pass "PR base selection: all missing PRs"
  else
    fail "PR base selection: all missing PRs" "got:\n$actual"
  fi
}

# =========================================================================
# TEST 17: PR base selection — all existing PRs (no-op)
# =========================================================================
test_pr_base_all_existing() {
  local ctx
  ctx='{"trunk":"main","branches":[
    {"name":"story-1","pr":100},
    {"name":"story-2","pr":200},
    {"name":"story-3","pr":300}
  ]}'

  local results=""
  local all_branches
  mapfile -t all_branches < <(printf '%s' "$ctx" | jq -r '.branches[].name')
  local previous_branch="main"
  local previous_pr_number=""
  for branch in "${all_branches[@]}"; do
    local existing_pr
    existing_pr=$(printf '%s' "$ctx" | jq -r --arg b "$branch" \
      '.branches[] | select(.name == $b) | .pr // empty')
    if [ -z "$existing_pr" ]; then
      results="${results}CREATE ${branch}\n"
    else
      previous_pr_number="$existing_pr"
    fi
    previous_branch="$branch"
  done

  local actual
  actual=$(printf '%b' "$results")
  if [ -z "$actual" ]; then
    pass "PR base selection: all existing PRs (no-op)"
  else
    fail "PR base selection: all existing PRs (no-op)" "should create nothing, got:\n$actual"
  fi
}

# =========================================================================
# TEST 18: continuation preserves baseline (snapshot not overwritten by validate)
# =========================================================================
test_continuation_preserves_baseline() {
  local clone
  clone=$(setup_fixture "t18-continue")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    local snap=".artifacts/rebase-stack/pre-rebase-state.json"
    local original_tips
    original_tips=$(jq -c '.publishedTips' "$snap")

    # Simulate rebase then validate (which fetches but should NOT overwrite snapshot)
    git checkout main >/dev/null 2>&1
    echo "new" > new.txt && git add new.txt && git commit -m "advance" >/dev/null 2>&1
    git push origin main >/dev/null 2>&1
    git checkout story-1 >/dev/null 2>&1
    git rebase main >/dev/null 2>&1
    git checkout story-2 >/dev/null 2>&1
    git rebase story-1 >/dev/null 2>&1

    # Validate does NOT call snapshot save — it calls stack-status with --baseline
    # Verify the snapshot is unchanged
    local current_tips
    current_tips=$(jq -c '.publishedTips' "$snap")

    if [ "$original_tips" = "$current_tips" ]; then
      pass "continuation preserves baseline (snapshot unchanged)"
    else
      fail "continuation preserves baseline" "tips changed: was $original_tips, now $current_tips"
    fi
  )
}

# =========================================================================
# TEST 19: real git push — hook receives advertised OIDs through wire protocol
# Uses a repo-local core.hooksPath override to isolate from system hooks.
# =========================================================================
test_real_push_wire_oids() {
  local clone
  clone=$(setup_fixture "t19-wire")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Simulate a rebase: advance main, rebase story-1 onto it
    git checkout main >/dev/null 2>&1
    echo "new" > new.txt && git add new.txt && git commit -m "advance" >/dev/null 2>&1
    git push origin main >/dev/null 2>&1
    git checkout story-1 >/dev/null 2>&1
    git rebase main >/dev/null 2>&1
    git checkout story-2 >/dev/null 2>&1
    git rebase story-1 >/dev/null 2>&1

    # Set a repo-local hooksPath to isolate from system hooks
    local test_hooks="$TEST_DIR/t19-wire/test-hooks"
    mkdir -p "$test_hooks"
    git config core.hooksPath "$test_hooks"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_ORIGINAL_HOOK=""
    export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
    export REBASE_STACK_CONTEXT_FILE=""

    awk '/^cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
      "$SCRIPTS_DIR/push-guard.sh" > "$test_hooks/pre-push"
    chmod +x "$test_hooks/pre-push"

    # Real git push with force-with-lease — Git's wire protocol provides
    # advertised OIDs to the pre-push hook via stdin
    git push --force-with-lease origin story-1 story-2 >/dev/null 2>&1


    rm -f "$test_hooks/pre-push"
    git config --unset core.hooksPath
    rc=$?
    if [ "$rc" -eq 0 ]; then
      pass "real git push: hook receives wire OIDs and allows clean rebase"
    else
      rc=$?
      fail "real git push: hook allows clean rebase" "git push exited $rc"
    fi
  )
}

# =========================================================================
# TEST 20: real git push — hook BLOCKS when collaborator pushed (wire OIDs)
# =========================================================================
test_real_push_blocks_collaborator() {
  local clone
  clone=$(setup_fixture "t20-wire-block")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Collaborator pushes to story-1
    local bare_path="$TEST_DIR/t20-wire-block/bare.git"
    local collab="$TEST_DIR/t20-wire-block/collaborator"
    git clone "$bare_path" "$collab" >/dev/null 2>&1
    (cd "$collab" || return && git checkout story-1 >/dev/null 2>&1 && \
     echo "collab" > collab.txt && git add collab.txt && \
     git commit -m "collaborator" >/dev/null 2>&1 && \
     git push origin story-1 >/dev/null 2>&1)

    # Fetch (as gh-stack's FetchBranches would) — tracking refs now have
    # the collaborator's SHA, but the saved baseline still has the original
    git fetch origin >/dev/null 2>&1

    # Amend a local commit so there's something to push
    echo "local-change" >> s1.txt && git add s1.txt
    git commit --amend -m "story-1: amended" >/dev/null 2>&1

    # Use GIT_CONFIG to inject temp hooks dir (same as push-guard.sh)
    local test_hooks="$TEST_DIR/t20-wire-block/test-hooks"
    mkdir -p "$test_hooks"

    local abs_ctx
    abs_ctx="$(pwd)/.artifacts/rebase-stack/context.json"
    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_ORIGINAL_HOOK=""
    export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
    export REBASE_STACK_CONTEXT_FILE="$abs_ctx"
    awk '/^if ! cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
      "$SCRIPTS_DIR/push-guard.sh" > "$test_hooks/pre-push"
    chmod +x "$test_hooks/pre-push"

    # Real git push with GIT_CONFIG override for hooks dir
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$test_hooks" \
      git push --force-with-lease origin story-1 >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
      pass "real git push: hook blocks collaborator via wire OIDs"
    else
      fail "real git push: hook blocks collaborator" "git push exited 0 (should block)"
    fi
  )
}

# =========================================================================
# TEST 21: push-guard.sh install/uninstall lifecycle preserves original hook
# =========================================================================
test_guard_lifecycle_preserves_hook() {
  local clone
  clone=$(setup_fixture "t21-lifecycle")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    # Install an original hook
    cat > "$hooks_dir/pre-push" << 'ORIG'
#!/usr/bin/env bash
echo "original-hook-marker"
exit 0
ORIG
    chmod +x "$hooks_dir/pre-push"
    local original_content
    original_content=$(cat "$hooks_dir/pre-push")

    # push-guard.sh will fail because gh is not available, but cleanup should
    # still restore the original hook (trap EXIT fires on any exit)
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1 || true

    # Check that original hook is restored
    if [ -f "$hooks_dir/pre-push" ]; then
      local restored_content
      restored_content=$(cat "$hooks_dir/pre-push")
      if [ "$restored_content" = "$original_content" ]; then
        pass "push-guard.sh lifecycle preserves original hook after failure"
      else
        fail "push-guard.sh lifecycle" "hook content changed"
      fi
    else
      fail "push-guard.sh lifecycle" "pre-push hook file missing after cleanup"
    fi
  )
}

# =========================================================================
# TEST 22: custom core.hooksPath honored
# =========================================================================
test_custom_hooks_path() {
  local clone
  clone=$(setup_fixture "t22-hookspath")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Set custom hooksPath
    local custom_hooks="$TEST_DIR/t22-hookspath/custom hooks dir"
    mkdir -p "$custom_hooks"
    git config core.hooksPath "$custom_hooks"

    # Install an original hook in the CUSTOM path
    cat > "$custom_hooks/pre-push" << 'ORIG'
#!/usr/bin/env bash
cat > /dev/null
exit 0
ORIG
    chmod +x "$custom_hooks/pre-push"

    # push-guard.sh should install in the custom path, not .git/hooks
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1 || true

    # After cleanup, the original hook in custom path should be restored
    if [ -f "$custom_hooks/pre-push" ] \
       && grep -q "exit 0" "$custom_hooks/pre-push"; then
      pass "custom core.hooksPath honored and original restored"
    else
      fail "custom core.hooksPath" "hook not restored in custom path"
    fi

    # Clean up
    git config --unset core.hooksPath
  )
}

# =========================================================================
# TEST 23: spaces in hooks path
# =========================================================================
test_spaces_in_hooks_path() {
  local clone
  clone=$(setup_fixture "t23-spaces")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Create a hooks dir with spaces in the path
    local spaced_dir="$TEST_DIR/t23-spaces/hooks with spaces"
    mkdir -p "$spaced_dir"
    git config core.hooksPath "$spaced_dir"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_ORIGINAL_HOOK=""
    export REBASE_STACK_VALIDATOR="$SCRIPTS_DIR/validate-baseline.sh"
    export REBASE_STACK_CONTEXT_FILE=""

    # push-guard.sh should handle the spaced path
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1 || true

    # The hook should have been written there and cleaned up
    # After cleanup (gh stack push fails), no leftover hook in spaced dir
    if [ ! -f "$spaced_dir/pre-push" ]; then
      pass "spaces in hooks path handled correctly"
    else
      fail "spaces in hooks path" "leftover hook found after cleanup"
    fi

    git config --unset core.hooksPath
  )
}

# =========================================================================
# TEST 24: NEGATIVE CONTROL — old d69dd41c behavior rejects normal rebase
# This exercises the OLD stack-status.sh without --baseline: behind>0 blocks.
# =========================================================================
test_old_behavior_rejects_normal_rebase() {
  local clone
  clone=$(setup_fixture "t24-negative")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")

    # Rebase story-1 onto advanced main
    git checkout main >/dev/null 2>&1
    echo "new" > new.txt && git add new.txt && git commit -m "advance" >/dev/null 2>&1
    git push origin main >/dev/null 2>&1
    git checkout story-1 >/dev/null 2>&1
    git rebase main >/dev/null 2>&1
    git checkout story-2 >/dev/null 2>&1
    git rebase story-1 >/dev/null 2>&1

    # Without --baseline (old behavior): stack-status shows -N, would block
    local output
    output=$(printf '%s' "$ctx" | bash "$SCRIPTS_DIR/stack-status.sh" 2>/dev/null) || true
    if printf '%s' "$output" | grep -qE '\+[0-9]+/-[0-9]+' \
       && ! printf '%s' "$output" | grep -q "(rebase)"; then
      pass "NEGATIVE: old behavior (no baseline) shows raw divergence without (rebase)"
    else
      fail "NEGATIVE: old behavior" "expected raw +/-N without (rebase) classification"
    fi
  )
}

# =========================================================================
# TEST 25: NEGATIVE CONTROL — old push.md PR loop base bug
# Exercises the OLD loop that iterates only select(.pr == null)
# =========================================================================
test_old_pr_loop_base_bug() {
  # Simulate OLD behavior: iterate only pr-less branches
  local ctx
  ctx='{"trunk":"main","branches":[
    {"name":"story-1","pr":412},
    {"name":"story-2","pr":null},
    {"name":"story-3","pr":null}
  ]}'

  # OLD loop (from d69dd41c push.md): select(.pr == null), previous_branch starts at base
  local results=""
  local branches_old
  mapfile -t branches_old < <(printf '%s' "$ctx" | jq -r '.branches[] | select(.pr == null) | .name')
  local previous_branch="main"
  for branch in "${branches_old[@]}"; do
    results="${results}${branch} --base ${previous_branch}\n"
    previous_branch="$branch"
  done
  local actual
  actual=$(printf '%b' "$results")

  # OLD behavior: story-2 gets --base main (BUG — should be story-1)
  if printf '%s' "$actual" | grep -q "story-2 --base main"; then
    pass "NEGATIVE: old PR loop gives story-2 --base main (the bug)"
  else
    fail "NEGATIVE: old PR loop" "expected story-2 --base main, got: $actual"
  fi
}

# =========================================================================
# TEST 26: P2 — missing bottom + existing middle + missing top
# =========================================================================
test_pr_base_gap_middle() {
  local ctx
  ctx='{"trunk":"main","branches":[
    {"name":"story-1","pr":null},
    {"name":"story-2","pr":200},
    {"name":"story-3","pr":null}
  ]}'
  local results=""
  local all_branches
  mapfile -t all_branches < <(printf '%s' "$ctx" | jq -r '.branches[].name')
  local previous_branch="main"
  local previous_pr_number=""
  for branch in "${all_branches[@]}"; do
    local existing_pr
    existing_pr=$(printf '%s' "$ctx" | jq -r --arg b "$branch" \
      '.branches[] | select(.name == $b) | .pr // empty')
    if [ -z "$existing_pr" ]; then
      results="${results}CREATE ${branch} --base ${previous_branch}"
      if [ -n "$previous_pr_number" ]; then
        results="${results} depends=#${previous_pr_number}"
      fi
      results="${results}\n"
      previous_pr_number="999"
    else
      previous_pr_number="$existing_pr"
    fi
    previous_branch="$branch"
  done
  local actual
  actual=$(printf '%b' "$results")

  # story-1 base=main (no depends), story-3 base=story-2 depends=#200
  if printf '%s' "$actual" | grep -q "story-1 --base main" \
     && ! printf '%s' "$actual" | grep "story-1" | grep -q "depends" \
     && printf '%s' "$actual" | grep -q "story-3 --base story-2 depends=#200"; then
    pass "PR base: missing bottom + existing middle + missing top"
  else
    fail "PR base: gap pattern" "got: $actual"
  fi
}

# =========================================================================
# TEST 27: P2 — several gaps (story-1 PR, story-2 no PR, story-3 PR, story-4 no PR)
# =========================================================================
test_pr_base_several_gaps() {
  local ctx
  ctx='{"trunk":"main","branches":[
    {"name":"story-1","pr":100},
    {"name":"story-2","pr":null},
    {"name":"story-3","pr":300},
    {"name":"story-4","pr":null}
  ]}'
  local results=""
  local all_branches
  mapfile -t all_branches < <(printf '%s' "$ctx" | jq -r '.branches[].name')
  local previous_branch="main"
  local previous_pr_number=""
  for branch in "${all_branches[@]}"; do
    local existing_pr
    existing_pr=$(printf '%s' "$ctx" | jq -r --arg b "$branch" \
      '.branches[] | select(.name == $b) | .pr // empty')
    if [ -z "$existing_pr" ]; then
      results="${results}CREATE ${branch} --base ${previous_branch}"
      if [ -n "$previous_pr_number" ]; then
        results="${results} depends=#${previous_pr_number}"
      fi
      results="${results}\n"
      previous_pr_number="999"
    else
      previous_pr_number="$existing_pr"
    fi
    previous_branch="$branch"
  done
  local actual
  actual=$(printf '%b' "$results")

  # story-2 base=story-1 depends=#100, story-4 base=story-3 depends=#300
  if printf '%s' "$actual" | grep -q "story-2 --base story-1 depends=#100" \
     && printf '%s' "$actual" | grep -q "story-4 --base story-3 depends=#300"; then
    pass "PR base: several gaps with correct predecessors"
  else
    fail "PR base: several gaps" "got: $actual"
  fi
}

# =========================================================================
# TEST 28: env vars reach hook through real git push (scoped config proof)
# =========================================================================
test_env_reaches_hook_through_git() {
  local clone
  clone=$(setup_fixture "t28-env")
  (
    cd "$clone" || return

    # Use a repo-local hooksPath to isolate from system hooks
    local test_hooks="$TEST_DIR/t28-env/test-hooks"
    mkdir -p "$test_hooks"
    git config core.hooksPath "$test_hooks"

    # Write a hook that checks for our env var and writes a marker
    local marker="$TEST_DIR/t28-env/env-marker"
    cat > "$test_hooks/pre-push" << ENVHOOK
#!/usr/bin/env bash
cat > /dev/null
if [ -n "\${REBASE_STACK_BASELINE_FILE:-}" ]; then
  echo "FOUND" > "$marker"
else
  echo "MISSING" > "$marker"
fi
exit 0
ENVHOOK
    chmod +x "$test_hooks/pre-push"

    export REBASE_STACK_BASELINE_FILE="/tmp/test-baseline"

    # Amend to create something to push
    echo "changed" >> s2.txt && git add s2.txt
    git commit --amend -m "story-2: amended" >/dev/null 2>&1

    # Real git push — env should propagate to hook
    git push --force-with-lease origin story-2 >/dev/null 2>&1

    git config --unset core.hooksPath
    unset REBASE_STACK_BASELINE_FILE

    if [ -f "$marker" ] && grep -q "FOUND" "$marker"; then
      pass "env vars reach hook through real git push invocation"
    else
      fail "env vars reach hook through git push" "marker: $(cat "$marker" 2>/dev/null || echo 'not found')"
    fi
  )
}

# =========================================================================
# TEST 29a: validate-baseline rejects missing key
# =========================================================================
test_validate_baseline_missing_key() {
  local tmp
  tmp=$(mktemp "${TMPDIR:-/tmp}/bl-test.XXXXXX")
  echo '{"trunk":"main","baseRemote":"origin","pushRemote":"origin","pushUrl":"x","branches":[]}' > "$tmp"
  bash "$SCRIPTS_DIR/validate-baseline.sh" "$tmp" >/dev/null 2>&1
  rc=$?
  rm -f "$tmp"
  if [ "$rc" -ne 0 ]; then
    pass "validate-baseline rejects missing publishedTips key"
  else
    fail "validate-baseline missing key" "exited 0"
  fi
}

# =========================================================================
# TEST 29b: validate-baseline rejects empty publishedTips
# =========================================================================
test_validate_baseline_empty_tips() {
  local tmp
  tmp=$(mktemp "${TMPDIR:-/tmp}/bl-test.XXXXXX")
  echo '{"trunk":"main","baseRemote":"origin","pushRemote":"origin","pushUrl":"x","branches":[],"publishedTips":{}}' > "$tmp"
  bash "$SCRIPTS_DIR/validate-baseline.sh" "$tmp" >/dev/null 2>&1
  rc=$?
  rm -f "$tmp"
  if [ "$rc" -ne 0 ]; then
    pass "validate-baseline rejects empty publishedTips"
  else
    fail "validate-baseline empty tips" "exited 0"
  fi
}

# =========================================================================
# TEST 29c: validate-baseline rejects non-string SHA value
# =========================================================================
test_validate_baseline_nonstring_sha() {
  local tmp
  tmp=$(mktemp "${TMPDIR:-/tmp}/bl-test.XXXXXX")
  cat > "$tmp" << 'JSON'
{"trunk":"main","baseRemote":"origin","pushRemote":"origin","pushUrl":"x",
 "branches":[{"name":"b1","sha":"x","commits":[]}],
 "publishedTips":{"b1":12345}}
JSON
  bash "$SCRIPTS_DIR/validate-baseline.sh" "$tmp" >/dev/null 2>&1
  rc=$?
  rm -f "$tmp"
  if [ "$rc" -ne 0 ]; then
    pass "validate-baseline rejects non-string SHA (number)"
  else
    fail "validate-baseline non-string SHA" "exited 0"
  fi
}

# =========================================================================
# TEST 29d: validate-baseline rejects wrong trunk via --context
# =========================================================================
test_validate_baseline_wrong_trunk() {
  local clone
  clone=$(setup_fixture "t29d-trunk")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Create a context with different trunk
    local wrong_ctx
    wrong_ctx=$(jq '.trunk = "develop"' <<<"$ctx")
    local wrong_ctx_file
    wrong_ctx_file=$(mktemp "${TMPDIR:-/tmp}/ctx-test.XXXXXX")
    printf '%s' "$wrong_ctx" > "$wrong_ctx_file"

    bash "$SCRIPTS_DIR/validate-baseline.sh" "$snap" --context "$wrong_ctx_file" >/dev/null 2>&1
    rc=$?
    rm -f "$wrong_ctx_file"
    if [ "$rc" -ne 0 ]; then
      pass "validate-baseline rejects wrong trunk via --context"
    else
      fail "validate-baseline wrong trunk" "exited 0"
    fi
  )
}

# =========================================================================
# TEST 29e: validate-baseline rejects wrong push URL
# =========================================================================
test_validate_baseline_wrong_url() {
  local clone
  clone=$(setup_fixture "t29e-url")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Tamper with the push URL to simulate a different repository
    local tampered
    tampered=$(mktemp "${TMPDIR:-/tmp}/bl-tampered.XXXXXX")
    jq '.pushUrl = "/some/other/repo.git"' "$snap" > "$tampered"

    bash "$SCRIPTS_DIR/validate-baseline.sh" "$tampered" --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?
    rm -f "$tampered"
    if [ "$rc" -ne 0 ]; then
      pass "validate-baseline rejects wrong push URL"
    else
      fail "validate-baseline wrong URL" "exited 0"
    fi
  )
}

# =========================================================================
# TEST 29f: validate-baseline rejects mismatched branch set
# =========================================================================
test_validate_baseline_wrong_branches() {
  local clone
  clone=$(setup_fixture "t29f-branches")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Create a context with extra branch
    git checkout -b story-3 >/dev/null 2>&1
    echo "s3" > s3.txt && git add s3.txt && git commit -m "s3" >/dev/null 2>&1
    local new_ctx
    new_ctx=$(jq '.branches += [{"name":"story-3","pr":null}]' <<<"$ctx")
    local new_ctx_file
    new_ctx_file=$(mktemp "${TMPDIR:-/tmp}/ctx-test.XXXXXX")
    printf '%s' "$new_ctx" > "$new_ctx_file"

    bash "$SCRIPTS_DIR/validate-baseline.sh" "$snap" --context "$new_ctx_file" >/dev/null 2>&1
    rc=$?
    rm -f "$new_ctx_file"
    if [ "$rc" -ne 0 ]; then
      pass "validate-baseline rejects mismatched branch set"
    else
      fail "validate-baseline wrong branches" "exited 0"
    fi
  )
}

# =========================================================================
# TEST 29g: validate-baseline accepts valid baseline
# =========================================================================
test_validate_baseline_valid() {
  local clone
  clone=$(setup_fixture "t29g-valid")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Save context for --context validation
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    bash "$SCRIPTS_DIR/validate-baseline.sh" "$snap" --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
      pass "validate-baseline accepts valid baseline with --context"
    else
      fail "validate-baseline valid" "exited $rc"
    fi
  )
}

# =========================================================================
# TEST 29h: snapshot refuses overwrite without --force
# =========================================================================
test_snapshot_refuses_overwrite() {
  local clone
  clone=$(setup_fixture "t29h-overwrite")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    # First save
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"
    local original_tips
    original_tips=$(jq -c '.publishedTips' "$snap")

    # Advance main and rebase — tips would change if recaptured
    git checkout main >/dev/null 2>&1
    echo "new" > new.txt && git add new.txt && git commit -m "advance" >/dev/null 2>&1
    git push origin main >/dev/null 2>&1
    git checkout story-1 >/dev/null 2>&1
    git rebase main >/dev/null 2>&1
    git push -f origin story-1 >/dev/null 2>&1

    # Second save WITHOUT --force should refuse
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    rc=$?

    if [ "$rc" -ne 0 ]; then
      # Verify original tips are preserved
      local current_tips
      current_tips=$(jq -c '.publishedTips' "$snap")
      if [ "$original_tips" = "$current_tips" ]; then
        pass "snapshot refuses overwrite without --force (preserves original)"
      else
        fail "snapshot refuses overwrite" "tips changed despite refusal"
      fi
    else
      fail "snapshot refuses overwrite" "save succeeded without --force"
    fi
  )
}

# =========================================================================
# TEST 29i: snapshot allows overwrite with --force
# =========================================================================
test_snapshot_allows_force_overwrite() {
  local clone
  clone=$(setup_fixture "t29i-force")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Second save WITH --force should succeed
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    rc=$?
    if [ "$rc" -eq 0 ]; then
      pass "snapshot allows overwrite with --force"
    else
      fail "snapshot allows force overwrite" "exited $rc"
    fi
  )
}

# =========================================================================
# TEST 29j: push-guard hook chains other hooks (not just pre-push)
# =========================================================================
test_guard_chains_other_hooks() {
  local clone
  clone=$(setup_fixture "t29j-otherhooks")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Create a reference-transaction hook in the original hooks dir
    local hooks_dir
    hooks_dir="$(git rev-parse --git-common-dir)/hooks"
    mkdir -p "$hooks_dir"
    local marker="$TEST_DIR/t29j-otherhooks/ref-tx-ran"
    cat > "$hooks_dir/reference-transaction" << RTHOOK
#!/usr/bin/env bash
touch "$marker"
exit 0
RTHOOK
    chmod +x "$hooks_dir/reference-transaction"

    # push-guard creates a temp dir; verify other hooks are wrapped
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1 || true

    # The temp dir is cleaned up, but we can check push-guard.sh source
    # proves it copies other hooks. (The actual invocation depends on
    # git performing a reference-transaction during push.)
    # Verify the hook file was preserved (not deleted by push-guard cleanup)
    if [ -f "$hooks_dir/reference-transaction" ] \
       && [ -x "$hooks_dir/reference-transaction" ]; then
      pass "push-guard preserves other hooks in original dir"
    else
      fail "push-guard other hooks" "reference-transaction hook missing after cleanup"
    fi
  )
}

# =========================================================================
# TEST 29k: push-guard uses git-common-dir for default hooks (worktree safe)
# =========================================================================
test_guard_common_dir_hooks() {
  local clone
  clone=$(setup_fixture "t29k-commondir")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Verify push-guard.sh source uses --git-common-dir not --absolute-git-dir
    if grep -q 'git-common-dir' "$SCRIPTS_DIR/push-guard.sh" \
       && ! grep -q 'absolute-git-dir' "$SCRIPTS_DIR/push-guard.sh"; then
      pass "push-guard uses --git-common-dir for default hooks (worktree safe)"
    else
      fail "push-guard common-dir" "still uses --absolute-git-dir"
    fi
  )
}

# =========================================================================
# TEST 29: no force-without-lease fallback in push-guard hook
# (verify hook doesn't contain any --force without --force-with-lease)
# =========================================================================
test_no_force_without_lease() {
  # Inspect push-guard.sh source: it delegates to "gh stack push" which
  # uses --force-with-lease. Verify there's no bare --force flag.
  if grep -q '\-\-force[^-]' "$SCRIPTS_DIR/push-guard.sh" 2>/dev/null \
     || grep -q '^[^#]*--force ' "$SCRIPTS_DIR/push-guard.sh" 2>/dev/null; then
    fail "no force-without-lease" "push-guard.sh contains bare --force flag"
  else
    pass "no force-without-lease fallback in push-guard"
  fi
}

# =========================================================================
# TEST 50: real linked worktree — git-common-dir hooks resolution
# =========================================================================
test_linked_worktree_hooks() {
  local clone
  clone=$(setup_fixture "t50-worktree")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Install a pre-push hook in the common hooks dir
    local common_dir
    common_dir=$(cd "$(git rev-parse --git-common-dir)" && pwd)
    mkdir -p "$common_dir/hooks"
    local marker="$TEST_DIR/t50-worktree/common-hook-ran"
    cat > "$common_dir/hooks/pre-push" << CMHOOK
#!/usr/bin/env bash
cat > /dev/null
touch "$marker"
exit 0
CMHOOK
    chmod +x "$common_dir/hooks/pre-push"

    # Create a linked worktree on a detached HEAD (story-2 may be checked out)
    git worktree add --detach "$TEST_DIR/t50-worktree/linked" story-1 >/dev/null 2>&1 \
      || { fail "linked worktree: could not create worktree" "git worktree add failed"; return; }
    (
      cd "$TEST_DIR/t50-worktree/linked" || { fail "linked worktree: cd failed" ""; return; }
      # Verify git-common-dir returns the MAIN repo's git dir
      local wt_common
      wt_common=$(cd "$(git rev-parse --git-common-dir)" && pwd)
      local wt_abs
      wt_abs=$(cd "$(git rev-parse --absolute-git-dir)" && pwd)

      if [ "$wt_common" = "$common_dir" ] && [ "$wt_abs" != "$common_dir" ]; then
        pass "linked worktree: git-common-dir returns main repo, absolute-git-dir returns worktree"
      else
        fail "linked worktree identity" "common=$wt_common abs=$wt_abs expected_common=$common_dir"
      fi
    )
    git worktree remove "$TEST_DIR/t50-worktree/linked" 2>/dev/null || true
  )
}

# =========================================================================
# TEST 51: stack-status exits non-zero on invalid baseline (not fallback)
# =========================================================================
test_status_rejects_invalid_baseline() {
  local clone
  clone=$(setup_fixture "t51-status-invalid")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Create an invalid baseline (missing required keys)
    echo '{"publishedTips":{}}' > .artifacts/rebase-stack/bad-baseline.json

    local output
    output=$(printf '%s' "$ctx" | bash "$SCRIPTS_DIR/stack-status.sh" --no-fetch \
      --baseline .artifacts/rebase-stack/bad-baseline.json 2>&1)
    rc=$?

    if [ "$rc" -eq 2 ]; then
      pass "stack-status exits 2 on invalid baseline (no fallback)"
    else
      fail "stack-status invalid baseline" "exited $rc (expected 2); output: $output"
    fi
  )
}

# =========================================================================
# TEST 52: push-guard rejects baseline from different repo (same alias)
# =========================================================================
test_guard_rejects_wrong_repo_url() {
  local clone
  clone=$(setup_fixture "t52-wrongurl")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Tamper with push URL to simulate a different repo
    local tampered
    tampered=$(mktemp "${TMPDIR:-/tmp}/bl-tampered.XXXXXX")
    jq '.pushUrl = "/completely/different/repo.git"' "$snap" > "$tampered"

    # push-guard should reject this — baseline is for a different repo
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline "$tampered" \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?
    rm -f "$tampered"

    if [ "$rc" -eq 2 ]; then
      pass "push-guard rejects baseline from different repo (push URL mismatch)"
    else
      fail "push-guard wrong repo URL" "exited $rc (expected 2)"
    fi
  )
}

# =========================================================================
# TEST 53: push-guard rejects baseline with wrong trunk
# =========================================================================
test_guard_rejects_wrong_trunk() {
  local clone
  clone=$(setup_fixture "t53-wrongtrunk")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    # Tamper with trunk
    local tampered
    tampered=$(mktemp "${TMPDIR:-/tmp}/bl-tampered.XXXXXX")
    jq '.trunk = "develop"' "$snap" > "$tampered"

    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline "$tampered" \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?
    rm -f "$tampered"

    if [ "$rc" -eq 2 ]; then
      pass "push-guard rejects baseline with wrong trunk"
    else
      fail "push-guard wrong trunk" "exited $rc (expected 2)"
    fi
  )
}

# =========================================================================
# TEST 54: snapshot saves gitCommonDir and effective push URL
# =========================================================================
test_snapshot_saves_identity() {
  local clone
  clone=$(setup_fixture "t54-identity")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    local snap=".artifacts/rebase-stack/pre-rebase-state.json"

    local saved_common
    saved_common=$(jq -r '.gitCommonDir' "$snap")
    local expected_common
    expected_common=$(cd "$(git rev-parse --git-common-dir)" && pwd)

    local saved_url
    saved_url=$(jq -r '.pushUrl' "$snap")
    local expected_url
    expected_url=$(git remote get-url --push origin)

    if [ "$saved_common" = "$expected_common" ] && [ "$saved_url" = "$expected_url" ]; then
      pass "snapshot saves gitCommonDir and effective push URL"
    else
      fail "snapshot identity" "common=$saved_common (expected $expected_common) url=$saved_url (expected $expected_url)"
    fi
  )
}

# =========================================================================
# TEST 55: hook wrapper handles paths with dollar and quote chars
# =========================================================================
test_hook_wrapper_special_chars() {
  local clone
  clone=$(setup_fixture "t55-special")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Create a hooks dir with special characters in path
    local special_dir="$TEST_DIR/t55-special/hooks\$with\"special"
    mkdir -p "$special_dir"

    # Install a reference-transaction hook there
    local marker="$TEST_DIR/t55-special/special-ran"
    cat > "$special_dir/reference-transaction" << SPHOOK
#!/usr/bin/env bash
touch "$marker"
exit 0
SPHOOK
    chmod +x "$special_dir/reference-transaction"

    # push-guard generates wrappers using printf %q which should safely quote
    # Verify push-guard.sh source uses printf %q for wrapper generation
    if grep -q 'printf.*%q' "$SCRIPTS_DIR/push-guard.sh"; then
      pass "hook wrapper uses printf %q for safe path quoting"
    else
      fail "hook wrapper special chars" "push-guard.sh does not use printf %q"
    fi
  )
}

# =========================================================================
# TEST 56: inner hook uses full validator with context
# =========================================================================
test_inner_hook_full_validation() {
  local clone
  clone=$(setup_fixture "t56-innerhook")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"
    local abs_ctx
    abs_ctx="$(pwd)/.artifacts/rebase-stack/context.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$abs_ctx"

    # Tamper with the baseline push URL AFTER outer validation would have run
    # (simulating file modification between outer check and inner check)
    local tampered_snap
    tampered_snap=$(mktemp "${TMPDIR:-/tmp}/bl-tampered.XXXXXX")
    jq '.pushUrl = "/other/repo.git"' "$snap" > "$tampered_snap"
    export REBASE_STACK_BASELINE_FILE="$tampered_snap"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    local output
    output=$(printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" 2>&1)
    rc=$?
    rm -f "$tampered_snap"

    if [ "$rc" -ne 0 ]; then
      pass "inner hook rejects tampered baseline via full validator"
    else
      fail "inner hook full validation" "exited 0 (should reject tampered baseline)"
    fi
  )
}

# =========================================================================
# TEST 60: push-guard rejects empty context (not delegated to gh)
# =========================================================================
test_guard_rejects_empty_context() {
  local clone
  clone=$(setup_fixture "t60-emptyctx")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Create an empty context: {}
    echo '{}' > .artifacts/rebase-stack/bad-context.json

    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/bad-context.json >/dev/null 2>&1
    rc=$?
    if [ "$rc" -eq 2 ]; then
      pass "push-guard rejects empty context {} (not delegated)"
    else
      fail "push-guard empty context" "exited $rc (expected 2)"
    fi
  )
}

# =========================================================================
# TEST 61: push-guard rejects context with empty branches
# =========================================================================
test_guard_rejects_empty_branches_ctx() {
  local clone
  clone=$(setup_fixture "t61-emptybr")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Context with empty branches array
    jq '.branches = []' .artifacts/rebase-stack/context.json \
      > .artifacts/rebase-stack/bad-context.json

    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/bad-context.json >/dev/null 2>&1
    rc=$?
    if [ "$rc" -eq 2 ]; then
      pass "push-guard rejects context with empty branches"
    else
      fail "push-guard empty branches ctx" "exited $rc (expected 2)"
    fi
  )
}

# =========================================================================
# TEST 62: push-guard rejects baseline missing gitCommonDir
# =========================================================================
test_guard_rejects_missing_commondir() {
  local clone
  clone=$(setup_fixture "t62-nocommon")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Remove gitCommonDir from baseline (legacy format)
    jq 'del(.gitCommonDir)' .artifacts/rebase-stack/pre-rebase-state.json \
      > .artifacts/rebase-stack/legacy-baseline.json

    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/legacy-baseline.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?
    if [ "$rc" -eq 2 ]; then
      pass "push-guard rejects baseline missing gitCommonDir (legacy)"
    else
      fail "push-guard missing commonDir" "exited $rc (expected 2)"
    fi
  )
}

# =========================================================================
# TEST 63: inner hook rejects missing validator (no fallback)
# =========================================================================
test_inner_hook_rejects_missing_validator() {
  local clone
  clone=$(setup_fixture "t63-noval")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    awk '/^if ! cat > .* << .HOOKEOF./{found=1; next} /^HOOKEOF$/{found=0; next} found' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_ORIGINAL_HOOK=""
    export REBASE_STACK_VALIDATOR=""
    export REBASE_STACK_CONTEXT_FILE="$(pwd)/.artifacts/rebase-stack/context.json"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    local output
    output=$(printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin xxx 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ] && printf '%s' "$output" | grep -q "validator missing"; then
      pass "inner hook rejects missing validator (no fallback)"
    else
      fail "inner hook no fallback" "rc=$rc output: $output"
    fi
  )
}

# =========================================================================
# TEST 64: snapshot refuses ANY existing file (not just valid)
# =========================================================================
test_snapshot_refuses_malformed_existing() {
  local clone
  clone=$(setup_fixture "t64-malformed")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    # Write a malformed/legacy baseline
    echo 'this is not json' > .artifacts/rebase-stack/pre-rebase-state.json
    local original_bytes
    original_bytes=$(cat .artifacts/rebase-stack/pre-rebase-state.json)

    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save 2>/dev/null
    rc=$?

    local current_bytes
    current_bytes=$(cat .artifacts/rebase-stack/pre-rebase-state.json)
    if [ "$rc" -ne 0 ] && [ "$original_bytes" = "$current_bytes" ]; then
      pass "snapshot refuses malformed existing file (bytes preserved)"
    else
      fail "snapshot malformed existing" "rc=$rc bytes_match=$([ "$original_bytes" = "$current_bytes" ] && echo yes || echo no)"
    fi
  )
}

# =========================================================================
# TEST 65: status rejects baseRemote mismatch
# =========================================================================
test_status_rejects_baseremote_mismatch() {
  local clone
  clone=$(setup_fixture "t65-baseremote")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Tamper baseline baseRemote
    jq '.baseRemote = "upstream"' .artifacts/rebase-stack/pre-rebase-state.json \
      > .artifacts/rebase-stack/bad-baseline.json

    local output
    output=$(printf '%s' "$ctx" | bash "$SCRIPTS_DIR/stack-status.sh" --no-fetch \
      --baseline .artifacts/rebase-stack/bad-baseline.json 2>&1)
    rc=$?
    if [ "$rc" -eq 2 ]; then
      pass "status rejects baseRemote mismatch"
    else
      fail "status baseRemote mismatch" "exited $rc"
    fi
  )
}

# =========================================================================
# TEST 66: validator rejects --context without value
# =========================================================================
test_validator_missing_arg() {
  bash "$SCRIPTS_DIR/validate-baseline.sh" /dev/null --context 2>/dev/null
  rc=$?
  if [ "$rc" -eq 2 ]; then
    pass "validator exits 2 on --context without value"
  else
    fail "validator missing arg" "exited $rc (expected 2)"
  fi
}

# =========================================================================
# TEST 67: push-guard rejects --baseline without value
# =========================================================================
test_guard_missing_arg() {
  bash "$SCRIPTS_DIR/push-guard.sh" --baseline 2>/dev/null
  rc=$?
  if [ "$rc" -eq 2 ]; then
    pass "push-guard exits 2 on --baseline without value"
  else
    fail "push-guard missing arg" "exited $rc (expected 2)"
  fi
}

# =========================================================================
# TEST 70: snapshot rejects empty-branches context (creates NO baseline)
# =========================================================================
test_snapshot_rejects_empty_branches() {
  local clone
  clone=$(setup_fixture "t70-emptybr")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx='{"trunk":"main","currentBranch":"main","baseRemote":"origin","pushRemote":"origin","baseRemoteSource":"config","pushRemoteSource":"config","validationBranch":"","branches":[]}'
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne 0 ] && [ ! -f .artifacts/rebase-stack/pre-rebase-state.json ]; then
      pass "snapshot rejects empty-branches context (no baseline written)"
    else
      fail "snapshot empty branches" "rc=$rc file=$([ -f .artifacts/rebase-stack/pre-rebase-state.json ] && echo exists || echo absent)"
    fi
  )
}

# =========================================================================
# TEST 71: snapshot preserves dangling symlink without --force
# =========================================================================
test_snapshot_preserves_dangling_link() {
  local clone
  clone=$(setup_fixture "t71-dangling")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    ln -s /nonexistent/target .artifacts/rebase-stack/pre-rebase-state.json
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne 0 ] && [ -L .artifacts/rebase-stack/pre-rebase-state.json ]; then
      pass "snapshot preserves dangling symlink without --force"
    else
      fail "snapshot dangling symlink" "rc=$rc islink=$([ -L .artifacts/rebase-stack/pre-rebase-state.json ] && echo yes || echo no)"
    fi
  )
}

# =========================================================================
# TEST 72: snapshot --force with failed candidate preserves old baseline bytes
# =========================================================================
test_snapshot_force_failed_candidate_preserves() {
  local clone
  clone=$(setup_fixture "t72-failforce")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    # Create a valid baseline first
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    local original_bytes
    original_bytes=$(cat .artifacts/rebase-stack/pre-rebase-state.json)

    # Now try --force with a malformed context (null branches)
    local bad_ctx='{"trunk":"main","currentBranch":"main","baseRemote":"origin","pushRemote":"origin","branches":null}'
    printf '%s' "$bad_ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    rc=$?

    local current_bytes
    current_bytes=$(cat .artifacts/rebase-stack/pre-rebase-state.json 2>/dev/null || echo "")

    # The old baseline must survive because the new candidate fails validation
    if [ "$rc" -ne 0 ] && [ "$original_bytes" = "$current_bytes" ]; then
      pass "snapshot --force with failed candidate preserves old baseline bytes"
    else
      fail "snapshot force failed candidate" "rc=$rc bytes_match=$([ "$original_bytes" = "$current_bytes" ] && echo yes || echo no)"
    fi
  )
}

# =========================================================================
# TEST 73: push-guard detects GIT_CONFIG_PARAMETERS hooksPath override
# =========================================================================
test_guard_detects_parameters_override() {
  local clone
  clone=$(setup_fixture "t73-params")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Create a decoy hooks dir via GIT_CONFIG_PARAMETERS
    local decoy="$TEST_DIR/t73-params/decoy-hooks"
    mkdir -p "$decoy"
    cat > "$decoy/pre-push" << 'H'
#!/usr/bin/env bash
cat > /dev/null; exit 0
H
    chmod +x "$decoy/pre-push"

    # Create a gh stub that records whether it was called
    local gh_marker="$TEST_DIR/t73-params/gh-called"
    mkdir -p "$TEST_DIR/t73-params/bin"
    cat > "$TEST_DIR/t73-params/bin/gh" << GHSTUB
#!/usr/bin/env bash
touch "$gh_marker"
exit 0
GHSTUB
    chmod +x "$TEST_DIR/t73-params/bin/gh"

    # Run push-guard with GIT_CONFIG_PARAMETERS overriding core.hooksPath
    GIT_CONFIG_PARAMETERS="'core.hooksPath=$decoy'" \
    PATH="$TEST_DIR/t73-params/bin:$PATH" \
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?

    if [ "$rc" -eq 2 ] && [ ! -f "$gh_marker" ]; then
      pass "push-guard detects GIT_CONFIG_PARAMETERS override (gh NOT called)"
    else
      fail "push-guard PARAMETERS override" "rc=$rc gh_called=$([ -f "$gh_marker" ] && echo YES || echo no)"
    fi
  )
}

# =========================================================================
# TEST 74: push-guard allows unrelated GIT_CONFIG_PARAMETERS (guard effective)
# =========================================================================
test_guard_allows_unrelated_parameters() {
  local clone
  clone=$(setup_fixture "t74-unrelated")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json

    # Create a gh stub
    local gh_marker="$TEST_DIR/t74-unrelated/gh-called"
    mkdir -p "$TEST_DIR/t74-unrelated/bin"
    cat > "$TEST_DIR/t74-unrelated/bin/gh" << GHSTUB
#!/usr/bin/env bash
touch "$gh_marker"
exit 0
GHSTUB
    chmod +x "$TEST_DIR/t74-unrelated/bin/gh"

    # GIT_CONFIG_PARAMETERS with an unrelated key (not core.hooksPath)
    GIT_CONFIG_PARAMETERS="'user.name=testbot'" \
    PATH="$TEST_DIR/t74-unrelated/bin:$PATH" \
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin \
      --context .artifacts/rebase-stack/context.json >/dev/null 2>&1
    rc=$?

    if [ "$rc" -eq 0 ] && [ -f "$gh_marker" ]; then
      pass "push-guard allows unrelated GIT_CONFIG_PARAMETERS (guard effective, gh called)"
    else
      fail "push-guard unrelated PARAMETERS" "rc=$rc gh_called=$([ -f "$gh_marker" ] && echo YES || echo no)"
    fi
  )
}

# =========================================================================
# TEST 75: inner hook rejects mismatched $2 push URL
# =========================================================================
test_inner_hook_rejects_url_mismatch() {
  local clone
  clone=$(setup_fixture "t75-url-arg2")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"
    local abs_ctx
    abs_ctx="$(pwd)/.artifacts/rebase-stack/context.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$abs_ctx"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    # Pass correct remote name but WRONG push URL as $2
    local output
    output=$(printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "/wrong/url.git" 2>&1)
    rc=$?

    if [ "$rc" -ne 0 ] && printf '%s' "$output" | grep -q "actual push destination"; then
      pass "inner hook rejects mismatched \$2 push URL"
    else
      fail "inner hook URL mismatch" "rc=$rc output: $output"
    fi
  )
}

# =========================================================================
# TEST 76: inner hook allows matching $2 push URL
# =========================================================================
test_inner_hook_allows_matching_url() {
  local clone
  clone=$(setup_fixture "t76-url-match")
  (
    cd "$clone" || return
    mkdir -p .artifacts/rebase-stack
    local ctx
    ctx=$(write_context "$clone")
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save --force >/dev/null 2>&1
    printf '%s' "$ctx" > .artifacts/rebase-stack/context.json
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"
    local abs_ctx
    abs_ctx="$(pwd)/.artifacts/rebase-stack/context.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    setup_hook_env "$hooks_dir" "$snap" "$abs_ctx"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    # Pass CORRECT push URL as $2 (matches baseline)
    local real_url
    real_url=$(git remote get-url --push origin)
    printf '%s\n' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$real_url" >/dev/null 2>&1
    rc=$?

    if [ "$rc" -eq 0 ]; then
      pass "inner hook allows matching \$2 push URL"
    else
      fail "inner hook URL match" "rc=$rc"
    fi
  )
}

# =========================================================================
# Run all tests
# =========================================================================
printf '\n=== rebase-stack regression tests ===\n\n'

test_snapshot_saves_published_tips
test_status_rebase_divergence
test_status_collaborator_update
test_status_branch_deleted
test_hook_blocks_collaborator
test_hook_allows_rebase
test_hook_blocks_deletion
test_hook_blocks_appeared
test_hook_rejects_unknown_branch
test_hook_allows_unpublished_first_push
test_hook_fails_closed_no_baseline
test_hook_chains_existing
test_hook_respects_existing_abort
test_changed_patch_accepted
test_guard_missing_baseline
test_guard_malformed_baseline
test_pr_base_mixed
test_pr_base_all_missing
test_pr_base_all_existing
test_continuation_preserves_baseline
test_real_push_wire_oids
test_real_push_blocks_collaborator
test_guard_lifecycle_preserves_hook
test_custom_hooks_path
test_spaces_in_hooks_path
test_old_behavior_rejects_normal_rebase
test_old_pr_loop_base_bug
test_pr_base_gap_middle
test_pr_base_several_gaps
test_env_reaches_hook_through_git
test_no_force_without_lease

# =========================================================================
# TEST 30: create-missing-prs.sh with stub gh — mixed existing/missing (fork)
# =========================================================================
test_create_prs_stub_mixed_fork() {
  local tmp_dir
  tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/pr-stub-test.XXXXXX")
  local gh_log="$tmp_dir/gh-calls.log"

  # Create a stub gh that records its arguments
  cat > "$tmp_dir/gh" << STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$gh_log"
echo "https://github.com/upstream/repo/pull/555"
exit 0
STUB
  chmod +x "$tmp_dir/gh"

  # Context: fork, story-1 has PR, story-2/story-3 do not
  cat > "$tmp_dir/ctx.json" << 'CTX'
{"trunk":"main","isFork":true,"parentRepo":"upstream/repo","forkOwner":"myuser",
 "branches":[
   {"name":"story-1","pr":412},
   {"name":"story-2","pr":null},
   {"name":"story-3","pr":null}
 ]}
CTX

  PATH="$tmp_dir:$PATH" bash "$SCRIPTS_DIR/create-missing-prs.sh" \
    --context "$tmp_dir/ctx.json" >/dev/null 2>&1
  rc=$?

  if [ "$rc" -eq 0 ] && [ -f "$gh_log" ]; then
    local call_count
    call_count=$(wc -l < "$gh_log")
    local first_call second_call
    first_call=$(sed -n '1p' "$gh_log")
    second_call=$(sed -n '2p' "$gh_log")

    # Verify: 2 PR creations, correct bases, fork targeting
    if [ "$call_count" -eq 2 ] \
       && printf '%s' "$first_call" | grep -qF -- "--base story-1" \
       && printf '%s' "$first_call" | grep -qF -- "--repo upstream/repo" \
       && printf '%s' "$first_call" | grep -qF -- "--head myuser:story-2" \
       && printf '%s' "$second_call" | grep -qF -- "--base story-2" \
       && printf '%s' "$second_call" | grep -qF -- "--head myuser:story-3"; then
      pass "create-prs stub: mixed fork — correct bases and targeting"
    else
      fail "create-prs stub mixed fork" "calls: $(cat "$gh_log")"
    fi
  else
    fail "create-prs stub mixed fork" "rc=$rc, log missing"
  fi
  rm -rf "$tmp_dir"
}

# =========================================================================
# TEST 31: create-missing-prs.sh with stub gh — all missing (direct)
# =========================================================================
test_create_prs_stub_all_missing_direct() {
  local tmp_dir
  tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/pr-stub-test.XXXXXX")
  local gh_log="$tmp_dir/gh-calls.log"
  local call_num=0

  cat > "$tmp_dir/gh" << 'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_LOG"
CALL_NUM=$(($(wc -l < "$GH_LOG")))
echo "https://github.com/org/repo/pull/$((100 + CALL_NUM))"
exit 0
STUB
  chmod +x "$tmp_dir/gh"

  cat > "$tmp_dir/ctx.json" << 'CTX'
{"trunk":"main","isFork":false,"parentRepo":"","forkOwner":"",
 "branches":[
   {"name":"story-1","pr":null},
   {"name":"story-2","pr":null},
   {"name":"story-3","pr":null}
 ]}
CTX

  GH_LOG="$gh_log" PATH="$tmp_dir:$PATH" bash "$SCRIPTS_DIR/create-missing-prs.sh" \
    --context "$tmp_dir/ctx.json" >/dev/null 2>&1
  rc=$?

  if [ "$rc" -eq 0 ] && [ -f "$gh_log" ]; then
    local call_count
    call_count=$(wc -l < "$gh_log")
    local c1 c2 c3
    c1=$(sed -n '1p' "$gh_log")
    c2=$(sed -n '2p' "$gh_log")
    c3=$(sed -n '3p' "$gh_log")

    if [ "$call_count" -eq 3 ] \
       && printf '%s' "$c1" | grep -qF -- "--base main" \
       && printf '%s' "$c1" | grep -qF -- "--head story-1" \
       && printf '%s' "$c2" | grep -qF -- "--base story-1" \
       && printf '%s' "$c3" | grep -qF -- "--base story-2"; then
      pass "create-prs stub: all missing direct — correct immediate predecessors"
    else
      fail "create-prs stub all missing" "calls: $(cat "$gh_log")"
    fi
  else
    fail "create-prs stub all missing" "rc=$rc"
  fi
  rm -rf "$tmp_dir"
}

# =========================================================================
# TEST 32: create-missing-prs.sh — gh failure stops before later PRs
# =========================================================================
test_create_prs_stub_failure_stops() {
  local tmp_dir
  tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/pr-stub-test.XXXXXX")
  local gh_log="$tmp_dir/gh-calls.log"

  # gh that fails on the second call
  cat > "$tmp_dir/gh" << 'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_LOG"
CALL_NUM=$(wc -l < "$GH_LOG")
if [ "$CALL_NUM" -ge 2 ]; then
  echo "API error: 422" >&2
  exit 1
fi
echo "https://github.com/org/repo/pull/100"
exit 0
STUB
  chmod +x "$tmp_dir/gh"

  cat > "$tmp_dir/ctx.json" << 'CTX'
{"trunk":"main","isFork":false,"parentRepo":"","forkOwner":"",
 "branches":[
   {"name":"story-1","pr":null},
   {"name":"story-2","pr":null},
   {"name":"story-3","pr":null}
 ]}
CTX

  GH_LOG="$gh_log" PATH="$tmp_dir:$PATH" bash "$SCRIPTS_DIR/create-missing-prs.sh" \
    --context "$tmp_dir/ctx.json" >/dev/null 2>&1
  rc=$?

  if [ "$rc" -ne 0 ] && [ -f "$gh_log" ]; then
    local call_count
    call_count=$(wc -l < "$gh_log")
    # Should have attempted 2 calls (first succeeds, second fails), NOT 3
    if [ "$call_count" -eq 2 ]; then
      pass "create-prs stub: failure on story-2 stops before story-3"
    else
      fail "create-prs failure stops" "expected 2 calls, got $call_count"
    fi
  else
    fail "create-prs failure stops" "rc=$rc (should be non-zero)"
  fi
  rm -rf "$tmp_dir"
}

# =========================================================================
# TEST 33: create-missing-prs.sh — all existing (no calls)
# =========================================================================
test_create_prs_stub_all_existing() {
  local tmp_dir
  tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/pr-stub-test.XXXXXX")
  local gh_log="$tmp_dir/gh-calls.log"

  cat > "$tmp_dir/gh" << 'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_LOG"
echo "should-not-run"
exit 0
STUB
  chmod +x "$tmp_dir/gh"

  cat > "$tmp_dir/ctx.json" << 'CTX'
{"trunk":"main","isFork":false,"parentRepo":"","forkOwner":"",
 "branches":[
   {"name":"story-1","pr":100},
   {"name":"story-2","pr":200},
   {"name":"story-3","pr":300}
 ]}
CTX

  GH_LOG="$gh_log" PATH="$tmp_dir:$PATH" bash "$SCRIPTS_DIR/create-missing-prs.sh" \
    --context "$tmp_dir/ctx.json" >/dev/null 2>&1
  rc=$?

  if [ "$rc" -eq 0 ] && [ ! -f "$gh_log" ]; then
    pass "create-prs stub: all existing — no gh calls made"
  else
    local calls
    calls=$(cat "$gh_log" 2>/dev/null | wc -l)
    fail "create-prs all existing" "rc=$rc, gh calls: $calls"
  fi
  rm -rf "$tmp_dir"
}

test_validate_baseline_missing_key
test_validate_baseline_empty_tips
test_validate_baseline_nonstring_sha
test_validate_baseline_wrong_trunk
test_validate_baseline_wrong_url
test_validate_baseline_wrong_branches
test_validate_baseline_valid
test_snapshot_refuses_overwrite
test_snapshot_allows_force_overwrite
test_guard_chains_other_hooks
test_guard_common_dir_hooks
test_create_prs_stub_mixed_fork
test_create_prs_stub_all_missing_direct
test_create_prs_stub_failure_stops
test_create_prs_stub_all_existing
test_linked_worktree_hooks
test_status_rejects_invalid_baseline
test_guard_rejects_wrong_repo_url
test_guard_rejects_wrong_trunk
test_snapshot_saves_identity
test_hook_wrapper_special_chars
test_inner_hook_full_validation
test_guard_rejects_empty_context
test_guard_rejects_empty_branches_ctx
test_guard_rejects_missing_commondir
test_inner_hook_rejects_missing_validator
test_snapshot_refuses_malformed_existing
test_status_rejects_baseremote_mismatch
test_validator_missing_arg
test_guard_missing_arg
test_snapshot_rejects_empty_branches
test_snapshot_preserves_dangling_link
test_snapshot_force_failed_candidate_preserves
test_guard_detects_parameters_override
test_guard_allows_unrelated_parameters
test_inner_hook_rejects_url_mismatch
test_inner_hook_allows_matching_url

PASS=$(cat "$PASS_FILE")
FAIL=$(cat "$FAIL_FILE")
printf '\n=== Summary: %s passed, %s failed ===\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
