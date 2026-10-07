---
name: continue
description: Resume a paused gh stack rebase after the user resolved a conflict.
---

# Continue Rebase Stack

Repeatable. Each run advances the rebase to the next conflict or to completion.
Local only — nothing is pushed.

## Step 1: Preflight

Follow `preflight.md` with `--allow-rebase-in-progress`.

If preflight reports `rebaseInProgress: false`, no rebase is paused:

```bash
jq -r '.rebaseInProgress' .artifacts/rebase-stack/context.json
```

Tell the user there is nothing to continue and point them at `/start`, which
reports where the stack actually stands before it rebases anything. Do not
start a new rebase from here.

## Step 2: Confirm the Conflict Is Resolved

```bash
git diff --name-only --diff-filter=U
git diff --cached --name-only
```

- First command prints files: conflicts remain. List them and stop. The user
  must resolve and `git add` each one.
- First command empty and second also empty: nothing was staged. The commit
  resolved away to nothing, which means its change is already present in the
  base. Drop it:

  ```bash
  git rebase --skip
  echo "skip exit: $?"
  ```

  Tell the user which commit was dropped and why. Do not hand-craft a commit to
  preserve the slot: a commit made during the rebase breaks `gh stack`'s
  bookkeeping, and an empty one records nothing anyway.

  **`git rebase --skip` does not stop at the skipped commit — it replays the
  rest of the layer.** It can therefore finish the rebase outright or stop
  again on the next conflict, and Step 3 is correct in neither case. Find out
  which happened before going anywhere:

  ```bash
  if [ -d "$(git rev-parse --git-path rebase-merge)" ] ||
     [ -d "$(git rev-parse --git-path rebase-apply)" ]; then
    echo "rebase still in progress"
  else
    echo "rebase ended"
  fi
  git diff --name-only --diff-filter=U
  ```

  - **`rebase ended`** — the skip completed the rebase. Do **not** run Step 3;
    `gh stack rebase --continue` would exit 1 on "no rebase in progress" and
    the report would read as a failure. Go straight to Step 4 and verify
    nothing was lost.
  - **`rebase still in progress` and the `git diff` prints files** — the skip
    landed on the next conflict. Do **not** run Step 3 with conflicts staged
    out: handle it exactly as `start.md` → "Conflict handling", then re-enter
    this skill at Step 2.
  - **`rebase still in progress` and the `git diff` is empty** — the replay
    paused cleanly. Re-run Step 2 from the top; if it still resolves to
    nothing staged, the next commit is empty too and is skipped the same way.
    Continue to Step 3 only once Step 2 reports "resolved".

- First command empty, second non-empty: resolved. Continue.

Reject any attempt to proceed after a `git commit` during the rebase — that
breaks `gh stack`'s bookkeeping. If `git log -1` shows a commit the user made
by hand mid-rebase, stop and report it.

## Step 3: Continue

```bash
gh stack rebase --continue --remote {base-remote}
echo "continue exit: $?"
```

| Exit | Action |
|------|--------|
| 0 | Go to Step 4. |
| 3 | Another conflict in a higher layer. Handle it exactly as `start.md` → "Conflict handling", then return here. |
| 1 | No rebase in progress, or git refused. Report the full stderr and stop. |
| other | Stop and report. See the exit-code table in `../guidelines.md`. |

When a second or third layer conflicts on the same hunk, say so explicitly:

> This is the same conflict as `{previous file}:{hunk}`, replayed on layer
> `{branch}`. `git config rerere.enabled true` would resolve the remaining
> layers automatically. Enable it?

## Step 4: Verify Nothing Was Lost

```bash
bash "{scripts}/snapshot.sh" verify \
  < .artifacts/rebase-stack/context.json
echo "verify exit: $?"
```

Only exit codes 0 and 1 are verdicts.

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | Every pre-rebase commit is still reachable. | Go to Step 5. |
| 1 | One or more pre-rebase commits are gone. | Handle it as described in `start.md` Step 5: account for each missing commit or stop. |
| other | No verdict was produced — 2 is a missing snapshot or bad input, and anything else is unexpected. | **Fatal. Stop.** Relay the script's stderr verbatim, report the exit code, and do not hand off. |

Fail closed on an unexpected exit, exactly as `start.md` Step 5 does: the
history is already rewritten, so a check that did not run is not a check that
passed.

## Step 5: Hand Off

> Rebase complete. Run `/validate` — it builds and tests
> `{validation-branch}`, the trunk-adjacent branch that merges first. Use
> `/validate --all` to cover the layers above it too.
