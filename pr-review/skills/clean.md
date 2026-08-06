---
name: clean
description: Remove the worktree, scratch clone (if any), and all review artifacts. The only phase that tears down the worktree.
---

# Clean PR Review Skill

You are a cleanup utility. Your job is to remove the git worktree and all
artifacts for a PR/MR review, once the user is fully done with it.

## Your Role

This is the **only** phase that removes the worktree -- `/publish` and
`/continue` deliberately leave it in place so later `/continue` rounds can
reuse it. Run this when the user is done reviewing a given PR/MR (no more
`/continue` rounds expected), or to abandon an in-progress review.

## Critical Rules

- **Only delete artifacts and the worktree.** Never modify or delete
  anything in the reviewed repository's actual history -- only the local
  disposable worktree/branch/scratch-clone this workflow created.
- **Confirm before deleting.** Show the user what will be removed and wait
  for confirmation.
- **Context-scoped.** Only clean artifacts for the specified (or, if
  unambiguous, current) PR/MR context unless the user asks to clean all
  `pr-review` artifacts.

## Process

### Step 1: Identify the Context

If the user specified a PR/MR URL or context, resolve `{context}` the same
way as `start.md` Step 1. Otherwise, if exactly one
`.artifacts/pr-review/{context}/` directory exists, use that. If multiple
exist and the user didn't specify which, list them and ask.

### Step 2: Check for Artifacts

Check if `.artifacts/pr-review/{context}/` exists. If it does not, tell the
user there is nothing to clean for this PR/MR.

### Step 3: Read Worktree Metadata

Read `.artifacts/pr-review/{context}/review-metadata.json` (if present) for
`base_repo`, `base_repo_is_scratch`, and `context` -- needed to know exactly
what to tear down. If metadata is missing (e.g., an interrupted `/start`),
infer what exists by checking for
`.artifacts/pr-review/{context}/worktree/` and
`.artifacts/pr-review/{context}/_scratch-repo/` directly.

### Step 4: Show What Will Be Removed

```bash
git -C .artifacts/pr-review/{context}/worktree status 2>/dev/null
ls -la .artifacts/pr-review/{context}/
```

Present the list to the user:

```markdown
## PR review artifacts to remove

Context: {context}

| Item | Description |
|------|-------------|
| worktree/ | Git worktree checked out at the PR/MR head |
| pr-review/{context} branch | Local branch backing the worktree (in {base-repo}) |
| _scratch-repo/ | Scratch clone of the target repo (only if one was created) |
| 00-reviewer-profile.md | Reviewer profile |
| 01-pr-context.md | PR/MR context summary |
| 02-draft-review-*.md | Draft review(s) |
| decisions-*.json | Round decisions |
| publish-metadata.json | Record of the posted review (if published) |
| review-metadata.json | Review state |

Confirm removal? (This cannot be undone. Anything already posted to the
host is unaffected -- this only removes local files.)
```

### Step 5: Remove the Worktree and Branch

After user confirmation:

```bash
git -C {base-repo} worktree remove --force .artifacts/pr-review/{context}/worktree
```

If `base_repo_is_scratch` is `false` (the base repo was reused, not
scratch-cloned), also drop the local tracking branch:

```bash
git -C {base-repo} branch -D pr-review/{context}
```

If `base_repo_is_scratch` is `true`, the branch lives inside the scratch
clone that Step 6 removes entirely -- no separate branch-delete needed.

If `git worktree remove --force` fails (e.g., already removed manually),
note it and continue with cleanup rather than aborting.

### Step 6: Remove the Scratch Clone (if any)

Only if `base_repo_is_scratch` is `true`:

```bash
rm -rf .artifacts/pr-review/{context}/_scratch-repo
```

### Step 7: Remove Artifacts

```bash
rm -rf .artifacts/pr-review/{context}
```

Clean up any empty parent directories left behind:

```bash
find .artifacts/pr-review -type d -empty -delete 2>/dev/null
```

Tell the user the worktree and artifacts have been removed. Remind them
that anything already posted to the host (comments, discussions) is
unaffected -- this only removes local files.

## Output

- Removed `.artifacts/pr-review/{context}/worktree/` (git worktree)
- Removed local `pr-review/{context}` branch (if `{base-repo}` was reused)
- Removed `.artifacts/pr-review/{context}/_scratch-repo/` (if one was
  created)
- Removed `.artifacts/pr-review/{context}/` directory

## When This Phase Is Done

Report what was cleaned up.

Then **re-read the controller** (`controller.md`) for next-step guidance.
