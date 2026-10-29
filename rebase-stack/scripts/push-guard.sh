#!/usr/bin/env bash
# Ephemeral pre-push baseline guard for the rebase-stack workflow.
#
# Installs a temporary pre-push hook that validates Git's advertised remote
# OIDs against a saved pre-rebase published-tip baseline, chains any existing
# pre-push hook with unchanged args/stdin/abort semantics, delegates to
# `gh stack push`, and unconditionally restores the original hook state on exit.
#
# The hook fires during the git push that gh-stack initiates. Because
# gh-stack's internal FetchBranches updates tracking refs before constructing
# force-with-lease, a collaborator push between the workflow's check and
# gh-stack's fetch would become the new expected SHA. This guard closes that
# gap: the pre-push hook runs after Git's ref advertisement, so it sees the
# actual remote state at wire time and rejects if any branch diverged from
# the saved baseline. The lease then covers the remaining window between
# advertisement and data transfer.
#
# Usage:
#   push-guard.sh --baseline <file> --remote <remote>
#
# Exit codes: passes through gh stack push's exit code.
#   2  bad usage, baseline missing/invalid, or hook setup failed

set -uo pipefail

baseline=""
remote=""
while [ $# -gt 0 ]; do
  case "$1" in
    --baseline) baseline="${2:-}"; shift 2 ;;
    --remote) remote="${2:-}"; shift 2 ;;
    *) echo "push-guard: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$baseline" ] || { echo "push-guard: --baseline is required" >&2; exit 2; }
[ -n "$remote" ]   || { echo "push-guard: --remote is required" >&2; exit 2; }
[ -f "$baseline" ] || { echo "push-guard: baseline file not found: ${baseline}" >&2; exit 2; }
jq -e '.publishedTips' "$baseline" >/dev/null 2>&1 \
  || { echo "push-guard: baseline file has no publishedTips object" >&2; exit 2; }

# Absolute path — the hook may run in a different working directory when
# gh-stack's git invocation is scoped to a worktree or subdir.
baseline=$(cd "$(dirname "$baseline")" && printf '%s/%s' "$(pwd)" "$(basename "$baseline")")

# ---------------------------------------------------------------------------
# Resolve the hooks directory. core.hooksPath takes precedence; the default
# is $GIT_DIR/hooks. Never modify core.hooksPath itself.
# ---------------------------------------------------------------------------
hooks_dir=$(git config core.hooksPath 2>/dev/null) \
  || hooks_dir="$(git rev-parse --git-dir)/hooks"
case "$hooks_dir" in
  /*) ;;
  *) hooks_dir="$(pwd)/${hooks_dir}" ;;
esac
mkdir -p "$hooks_dir"

target="$hooks_dir/pre-push"
saved="$hooks_dir/pre-push.rebase-stack-saved"

# ---------------------------------------------------------------------------
# Save any existing pre-push hook so it can be chained and restored.
# Use cp -a to preserve permissions and symlinks.
# ---------------------------------------------------------------------------
had_original=false
if [ -f "$target" ] || [ -L "$target" ]; then
  cp -a "$target" "$saved"
  had_original=true
fi

# Unconditional cleanup — restores the original hook regardless of how this
# script exits (success, failure, signal).
cleanup() {
  if [ "$had_original" = true ] && [ -f "$saved" ]; then
    mv -f "$saved" "$target"
  elif [ "$had_original" = false ]; then
    rm -f "$target"
  fi
  rm -f "$saved"  # belt-and-suspenders
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Write the ephemeral pre-push hook.
# ---------------------------------------------------------------------------
cat > "$target" << 'HOOKEOF'
#!/usr/bin/env bash
# Ephemeral pre-push hook installed by rebase-stack push-guard.sh.
# Validates advertised remote OIDs against a saved pre-rebase baseline.
# Chains to the original pre-push hook if one was present.
set -uo pipefail

ZERO="0000000000000000000000000000000000000000"
baseline_file="${REBASE_STACK_BASELINE_FILE:-}"
saved_hook_path="${REBASE_STACK_SAVED_HOOK:-}"

# Read all of stdin so it can be replayed for the original hook and our check.
input=$(cat)

# ------ Chain: run original hook first with unchanged args and stdin ------
if [ -n "$saved_hook_path" ] && [ -x "$saved_hook_path" ]; then
  printf '%s' "$input" | "$saved_hook_path" "$@"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    exit "$rc"
  fi
fi

# ------ Baseline guard ---------------------------------------------------
if [ -z "$baseline_file" ] || [ ! -f "$baseline_file" ]; then
  echo "rebase-stack pre-push: baseline file missing; refusing push" >&2
  exit 1
fi
if ! jq -e '.publishedTips' "$baseline_file" >/dev/null 2>&1; then
  echo "rebase-stack pre-push: baseline has no publishedTips; refusing push" >&2
  exit 1
fi

# No refs being pushed — nothing to guard.
[ -n "$input" ] || exit 0

failed=0
while IFS=' ' read -r _local_ref _local_sha remote_ref remote_sha; do
  [ -n "$remote_ref" ] || continue
  # Only guard branch refs, not tags or other ref namespaces.
  branch="${remote_ref#refs/heads/}"
  [ "$branch" != "$remote_ref" ] || continue

  saved_tip=$(jq -r --arg b "$branch" \
    '.publishedTips[$b] // "ABSENT"' "$baseline_file")

  if [ "$saved_tip" = "ABSENT" ]; then
    # Branch was unpublished before the rebase.
    if [ "$remote_sha" != "$ZERO" ]; then
      printf 'rebase-stack pre-push: %s was unpublished but remote advertises %s; refusing\n' \
        "$branch" "${remote_sha:0:12}" >&2
      failed=1
    fi
  else
    if [ "$remote_sha" = "$ZERO" ]; then
      printf 'rebase-stack pre-push: %s was at baseline %s but deleted from remote; refusing\n' \
        "$branch" "${saved_tip:0:12}" >&2
      failed=1
    elif [ "$remote_sha" != "$saved_tip" ]; then
      printf 'rebase-stack pre-push: %s remote changed: baseline=%s advertised=%s; refusing\n' \
        "$branch" "${saved_tip:0:12}" "${remote_sha:0:12}" >&2
      failed=1
    fi
  fi
done <<< "$input"

exit "$failed"
HOOKEOF
chmod +x "$target"

# ---------------------------------------------------------------------------
# Export state for the hook. Environment variables propagate through
# gh (Go) → exec.Cmd (Environ()) → git push → pre-push hook.
# ---------------------------------------------------------------------------
export REBASE_STACK_BASELINE_FILE="$baseline"
export REBASE_STACK_SAVED_HOOK=""
if [ "$had_original" = true ]; then
  export REBASE_STACK_SAVED_HOOK="$saved"
fi

# ---------------------------------------------------------------------------
# Delegate to gh stack push. The trap restores the original hook on exit.
# ---------------------------------------------------------------------------
gh stack push --remote "$remote"
