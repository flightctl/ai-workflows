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
- **Jira write is limited.** The only Jira write allowed in this workflow is setting the story's **Git Pull Request** field to the created PR URL after successful draft PR creation during `/publish`. Do not transition status, change assignee, add comments, or edit any other field.

## Process

### Step 1: Pre-Flight Checks

Verify readiness:

1. Read `.artifacts/implement/{issue-key}/05-validation-report.md`. Check
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

3. Check for uncommitted changes:

   ```bash
   git status
   ```

   If there are uncommitted changes, ask the user how to proceed.

4. Verify GitHub CLI is authenticated:

   ```bash
   gh auth status
   ```

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
| CONTEXT_FILES | `.artifacts/implement/{issue-key}/01-context.md`, `.artifacts/implement/{issue-key}/02-plan.md` (if they exist) |
| SUPPLEMENTARY_CRITERIA | This is a cross-cutting review. Each sub-task was already reviewed individually. Focus on inter-task issues: (1) Inconsistencies across files or tasks (error handling style, naming conventions, logging patterns). (2) Duplicated logic that emerged across separate tasks. (3) Integration gaps between components implemented in different tasks. (4) API surface coherence (public interfaces make sense together). Skip issues already caught per-task: individual function correctness, per-file error handling completeness, single-task test coverage. |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user. Do not proceed until the user decides
how to handle them.

If the gate made code fixes, commit them before proceeding:

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
- **Jira link:** After the PR is created, the PR URL will be written to the
  story's **Git Pull Request** field on `{issue-key}`

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
`.artifacts/implement/{issue-key}/06-pr-description.md`.

**Default template** (used when the project has no PR template):

```markdown
## {issue-key}: {story title}

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
gh pr create --draft --repo {upstream-owner}/{repo} --base {pr-target} --head {fork-owner}:{branch-name} --title "{issue-key}: {story title}" --body-file .artifacts/implement/{issue-key}/06-pr-description.md
```

The `--repo` flag targets the upstream repository (where the PR lives),
and `--head {fork-owner}:{branch-name}` tells GitHub where to find the
branch (on the fork).

**If the repo is a direct clone** (not a fork):

```bash
gh pr create --draft --base {pr-target} --head {branch-name} --title "{issue-key}: {story title}" --body-file .artifacts/implement/{issue-key}/06-pr-description.md
```

Parse the PR number and URL from the `gh pr create` output. The command
prints a URL like `https://github.com/owner/repo/pull/42` — extract the
number from the URL path.

### Step 7: Link PR on the Jira Story

Immediately after the draft PR is created (Step 6), write the PR URL into
the Jira story's **Git Pull Request** field. The issue key is
`{issue-key}` from the artifact directory / `01-context.md`. The PR URL
is the one returned by `gh pr create` in Step 6.

Record a `jira_link_status` of `linked`, `skipped`, or `failed` for
Step 8 metadata and Step 9 reporting.

1. **Resolve the field ID** for the current Jira instance (IDs are
   instance-specific — do not hardcode):

   ```text
   GET /rest/api/3/field
   ```

   Match `name` case-insensitively to `Git Pull Request`.

   - If **exactly one** field matches, use that field's `id` (for example
     `customfield_XXXXX`) and continue.
   - If **none** match, set `jira_link_status` to `skipped`, report that
     the PR was created but the Jira link was skipped (field not found),
     and continue to Step 8. Do not fail the publish phase.
   - If **more than one** field matches, set `jira_link_status` to
     `skipped`, report the ambiguity (list matching field IDs), and
     continue to Step 8 without writing. Do not pick an arbitrary ID.

2. **Inspect the field schema** from the same field descriptor before
   encoding any update. Use the schema to choose the write shape:

   | Schema shape | How to encode the value |
   |--------------|-------------------------|
   | Scalar string / URL | Single string: `"{pr_url}"` |
   | Multi-line / free text | Newline-delimited string; preserve existing lines |
   | Array / multi-value | JSON array of strings; preserve existing entries |

   If the schema is unrecognized or incompatible, set
   `jira_link_status` to `skipped`, report why, and continue to Step 8.

3. **Read the current value** of that field on `{issue-key}`.

4. **Update the field** (schema-appropriate encoding from step 2):
   - If the field is empty, set it to the PR URL.
   - If it already contains this exact PR URL, set `jira_link_status` to
     `linked` (idempotent no-op) and continue to Step 8.
   - If it already contains other PR URL(s) and the schema is multi-line
     or array, append the new URL without removing existing ones.
   - If the schema is scalar and already set to a different URL, ask the
     user whether to replace it or leave it. If they leave it, set
     `jira_link_status` to `skipped` and continue to Step 8.

   Prefer the available Jira MCP update tool when authenticated:

   ```text
   jira_update_issue(
     issue_key: "{issue-key}",
     fields: {"{git_pull_request_field_id}": {schema-appropriate value}}
   )
   ```

   If MCP is unavailable, use the Jira REST API or `jira` CLI equivalent.

   **Concurrency:** Immediately before writing, re-read the field. If the
   value changed since step 3, recompute the update from the fresh value
   (still idempotent on this PR URL) and write once. If the write still
   fails due to a conflict, retry the re-read/recompute/write path once.
   Do not invent unsupported "atomic append" APIs.

5. **On failure:** set `jira_link_status` to `failed`, report the error
   and the PR URL so the user can paste it manually. Do not roll back
   the GitHub PR. Continue to Step 8.

6. **On success:** set `jira_link_status` to `linked`.

### Step 8: Save Publish Metadata

Read `{owner}/{repo}` from the **Origin** field of the Repository
Topology section of `01-context.md`. If the repo is a fork, also read
the **Upstream** field.

Write `.artifacts/implement/{issue-key}/publish-metadata.json`.

The `repo` field always refers to where the PR lives. The `origin` field
records the repo that was pushed to. Include `jira_link_status` from
Step 7 (`linked`, `skipped`, or `failed`).

**If the repo is a fork** (set `repo` to the upstream, `origin` to the fork):

```json
{
  "repo": "{upstream-owner}/{repo}",
  "origin": "{fork-owner}/{repo}",
  "branch": "{branch-name}",
  "base": "{pr-target}",
  "pr_number": {pr-number},
  "pr_url": "{url from gh pr create output}",
  "jira_key": "{issue-key}",
  "jira_link_status": "{linked|skipped|failed}"
}
```

**If the repo is a direct clone** (`repo` and `origin` are the same):

```json
{
  "repo": "{owner}/{repo}",
  "origin": "{owner}/{repo}",
  "branch": "{branch-name}",
  "base": "{pr-target}",
  "pr_number": {pr-number},
  "pr_url": "{url from gh pr create output}",
  "jira_key": "{issue-key}",
  "jira_link_status": "{linked|skipped|failed}"
}
```

### Step 9: Report to User

Present:
- PR URL (the full `https://github.com/...` link, not just `owner/repo#number`)
- Branch name and base
- Number of commits included
- Jira **Git Pull Request** link result from `jira_link_status`
  (`linked` / `skipped` / `failed`)
- Next steps (share with reviewers, wait for comments, then use `/respond`)

## Output

- Feature branch pushed to remote
- Draft PR created
- Jira link result recorded in `publish-metadata.json` as `jira_link_status`
  (`linked`, `skipped`, or `failed`); the PR URL is written to the story's
  **Git Pull Request** field only when status is `linked`
- `.artifacts/implement/{issue-key}/06-pr-description.md`
- `.artifacts/implement/{issue-key}/publish-metadata.json`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Commits included
- `jira_link_status` (`linked` / `skipped` / `failed`)
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
