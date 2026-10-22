#!/usr/bin/env bash
# Stack health report for the rebase-stack workflow.
#
# Answers, in one pass, the questions a stacked-branch rebase actually turns on:
#   - has the base branch moved, and by how much?
#   - which layers are stale relative to the layer below them?
#   - which layers have diverged from their published copies?
#   - which layers would become empty (all their commits already upstream)?
#   - which layers still have no PR?
#
# Reads the JSON context produced by preflight.sh on stdin.
#
# Usage:
#   ./scripts/preflight.sh | ./scripts/stack-status.sh
#   ./scripts/preflight.sh | ./scripts/stack-status.sh --no-fetch
#
# Exit codes:
#   0  report printed, stack is already up to date with the base
#   1  report printed, at least one layer needs rebasing
#   2  bad input
#   3  a remote could not be fetched; refusing to report from stale refs

set -uo pipefail

do_fetch=1
[ "${1:-}" = "--no-fetch" ] && do_fetch=0

ctx=$(cat)
jq -e . >/dev/null 2>&1 <<<"$ctx" || { echo "stack-status: stdin is not valid JSON" >&2; exit 2; }

trunk=$(jq -r '.trunk' <<<"$ctx")
base_remote=$(jq -r '.baseRemote' <<<"$ctx")
push_remote=$(jq -r '.pushRemote' <<<"$ctx")
current=$(jq -r '.currentBranch' <<<"$ctx")
mapfile -t branches < <(jq -r '.branches[].name' <<<"$ctx")

# A failed fetch means every drift and divergence number below would be
# computed from stale refs — and the whole point of this report is to decide
# whether it is safe to force-push. Fail instead of reporting stale data.
if [ "$do_fetch" -eq 1 ]; then
  if ! git fetch --quiet "$base_remote" "$trunk"; then
    echo "stack-status: could not fetch ${base_remote}/${trunk}." >&2
    echo "  Refusing to report from stale refs. Fix connectivity and retry," >&2
    echo "  or pass --no-fetch to accept the local view explicitly." >&2
    exit 3
  fi
  if [ "$push_remote" != "$base_remote" ]; then
    if ! git fetch --quiet "$push_remote"; then
      echo "stack-status: could not fetch ${push_remote}." >&2
      echo "  Divergence against the published branches cannot be trusted." >&2
      echo "  Fix connectivity and retry, or pass --no-fetch to accept the" >&2
      echo "  local view explicitly." >&2
      exit 3
    fi
  fi
else
  echo "stack-status: --no-fetch — remote columns reflect the last fetch, not GitHub." >&2
fi

base_ref="${base_remote}/${trunk}"
git rev-parse --verify --quiet "$base_ref" >/dev/null \
  || { echo "stack-status: base ref ${base_ref} does not exist" >&2; exit 2; }

printf '\nStack: (%s) <- %s\n' "$trunk" "$(printf '%s <- ' "${branches[@]}" | sed 's/ <- $//')"
printf 'Base remote: %s (%s)   Push remote: %s (%s)\n' \
  "$base_remote" "$(jq -r '.baseRemoteSource' <<<"$ctx")" \
  "$push_remote" "$(jq -r '.pushRemoteSource' <<<"$ctx")"

# --- base drift -----------------------------------------------------------
drift=0
if git rev-parse --verify --quiet "$trunk" >/dev/null; then
  drift=$(git rev-list --count "${trunk}..${base_ref}" 2>/dev/null || echo 0)
  if [ "$drift" -gt 0 ]; then
    printf 'Base drift: %s/%s is %s commit(s) ahead of your local %s\n' \
      "$base_remote" "$trunk" "$drift" "$trunk"
  else
    printf 'Base drift: local %s is level with %s\n' "$trunk" "$base_ref"
  fi
fi

printf '\n%-28s %-10s %-9s %-13s %-10s %s\n' \
  LAYER COMMITS STALE "VS-PUBLISHED" PR NOTES
printf '%s\n' "----------------------------------------------------------------------------------------------"

needs_rebase_any=0
parent="$base_ref"

for b in "${branches[@]}"; do
  row_notes=""

  if ! git rev-parse --verify --quiet "$b" >/dev/null; then
    printf '%-28s %s\n' "$b" "MISSING LOCALLY — stack metadata references a branch that does not exist"
    needs_rebase_any=1
    continue
  fi

  commits=$(git rev-list --count "${parent}..${b}" 2>/dev/null || echo "?")

  # Stale = the layer below is no longer an ancestor of this layer.
  if git merge-base --is-ancestor "$parent" "$b" 2>/dev/null; then
    stale="no"
  else
    stale="YES"
    needs_rebase_any=1
  fi

  # Divergence from the published copy on the push remote.
  pub_ref="${push_remote}/${b}"
  if git rev-parse --verify --quiet "$pub_ref" >/dev/null; then
    ahead=$(git rev-list --count "${pub_ref}..${b}" 2>/dev/null || echo "?")
    behind=$(git rev-list --count "${b}..${pub_ref}" 2>/dev/null || echo "?")
    if [ "$ahead" = "0" ] && [ "$behind" = "0" ]; then
      published="in sync"
    else
      published="+${ahead}/-${behind}"
      [ "$behind" != "0" ] && row_notes="${row_notes}remote has ${behind} commit(s) you do not; "
    fi
  else
    published="unpublished"
  fi

  pr=$(jq -r --arg b "$b" '.branches[] | select(.name == $b) | (.pr // "none") | tostring' <<<"$ctx")
  [ "$pr" = "none" ] && row_notes="${row_notes}no PR yet; "

  # Commits whose change is already present upstream — these vanish on rebase.
  dupes=$(git cherry "$base_ref" "$b" "$parent" 2>/dev/null | grep -c '^-' || true)
  if [ "${dupes:-0}" -gt 0 ]; then
    row_notes="${row_notes}${dupes} commit(s) already in ${trunk} (will be dropped); "
  fi
  if [ "$commits" = "0" ]; then
    row_notes="${row_notes}EMPTY layer; "
  fi

  printf '%-28s %-10s %-9s %-13s %-10s %s\n' \
    "$b$([ "$b" = "$current" ] && echo ' *')" "$commits" "$stale" "$published" "$pr" "${row_notes%%; }"

  parent="$b"
done

printf '\n* = currently checked out\n'

validation_branch=$(jq -r '.validationBranch' <<<"$ctx")
printf 'Trunk-adjacent branch (what /validate builds by default; --all covers every layer): %s\n' \
  "$validation_branch"

if [ "$drift" -gt 0 ] || [ "$needs_rebase_any" -eq 1 ]; then
  printf 'VERDICT: rebase needed\n\n'
  exit 1
fi

printf 'VERDICT: up to date — no rebase needed\n\n'
exit 0
