---
name: validate
description: Verify the rebase is complete, check remote currency, validate each branch, and show a push overview.
---

# Validate Rebase Stack

## Process

### Step 1: Verify Rebase Is Complete

```bash
git rebase --show-current-patch 2>&1
```

If this outputs patch content (rather than an error saying no rebase is in
progress), a rebase is still ongoing. Tell the user to resolve any remaining
conflicts and run `/continue` before validating.

### Step 2: Collect Stack State

```bash
gh stack view --json
```

If the exit code is not 0, stop and report the exit code and stderr. Do not
proceed. For exit code 6 (branch belongs to multiple stacks), instruct the
user to run `gh stack checkout <specific-branch>` to resolve the disambiguation
before retrying.

From the JSON:

- Collect the `name` of every branch where `isMerged` is `false`, in the order
  they appear in the `branches` array (bottom to top). Save this as
  **`{push-list}`**.
- Note the `trunk` value. Save this as **`{pr-target}`** — used as the PR base
  in `/push`.
- For each branch, note whether a `pr` object is present and its PR number if
  so, or `null` if absent. Save this as **`{existing-pr}`** per branch — used
  in `/push` to skip branches that already have an open PR.

### Step 3: Refresh Remote and Detect Changes

Fetch to refresh remote-tracking refs (needed for tip comparison and so that
`gh stack push --force-with-lease` has accurate data):

```bash
git fetch origin
```

For each branch in `{push-list}`, compare local and remote tip SHAs:

```bash
git rev-parse {branch}
git rev-parse origin/{branch} 2>/dev/null || echo "(not on remote)"
```

Record whether the local tip differs from `origin/{branch}`. Save this as
**`{tip-changed}`** per branch (`true` / `false`). Branches not yet on the
remote count as changed.

There is no need to block on remote-ahead commits — after a rebase the remote
naturally holds the pre-rebase history, which diverges from the new local tips.
`gh stack push --force-with-lease --atomic` provides the real safety net: if
someone pushes to origin between now and `/push`, the entire push is rejected.

### Step 4: Determine Validation Range

Each branch will become an independent PR that CI runs against on its own.
Because branches are cumulative, a lower branch changing affects the state of
every branch above it — even if those upper branches' own commits didn't move.

The cache (`.artifacts/rebase-stack/validation-cache`) records every branch
that has passed validation as `branch:sha` lines. It persists across runs.
After a rebase, branch SHAs change and the stale cache entries are ignored
automatically — no explicit clear is needed.

```bash
cat .artifacts/rebase-stack/validation-cache 2>/dev/null
```

Scan `{push-list}` bottom-to-top. For each branch:

```bash
git rev-parse {branch}
```

Find `{first-to-validate}` — the lowest branch where either:
- the branch is not in the cache, or
- its current SHA differs from the cached SHA.

**All branches strictly below `{first-to-validate}`** are skipped and marked
`— skip (already validated)`. Do not apply the cache check to branches at or
above `{first-to-validate}` — they must be validated unconditionally because
their cumulative base has changed.

If every branch is cached with a matching SHA: skip all validation, mark
every branch `— skip (already validated)`, and proceed to Step 8.

### Step 5: Set Up Worktrees

Discover the validation commands once from the project's `AGENTS.md`,
`CLAUDE.md`, or `Makefile` (lint and unit tests at minimum). If none of
those sources document the commands, ask the user before proceeding.

Get the currently checked-out branch in the main working tree:

```bash
git branch --show-current
```

For each branch in the validation range, set up its work directory:

- If the branch is the currently checked-out branch in the main working tree:
  use the repo root as `{work-dir}` for this branch. No worktree needed.
- Otherwise, create a worktree (branch name with `/` replaced by `-`) and
  save its path as `{work-dir}` for this branch:

  ```bash
  mkdir -p .artifacts/rebase-stack/worktrees
  git worktree add .artifacts/rebase-stack/worktrees/{branch-safe-name} {branch}
  # {work-dir} = .artifacts/rebase-stack/worktrees/{branch-safe-name}
  ```

  If `git worktree add` fails for any reason other than "already checked out
  in the main working tree": stop, report the error, and ask the user to run
  `git worktree list` to inspect and `git worktree remove --force` to clean up
  any stale entries before retrying.

### Step 6: Run Validation

Always capture full output to a log file — never pipe to `tail`, `head`, or
any truncating filter. On pass, show a one-line summary. On failure, report
the log file path so the user can inspect it; do not dump the full contents
into the chat.

For each branch in the validation range, bottom-to-top:

```bash
mkdir -p .artifacts/rebase-stack/logs
(cd {work-dir} && {lint command} && {unit test command}) > .artifacts/rebase-stack/logs/{branch-safe-name}.log 2>&1
exit_code=$?
```

- Exit 0: show a one-line pass summary and append to cache:
  ```bash
  echo "{branch}: ✓ pass"
  echo "{branch}:$(git rev-parse {branch})" >> .artifacts/rebase-stack/validation-cache
  ```
- Non-zero: report the failure and log path, then proceed to Step 7:
  ```
  {branch}: ✗ fail — see .artifacts/rebase-stack/logs/{branch-safe-name}.log
  ```

### Step 7: Clean Up and Report

Remove log files created in Step 6 on success only — on failure they are
kept for the user to inspect:

```bash
# only if all branches passed:
rm -f .artifacts/rebase-stack/logs/{branch-safe-name}.log
# repeat for each branch in the validation range
```

Remove all worktrees created in Step 5 (always, regardless of outcome):

```bash
git worktree remove --force .artifacts/rebase-stack/worktrees/{branch-safe-name}
# repeat for each worktree created (skip branches that used the main working tree)
```

**On any failure:** the cache already contains all branches that passed.
Tell the user:

> Validation failed on `{failing-branch}`.
> Full output: `.artifacts/rebase-stack/logs/{branch-safe-name}.log`
> Fix the issue, then run `/validate` again.
> Branches that already passed will be skipped automatically.

**Stop here.** Do not proceed to Step 8.

**On success:** the cache is kept — subsequent `/validate` runs will skip
already-validated branches automatically.

### Step 8: Build Push Overview

For each branch in `{push-list}`, get its new local tip:

```bash
git log --oneline -1 {branch}
```

And the current remote tip for comparison (remote-tracking ref was just
refreshed by the fetch in Step 3):

```bash
git log --oneline -1 origin/{branch} 2>/dev/null || echo "(not on remote)"
```

Present the overview as a table. Use `✓ pass` for validated branches,
`— skip` for branches skipped because they and everything below them were
unchanged:

```
Branch          Validation     New tip (local)                  Remote tip (before push)
────────────────────────────────────────────────────────────────────────────────────────
story-1         — skip         abc1234 EDM-4100: add routing    abc1234 (same)
story-2         ✓ pass         def5678 EDM-4200: add handler    e3f1a2b EDM-4200: ... (old)
story-3 (HEAD)  ✓ pass         ghi9012 EDM-4300: add test       cba3210 EDM-4300: ... (old)
```

Then tell the user:

> All branches validated. Run `/push` to push and create any missing PRs.
