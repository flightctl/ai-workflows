---
name: feedback-submit
description: Commit, push, and post review-thread replies for an existing PR after a /feedback round. Explicit submit path — do not run from /feedback.
---

# Submit Feedback to Existing PR Skill

You are submitting the results of a `/feedback` round to an existing pull
request. Invocation of this skill is the explicit signal to commit, push,
and post replies — do not infer submit intent from other user messages.

## Your Role

1. Re-run validation and self-review gates
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

If `comment-responses.json` is missing, continue with commit/push but skip
posting replies and note that in the report.

## Process

### Step 1: Locate the Project Repository

Work in the **target project** directory (where the PR branch lives), not
the ai-workflows install tree. If unclear, ask the user.

### Step 2: Run Shared PR Gates (by title)

Read `pr.md` and execute **only** these steps, in order, matching by
**step title** (not step number):

1. **Run Validation**
2. **Self-Review Gate**
3. **Stage and Commit** — exclude `.artifacts/` unless the user asks to
   commit them
4. **Push to Fork** — push to the `fork` remote, never `origin`

Do **not** run **Create the Draft PR** — the PR already exists.

Before pushing or posting replies, resolve the existing PR (URL or
`owner/repo#number`) from the current branch, session context, or prior
`/pr` output. If you cannot find it with certainty, **stop and ask the
user where the PR is**. Do not invent remotes, branches, forks, or PR
URLs, and do not run setup steps from `pr.md` to "recover."

If push fails due to missing fork remote or auth, stop and report the
error — ask the user how to proceed.

### Step 3: Post Review Replies

If `.artifacts/bugfix/{issue}/comment-responses.json` has entries with
`comment_id`, post each as a review-thread reply:

```bash
gh api repos/acme/myproject/pulls/42/comments \
  -f body='Switched to Optional pattern as suggested (fixed in abc1234).' \
  -F in_reply_to=123456
```

Use each entry's `comment_id` and `response`. Mention the commit SHA when
helpful. Skip entries without `comment_id`.

If push or reply posting fails, stop and report the error — do not claim
the feedback was submitted.

### Step 4: Confirm and Report

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
