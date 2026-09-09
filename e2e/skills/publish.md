---
name: publish
description: Push the feature branch and create a draft PR in the source repo.
---

# Publish E2E Tests Skill

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

## Shared Script

This skill delegates deterministic git and CLI operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/publish.sh
```

The script provides subcommands: `preflight`, `push`, `check-existing`,
`create-pr`, and `save-metadata`. See the script header for full usage.

## Process

### Step 1: Pre-Flight Checks

Verify readiness:

1. Read `.artifacts/e2e/{issue-key}/05-validation-report.md`. Check
   that the `## Result` section contains `PASS`. If the file doesn't exist,
   the `## Result` section is missing, or it contains `FAIL`, tell the user
   that `/validate` should be run (or re-run) first.

2. Verify the feature branch exists and has commits:

   ```bash
   git branch --show-current
   ```

   Read the `## Branch` section of `02-plan.md` to get the Local Base and PR Target.

   ```bash
   git log --oneline {local-base}..HEAD
   ```

   If there are no commits ahead of the Local Base, there's nothing to publish.

3. Run the shared pre-flight checks:

   ```bash
   ../../_shared/scripts/publish.sh preflight --platform github
   ```

   Parse the output to confirm `auth_ok=true` and check for
   `has_uncommitted=true` or `has_staged=true`. If there are uncommitted
   changes, ask the user how to proceed.

### Step 2: Cross-Cutting Review

Each sub-task was already reviewed individually during `/code`. This
review focuses on issues that only emerge when looking at the branch
as a whole — problems that span tasks or arise from their interaction.

Read the `## Branch` section of `02-plan.md` to get the Local Base, then
read and follow `../../_shared/recipes/self-review-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff {local-base}...HEAD` |
| MAX_ROUNDS | `3` |
| CONTEXT_FILES | `.artifacts/e2e/{issue-key}/01-context.md`, `.artifacts/e2e/{issue-key}/02-plan.md` (if they exist) |
| SUPPLEMENTARY_CRITERIA | This is a cross-cutting review. Each sub-task was already reviewed individually. Focus on inter-task issues: (1) Cross-test consistency (setup/teardown patterns, assertion style). (2) Shared fixtures or helpers that emerged across tasks. (3) Label and tag consistency across test files. (4) Pattern drift between tests written in different tasks. Skip issues already caught per-task: individual test correctness, per-test anti-pattern checks, single-task infrastructure usage. |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user. Do not proceed until the user decides
how to handle them.

If the gate made code fixes, re-run the validation profile's required
checks to verify the post-fix state. Once checks pass, commit:

```bash
git add {fixed files}
```

```bash
git commit -m "{issue-key}: address cross-cutting review findings"
```

### Step 3: Confirm Details

Present the PR details to the user for confirmation:

- **Branch:** `{branch-name}` (from the plan)
- **Local Base:** `{local-base}` (branch this story is stacked on — from `## Branch` in `02-plan.md`)
- **PR Target:** `{pr-target}` (upstream branch the PR will target — from `## Branch` in `02-plan.md`)
- **Commits:** List the commits that will be included (only this story's commits)

```bash
git log --oneline {local-base}..HEAD
```

- **PR title:** Use the title format from the **PR Conventions** section of
  `01-context.md` (typically `{issue-key}: {story title}`)

Confirm with the user before proceeding.

### Step 4: Push Branch

```bash
../../_shared/scripts/publish.sh push --remote origin --branch {branch-name}
```

### Step 5: Create PR Description

Check the **PR Conventions** section of `01-context.md`:

- If a **PR template** path is listed, read the template and populate it
  with content from the story context and test reports.
- If no project template exists, use the default template below.

In either case, save the result to
`.artifacts/e2e/{issue-key}/06-pr-description.md`.

**Default template** (used when the project has no PR template):

```markdown
## {issue-key}: {story title}

**Jira:** {jira-link}
**Story type:** [QE]

### Summary
{2-3 sentence summary of the e2e tests added and what user-facing
 behaviors they validate.}

### E2E Test Scenarios
{Bulleted list of test scenarios — consolidated and standalone — with
 their AC coverage noted (e.g., "[AC-1, AC-3]").}

### Test Infrastructure
- **Suite location:** {path to the new test suite directory}
- **Reference suite:** {which existing suite was used as the pattern}
- **Auxiliary services:** {services required, or "None beyond suite defaults"}
- **Test infrastructure used:** {key methods from the project's test abstractions}

### Acceptance Criteria
{Checklist of acceptance criteria from the story, each prefixed with a
 checkbox. Reviewers can use this to verify scenario coverage.}

- [ ] AC-1: {description}
- [ ] AC-2: {description}
```

### Step 6: Create Draft PR

Check the **Repository Topology** section of `01-context.md` to determine
whether this is a fork-based workflow.

First, check whether a PR already exists for this branch:

For fork-based workflows, use `{fork-owner}:{branch-name}` as the
`--head` value so the check matches only PRs from this fork (plain
`{branch-name}` would match any fork's branch with the same name):

```bash
# Fork-based:
../../_shared/scripts/publish.sh check-existing --repo {upstream-owner}/{repo} --head {fork-owner}:{branch-name}

# Direct clone:
../../_shared/scripts/publish.sh check-existing --repo {upstream-owner}/{repo} --head {branch-name}
```

If exit code is 5, a PR already exists — parse the PR number and URL
from the returned JSON output, then skip to Step 7 and use those values
in the metadata. If the command fails (non-zero exit other than 5),
stop and report the error. If exit code is 0, create a new PR.

**If the repo is a fork** (Origin is `{fork-owner}/{repo}`, Upstream is
`{upstream-owner}/{repo}`):

```bash
../../_shared/scripts/publish.sh create-pr \
  --repo {upstream-owner}/{repo} \
  --base {pr-target} \
  --head {fork-owner}:{branch-name} \
  --title "{issue-key}: {story title}" \
  --body-file .artifacts/e2e/{issue-key}/06-pr-description.md \
  --draft
```

The `--repo` flag targets the upstream repository (where the PR lives),
and `--head {fork-owner}:{branch-name}` tells GitHub where to find the
branch (on the fork).

**If the repo is a direct clone** (not a fork):

```bash
../../_shared/scripts/publish.sh create-pr \
  --base {pr-target} \
  --head {branch-name} \
  --title "{issue-key}: {story title}" \
  --body-file .artifacts/e2e/{issue-key}/06-pr-description.md \
  --draft
```

The script prints the PR URL on stdout. Parse the PR number from the URL
path (e.g., `https://github.com/owner/repo/pull/42` → `42`).

If the script exits with code 4 (PR creation failed), fall back to
providing the user with a GitHub compare URL:

- Fork-based: `https://github.com/{upstream-owner}/{repo}/compare/{pr-target}...{fork-owner}:{branch-name}?expand=1`
- Direct clone: `https://github.com/{upstream-owner}/{repo}/compare/{pr-target}...{branch-name}?expand=1`

### Step 7: Save Publish Metadata

Read `{owner}/{repo}` from the **Origin** field of the Repository
Topology section of `01-context.md`. If the repo is a fork, also read
the **Upstream** field.

The `repo` field always refers to where the PR lives. The `origin` field
records the repo that was pushed to.

**If the repo is a fork** (set `repo` to the upstream, `origin` to the fork):

```bash
../../_shared/scripts/publish.sh save-metadata \
  --file .artifacts/e2e/{issue-key}/publish-metadata.json \
  repo={upstream-owner}/{repo} \
  origin={fork-owner}/{repo} \
  branch={branch-name} \
  base={pr-target} \
  pr_number={pr-number} \
  pr_url={url-from-create-pr-output} \
  jira_key={issue-key}
```

**If the repo is a direct clone** (`repo` and `origin` are the same):

```bash
../../_shared/scripts/publish.sh save-metadata \
  --file .artifacts/e2e/{issue-key}/publish-metadata.json \
  repo={owner}/{repo} \
  origin={owner}/{repo} \
  branch={branch-name} \
  base={pr-target} \
  pr_number={pr-number} \
  pr_url={url-from-create-pr-output} \
  jira_key={issue-key}
```

### Step 8: Report to User

Present:
- PR URL (the full `https://github.com/...` link, not just `owner/repo#number`)
- Branch name and base
- Number of commits included

## Output

- Feature branch pushed to remote
- Draft PR created
- `.artifacts/e2e/{issue-key}/06-pr-description.md`
- `.artifacts/e2e/{issue-key}/publish-metadata.json`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Commits included

Then return to the invoking workflow router for completion guidance.
