# Rebase Stack Workflow

Rebases a `gh stack`-tracked chain of branches onto its updated base, guides
conflict resolution layer by layer, verifies that no commit was silently
dropped, validates the trunk-adjacent branch (or every branch, on request), and pushes
every branch with fork-aware PR creation.

## When to Use It — and When Not To

Use it when you have a **tracked stack of two or more dependent branches** and
the base branch has moved.

Do **not** use it when:

| Situation | Use instead |
|-----------|-------------|
| Rebasing a single branch onto `main` | `git fetch <remote> && git rebase <remote>/main` |
| The branches are not in a stack yet | `gh stack init --base <base> <bottom> … <top>` first |
| You only want to see the stack | `gh stack view --json` |

The workflow enforces this itself: `scripts/preflight.sh` exits 2 when
`gh stack view --json` reports "not in a stack", and every phase stops there.
It will never initialize a stack for you.

## Hard Requirements

| Requirement | Behavior if missing |
|-------------|---------------------|
| `git` | Refuse (exit 8) |
| `jq` | Refuse (exit 8) |
| `gh` (GitHub CLI), authenticated | Refuse (exit 8 / exit 4) |
| `gh stack` extension | **Refuse (exit 8).** Never installed automatically, never emulated with `git rebase --onto`. |
| A tracked stack | **Refuse (exit 2).** Never initialized automatically. |

Install the extension yourself once:

```bash
gh extension install github/gh-stack
```

> `gh stack submit` additionally needs the Stacked PRs feature enabled on the
> upstream repository. If it exits 9, `/push` opens the PRs with `gh pr create`
> instead. That is PR plumbing, not a `gh stack` fallback — the extension
> itself is still mandatory.

## Remote Resolution — `origin` Is Not Assumed

The workflow resolves two remotes separately, because in a fork workflow they
differ:

| Name | What it is | Resolution order |
|------|------------|------------------|
| `{base-remote}` | Hosts the base branch the stack targets. Used for fetch and `gh stack rebase --remote`. | base branch's upstream tracking ref → `branch.<base>.remote` → the remotes that carry the ref (`upstream` then `origin` as tiebreak) → the single configured remote |
| `{push-remote}` | Where the stack's branches are published. Used for `gh stack push --remote`. | `remote.pushDefault` → the current branch's `@{push}` → the single configured remote → `{base-remote}` |

If either is ambiguous, preflight exits 9 and the workflow asks you instead of
guessing. Every `gh stack` call passes `--remote` explicitly.

## Validation Policy — Trunk-Adjacent by Default, `--all` on Request

The **entire** stack is always rebased and every branch is always pushed. Only
the amount of linting and testing changes.

| | `/validate` (default) | `/validate --all` |
|---|---|---|
| Branches rebased | all | all |
| Branches linted and tested | the trunk-adjacent branch only | every branch, bottom to top |
| Stops at | the single failure | the first failing layer |
| Worktrees created | none | one per branch, removed afterwards |
| Branches pushed | all | all |
| Cost | one suite run | N suite runs |

The default is the trunk-adjacent branch — the layer closest to the base, the
one that merges first — so one run exercises the change that lands soonest. It
does not exercise any layer above it.

Reach for `--all` when the layers above the bottom have to be covered:

- the stack's final state must be exercised before pushing;
- an upper layer must be independently releasable or mergeable;
- the trunk-adjacent layer passed and you want the layers above it attributed
  individually rather than left to per-PR CI.

Both modes state what they covered. In the default mode the overview marks the
other layers `not run`, never `pass`, and per-PR CI is the first independent
check on them after `/push`.

If the suite needs dependencies installed in the main working tree
(`node_modules`, `vendor`, `.venv`), worktrees will not have them — `/validate`
switches to `--mode checkout`, which checks each branch out in turn and
restores the starting branch afterwards.

## Phase Flow

```text
/start ──► already up to date ──► done
       │
       ├─── clean ─────────────► /validate ──► /push ──► done
       └─── conflict ──► (resolve) ──► /continue ──┐
                                                    │
                          conflict ◄────────────────┤
                          clean ──► /validate ──► /push ──► done
```

## Commands

| Command | What it does |
|---------|--------------|
| `/start` | Preflight, health report, snapshot every branch tip, then `gh stack rebase --remote {base-remote}` across the whole stack. Exits early if nothing needs rebasing. Local only. |
| `/continue` | Resume a paused rebase after you staged the resolution. Repeatable. Local only. |
| `/validate` | Re-fetch, re-check health, discover the project's lint and test commands, run them on the trunk-adjacent branch, print the push overview. |
| `/validate --all` | Same, but runs the suite on every branch bottom-to-top, stopping at the first failing layer. Use when the layers above the bottom must be exercised too. |
| `/push` | Confirm, `gh stack push --remote {push-remote}`, then open PRs for branches that lack one, fork-aware. |

## The Health Report

`/start` prints this before it snapshots or rebases anything, and `/validate`
prints it again after re-fetching. It is read-only; seeing it never commits you
to the rebase.

```text
Stack: (main) <- story-1 <- story-2 <- story-3
Base remote: upstream (upstream tracking ref of main)   Push remote: origin (remote.pushDefault)
Base drift: upstream/main is 14 commit(s) ahead of your local main

LAYER                        COMMITS    STALE     VS-PUBLISHED  PR         NOTES
----------------------------------------------------------------------------------------------
story-1                      3          YES       in sync       412
story-2                      2          YES       +2/-0         418        1 commit(s) already in main (will be dropped)
story-3 *                    0          YES       unpublished   none       EMPTY layer; no PR yet

* = currently checked out
Trunk-adjacent branch (what /validate builds by default; --all covers every layer): story-1
VERDICT: rebase needed
```

Each column exists because it changes what you should do next: `-N` under
`VS-PUBLISHED` means a force push would destroy someone's commits, an `EMPTY
layer` means you are about to open an empty PR, and `already in main` names the
commits the rebase is about to drop on purpose.

## Safety Net

`/start` records every branch tip and commit subject to
`.artifacts/rebase-stack/pre-rebase-state.json` before rewriting history.
After the rebase, `scripts/snapshot.sh verify` compares the two and reports any
commit that is no longer reachable. A dropped commit is legitimate only when
that change already landed in the base, and the workflow makes you confirm each
one before continuing.

If the rebase has to be undone and `gh stack rebase --abort` is no longer
available:

```bash
bash "{scripts}/snapshot.sh" restore-plan
```

prints one `git branch -f <name> <sha>` line per branch. It only prints; you
decide whether to run them. `{scripts}` is the `scripts/` directory of this
package — resolved relative to the installed files, never a fixed path, so the
same instructions work for global, project-local, and symlinked installs.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/preflight.sh` | Hard gates (tooling, stack membership, clean tree) plus remote resolution. Emits the JSON context every phase reads. |
| `scripts/stack-status.sh` | Health table and the `rebase needed` / `up to date` verdict. Run by `/start` before it snapshots, and by `/validate` before it tests. |
| `scripts/validate-branches.sh` | Runs the lint and test commands against one or more branches, in throwaway worktrees or by sequential checkout. Backs both `/validate` modes. |
| `scripts/snapshot.sh` | `save`, `verify`, and `restore-plan` for the pre-rebase safety net. |

All four read and write only the current repository and
`.artifacts/rebase-stack/`. None of them push.

## Artifacts

Local state under `.artifacts/rebase-stack/` (gitignored):

| File | Written by | Purpose | How to clear |
|------|-----------|---------|--------------|
| `context.json` | every phase | Resolved stack, branch order, and remotes. Rewritten on each preflight. | Regenerated automatically; safe to delete. |
| `pre-rebase-state.json` | `/start` | Branch tips and commit subjects captured before the rebase. Backs `snapshot.sh verify` and `restore-plan`. | Removed by `/push` after a successful push; `rm` it to discard the safety net early. |
| `logs/{branch}.log` | `/validate` | Full lint and test output for one branch. Deleted on pass, kept on failure. | Inspect, then re-run `/validate`. |
| `validated` | `/validate` | `mode=` line plus one `<state> <branch> <sha>` line for **every** stack branch, where state is `validated` or `not-run`. `/push` refuses if any recorded SHA has moved. | Deleted at the start of each `/validate` run, rewritten only on success. |

## Push Safety

- `gh stack push --remote {push-remote}` requests `--force-with-lease --atomic`.
  A moved remote branch rejects the push. All-or-nothing holds only when the
  remote supports the `atomic` push capability — otherwise branches whose lease
  still held may already have updated, so run `/validate` after any rejection
  instead of assuming nothing moved.
- The base branch is never pushed, and neither are `main`, `master`, or
  `develop`.
- `/push` refuses to run when `.artifacts/rebase-stack/validated` is missing or
  records a SHA that no longer matches, because `/validate` performs the fetch
  that makes the lease check meaningful. The push report states whether the run
  was `mode=tip` or `mode=all`.
