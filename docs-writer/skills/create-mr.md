---
name: create-mr
description: Create a GitLab merge request for documentation changes, handling fork workflows, authentication, and remote setup systematically.
---

# Create Merge Request

You are preparing to submit documentation changes as a merge request. This skill provides a systematic, failure-resistant process for getting changes from the working directory
into an MR on GitLab. It handles common obstacles: authentication, fork workflows, remote configuration, and cross-fork MR creation.

## IMPORTANT: Follow This Skill Exactly

This skill exists because ad-hoc MR creation fails in predictable ways.
**Do not improvise.** Follow the numbered steps in order.
Do not skip steps.
Do not invent alternative approaches when a step fails — use the documented
fallback ladder at the bottom of this file.

## Your Role

Get the documentation changes submitted as a draft merge request. Handle the full git workflow: branch, commit, push, and MR creation. When steps fail, follow the documented
recovery paths instead of guessing.

## Critical Rules

- **Never ask the user for git credentials.** Use `glab auth status` to check.
- **Never push directly to upstream** unless the user explicitly confirms they have write access. Default to using a fork.
- **Never skip pre-flight checks.** They prevent every common failure.
- **Always create a draft MR.** Let the author mark it ready after review.
- **Never attempt `glab repo fork` without asking the user first.**

## Process

### Placeholders Used in This Skill

These are determined during pre-flight checks. Record each value as you go.

| Placeholder        | Source                                 | Example                                                   |
|--------------------|----------------------------------------|-----------------------------------------------------------|
| `GL_USER`          | Step 1a: `glab api user`               | `jsmith`                                                  |
| `UPSTREAM_PROJECT` | Step 1d: project path from remote URL  | `red-hat-enterprise-openshift-documentation/edge-manager` |
| `FORK_PROJECT`     | Step 2: user's fork path               | `jsmith/edge-manager`                                     |
| `BRANCH_NAME`      | Step 4: the branch you create          | `docs/RHEM-456-enrollment-api`                            |
| `TICKET_ID`        | From artifacts directory or user input | `RHEM-456`                                                |

### Step 1: Pre-flight Checks

Run ALL of these before doing anything else. Do not skip any.

**1a. Check GitLab CLI authentication and determine GL_USER:**

```bash
glab auth status
```

- If authenticated, determine `GL_USER`:

```bash
glab api user --jq .username
```

- If not authenticated: note this and continue the remaining pre-flight checks (1b–1e) to gather as much information as possible from git alone. After pre-flight, present options
  to the user.

**1b. Check git configuration:**

```bash
git config user.name
git config user.email
```

- If both are set: proceed.
- If missing and `glab` is authenticated: set them using `GL_USER` from Step 1a:

```bash
git config user.name "GL_USER"
git config user.email "GL_USER@users.noreply.gitlab.com"
```

- If missing and `glab` is NOT authenticated: set reasonable defaults so commits work. Use `"docs-workflow"` / `"docs@workflow.local"` as placeholders.

**1c. Inventory existing remotes:**

```bash
git remote -v
```

Note which remote points to the upstream repo and which (if any) points to
the user's fork. Common patterns:

| Remote Name | URL Contains       | Likely Role                                 |
|-------------|--------------------|---------------------------------------------|
| `origin`    | upstream group/org | Upstream (may or may not have write access) |
| `origin`    | user's namespace   | Fork (read-write)                           |
| `fork`      | user's namespace   | Fork (read-write)                           |
| `upstream`  | upstream group/org | Upstream (read-only)                        |

**1d. Identify the upstream project:**

If `glab` is authenticated:

```bash
glab repo view --output json | jq -r '.full_path // .path_with_namespace'
```

If `glab` is NOT authenticated, extract from the git remote URL:

```bash
git remote get-url origin | sed -E 's#.*[:/]([^/]+/[^/]+?)(\.git)?$#\1#'
```

Record the result as `UPSTREAM_PROJECT`.

**1e. Check current branch and changes:**

```bash
git status
git diff --stat
```

Confirm there are actual changes to commit. If there are no changes, stop and tell the user.

**Pre-flight summary:** Before moving on, you should now know:
`UPSTREAM_PROJECT`, which remotes exist, and whether there are changes to commit. You may also know `GL_USER` (if auth is available).

**If `glab` is authenticated:** Continue to Step 2.

**If `glab` is NOT authenticated — STOP and ask the user.** Present their
options clearly:

> GitLab CLI authentication is not available in this environment, which
> means I can't push branches or create MRs directly.
>
> I can still prepare everything (branch, commit, MR description). To get
> it submitted, you have a few options:
>
> 1. **Set up `glab auth`** in this environment (`glab auth login`) and
     > I'll handle the rest
> 2. **Tell me your fork URL** if you already have one — I may be able to
     > push to it
> 3. **I'll prepare the branch and MR description**, and give you the exact
     > commands to push and create the MR from your own machine
>
> Which would you prefer?

**Wait for the user to respond.** Then proceed accordingly.

### Step 2: Determine Push Strategy

Unlike GitHub, many GitLab projects grant contributors direct push access.
Check whether the user can push to the upstream project before setting up a fork.

**Ask the user:**

> Do you have write (push) access to `UPSTREAM_PROJECT`? If yes, I'll push
> the branch directly. If not (or you're unsure), I'll use a fork.

- **Direct push:** Skip fork setup. Use `origin` (or whichever remote points to upstream) as the push target. Continue to Step 4.
- **Fork workflow:** Continue to Step 3.

### Step 3: Ensure a Fork Exists (fork workflow only)

**Check if the user has a fork:**

```bash
glab repo fork --list 2>/dev/null || glab api "projects/$(echo UPSTREAM_PROJECT | sed 's|/|%2F|g')/forks" --jq '.[].path_with_namespace' | grep GL_USER
```

**If a fork exists:** record its path as `FORK_PROJECT` and skip ahead to configure the remote.

**If NO fork exists — ask the user:**

> I don't see a fork of `UPSTREAM_PROJECT` under your GitLab account
> (`GL_USER`). I need a fork to push the branch and create an MR.
>
> Would you like me to try creating one? If that doesn't work, you can
> create one yourself at:
> `https://gitlab.cee.redhat.com/UPSTREAM_PROJECT/-/forks/new`
>
> Let me know when you're ready and I'll continue.

**Stop and wait for the user to respond.** Once confirmed:

```bash
glab repo fork UPSTREAM_PROJECT --clone=false
```

**Configure the fork remote:**

```bash
git remote -v | grep GL_USER
```

If not present, add it:

```bash
git remote add fork https://gitlab.cee.redhat.com/FORK_PROJECT.git
```

### Step 4: Create a Branch

```bash
git checkout -b docs/BRANCH_NAME
```

Branch naming conventions:

- `docs/TICKET_ID-SHORT_DESCRIPTION` if there's a ticket (e.g. `docs/RHEM-456-enrollment-api`)
- `docs/SHORT_DESCRIPTION` if there's no ticket
- Use kebab-case, keep it under 50 characters

If a branch already exists with the changes (from a prior `/apply` phase), use it instead of creating a new one.

### Step 5: Stage and Commit

**Stage changes selectively** — don't blindly `git add .`:

```bash
git diff --stat
git add path/to/changed/files
git status
```

**Commit with a structured message:**

```bash
git commit -m "[TICKET_ID]: SHORT_DESCRIPTION

DETAILED_DESCRIPTION"
```

Use prior artifacts (context, plan) to write an accurate commit message.
Don't make up details.

### Step 6: Push

**Direct push (write access):**

```bash
git push -u origin docs/BRANCH_NAME
```

**Fork push:**

```bash
git push -u fork docs/BRANCH_NAME
```

**If push fails:**

- **Authentication error**: Check `glab auth status`. User may need to re-authenticate.
- **Permission denied**: Verify the remote URL points to the correct project.
- **Remote not found**: Re-check `git remote -v`.

### Step 7: Create the Draft Merge Request

**MR title format:** Use `[TICKET_ID]: short description in lowercase`.

**Direct push (user has write access):**

```bash
glab mr create \
  --draft \
  --source-branch docs/BRANCH_NAME \
  --target-branch main \
  --title "[TICKET_ID]: short description" \
  --description "DESCRIPTION" \
  --yes
```

**Fork workflow:**

```bash
glab mr create \
  --draft \
  --repo UPSTREAM_PROJECT \
  --head FORK_PROJECT \
  --source-branch docs/BRANCH_NAME \
  --target-branch main \
  --title "[TICKET_ID]: short description" \
  --description "DESCRIPTION" \
  --yes
```

**Building the description:** Use the MR description prepared by the `/apply` phase at `.artifacts/${ticket_id}/04-mr-description.md`. If the file does not exist, build the
description from the context artifact (`01-context.md`) and plan artifact (`02-plan.md`).

**If `glab mr create` fails:**

1. **Write the MR description** to `.artifacts/${ticket_id}/04-mr-description.md`

2. **Give the user a pre-filled GitLab MR URL:**

   Direct push:
   ```text
   https://gitlab.cee.redhat.com/UPSTREAM_PROJECT/-/merge_requests/new?merge_request[source_branch]=docs/BRANCH_NAME&merge_request[target_branch]=main
   ```

   Fork:
   ```text
   https://gitlab.cee.redhat.com/UPSTREAM_PROJECT/-/merge_requests/new?merge_request[source_project_id]=FORK_PROJECT_ID&merge_request[source_branch]=docs/BRANCH_NAME&merge_request[target_branch]=main
   ```

3. **Provide the MR title and description** for the user to paste in.

### Step 8: Confirm and Report

After the MR is created (or the URL is provided), summarize:

- MR URL (or manual creation URL)
- What was included in the MR
- What branch it targets
- The Jira ticket reference (if any)
- Any follow-up actions needed (mark ready for review, add reviewers, etc.)

## Fallback Ladder

When something goes wrong, work down this list. **Do not skip to lower rungs** — always try the higher options first.

### Rung 1: Fix and Retry (preferred)

Most failures have a specific cause (wrong remote, auth scope, branch name).
Diagnose it using the Error Recovery table and retry.

### Rung 2: Manual MR via GitLab URL

If `glab mr create` fails but the branch is pushed:

1. **Write the MR description** to `.artifacts/${ticket_id}/04-mr-description.md`
2. **Provide the new MR URL** for the user to open in their browser
3. **Show the MR title and description** for the user to paste in

### Rung 3: User pushes manually

If push fails due to network or auth restrictions:

1. Provide the exact `git push` and `glab mr create` commands
2. Include the MR title and description for copy-paste

### Rung 4: Patch file (absolute last resort)

Only if ALL of the above fail:

1. Generate a patch: `git diff > docs-changes.patch`
2. Write it to `.artifacts/${ticket_id}/docs-changes.patch`
3. Explain how to apply it: `git apply docs-changes.patch`
4. **Acknowledge this is a degraded experience**

## Error Recovery Quick Reference

| Symptom                      | Cause                                   | Fix                                 |
|------------------------------|-----------------------------------------|-------------------------------------|
| `glab auth status` fails     | Not logged in                           | User must run `glab auth login`     |
| `git push` permission denied | No write access to remote               | Switch to fork workflow (Step 3)    |
| `glab mr create` fails       | Auth or permission issue                | Give user the MR URL (Rung 2)       |
| `glab repo fork` fails       | Sandbox/permission restriction          | User creates fork manually          |
| Branch not found on remote   | Push failed silently                    | Re-run `git push`, check network    |
| No changes to commit         | Changes already committed or not staged | Check `git status`, `git log`       |
| Wrong target branch          | Upstream default isn't `main`           | Check with `git remote show origin` |

## When This Phase Is Done

Report your results:

- MR URL (or manual creation URL if automated creation wasn't possible)
- What was included
- Any follow-up actions needed (mark ready for review, add reviewers, etc.)
