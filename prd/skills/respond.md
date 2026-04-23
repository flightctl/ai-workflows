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
- **Allowed `gh` operations:**
  - **Read:** `gh pr view`, `gh api` GET (for fetching PR comments and review data)
  - **Write:** `gh pr comment` (for top-level replies), `gh api` POST to `pulls/{pr-number}/comments/{id}/replies` (for replying to line-level review comments)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Process

### Step 1: Resolve Docs Repo and Fetch PR Comments

Read `.artifacts/prd/config.json` to get the docs repo path and
`.artifacts/prd/{issue-number}/publish-metadata.json` to get the PR
number and file path. If either file doesn't exist, tell the user that
`/publish` should be run first.

Determine `{owner}/{repo}` from the `docs_repo_remote` in the config.
Extract the PR number from the publish metadata. If the `pr_number` field
is missing or null, `/publish` was likely interrupted before the PR was
created — suggest the user re-run `/publish`. If the user provides a PR
number directly, use that instead.

Validate the docs repo path still exists:

```bash
git -C "{docs_repo_path}" status
```

Fetch both issue-level comments (general discussion) and review-level
comments (inline on specific lines):

```bash
gh pr view {pr-number} --repo {owner}/{repo} --json comments,reviews,url
```

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments --paginate
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
| **Open question resolution** | Resolve the open question (see Step 4) |
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
**PRD change needed:** Yes — update Section 3.1, requirement 3

### Comment 3 — {reviewer} on Section 7 (open question 7.2)
> {quoted comment text, possibly spanning multiple replies in a thread}

**Category:** Open question resolution
**Proposed resolution:** {synthesized answer from the discussion}
**PRD change needed:** Yes — incorporate into Section {N}, remove open question 7.2

...
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

#### Resolving open questions

When reviewer comments relate to an open question from Section 7,
synthesize the discussion into a proposed resolution:

1. Identify which open question (7.1, 7.2, ...) the discussion relates to.
2. Read the full thread — there may be multiple reviewers with differing
   views. Synthesize the discussion into a single proposed resolution.
   Do not assume a single comment is the final answer. If reviewers
   disagree and no consensus is apparent, present the competing positions
   to the user and ask them to decide rather than fabricating a
   compromise that nobody advocated.
3. Determine the appropriate target section based on the **Impact** field
   of the open question — e.g., a scope decision becomes a non-goal in
   Section 2.3, a constraint goes into NFRs in Section 3.2, a requirement
   clarification updates the relevant FR in Section 3.1.
4. Present the proposed resolution to the user: show which open question
   is being resolved, the synthesized answer, where it will be placed in
   the PRD, and the proposed text. The user may approve, correct, or
   rewrite the synthesis.
5. After user approval, incorporate the answer into the target section,
   writing it in final form as if it was always the intent (do not
   narrate the resolution).
6. Remove the resolved entry from Section 7.
7. If Section 7 is now empty, remove the entire section (heading and
   introductory text) from the PRD.

#### PRD changes (other than open question resolutions)

For comments that require PRD changes:

**Check locked decisions:** Before applying any PRD change, read the
"Locked Decisions" section of `.artifacts/prd/{issue-number}/02-clarifications.md`
(if it exists). If a requested change contradicts a locked decision, flag the
conflict to the user rather than applying the change — locked decisions are
binding and cannot be overridden without explicit user approval.

**Update the local artifact:** Update `.artifacts/prd/{issue-number}/03-prd.md`
in the source repo.

**Update the docs repo copy:** Read `.artifacts/prd/{issue-number}/publish-metadata.json`
to get `{prd-file-path}` (the PRD's location within the docs repo). If the
metadata file doesn't exist, ask the user for the file path within the docs
repo. If they provide it, write it to `publish-metadata.json` so subsequent
runs don't re-ask, then proceed with the docs repo update. If they cannot
provide it, skip the docs repo update.

Copy the updated artifact to the docs repo and commit. All git operations use
the docs repo path from `.artifacts/prd/config.json`.

Fetch the latest state from the remote and verify the working tree is clean:

```bash
git -C "{docs_repo_path}" fetch origin
```

```bash
git -C "{docs_repo_path}" status
```

If there are uncommitted changes, ask the user before continuing.

Ensure the correct branch is checked out:

```bash
git -C "{docs_repo_path}" branch --show-current
```

If not on `prd/{issue-number}`, check it out:

```bash
git -C "{docs_repo_path}" checkout prd/{issue-number}
```

Fast-forward the local branch if the remote is ahead:

```bash
git -C "{docs_repo_path}" pull --ff-only
```

Ensure the target directory exists, copy the updated artifact, and commit.

Note: substitute `{prd-file-path}` into the command before running — do not
pass the placeholder literally.

```bash
mkdir -p "{docs_repo_path}/$(dirname "{prd-file-path}")"
```

```bash
cp ".artifacts/prd/{issue-number}/03-prd.md" "{docs_repo_path}/{prd-file-path}"
```

```bash
git -C "{docs_repo_path}" add "{prd-file-path}"
```

```bash
git -C "{docs_repo_path}" commit -m "PRD {issue-number}: address review feedback"
```

```bash
git -C "{docs_repo_path}" push
```

**Post the reply** as a PR comment (see "Posting replies" below).

#### Clarification-only replies

For comments that only need a reply (no PRD changes), post the reply directly.

#### Posting replies

Write the reply to a temp file to avoid shell metacharacter issues:

```bash
cat > .artifacts/prd/{issue-number}/tmp-reply.md << 'REPLY_EOF'
{approved reply text}
REPLY_EOF
```

**For line-level review comments** (those fetched via
`gh api .../pulls/{pr-number}/comments` — attached to a specific file and
line), reply in-thread so the response appears alongside the original
comment:

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments/{comment-id}/replies --field body=@.artifacts/prd/{issue-number}/tmp-reply.md
```

**For top-level PR comments** (those from `gh pr view --json comments` —
general conversation comments), use:

```bash
gh pr comment {pr-number} --repo {owner}/{repo} --body-file .artifacts/prd/{issue-number}/tmp-reply.md
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

### Open question 7.2 resolved — {reviewer} thread on Section 7
- **Comment:** {summary of discussion thread}
- **Category:** Open question resolution
- **Response:** {what was replied}
- **PRD change:** Yes — resolved open question 7.2, incorporated into Section 3.2 as NFR-3
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
