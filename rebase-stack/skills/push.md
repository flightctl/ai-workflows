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

```bash
gh stack push --remote {push-remote}
echo "push exit: $?"
```

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Every branch pushed. | Go to Step 4. |
| 1 | Lease rejected — someone pushed since the fetch. | Re-run `/validate`: it re-fetches and re-reads stack health, so it shows what actually moved and re-establishes the lease. Never add `--force`. |
| 4 | GitHub API failure. | Report `gh auth status`; re-read the state as below, then ask before retrying. |
| 8 | Stack file locked. | Wait about 5s, re-read the state as below, retry once, then stop. |
| other | Unknown. | Stop and report the exit code and full stderr. |

**Never retry a rejected push blind.** `gh stack push` requests
`--force-with-lease`, and the lease is only safe against the remote state the
last fetch recorded. A failed push may still have updated some branches
(see atomicity below), and the lock or API failure may have been another
client pushing. Re-read the stack before every retry:

```bash
view=$(gh stack view --json); echo "view exit: $?"
jq -r '.branches[] | "\(.name)  \(.head[0:8])  pr=\(.pr.number // "none")"' <<<"$view"
```

Capture first and report that exit code: reading `$?` after a pipe reports
`jq`, not `gh`, and a failed `gh stack view` piped into `jq` looks like an
empty stack rather than an error.

Compare that against the tips recorded in `.artifacts/rebase-stack/validated`.
Retry only when `gh stack view --json` exits 0 and every branch head still
matches its recorded SHA. If any head moved, or the command does not exit 0,
stop and send the user back to `/validate` — it re-fetches and re-establishes
the lease. Never add `--force`.

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
gh stack submit --auto --remote {push-remote}
echo "submit exit: $?"
```

Exit 0 means PRs were created and linked as a stack; skip the manual path.
Exit 9 means Stacked PRs are not enabled on this repository — continue below.
Any other non-zero: stop and report.

**Fork (`isFork` is `true`):** skip `gh stack submit` entirely. It targets the
fork, not the upstream, so it would open PRs on the wrong repository.

**Manual creation.** Bottom to top, so each PR can reference the one below it:

```bash
gh pr create \
  --repo {parent-repo} \
  --head {fork-owner}:{branch} \
  --base {base} \
  --title "{branch-title}" \
  --draft \
  --body "Depends on: #{previous-pr-number}"
```

For a direct clone drop `--repo` and use `--head {branch}`. Omit the
`Depends on:` line for `{bottom-branch}`. Feed the number returned by each
call into the next one.

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
