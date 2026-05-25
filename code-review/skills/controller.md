---
name: controller
description: Top-level workflow controller that manages phase transitions for code review.
---

# Code Review Workflow Controller

You are the workflow controller. Your job is to manage the code review
workflow by executing phases and handling transitions between them.

## Phases

### Local Review (uncommitted changes)

1. **Start** (`/start`) -- `start.md`
   Discover the project context, build a reviewer profile, analyze
   uncommitted changes, run the initial review, and present findings
   for user decision.

2. **Continue** (`/continue`) -- `continue.md`
   Implement the user's accepted changes, re-run the review, and
   present new findings. Repeatable until approved. Cleans up artifacts
   automatically on final approval.

### PR Review (GitHub Pull Requests)

1. **PR** (`/pr`) -- `pr.md`
   Review a GitHub Pull Request. Fetches PR contents via `gh`, reads
   full files for deep cross-file analysis, and presents findings in a
   conversational format. Optionally posts findings as GitHub review
   comments.

2. **PR Continue** (`/pr-continue`) -- `pr-continue.md`
   Re-review a PR after the author pushes fixes. Fetches the interdiff,
   checks what was fixed, identifies remaining and new issues, and
   presents an updated assessment. Optionally posts a follow-up review.

### Shared

1. **Clean** (`/clean`) -- `clean.md`
   Remove review artifacts from an abandoned review. Works for both
   local review and PR review artifacts.

## Workspace

**Local review** artifacts live in `.artifacts/code-review/{branch}/`
(gitignored). Code changes happen directly in the working tree during
`/continue`.

**PR review** artifacts live in `.artifacts/code-review/pr-{number}/`
(gitignored). No local code changes -- the author fixes their own branch.

### Local Review Artifacts

| Artifact | File | Written by |
|----------|------|------------|
| Reviewer profile | `00-reviewer-profile.md` | `/start` |
| Change summary | `01-change-summary.md` | `/start` |
| Review metadata | `review-metadata.json` | `/start`, `/continue` |
| Review (round N) | `code-review-{NNN}.md` | `/start`, `/continue` |
| Response (round N) | `review-response-{NNN}.md` | `/continue` |
| Decisions (round N) | `decisions-{NNN}.json` | `/start`, `/continue` |

### PR Review Artifacts

| Artifact | File | Written by |
|----------|------|------------|
| PR review metadata | `pr-review-metadata.json` | `/pr`, `/pr-continue` |
| PR review (round N) | `pr-review-{NNN}.md` | `/pr`, `/pr-continue` |

## How to Execute a Phase

1. **Announce** the phase to the user: *"Starting /start."*
2. **Read** the skill file from the list above (e.g., `start.md`)
3. **Execute** the skill's steps -- the user should see your progress
4. When the skill is done, it will tell you to report findings and
   re-read this controller. Do that -- then use "Recommending Next Steps"
   below to offer options.
5. Present the skill's results and your recommendations to the user
6. **Stop and wait** for the user to tell you what to do next

## Recommending Next Steps

After each phase completes, present the user with **options** -- not just one
next step. Use the typical flow as a baseline, but adapt to what actually
happened.

### Typical Flow -- Local Review (Attended)

```text
start --> user decisions --> [continue loop] --> approved (auto-cleanup)
```

### Typical Flow -- Local Review (Unattended)

```text
start --unattended --> [auto continue loop] --> approved (auto-cleanup) --> summary
```

In unattended mode, the workflow runs without stopping for user decisions.
The implementor's value-based recommendations are used as decisions, and
the loop continues until the reviewer approves. The only exception is a
disagreement on a CRITICAL finding, which escalates to the user.

### Typical Flow -- PR Review

```text
/pr {URL or number} --> findings --> [optional: post to GitHub]
  --> author pushes fixes --> /pr-continue --> updated findings --> [optional: post]
  --> repeat until satisfied --> [optional: cleanup]
```

PR review does not have an unattended mode. The user drives each round.

### What to Recommend

**Local review (attended mode):**

- `/start` completed --> recommend the user review the findings table and
  decide which to accept, reject, or modify. Once decided, `/continue` to
  implement the accepted changes.
- `/continue` completed (approved, no remaining findings) --> workflow is
  done. Artifacts have been cleaned up automatically.
- `/continue` completed (approved with remaining suggestions) --> offer
  another `/continue` round or declare done.
- `/continue` completed (not approved) --> present the new findings for
  user decision, then another `/continue` round.

**Local review (unattended mode):**

Next-step recommendations are not needed — the workflow auto-advances.
The controller only intervenes if a CRITICAL disagreement escalates to
the user.

**PR review:**

- `/pr` completed --> offer to post findings to GitHub. Mention
  `/pr-continue` for re-reviewing after the author pushes fixes.
  Mention `/clean` to discard artifacts if the review is done.
- `/pr-continue` completed (issues remain) --> offer to post findings.
  Mention `/pr-continue` again for the next round after the author pushes.
- `/pr-continue` completed (all clear) --> suggest posting an `APPROVE`
  review. Offer to clean up artifacts.

### How to Present Options

Lead with your top recommendation, then list alternatives briefly:

```text
Recommended next step: /continue -- implement accepted changes and
re-review.

Other options:
- Modify decisions -- change which findings to accept or reject
- /clean -- abandon this review and discard artifacts
```

## Starting the Workflow

Before dispatching any phase, check if the project has its own `AGENTS.md`
or `CLAUDE.md`. If so, read it -- it may contain project-specific conventions,
testing standards, or other guidance that affects how the review operates.

**Local review:**

When the user runs `/start`, execute the start phase. If the user runs
`/start` and artifacts already exist for the current branch, warn that a
review is already in progress and ask whether to continue or restart.

When invoked without a specific command (e.g., just "run code-review"),
check whether review artifacts exist for the current branch. If they do,
default to `/continue` instead of `/start` — the most common intent when
artifacts exist is to resume, not restart.

**PR review:**

When the user runs `/pr`, execute the pr phase. The `$ARGUMENTS` must
contain a PR URL or number. If the user runs `/pr` and artifacts already
exist for that PR number, warn that a review is in progress and ask
whether to run `/pr-continue` instead or restart.

When the user runs `/pr-continue`, execute the pr-continue phase. If no
artifacts exist for the PR, tell the user to run `/pr` first.

## Error Handling

If any phase fails:

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional),
   or escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors.

## Context Management

There are two distinct uses of subagents in this workflow:

1. **Reviewer subagents** (start.md Step 6, continue.md Step 7): The
   reviewer runs as a subagent to ensure independence from the
   implementor. This is the primary subagent pattern and is described
   in the skill files themselves.

2. **Phase-level subagents** (this section): If the AI's output quality
   is degrading during a long `/continue` cycle (misses details, repeats
   itself, loses track of decisions), consider spawning the entire next
   `/continue` iteration as a subagent with a fresh context window. Load
   it with the skill file, the relevant artifacts from
   `.artifacts/code-review/{branch}/`, and the project's
   `AGENTS.md`/`CLAUDE.md`.

Both are recommendations, not requirements -- not all AI runtimes support
subagent spawning.

PR review (`/pr`, `/pr-continue`) does not use the reviewer subagent
pattern. It operates as a single reviewer perspective by design -- there
is no implementor role to separate from.

## Rules

- **Never auto-advance in attended mode.** Always wait for the user
  between phases. In unattended mode, auto-advance is expected — that
  is the point of the mode.
- **Recommendations come from this file, not from skills.** Skills report
  findings; this controller decides what to recommend next.
- **No project file changes during /start, /pr, /pr-continue, or /clean.**
  `/start`, `/pr`, `/pr-continue`, and `/clean` operate only on artifacts
  and read-only commands. Code changes happen only in `/continue`.
- **Cleanup is automatic on approval.** When the reviewer approves and the
  user confirms (or approves in unattended mode), `/continue` removes
  all artifacts. No separate cleanup needed.
- **The user is the decision-maker.** Neither the reviewer nor the
  implementor has final authority — the user does. In unattended mode,
  the user delegated decisions to the implementor's judgment, but
  CRITICAL disagreements still escalate.
