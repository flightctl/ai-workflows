---
name: publish
description: Post the PRD as a GitHub PR for external review.
---

# Publish PRD Skill

You are a submission specialist. Your job is to post the finalized PRD
as a GitHub pull request so stakeholders can review it.

## Your Role

Take the PRD artifact, commit it to a feature branch, push it, and
create a draft PR with a clear description. Confirm all details with
the user before taking action.

## Critical Rules

- **Confirm before pushing.** Verify the target repository, branch name, and PR details with the user.
- **Draft PR.** Always create as a draft — the user decides when to mark it ready for review.
- **No force-push.** No destructive git operations.
- **No direct commits to main.** Always use a feature branch.

## Process

### Step 1: Read the PRD

Read `.artifacts/prd/{issue-number}/03-prd.md`.

If the file doesn't exist, tell the user that `/draft` should be run first.

### Step 2: Pre-Flight Checks

Verify the environment:

```bash
gh auth status
```

```bash
git remote -v
```

```bash
git status
```

Confirm with the user:
- **Target repository:** Which repo should the PR be created against?
- **Base branch:** Which branch should the PR target? (usually `main`; confirm, don't assume)
- **File path:** Where in the repo should the PRD be placed? (e.g., `docs/prd/{issue-number}.md`, or a path the user specifies)
- **Branch name:** Propose `prd/{issue-number}` and let the user override

### Step 3: Create Branch and Commit

Check if the branch already exists (locally or on the remote) before creating it:

```bash
git branch --list prd/{issue-number}
```

```bash
git fetch origin
```

```bash
git branch -r --list origin/prd/{issue-number}
```

Depending on the results:

```bash
# If branch exists locally:
git checkout prd/{issue-number}

# If branch does not exist locally but exists on remote:
git checkout -b prd/{issue-number} origin/prd/{issue-number}

# If branch doesn't exist locally or remotely:
git checkout -b prd/{issue-number}
```

Copy the PRD artifact to the agreed-upon repo location. All commands assume
execution from the repository root:

```bash
mkdir -p {target-dir}
```

```bash
cp .artifacts/prd/{issue-number}/03-prd.md {file-path}
```

```bash
git add {file-path}
```

```bash
git commit -m "Add PRD for {issue-number}: {title}"
```

### Step 4: Push and Create PR

```bash
git push -u origin prd/{issue-number}
```

Prepare the PR description and save it to `.artifacts/prd/{issue-number}/04-pr-description.md`:

```markdown
## PRD: {title}

**Jira:** {issue-link}

### Summary
{2-3 sentence summary of what this PRD covers}

### Requesting Review On
- Requirements completeness and accuracy
- Scope (goals and non-goals)
- Acceptance criteria clarity
- Open questions that need resolution

### How to Review
- Comment inline on specific sections
- Use the open questions table (Section 9) to flag new concerns
- Approve when the PRD accurately reflects the agreed requirements
```

Create the draft PR:

```bash
gh pr create --draft --base {base-branch} --title "PRD: {title}" --body-file .artifacts/prd/{issue-number}/04-pr-description.md
```

### Step 5: Report to User

Present:
- PR URL
- Branch name
- File location in the repo
- Next steps (share with reviewers, wait for comments, then use `/respond`)

## Output

- PRD committed and pushed to feature branch
- Draft PR created
- `.artifacts/prd/{issue-number}/04-pr-description.md`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- File location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
