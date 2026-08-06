---
name: continue
description: After the PR/MR receives new commits, refresh the existing worktree in place and draft a review of what's new.
---

# Continue PR Review Skill

You are re-reviewing a PR/MR that already had a review posted, after it
received new commits. Your job is to refresh the worktree in place, figure
out what's actually new, check whether previously posted comments look
addressed, and draft comments only for the net-new material.

## Your Role

Pick up where `/publish` left off: same worktree, same artifact directory,
new commits to look at. Produce a new draft round that feeds back into the
same `/revise` -> `/publish` loop as `/start` did.

## Critical Rules

- **Read-only against the reviewed repository.** Same as `/start` and
  `/revise` -- refreshing the worktree (`fetch` + `reset --hard`) is the
  only "mutation," and it only touches the local disposable worktree, never
  the reviewed repo's actual history.
- **Don't re-propose what's already an open thread.** Only draft comments
  for genuinely new findings; existing threads on the host are already
  visible there.
- **Same validation and style rules as `/start`.** Every new finding still
  needs a real file/line inside the current diff, a permalink, a snippet,
  and (when mechanical) a suggestion block, rendered in the resolved
  comment style.
- **No posting here.** This phase only produces a new draft; `/publish`
  posts it, after another round of local approval.

## Process

### Step 1: Read Prior State

Read `.artifacts/pr-review/{context}/review-metadata.json` and
`publish-metadata.json`. If `publish-metadata.json` doesn't exist, `/publish`
was never run (or was interrupted) -- tell the user and suggest resolving
that first (`/revise` then `/publish`) rather than running `/continue`.

### Step 2: Check for New Commits

Fetch current PR/MR metadata with the provider's command (same as
`start.md` Step 1) to get the current head SHA:

```bash
# github
gh pr view {number} --repo {owner}/{repo} --json headRefName,commits,state

# gitlab
glab mr view {number} --repo {namespace}/{project} -F json
```

Compare the current head SHA to `head_sha_reviewed` from
`publish-metadata.json`. If they match, tell the user there's nothing new
to review and stop here.

### Step 3: Refresh the Worktree

If `.artifacts/pr-review/{context}/worktree` still exists (the normal case,
since only `/clean` removes it), refresh it in place using exactly
`start.md` Step 2's refresh form (fetch the head ref, fast-forward the
local branch, then `reset --hard` the worktree to it).

If the worktree was somehow removed outside of `/clean` (e.g., manually
deleted), fall through to `start.md` Step 2's full setup procedure instead
(check for a reusable local repo or scratch-clone, then create the
worktree fresh) before proceeding.

Recompute the merge base and new head SHA:

```bash
git -C {base-repo} merge-base origin/{base_ref_name} pr-review/{context}
git -C {base-repo} rev-parse pr-review/{context}
```

### Step 4: Determine What's New

Two diffs matter here:

- **Full PR/MR diff** (for context): `git -C {worktree} diff {new-merge-base-sha} HEAD`
- **Incremental diff** (what's actually new since the last review):
  `git -C {worktree} diff {head_sha_reviewed} HEAD`

Also re-check previously posted comments against the current code, using
the provider's listing command (same as `start.md` Step 3):

```bash
# github
gh api repos/{owner}/{repo}/pulls/{number}/comments --paginate

# gitlab (project ID is the URL-encoded "namespace/project" path)
glab api "projects/{namespace}%2F{project}/merge_requests/{number}/discussions" --paginate
```

For each previously posted comment, note whether it looks **addressed**
(the flagged code changed in a way that resolves the concern), **still
open** (the code is unchanged or the concern remains), or has a reply from
the author worth factoring in.

### Step 5: Update PR Context

Refresh `.artifacts/pr-review/{context}/01-pr-context.md`'s commit
narrative and existing-discussion sections to reflect the new commits and
any new discussion, following the same format as `start.md` Step 3.

### Step 6: Obtain the Incremental Review

Follow the same subagent pattern as `start.md` Step 6, scoped to the
**incremental diff**, but give the reviewer `00-reviewer-profile.md`, the
full diff, and `01-pr-context.md` too for context. If a subagent was used
originally (`reviewer_agent_id` in metadata) and the runtime supports
resuming it, do so -- this gives it memory of the previous round's findings
and previously posted comments. Otherwise spawn fresh, loaded with
`00-reviewer-profile.md` and the previous round's `02-draft-review-{NNN}.md`
files so it doesn't re-flag what's already posted, and record the new
`reviewer_agent_id` (see Step 8).

Ask the reviewer to also flag, from the previously-open-comments list in
Step 4, any that the new commits clearly resolved (for the user's
awareness in the presentation -- this workflow doesn't reply to or resolve
threads itself, since that's outside its scope).

Extend every new finding with a permalink, snippet, and suggestion block
exactly as `start.md` Step 6 does, anchored to the new head SHA. Validate
and assess exactly as `start.md` Step 7 does.

### Step 7: Draft the Incremental Review

Resolve the comment style the same way as `start.md` Step 8. Increment the
round number from `review-metadata.json`. Write
`.artifacts/pr-review/{context}/02-draft-review-{NNN}.md` in the same
format as `start.md` Step 8, containing only the net-new candidate
comments -- do not re-include comments from the previous round that are
already posted and open on the host.

### Step 8: Update Metadata

Update `.artifacts/pr-review/{context}/review-metadata.json`: bump
`iteration`, `head_sha`, `merge_base_sha`, `last_updated`, and set `state`
to `awaiting_decision`. If Step 6 spawned a fresh subagent rather than
resuming the original one, overwrite `reviewer_agent_id` with its new ID so
a later `/continue` round can resume it in turn.

### Step 9: Present

Present the same way as `start.md` Step 9, plus a short summary of the
previously-posted-comment status from Step 4 (addressed / still open /
has a reply):

```markdown
## Since the Last Review
- {N} new commit(s) since the last posted review
- Previously posted comments: {N} look addressed, {N} still open, {N} have a reply worth noting
```

Persist decisions to `decisions-{NNN}.json` (matching the incremented
round), same schema as `start.md`/`revise.md`.

If there are no net-new candidate comments after assessment, tell the user
the new commits look fine and no additional comments are proposed --
there's nothing to `/publish` this round.

## Output

- Updated `.artifacts/pr-review/{context}/worktree/` (refreshed in place)
- Updated `01-pr-context.md`
- `.artifacts/pr-review/{context}/02-draft-review-{NNN}.md`
- `.artifacts/pr-review/{context}/decisions-{NNN}.json`
- Updated `review-metadata.json`

## When This Phase Is Done

Present the incremental draft (or "nothing new to propose") and the
previously-posted-comment status to the user.

Then **re-read the controller** (`controller.md`) for next-step guidance.
