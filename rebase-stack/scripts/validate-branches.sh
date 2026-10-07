#!/usr/bin/env bash
# Run a project's lint and test commands against one or more stack branches.
#
# /validate uses this for both of its modes:
#   default    one branch  — the trunk-adjacent branch
#   --all      every branch in the stack, bottom to top
#
# Usage:
#   validate-branches.sh --lint "<cmd>" --test "<cmd>" [--mode worktree|checkout] <branch>...
#
# Modes:
#   worktree  (default) each branch is validated in its own throwaway worktree
#             under .artifacts/rebase-stack/worktrees/. The main working tree is
#             never touched. Fails for projects whose suite needs installed
#             dependencies that live in the main tree (node_modules, vendor,
#             .venv) — use checkout mode there.
#   checkout  branches are checked out one at a time in the main working tree
#             and the starting branch is restored at the end. Reuses installed
#             dependencies; requires a clean tree.
#
# Validation stops at the first failing branch: every branch above it builds on
# that failure, so continuing only produces noise.
#
# Logs: .artifacts/rebase-stack/logs/<flattened-branch>-<digest>.log
#
# Exit codes:
#   0  every requested branch passed
#   1  a branch failed validation (its log path is printed)
#   2  bad usage or git refused to set up a work directory

set -uo pipefail

LOG_DIR=".artifacts/rebase-stack/logs"
WT_DIR=".artifacts/rebase-stack/worktrees"

lint_cmd=""
test_cmd=""
mode="worktree"
branches=()

while [ $# -gt 0 ]; do
  case "$1" in
    --lint) lint_cmd="${2:-}"; shift 2 ;;
    --test) test_cmd="${2:-}"; shift 2 ;;
    --mode) mode="${2:-}"; shift 2 ;;
    --) shift; break ;;
    -*) echo "validate-branches: unknown flag: $1" >&2; exit 2 ;;
    *) branches+=("$1"); shift ;;
  esac
done
while [ $# -gt 0 ]; do branches+=("$1"); shift; done

[ -n "$lint_cmd" ] || [ -n "$test_cmd" ] \
  || { echo "validate-branches: at least one of --lint / --test is required" >&2; exit 2; }
[ "${#branches[@]}" -gt 0 ] \
  || { echo "validate-branches: no branches given" >&2; exit 2; }
case "$mode" in
  worktree|checkout) ;;
  *) echo "validate-branches: --mode must be 'worktree' or 'checkout'" >&2; exit 2 ;;
esac

# Branch names are not unique after slash-flattening ("a/b" and "a-b" collide),
# so append a short digest of the real name.
safe_name() {
  local flat digest
  flat="${1//\//-}"
  flat="${flat//[^A-Za-z0-9._-]/_}"
  digest=$(printf '%s' "$1" | git hash-object --stdin)
  printf '%s-%s' "$flat" "${digest:0:8}"
}

mkdir -p "$LOG_DIR"
start_branch=$(git branch --show-current)
created_worktrees=()

cleanup() {
  # Only ever removes worktrees this run created, tracked in created_worktrees.
  local wt
  for wt in ${created_worktrees+"${created_worktrees[@]}"}; do
    git worktree remove --force "$wt" || \
      echo "validate-branches: WARNING: could not remove worktree ${wt}" >&2
  done
  if [ "$mode" = "checkout" ] && [ -n "$start_branch" ]; then
    local now
    now=$(git branch --show-current)
    if [ "$now" != "$start_branch" ]; then
      git checkout --quiet "$start_branch" \
        || echo "validate-branches: WARNING: could not return to ${start_branch}" >&2
    fi
  fi
}
trap cleanup EXIT

if [ "$mode" = "checkout" ] && [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "validate-branches: checkout mode needs a clean working tree." >&2
  exit 2
fi

# The lint/test commands arrive from the project's own docs as opaque strings,
# so a shell is needed to run them. Use a CHILD shell via 'bash -c' rather than
# 'eval': the command then cannot reassign this script's variables, redefine its
# functions, or alter its control flow.
run_cmd() {
  [ -n "$1" ] || return 0
  bash -c "$1"
}

suite() {
  run_cmd "$lint_cmd" && run_cmd "$test_cmd"
}

repo_root=$(git rev-parse --show-toplevel)
failed=""

for branch in "${branches[@]}"; do
  safe=$(safe_name "$branch")
  log="${LOG_DIR}/${safe}.log"
  work_dir=""

  if [ "$mode" = "checkout" ]; then
    if ! git checkout --quiet "$branch" 2>>"$log"; then
      echo "${branch}: ERROR — could not check out; see ${log}" >&2
      failed="$branch"
      break
    fi
    work_dir="$repo_root"
  elif [ "$branch" = "$start_branch" ]; then
    # Already checked out in the main tree; a worktree is impossible and
    # unnecessary.
    work_dir="$repo_root"
  else
    mkdir -p "$WT_DIR"
    wt="${WT_DIR}/${safe}"
    # Never force-remove an existing path: it may hold someone else's worktree
    # or real work. Prune stale administrative entries, then refuse if the path
    # is still occupied.
    git worktree prune
    if [ -e "$wt" ]; then
      echo "${branch}: ERROR — ${wt} already exists; refusing to overwrite it." >&2
      echo "  Inspect with 'git worktree list'. If it is stale, remove it yourself:" >&2
      echo "      git worktree remove ${wt}" >&2
      failed="$branch"
      break
    fi
    if ! git worktree add --quiet --detach "$wt" "$branch" 2>>"$log"; then
      echo "${branch}: ERROR — 'git worktree add' failed; see ${log}" >&2
      echo "  Inspect with 'git worktree list' and clean up with 'git worktree remove --force'." >&2
      failed="$branch"
      break
    fi
    created_worktrees+=("$wt")
    work_dir="$wt"
  fi

  printf '%s: validating in %s ... ' "$branch" "$work_dir"
  ( cd "$work_dir" && suite ) > "$log" 2>&1
  rc=$?

  if [ "$rc" -eq 0 ]; then
    printf 'PASS\n'
    rm -f "$log"
  else
    printf 'FAIL (exit %s)\n' "$rc"
    echo "  log: ${log}"
    failed="$branch"
    break
  fi
done

if [ -n "$failed" ]; then
  echo
  echo "validate-branches: stopped at '${failed}'. Branches above it were not run,"
  echo "because they contain this branch's commits and would fail the same way."
  exit 1
fi

echo "validate-branches: all ${#branches[@]} branch(es) passed."
exit 0
