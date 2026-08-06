---
name: pr-review
version: 0.1.0
description: >-
  AI-driven review of a remote pull request or merge request, given its URL
  (GitHub or GitLab, auto-detected). Checks out the PR/MR into a git worktree,
  explains PR context and key decisions, evaluates changes using the shared
  code-review protocol, and drafts inline review comments (with code links,
  snippets, and suggested-change blocks) in a pluggable, suggestive tone.
  Always presents the draft for local approval before posting a review, never
  changes the reviewed code, supports revision based on questions or new
  findings, and can resume after the PR/MR receives new commits. Use when
  asked to review, comment on, or give feedback on a GitHub PR or GitLab MR
  URL. Activated by commands: /start, /revise, /publish, /continue, /clean.
---
# PR Review Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/start`, `/revise`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller and
   follow its dispatch logic.

If a step fails or produces unexpected output, stop and report the error to
the user. Do not advance to the next phase. Offer to retry or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
