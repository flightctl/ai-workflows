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

## Shared Script

This skill delegates deterministic git and CLI operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/publish.py
```

The script provides subcommands: `preflight`, `push`, `check-existing`,
`create-pr`, and `save-metadata`. See the script header for full usage.

## Process

### Prerequisites: Resolve Script Path

Before running any subcommands, resolve the shared script to an
absolute path so it remains valid regardless of working directory:

```bash
PUBLISH_SCRIPT="${HOME}/.ai-workflows/_shared/scripts/publish.py"
```

Use `$PUBLISH_SCRIPT` instead of the relative path in all subsequent
commands.

### Step 1: Pre-Flight Checks

Verify readiness:

1. Read `.artifacts/ui-implement/{issue-key}/05-validation-report.md`. Locate
   the `## Result` heading and parse the first non-empty, non-HTML-comment
   line after it. That line must be exactly `PASS` (case-sensitive, no
   surrounding text). If the file doesn't exist, the `## Result` section is
   missing, or the first non-empty, non-comment line is anything other than
   `PASS`, tell the user that `/validate` should be run (or re-run) first.

2. Compare the current HEAD SHA against the `## Validated HEAD` SHA
   recorded in the validation report. If the SHAs differ, code has
   changed since validation (e.g., via `/respond`). Tell the user that
   `/validate` must be re-run before publishing.

3. Verify the feature branch exists and has commits:

   ```bash
   git branch --show-current
   ```

   Read the `## Branch` section of `02-plan.md` to get the Local Base and PR Target.

   ```bash
   git log --oneline {local-base}..HEAD
   ```

   If there are no commits ahead of the Local Base, there's nothing to publish.

4. Run the shared pre-flight checks:

   ```bash
   python3 "$PUBLISH_SCRIPT" preflight --platform github
   ```

   Parse the output to confirm `auth_ok=true`. If `auth_ok=false`, stop
   and tell the user to authenticate first. Check for
   `has_uncommitted=true`, `has_staged=true`, or `has_untracked=true`.
   If there are uncommitted or untracked changes, ask the user how to
   proceed.

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
| CONTEXT_FILES | `.artifacts/ui-implement/{issue-key}/01-context.md`, `.artifacts/ui-implement/{issue-key}/02-plan.md` (if they exist) |
| SUPPLEMENTARY_CRITERIA | This is a cross-cutting review. Each sub-task was already reviewed individually. Focus on inter-task issues: (1) Inconsistencies across components (naming conventions, prop patterns, event handling style). (2) Duplicated logic that emerged across separate tasks — shared hooks or utilities that should be extracted. (3) Integration gaps between components implemented in different tasks. (4) Design system usage coherence (consistent component choices, token usage). (5) i18n key consistency (naming convention, namespace usage). Skip issues already caught per-task: individual component correctness, per-file error handling, single-task test coverage. |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user. Do not proceed until the user decides
how to handle them.

If the gate made code fixes, commit them before proceeding:

```bash
git add {fixed files}
git commit -m "{issue-key}: address cross-cutting review findings"
```

### Step 3: Confirm Details

Present the PR details to the user for confirmation:

- **Branch:** `{branch-name}` (from the plan)
- **Local Base:** `{local-base}` (from `## Branch` in `02-plan.md`)
- **PR Target:** `{pr-target}` (from `## Branch` in `02-plan.md`)
- **Commits:** List the commits that will be included

```bash
git log --oneline {local-base}..HEAD
```

- **PR title:** Use the title format from the **PR Conventions** section of
  `01-context.md` (typically `{issue-key}: {story title}`)

Confirm with the user before proceeding.

### Step 4: Push Branch

```bash
python3 "$PUBLISH_SCRIPT" push --remote origin --branch {branch-name}
```

### Step 5: Create PR Description

Check the **PR Conventions** section of `01-context.md`:

- If a **PR template** path is listed, read the template and populate it
  with content from the story context and implementation/test reports.
- If no project template exists, use the default template below.

In either case, save the result to
`.artifacts/ui-implement/{issue-key}/06-pr-description.md`.

**Default template** (used when the project has no PR template):

```markdown
## {issue-key}: {story title}

**Jira:** {jira-link}
**Story type:** {[UI]}

### Summary
{2-3 sentence summary of what was implemented and why.}

### Changes
{Bulleted list of key changes, organized by component.}

### New Components
{List of new components/hooks added, with brief description.}

### Testing
- **Unit tests:** {summary of unit tests added}
- **Integration/e2e stubs:** {summary of stubs added, or "N/A"}
- **Coverage:** {qualitative assessment}

### UI Concerns
- **Design system:** {components used}
- **i18n:** {keys added or "N/A — project has no i18n"}
- **Accessibility:** {a11y features implemented}

### Acceptance Criteria
{Checklist of acceptance criteria from the story.}

- [ ] AC-1: {description}
- [ ] AC-2: {description}
```

### Step 6: Create Draft PR

Check the **Repository Topology** section of `01-context.md` to determine
whether this is a fork-based workflow.

First, check whether a PR already exists for this branch. Use the same
`--head` format that `create-pr` uses — fork-qualified for forks:

**If the repo is a fork:**

```bash
python3 "$PUBLISH_SCRIPT" check-existing --repo {upstream-owner}/{repo} --head {fork-owner}:{branch-name}
```

**If the repo is a direct clone:**

```bash
python3 "$PUBLISH_SCRIPT" check-existing --repo {upstream-owner}/{repo} --head {branch-name}
```

If exit code is 5, a PR already exists — parse the PR number and URL,
then skip to Step 7. If non-zero exit other than 5, stop and report the
error. If exit code is 0, create a new PR.

**If the repo is a fork:**

```bash
python3 "$PUBLISH_SCRIPT" create-pr \
  --repo {upstream-owner}/{repo} \
  --base {pr-target} \
  --head {fork-owner}:{branch-name} \
  --title "{issue-key}: {story title}" \
  --body-file .artifacts/ui-implement/{issue-key}/06-pr-description.md \
  --draft
```

**If the repo is a direct clone:**

```bash
python3 "$PUBLISH_SCRIPT" create-pr \
  --base {pr-target} \
  --head {branch-name} \
  --title "{issue-key}: {story title}" \
  --body-file .artifacts/ui-implement/{issue-key}/06-pr-description.md \
  --draft
```

Parse the PR number from the URL. If the script exits with code 4, fall
back to providing a GitHub compare URL.

### Step 7: Save Publish Metadata

Read `{owner}/{repo}` from the **Origin** field of the Repository
Topology section of `01-context.md`. If the repo is a fork, also read
the **Upstream** field.

**If the repo is a fork:**

```bash
python3 "$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/ui-implement/{issue-key}/publish-metadata.json \
  repo={upstream-owner}/{repo} \
  origin={fork-owner}/{repo} \
  branch={branch-name} \
  base={pr-target} \
  pr_number={pr-number} \
  pr_url={url-from-create-pr-output} \
  jira_key={issue-key}
```

**If the repo is a direct clone:**

```bash
python3 "$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/ui-implement/{issue-key}/publish-metadata.json \
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
- PR URL (the full `https://github.com/...` link)
- Branch name and base
- Number of commits included

## Output

- Feature branch pushed to remote
- Draft PR created
- `.artifacts/ui-implement/{issue-key}/06-pr-description.md`
- `.artifacts/ui-implement/{issue-key}/publish-metadata.json`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Commits included

Then return to the invoking workflow router for completion guidance.
