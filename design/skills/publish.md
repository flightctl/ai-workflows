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

## Shared Script

This skill delegates deterministic git and CLI operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/publish.sh
```

The script provides subcommands: `preflight`, `push`, `check-existing`,
`create-pr`, and `save-metadata`. See the script header for full usage.

## Process

### Prerequisites: Resolve Script Path

Before any `cd` or subshell that changes the working directory, resolve
the shared script to an absolute path so it remains valid:

```bash
PUBLISH_SCRIPT="$(git rev-parse --show-toplevel)/_shared/scripts/publish.sh"
```

Use `$PUBLISH_SCRIPT` instead of the relative path in all subsequent
commands.

### Step 1: Read the Design Document

Read `.artifacts/design/{issue-key}/03-design.md`.

If the file doesn't exist, tell the user that `/draft` should be run first.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at `.artifacts/config.json`.

**If the config exists**, read it and validate:

1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the remote URL matches the configured `docs_repo_remote`

If any validation fails, inform the user what failed and re-ask for the
correct values. Resolve `~` to an absolute path before saving. Update
`.artifacts/config.json` with the corrected values.

**If the config does not exist**, ask the user:

- **Docs repo local path:** Where is the planning docs repo checked out?
  (e.g., `~/src/planning-docs`)
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote get-url origin`
  and confirm the result with the user before proceeding

Validate the path and remote. Resolve `~` to the user's home directory
so the stored path is absolute. Write `.artifacts/config.json` with the
validated `docs_repo_path` and `docs_repo_remote`.

### Step 3: Pre-Flight Checks

Run the shared pre-flight checks from the docs repo directory:

```bash
(cd "{docs_repo_path}" && "$PUBLISH_SCRIPT" preflight --platform github)
```

Parse the output to confirm `auth_ok=true`. Also verify the docs repo state:

```bash
git -C "{docs_repo_path}" remote -v
```

```bash
git -C "{docs_repo_path}" status
```

Provenance at publish time:
- If `.artifacts/design/{issue-key}/provenance.json` exists from `/draft`, `/revise`,
  or `/respond`, the footer reflects the full authoring session (`provenance_kind:
  session`).
- If the log is missing, the render recipe **auto-captures a commit-time snapshot**
  (`phase=commit`, `provenance_kind: commit_only`) so stale footers are replaced
  instead of copied forward.
- Only if the user explicitly declines provenance, pass `ALLOW_MISSING=yes` to strip
  the footer and record `provenance_kind: declined` (no human-readable block).

Search the docs repo for a published PRD directory containing
`{issue-key}`:

```bash
find "{docs_repo_path}" -type d -name "*{issue-key}*"
```

Filter matches to directories that contain a `prd.md` file.

If exactly one matching directory contains `prd.md` (e.g.,
`v2.1/delta-updates-EDM-4867`), parse the path to extract `release` (first
path component under the docs repo root) and `feature` (second component)
and propose them as defaults below. If multiple matches contain `prd.md`,
present them to the user and ask which one to use.

Confirm with the user:
- **Base branch:** Which branch should the PR target? (usually `main`)
- **Release:** Which release is this for? (e.g., `v2.1`, `2026-Q2`).
  If a PRD directory was found, propose the extracted `release` value as
  the default. Otherwise, if the Jira issue has a fix version, suggest that.
- **Feature:** A short, lowercase, hyphenated slug for the feature
  directory, with the Jira issue key appended (e.g., `port-mappings-EDM-1471`).
  If a PRD directory was found, propose the extracted `feature` value as
  the default. Otherwise, suggest a slug derived from the Jira issue summary
  with the issue key appended. Ask for **just the slug**, not a full path.
- **Branch name:** Propose `design/{issue-key}` and let the user override.
  Use the confirmed value as `{branch-name}` in all subsequent steps.

These values determine the design document file path in the docs repo:
`{release}/{feature}/design.md`. The filename is always `design.md` —
placed alongside the PRD (`prd.md`) if one was published previously.

### Step 4: Create Branch and Commit

All git operations run against the **docs repo**. Use
`git -C "{docs_repo_path}"` for all commands.

Verify the docs repo is clean before modifying it:

```bash
git -C "{docs_repo_path}" status
```

If there are uncommitted changes, ask the user before continuing.

Check if the branch already exists:

```bash
git -C "{docs_repo_path}" branch --list {branch-name}
```

```bash
git -C "{docs_repo_path}" fetch origin
```

```bash
git -C "{docs_repo_path}" branch -r --list origin/{branch-name}
```

Depending on results:

```bash
# If branch exists locally:
git -C "{docs_repo_path}" checkout {branch-name}

# If branch does not exist locally but exists on remote:
git -C "{docs_repo_path}" checkout -b {branch-name} origin/{branch-name}

# If branch doesn't exist at all:
git -C "{docs_repo_path}" checkout -b {branch-name}
```

Copy the design document artifact to the docs repo:

```bash
mkdir -p "{docs_repo_path}/{release}/{feature}"
```

```bash
cp ".artifacts/design/{issue-key}/03-design.md" "{docs_repo_path}/{release}/{feature}/design.md"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{release}/{feature}/design.md"`.

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/design.md"
```

**Testplan publication:**

**If `04-testplan.md` does not exist:** check whether a previously
published testplan exists at
`{docs_repo_path}/{release}/{feature}/testplan.md`. If it does, remove
it:

```bash
git -C "{docs_repo_path}" rm -- "{release}/{feature}/testplan.md"
```

Commit with the design-only message (regardless of whether a stale
testplan was removed) and skip to Step 5:

```bash
git -C "{docs_repo_path}" commit -m "Add design document for {issue-key}: {title}"
```

**If `04-testplan.md` exists**, copy it to the docs repo:

```bash
cp ".artifacts/design/{issue-key}/04-testplan.md" "{docs_repo_path}/{release}/{feature}/testplan.md"
```

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/testplan.md"
```

```bash
git -C "{docs_repo_path}" commit -m "Add design document and testplan for {issue-key}: {title}"
```

### Step 5: Push and Create PR

Push the branch using the shared script (run from the docs repo):

```bash
(cd "{docs_repo_path}" && "$PUBLISH_SCRIPT" push --remote origin --branch {branch-name})
```

Read the design document and identify specific areas that warrant reviewer
attention (AI-dependent):
- Open questions from Section 9 (list each by title)
- Sections with remaining TBD markers
- Key architectural decisions that have significant trade-offs

Prepare the PR description and save it to
`.artifacts/design/{issue-key}/08-pr-description.md`:

```markdown
## Design: {title}

**Jira:** {issue-link}
**PRD:** {link to PRD PR or file, if available}

### Summary
{2-3 sentence summary of the design approach}

### Requesting Review On
{Populate from the design document. If there are open questions, TBD
markers, or significant trade-offs, list each as a bullet. If none
exist, write "General review — no specific items flagged."}

### Documents
- `design.md` — technical design document
{If `04-testplan.md` was published, add:
- `testplan.md` — behavioral test cases mapped to PRD requirements
Otherwise, omit the testplan bullet entirely.}

### How to Review
- Comment inline on specific sections
- Approve when the design accurately reflects a viable implementation approach
```

Determine `{owner}/{repo}` from `docs_repo_remote`, then create the
draft PR. Set `{pr-title}` based on whether `{issue-key}` is a Jira
key: if yes, use `{issue-key}: Design - {title}`; otherwise use
`Design: {title}`.

First, check whether a PR already exists for this branch:

```bash
"$PUBLISH_SCRIPT" check-existing --repo {owner}/{repo} --head {branch-name}
```

If exit code is 5, a PR already exists — skip to Step 6 and report its
URL. Parse the PR number from the returned JSON. If the command fails
(non-zero exit other than 5), stop and report the error. If exit code
is 0, create a new PR:

```bash
"$PUBLISH_SCRIPT" create-pr \
  --repo {owner}/{repo} \
  --base {base-branch} \
  --head {branch-name} \
  --title "{pr-title}" \
  --body-file .artifacts/design/{issue-key}/08-pr-description.md \
  --draft
```

The script prints the PR URL on stdout. Parse the PR number from the URL path.

### Step 6: Save Publish Metadata

If `04-testplan.md` was published:

```bash
"$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/design/{issue-key}/publish-metadata.json \
  release={release} \
  feature={feature} \
  design_file_path={release}/{feature}/design.md \
  testplan_file_path={release}/{feature}/testplan.md \
  pr_number={pr-number} \
  branch={branch-name}
```

If no testplan was published, omit `testplan_file_path`:

```bash
"$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/design/{issue-key}/publish-metadata.json \
  release={release} \
  feature={feature} \
  design_file_path={release}/{feature}/design.md \
  pr_number={pr-number} \
  branch={branch-name}
```

### Step 7: Report to User

Present:
- PR URL
- Docs repo and branch name
- File location in the docs repo
- Next steps (share with reviewers, wait for comments, then use `/respond`)

## Output

- `.artifacts/config.json` (workspace-level config, created if it didn't exist)
- `.artifacts/design/{issue-key}/publish-metadata.json`
- Design document committed and pushed to feature branch in the docs repo
- Draft PR created against the docs repo
- `.artifacts/design/{issue-key}/08-pr-description.md`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
