# PR Review Workflow Guidelines

## Shared Review Protocol

Read and follow `../_shared/review-protocol.md` for evaluation criteria,
finding format, severity definitions, and core review principles. Those
shared standards apply to this workflow. The principles and rules below are
specific to reviewing a remote PR/MR.

## Terminology

- **"PR"** means "PR or MR" throughout this workflow's files — GitHub pull
  requests and GitLab merge requests are treated identically except at the
  handful of host-API touchpoints called out in `skills/start.md` and
  `skills/publish.md`.
- **"Approve" means approve-to-post, not approve-the-PR.** Everywhere this
  workflow says the user "approved" or "approves," it means the local user
  signed off in chat on the draft review's content so `/publish` may post
  it. That is a decision made entirely outside the reviewed host — it is
  never a GitHub/GitLab PR/MR approval, and this workflow never performs one
  (see the hard limits below).

## Principles

- **The review is external.** This workflow never modifies the reviewed
  repository's code, ever — not even with approval. It reads a worktree and
  posts comments; nothing else. This is stronger than `code-review`'s "no
  changes without approval," since there is no implementation phase here at
  all.
- **Context before critique.** Every review presentation leads with the PR's
  context and key design decisions (title, author, linked issues, commit
  narrative, existing discussion) before any findings. A reviewer who
  doesn't understand what a PR is trying to do isn't ready to critique it.
- **The worktree is ephemeral, but not per-round.** The PR/MR is always
  checked out into a git worktree, never reviewed by mutating the user's own
  checkout. The worktree persists across `/start` -> `/revise` -> `/publish`
  -> `/continue` rounds so later rounds can refresh it in place; it is
  removed only by `/clean`.
- **Comments propose, they never command.** Posted comment tone is
  suggestive ("Should we...", "What if...") by default, and pluggable per
  `templates/comment-style.md`. Never phrase a posted comment as an
  instruction ("Do X", "Please fix Y").
- **Nothing is posted without local sign-off.** The exact rendered content
  of every comment — link, snippet, suggestion block, and comment text — is
  shown to the local user before `/publish` runs. Silence is not consent;
  wait for an explicit go-ahead.
- **The human decides.** The reviewer proposes findings; the local user
  decides which become posted comments, same as `code-review`'s "the
  reviewer proposes, the user approves" principle, adapted since there is no
  implementor role here.

## Hard Limits

- **No code changes to the reviewed repository, ever.** Not in the
  worktree, not upstream. This workflow only reads code and drafts/posts
  comments.
- **No auto-advancing between phases.** Always wait for the user between
  `/start`, `/revise`, and `/publish`.
- **No posting without explicit local approval-to-post** of the exact
  content that will be sent to the host.
- **No mutating host operations beyond the approved review post.** No
  merge, close, edit of PR/MR metadata, or formal approve/request-changes
  action. On GitHub, every posted review uses `event: COMMENT` — never
  `APPROVE` or `REQUEST_CHANGES`. On GitLab, never call the approve/unapprove
  endpoint.
- **No fabricated findings.** Every finding must cite a real file and a real
  line inside the PR/MR diff, with a working permalink and an accurate
  snippet read from the worktree.
- **No fabricated suggestions.** A `suggestion` code block is only included
  when the fix is a concrete, mechanical replacement of the flagged lines.
  Conceptual or design findings get an explanatory comment with no
  suggestion block — never invent a diff just to fill the field.
- **The worktree is removed only by `/clean`.** `/publish` and `/continue`
  read from and refresh the worktree but never delete it.
- **No mutating git operations against the reviewed repo's remote.** Only
  local `git fetch`/`worktree`/`diff`/`merge-base` operations against a
  scratch clone or a local ref — never `git push` to the reviewed repo.

## Safety

- Verify the matching host CLI is authenticated (`gh auth status` /
  `glab auth status`) before any phase that calls a host API (`/start`,
  `/publish`, `/continue`). `/clean` only reads local metadata and removes
  local files -- it never calls a host API, so it must not be blocked by
  missing or expired host credentials.
- Read the target project's own `AGENTS.md`, `CLAUDE.md`, and contribution
  guidelines (from the worktree) before reviewing. The reviewed project's
  conventions override general preferences.
- Verify every finding references a real file and a real, currently-diffed
  line before it is drafted as a comment. If a finding cites a location that
  doesn't exist in the diff, discard it.
- Before posting, confirm every comment still anchors to a line inside the
  current diff — the PR/MR may have changed since the draft was written.
- If the host rejects part of a post, report exactly what failed and ask the
  user how to proceed. Never silently drop or silently retry with altered
  content.

## Quality

- Evaluation criteria are defined in `../_shared/review-protocol.md`; the
  reviewer must cover all listed categories.
- Every kept finding must have a permalink, a quoted snippet, and (when the
  fix is mechanical) a suggestion block — findings without a citable
  location are discarded before the user ever sees them.
- Tone and structure follow `templates/comment-style.md` (or the project's
  override, if one exists) for every posted comment, with no exceptions.
- The review summary posted to the host is always the literal string
  `See comments below` — never restate finding counts or severities there.

## Escalation

Stop and request human guidance when:

- The PR/MR is too large to review meaningfully in one pass (recommend
  splitting the review into focus areas).
- The host CLI is not authenticated, or the PR/MR cannot be fetched
  (private repo without access, deleted PR/MR, etc.).
- `git worktree add` fails for a reason other than "already checked out"
  (see `skills/start.md`).
- The host rejects one or more comments when posting (a line moved outside
  the diff, permissions issue, etc.).
- The project has no discoverable conventions and the reviewer cannot
  calibrate.

## Working With the Reviewed Project

This workflow reviews a project it does not own. Respect it:

- Read and follow the reviewed project's own `AGENTS.md`/`CLAUDE.md` (from
  the worktree) for conventions and review focus areas.
- Honor a project-level comment-style override
  (`.pr-review/templates/comment-style.md` in the reviewed repo) if one
  exists — see `templates/comment-style.md` for the resolution order.
- Do not impose the local user's personal style preferences over the
  reviewed project's own documented conventions.
