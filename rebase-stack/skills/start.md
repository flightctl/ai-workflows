---
name: start
description: Gate the context, snapshot every branch tip, then rebase the whole stack onto its updated base.
---

# Start Rebase Stack

Rebases **every** layer in the stack. Local only — nothing is pushed.

## Step 1: Preflight

Follow `preflight.md`. On any non-zero exit, relay the message and stop. In
particular, exit 2 means this is not a stack and the workflow must refuse: do
not initialize one, and do not fall back to `git rebase`.

## Step 2: Show the Starting State

If a pre-rebase snapshot exists from a previous `/start` (the user is
re-running `/start` after a completed rebase but before `/push`), pass it
so the health report can distinguish expected rebase divergence from genuine
collaborator updates:

```bash
baseline_args=""
if [ -f .artifacts/rebase-stack/pre-rebase-state.json ] \
   && bash "{scripts}/validate-baseline.sh" \
        .artifacts/rebase-stack/pre-rebase-state.json \
        --context .artifacts/rebase-stack/context.json >/dev/null 2>&1; then
  baseline_args="--baseline .artifacts/rebase-stack/pre-rebase-state.json"
fi
bash "{scripts}/stack-status.sh" $baseline_args \
  < .artifacts/rebase-stack/context.json
echo "status exit: $?"
```

Only exit codes 0 and 1 are report verdicts. **On any other exit — 2 (bad
input) or 3 (a remote could not be fetched) — there is no health report, so
stop before the snapshot and before the rebase.** Relay the script's stderr
verbatim and do not continue; a drift number computed from stale refs is
exactly what this phase must not act on.

**If the exit code is 0** the stack is already level with its base. Do not
rebase. "Level with the base" says nothing about the published copies, though,
so do not offer `/push` until the divergence check below has run — the remote
may have moved since the last rebase even though the base has not.

Count, for every branch, the commits on each side of its published copy. Bind
the names to shell variables rather than splicing them into the command text:
a branch name is user-controlled and must never be parsed as shell syntax.

```bash
snapshot=.artifacts/rebase-stack/pre-rebase-state.json
push_remote=$(jq -r '.pushRemote' .artifacts/rebase-stack/context.json)
jq -r '.branches[].name' .artifacts/rebase-stack/context.json | while read -r branch; do
  if git show-ref --quiet --verify "refs/remotes/${push_remote}/${branch}"; then
    ahead=$(git rev-list --count "${push_remote}/${branch}..${branch}")
    behind=$(git rev-list --count "${branch}..${push_remote}/${branch}")
    # When a pre-rebase snapshot with published tips exists, classify
    # the divergence rather than treating all behind>0 as collaborator.
    divergence_class=""
    if [ "$behind" -gt 0 ] && [ -f "$snapshot" ] \
       && bash "{scripts}/validate-baseline.sh" "$snapshot" \
              --context .artifacts/rebase-stack/context.json >/dev/null 2>&1; then
      saved_tip=$(jq -r --arg b "$branch" '.publishedTips[$b] // "ABSENT"' "$snapshot")
      current_tip=$(git rev-parse --verify --quiet "refs/remotes/${push_remote}/${branch}")
      if [ "$saved_tip" != "ABSENT" ] && [ "$saved_tip" = "$current_tip" ]; then
        divergence_class=" (rebase)"
      elif [ "$saved_tip" != "ABSENT" ]; then
        divergence_class=" (UPDATED)"
      fi
    fi
    printf '%-28s ahead=%s behind=%s%s\n' "$branch" "$ahead" "$behind" "$divergence_class"
  else
    printf '%-28s unpublished\n' "$branch"
  fi
done
```

- **Every branch `behind=0`** — the published copies are either identical or
  strictly behind the local tips. Tell the user:

  > The stack is already rebased onto `{base-remote}/{base}`. Nothing to do.
  > Run `/validate` to re-run the checks, then `/push` to publish.

  Suggest `/push` only after `/validate`: the record `/push` reads is pinned to
  branch SHAs, and a stale or missing one sends the user straight back.

- **Any branch shows `(UPDATED)` or has `behind>0` without a baseline** —
  that branch has unexpected divergence: the remote was updated by someone
  else since the last rebase. **Do not offer `/push`.** Report which branches
  diverged and by how much, show the remote-only commits as below, and stop.

- **All `behind>0` branches show `(rebase)`** — the remote tips match the
  pre-rebase snapshot. The divergence is the expected result of rebasing
  locally. The remote has not changed. Proceed as if `behind=0`.

**If any layer has genuine remote changes** (`UPDATED` classification, or
`behind>0` without a baseline to classify), stop before touching history. The
remote has commits you do not, and rebasing then force-pushing would destroy
them. Do **not** reach for `gh stack sync`: it rebases and pushes in one step,
skipping this workflow's snapshot, validation, and push confirmation. Show the
remote-only commits without publishing anything — again through variables,
never by splicing the name into the command:

```bash
ctx=.artifacts/rebase-stack/context.json
push_remote=$(jq -r '.pushRemote' "$ctx")
jq -r '.branches[].name' "$ctx" | while read -r branch; do
  git log --oneline "${branch}..${push_remote}/${branch}" --
done
```

Then let the user decide how to reconcile — cherry-pick them onto the layer
that owns them, or accept losing them deliberately — and re-run `/start` from
the top once the stack is reconciled.

Otherwise show the table and continue. Call out, from the `NOTES` column:

- **Commits already in the base.** Name them. The rebase will drop them; that
  is correct behavior, not data loss.
- **Empty layers** (`COMMITS` is 0). Suggest removing them
  (`gh stack unstack --local`, then re-`init` without that branch) rather than
  carrying a branch that would open an empty PR.

## Step 3: Snapshot Before Rewriting History

The snapshot records the pre-rebase state and must not be silently overwritten
by a rerun. If `/start` is rerun after a completed rebase but before `/push`,
the existing snapshot still contains the correct pre-rebase tips; overwriting
it would silently accept whatever the remote shows now.

- **First run** (no existing snapshot): `save` writes the snapshot normally.
- **Rerun after completed rebase** (valid snapshot exists): `save` refuses and
  exits 2. This is correct — the existing baseline is still needed for `/push`.
- **Explicit new operation**: Pass `--force` to deliberately discard the
  existing baseline and start fresh (e.g. after a successful `/push` cleared
  the snapshot, or when the user explicitly wants to start over).

```bash
bash "{scripts}/snapshot.sh" save \
  < .artifacts/rebase-stack/context.json
echo "snapshot exit: $?"
```

This writes `.artifacts/rebase-stack/pre-rebase-state.json` with every branch
tip and commit identity. It is the recovery path if the rebase goes wrong and
`gh stack rebase --abort` is no longer available.

**On exit 2 because a valid snapshot already exists:** The rebase was already
started or completed. Do not pass `--force` automatically — tell the user:

> A pre-rebase baseline already exists. This means a previous `/start` already
> captured the branch tips. If the rebase is complete, run `/validate` then
> `/push` to publish. To discard the existing baseline and start over, confirm
> then run:
>
> ```bash
> bash "{scripts}/snapshot.sh" save --force \
>   < .artifacts/rebase-stack/context.json
> ```

**On any other non-zero exit, stop. Do not rebase.** The snapshot is the only
record of the pre-rebase tips, so a rebase started without it has no recovery
path and Step 5 cannot tell a dropped commit from a rebased one. Relay the
script's stderr verbatim, say that nothing was rewritten, and let the user fix
the cause — most often an unwritable `.artifacts/` directory or a branch in
`context.json` that no longer resolves — then re-run `/start`. Never work
around it by rebasing anyway or by hand-writing `pre-rebase-state.json`.

Confirm the file exists and covers every branch before continuing:

```bash
jq -r '.branches | length' .artifacts/rebase-stack/pre-rebase-state.json
jq -r '.branches | length' .artifacts/rebase-stack/context.json
```

The two counts must match. If they do not, treat it as a snapshot failure and
stop on the same terms.

Offer `rerere` once, and set it only if the user agrees:

> Enable `git config rerere.enabled true`? It replays one conflict resolution
> across the upper layers, which removes most of the repeated work in a stack
> rebase. It changes git behavior for this repository.

## Step 4: Rebase the Whole Stack

```bash
base_remote=$(jq -r '.baseRemote' .artifacts/rebase-stack/context.json)
gh stack rebase --remote "$base_remote"
echo "rebase exit: $?"
```

Capture the full output. Branch on the exit code:

| Exit | Action |
|------|--------|
| 0 | Go to Step 5. |
| 3 | Conflict — go to "Conflict handling" below. |
| 7 | A rebase was already in progress. Run `/continue` instead. |
| other | Stop. Report the exit code and the full stderr. Do not retry. See the exit-code table in `../guidelines.md`. |

### Conflict handling

Gather the facts before saying anything. A rebase is in progress, so each of
these resolves — no error suppression is needed or wanted, and an unexpected
error is itself information:

```bash
git rebase --show-current-patch | head -20
git diff --name-only --diff-filter=U
git log --oneline -1 REBASE_HEAD
```

Check whether **this one commit** already landed in the base — that changes the
correct resolution entirely. Bound `git cherry` with `REBASE_HEAD^` so it
compares only the conflicting commit; without the limit it walks every commit
reachable from `REBASE_HEAD` and can report an ancestor as already-upstream:

```bash
ctx=.artifacts/rebase-stack/context.json
base_remote=$(jq -r '.baseRemote' "$ctx")
base=$(jq -r '.trunk' "$ctx")
git cherry "${base_remote}/${base}" REBASE_HEAD REBASE_HEAD^
```

One line of output. A leading `-` means this commit's change is already in the
base and `git rebase --skip` is correct. A leading `+` means it is genuinely
new — resolve the conflict, never skip.

Present the conflicting commit, the file list, and which of the three cases in
`../guidelines.md` → "Conflict Handling" each file falls into. Then ask:

> Conflict on `{file list}` while replaying `{commit subject}`.
> My read: `{per-file classification}`.
>
> - **Fix it for me** — I apply the classification above and continue.
> - **I'll fix it** — you resolve, `git add` the files (do not commit), then run `/continue`.
> - **Abort** — I run `gh stack rebase --abort` and every branch returns to its pre-rebase tip.

**Stop here.** Wait for the answer. Do not edit a file first.

If the user chooses "fix it for me", apply only the resolutions you described,
then:

```bash
git diff --name-only --diff-filter=U   # must print nothing
base_remote=$(jq -r '.baseRemote' .artifacts/rebase-stack/context.json)
gh stack rebase --continue --remote "$base_remote"
echo "continue exit: $?"
```

Re-enter the exit-code table above on each result.

## Step 5: Verify Nothing Was Lost

```bash
bash "{scripts}/snapshot.sh" verify \
  < .artifacts/rebase-stack/context.json
echo "verify exit: $?"
```

Only exit codes 0 and 1 are verdicts.

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Every pre-rebase commit is still reachable. | Go to Step 6. |
| 1 | One or more pre-rebase commits are gone. | Account for each one below. |
| other | No verdict was produced — 2 is a missing snapshot or bad input, and anything else is unexpected. | **Fatal. Stop.** Relay the script's stderr verbatim, report the exit code, and do not continue to `/validate` or `/push`. |

Fail closed on an unexpected exit: the history has already been rewritten at
this point, and "the check did not run" is not "the check passed". Never treat
a non-0/1 exit as a pass, and never re-run the rebase to try to clear it.

On exit 1: list the missing commits and account for each one. The legitimate
cause is that the change already landed in `{base}`.

Confirm that **by patch identity, never by subject**. A subject search matches
any unrelated base commit that happens to share the message, and an
accepted-by-subject commit is a silently dropped change. The script printed the
pre-rebase SHA next to each missing commit; that object is still in the
repository, so ask git directly whether its patch is upstream:

```bash
ctx=.artifacts/rebase-stack/context.json
base_remote=$(jq -r '.baseRemote' "$ctx")
base=$(jq -r '.trunk' "$ctx")
missing_sha='<full SHA printed by snapshot.sh>'
git cherry "${base_remote}/${base}" "$missing_sha" "${missing_sha}^"
```

One line. A leading `-` means this exact patch is already in the base — the
commit is accounted for. A leading `+` means it is not; the change was dropped.

If the commit does not resolve (it was never recorded with a usable parent) or
`git cherry` cannot be run against it, compare patch-ids explicitly:

```bash
git show "$missing_sha" | git patch-id --stable | cut -d' ' -f1
git log --format=%H "${base_remote}/${base}" -50 \
  | while read -r c; do git show "$c" | git patch-id --stable; done \
  | cut -d' ' -f1
```

A matching patch-id accounts for the commit. **If patch equivalence cannot
establish the match either way, the commit is unaccounted for** — do not accept
it on a subject match. Say so plainly and ask the user to review that commit
before anything continues.

If a missing commit cannot be accounted for, stop and show the recovery plan:

```bash
bash "{scripts}/snapshot.sh" restore-plan
```

Do not proceed to `/validate` until the user accepts every dropped commit.

## Step 6: Hand Off

> Rebased `{N}` layers onto `{base-remote}/{base}`. Nothing pushed yet.
> Run `/validate` — it builds and tests `{validation-branch}`, the
> trunk-adjacent branch that merges first. Use `/validate --all` to cover the
> layers above it too.
