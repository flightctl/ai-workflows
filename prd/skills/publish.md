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

## Shared Script

This skill delegates deterministic git and CLI operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/publish.py
```

The script provides subcommands: `preflight`, `resolve-remotes`, `push`,
`check-existing`, `create-pr`, and `save-metadata`. See the script header for
full usage.

## Process

### Prerequisites: Resolve Script Path

Before any `cd` or subshell that changes the working directory, resolve
the shared script to an absolute path so it remains valid:

```bash
PUBLISH_SCRIPT="$(git rev-parse --show-toplevel)/_shared/scripts/publish.py"
```

Use `$PUBLISH_SCRIPT` instead of the relative path in all subsequent
commands.

### Step 1: Read the PRD

Read `.artifacts/prd/{issue-key}/03-prd.md`.

If the file doesn't exist, tell the user that `/draft` should be run first.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at `.artifacts/config.json`.

**If the config exists**, read it and validate:

1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the configured `docs_repo_remote` matches at least one fetch or push
   URL in the docs repository; do not require it to be named `origin`

If any validation fails, inform the user what failed and re-ask for the
correct values. Resolve `~` to an absolute path before saving. Update
`.artifacts/config.json` with the corrected values.

**If the config does not exist**, ask the user:

- **Docs repo local path:** Where is the planning docs repo checked out?
  (e.g., `~/src/planning-docs`)
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote -v`, choose the
  docs repository URL without embedded credentials to save, and confirm it
  with the user before proceeding. Never save a token or password in
  `.artifacts/config.json`.
  The remote name is not part of the configuration contract.

Validate the path and remote. Resolve `~` to the user's home directory
so the stored path is absolute. Write `.artifacts/config.json` with the
validated `docs_repo_path` and `docs_repo_remote`.

### Step 3: Pre-Flight Checks

Run the shared pre-flight checks from the docs repo directory:

```bash
(cd "{docs_repo_path}" && python3 "$PUBLISH_SCRIPT" preflight --platform github)
```

Parse the output and check `auth_ok`. If `auth_ok=false`, **stop and
tell the user** that GitHub CLI authentication is required to push and
create a PR. Suggest running `gh auth login` and retrying `/publish`.
Do not continue to later steps without authentication.

If `auth_ok=true`, verify the docs repo state:

```bash
git -C "{docs_repo_path}" remote -v
```

```bash
git -C "{docs_repo_path}" status
```

Resolve the canonical PR target and the branch push destination:

Read and follow `../../_shared/recipes/resolve-docs-publish-remotes.md` with
`DOCS_REPO_PATH`, `CONFIGURED_DOCS_REPO_REMOTE`, and `BRANCH_NAME`. The shared
script invocation below performs that resolution and emits the recipe's
outputs as JSON.

```bash
(cd "{docs_repo_path}" && python3 "$PUBLISH_SCRIPT" resolve-remotes --configured-remote "{docs_repo_remote}")
```

Parse the JSON output and confirm these values with the user before modifying
or pushing the docs repository:

- `upstream_repo` — repository where the PR will be created
- `upstream_remote` — remote used to fetch the canonical base branch
- `push_remote` and `push_url` — destination for the feature branch
- `fork_owner` and `cross_repository` — values used to qualify the PR head

`push_url` is a credential-free display value. When a Git command needs the
actual push transport, derive it locally with `git remote get-url --push
"{push_remote}"`; do not copy credentials into workflow artifacts or prompts.

Provenance at publish time:
- If `.artifacts/prd/{issue-key}/provenance.json` exists from `/draft`, `/revise`,
  or `/respond`, the footer reflects the full authoring session (`provenance_kind:
  session`).
- If the log is missing, the render recipe **auto-captures a commit-time snapshot**
  (`phase=commit`, `provenance_kind: commit_only`) so stale footers are replaced
  instead of copied forward.
- Only if the user explicitly declines provenance, pass `ALLOW_MISSING=yes` to strip
  the footer and record `provenance_kind: declined` (no human-readable block).

Confirm with the user:
- **Base branch:** Which branch should the PR target in the docs repo?
  (usually `main`; confirm, don't assume)
- **Release:** Which release is this PRD for? (e.g., `v2.1`, `2026-Q2`).
  If the Jira issue has a fix version, suggest it as the default.
- **Feature:** A short, lowercase, hyphenated slug for the feature
  directory, with the Jira issue key appended (e.g., if the summary is
  "Container Port Mapping Support" and the issue is EDM-1471, suggest
  `port-mappings-EDM-1471`). Ask for **just the slug**, not a full path.
- **Branch name:** Propose `prd/{issue-key}` and let the user override.
  Use the confirmed value as `{branch-name}` in all subsequent steps.

These two values determine the PRD file path in the docs repo:
`{release}/{feature}/prd.md`. The filename is always `prd.md` — future
documents (design docs, test plans) will be placed alongside it in the
same directory. Do not show this path pattern as an input example — ask
for release and feature slug separately.

### Step 4: Create Branch and Commit

All git operations in this step run against the **docs repo**, not the source
repo. Use `git -C "{docs_repo_path}"` for all commands.

Verify the docs repo has no uncommitted, staged, or untracked changes
before modifying it:

```bash
git -C "{docs_repo_path}" status --porcelain
```

If the output is non-empty, the docs repo has local changes. **Stop and
ask the user** how to proceed — they may need to stash or commit those
changes first. Do not copy files into a dirty working tree.

Check if the branch already exists (locally or on the remote) before creating it:

```bash
git -C "{docs_repo_path}" branch --list {branch-name}
```

```bash
git -C "{docs_repo_path}" fetch {upstream-remote}
```

```bash
PUSH_URL_RAW="$(git -C "{docs_repo_path}" remote get-url --push "{push-remote}")"
git -C "{docs_repo_path}" ls-remote --heads "$PUSH_URL_RAW" "refs/heads/{branch-name}"
```

Depending on the results:

```bash
# If branch exists locally:
git -C "{docs_repo_path}" checkout {branch-name}

# If branch does not exist locally but exists on the push URL:
git -C "{docs_repo_path}" fetch "$PUSH_URL_RAW" "refs/heads/{branch-name}:refs/remotes/publish-push/{branch-name}"
git -C "{docs_repo_path}" checkout -b {branch-name} publish-push/{branch-name}

# If branch doesn't exist locally or remotely:
git -C "{docs_repo_path}" checkout -b {branch-name}
```

Copy the PRD artifact from the source repo to the docs repo:

```bash
mkdir -p "{docs_repo_path}/{release}/{feature}"
```

```bash
cp ".artifacts/prd/{issue-key}/03-prd.md" "{docs_repo_path}/{release}/{feature}/prd.md"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=prd`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{release}/{feature}/prd.md"`.

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/prd.md"
```

If `.artifacts/prd/{issue-key}/02-clarifications.md` exists, publish it
alongside the PRD:

```bash
cp ".artifacts/prd/{issue-key}/02-clarifications.md" "{docs_repo_path}/{release}/{feature}/clarifications.md"
```

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/clarifications.md"
```

If clarifications were published, use:

```bash
git -C "{docs_repo_path}" commit -m "Add PRD and clarifications for {issue-key}: {title}"
```

Otherwise:

```bash
git -C "{docs_repo_path}" commit -m "Add PRD for {issue-key}: {title}"
```

### Step 5: Push and Create PR

Push the branch using the shared script (run from the docs repo):

```bash
(cd "{docs_repo_path}" && python3 "$PUBLISH_SCRIPT" push --remote {push-remote} --branch {branch-name})
```

Prepare the PR description (AI-dependent — summarize the PRD content) and
save it to `.artifacts/prd/{issue-key}/04-pr-description.md` (in the source
repo's artifact directory):

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
- Review the open questions — these need your input
- Approve when the PRD accurately reflects the agreed requirements
```

Use `upstream_repo` from `resolve-remotes` as `{owner}/{repo}`, then check for
an existing PR before creating one. If `{issue-key}` is a Jira
key, prefix the title with it (`{issue-key}: PRD - {title}`); otherwise
use `PRD: {title}`.

Set `{head-ref}` to `{fork-owner}:{branch-name}` when `cross_repository=true`;
otherwise set it to `{branch-name}`.

First, check whether a PR already exists for this branch:

```bash
python3 "$PUBLISH_SCRIPT" check-existing --repo {owner}/{repo} --head {head-ref}
```

If exit code is 5, a PR already exists — skip to Step 6 and report its
URL. Parse the PR number from the returned JSON. If the command fails
(non-zero exit other than 5), stop and report the error. If exit code
is 0, create a new PR:

```bash
# When {issue-key} is a Jira key (e.g., EDM-1471):
python3 "$PUBLISH_SCRIPT" create-pr \
  --repo {owner}/{repo} \
  --base {base-branch} \
  --head {head-ref} \
  --title "{issue-key}: PRD - {title}" \
  --body-file .artifacts/prd/{issue-key}/04-pr-description.md \
  --draft

# When no issue key exists:
python3 "$PUBLISH_SCRIPT" create-pr \
  --repo {owner}/{repo} \
  --base {base-branch} \
  --head {head-ref} \
  --title "PRD: {title}" \
  --body-file .artifacts/prd/{issue-key}/04-pr-description.md \
  --draft
```

The script prints the PR URL on stdout. Parse the PR number from the URL path.

### Step 6: Save Publish Metadata

Save metadata for use by `/revise` and `/respond`:

```bash
python3 "$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/prd/{issue-key}/publish-metadata.json \
  release={release} \
  feature={feature} \
  prd_file_path={release}/{feature}/prd.md \
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
- `.artifacts/prd/{issue-key}/publish-metadata.json`
- PRD committed and pushed to feature branch in the docs repo
- Clarifications committed alongside PRD (if `02-clarifications.md` exists)
- Draft PR created against the docs repo
- `.artifacts/prd/{issue-key}/04-pr-description.md`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
