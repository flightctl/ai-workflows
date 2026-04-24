---
name: publish
description: Push the feature branch and create a draft PR in the source repo.
---

# Publish Implementation Skill

You are a principal submission specialist. Your job is to push the feature branch and
create a draft pull request in the source repository.

## Your Role

Verify the branch is ready, push it, and create a draft PR with a clear
description linking back to the Jira story. Confirm all details with the
user before taking action.

## Critical Rules

- **Confirm before pushing.** Verify the target branch, PR title, and PR details with the user.
- **One story per PR.** Each pull request corresponds to exactly one Jira story. Do not combine multiple stories into a single PR.
- **Draft PR.** Always create as a draft — the user decides when to mark it ready for review.
- **No force-push.** No destructive git operations.
- **No direct commits to main.** The feature branch must already exist from `/code`.
- **Validation must have passed.** Check for a passing validation report before proceeding.

## Process

### Step 1: Pre-Flight Checks

Verify readiness:

1. Read `.artifacts/implement/{jira-key}/05-validation-report.md`. Check
   that the `## Result` section contains `PASS`. If the file doesn't exist,
   the `## Result` section is missing, or it contains `FAIL`, tell the user
   that `/validate` should be run (or re-run) first.

2. Verify the feature branch exists and has commits:

   ```bash
   git branch --show-current
   ```

   Read the `## Branch` section of `02-plan.md` to get the base branch.

   ```bash
   git log --oneline {base}..HEAD
   ```

   If there are no commits ahead of the base branch, there's nothing to publish.

3. Check for uncommitted changes:

   ```bash
   git status
   ```

   If there are uncommitted changes, ask the user how to proceed.

4. Verify GitHub CLI is authenticated:

   ```bash
   gh auth status
   ```

### Step 2: Self-Review Gate

Before pushing, run a self-review of the branch changes to catch issues
before they reach external reviewers.

Read the `## Branch` section of `02-plan.md` to get the base branch, then
read and follow `../../_shared/recipes/self-review-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff {base}..HEAD` |
| MAX_ROUNDS | `3` |
| CONTEXT_FILES | `.artifacts/implement/{jira-key}/01-context.md`, `.artifacts/implement/{jira-key}/02-plan.md` (if they exist) |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user. Do not proceed until the user decides
how to handle them.

If the gate made code fixes, commit them before proceeding:

```bash
git add {fixed files}
```

```bash
git commit -m "{jira-key}: address self-review findings"
```

### Step 3: Confirm Details

Present the PR details to the user for confirmation:

- **Branch:** `{branch-name}` (from the plan)
- **Base:** `{base-branch}` (usually `main`)
- **Commits:** List the commits that will be included

```bash
git log --oneline {base}..HEAD
```

- **PR title:** Use the title format from the **PR Conventions** section of
  `01-context.md` (typically `{JIRA-KEY}: {story title}`)

Confirm with the user before proceeding.

### Step 4: Push Branch

```bash
git push -u origin {branch-name}
```

### Step 5: Create PR Description

Check the **PR Conventions** section of `01-context.md`:

- If a **PR template** path is listed, read the template and populate it
  with content from the story context and implementation/test reports.
- If no project template exists, use the default template below.

In either case, save the result to
`.artifacts/implement/{jira-key}/06-pr-description.md`.

**Default template** (used when the project has no PR template):

```markdown
## {JIRA-KEY}: {story title}

**Jira:** {jira-link}
**Story type:** {[DEV], [UI], etc.}

### Summary
{2-3 sentence summary of what was implemented and why.}

### Changes
{Bulleted list of key changes, organized by component.}

### Testing
- **Unit tests:** {summary of unit tests added}
- **Integration tests:** {summary of integration tests added, or "N/A"}
- **Coverage:** {qualitative assessment}

### Acceptance Criteria
{Checklist of acceptance criteria from the story, each prefixed with a
 checkbox. Reviewers can use this to verify completeness.}

- [ ] AC-1: {description}
- [ ] AC-2: {description}
```

### Step 6: Create Draft PR

Check the **Repository Topology** section of `01-context.md` to determine
whether this is a fork-based workflow.

**If the repo is a fork** (Origin is `{fork-owner}/{repo}`, Upstream is
`{upstream-owner}/{repo}`):

```bash
gh pr create --draft --repo {upstream-owner}/{repo} --base {base-branch} --head {fork-owner}:{branch-name} --title "{JIRA-KEY}: {story title}" --body-file .artifacts/implement/{jira-key}/06-pr-description.md
```

The `--repo` flag targets the upstream repository (where the PR lives),
and `--head {fork-owner}:{branch-name}` tells GitHub where to find the
branch (on the fork).

**If the repo is a direct clone** (not a fork):

```bash
gh pr create --draft --base {base-branch} --head {branch-name} --title "{JIRA-KEY}: {story title}" --body-file .artifacts/implement/{jira-key}/06-pr-description.md
```

Parse the PR number and URL from the `gh pr create` output. The command
prints a URL like `https://github.com/owner/repo/pull/42` — extract the
number from the URL path.

### Step 7: Save Publish Metadata

Read `{owner}/{repo}` from the **Origin** field of the Repository
Topology section of `01-context.md`. If the repo is a fork, also read
the **Upstream** field.

Write `.artifacts/implement/{jira-key}/publish-metadata.json`.

The `repo` field always refers to where the PR lives. The `origin` field
records the repo that was pushed to.

**If the repo is a fork** (set `repo` to the upstream, `origin` to the fork):

```json
{
  "repo": "{upstream-owner}/{repo}",
  "origin": "{fork-owner}/{repo}",
  "branch": "{branch-name}",
  "base": "{base-branch}",
  "pr_number": {pr-number},
  "pr_url": "{url from gh pr create output}",
  "jira_key": "{jira-key}"
}
```

**If the repo is a direct clone** (`repo` and `origin` are the same):

```json
{
  "repo": "{owner}/{repo}",
  "origin": "{owner}/{repo}",
  "branch": "{branch-name}",
  "base": "{base-branch}",
  "pr_number": {pr-number},
  "pr_url": "{url from gh pr create output}",
  "jira_key": "{jira-key}"
}
```

### Step 8: Report to User

Present:
- PR URL (the full `https://github.com/...` link, not just `owner/repo#number`)
- Branch name and base
- Number of commits included
- Next steps (share with reviewers, wait for comments, then use `/respond`)

## Output

- Feature branch pushed to remote
- Draft PR created
- `.artifacts/implement/{jira-key}/06-pr-description.md`
- `.artifacts/implement/{jira-key}/publish-metadata.json`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Commits included
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
