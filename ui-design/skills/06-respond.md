---
name: respond
description: Fetch and address PR reviewer comments on the published UI design document.
---

# Respond to Review Skill

You are a frontend architect responding to PR review feedback. Your job is
to fetch reviewer comments, propose responses, and update the UI design
document when changes are needed.

## Your Role

Read the PR review comments, understand each reviewer's concern, propose
a response for each, and get user approval before posting any reply or
making any change. When changes are needed, update the local artifacts
and push to the docs repo branch.

## Critical Rules

- **User approves every response.** Never post a PR comment or make a change without the user's explicit approval.
- **Understand before responding.** Read each comment in context — check which section of the document it refers to, and what the reviewer's concern actually is.
- **Maintain consistency.** When a reviewer's feedback causes a change, propagate ripple effects the same way `/revise` does — component renames, data flow changes, etc.
- **Preserve provenance.** After updating, capture a new provenance event.
- **Track responses.** Record all responses in `05-review-responses.md` for audit.

## Process

### Step 1: Read Current State

Read these files:
1. `.artifacts/ui-design/{issue-key}/publish-metadata.json` (PR details)
2. `.artifacts/ui-design/{issue-key}/02-ui-design.md` (current UI design)
3. `.artifacts/ui-design/{issue-key}/03-api-findings.md` (if it exists)

If `publish-metadata.json` doesn't exist, tell the user that `/publish`
should be run first.

### Step 2: Fetch PR Comments

Using the PR number and repo from `publish-metadata.json`:

```bash
gh pr view {pr_number} --repo "{upstream_repo}" --json comments,reviews
```

Parse the comments and organize by:
- **Inline comments** — tied to specific lines or sections
- **General comments** — overall feedback
- **Approval/change-request status** — who approved, who requested changes

If no new comments exist since the last `/respond` run (check
`05-review-responses.md` for previously addressed comments), report that
to the user.

### Step 3: Categorize Comments

For each comment, categorize it:

| Category | Action |
|----------|--------|
| **Question** | Prepare an answer based on the design document and context |
| **Correction** | Prepare a fix to the design document |
| **Suggestion** | Evaluate the suggestion and recommend accept/discuss |
| **Objection** | Flag for user decision — the reviewer disagrees with a design choice |
| **Out of scope** | Note that it's beyond the UI design scope |

### Step 4: Propose Responses

Present each comment to the user with a proposed response:

```text
Comment #{N} by {reviewer} on {section}:
  "{comment text}"

Category: {category}
Proposed response: {your proposed reply}
Document change: {what would change in 02-ui-design.md, or "None"}

Options:
  (a) Post as proposed
  (b) Edit the response
  (c) Skip this comment for now
```

Wait for the user's decision on each comment before proceeding.

### Step 5: Apply Changes

For each approved response that requires a document change:

1. Update `02-ui-design.md` (and `03-api-findings.md` if affected)
2. Propagate ripple effects (same rules as `/revise` Step 3)
3. Update source markers if needed

After all changes are applied:

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={issue-key}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={issue-key}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/ui-design/{issue-key}/02-ui-design.md`.

### Step 6: Post Responses

For each approved response, post the comment on the PR:

```bash
gh pr comment {pr_number} --repo "{upstream_repo}" --body "{response}"
```

For inline replies, use the appropriate `gh` command to reply to the
specific review comment thread.

### Step 7: Push Updates

If any document changes were made, copy the updated files to the docs repo
and push:

```bash
cp ".artifacts/ui-design/{issue-key}/02-ui-design.md" "{target_directory}/ui-design.md"
# If api-findings.md was updated:
cp ".artifacts/ui-design/{issue-key}/03-api-findings.md" "{target_directory}/api-findings.md"
```

Render provenance footer on the docs-repo copies before staging.

```bash
git -C "{docs_repo_path}" add "{target_directory}/"
git -C "{docs_repo_path}" commit -m "Address review feedback for {issue-key} UI design"
git -C "{docs_repo_path}" push
```

### Step 8: Record Responses

Write or update `.artifacts/ui-design/{issue-key}/05-review-responses.md`:

```markdown
# Review Responses — {issue-key}

## Round {N} — {date}

### Comment #{N}: {reviewer} on {section}

**Comment:** {text}
**Category:** {category}
**Response:** {what was posted}
**Document change:** {what was changed, or "None"}
```

### Step 9: Report to User

Present:
- How many comments were addressed
- How many document changes were made
- Whether any comments were skipped
- Whether any objections remain unresolved
- Current PR approval status

## Output

- `.artifacts/ui-design/{issue-key}/02-ui-design.md` (updated, if changes were made)
- `.artifacts/ui-design/{issue-key}/03-api-findings.md` (updated, if it exists and was affected)
- `.artifacts/ui-design/{issue-key}/05-review-responses.md`
- `.artifacts/ui-design/{issue-key}/provenance.json` (updated, if changes were made)
- Updated PR in docs repo (if changes were pushed)

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Document changes made
- Unresolved objections (if any)
- PR approval status
- Recommendation on next step (`/respond` again, or `/sync` if approved)

Then return to the invoking workflow router for completion guidance.
