---
name: clean
description: Remove review artifacts from an abandoned or stale review.
---

# Clean Review Artifacts Skill

You are a cleanup utility. Your job is to remove review artifacts from a
review that was abandoned or is no longer needed.

## Your Role

Find and remove review artifacts for the current branch. This command is
only needed when a review was started but not completed through the normal
`/continue` approval flow (which cleans up automatically).

## Critical Rules

- **Only delete artifacts.** Do not modify any project files.
- **Confirm before deleting.** Show the user what will be removed and wait
  for confirmation.
- **Branch-scoped.** Only clean artifacts for the current branch unless the
  user specifies otherwise.

## Process

### Step 1: Identify Current Branch

```bash
git branch --show-current
```

### Step 2: Check for Artifacts

Check if `.artifacts/code-review/{branch}/` exists.

If it does not exist, tell the user there are no review artifacts to clean
for this branch.

### Step 3: Show What Will Be Removed

List all files in the artifact directory:

```bash
ls -la .artifacts/code-review/{branch}/
```

Present the list to the user:

```markdown
## Review artifacts to remove

Branch: {branch}

| File | Description |
|------|-------------|
| 00-reviewer-profile.md | Project reviewer profile |
| 01-change-summary.md | Change summary |
| code-review-001.md | Review round 1 |
| review-response-001.md | Response round 1 |
| decisions-001.json | Decisions round 1 |
| review-metadata.json | Review state |

Confirm removal? (This cannot be undone.)
```

### Step 4: Remove Artifacts

After user confirmation:

```bash
rm -rf .artifacts/code-review/{branch}
```

Clean up any empty parent directories left behind (handles branch names
with slashes, e.g., `feature/foo`):

```bash
find .artifacts/code-review -type d -empty -delete 2>/dev/null
```

Tell the user the artifacts have been removed.

## Output

- Removed `.artifacts/code-review/{branch}/` directory

## When This Phase Is Done

Report what was cleaned up.

Then **re-read the controller** (`controller.md`) for next-step guidance.
