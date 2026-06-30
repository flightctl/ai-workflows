# Rebase Stack Workflow

Rebases a stacked-branch chain onto an updated base branch using `gh stack`,
guides you through conflict resolution if needed, validates each branch, and
pushes all updated branches. Creates any missing PRs afterwards, with
fork-aware targeting.

## Phase Flow

```
/start ──── success ──────────────────────── /validate ──── /push ──── done
       └─── conflict ──── (resolve) ──── /continue ──┐
                                                      │
                          conflict ──── (resolve) ────┘
                          success ──────────────── /validate ──── /push ──── done
```

## Prerequisites

| Tool | Purpose |
|------|---------|
| `git` | Rebase and push operations |
| `gh` (GitHub CLI) | Stack management, PR creation |
| `gh-stack` extension | `gh extension install github/gh-stack` |
| Remote access (`origin`) | Fetch and push |

`/start` installs the extension automatically if it is not found.

> **Note:** `gh-stack` is in private preview. The CLI extension installs for
> anyone, but the Stacked PRs feature (used by `gh stack submit`) requires
> enablement on the upstream repository. If `gh stack submit` exits with
> code 9, the repo does not have it enabled — the skill falls back to
> `gh pr create` automatically.

## Stack Initialization

`/start` detects whether your branches are already tracked by `gh stack`:

- **Already tracked** (`gh stack view --json` exits 0): proceeds directly to
  the rebase.
- **Not yet tracked** (exit code 2): discovers branches from the commit graph
  (`git log --reverse --decorate origin/{base}..HEAD`), presents the
  bottom-to-top list for your confirmation, then runs:
  ```bash
  gh stack init --base {base} branch-1 branch-2 branch-3 ...
  ```
  `gh stack` adopts the existing branches and detects any open PRs automatically.

You only need to initialize once per stack. Subsequent `/start` runs skip
this step.

## Commands

| Command | When to use |
|---------|-------------|
| `/start` | Begin the rebase. Takes an optional base branch (default: `main`). Installs `gh-stack` if needed, initializes the stack if not yet tracked, then rebases. Local only — does not push. |
| `/continue` | Resume after resolving a conflict mid-rebase. Repeat as needed. Local only — does not push. |
| `/validate` | After rebase completes: re-fetches to check remote currency, runs lint and unit tests on each branch independently, and shows a branch overview table. Does not push. |
| `/push` | After validation: asks for confirmation, pushes all branches atomically with `gh stack push`, then creates any missing PRs with fork-aware targeting. |

## Usage Examples

### Typical: rebase a stack onto updated main

You have three branches stacked: `main → story-1 → story-2 → story-3 (HEAD)`.
Main has moved forward. Run:

```
/start
```

The agent checks for `gh-stack`, detects the stack (or initializes it),
then runs `gh stack rebase --remote origin`. On success it prompts you to
run `/validate`, which checks each branch and shows an overview table. Then
run `/push` to push all branches atomically with `gh stack push` after
confirmation.

### With conflicts

Same scenario, but `story-2` conflicts with a change on main:

1. `/start` — rebase stops at `story-2`, shows the conflicting files
2. Resolve conflicts. For "old version vs evolved version" conflicts (the lower
   branch was rebased and this branch has older copies): `git checkout --ours <file> && git add <file>`.
   For genuine new-code conflicts: merge manually, then `git add <file>`. Do not `git commit`.
3. `/continue` — rebase resumes; if clean, prompts you to run `/validate`
4. If another conflict appears, repeat steps 2–3
5. `/validate` — shows branch overview table after per-branch lint/test
6. `/push` — pushes after confirmation, creates any missing PRs

### Rebasing onto a branch other than main

```
/start feature/platform-upgrade
```

The agent fetches `origin/feature/platform-upgrade` and rebases onto it.

### Fork-based workflow (no Stacked PRs)

After `/push` completes the push, it tries `gh stack submit --auto`. If the
upstream repo does not have Stacked PRs enabled (exit code 9), it falls back
to `gh pr create` with `--head fork-owner:branch --repo upstream/repo`, setting
`Depends on: #N` in each PR body. All PRs target the upstream default branch.

## Artifacts

Local state written to `.artifacts/rebase-stack/` during the workflow (gitignored):

| File | Written by | Purpose | How to clear |
|------|-----------|---------|--------------|
| `validation-cache` | `/validate` | `branch:sha` pairs for each branch that has passed validation. Persists across runs; stale entries are ignored automatically when SHAs change after a rebase. | `rm .artifacts/rebase-stack/validation-cache` to force full re-validation on the next `/validate` run. |
| `logs/{branch}.log` | `/validate` | Full lint and test output per branch. Kept on failure for inspection; deleted on success. | Inspect directly; deleted automatically on the next successful `/validate` run. |

## Push Safety

- Branches are pushed **atomically**: `gh stack push` uses `--force-with-lease
  --atomic`, so if any remote branch was updated since the last fetch, the
  entire push is rejected rather than partially applied.
- Protected branches (`main`, `master`, `develop`, PR targets) are never
  pushed — only the stack branches above them.
