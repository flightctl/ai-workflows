---
name: push
description: Confirm, push all stack branches atomically, and create any missing PRs.
---

# Push Rebase Stack

## Process

### Step 1: Push

```bash
gh stack push --remote origin
```

`gh stack push` uses `--force-with-lease --atomic` internally: if any remote
branch was updated since the last fetch in `/validate`, the entire push is
rejected rather than partially applied.

If the exit code is non-0, stop immediately and report the exit code and
full stderr. Do not retry without re-running `/validate` (which re-fetches)
first. A lease rejection means a concurrent push occurred; any other failure
(e.g. exit 4 GitHub API error, exit 8 lock timeout) requires the user to
investigate before retrying.

### Step 2: Create Missing PRs

Using `{existing-pr}` from `/validate`, identify branches where the value is
`null`. If all branches already have open PRs, skip this step and report.

**Detect repo topology:**

```bash
gh repo view --json isFork,owner,parent --jq '{isFork: .isFork, owner: .owner.login, parent: .parent.nameWithOwner}'
```

Save `isFork`, `owner` (the fork owner login), and `parent` (upstream
`nameWithOwner`, e.g. `flightctl/flightctl`).

**If `isFork` is `true`**: skip `gh stack submit` entirely and go straight to
manual PR creation below. `gh stack submit` targets the fork itself, not the
upstream, so it would create PRs on the wrong repository.

**If `isFork` is `false`**: try Stacked PRs (works when the upstream has the
feature enabled):

```bash
gh stack submit --auto
```

- Exit code 0: PRs created and linked as a stack. Done — skip manual creation.
- Any non-zero exit (including exit code 9): fall through to manual creation.

**Manual PR creation** (always used for forks; fallback for direct clones):

For each branch in `{push-list}` where `{existing-pr}` is `null`, in
bottom-to-top order:

For a **fork**:
```bash
gh pr create \
  --head {owner}:{branch} \
  --base {pr-target} \
  --repo {parent} \
  --title "{branch-title}" \
  --draft \
  --body "Depends on: #{previous-pr-number}"
```

For a **direct clone**:
```bash
gh pr create \
  --head {branch} \
  --base {pr-target} \
  --title "{branch-title}" \
  --draft \
  --body "Depends on: #{previous-pr-number}"
```

Use `{pr-target}` from `/validate`. Omit the `Depends on:` line for the bottom
branch of the stack (it has no predecessor). Use the PR number returned by each
`gh pr create` call as `{previous-pr-number}` for the next branch.

### Step 3: Report

Summarize:
- Each branch pushed and its new tip commit
- Each PR created (number and URL) or already existing
- Any push rejection
