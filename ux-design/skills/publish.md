---
name: publish
description: Push the handoff spec as a GitHub PR for external review.
---

# Publish — Post Handoff Spec

Post the finalized handoff spec as a GitHub pull request so technical
reviewers and stakeholders can review it.

## Critical Rules

- **Confirm before pushing.** Verify the target repository, branch name, and PR details with the user.
- **Draft PR.** Always create as a draft — the user decides when to mark it ready for review.
- **No force-push.** No destructive git operations.
- **No direct commits to main.** Always use a feature branch.

## Process

### Step 1: Read the Handoff Spec

Read `.artifacts/ux-design/{issue-key}/05-handoff.md`.

If the file doesn't exist, tell the user that `/handoff` should be run first.

Read `00-context.md` and verify that the context is `enriched` and the handoff
is approved against the current discovery revision. If the manifest marks the
handoff stale or its revision differs, stop and recommend `/handoff` before
publishing. Never publish a handoff produced from exploratory context.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at `.artifacts/config.json`.

Before resolving the configured path, determine `{source_repo_root}` by
running `git rev-parse --show-toplevel` from anywhere inside the source repo.
If this command fails, stop and ask the researcher to open the source-repo
workspace. The shared config stores `docs_repo_path` relative to this root.
Resolve a relative configured or researcher-supplied path against
`{source_repo_root}`; keep an absolute path absolute. Use the normalized
absolute result as runtime `{docs_repo_path}` for all validation, `git -C`
commands, filesystem paths, and provenance targets below. Never pass the raw
relative config value to Git or file operations.

**If the config exists**, read it and validate:
1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the remote URL matches the configured `docs_repo_remote`

**If the config does not exist**, ask the user:
- **Docs repo local path:** Where is the planning docs repo checked out? Accept
  an absolute path or a path relative to `{source_repo_root}`.
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote get-url origin`
  and confirm the result with the user

Validate the resolved path and remote, then save `docs_repo_path` relative to
`{source_repo_root}` and `docs_repo_remote` to the shared config. Keep using
the resolved absolute `{docs_repo_path}` for the rest of this phase.

Derive `{owner}/{repo}` from the remote URL (e.g.,
`git@github.com:org/repo.git` → `org/repo`).

### Step 3: Pre-Flight Checks

Verify the environment:

```bash
gh auth status
```

```bash
git -C "{docs_repo_path}" remote -v
```

```bash
git -C "{docs_repo_path}" status --porcelain
```

If the output is not empty, stop and tell the researcher the docs repo has
uncommitted changes that must be resolved before publishing. Do not proceed
with a dirty working tree.

Confirm with the user:
- **Base branch:** Which branch should the PR target? (usually `main`)
- **Release:** Which release is this for?
- **Feature:** A short, lowercase, hyphenated slug with the issue key appended
- **Branch name:** Propose `ux-design/{issue-key}` and let the user override

The handoff spec file path in the docs repo: `{release}/{feature}/handoff.md`.

### Step 4: Create Branch and Commit

All git operations run against the **docs repo**. Use
`git -C "{docs_repo_path}"` for all commands.

```bash
git -C "{docs_repo_path}" checkout -b {branch-name} {base-branch}
```

```bash
mkdir -p "{docs_repo_path}/{release}/{feature}"
```

```bash
cp ".artifacts/ux-design/{issue-key}/05-handoff.md" "{docs_repo_path}/{release}/{feature}/handoff.md"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{release}/{feature}/handoff.md"`.

Provenance at publish time:
- If `.artifacts/ux-design/{issue-key}/provenance.json` exists from `/handoff`,
  `/revise`, or `/respond`, the footer reflects the full authoring session
  (`provenance_kind: session`).
- If the log is missing, the render recipe **auto-captures a commit-time
  snapshot** (`phase=commit`, `provenance_kind: commit_only`) so stale footers
  are replaced instead of copied forward.
- Only if the user explicitly declines provenance, pass `ALLOW_MISSING=yes` to
  strip the footer and record `provenance_kind: declined`.

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/handoff.md"
```

```bash
git -C "{docs_repo_path}" commit -m "Add UX design handoff for {issue-key}: {title}"
```

### Step 5: Prepare PR Description

Prepare the PR description and save it to `.artifacts/ux-design/{issue-key}/06-pr-description.md`
(in the source repo's artifact directory):

```markdown
## UX Design Handoff: {title}

**Jira:** {issue-link}

### Summary
{2-3 sentence summary of what this handoff spec covers}

### Requesting Review On
- Component mapping accuracy
- State enumeration completeness
- Acceptance criteria clarity
- Interaction specs correctness

### How to Review
- Comment inline on specific sections
- Flag any missing states or interaction edge cases
- Approve when the handoff spec is implementation-ready
```

### Step 6: Push and Create PR

```bash
git -C "{docs_repo_path}" push -u origin {branch-name}
```

Create a draft PR:

```bash
gh pr create --draft --repo {owner}/{repo} --base {base-branch} --head {branch-name} --title "{issue-key}: UX Design Handoff - {title}" --body-file .artifacts/ux-design/{issue-key}/06-pr-description.md
```

### Step 7: Save Publish Metadata

Write `.artifacts/ux-design/{issue-key}/publish-metadata.json`:

```json
{
  "release": "{release}",
  "feature": "{feature}",
  "handoff_file_path": "{release}/{feature}/handoff.md",
  "pr_number": "{pr-number}",
  "branch": "{branch-name}"
}
```

### Step 8: Report to User

Present:
- PR URL
- Docs repo and branch name
- File location in the docs repo
- Next steps (share with reviewers, then use `/respond` when comments arrive)

## Output

- `.artifacts/ux-design/{issue-key}/06-pr-description.md`
- `.artifacts/ux-design/{issue-key}/publish-metadata.json`
- Handoff spec committed and pushed to feature branch in the docs repo
- Draft PR created against the docs repo

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
