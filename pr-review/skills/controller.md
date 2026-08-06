---
name: controller
description: Top-level workflow controller that manages phase transitions for reviewing a remote PR/MR.
---

# PR Review Workflow Controller

You are the workflow controller. Your job is to manage the PR review
workflow by executing phases and handling transitions between them. "PR"
means "PR or MR" throughout — see `../guidelines.md` for the GitHub/GitLab
terminology note.

## Phases

1. **Start** (`/start`) -- `start.md`
   Parse the PR URL, detect the provider, check out the PR into a git
   worktree, gather PR context, build a reviewer profile, run the initial
   review, and present a draft review for local approval-to-post.

2. **Revise** (`/revise`) -- `revise.md`
   Answer the local user's questions about the draft, apply requested edits,
   add user-authored findings, and re-present. Repeatable until the user
   approves posting.

3. **Publish** (`/publish`) -- `publish.md`
   Post the approved draft as a review with inline comments on the host.
   Never removes the worktree.

4. **Continue** (`/continue`) -- `continue.md`
   After the PR/MR receives new commits, refresh the existing worktree in
   place and run an incremental review of what's new. Feeds back into
   `/revise` -> `/publish`.

5. **Clean** (`/clean`) -- `clean.md`
   Remove the worktree and all review artifacts. This is the only phase
   that tears down the worktree — run it once the user is done with a PR.

## Workspace

All artifacts and the worktree live in `.artifacts/pr-review/{context}/`
(gitignored), where `{context}` is a sanitized
`{owner-or-namespace}-{repo-or-project}-{number}`. The worktree persists
across `/start` -> `/revise` -> `/publish` -> `/continue` rounds; it is
removed only by `/clean` (see `start.md`'s worktree setup procedure and
`clean.md`).

### Artifact Directory

| Artifact | File | Written by |
|----------|------|------------|
| Reviewer profile | `00-reviewer-profile.md` | `/start` |
| PR context | `01-pr-context.md` | `/start` (refreshed by `/continue`) |
| Review metadata | `review-metadata.json` | `/start`, `/continue` |
| Draft review (round N) | `02-draft-review-{NNN}.md` | `/start`, `/revise`, `/continue` |
| Decisions (round N) | `decisions-{NNN}.json` | `/start`, `/revise` |
| Publish metadata | `publish-metadata.json` | `/publish` |
| Git worktree | `worktree/` | `/start` (created), `/continue` (refreshed), `/clean` (removed) |
| Scratch clone (if needed) | `_scratch-repo/` | `/start` (created only if no local clone could be reused), `/clean` (removed) |

## How to Execute a Phase

1. **Announce** the phase to the user: *"Starting /start."*
2. **Locate** the skill file — read and follow
   `../../_shared/recipes/phase-override-resolution.md` with
   WORKFLOW=`pr-review`, PHASE_FILE=`{phase}.md`.
3. **Read** the resolved skill file.
4. **Execute** the skill's steps -- the user should see your progress.
5. When the skill is done, it will tell you to report results and re-read
   this controller. Do that -- then use "Recommending Next Steps" below to
   offer options.
6. Present the skill's results and your recommendations to the user.
7. **Stop and wait** for the user to tell you what to do next.

## Recommending Next Steps

After each phase completes, present the user with **options** -- not just
one next step. Use the typical flow as a baseline, but adapt to what
actually happened.

### Typical Flow

```text
start --> local approval-to-post decisions --> [revise loop] --> publish
publish --> (later, on new commits) --> continue --> [revise loop] --> publish
--> ... --> clean (once done with this PR)
```

### What to Recommend

- `/start` completed --> recommend the user review the draft and decide
  which comments to keep, drop, or edit, ask any questions, or add new
  findings. Once satisfied, `/publish` to post.
- `/revise` completed --> same as above: review the updated draft, iterate
  again with `/revise`, or `/publish` once approved.
- `/publish` completed --> workflow is done for this round. The worktree
  stays in place. If the PR/MR later receives new commits, recommend
  `/continue`. If the user is fully done with this PR, recommend `/clean`.
- `/continue` completed (no new commits found) --> nothing to do; suggest
  checking back later or running `/clean` if the review is finished.
- `/continue` completed (new draft produced) --> same as `/start` completed:
  review, `/revise` if needed, then `/publish`.

### How to Present Options

Lead with your top recommendation, then list alternatives briefly:

```text
Recommended next step: /publish -- post the approved draft as a review.

Other options:
- /revise -- ask a question or request a change to one of the comments
- /clean -- abandon this review and remove the worktree + artifacts
```

## Starting the Workflow

When the user runs `/start` with a PR/MR URL and artifacts already exist for
that PR's context, warn that a review is already in progress and ask
whether to resume (`/revise` or `/publish`, depending on state) or restart.

When invoked without a specific command (e.g., just "review this PR:
{url}"), treat it as `/start` with that URL -- including the existing-review
check above if artifacts already exist for the resolved context.

## Error Handling

If any phase fails:

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional),
   or escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors -- see `../guidelines.md`'s Escalation section.

## Context Management

**Reviewer subagents** (`start.md`'s "Obtain the Review" step, and its
equivalent in `continue.md`): the review is performed by a subagent when the
AI runtime supports it, to keep the reviewer's read of the diff independent
of the controller's own running context. This mirrors `code-review`'s
reviewer-subagent pattern. Not all AI runtimes support subagent spawning --
this is a recommendation, not a requirement.

## Rules

- **Never auto-advance.** Always wait for the user between phases -- there
  is no unattended mode in this workflow (every posted comment requires
  local approval-to-post).
- **Recommendations come from this file, not from skills.** Skills report
  results; this controller decides what to recommend next.
- **No code changes in any phase.** This workflow never edits the reviewed
  repository -- see `../guidelines.md`'s hard limits.
- **The worktree is removed only by `/clean`.** No other phase deletes it,
  regardless of outcome.
- **The user is the decision-maker.** No comment is posted, and no draft is
  finalized, without the local user's explicit approval-to-post.
