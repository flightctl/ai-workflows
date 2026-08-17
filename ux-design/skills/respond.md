---
name: respond
description: Fetch and address reviewer comments on the published handoff spec PR.
---

# Respond — Address Review Comments

Fetch reviewer comments from the GitHub PR, help the user understand and
respond to them, and apply any resulting handoff spec changes.

## Critical Rules

- **Never post comments without user approval.** Propose responses, then wait.
- **Separate content changes from clarifications.** Some comments need handoff spec edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing comments.
- **Allowed `gh` operations:**
  - **Read:** `gh pr view`, `gh api` GET
  - **Write:** `gh pr comment`, `gh api` POST to reply to review comments
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Process

### Step 1: Fetch PR Comments

Read `.artifacts/prd/config.json` to get the docs repo path and
`.artifacts/ux-design/{issue-key}/publish-metadata.json` to get the PR
number and `{branch-name}`. If either file doesn't exist, tell the user
that `/publish` should be run first.

Determine `{owner}/{repo}` from the config's `docs_repo_remote`.

```bash
gh pr view {pr-number} --repo {owner}/{repo} --json comments,reviews,url
```

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments --paginate
```

If no comments are found, tell the user and suggest checking back later.

### Step 2: Categorize Comments

| Category | Action |
|----------|--------|
| **Clarification request** | Draft a reply explaining the rationale |
| **Design alternative** | Evaluate the suggestion, propose a response |
| **Factual correction** | Update the handoff spec and acknowledge |
| **Scope question** | Draft a reply; may need `/revise` |
| **New requirement** | Flag for user decision — update or defer |
| **Approval / positive** | Acknowledge |

### Step 3: Propose Responses

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer}
> {quoted comment text}

**Category:** {category}
**Proposed response:** {your suggested reply}
**Handoff change needed:** {Yes/No — description if yes}
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

Update `.artifacts/ux-design/{issue-key}/04-handoff.md` with approved changes.

Update the docs repo copy:

```bash
git -C "{docs_repo_path}" checkout {branch-name}
```

```bash
git -C "{docs_repo_path}" pull --ff-only
```

```bash
cp ".artifacts/ux-design/{issue-key}/04-handoff.md" "{docs_repo_path}/{handoff_file_path}"
```

Run Vale against the updated file before staging:

```bash
vale "{docs_repo_path}/{handoff_file_path}"
```

If Vale reports errors, fix them in the source artifact and re-copy.
If Vale is not installed, note the skip and continue.

```bash
git -C "{docs_repo_path}" add "{handoff_file_path}"
```

```bash
git -C "{docs_repo_path}" commit -m "UX design {issue-key}: address review feedback"
```

```bash
git -C "{docs_repo_path}" push
```

Post approved replies using `gh pr comment` or `gh api` for line-level replies.

### Step 5: Report to User

Summarize:
- How many comments were addressed
- How many handoff spec changes were made
- Whether any comments remain unresolved

## Output

- PR comments posted (with user approval)
- `.artifacts/ux-design/{issue-key}/04-handoff.md` (updated if needed)

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Handoff spec changes made
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
