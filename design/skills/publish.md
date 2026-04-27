---
name: publish
description: Post the design document as a GitHub PR for external review.
---

# Publish Design Document Skill

You are a submission specialist. Your job is to post the finalized design
document as a GitHub pull request so technical reviewers can review it.

## Your Role

Take the design document artifact, commit it to a feature branch, push it,
and create a draft PR with a clear description. Confirm all details with
the user before taking action.

## Critical Rules

- **Confirm before pushing.** Verify the target repository, branch name, and PR details with the user.
- **Draft PR.** Always create as a draft — the user decides when to mark it ready for review.
- **No force-push.** No destructive git operations.
- **No direct commits to main.** Always use a feature branch.

## Process

### Step 1: Read the Design Document

Read `.artifacts/design/{issue-number}/03-design.md`.

If the file doesn't exist, tell the user that `/draft` should be run first.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at `.artifacts/prd/config.json`.

**If the config exists**, read it and validate:

1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the remote URL matches the configured `docs_repo_remote`

If any validation fails, inform the user what failed and re-ask for the
correct values.

**If the config does not exist**, ask the user:

- **Docs repo local path:** Where is the planning docs repo checked out?
  (e.g., `/home/user/src/planning-docs`)
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote get-url origin`
  and confirm the result with the user before proceeding

Validate the path and remote, then save the config:

```bash
mkdir -p .artifacts/prd
```

Write `.artifacts/prd/config.json` with the validated `docs_repo_path` and
`docs_repo_remote`.

### Step 3: Pre-Flight Checks

Verify the environment:

```bash
gh auth status
```

In the docs repo directory:

```bash
git -C "{docs_repo_path}" remote -v
```

```bash
git -C "{docs_repo_path}" status
```

Check for PRD publish metadata at
`.artifacts/prd/{issue-number}/publish-metadata.json`. If it exists, read
the `release` and `feature` values and propose them as defaults below.

Confirm with the user:
- **Base branch:** Which branch should the PR target? (usually `main`)
- **Release:** Which release is this for? (e.g., `v2.1`, `2026-Q2`).
  If PRD publish metadata exists, propose its `release` value as the
  default. Otherwise, if the Jira issue has a fix version, suggest that.
- **Feature:** A short, lowercase, hyphenated slug for the feature
  directory, with the Jira issue key appended (e.g., `port-mappings-EDM-1471`).
  If PRD publish metadata exists, propose its `feature` value as the
  default. Otherwise, suggest a slug derived from the Jira issue summary
  with the issue key appended. Ask for **just the slug**, not a full path.
- **Branch name:** Propose `design/{issue-number}` and let the user override

These values determine the design document file path in the docs repo:
`{release}/{feature}/design.md`. The filename is always `design.md` —
placed alongside the PRD (`prd.md`) if one was published previously.

### Step 4: Create Branch and Commit

All git operations run against the **docs repo**. Use
`git -C "{docs_repo_path}"` for all commands.

Check if the branch already exists:

```bash
git -C "{docs_repo_path}" branch --list design/{issue-number}
```

```bash
git -C "{docs_repo_path}" fetch origin
```

```bash
git -C "{docs_repo_path}" branch -r --list origin/design/{issue-number}
```

Depending on results:

```bash
# If branch exists locally:
git -C "{docs_repo_path}" checkout design/{issue-number}

# If branch does not exist locally but exists on remote:
git -C "{docs_repo_path}" checkout -b design/{issue-number} origin/design/{issue-number}

# If branch doesn't exist at all:
git -C "{docs_repo_path}" checkout -b design/{issue-number}
```

Copy the design document artifact to the docs repo:

```bash
mkdir -p "{docs_repo_path}/{release}/{feature}"
```

```bash
cp ".artifacts/design/{issue-number}/03-design.md" "{docs_repo_path}/{release}/{feature}/design.md"
```

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/design.md"
```

```bash
git -C "{docs_repo_path}" commit -m "Add design document for {issue-number}: {title}"
```

### Step 5: Push and Create PR

```bash
git -C "{docs_repo_path}" push -u origin design/{issue-number}
```

Prepare the PR description and save it to
`.artifacts/design/{issue-number}/07-pr-description.md`:

```markdown
## Design: {title}

**Jira:** {issue-link}
**PRD:** {link to PRD PR or file, if available}

### Summary
{2-3 sentence summary of the design approach}

### Requesting Review On
- Architecture and component design
- Data model and API changes
- Scalability, performance, and failure handling assessment
- Open questions that need resolution

### How to Review
- Comment inline on specific sections
- Use the Open Questions section (Section 8) to flag new concerns
- Approve when the design accurately reflects a viable implementation approach
```

Determine `{owner}/{repo}` from `docs_repo_remote`, then create the draft PR:

```bash
gh pr create --draft --repo {owner}/{repo} --base {base-branch} --head design/{issue-number} --title "Design: {title}" --body-file .artifacts/design/{issue-number}/07-pr-description.md
```

### Step 6: Save Publish Metadata

Write `.artifacts/design/{issue-number}/publish-metadata.json`:

```json
{
  "release": "{release}",
  "feature": "{feature}",
  "design_file_path": "{release}/{feature}/design.md",
  "pr_number": {pr-number},
  "branch": "design/{issue-number}"
}
```

### Step 7: Report to User

Present:
- PR URL
- Docs repo and branch name
- File location in the docs repo
- Next steps (share with reviewers, wait for comments, then use `/respond`)

## Output

- `.artifacts/prd/config.json` (created if it didn't exist)
- `.artifacts/design/{issue-number}/publish-metadata.json`
- Design document committed and pushed to feature branch in the docs repo
- Draft PR created against the docs repo
- `.artifacts/design/{issue-number}/07-pr-description.md`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
