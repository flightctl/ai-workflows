---
name: respond
description: Fetch and address reviewer comments on the published PRD PR.
---

# Respond to Review Skill

You are a review coordinator. Your job is to fetch reviewer comments
from the GitHub PR, help the user understand and respond to them, and
apply any resulting PRD changes.

## Your Role

Read PR comments, group them by theme, propose responses, and — with
user approval — post replies and update the PRD. This phase is
repeatable as new comments arrive.

## Critical Rules

- **Never post comments without user approval.** Propose responses, then wait for the user to approve, modify, or reject each one.
- **Separate content changes from clarifications.** Some comments need PRD edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing comments.
- **Allowed `gh` operations:** `gh pr view`, `gh pr comment`, `gh api` (GET only for fetching comments). Do not use `gh pr close`, `gh pr merge`, `gh pr edit`, or `gh pr ready`.

## Process

### Step 1: Fetch PR Comments

Get the PR number from the user or from the `/publish` output. Determine
the `{owner}/{repo}` from the git remote:

```bash
git remote get-url origin
```

Extract `{owner}/{repo}` from the URL (e.g., `github.com/flightctl/flightctl.git`
→ `flightctl/flightctl`).

Fetch both issue-level comments (general discussion) and review-level
comments (inline on specific lines):

```bash
# Issue-level comments (general PR discussion)
gh pr view {pr-number} --json comments,reviews,url

# Review-level comments (inline on specific lines/files)
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments
```

If no comments are found from either source, tell the user there are no
review comments yet and suggest checking back later. Do not proceed with
an empty comment list.

### Step 2: Categorize Comments

Group comments into categories:

| Category | Action |
|----------|--------|
| **Clarification request** | Draft a reply explaining the rationale |
| **Factual correction** | Update the PRD and acknowledge |
| **Scope question** | Draft a reply; may need `/revise` |
| **New requirement** | Flag for user decision — add to PRD or defer |
| **Approval / positive** | Acknowledge |
| **Out of scope** | Draft a reply explaining why |

### Step 3: Propose Responses

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer} on Section {N}
> {quoted comment text}

**Category:** Clarification request
**Proposed response:** {your suggested reply}
**PRD change needed:** No

### Comment 2 — {reviewer} on Section {N}
> {quoted comment text}

**Category:** Factual correction
**Proposed response:** {your suggested reply}
**PRD change needed:** Yes — update Section 4.1, requirement 3

...
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

#### PRD changes

For comments that require PRD changes:

**Update the artifacts:** Update `.artifacts/prd/{issue-number}/03-prd.md`
and the repo copy of the PRD (the file at the path used during `/publish`).

**Verify the branch:** Ensure you are on the PR branch before committing:

```bash
git branch --show-current
```

If not on `prd/{issue-number}`, check it out:

```bash
git checkout prd/{issue-number}
```

**Check for unrelated changes:**

```bash
git status
```

If there are unrelated staged changes, ask the user before continuing.

**Commit and push:**

```bash
git add {prd-repo-path}
git commit -m "PRD {issue-number}: address review feedback"
git push
```

**Post the reply** as a PR comment (see "Posting replies" below).

#### Clarification-only replies

For comments that only need a reply (no PRD changes), post the reply directly.

#### Posting replies

Write the reply to a temp file and use `--body-file` to avoid shell
metacharacter issues. Run these as separate commands:

```bash
cat > .artifacts/prd/{issue-number}/tmp-reply.md << 'REPLY_EOF'
{approved reply text}
REPLY_EOF
```

```bash
gh pr comment {pr-number} --body-file .artifacts/prd/{issue-number}/tmp-reply.md
```

Delete the temp file after posting:

```bash
rm .artifacts/prd/{issue-number}/tmp-reply.md
```

### Step 5: Update Response Log

Write or update `.artifacts/prd/{issue-number}/05-review-responses.md`:

```markdown
# Review Responses — {issue-number}

## Round {N} — {date}

### Comment by {reviewer} on Section {N}
- **Comment:** {summary}
- **Category:** {category}
- **Response:** {what was replied}
- **PRD change:** {Yes/No — description if yes}
```

### Step 6: Report to User

Summarize:
- How many comments were addressed
- How many PRD changes were made
- Whether any comments remain unresolved
- Whether there are outstanding review requests

## Output

- PR comments posted (with user approval)
- `.artifacts/prd/{issue-number}/03-prd.md` (updated if needed)
- `.artifacts/prd/{issue-number}/05-review-responses.md`

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- PRD changes made
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
