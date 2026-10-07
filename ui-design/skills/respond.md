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

### Step 1a: Check Out the PR Branch

After `/publish` completes, it restores the docs repo to the user's
original branch. `/respond` needs to be on the PR branch to push review
changes. Read the branch name from `publish-metadata.json` and check it
out in the docs repo:

```bash
DOCS_REPO_PATH=$(python3 -c "import json; print(json.load(open('.artifacts/config.json'))['docs_repo_path'])")
PR_BRANCH=$(python3 -c "import json; print(json.load(open('.artifacts/ui-design/{workspace-id}/publish-metadata.json'))['branch'])")
```

Check out the branch. If it doesn't exist locally, create a tracking
branch from the push remote:

```bash
if git -C "${DOCS_REPO_PATH}" show-ref --verify --quiet "refs/heads/${PR_BRANCH}"; then
  git -C "${DOCS_REPO_PATH}" checkout "${PR_BRANCH}"
else
  PUSH_REMOTE=$(python3 -c "import json; m=json.load(open('.artifacts/ui-design/{workspace-id}/publish-metadata.json')); print(m.get('push_repo','origin').split('/')[-1] if '/' in m.get('push_repo','origin') else 'origin')")
  git -C "${DOCS_REPO_PATH}" fetch "${PUSH_REMOTE}" "${PR_BRANCH}"
  git -C "${DOCS_REPO_PATH}" checkout -b "${PR_BRANCH}" "${PUSH_REMOTE}/${PR_BRANCH}"
fi
```

If the checkout fails, stop and report the error — the PR branch must
be available before proceeding.

### Step 2: Fetch PR Comments

If `gh` or the GitHub API is unavailable (command not found, auth
failure, or network error), stop and report the failure — do not
treat a failed fetch as "no comments found" or proceed with an empty
comment list.

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
        # NOTE: The nested comments(first: 50) has no cursor pagination.
        # Threads with >50 comments will be truncated here.
        # See the REST-as-source-of-truth rules below.
      }
    }
  }' -f owner="{owner}" -f repo="{repo}" -F pr={pr_number}
```

**REST as source of truth.** Follow these rules when merging REST and
GraphQL comment data:

1. **REST is the complete source of truth for comment content.** Use
   paginated REST responses to discover and process every comment —
   never skip or ignore a comment because it is absent from GraphQL
   results.
2. **GraphQL is metadata-only.** Use GraphQL only to attach `isResolved`
   status and thread grouping metadata when available. Do not rely on
   GraphQL for comment discovery or content.
3. **Missing GraphQL comments are expected.** Treat comments absent from
   GraphQL results as expected for long threads (>50 comments per
   thread), not as absent comments. The nested `comments(first: 50)`
   connection has no cursor pagination, so truncation is normal.

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

Read and follow `${HOME}/.ai-workflows/_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={workspace-id}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

Read and follow `${HOME}/.ai-workflows/_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={workspace-id}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/ui-design/{workspace-id}/02-ui-design.md`.

Copy the updated files to the docs repo, commit, and push **before
posting any PR comments** — this ensures responses reference committed
content:

Resolve `target_directory` from `publish-metadata.json` (the
`target_directory` field). Load `docs_repo_path` from
`.artifacts/config.json`. Canonicalize both paths (resolve symlinks
and `..` segments) and verify that `target_directory` is inside
`docs_repo_path` — if it is not, stop and report the mismatch before
copying any files. Verify the recorded branch is checked out and
the push remote is valid before committing.

```bash
cp ".artifacts/ui-design/{workspace-id}/02-ui-design.md" "{target_directory}/ui-design-{workspace-id}.md"
# If api-findings-{workspace-id}.md was updated:
cp ".artifacts/ui-design/{workspace-id}/03-api-findings.md" "{target_directory}/api-findings-{workspace-id}.md"
```

If `03-api-findings.md` does **not** exist (findings fit inline in
`02-ui-design.md`), delete any stale separate findings file from a
prior publish that may remain in the docs repo, and also remove the
private overflow file from the artifacts directory:

```bash
git -C "{docs_repo_path}" rm "{target_directory}/api-findings-{workspace-id}.md" 2>/dev/null || true
rm -f ".artifacts/ui-design/{workspace-id}/03-api-findings.md"
```

Include the docs-repo deletion in the same commit below.

Update cross-references in the copied files to reflect the published
filenames (same rewrite as `/publish` Step 8):

```bash
tmp=$(mktemp)
sed 's/03-api-findings\.md/api-findings-{workspace-id}.md/g' "{target_directory}/ui-design-{workspace-id}.md" > "$tmp" && mv "$tmp" "{target_directory}/ui-design-{workspace-id}.md"
```

If `api-findings-{workspace-id}.md` was copied:

```bash
tmp=$(mktemp)
sed 's/02-ui-design\.md/ui-design-{workspace-id}.md/g' "{target_directory}/api-findings-{workspace-id}.md" > "$tmp" && mv "$tmp" "{target_directory}/api-findings-{workspace-id}.md"
```

Render provenance footer on the docs-repo copies before staging.

**Index isolation.** Before staging, reset the index to prevent
unrelated pre-staged files from leaking into this commit:

```bash
git -C "{docs_repo_path}" reset HEAD --quiet
git -C "{docs_repo_path}" add "{target_directory}/ui-design-{workspace-id}.md"
# If api-findings-{workspace-id}.md was updated during this phase:
git -C "{docs_repo_path}" add "{target_directory}/api-findings-{workspace-id}.md"
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

#### 6c: Write preliminary log entry and post the response

**Initialize the response log before the API call.** Before attempting
the GitHub API post, ensure `05-review-responses.md` exists and is
ready for this comment's entry. This guarantees that if the process
crashes during or immediately after the API call, the entry exists and
the next `/respond` invocation can detect the ambiguous state.

If the file does not exist yet, create it with the round header:

```markdown
# Review Responses — {workspace-id}

## Round {N} — {date}
```

If the file exists but does not contain a `## Round {N}` header for the
current round, append the round header.

**Duplicate-entry guard.** Before appending a new entry, search
`05-review-responses.md` for an existing entry whose `**Comment ID:**`
matches the current `{comment_id}`.

- If found with a successful `Post result` and a non-`"unknown"`
  `API Response ID`, this response was already posted — skip the
  entire comment (do not append, do not post) to avoid duplicates.
- If found with `Post result: pending` or `API Response ID: unknown`,
  reuse the existing entry — do not append a duplicate. Perform a
  **GitHub lookup** before re-posting to determine whether the prior
  attempt actually succeeded. Search the correct endpoint for the
  response type: for **inline review replies**, query the PR's review
  comments (`pulls/{pr_number}/comments`) and filter to comments
  whose `in_reply_to_id` chain traces back to the same root comment
  as the selected thread — do not match against unrelated threads;
  for **top-level responses** (posted with `gh pr comment`), query
  issue comments (`issues/{pr_number}/comments`) and match by a
  unique correlation marker embedded in the comment body (e.g.,
  `<!-- respond-correlation: {workspace-id}/{comment_id} -->`) rather
  than by body text alone — an identical reply on a different thread
  must not be treated as this response. If a matching reply is found,
  update the existing entry with the discovered `API Response ID` and
  mark it successful — skip re-posting.
  If no matching reply is found, proceed with posting and update the
  existing entry in Step 6d.
- If found with a failed `Post result`, reuse the existing entry —
  do not append a duplicate. Before re-posting, perform the same
  GitHub lookup as the `pending`/`unknown` path above: search issue
  comments for top-level responses and review comments for inline
  replies. If the response was already posted, mark it `success` and
  skip. Otherwise proceed with posting and update the existing entry
  in Step 6d.
- If no matching entry exists, append a new preliminary entry with
  `Post result: pending` and `API Response ID: unknown`:

```markdown
### Comment #{N}: {reviewer} on {section}

**Comment ID:** {comment_id} (originally selected comment)
**Root Comment ID:** {root_comment_id} (used for posting; same as Comment ID if not a nested reply)
**Timestamp:** {ISO timestamp}
**Comment:** {text}
**Category:** {category}
**Response:** {what will be posted}
**Document change:** {what was changed, or "None"}
**Post result:** pending
**API Response ID:** unknown
```

For inline replies, use the resolved `root_comment_id`:

```bash
gh api "repos/{upstream_repo}/pulls/{pr_number}/comments/${root_comment_id}/replies" \
  -F "body=@.artifacts/ui-design/{workspace-id}/pr-response-{N}.md"
```

For general (non-inline) comments, append a hidden correlation marker
to the response file before posting so the retry lookup can
distinguish this response from identical text posted elsewhere:

```bash
echo '<!-- respond-correlation: {workspace-id}/{comment_id} -->' \
  >> .artifacts/ui-design/{workspace-id}/pr-response-{N}.md
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

Update the entry identified in Step 6c (whether a newly appended
preliminary entry or an existing entry being retried) in
`.artifacts/ui-design/{workspace-id}/05-review-responses.md` with the
final post result and API response ID. Do this immediately after
confirmed posting, before moving to the next comment. This ensures
that if the run is interrupted, already-posted responses are recorded
with their final status and will not be reposted on the next `/respond`
invocation.

Replace the `**Post result:** pending` line with the actual outcome
(`success` or `failed — {error}`), and replace
`**API Response ID:** unknown` with the ID returned by the GitHub API
(or `"N/A"` on failure). Do not append a new entry — update the
identified entry in place.

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
