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
`host` (GitLab only), `owner_or_namespace`, `repo_or_project`, `number`,
`head_sha`, `merge_base_sha`, and the worktree location. For GitLab, derive
`{namespace}` and `{project}` from `owner_or_namespace`/`repo_or_project`,
and `{project_path}` the same way `start.md` Step 1 does (every `/` in
`{namespace}/{project}` replaced by `%2F`).

If `review-metadata.json` is missing, stop and tell the user there's no
review in progress for this context -- run `/start` first. The only valid
pre-publish `state` is `awaiting_decision`; any other value is explicit:
- `published`: this round was already posted. Report that instead of
  posting again (see the idempotency note in Step 5) -- don't silently
  re-post.
- Anything else (or the field missing): stop and tell the user there's no
  approved draft to publish yet -- run `/start` or `/revise` first.

**Determine what's actually approved -- the draft alone is not enough.**
Read the decisions file matching the current `iteration`
(`decisions-{NNN}.json`). `02-draft-review-{NNN}.md` documents every
candidate for transparency, including ones assessed "Disagree" and never
selected to post -- only comments whose matching entry in
`decisions-{NNN}.json` has `"decision": "keep"` may be posted. If a draft
comment has no matching decision entry, treat it as not approved: stop and
ask the user to confirm keep/drop for it rather than guessing either way.

### Step 2: Re-Verify Line Anchors

The PR/MR may have changed since the draft was written (a `/revise` round
can span time). `--name-status` only proves a file is still touched, not
that a specific line is still inside a hunk -- for each kept comment's
`{path}`, pull the actual hunk ranges instead:

```bash
git -C {worktree} diff --unified=0 {merge-base-sha} HEAD -- {path}
```

Parse the `@@ -a,b +c,d @@` hunk headers and confirm the comment's line
(and, for multi-line comments, its full `start_line`-`line` range) falls
within one of the `+c,d` ranges on the new side. If a comment's file no
longer appears in the diff at all, or its line falls outside every hunk,
do not post it silently and do not silently drop it either -- tell the
user which comment(s) are affected and ask whether to drop, relocate, or
abort.

### Step 3: Build the Payload

Comment bodies are rendered Markdown and will routinely contain quotes,
backslashes, or literal newlines (code snippets, suggestion blocks). Never
build the JSON by string-interpolating that text between quotes -- a single
`"`, `\`, or newline produces invalid JSON or a silently corrupted body.
Build every payload with `jq`, which serializes each string correctly:
write the exact comment text (as it will be posted) to its own plain-text
temp file, then pass it in with `jq`'s `--rawfile` so `jq` handles escaping
-- never `--arg` from a shell-interpolated variable holding the same text.
Delete all temp files (bodies, per-comment JSON, assembled payload) after
posting.

**GitHub** -- one batched review object. Build each comment as its own
JSON object from its body file, collect them into an array, then assemble
the final payload:

```bash
# per kept comment, {n} = its position in the kept list
jq -n --rawfile body .artifacts/pr-review/{context}/tmp-body-{n}.txt \
     --arg path "{path}" --argjson line {end-line} \
     '{path: $path, line: $line, side: "RIGHT", body: $body}' \
     > .artifacts/pr-review/{context}/tmp-comment-{n}.json
# multi-line comment: add --argjson start_line {start-line} and merge in
# {start_line: $start_line, start_side: "RIGHT"}

jq -s '.' .artifacts/pr-review/{context}/tmp-comment-*.json \
     > .artifacts/pr-review/{context}/tmp-comments-array.json

jq -n --arg commit_id "{head-sha}" \
     --slurpfile comments .artifacts/pr-review/{context}/tmp-comments-array.json \
     '{commit_id: $commit_id, event: "COMMENT", body: "See comments below", comments: $comments[0]}' \
     > .artifacts/pr-review/{context}/tmp-review-payload.json
```

Illustrative shape of the assembled payload (the commands above produce
this -- don't hand-write it):

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

Post it:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews --method POST --input .artifacts/pr-review/{context}/tmp-review-payload.json
```

**GitLab** -- no batched review object exists. First fetch the diff refs
needed to anchor each discussion (base/start/head SHAs from the MR's own
diff, not just the worktree's). `{project_path}` is the fully URL-encoded
`namespace/project` path from Step 1, which GitLab's REST API accepts
directly in place of the numeric ID; every call must also target `{host}`
explicitly for self-hosted instances:

```bash
glab api --hostname {host} "projects/{project_path}/merge_requests/{number}" | jq '.diff_refs'
```

Before posting, check whether
`.artifacts/pr-review/{context}/publish-metadata.json` already exists **for
this `iteration`** (a prior `/publish` run was interrupted partway through
this exact round). If so, skip any kept comment whose number already
appears in its `posted_comments` -- only post the ones still missing. This
is what keeps a retry from double-posting discussions that already
succeeded.

Then, for each remaining kept comment, build the discussion payload the
same `--rawfile` way as the GitHub comments above, then POST it:

```bash
jq -n --rawfile body .artifacts/pr-review/{context}/tmp-body-{n}.txt \
     --arg base_sha "{diff_refs.base_sha}" --arg start_sha "{diff_refs.start_sha}" \
     --arg head_sha "{diff_refs.head_sha}" --arg new_path "{path}" --argjson new_line {line} \
     '{body: $body, position: {position_type: "text", base_sha: $base_sha, start_sha: $start_sha, head_sha: $head_sha, new_path: $new_path, new_line: $new_line}}' \
     > .artifacts/pr-review/{context}/tmp-discussion-{n}.json

glab api --hostname {host} "projects/{project_path}/merge_requests/{number}/discussions" --method POST --input .artifacts/pr-review/{context}/tmp-discussion-{n}.json
```

Illustrative shape of the assembled payload (for reference only):

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

After each successful POST, immediately write (don't wait for Step 5) the
comment number and returned discussion ID into
`.artifacts/pr-review/{context}/publish-metadata.json`'s `posted_comments`
array, with `iteration` set to the current round. Persisting this on every
success, not just at the end, is what makes a retry after a partial
failure safe.

Then post one separate top-level note carrying the fixed summary (only
after every discussion above succeeded -- see Step 5's idempotency note):

```bash
glab mr note {number} --repo "https://{host}/{namespace}/{project}" --message "See comments below"
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

### Step 5: Finalize Publish Metadata

For GitHub, the single batched review call from Step 3 either creates the
whole review or fails creating nothing -- write
`.artifacts/pr-review/{context}/publish-metadata.json` fresh on success:

```json
{
  "iteration": {N},
  "posted_at": "{ISO 8601 timestamp}",
  "head_sha_reviewed": "{head-sha}",
  "comments_posted": {N},
  "review_id": "{GitHub review id}",
  "review_url": "{URL to view the posted review}"
}
```

For GitLab, `publish-metadata.json` was already being written incrementally
in Step 3 (`posted_comments`); once every kept comment has a discussion ID
and the summary note posted successfully, finalize it:

```json
{
  "iteration": {N},
  "posted_at": "{ISO 8601 timestamp}",
  "head_sha_reviewed": "{head-sha}",
  "comments_posted": {N},
  "posted_comments": [{"comment": 1, "discussion_id": "{id}"}],
  "review_url": "{URL to view the posted discussions}"
}
```

Only set `review-metadata.json`'s `state` to `published` once this file is
complete for every kept comment (and, for GitLab, the summary note has
posted) -- not on a partial post. If the user explicitly accepted a
partial post (Step 4), leave `state` as `awaiting_decision` so a later
`/publish` retry is still recognized as having unfinished work, and note in
`publish-metadata.json` which comments were intentionally left unposted.

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
