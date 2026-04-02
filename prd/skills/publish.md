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
git remote -v
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
git branch -r --list origin/prd/{issue-number}
```

If the branch exists locally, check it out. If it exists only on the remote
(e.g., fresh clone after a partial failure), fetch and check it out. If it
doesn't exist anywhere, create it:

```bash
# Branch does not exist
git checkout -b prd/{issue-number}

# Branch exists locally (e.g., retry after partial failure)
git checkout prd/{issue-number}

# Branch exists only on remote
git checkout -b prd/{issue-number} origin/prd/{issue-number}
```

Copy the PRD artifact to the agreed-upon repo location. All commands assume
execution from the repository root:

```bash
# Determine the target directory
# e.g., for file-path "docs/prd/EDM-2324.md", target-dir is "docs/prd"
mkdir -p {target-dir}
cp .artifacts/prd/{issue-number}/03-prd.md {file-path}
git add {file-path}
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
