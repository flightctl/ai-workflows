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

```bash
bash "{scripts}/stack-status.sh" \
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
push_remote=$(jq -r '.pushRemote' .artifacts/rebase-stack/context.json)
jq -r '.branches[].name' .artifacts/rebase-stack/context.json | while read -r branch; do
  if git show-ref --quiet --verify "refs/remotes/${push_remote}/${branch}"; then
    ahead=$(git rev-list --count "${push_remote}/${branch}..${branch}")
    behind=$(git rev-list --count "${branch}..${push_remote}/${branch}")
    printf '%-28s ahead=%s behind=%s\n' "$branch" "$ahead" "$behind"
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

- **Any branch `behind>0`** — that branch has unexpected divergence: the remote
  was updated by someone else since the last rebase. **Do not offer `/push`.**
  Report which branches diverged and by how much, show the remote-only commits
  as below, and stop.

**If any layer is behind its published copy** (`-N` in `VS-PUBLISHED`, or
`behind>0` above), stop before touching history. The remote has commits you do
not, and rebasing then force-pushing would destroy them. Do **not** reach for
`gh stack sync`: it rebases and pushes in one step, skipping this workflow's
snapshot, validation, and push confirmation. Show the remote-only commits
without publishing anything — again through variables, never by splicing the
name into the command:

```bash
branch="{branch}"; push_remote="{push-remote}"
git log --oneline "${branch}..${push_remote}/${branch}"
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

```bash
bash "{scripts}/snapshot.sh" save \
  < .artifacts/rebase-stack/context.json
echo "snapshot exit: $?"
```

This writes `.artifacts/rebase-stack/pre-rebase-state.json` with every branch
tip and commit identity. It is the recovery path if the rebase goes wrong and
`gh stack rebase --abort` is no longer available.

**On any non-zero exit, stop. Do not rebase.** The snapshot is the only record
of the pre-rebase tips, so a rebase started without it has no recovery path
and Step 5 cannot tell a dropped commit from a rebased one. Relay the script's
stderr verbatim, say that nothing was rewritten, and let the user fix the
cause — most often an unwritable `.artifacts/` directory or a branch in
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
gh stack rebase --remote {base-remote}
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
git cherry {base-remote}/{base} REBASE_HEAD REBASE_HEAD^
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
gh stack rebase --continue --remote {base-remote}
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
# {missing-sha}: the 12-char SHA snapshot.sh printed for the missing commit.
git cherry {base-remote}/{base} {missing-sha} {missing-sha}^
```

One line. A leading `-` means this exact patch is already in the base — the
commit is accounted for. A leading `+` means it is not; the change was dropped.

If the commit does not resolve (it was never recorded with a usable parent) or
`git cherry` cannot be run against it, compare patch-ids explicitly:

```bash
git show {missing-sha} | git patch-id --stable | cut -d' ' -f1
git log --format=%H {base-remote}/{base} -50 \
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
