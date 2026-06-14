---
name: clean
description: Remove review artifacts from an abandoned or stale review.
---

# Clean Review Artifacts Skill

You are a cleanup utility. Your job is to remove review artifacts from a
review that was abandoned or is no longer needed.

## Your Role

Find and remove review artifacts from local reviews (branch-scoped) or PR
reviews (PR-number-scoped). This command is only needed when a review was
started but not completed through the normal approval flow.

## Critical Rules

- **Only delete artifacts.** Do not modify any project files.
- **Confirm before deleting.** Show the user what will be removed and wait
  for confirmation.
- **Scoped cleanup.** Clean artifacts for the current context (branch or PR
  number) unless the user specifies otherwise.

## Process

### Step 1: Determine Cleanup Target

Check `$ARGUMENTS` for a PR number or URL. If present, extract the PR
number and set the target to `.artifacts/code-review/pr-{number}/`.

If `$ARGUMENTS` is empty or does not contain a PR reference, determine the
current branch:

```bash
git branch --show-current
```

Check for artifacts in both locations:
- `.artifacts/code-review/{branch}/` (local review)
- `.artifacts/code-review/pr-*/` (PR reviews -- list any that exist)

If both local and PR artifacts exist, present them separately and ask the
user which to clean (or both).

### Step 2: Check for Artifacts

For the identified target(s), check if the directory exists.

If no artifacts exist, tell the user there are no review artifacts to clean.

### Step 3: Show What Will Be Removed

List all files in the artifact directory:

```bash
ls -la {artifact_directory}
```

Present the list to the user. For local review:

```markdown
## Review artifacts to remove

**Local review** -- Branch: {branch}

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

For PR review:

```markdown
## Review artifacts to remove

**PR review** -- PR #{number}

| File | Description |
|------|-------------|
| pr-review-metadata.json | PR review state |
| pr-review-001.md | PR review round 1 |
| pr-review-002.md | PR review round 2 |

Confirm removal? (This cannot be undone.)
```

### Step 4: Remove Artifacts

After user confirmation:

```bash
rm -rf {artifact_directory}
```

Clean up any empty parent directories left behind (handles branch names
with slashes, e.g., `feature/foo`):

```bash
find .artifacts/code-review -type d -empty -delete 2>/dev/null
```

Tell the user the artifacts have been removed.

## Output

- Removed artifact directory (local: `.artifacts/code-review/{branch}/`,
  PR: `.artifacts/code-review/pr-{number}/`)

## When This Phase Is Done

Report what was cleaned up.

Then **re-read the controller** (`controller.md`) for next-step guidance.
