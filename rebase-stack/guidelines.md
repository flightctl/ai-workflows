# Rebase Stack Guidelines

## Scope — When This Workflow Applies

This workflow rebases a **chain of stacked branches tracked by `gh stack`**. It
does nothing else.

Refuse and stop when any of these is true:

| Situation | Response |
|-----------|----------|
| `gh stack view --json` exits 2 (not in a stack) | Refuse. Tell the user to run `git fetch <remote> && git rebase <remote>/<base>` for a single branch, or `gh stack init` to adopt a chain first. |
| The user asks to rebase one branch onto `main` | Refuse. This is not a stack rebase. |
| The stack has fewer than two unmerged branches | Refuse. There is nothing stacked to rebase; a plain `git rebase` is the right tool. |
| `gh stack` is not installed | Refuse. Print the install command; do not install it. |
| Every branch in the stack is already merged | Refuse. Suggest `gh stack unstack --local` to drop the local stack. |

Never initialize a stack on the user's behalf. Adopting branches into a stack
changes how every later `gh stack` command behaves and is the user's decision.

## Hard Requirements — No Fallbacks

- **`gh stack` is mandatory.** Do not install the extension, do not emulate it
  with `git rebase --onto`, do not degrade to a single-branch rebase.
- **Never test for it by exit code.** When the extension is missing, gh prints
  an advisory and exits **0** for every `gh stack` invocation, including
  `view --json`. `scripts/preflight.sh` detects it from the output instead.
- **`jq` and `gh` are mandatory.** The scripts parse `gh stack view --json`.
- **A tracked stack is mandatory.** Exit code 2 from `gh stack view --json` ends
  the run.

## Principles

- Run `scripts/preflight.sh` before every phase. It is the single source of
  truth for stack membership, branch order, and remote names.
- Prefer the exact commands in the phase files over improvised equivalents.
  Every command this workflow needs is written out; none needs to be invented.
- A rebase reorganizes history but must never silently drop a commit. Verify
  with `scripts/snapshot.sh verify` after the rebase completes.
- Stop at every decision point that needs the user. Never auto-advance a phase.

## Shared Content Rules

Read and follow `../_shared/content-rules.md` for generated-content rules. Those
standards apply to all artifacts and published output from this workflow.

## Remotes — Never Assume `origin`

There are two distinct remotes and they are frequently different:

- **`{base-remote}`** — hosts the base branch the stack targets. Resolved from
  the base branch's upstream tracking ref, then `branch.<base>.remote`, then the
  remotes that actually carry the ref. Used for fetching and for
  `gh stack rebase --remote`.
- **`{push-remote}`** — where the stack's branches are published. Resolved from
  `remote.pushDefault`, then the current branch's `@{push}` ref, then the single
  configured remote. Used for `gh stack push --remote`.

In a fork workflow `{base-remote}` is typically the upstream and `{push-remote}`
is the fork. `scripts/preflight.sh` resolves both and reports which rule fired.
If either cannot be resolved unambiguously it exits 9 — ask the user rather
than defaulting to `origin`.

Pass `--remote {name}` explicitly on every `gh stack push`, `rebase`, `sync`,
`submit`, and `link` call. Never rely on the implicit default.

## Hard Limits

- Never push to the base branch, or to `main`, `master`, or `develop`.
- Never run a destructive git operation (force push, branch deletion, reset)
  without showing the user the exact commands and the branches affected first.
- Never resolve a conflict without the user's explicit choice.
- Never push without re-running `/validate` first — `/validate` performs the
  fetch that makes `--force-with-lease` meaningful.

## Validation Policy

The whole stack is always rebased. How much of it gets linted and tested is the
user's choice, and `/validate` has exactly two modes.

**Default — the trunk-adjacent branch only.** `scripts/preflight.sh` reports it
as `validationBranch`: the branch closest to the base, the layer that merges
first. One suite run exercises the layer that lands soonest, which is why this
is the default.

**`/validate --all` — every branch, bottom to top.** Each layer is validated in
its own worktree (or by sequential checkout when the suite needs dependencies
installed in the main tree). Validation stops at the first failing layer,
because every layer above it contains that layer's commits.

Never silently choose for the user:

- Echo the resolved mode before running anything.
- In the default mode, label the other layers `not run` in the overview — never
  `pass` — and mention that `--all` covers them.
- Recommend `--all` whenever the layers above the bottom matter: the stack's
  final state has to be exercised before pushing, an upper layer must stand on
  its own, or a failure needs to be attributed to a specific layer.
- The default proves only that the trunk-adjacent layer builds and passes. It
  says nothing about any layer above it, including the stack's final state.
  Per-PR CI is the first check that covers those, after `/push`.

## Conflict Handling

- On conflict, show the commit that caused it and the conflicting files, then
  ask whether the user wants you to resolve it or will do it themselves. Do not
  touch a file before they answer.
- Classify each conflicting file before resolving:
  - **Stale copy** — this layer carries an older version of a commit the layer
    below already evolved. Take the rebase's `--ours` (the onto side, that is,
    the updated lower layer): `git checkout --ours <file> && git add <file>`.
  - **Already upstream** — the whole conflicting commit already landed in the
    base branch. Drop it with `git rebase --skip` and say so explicitly.
  - **Genuine divergence** — new code on both sides. Show the conflict hunks and
    merge by hand. Never guess.
- After `git add`, do **not** `git commit`. Run `/continue`.
- `git config rerere.enabled true` makes a conflict that repeats across layers
  resolve itself. Recommend it, but set it only with the user's agreement — it
  changes git behavior beyond this workflow.
- Never offer `gh stack sync` as a shortcut. It rebases *and* pushes in one
  step, bypassing this workflow's snapshot, validation, and push confirmation.
- Escape hatch: `gh stack rebase --abort` restores every branch.
  `scripts/snapshot.sh restore-plan` prints per-branch recovery commands when
  the abort is no longer possible.

## Error Handling

Map each `gh stack` exit code to an action. Never retry blindly.

| Code | Meaning | Action |
|------|---------|--------|
| 2 | Not in a stack | Refuse the run (see Scope). |
| 3 | Rebase conflict | Enter conflict handling. |
| 4 | GitHub API failure | Report `gh auth status` output; ask before retrying. |
| 5 | Invalid arguments | A command in this workflow is wrong; report it, do not improvise. |
| 6 | Disambiguation required | Ask the user to run `gh stack checkout <branch>`. |
| 7 | Rebase already in progress | Run `/continue`, or `gh stack rebase --abort`. |
| 8 | Stack file locked | Another `gh stack` process is writing; wait about 5s and retry once. |
| 9 | Stacked PRs unavailable | Use `gh pr create` for PR creation only. |
| 10 | Modify recovery required | Run `gh stack modify --abort`. |

Report failures with the exit code, the command, and the log path. Do not dump
full logs into chat.

## Push Safety

- `gh stack push --remote {push-remote}` requests `--force-with-lease --atomic`.
  All-or-nothing holds only when the remote supports the `atomic` capability;
  otherwise branches whose lease still held may already have updated. Never
  report "nothing was pushed" from a non-zero exit alone.
- Present the complete branch list and wait for explicit confirmation.
- A lease rejection means someone else pushed. Re-run `/validate` to re-fetch
  and re-read stack health, so you see what actually landed before retrying.
  Never retry with `--force`.

## PR Creation

- After pushing, create PRs only for branches that `gh stack view --json`
  reports without one.
- Direct clone: try `gh stack submit --auto`. Exit 9 means Stacked PRs are not
  enabled on the repository; use `gh pr create` instead.
- Fork: skip `gh stack submit` entirely — it targets the fork, not the upstream.
  Use `gh pr create --head {fork-owner}:{branch} --repo {parent}`.
- Express ordering with `Depends on: #N` in each PR body. The bottom branch has
  no predecessor.
