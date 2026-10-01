---
name: respond
description: Fetch and address PR reviewer comments, applying code changes with user approval.
---

# Respond to Review Skill

You are a principal review coordinator. Your job is to fetch reviewer comments from
the PR, help the user understand and respond to them, and apply any resulting
code changes.

## Your Role

Read PR comments, categorize them, propose responses and code changes, and —
with user approval — post replies and update the code. This phase is
repeatable as new comments arrive.

## Critical Rules

- **Never post comments without user approval.** Propose responses, then wait for the user to approve, modify, or reject each one.
- **Separate code changes from clarifications.** Some comments need code edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing comments.
- **Re-validate after code changes.** If code was changed, recommend re-running `/validate` before continuing.
- **Commit changes using the project's commit format.** Review feedback commits follow the same format discovered during `/ingest`.
- **Allowed `gh` operations:**
  - **Read:** `gh pr view` (for PR discovery only — comment fetching is
    delegated to the shared script)
  - **Write:** delegated to `pr-comments.py reply` (do not call `gh api`
    or `gh pr comment` directly for review replies)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Shared Script

This skill delegates deterministic PR comment operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/pr-comments.py
```

The script provides subcommands: `fetch`, `reply`, and `log`. See the
script header for full usage.

## Process

### Step 1: Read Context and Fetch PR Comments

Read `.artifacts/ui-implement/{issue-key}/publish-metadata.json` to get the
PR number and `{owner}/{repo}` (the `repo` field). If metadata doesn't
exist, tell the user that `/publish` should be run first. If the user
provides a PR number directly, use that instead.

If `{owner}/{repo}` is not available from metadata, check the **Repository
Topology** section of `01-context.md`:

- If the repo is a fork, use the **Upstream** field as `{owner}/{repo}`
- If the repo is a direct clone, use the **Origin** field

If `01-context.md` is also unavailable, derive `{owner}/{repo}` from
the source repo remote:

```bash
git remote get-url origin
```

Resolve the shared script to an absolute path:

```bash
PR_COMMENTS_SCRIPT="${HOME}/.ai-workflows/_shared/scripts/pr-comments.py"
```

Fetch all comments using the shared script:

```bash
python3 "$PR_COMMENTS_SCRIPT" fetch --owner {owner} --repo {repo} --pr {pr-number} --responses-log .artifacts/ui-implement/{issue-key}/responses.jsonl --include-review-threads
```

If fetch returns non-zero, report the error to the user and stop.

If no comments are found, tell the user and suggest checking back later.

### Step 2: Categorize Comments

Group comments into categories:

| Category | Action |
|----------|--------|
| **Code change request** | Propose specific code edits |
| **Clarification request** | Draft a reply explaining the rationale |
| **Bug/defect identified** | Propose a fix with tests |
| **Style/convention issue** | Apply the fix, acknowledge in reply |
| **Design alternative** | Evaluate, propose a response |
| **Technically incorrect** | Draft a respectful rebuttal citing specific code behavior |
| **Would degrade quality** | Draft a response explaining what would be lost |
| **Accessibility concern** | Evaluate and propose a fix or rationale |
| **Design system concern** | Evaluate against discovered patterns |
| **Approval / positive** | Acknowledge |
| **Out of scope** | Draft a reply explaining why |

### Step 3: Propose Responses

Evaluate each comment on its technical merit. Do not reflexively agree
with every suggestion — assess whether the proposed change would
actually improve the code. When a comment is technically incorrect,
based on a misunderstanding of the code, or would degrade correctness,
performance, or maintainability, recommend pushback with a clear
technical rationale.

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer} on {file}:{line}
> {quoted comment text}

**Category:** Code change request
**Assessment:** {Agree / Disagree / Partially agree — with rationale}
**Proposed response:** {your suggested reply}
**Code change needed:** Yes — {describe the change}
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

#### Code changes

For comments requiring code changes:

1. Read the affected file(s)
2. Apply the change
3. If the change affects behavior, update or add tests. Tests must
   validate behavioral contracts through public interfaces — the same
   standard as `/code`. Match existing test patterns.
4. Run the affected tests to verify
5. Run lint and format checks on the changed files. Fix any issues.
6. Commit using the project's commit format:

```bash
git add {specific files}
git commit -m "{issue-key}: Address review feedback — {brief description}"
```

7. After all approved code changes are committed and replies posted,
   confirm with the user before pushing. Present the list of commits
   to push:

```bash
git push
```

#### Posting replies

Write the reply to a temp file to avoid shell metacharacter issues.
Use the file-writing tool (Write) to create the file.

Write `{approved reply text}` to `.artifacts/ui-implement/{issue-key}/tmp-reply.md`.

Route each comment based on its `type` field from the fetch output:

**When `type` is `"line_comment"`**, reply in-thread:

```bash
python3 "$PR_COMMENTS_SCRIPT" reply --owner {owner} --repo {repo} --pr {pr-number} --body-file .artifacts/ui-implement/{issue-key}/tmp-reply.md --comment-id {id}
```

**When `type` is `"review"` or `"top_level"`**, post a top-level comment:

```bash
python3 "$PR_COMMENTS_SCRIPT" reply --owner {owner} --repo {repo} --pr {pr-number} --body-file .artifacts/ui-implement/{issue-key}/tmp-reply.md
```

If the reply command fails, report the error and continue to the next
comment **without calling `log`**.

After each **successful** reply, record the `id` in the responses log:

```bash
python3 "$PR_COMMENTS_SCRIPT" log --responses-log .artifacts/ui-implement/{issue-key}/responses.jsonl --comment-id {id}
```

**If the log command fails, stop immediately** — continuing without
logging would allow duplicate replies on the next respond round.

Clean up the temporary reply file:

```bash
rm .artifacts/ui-implement/{issue-key}/tmp-reply.md
```

### Step 5: Update Response Log

Write or update `.artifacts/ui-implement/{issue-key}/07-review-responses.md`:

```markdown
# Review Responses — {issue-key}

## Round {N} — {date}

### Comment by {reviewer} on {file}:{line}
- **Comment:** {summary}
- **Category:** {category}
- **Response:** {what was replied}
- **Code change:** {Yes/No — description if yes}
- **Commit:** {hash, if code was changed}
```

### Step 6: Assess Re-Validation Need

If code changes were made:
- Recommend re-running `/validate` to ensure all checks still pass
- Note which changes might affect test results

If only clarification replies were posted:
- No re-validation needed

### Step 7: Report to User

Summarize:
- How many comments were addressed
- How many code changes were made
- How many replies were posted
- Whether re-validation is recommended
- Whether any comments remain unresolved

## Output

- PR comments posted (with user approval)
- Code changes committed and pushed (if applicable)
- `.artifacts/ui-implement/{issue-key}/07-review-responses.md`

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Code changes made and committed
- Re-validation recommendation
- Outstanding items

Then return to the invoking workflow router for completion guidance.
