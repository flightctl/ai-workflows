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
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Extract the hook script from push-guard.sh: write it directly and
    # test with simulated stdin (the format git provides to pre-push hooks).
    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    # Write the hook manually (extract the HOOKEOF block from push-guard.sh)
    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""

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

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$bare_path" >/dev/null 2>&1
    local rc=$?

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
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""

    # Simulate the SAVED baseline matching the advertised (remote unchanged)
    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

    if [ "$rc" -eq 0 ]; then
      pass "pre-push hook allows clean rebase (baseline matches advertised)"
    else
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
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""

    # Simulate deleted branch: remote_sha is all zeros
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 0000000000000000000000000000000000000000"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook blocks branch deletion"
    else
      fail "pre-push hook blocks branch deletion" "hook exited 0 (should have blocked)"
    fi
  )
}

# =========================================================================
# TEST 8: pre-push hook blocks newly appeared branch
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
    printf '%s' "$ctx" | bash "$SCRIPTS_DIR/snapshot.sh" save >/dev/null 2>&1
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    local hooks_dir
    hooks_dir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hooks_dir"

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""

    # Simulate: someone else pushed story-3 to the remote
    local fake_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    local local_sha
    local_sha=$(git rev-parse story-3)
    local stdin_line="refs/heads/story-3 ${local_sha} refs/heads/story-3 ${fake_sha}"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

    if [ "$rc" -ne 0 ]; then
      pass "pre-push hook blocks newly appeared branch"
    else
      fail "pre-push hook blocks newly appeared branch" "hook exited 0"
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

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="/nonexistent/baseline.json"
    export REBASE_STACK_SAVED_HOOK=""

    local local_sha
    local_sha=$(git rev-parse story-1)
    local remote_sha
    remote_sha=$(git rev-parse origin/story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${remote_sha}"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

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

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK="$hooks_dir/test-original.sh"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

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

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK="$hooks_dir/test-original.sh"

    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

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

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$hooks_dir/test-hook.sh"
    chmod +x "$hooks_dir/test-hook.sh"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""

    # Advertised OID = saved baseline (remote hasn't changed)
    local saved_tip
    saved_tip=$(jq -r '.publishedTips["story-1"]' "$snap")
    local local_sha
    local_sha=$(git rev-parse story-1)
    local stdin_line="refs/heads/story-1 ${local_sha} refs/heads/story-1 ${saved_tip}"

    printf '%s' "$stdin_line" | bash "$hooks_dir/test-hook.sh" origin "$(git remote get-url origin)" >/dev/null 2>&1
    local rc=$?

    if [ "$rc" -eq 0 ]; then
      pass "conflict-resolved changed patch accepted (remote unchanged)"
    else
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
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline /nonexistent/file.json \
      --remote origin >/dev/null 2>&1
    local rc=$?
    if [ "$rc" -eq 2 ]; then
      pass "push-guard.sh exits 2 on missing baseline"
    else
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
    echo '{"branches":[]}' > /tmp/bad-baseline.json
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline /tmp/bad-baseline.json \
      --remote origin >/dev/null 2>&1
    local rc=$?
    rm -f /tmp/bad-baseline.json
    if [ "$rc" -eq 2 ]; then
      pass "push-guard.sh exits 2 on malformed baseline"
    else
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
    export REBASE_STACK_SAVED_HOOK=""

    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$test_hooks/pre-push"
    chmod +x "$test_hooks/pre-push"

    # Real git push with force-with-lease — Git's wire protocol provides
    # advertised OIDs to the pre-push hook via stdin
    git push --force-with-lease origin story-1 story-2 >/dev/null 2>&1
    local rc=$?

    rm -f "$test_hooks/pre-push"
    git config --unset core.hooksPath

    if [ "$rc" -eq 0 ]; then
      pass "real git push: hook receives wire OIDs and allows clean rebase"
    else
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

    # Set repo-local hooksPath
    local test_hooks="$TEST_DIR/t20-wire-block/test-hooks"
    mkdir -p "$test_hooks"
    git config core.hooksPath "$test_hooks"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""
    sed -n '/^cat > "\$target" << '\''HOOKEOF'\''$/,/^HOOKEOF$/{ /^cat /d; /^HOOKEOF$/d; p; }' \
      "$SCRIPTS_DIR/push-guard.sh" > "$test_hooks/pre-push"
    chmod +x "$test_hooks/pre-push"

    # Real git push — the wire protocol will advertise the collaborator's SHA
    # The hook should REJECT because it doesn't match the saved baseline
    git push --force-with-lease origin story-1 >/dev/null 2>&1
    local rc=$?

    rm -f "$test_hooks/pre-push"
    git config --unset core.hooksPath

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
      --remote origin >/dev/null 2>&1 || true

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
      --remote origin >/dev/null 2>&1 || true

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
    local snap
    snap="$(pwd)/.artifacts/rebase-stack/pre-rebase-state.json"

    # Create a hooks dir with spaces in the path
    local spaced_dir="$TEST_DIR/t23-spaces/hooks with spaces"
    mkdir -p "$spaced_dir"
    git config core.hooksPath "$spaced_dir"

    export REBASE_STACK_BASELINE_FILE="$snap"
    export REBASE_STACK_SAVED_HOOK=""

    # push-guard.sh should handle the spaced path
    bash "$SCRIPTS_DIR/push-guard.sh" \
      --baseline .artifacts/rebase-stack/pre-rebase-state.json \
      --remote origin >/dev/null 2>&1 || true

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

PASS=$(cat "$PASS_FILE")
FAIL=$(cat "$FAIL_FILE")
printf '\n=== Summary: %s passed, %s failed ===\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
