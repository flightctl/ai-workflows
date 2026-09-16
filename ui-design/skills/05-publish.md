---
name: publish
description: Push the UI design document to the docs repo and create a draft GitHub PR.
---

# Publish UI Design Skill

You are a technical writer preparing a UI design document for review. Your
job is to commit the UI design document to the docs repo and create a draft
PR for the team to review.

## Your Role

Copy the UI design document (and API findings, if separate) to the docs
repo, commit on a feature branch, push, and create a draft PR. The PR
description summarizes the UI design for reviewers.

## Critical Rules

- **Confirm before publishing.** Always confirm the target repo, branch, and PR details with the user before creating anything.
- **Feature branch only.** Never commit to `main` directly.
- **Draft PR.** Create the PR as a draft — the user marks it ready for review.
- **No modification of content during publish.** Copy the artifacts as-is. Content changes happen in `/revise`.

## Process

### Step 1: Verify Prerequisites

Confirm these artifacts exist:
- `.artifacts/ui-design/{issue-key}/02-ui-design.md` (required)
- `.artifacts/ui-design/{issue-key}/03-api-findings.md` (optional — include if exists)

If `02-ui-design.md` doesn't exist, tell the user that `/plan` should be
run first.

### Step 2: Resolve the Docs Repo

Read `.artifacts/config.json` for `docs_repo_path` and `docs_repo_remote`.

If the config doesn't exist, ask the user for the docs repo local path and
remote. Write `.artifacts/config.json`.

Validate that the docs repo path exists, is a git repo, and the remote
matches.

### Step 3: Resolve Publish Remotes

Read and follow `../../_shared/recipes/resolve-docs-publish-remotes.md` with:
- `DOCS_REPO_PATH` = the validated docs repo path
- `CONFIGURED_DOCS_REPO_REMOTE` = `docs_repo_remote` from config
- `BRANCH_NAME` = `{issue-key}-ui-design` (e.g., `EDM-1234-ui-design`)

This resolves `UPSTREAM_REMOTE`, `PUSH_REMOTE`, `UPSTREAM_REPO`, `PUSH_REPO`,
`PUSH_URL`, `FORK_OWNER`, and `CROSS_REPOSITORY`.

### Step 4: Confirm with User

Present the publish plan:

```text
Publishing UI design document:
  Source: .artifacts/ui-design/{issue-key}/02-ui-design.md
  API findings: {included / not applicable}
  Docs repo: {UPSTREAM_REPO}
  Push to: {PUSH_URL} (branch: {BRANCH_NAME})
  PR target: {UPSTREAM_REPO} ({base branch})
  Cross-repository: {CROSS_REPOSITORY}

Proceed?
```

Wait for explicit approval.

### Step 5: Determine Target Directory

Search the docs repo for the feature directory (the same directory that
contains the PRD and design document):

```bash
find "{docs_repo_path}" -type d \( -name "*{issue-key}*" -o -name "*{feature-key}*" \)
```

If found, the UI design document goes alongside the existing planning
artifacts. If multiple matches, ask the user.

If not found, ask the user where to place the document.

### Step 6: Prepare the Branch

```bash
git -C "{docs_repo_path}" fetch "{UPSTREAM_REMOTE}"
git -C "{docs_repo_path}" checkout -b "{BRANCH_NAME}" "{UPSTREAM_REMOTE}/{base_branch}"
```

### Step 7: Copy and Commit

Copy the artifacts to the docs repo:

```bash
cp ".artifacts/ui-design/{issue-key}/02-ui-design.md" "{target_directory}/ui-design.md"
```

If `03-api-findings.md` exists:

```bash
cp ".artifacts/ui-design/{issue-key}/03-api-findings.md" "{target_directory}/api-findings.md"
```

Render provenance footer on the docs-repo copies:

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={issue-key}`, and `TARGET_FILE` set to
each copied file's absolute path in the docs repo.

**Note:** The provenance script (`_shared/scripts/provenance.py`) must
support `ui-design` as a `--workflow` value. If it rejects the value,
the workflow operator should add `ui-design` to `WORKFLOW_DOCS` and the
CLI `--workflow` choices in `provenance.py`, matching the existing `prd`
and `design` entries. The same identifier must be used in the script,
recipes, and `_shared/provenance-schema.md`.

Stage and commit:

```bash
git -C "{docs_repo_path}" add "{target_directory}/ui-design.md"
# If api-findings.md was copied:
git -C "{docs_repo_path}" add "{target_directory}/api-findings.md"
git -C "{docs_repo_path}" commit -m "Add UI design for {issue-key}"
```

### Step 8: Push and Create PR

Push the branch:

```bash
git -C "{docs_repo_path}" push -u "{PUSH_REMOTE}" "{BRANCH_NAME}"
```

Generate the PR description and save to
`.artifacts/ui-design/{issue-key}/04-pr-description.md`:

```markdown
## UI Design — {issue-key}: {title}

### Summary

{1–2 paragraph summary of the UI design — component architecture approach,
key hooks, state management decisions, and API findings.}

### Key Decisions

- {decision 1 — e.g., "Component tree uses feature-based decomposition with shared layout components"}
- {decision 2 — e.g., "State management uses React Query for server state, local state for UI state"}
- {decision 3}

### API Findings

- **Confirmed mappings:** {N} of {total}
- **Gaps identified:** {N} ({breakdown by severity})
- **Implementation readiness:** {assessment}

### Open Questions

{List any open questions from the UI design document that reviewers should weigh in on.}

### Review Checklist

- [ ] Component decomposition is appropriate for the feature scope
- [ ] Hook design follows project data-fetching conventions
- [ ] State management scope decisions are justified
- [ ] Data flow mapping is complete and accurate
- [ ] Accessibility implementation meets project standards
- [ ] API gaps are correctly categorized and scoped for [DEV] stories
```

Create the draft PR:

If `CROSS_REPOSITORY` is true:
```bash
gh pr create --draft --repo "{UPSTREAM_REPO}" --head "{FORK_OWNER}:{BRANCH_NAME}" \
  --base "{base_branch}" --title "UI design: {issue-key} — {short title}" \
  --body-file ".artifacts/ui-design/{issue-key}/04-pr-description.md"
```

If `CROSS_REPOSITORY` is false:
```bash
gh pr create --draft --repo "{UPSTREAM_REPO}" --head "{BRANCH_NAME}" \
  --base "{base_branch}" --title "UI design: {issue-key} — {short title}" \
  --body-file ".artifacts/ui-design/{issue-key}/04-pr-description.md"
```

### Step 9: Record Publish Metadata

Write `.artifacts/ui-design/{issue-key}/publish-metadata.json`:

```json
{
  "pr_number": {number},
  "pr_url": "{url}",
  "branch": "{BRANCH_NAME}",
  "base_branch": "{base_branch}",
  "upstream_repo": "{UPSTREAM_REPO}",
  "push_repo": "{PUSH_REPO}",
  "cross_repository": {true/false},
  "head_sha": "{commit SHA}",
  "published_at": "{ISO timestamp}",
  "target_directory": "{resolved target directory path in docs repo}",
  "files": [
    "ui-design.md"
  ]
}
```

Include `"api-findings.md"` in the `files` array only if
`03-api-findings.md` was actually copied to the docs repo. Always
include `"ui-design.md"`. Do not list files that were not published.

```text
Example when API findings were published:
  "files": ["ui-design.md", "api-findings.md"]

Example when API findings are inline:
  "files": ["ui-design.md"]
```

### Step 10: Report to User

Present:
- PR URL and number
- Branch name
- Files published
- Reminder that the PR is in draft state

## Output

- PR in the docs repo (draft)
- `.artifacts/ui-design/{issue-key}/04-pr-description.md`
- `.artifacts/ui-design/{issue-key}/publish-metadata.json`

## When This Phase Is Done

Report your results:
- PR URL
- Files published to the docs repo
- Reminder to share the PR with reviewers

Then return to the invoking workflow router for completion guidance.
