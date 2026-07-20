---
name: feedback-submit
description: Commit, push, and post review-thread replies for an existing PR after a /feedback round. Explicit submit path — do not run from /feedback.
---

# Submit Feedback to Existing PR Skill

You are submitting the results of a `/feedback` round to an existing pull
request. Invocation of this skill is the explicit signal to commit, push,
and post replies — do not infer submit intent from other user messages.

## Your Role

1. Re-run validation and verify comment-response fixes were applied
2. Stage and commit feedback changes
3. Push to the fork remote
4. Post review-thread replies from `comment-responses.json`
5. Report commit SHA, push result, and reply outcomes

## Prerequisites

- A pull request already exists for the current branch (created earlier via
  `/pr` or manually). If you cannot locate it with certainty, stop and ask
  the user for the PR URL or number — do not create a new PR.
- Feedback changes are in the working tree (and/or staged). Prefer that
  `/feedback` has already written
  `.artifacts/bugfix/{issue}/comment-responses.json`.

If `comment-responses.json` is missing entirely, stop and ask the user how
to proceed (e.g., confirm `/feedback` ran, or explicitly proceed with
commit/push but no posted replies) — don't push a branch and only surface
the gap afterward in the report.

If the file exists but some entries have no `comment_id` (expected for
feedback gathered from user-provided text rather than a PR — see
`feedback.md` Step 1), that's benign: skip posting for those entries and
note it in the report as usual.

## Process

### Step 1: Locate the Project Repository

Work in the **target project** directory (where the PR branch lives), not
the ai-workflows install tree. If unclear, ask the user.

### Step 2: Run Validation

**Gate: do not commit or push until all checks pass.**

Validation must run in the repository directory from Step 1, not in the
workflow install tree or any other context. This ensures changes are
validated against the target project's actual CI equivalent.

Read and follow `../../_shared/recipes/validation-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| PROJECT_DIR | The repository directory from Step 1 (explicit — do not allow default or inherit from pr.md) |
| SCOPE | `full` |

**If any check fails:** Stop. Fix the failure and re-run. Do not proceed
to commit.

### Step 3: Verify Fixes Were Applied

Before committing, confirm that each response recorded in
`comment-responses.json` reflects an actual code change — not just a
claimed one.

If `comment-responses.json` is missing (per Prerequisites), skip this
step and proceed to **Stage and Commit**.

For each entry in `.artifacts/bugfix/{issue}/comment-responses.json`:

1. Fetch the original comment for context:
   ```bash
   gh api repos/{owner}/{repo}/pulls/comments/{comment_id}
   ```
2. Check `git diff HEAD` for a change matching the response. Read the
   relevant file if the diff alone isn't conclusive.
3. If the response claims a change but the diff shows none, or the
   change doesn't match what the response describes, flag it.

If any entries are flagged, stop and report them to the user — do not
commit until they confirm how to proceed (fix the code, or correct the
response). Otherwise, proceed to **Stage and Commit**.

### Step 4: Stage and Commit

Work in the repository located in Step 1.

**Stage changes selectively** — don't blindly `git add .`:

```bash
# Review what would be staged
git diff --stat

# Stage the relevant files (exclude .artifacts/ unless the user asks to commit them)
git add path/to/changed/files

# Verify staging
git status
```

**Commit with a structured message:**

```bash
git commit -m "[SCOPE]: SHORT_DESCRIPTION

DETAILED_DESCRIPTION"
```

Follow conventional commit format. The scope should identify the affected
component.

### Step 5: Push to Fork

Before pushing, resolve the existing PR (URL or `owner/repo#number`) from
the current branch, session context, or prior `/pr` output. If you cannot
find it with certainty, **stop and ask the user where the PR is**. Do not
invent remotes, branches, forks, or PR URLs.

```bash
git push -u fork BRANCH_NAME
```

Push to the `fork` remote, never `origin`.

If push fails due to missing fork remote or auth, stop and report the
error — ask the user how to proceed.

### Step 6: Post Review Replies

If `.artifacts/bugfix/{issue}/comment-responses.json` has entries with
`comment_id`, post each as a review-thread reply:

```bash
gh api repos/acme/myproject/pulls/42/comments \
  -f body='Switched to Optional pattern as suggested (fixed in abc1234).' \
  -F in_reply_to=123456
```

Use each entry's `comment_id` and `response`. Mention the commit SHA when
helpful. Skip entries without `comment_id` or where `"posted": true`.

**After each successful post**, update the entry in
`comment-responses.json` with `"posted": true` and write the file back
to disk immediately. This ensures retries skip already-posted replies.

If a reply fails, stop and report which comments were posted and which
failed — do not claim the feedback was fully submitted.

### Step 7: Confirm and Report

Summarize:

- Commit SHA
- Push result (remote and branch)
- PR URL
- Which review replies were posted (or skipped)

Append a short **Submission** note under the latest `## Feedback Round`
section in `session-context.md` (commit SHA, push, reply count).

## Output

- Pushed commit(s) on the existing PR branch
- Posted review-thread replies (when comment IDs were available)
- Updated session context with submission details

## When This Phase Is Done

Report the submission results, then **stop and wait**. Do not re-read the
controller. (If invoked by an automated orchestrator, return control to it.)
