---
name: push
description: Confirm, push every stack branch atomically to the resolved push remote, then open missing PRs.
---

# Push Rebase Stack

## Step 1: Preflight

Follow `preflight.md`. Then confirm `/validate` actually ran against the
current tips — a push on an unvalidated rebase is the failure mode this
workflow exists to prevent:

The record pins **every** stack branch, with a `validated` / `not-run` flag.
Check them all: an intermediate branch that moved since validation must not be
published even when the trunk-adjacent branch is untouched.

```bash
record=.artifacts/rebase-stack/validated
if [ ! -f "$record" ]; then
  echo "NEVER VALIDATED — run /validate first"
else
  head -1 "$record"                       # mode=tip | mode=all
  tail -n +2 "$record" | while read -r state branch sha; do
    now=$(git rev-parse --verify --quiet "$branch")
    if [ "$now" = "$sha" ]; then
      printf '%-28s %-10s unchanged\n' "$branch" "$state"
    else
      printf '%-28s %-10s MOVED %s -> %s\n' "$branch" "$state" "$sha" "${now:-missing}"
    fi
  done
  # The loop above only sees branches the record already knows about. A branch
  # added to the stack after /validate ran is absent from it entirely, so it
  # would otherwise be published having never been tested. Drive the second
  # pass from context.json, which is the current stack.
  jq -r '.branches[].name' .artifacts/rebase-stack/context.json | while read -r b; do
    tail -n +2 "$record" | awk -v b="$b" '$2 == b {found=1} END {exit !found}' \
      || printf '%-28s %-10s NOT RECORDED — not covered by /validate\n' "$b" "absent"
  done
fi
```

`git rev-parse --verify --quiet` is silent on a missing branch, so no output
needs redirecting away. The `awk` field match compares the whole branch field,
so a branch whose name is a substring of another is not mistaken for it.

Send the user back to `/validate` if the record is missing, if any branch shows
`MOVED`, or if any branch shows `NOT RECORDED`. `/validate` also performs the
fetch that `--force-with-lease` depends on.

Report the recorded mode in Step 5 so the user knows what was covered:
`mode=tip` means only the trunk-adjacent branch was built and tested and per-PR
CI will be the first check on every layer above it; `mode=all` means every
layer was validated locally.

Before presenting the push confirmation, refresh the published state and
compare against the pre-rebase baseline. This catches collaborator pushes
that appeared between `/validate` and `/push`:

```bash
ctx=.artifacts/rebase-stack/context.json
snapshot=.artifacts/rebase-stack/pre-rebase-state.json
push_remote=$(jq -r '.pushRemote' "$ctx")
git fetch --quiet "$push_remote"
echo "fetch exit: $?"
```

Stop if the fetch fails — divergence cannot be classified without current
remote refs. Then check every branch against the saved pre-rebase baseline:

```bash
if [ ! -f "$snapshot" ] \
   || ! bash "{scripts}/validate-baseline.sh" "$snapshot" \
          --context .artifacts/rebase-stack/context.json >/dev/null 2>&1; then
  echo "NO BASELINE — cannot classify divergence; run /start first"
fi
jq -r '.branches[].name' "$ctx" | while read -r branch; do
  saved_tip=$(jq -r --arg b "$branch" '.publishedTips[$b] // "ABSENT"' "$snapshot")
  if git show-ref --quiet --verify "refs/remotes/${push_remote}/${branch}"; then
    current_tip=$(git rev-parse --verify --quiet "refs/remotes/${push_remote}/${branch}")
    if [ "$saved_tip" = "ABSENT" ]; then
      printf 'APPEARED  %-28s current=%s\n' "$branch" "${current_tip:0:12}"
    elif [ "$saved_tip" != "$current_tip" ]; then
      printf 'UPDATED   %-28s baseline=%s current=%s\n' \
        "$branch" "${saved_tip:0:12}" "${current_tip:0:12}"
    fi
  else
    if [ "$saved_tip" != "ABSENT" ]; then
      printf 'DELETED   %-28s baseline=%s\n' "$branch" "${saved_tip:0:12}"
    fi
  fi
done
```

If any branch prints `UPDATED`, `APPEARED`, or `DELETED`, stop. The remote
changed since the pre-rebase snapshot — a force-push would discard
collaborator work. Send the user back to `/start` to reconcile.

If the baseline is missing or malformed, stop: divergence cannot be
classified without it, and defaulting to "allow" would be unsafe.

## Step 2: Confirm the Push

Present the exact command and the exact branch list, then wait:

```bash
jq -r '"push remote : \(.pushRemote)  (\(.pushRemoteSource))",
       "base branch : \(.baseRemote)/\(.trunk)",
       "branches    :", (.branches[] | "  - \(.name)  pr=\(.pr // "will be created")")' \
  .artifacts/rebase-stack/context.json
```

> This force-pushes `{N}` branches to `{push-remote}` with
> `--force-with-lease --atomic`. The base branch `{base}` is never pushed.
> If the remote does not support atomic pushes, a partial update is possible.
> Proceed?

**Stop here.** Wait for explicit confirmation.

## Step 3: Push

Resolve `{scripts}` as described in `preflight.md` Step 1. `push-guard.sh`
installs an ephemeral pre-push hook that validates Git's advertised remote
OIDs against the saved pre-rebase baseline, chains any existing pre-push hook
with unchanged args/stdin/abort semantics, delegates to `gh stack push`, and
unconditionally restores the original hook state on exit. This closes the gap
between the workflow's divergence check and `gh stack push`'s internal fetch:
the hook runs after Git's ref advertisement, so it sees the actual remote
state at wire time.

```bash
scripts="{scripts}"
ctx=.artifacts/rebase-stack/context.json
push_remote=$(jq -r '.pushRemote' "$ctx")
bash "$scripts/push-guard.sh" \
  --baseline .artifacts/rebase-stack/pre-rebase-state.json \
  --remote "$push_remote" \
  --context .artifacts/rebase-stack/context.json
echo "push exit: $?"
```

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Every branch pushed. | Go to Step 4. |
| 1 | Lease rejected or pre-push baseline guard blocked the push — someone pushed since the pre-rebase snapshot. | Re-run `/validate`: it re-fetches and re-reads stack health, so it shows what actually moved and re-establishes the lease. Never add `--force`. |
| 2 | Bad arguments, missing baseline, or hook setup failed. | Stop and report. Confirm the pre-rebase snapshot exists. |
| 4 | GitHub API failure. | Stop. Report `gh auth status`; run preflight and `/validate` again before asking for a new push confirmation. |
| 8 | Stack file locked. | Stop. Another `gh stack` process may be writing; run preflight and `/validate` again before asking for a new push confirmation. |
| other | Unknown. | Stop and report the exit code and full stderr. |

**Never retry a rejected push in this phase.** `gh stack push` requests
`--force-with-lease`, and the pre-push guard validates against the saved
pre-rebase baseline. Together, these cover two windows: the guard catches
collaborator pushes up to Git's ref advertisement; the lease catches changes
between advertisement and data transfer. A failed push may still have updated
some branches (see atomicity below), and the lock or API failure may have been
another client pushing. Stop, report the exit code, and start over with
preflight and `/validate` before a new push confirmation:

```bash
view=$(gh stack view --json); echo "view exit: $?"
jq -r '.branches[] | "\(.name)  \(.head[0:8])  pr=\(.pr.number // "none")"' <<<"$view"
```

Capture first and report that exit code: reading `$?` after a pipe reports
`jq`, not `gh`, and a failed `gh stack view` piped into `jq` looks like an
empty stack rather than an error.

`/validate` re-fetches, re-reads stack health, and rewrites the record against
the current tips. Its SHA check then rejects any branch that moved during the
failed push or lock contention. Never add `--force`.

`gh stack push` also requests `--atomic`, but atomicity depends on the remote
supporting the `atomic` push capability: when it does, a single rejected
branch rejects the whole push; when it does not, branches whose lease still
held may already have updated. Never assume nothing moved — re-run `/validate`
after any rejection to re-fetch and see the real state.

## Step 4: Open Missing PRs

```bash
jq -r '.branches[] | select(.pr == null) | .name' .artifacts/rebase-stack/context.json
jq -r '"isFork=\(.isFork)  repo=\(.repo)  parent=\(.parentRepo)  owner=\(.forkOwner)"' \
  .artifacts/rebase-stack/context.json
```

If the list is empty, skip to Step 5.

**Direct clone (`isFork` is `false`):**

```bash
push_remote=$(jq -r '.pushRemote' .artifacts/rebase-stack/context.json)
gh stack submit --auto --remote "$push_remote"
echo "submit exit: $?"
```

Exit 0 means PRs were created and linked as a stack; skip the manual path.
Exit 9 means Stacked PRs are not enabled on this repository — continue below.
Any other non-zero: stop and report.

**Fork (`isFork` is `true`):** skip `gh stack submit` entirely. It targets the
fork, not the upstream, so it would open PRs on the wrong repository.

**Manual creation.** Bottom to top, so each PR can reference the one below it.
Read the fork owner, parent repo, and base branch from the context at runtime —
never splice these values into shell syntax, as they may contain shell
metacharacters:

```bash
ctx=.artifacts/rebase-stack/context.json
parent_repo=$(jq -r '.parentRepo' "$ctx")
fork_owner=$(jq -r '.forkOwner' "$ctx")
base=$(jq -r '.trunk' "$ctx")
```

Then create PRs bottom to top using the helper script. It iterates **all**
branches to advance `previous_branch` to the correct immediate predecessor,
but creates a PR only for branches that lack one. This ensures that when
story-1 already has a PR and story-2 does not, story-2 targets story-1
(not the trunk). Resolve `{scripts}` as described in `preflight.md` Step 1:

```bash
scripts="{scripts}"
bash "$scripts/create-missing-prs.sh" --context "$ctx"
echo "create-prs exit: $?"
```

For a direct clone the script uses `--head "$branch"` automatically.
The bottom branch in the stack — whether it needs a PR or already has one —
provides the base for the next layer up.

If PR creation fails, the script exits 1 immediately and names the branch.
Do not continue to Step 5; the user needs to fix the failure and re-run
`/push`.

## Step 5: Report

```bash
gh stack view --json | jq -r '.branches[] | "\(.name)  \(.head[0:8])  pr=\(.pr.number // "none")  \(.pr.url // "")"'
```

Summarize:

- Each branch pushed and its new tip.
- Each PR created (number and URL) and each that already existed.
- Which branches were built and tested, taken from `mode=` in
  `.artifacts/rebase-stack/validated`. For `mode=tip`, name
  `{validation-branch}` and note that per-PR CI is the first independent
  check on the intermediate layers.
- Any branch still without a PR, and why.

Then clear the rebase safety net, which is now stale:

```bash
rm -f .artifacts/rebase-stack/pre-rebase-state.json
```
