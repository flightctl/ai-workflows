---
name: pr
description: Create a pull request for a bug fix, handling fork workflows, authentication, and remote setup systematically.
---

# Create Pull Request Skill

You are preparing to submit a bug fix as a pull request. This skill provides a
systematic, failure-resistant process for getting code from the working directory
into a PR. It handles the common obstacles: authentication, fork workflows,
remote configuration, and cross-repo PR creation.

## IMPORTANT: Follow This Skill Exactly

This skill exists because ad-hoc PR creation fails in predictable ways.
**Do not improvise.** Follow the numbered steps in order. Do not skip steps.
Do not invent alternative approaches when a step fails — use the documented
fallback ladder at the bottom of this file.

## Your Role

Get the bug fix changes submitted as a draft pull request. Handle the full
git workflow: branch, commit, push, and PR creation. When steps fail, follow
the documented recovery paths instead of guessing.

## Critical Rules

- **Never ask the user for git credentials.** Use `gh auth status` to check.
- **Never push directly to upstream.** Always use a fork remote. This applies
  even if you are authenticated as an org bot or app — do not assume any
  account has push access to upstream. Always go through a fork.
- **Never skip pre-flight checks.** They prevent every common failure.
- **Always create a draft PR.** Let the author mark it ready after review.
- **Always work in the project repo directory**, not the workflow directory.
- **Never attempt `gh repo fork` without asking the user first.**
- **Never fall back to patch files without exhausting all other options.**

## Process

### Placeholders Used in This Skill

These are determined during pre-flight checks. Record each value as you go.

| Placeholder | Source | Example |
| --- | --- | --- |
| `GH_USER` | Step 1a: `gh api user` or `/installation/repositories` (for bots) | `jsmith` |
| `UPSTREAM_OWNER/REPO` | Step 1d: `gh repo view --json nameWithOwner` | `acme/myproject` |
| `FORK_OWNER` | Step 2: owner portion of fork's `nameWithOwner`, or `GH_USER` if newly created | `jsmith` |
| `REPO` | The repository name (without owner) | `myproject` |
| `BRANCH_NAME` | Step 4: the branch you create | `bugfix/issue-42-null-check` |
| `ISSUE_KEY` | Branch name, artifact (e.g. pr-description.md), or context (e.g. Jira EDM-3407, GitHub #47) | `EDM-3407` or `#47` |

### Step 0: Locate the Project Repository

If the project repo is already the current workspace (e.g., opened in Cursor or
the IDE), skip this step — you're already in it.

Otherwise (sandboxed environments, CI pipelines), locate the project repo:

```bash
ls /workspace/repos/ 2>/dev/null
```

`cd` into the project repo directory before proceeding. All subsequent git
commands run from there.

If the user provides a path or the repo is obvious from session context
(prior commands, artifacts), use that directly.

### Step 1: Pre-flight Checks

Run ALL of these before doing anything else. Do not skip any.

**1a. Check GitHub CLI authentication and determine GH_USER:**

```bash
gh auth status
```

- If authenticated, determine `GH_USER` — the **real user's** GitHub username
  (not the bot). Try these in order:

```bash
# Works for normal user tokens:
gh api user --jq .login 2>/dev/null

# If that fails (403), you're running as a GitHub App/bot.
# Get the real user from the app installation:
gh api /installation/repositories --jq '.repositories[0].owner.login'
```

The `/installation/repositories` endpoint works because GitHub Apps are
installed on user accounts — the repo owner is the actual user.

- If not authenticated: note this — several later steps depend on `gh`. But
  do NOT dump all manual instructions yet. Continue the remaining pre-flight
  checks (1b–1e) to gather as much information as possible from git alone.
  After pre-flight, you will present options to the user.

**1b. Check git configuration:**

```bash
git config user.name
git config user.email
```

- If both are set: proceed.
- If missing and `gh` is authenticated: set them using `GH_USER` from Step 1a:

```bash
git config user.name "GH_USER"
git config user.email "GH_USER@users.noreply.github.com"
```

- If missing and `gh` is NOT authenticated: set reasonable defaults so commits
  work. Use `"bugfix-workflow"` / `"bugfix@workflow.local"` as placeholders.

**1c. Inventory existing remotes:**

```bash
git remote -v
```

Note which remote points to the upstream repo and which (if any) points to
the user's fork. Common patterns:

| Remote Name | URL Contains | Likely Role |
| --- | --- | --- |
| `origin` | upstream org | Upstream (read-only) |
| `origin` | user's name | Fork (read-write) |
| `fork` | user's name | Fork (read-write) |
| `upstream` | upstream org | Upstream (read-only) |

**1d. Identify the upstream repo:**

If `gh` is authenticated:

```bash
gh repo view --json nameWithOwner --jq .nameWithOwner
```

If `gh` is NOT authenticated, extract from the git remote URL:

```bash
git remote get-url origin | sed -E 's#.*/([^/]+/[^/]+?)(\.git)?$#\1#'
```

Record the result as `UPSTREAM_OWNER/REPO` — you'll need it later.

**1e. Check current branch and changes:**

```bash
git status
git diff --stat
```

Confirm there are actual changes to commit. If there are no changes, stop
and tell the user.

**Pre-flight summary:** Before moving on, you should now know:
`UPSTREAM_OWNER/REPO`, which remotes exist, and whether there are changes to
commit. You may also know `GH_USER` (if auth is available).

**If `gh` is authenticated:** Continue to Step 2. Do NOT skip Step 2 based on
the account type — even org bots and GitHub Apps need a fork.

**If `gh` is NOT authenticated — STOP and ask the user.** Present their
options clearly:

> GitHub CLI authentication is not available in this environment, which means
> I can't push branches or create PRs directly.
>
> I can still prepare everything (branch, commit, PR description). To get it
> submitted, you have a few options:
>
> 1. **Set up `gh auth`** in this environment (`gh auth login`) and I'll
     >    handle the rest
> 2. **Tell me your fork URL** if you already have one — I may be able to
     >    push to it
> 3. **I'll prepare the branch and PR description**, and give you the exact
     >    commands to push and create the PR from your own machine
>
> Which would you prefer?

**Wait for the user to respond.** Then proceed accordingly:

- Option 1: User sets up auth → re-run Step 1a, continue normally
- Option 2: User provides fork → set `FORK_OWNER` from it, skip to Step 3
- Option 3: Continue through Steps 2–5 (branch, commit, PR description) but
  skip Steps 6–7 (push, PR creation). At the end, provide the user with
  the exact push and PR creation commands — but only ONE set of clear
  instructions, not a wall of text

### Step 2: Ensure a Fork Exists

You almost certainly do NOT have push access to the upstream repo. Use a fork.

**Determining FORK_OWNER:** The fork owner is almost always `GH_USER` (the
authenticated GitHub username from Step 1a). When the `gh repo list` command
below returns a fork, its `nameWithOwner` will be in `FORK_OWNER/REPO` format —
use the owner portion. If the user creates a new fork, `FORK_OWNER` = `GH_USER`.

**Check if the user has a fork:**

```bash
gh repo list GH_USER --fork --json nameWithOwner,parent --jq '.[] | select(.parent.owner.login == "UPSTREAM_OWNER" and .parent.name == "REPO") | .nameWithOwner'
```

Replace `GH_USER` with the value from Step 1a. Replace `UPSTREAM_OWNER` and
`REPO` with the two parts of `UPSTREAM_OWNER/REPO` from Step 1d (e.g., for
`acme/myproject`, use `UPSTREAM_OWNER` = `acme` and `REPO` = `myproject`).

**Note:** The GitHub API returns the parent as separate `.parent.owner.login`
and `.parent.name` fields — it does NOT have a `.parent.nameWithOwner` field.

The output will be `FORK_OWNER/REPO` (e.g., `jsmith/myproject`). Record
the owner portion as `FORK_OWNER`.

**If a fork exists:** use it — skip ahead to Step 3.

**If NO fork exists — HARD STOP.** You cannot continue without a fork.
Do not try to push to upstream. Do not create a patch file. Do not try
API workarounds. Ask the user:

> I don't see a fork of `UPSTREAM_OWNER/REPO` under your GitHub account
> (`GH_USER`). I need a fork to push the branch and create a PR.
>
> Would you like me to try creating one? If that doesn't work in this
> environment, you can create one yourself at:
> `https://github.com/UPSTREAM_OWNER/REPO/fork`
>
> Let me know when you're ready and I'll continue.

**Then stop. Do not proceed until the user responds.**

Once the user confirms, try creating the fork:

```bash
gh repo fork UPSTREAM_OWNER/REPO --clone=false
```

- If this succeeds: continue to Step 3.
- If this fails (sandbox/permission issue): tell the user to create the fork
  manually using the URL above. **Stop again and wait for the user to confirm
  the fork exists before continuing.**

Do not proceed to Step 3 until a fork actually exists and you have confirmed
it with:

```bash
gh repo view GH_USER/REPO --json nameWithOwner --jq .nameWithOwner
```

### Step 3: Configure the Fork Remote

Once a fork exists (or was found), ensure there's a git remote pointing to it.

```bash
# Check if fork remote already exists
git remote -v | grep FORK_OWNER
```

If not present, add it:

```bash
git remote add fork https://github.com/FORK_OWNER/REPO.git
```

Use `fork` as the remote name. If `origin` already points to the fork, that's
fine — just use `origin` in subsequent commands instead of `fork`.

### Step 3a: Check Fork Sync Status

**Why this check exists:** When a user's fork is out of sync with upstream,
particularly when upstream has added workflow files (`.workflows/`) that
don't exist in the fork, pushing a feature branch can fail with a confusing
error like:

```
refusing to allow a GitHub App to create or update workflow `.workflows/foo.yml` without `workflows` permission
```

This happens because GitHub sees the push as "creating" workflow files (from
the fork's perspective), even though the feature branch simply includes files
that already exist in upstream. The GitHub App typically doesn't have `workflows`
permission by design.

**Detection:**

```bash
# Fetch the fork to get its current state
git fetch fork

# Check for workflow file differences between fork/main and local main
# (local main should be synced with upstream)
WORKFLOW_DIFF=$(git diff fork/main..main -- .workflows/ --name-only 2>/dev/null)

if [ -n "$WORKFLOW_DIFF" ]; then
  echo "Fork is out of sync with upstream (workflow files differ):"
  echo "$WORKFLOW_DIFF"
fi
```

**If workflow differences exist — attempt automated sync:**

```bash
# Try to sync the fork's main branch with upstream
gh api --method POST repos/FORK_OWNER/REPO/merge-upstream -f branch=main
```

- If this succeeds: fetch the fork again (`git fetch fork`) and continue
- If this fails (usually due to workflow permission restrictions): guide the
  user to sync manually

**If automated sync fails — STOP and guide the user:**

> Your fork is out of sync with upstream and contains workflow file differences.
> This prevents me from pushing because GitHub would interpret it as creating
> workflow files, which requires special permissions.
>
> Please sync your fork by either:
>
> 1. **Via GitHub web UI:** Visit https://github.com/FORK_OWNER/REPO and click
     >    "Sync fork" → "Update branch"
>
> 2. **Via command line** (may require `gh auth refresh -s workflow` first):
     >    ```
>    gh repo sync FORK_OWNER/REPO --branch main
>    ```
>
> Let me know when the sync is complete and I'll continue with the PR.

**After user confirms sync — rebase and continue:**

```bash
# Fetch the updated fork
git fetch fork

# Rebase the feature branch onto the synced fork/main
git rebase fork/main

# Continue to Step 4 (create branch)
```

### Step 4: Create a Branch

```bash
git checkout -b bugfix/BRANCH_NAME
```

Branch naming conventions:

- `bugfix/issue-NUMBER-SHORT_DESCRIPTION` if there's an issue number
- `bugfix/SHORT_DESCRIPTION` if there's no issue number
- Use kebab-case, keep it under 50 characters

If a branch already exists with the changes (from a prior `/fix` phase), use
it instead of creating a new one.

### Step 5: Self-Review Gate

Before committing, run a self-review of the changes to catch issues before
they reach external reviewers.

Read and follow `../../_shared/recipes/self-review-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff HEAD` |
| MAX_ROUNDS | `3` |
| CONTEXT_FILES | `.artifacts/bugfix/{issue}/root-cause.md`, `.artifacts/bugfix/{issue}/implementation-notes.md` (if they exist) |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user. Do not proceed to commit until the user
decides how to handle them.

If the gate reports PASS, proceed to Step 6. Any code fixes made by the
gate are uncommitted changes that will be included in the commit below.

**Note:** The bugfix workflow also has an optional `/review` phase that
provides a thorough, interactive review with findings and verdict. The
self-review gate here is a different mechanism — an automated quality check
that fixes obvious issues without user interaction, similar to running lint
before pushing.

### Step 6: Stage and Commit

This is the **only** phase that creates git commits. All code changes from
prior phases (`/fix`, `/test`, etc.) plus any fixes from the self-review
gate should be in the working tree as an uncommitted diff. This step
consolidates them into a single commit.

**Stage changes selectively** — don't blindly `git add .`:

```bash
# Review what would be staged
git diff --stat

# Stage the relevant files (exclude .artifacts/ and other non-code files)
git add path/to/changed/files

# Verify staging
git status
```

**Commit with a structured message:**

```bash
git commit -m "[SCOPE]: SHORT_DESCRIPTION

DETAILED_DESCRIPTION

Fixes #ISSUE_NUMBER"
```

Follow conventional commit format. The scope should identify the affected
component. Reference the issue number if one exists.

If prior artifacts exist (root cause analysis, implementation notes), use them
to write an accurate commit message. Don't make up details.

### Step 7: Push to Fork

```bash
git push -u fork bugfix/BRANCH_NAME
```

**If this fails:**

- **Authentication error**: Check `gh auth status` again. The user may need
  to re-authenticate or the sandbox may be blocking network access.
- **Remote not found**: Verify the fork remote URL is correct.
- **Permission denied**: The fork remote may be pointing to upstream, not the
  actual fork. Verify with `git remote get-url fork`.

If push requires sandbox permissions, tell the user: "The push needs network
access. Please run: `git push -u fork BRANCH_NAME`"

### Step 8: Create the Draft PR

**PR title format:** Use **`[ISSUE_KEY]: short description in lowercase`**. If the artifact `.artifacts/bugfix/{issue}/pr-description.md` exists and has a `## Title` line in this format, use that title. Otherwise set `ISSUE_KEY` from the branch name or context (e.g. Jira EDM-1234, GitHub #47) and build the title as `[ISSUE_KEY]: short description`.

**Try `gh pr create` first** (it works for normal user tokens):

```bash
gh pr create \
  --draft \
  --repo UPSTREAM_OWNER/REPO \
  --head FORK_OWNER:bugfix/BRANCH_NAME \
  --base main \
  --title "[ISSUE_KEY]: short description in lowercase" \
  --body-file .artifacts/bugfix/{issue}/pr-description.md
```

**Key flags explained:**

- `--repo`: The upstream repository (where the PR goes). REQUIRED for cross-fork PRs.
- `--head`: Must be `FORK_OWNER:BRANCH_NAME` format for fork-based PRs. Without the
  owner prefix, GitHub looks for the branch on the upstream repo and fails.
- `--base`: The target branch on upstream (usually `main`).
- `--draft`: Always submit as draft first.
- `--title`: PR title must be `[ISSUE_KEY]: short description`. Prefer the title from the artifact's `## Title` section if present.
- `--body-file`: Use the PR description artifact if `/document` was run.

**If `--body-file` artifact doesn't exist**, use `--body` with inline content:

```bash
gh pr create \
  --draft \
  --repo UPSTREAM_OWNER/REPO \
  --head FORK_OWNER:bugfix/BRANCH_NAME \
  --base main \
  --title "[ISSUE_KEY]: short description in lowercase" \
  --body "## Problem
WHAT_WAS_BROKEN

## Root Cause
WHY_IT_WAS_BROKEN

## Fix
WHAT_THIS_PR_CHANGES

## Testing
HOW_THE_FIX_WAS_VERIFIED

## Confidence
HIGH_MEDIUM_LOW — BRIEF_JUSTIFICATION

## Rollback
HOW_TO_REVERT_IF_SOMETHING_GOES_WRONG

## Risk Assessment
LOW_MEDIUM_HIGH — WHAT_COULD_BE_AFFECTED

Fixes #ISSUE_NUMBER"
```

**If `gh pr create` fails (403, "Resource not accessible by integration", etc.):**

This is the expected outcome when running as a GitHub App bot. Do NOT retry,
do NOT debug further, do NOT fall back to a patch file. Instead:

1. **Write the PR description** to `.artifacts/bugfix/{issue}/pr-description.md`
   (if not already written). This ensures the user has the body ready to paste.

2. **Give the user a pre-filled GitHub compare URL:**

   ```text
   https://github.com/UPSTREAM_OWNER/REPO/compare/main...FORK_OWNER:bugfix/BRANCH_NAME?expand=1
   ```

   This URL opens GitHub's "Open a pull request" form with the branches
   pre-selected and the description field ready to fill in.

3. **Provide the PR title and body** so the user can paste them in. The title
   must follow `[ISSUE_KEY]: short description in lowercase`. Show the title
   as a single line and the body as a code block for easy copying.

4. **Remind the user** to check "Create draft pull request" if they want
   it as a draft.

**If "branch not found"**: The push in Step 7 may have failed silently.
Verify with `git ls-remote fork bugfix/BRANCH_NAME`.

### Step 9: Confirm and Report

After the PR is created (or the URL is provided), summarize:

- PR URL (or manual creation URL)
- What was included in the PR
- What branch it targets
- Any follow-up actions needed (mark ready for review, add reviewers, etc.)

## Fallback Ladder

When something goes wrong, work down this list. **Do not skip to lower
rungs** — always try the higher options first.

### Rung 1: Fix and Retry (preferred)

Most failures have a specific cause (wrong remote, auth scope, branch name).
Diagnose it using the Error Recovery table and retry.

### Rung 2: Manual PR via GitHub Compare URL

If `gh pr create` fails but the branch is pushed to the fork (this is the
**expected** outcome when running as a GitHub App bot):

1. **Write the PR body** to `.artifacts/bugfix/{issue}/pr-description.md`
2. **Provide the compare URL**: `https://github.com/UPSTREAM_OWNER/REPO/compare/main...FORK_OWNER:BRANCH?expand=1`
3. **Show the PR title and body** for the user to paste in. The PR title must follow `[ISSUE_KEY]: short description in lowercase`.
4. **Note**: this is a good outcome — the user gets a pre-filled PR form

### Rung 3: User creates fork, you push and PR

If no fork exists and automated forking fails:

1. Give the user the fork URL: `https://github.com/UPSTREAM_OWNER/REPO/fork`
2. **Wait for the user to confirm the fork exists**
3. Add the fork remote, push the branch, create the PR

### Rung 4: Patch file (absolute last resort)

Only if ALL of the above fail — for example, the user has no GitHub account,
or network access is completely blocked:

1. Generate a patch: `git diff > bugfix.patch`
2. Write it to `.artifacts/bugfix/{issue}/bugfix.patch`
3. Explain to the user how to apply it: `git apply bugfix.patch`
4. **Acknowledge this is a degraded experience** and explain what prevented the normal flow

## Output

- The PR URL (printed to the user)
- Optionally updates `.artifacts/bugfix/{issue}/pr-description.md` if it didn't already exist

## Usage Examples

**After completing the workflow:**

```text
/pr
```

**With a specific issue reference:**

```text
/pr Fixes #47 - include all documented tool types in OpenAPI spec
```

**When the fork is already set up:**

```text
/pr --repo openresponses/openresponses
```

## Error Recovery Quick Reference

| Symptom | Cause | Fix |
| --- | --- | --- |
| `gh auth status` fails | Not logged in | User must run `gh auth login` |
| `git push` permission denied | Pushing to upstream, not fork | Verify remote URL, switch to fork |
| `git push` "refusing to allow...without `workflows` permission" | Fork out of sync with upstream (missing workflow files) | Run Step 3a: sync fork, then rebase and retry push |
| `gh pr create` 403 / "Resource not accessible" | Bot installed on user, not upstream org | Give user the compare URL (Rung 2) — this is expected |
| `gh repo fork` fails | Sandbox blocks forking | User creates fork manually |
| Branch not found on remote | Push failed silently | Re-run `git push`, check network |
| No changes to commit | Changes already committed or not staged | Check `git status`, `git log` |
| Wrong base branch | Upstream default isn't `main` | Check with `gh repo view --json defaultBranchRef` |

## Notes

- This skill assumes the bug fix work (code changes, tests) is already done.
  Run `/fix` and `/test` first.
- If `/document` was run, the PR description artifact should already exist at
  `.artifacts/bugfix/{issue}/pr-description.md`. Use its `## Title` line
  for the PR title if it follows `[ISSUE_KEY]: description`.
- If `/document` was NOT run, this skill creates a minimal PR body from
  session context (conversation history, prior artifacts). Build the title as
  `[ISSUE_KEY]: short description`.
- The fork workflow is the standard for open source contributions. Even if the
  user has write access to upstream, using a fork keeps the upstream clean.

## When This Phase Is Done

Report your results:

- PR URL (or manual creation URL if automated creation wasn't possible)
- What was included
- Any follow-up actions needed (mark ready for review, add reviewers, etc.)

Then **re-read the controller** (`skills/controller.md`) for next-step guidance.
