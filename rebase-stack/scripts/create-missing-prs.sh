#!/usr/bin/env bash
# Create PRs for stack branches that lack one, using the correct base branch.
#
# This is the executable form of the manual PR creation loop in push.md.
# It iterates ALL stack branches to advance the base correctly, but only
# creates PRs for branches without one.
#
# Usage:
#   create-missing-prs.sh --context <context.json> [--dry-run]
#
# In --dry-run mode, prints what it would do without calling gh pr create.
# Exit codes:
#   0  all missing PRs created (or nothing to create)
#   1  a PR creation failed
#   2  bad usage or missing input

set -uo pipefail

ctx_file=""
dry_run=false
while [ $# -gt 0 ]; do
  case "$1" in
    --context)
      [ $# -ge 2 ] || { echo "create-missing-prs: --context requires a value" >&2; exit 2; }
      ctx_file="$2"; shift 2 ;;
    --dry-run)  dry_run=true; shift ;;
    *) echo "create-missing-prs: unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$ctx_file" ] || { echo "create-missing-prs: --context required" >&2; exit 2; }
[ -f "$ctx_file" ] || { echo "create-missing-prs: context file not found: $ctx_file" >&2; exit 2; }

is_fork=$(jq -r '.isFork // false' "$ctx_file")
parent_repo=$(jq -r '.parentRepo // empty' "$ctx_file")
fork_owner=$(jq -r '.forkOwner // empty' "$ctx_file")
base=$(jq -r '.trunk' "$ctx_file")

mapfile -t all_branches < <(jq -r '.branches[].name' "$ctx_file")
previous_branch="$base"
previous_pr_number=""

for branch in "${all_branches[@]}"; do
  existing_pr=$(jq -r --arg b "$branch" \
    '.branches[] | select(.name == $b) | .pr // empty' "$ctx_file")

  if [ -z "$existing_pr" ]; then
    pr_args=()
    if [ "$is_fork" = "true" ] && [ -n "$parent_repo" ]; then
      pr_args+=(--repo "$parent_repo" --head "${fork_owner}:${branch}")
    else
      pr_args+=(--head "$branch")
    fi
    pr_args+=(--base "$previous_branch" --title "$branch" --draft)
    if [ -n "$previous_pr_number" ]; then
      pr_args+=(--body "Depends on: #${previous_pr_number}")
    fi

    if [ "$dry_run" = true ]; then
      printf 'CREATE %s --base %s' "$branch" "$previous_branch"
      [ -n "$previous_pr_number" ] && printf ' depends=#%s' "$previous_pr_number"
      printf '\n'
      previous_pr_number="CREATED"
    else
      pr_url=$(gh pr create "${pr_args[@]}" 2>&1)
      rc=$?
      if [ "$rc" -ne 0 ]; then
        printf 'create-missing-prs: failed to create PR for %s (exit %s): %s\n' \
          "$branch" "$rc" "$pr_url" >&2
        exit 1
      fi
      previous_pr_number=$(printf '%s' "$pr_url" | grep -o '[0-9]*$')
    fi
  else
    previous_pr_number="$existing_pr"
  fi
  previous_branch="$branch"
done
