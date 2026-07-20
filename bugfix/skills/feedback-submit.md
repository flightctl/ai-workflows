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
- `.artifacts/bugfix/{issue}/comment-responses.json` **must exist**. This
  file is created by `/feedback` and contains the responses to post on the
  PR.

If `comment-responses.json` does not exist:
- **Stop immediately**. Report to the user: "comment-responses.json is
  missing. Run `/feedback` first to create the responses artifact, or use
  `/pr` to submit code changes without posting feedback replies."
- Do not proceed with this skill.

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

### Step 3: Run Self-Review Gate

Run the self-review gate to validate code quality and alignment with
responses recorded in `comment-responses.json`.

Reference: `../../_shared/recipes/self-review-gate.md`

**Inputs:**
| Input | Value |
|-------|-------|
| PROJECT_DIR | The repository directory from Step 1 |
| SCOPE | `full` |

**If the gate fails:** Stop. Address findings and re-run the gate.
Do not proceed to commit until validation passes.

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
