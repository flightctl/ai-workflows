---
name: publish
description: Post the approved draft as a review with inline comments on the host. Never removes the worktree.
---

# Publish PR Review Skill

You are posting an already-approved draft review to the host. Your job is
to turn the approved draft into the host's native review/comment objects,
post them, and record what was posted -- nothing more.

## Your Role

Translate `02-draft-review-{NNN}.md`'s kept comments into the provider's
posting mechanics (see `../guidelines.md`'s terminology note and the table
below), post them, and report the result. The worktree is left exactly as
it is.

## Critical Rules

- **Precondition: local approval-to-post.** Only run this after the user
  has explicitly approved the current draft's exact content (from `/start`
  or `/revise`) -- never a host-level PR/MR approval. If there is no clear
  approval in the conversation, stop and ask before posting anything.
- **Post only what's in the approved draft.** The posted comment bodies are
  exactly the "Comment (as it will be posted)" text from the draft --
  never the internal severity/category/assessment notes.
- **Review summary is always fixed.** `See comments below`, verbatim,
  regardless of comment count or severity.
- **Never a formal approve/request-changes action.** GitHub reviews always
  use `event: COMMENT`. GitLab: never call the approve/unapprove endpoint.
- **No silent partial-post.** If the host rejects any comment, report
  exactly which ones and why, and ask the user how to proceed -- don't
  invent a fallback (e.g., posting as a generic top-level comment instead)
  unless the user asks for that.
- **The worktree is not touched here.** Do not remove it, do not modify it
  beyond what Step 2 needs to re-verify line anchors.

## Process

### Step 1: Read Context

Read `.artifacts/pr-review/{context}/review-metadata.json` for `provider`,
`owner_or_namespace`, `repo_or_project`, `number`, `head_sha`,
`merge_base_sha`, and the worktree location, plus the latest draft
(`02-draft-review-{NNN}.md`, per the current `iteration`) for the kept
comments to post. For GitLab, derive `{namespace}` and `{project}` from
`owner_or_namespace`/`repo_or_project`.

If `review-metadata.json` is missing, or `state` isn't `awaiting_decision`
or a later approved state, stop and tell the user there's no approved draft
to publish yet -- run `/start` or `/revise` first.

### Step 2: Re-Verify Line Anchors

The PR/MR may have changed since the draft was written (a `/revise` round
can span time). Refresh what's needed and re-check that every kept comment
still anchors to a line inside the current diff:

```bash
git -C {worktree} diff {merge-base-sha} HEAD --name-status
```

If a comment's file or line no longer exists in the diff, do not post it
silently and do not silently drop it either -- tell the user which
comment(s) are affected and ask whether to drop, relocate, or abort.

### Step 3: Build the Payload

Write the payload to a temp file first (same pattern as other workflows'
`gh api`/`glab api` calls in this repo) to avoid shell-escaping issues, then
delete the temp file after posting.

**GitHub** -- one batched review object,
`.artifacts/pr-review/{context}/tmp-review-payload.json`:

```json
{
  "commit_id": "{head-sha}",
  "event": "COMMENT",
  "body": "See comments below",
  "comments": [
    {"path": "{path}", "line": {end-line}, "side": "RIGHT", "body": "{comment text}"}
  ]
}
```

For a multi-line comment, add `"start_line": {start-line}, "start_side": "RIGHT"` alongside `"line"` (the end line).

Post it:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews --method POST --input .artifacts/pr-review/{context}/tmp-review-payload.json
```

**GitLab** -- no batched review object exists. First fetch the diff refs
needed to anchor each discussion (base/start/head SHAs from the MR's own
diff, not just the worktree's). The project ID is the URL-encoded
"namespace/project" path, which GitLab's REST API accepts directly in
place of the numeric ID:

```bash
glab api "projects/{namespace}%2F{project}/merge_requests/{number}" | jq '.diff_refs'
```

Then, for each kept comment, POST one discussion,
`.artifacts/pr-review/{context}/tmp-discussion-{n}.json`:

```json
{
  "body": "{comment text}",
  "position": {
    "position_type": "text",
    "base_sha": "{diff_refs.base_sha}",
    "start_sha": "{diff_refs.start_sha}",
    "head_sha": "{diff_refs.head_sha}",
    "new_path": "{path}",
    "new_line": {line}
  }
}
```

```bash
glab api "projects/{namespace}%2F{project}/merge_requests/{number}/discussions" --method POST --input .artifacts/pr-review/{context}/tmp-discussion-{n}.json
```

Then post one separate top-level note carrying the fixed summary:

```bash
glab mr note {number} --repo {namespace}/{project} --message "See comments below"
```

Only the rendered posted text goes in any `body` field -- no internal
severity/category metadata, in either provider's payload.

### Step 4: Handle Rejections

If the host rejects a comment (e.g., a line fell outside the diff, a
permissions error, a malformed position object), do not retry with altered
content and do not skip it silently. Report:

- Which comment(s) failed
- The host's error message
- Whether any comments were successfully posted before the failure

Then ask the user how to proceed (fix and retry, drop the failed ones and
post the rest, or abort). Do not invent a resolution on their behalf.

### Step 5: Write Publish Metadata

On success (all kept comments posted, or the user explicitly accepted a
partial post), write `.artifacts/pr-review/{context}/publish-metadata.json`:

```json
{
  "posted_at": "{ISO 8601 timestamp}",
  "head_sha_reviewed": "{head-sha}",
  "comments_posted": {N},
  "review_id": "{GitHub review id, if provider = github}",
  "discussion_ids": ["{GitLab discussion id, ...}", "..."],
  "review_url": "{URL to view the posted review/discussions}"
}
```

Update `review-metadata.json`'s `state` to `published`.

Clean up any temp payload files created in Step 3.

### Step 6: Report

Tell the user:

- How many comments were posted, and the review URL
- That the worktree is still in place (not removed) -- `/continue` can
  reuse it later if the PR/MR receives new commits; run `/clean` once
  they're fully done with this PR.

## Output

- Review/discussions posted to the host
- `.artifacts/pr-review/{context}/publish-metadata.json`
- Updated `review-metadata.json`

## When This Phase Is Done

Report the posted review URL and comment count.

Then **re-read the controller** (`controller.md`) for next-step guidance.
