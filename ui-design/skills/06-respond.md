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

Using the PR number and repo from `publish-metadata.json`, fetch comments
with paginated API queries that capture inline review comments and thread
identifiers:

```bash
gh api --paginate "repos/{upstream_repo}/pulls/{pr_number}/comments" \
  --jq '.[] | {id, path, body, in_reply_to_id, created_at, user: .user.login}'
gh api --paginate "repos/{upstream_repo}/pulls/{pr_number}/reviews" \
  --jq '.[] | {id, state, body, user: .user.login}'
gh api --paginate "repos/{upstream_repo}/issues/{pr_number}/comments" \
  --jq '.[] | {id, body, created_at, user: .user.login}'
```

Store the `id` of each review comment and thread for use in Step 6.

**Scope limitation:** The REST API endpoints above return individual
inline review comments and top-level PR comments, but do not return
GitHub review thread groupings (e.g., which inline comments form a
resolved/unresolved thread). To get full thread context including
resolution state, use the GraphQL API:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $pr: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $pr) {
        reviewThreads(first: 100) {
          nodes {
            isResolved
            comments(first: 50) {
              nodes { id databaseId body author { login } path line createdAt }
            }
          }
        }
      }
    }
  }' -f owner="{owner}" -f repo="{repo}" -F pr={pr_number}
```

If GraphQL is unavailable, fall back to the REST calls above and
reconstruct threads from `in_reply_to_id` chains. In this fallback
mode, thread resolution state is not available — note this in the
response log.

Parse the comments and organize by:
- **Inline comments** — tied to specific lines or sections (with thread IDs)
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

### Step 5: Apply Changes and Push

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

If document changes were made, copy the updated files to the docs repo,
commit, and push **before posting any PR comments** — this ensures
responses reference committed content:

Resolve `target_directory` from `publish-metadata.json` (the
`target_directory` field). Load `docs_repo_path` from
`.artifacts/config.json`. Verify the recorded branch is checked out and
the push remote is valid before committing.

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

### Step 6: Post Responses and Record

Post responses only after the corresponding document commit is confirmed
pushed. For each approved response, perform steps 6a–6d before moving to
the next comment.

#### 6a: Write response file safely

Use a heredoc with a quoted delimiter so reviewer-controlled content is
treated as literal data, preventing shell interpolation:

```bash
cat > .artifacts/ui-design/{issue-key}/pr-response-{N}.md << 'ENDOFRESPONSE'
{response}
ENDOFRESPONSE
```

#### 6b: Resolve root comment ID for inline replies

The GitHub `/replies` endpoint requires a top-level review comment ID.
If the selected comment is a nested reply (its `in_reply_to_id` is set),
walk the chain to find the root comment. Retain the originally selected
`{comment_id}` for the response log in Step 6d.

```bash
root_comment_id={comment_id}
while true; do
  parent_id=$(gh api "repos/{upstream_repo}/pulls/comments/${root_comment_id}" \
    --jq '.in_reply_to_id // empty')
  [ -z "$parent_id" ] && break
  root_comment_id="$parent_id"
done
```

#### 6c: Post the response

For inline replies, use the resolved `root_comment_id`:

```bash
gh api "repos/{upstream_repo}/pulls/{pr_number}/comments/${root_comment_id}/replies" \
  -F "body=@.artifacts/ui-design/{issue-key}/pr-response-{N}.md"
```

For general (non-inline) comments, use:

```bash
gh pr comment {pr_number} --repo "{upstream_repo}" \
  --body-file .artifacts/ui-design/{issue-key}/pr-response-{N}.md
```

#### 6d: Persist each response immediately

Append the log entry for this response to
`.artifacts/ui-design/{issue-key}/05-review-responses.md` immediately
after confirmed posting, before moving to the next comment. This ensures
that if the run is interrupted, already-posted responses are recorded and
will not be reposted on the next `/respond` invocation.

If the file does not exist yet, create it with the round header first:

```markdown
# Review Responses — {issue-key}

## Round {N} — {date}
```

Then append each entry immediately after posting:

```markdown
### Comment #{N}: {reviewer} on {section}

**Comment ID:** {comment_id} (originally selected comment)
**Root Comment ID:** {root_comment_id} (used for posting; same as Comment ID if not a nested reply)
**Thread ID:** {root_comment_id from Step 6b for inline review comments; "N/A" for general comments}
**Timestamp:** {ISO timestamp when response was posted}
**Comment:** {text}
**Category:** {category}
**Response:** {what was posted}
**Document change:** {what was changed, or "None"}
**Post result:** {success / failed — include error if failed}
```

#### 6e: Clean up

After all responses have been posted, clean up the individual response
files — their content is captured in the per-response log entries above:

```bash
rm -f .artifacts/ui-design/{issue-key}/pr-response-*.md
```

### Step 7: Verify Response Log

Verify that `.artifacts/ui-design/{issue-key}/05-review-responses.md`
contains an entry for every response posted in this round. This file is
the persistent record of all review interactions and must survive across
sessions.

### Step 8: Report to User

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
