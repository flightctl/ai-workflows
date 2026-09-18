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
1. `.artifacts/ui-design/{workspace-id}/publish-metadata.json` (PR details)
2. `.artifacts/ui-design/{workspace-id}/02-ui-design.md` (current UI design)
3. `.artifacts/ui-design/{workspace-id}/03-api-findings.md` (if it exists)

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
resolution state, use the GraphQL API.

Before running the GraphQL query, split `upstream_repo` (from
`publish-metadata.json`) into `{owner}` and `{repo}` components:
`{owner}` = path segment before the last `/`, `{repo}` = last path
segment with `.git` suffix stripped. For example,
`my-org/my-repo` yields `owner=my-org`, `repo=my-repo`; and
`my-org/my-repo.git` also yields `owner=my-org`, `repo=my-repo`.

**Validate the derived values.** If either `{owner}` or `{repo}` is
empty after splitting (e.g., `upstream_repo` has no `/` separator, or
the repo segment is blank after stripping `.git`), stop and report the
error to the user: *"Could not derive owner/repo from upstream_repo
value '{upstream_repo}'. Check publish-metadata.json."* Do not attempt
the GraphQL query with empty values.

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $pr) {
        reviewThreads(first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            isResolved
            comments(first: 50) {
              nodes { id databaseId body author { login } path line createdAt }
            }
          }
        }
        # NOTE: The nested comments(first: 50) connection has no cursor
        # pagination. Threads with more than 50 comments may be truncated
        # here. This is intentional — the paginated REST endpoints above
        # are authoritative for full comment content. GraphQL is used for
        # thread-resolution metadata (isResolved) and structural discovery;
        # REST is the fallback for complete comment data in long threads.
      }
    }
  }' -f owner="{owner}" -f repo="{repo}" -F pr={pr_number}
```

**Pagination.** The query fetches up to 100 threads per page. If
`pageInfo.hasNextPage` is `true`, re-run the query with
`-f cursor="{endCursor}"` to fetch the next page. Repeat until
`hasNextPage` is `false`. Merge all `nodes` arrays before processing.

If GraphQL is unavailable, fall back to the REST calls above (which
already use `--paginate`) and reconstruct threads from
`in_reply_to_id` chains. In this fallback mode, thread resolution
state is not available — note this in the response log.

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

**If all approved responses are clarification-only** (every response has
Document change: "None"), skip this entire step — no document commit or
provenance capture is needed. Proceed directly to Step 6.

**If any approved response requires a document change**, apply them:

For each approved response that requires a document change:

1. Update `02-ui-design.md` (and `03-api-findings.md` if affected)
2. Propagate ripple effects (same rules as `/revise` Step 3)
3. Update source markers if needed

After all changes are applied:

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={workspace-id}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={workspace-id}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/ui-design/{workspace-id}/02-ui-design.md`.

Copy the updated files to the docs repo, commit, and push **before
posting any PR comments** — this ensures responses reference committed
content:

Resolve `target_directory` from `publish-metadata.json` (the
`target_directory` field). Load `docs_repo_path` from
`.artifacts/config.json`. Verify the recorded branch is checked out and
the push remote is valid before committing.

```bash
cp ".artifacts/ui-design/{workspace-id}/02-ui-design.md" "{target_directory}/ui-design.md"
# If api-findings.md was updated:
cp ".artifacts/ui-design/{workspace-id}/03-api-findings.md" "{target_directory}/api-findings.md"
```

Render provenance footer on the docs-repo copies before staging.

```bash
git -C "{docs_repo_path}" add "{target_directory}/ui-design.md"
# If api-findings.md was updated during this phase:
git -C "{docs_repo_path}" add "{target_directory}/api-findings.md"
git -C "{docs_repo_path}" commit -m "Address review feedback for {workspace-id} UI design"
git -C "{docs_repo_path}" push
```

### Step 6: Post Responses and Record

Apply the document-change check **per-response**, not globally. In a
mixed batch of responses:

- Responses **with** document changes: post only after the
  corresponding document commit from Step 5 is confirmed pushed.
- Responses **without** document changes (Document change: None):
  post immediately as clarification-only — no commit or push
  confirmation is needed for these responses.

If **all** approved responses are clarification-only (every response has
Document change: None), Step 5 was skipped entirely and no push is
needed — post all responses directly.

For each approved response, perform steps 6a–6d before moving to
the next comment.

#### 6a: Write response file safely

Use a heredoc with a quoted delimiter so reviewer-controlled content is
treated as literal data, preventing shell interpolation:

```bash
cat > .artifacts/ui-design/{workspace-id}/pr-response-{N}.md << 'ENDOFRESPONSE'
{response}
ENDOFRESPONSE
```

If the response text contains a line matching the heredoc delimiter, use
the agent's file-writing tool instead of shell heredoc.

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

**Persist an "unknown" post state before the API call.** Before
attempting the GitHub API post, write a preliminary entry to
`05-review-responses.md` with `Post result: pending` and
`API Response ID: unknown`. This ensures that if the process crashes
during the API call, the entry exists and the next `/respond`
invocation can detect the ambiguous state.

**Lookup-before-retry.** Before posting, check
`05-review-responses.md` for an existing entry with the same
`Comment ID` in this round.

- If found with a successful `Post result` and a non-`"unknown"`
  `API Response ID`, this response was already posted — skip it to
  avoid duplicates.
- If found with `Post result: pending` or `API Response ID: unknown`,
  perform a **GitHub lookup** before re-posting: query the PR's
  comment thread for a reply matching this response's body text to
  determine whether the prior attempt actually succeeded. If a
  matching reply is found, update the existing entry with the
  discovered `API Response ID` and skip re-posting. If no matching
  reply is found, proceed with posting.
- If found with a failed `Post result`, proceed with posting.

For inline replies, use the resolved `root_comment_id`:

```bash
gh api "repos/{upstream_repo}/pulls/{pr_number}/comments/${root_comment_id}/replies" \
  -F "body=@.artifacts/ui-design/{workspace-id}/pr-response-{N}.md"
```

For general (non-inline) comments, use:

```bash
gh pr comment {pr_number} --repo "{upstream_repo}" \
  --body-file .artifacts/ui-design/{workspace-id}/pr-response-{N}.md
```

**Capture the API response ID.** After each successful post, extract
the comment or review ID from the API response (the `id` field in the
JSON response for `gh api` calls, or parse the URL from `gh pr comment`
output). Store this value for the response log in Step 6d. If the API
returns a success status but the response does not contain an `id`
field, record `API Response ID` as `"unknown"` rather than omitting it.

#### 6d: Update the response entry after posting

Update the preliminary entry (written in Step 6c before the API call)
in `.artifacts/ui-design/{workspace-id}/05-review-responses.md` with the
final post result and API response ID. Do this immediately after
confirmed posting, before moving to the next comment. This ensures
that if the run is interrupted, already-posted responses are recorded
with their final status and will not be reposted on the next `/respond`
invocation.

If the file does not exist yet, create it with the round header first:

```markdown
# Review Responses — {workspace-id}

## Round {N} — {date}
```

Then append each entry immediately after posting:

```markdown
### Comment #{N}: {reviewer} on {section}

**Comment ID:** {comment_id} (originally selected comment)
**Root Comment ID:** {root_comment_id} (used for posting; same as Comment ID if not a nested reply)
**Timestamp:** {ISO timestamp when response was posted}
**Comment:** {text}
**Category:** {category}
**Response:** {what was posted}
**Document change:** {what was changed, or "None"}
**Post result:** {success / failed — include error if failed}
**API Response ID:** {id returned by the GitHub API response on successful post; "N/A" on failure}
```

#### 6e: Clean up

After all responses have been posted, clean up the individual response
files — their content is captured in the per-response log entries above:

```bash
rm -f .artifacts/ui-design/{workspace-id}/pr-response-*.md
```

### Step 7: Verify Response Log

Verify that `.artifacts/ui-design/{workspace-id}/05-review-responses.md`
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

- `.artifacts/ui-design/{workspace-id}/02-ui-design.md` (updated, if changes were made)
- `.artifacts/ui-design/{workspace-id}/03-api-findings.md` (updated, if it exists and was affected)
- `.artifacts/ui-design/{workspace-id}/05-review-responses.md`
- `.artifacts/ui-design/{workspace-id}/provenance.json` (updated, if changes were made)
- Updated PR in docs repo (if changes were pushed)

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Document changes made
- Unresolved objections (if any)
- PR approval status
- Recommendation on next step (`/respond` again, or `/sync` if approved)

Then return to the invoking workflow router for completion guidance.
