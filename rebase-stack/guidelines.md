# Rebase Stack Guidelines

## Principles

- Work branch-by-branch and confirm state at each step before proceeding.
- Prefer explicit commands over assumptions — always check exit codes and capture output.
- Preserve the user's intent: rebasing reorganizes history but must not silently drop commits.
- Keep the user informed at every decision point that requires their input.

## Hard Limits

- Never push directly to `main`, `master`, `develop`, or any branch designated as a PR target.
- Never run a destructive git operation (force push, branch deletion) without presenting the
  scope to the user first.
- Never resolve a conflict without the user's explicit choice (fix-for-me vs. manual).
- Never skip validation for a branch unless the cache holds a matching `branch:sha` entry
  from a previous passing run. Any branch whose SHA has changed must be re-validated.

## Safety Rules

- **Push with `gh stack push --remote origin`.** It uses `--force-with-lease --atomic`
  internally, so if the remote was updated since your last fetch the entire push is
  rejected rather than partially applied.
- **Never push protected branches.** Do not push to `main`, `master`, `develop`, or any
  branch that is the PR target — only push the stack branches above it.
- **Confirm before pushing.** Always present the full list of branches to be pushed and
  wait for explicit user confirmation.
- **Stop on unexpected state.** If git or `gh stack` output is ambiguous or unexpected,
  stop and report rather than guess.

## Conflict Handling

- When a conflict occurs, show the user the commit that caused it and the conflicting files,
  then ask whether they want the agent to fix it or prefer to fix it themselves. Do not
  attempt resolution before the user answers.
- **Conflict strategy:** When the conflict is "old version vs evolved version" (a lower
  branch was rebased and this branch carries older copies of the same commits), take
  `--ours`. In a rebase, `--ours` is the onto-branch (the lower branch's updated tip),
  so it keeps the evolved version and discards the stale copy:
  ```bash
  git checkout --ours <file>
  git add <file>
  ```
  For conflicts involving genuinely new code unique to this branch, manually merge both sides.
- Instruct the user to resolve, `git add` the resolved files (do NOT `git commit`),
  then run `/continue`.
- `gh stack rebase --continue` resumes from where the rebase paused — do not restart
  from scratch.

## Quality

- Every branch must pass its project's lint and test suite before being pushed.
- The validation cache (`branch:sha`) ensures previously validated branches are not
  re-run unless their tip SHA changed — do not skip cache checks.
- Report validation failures with the log file path; do not dump the full log to chat.
- A clean `git status` (no uncommitted changes) is required before starting a rebase.

## Escalation

- If `gh stack` output is ambiguous or exits with an unexpected code, stop and report
  the full output before taking any further action.
- If a conflict cannot be cleanly resolved with `--ours`, show the conflict markers to
  the user and wait for their decision.
- If a push is rejected despite `--force-with-lease`, report the rejection and ask the
  user how to proceed — do not retry automatically.

## PR Creation

- After pushing, check which branches lack an open PR (use `gh stack view --json`).
- For repos with Stacked PRs enabled: try `gh stack submit --auto`. If it succeeds, done.
- For forks or repos where Stacked PRs are not enabled (exit code 9): create PRs manually
  with `gh pr create`, setting `--head owner:branch` and `--repo upstream` for forks.
- All PRs in a fork-based workflow target the upstream default branch (PR Target), not
  each other's branches. Use `Depends on: #N` in the PR body to express ordering.
