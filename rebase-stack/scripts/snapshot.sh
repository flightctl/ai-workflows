#!/usr/bin/env bash
# Pre-rebase safety net for the rebase-stack workflow.
#
# A stack rebase rewrites every layer at once. If it goes wrong there is no
# single reflog entry to undo it, so this records every branch tip before the
# rebase and verifies afterwards that no commit silently disappeared.
#
# Usage:
#   ./scripts/preflight.sh | ./scripts/snapshot.sh save
#   ./scripts/preflight.sh | ./scripts/snapshot.sh verify
#   ./scripts/snapshot.sh restore-plan      # prints the exact recovery commands
#
# Exit codes:
#   0  success (verify: no commits lost)
#   1  verify: one or more commits present before the rebase are gone
#   2  bad usage, or no snapshot found

set -uo pipefail

STATE_DIR=".artifacts/rebase-stack"
SNAPSHOT="${STATE_DIR}/pre-rebase-state.json"

cmd="${1:-}"

case "$cmd" in
  save)
    ctx=$(cat)
    jq -e . >/dev/null 2>&1 <<<"$ctx" || { echo "snapshot: stdin is not valid JSON" >&2; exit 2; }
    mkdir -p "$STATE_DIR"

    base_ref="$(jq -r '.baseRemote' <<<"$ctx")/$(jq -r '.trunk' <<<"$ctx")"
    git rev-parse --verify --quiet "$base_ref" >/dev/null \
      || { echo "snapshot: base ref ${base_ref} does not exist; cannot snapshot" >&2; exit 2; }

    entries="[]"
    while IFS= read -r b; do
      [ -n "$b" ] || continue
      # An unresolvable branch means the snapshot would be incomplete, and an
      # incomplete snapshot is worse than none: verify would report no loss.
      if ! sha=$(git rev-parse --verify --quiet "$b"); then
        echo "snapshot: branch '${b}' does not resolve; refusing to write a partial snapshot" >&2
        exit 2
      fi
      # Identify commits by patch-id so a rebase that rewrites SHAs still
      # matches, and two commits sharing a subject stay distinguishable.
      commits=$(git log --reverse --format='%H' "${base_ref}..${b}" \
        | while IFS= read -r sha1; do
            pid=$(git show "$sha1" | git patch-id --stable | cut -d' ' -f1)
            jq -n --arg sha "$sha1" --arg patchId "${pid:-}" \
                  --arg subject "$(git log -1 --format=%s "$sha1")" \
                  '{sha: $sha, patchId: $patchId, subject: $subject}'
          done | jq -s .)
      entries=$(jq --arg name "$b" --arg sha "$sha" --argjson commits "${commits:-[]}" \
                   '. + [{name: $name, sha: $sha, commits: $commits}]' <<<"$entries")
    done < <(jq -r '.branches[].name' <<<"$ctx")

    jq -n --argjson ctx "$ctx" --argjson branches "$entries" \
      '{trunk: $ctx.trunk, baseRemote: $ctx.baseRemote, pushRemote: $ctx.pushRemote, branches: $branches}' \
      > "$SNAPSHOT"

    printf 'snapshot: saved %s branch tip(s) to %s\n' \
      "$(jq '.branches | length' "$SNAPSHOT")" "$SNAPSHOT"
    ;;

  verify)
    [ -f "$SNAPSHOT" ] || { echo "snapshot: no snapshot at ${SNAPSHOT}; nothing to verify" >&2; exit 2; }
    ctx=$(cat)
    base_ref="$(jq -r '.baseRemote' <<<"$ctx")/$(jq -r '.trunk' <<<"$ctx")"
    lost=0

    while IFS= read -r b; do
      [ -n "$b" ] || continue

      if ! git rev-parse --verify --quiet "$b" >/dev/null; then
        lost=1
        printf '\nsnapshot: branch %s no longer exists.\n' "$b"
        continue
      fi

      # Current identities of this branch, by patch-id and by SHA.
      after_pids=$(git log --format='%H' "${base_ref}..${b}" \
        | while IFS= read -r sha1; do
            git show "$sha1" | git patch-id --stable | cut -d' ' -f1
          done)
      after_shas=$(git log --format='%H' "${base_ref}..${b}")

      n=$(jq --arg b "$b" '[.branches[] | select(.name == $b) | .commits[]?] | length' "$SNAPSHOT")
      i=0
      while [ "$i" -lt "$n" ]; do
        entry=$(jq -c --arg b "$b" --argjson i "$i" \
                  '[.branches[] | select(.name == $b) | .commits[]?][$i]' "$SNAPSHOT")
        o_sha=$(jq -r '.sha' <<<"$entry")
        o_pid=$(jq -r '.patchId // ""' <<<"$entry")
        o_sub=$(jq -r '.subject' <<<"$entry")
        i=$((i + 1))

        # Matched if the rewritten commit carries the same patch, or the very
        # same SHA survived. An empty patch-id means an empty commit: fall back
        # to the subject rather than reporting a false loss.
        if [ -n "$o_pid" ] && printf '%s\n' "$after_pids" | grep -qxF "$o_pid"; then
          continue
        fi
        if printf '%s\n' "$after_shas" | grep -qxF "$o_sha"; then
          continue
        fi
        if [ -z "$o_pid" ] \
           && git log --format=%s "${base_ref}..${b}" | grep -qxF "$o_sub"; then
          continue
        fi

        [ "$lost" -eq 1 ] || printf '\nsnapshot: commits no longer reachable from %s:\n' "$b"
        lost=1
        printf '  - %s  (%s)\n' "$o_sub" "${o_sha:0:12}"
      done
    done < <(jq -r '.branches[].name' "$SNAPSHOT")

    if [ "$lost" -eq 1 ]; then
      printf '\nsnapshot: some commits are gone. This is EXPECTED only when those\n'
      printf 'changes already landed in %s. Confirm each one before pushing, or run:\n' "$base_ref"
      printf '    ./scripts/snapshot.sh restore-plan\n\n'
      exit 1
    fi

    printf 'snapshot: verified — every pre-rebase commit is still present.\n'
    ;;

  restore-plan)
    [ -f "$SNAPSHOT" ] || { echo "snapshot: no snapshot at ${SNAPSHOT}" >&2; exit 2; }
    printf '# Recovery plan — restores every branch to its pre-rebase tip.\n'
    printf '# Review before running. These are local resets; nothing is pushed.\n'
    jq -r '.branches[] | "git branch -f \(.name) \(.sha)"' "$SNAPSHOT"
    printf '# Then re-sync the stack metadata:\n'
    printf '#   gh stack view --json\n'
    ;;

  *)
    echo "usage: snapshot.sh save|verify|restore-plan" >&2
    exit 2
    ;;
esac
