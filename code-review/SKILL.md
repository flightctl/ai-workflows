---
name: code-review
version: 0.1.1
description: >-
  AI-driven code review workflow. Reviews uncommitted local changes or GitHub
  Pull Requests. Local mode uses a discoverable reviewer profile with
  iterative human decisions; PR mode performs deep cross-file analysis and
  optionally posts findings as GitHub review comments. Supports --unattended
  for local review automation.
  Use when reviewing code before commit, reviewing PRs, or posting review
  comments to GitHub.
  Activated by commands: /start, /continue, /pr, /pr-continue, /clean.
---
# Code Review Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/start`, `/continue`, `/pr`,
   `/pr-continue`), read `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller and
   follow its dispatch logic.

If a step fails or produces unexpected output, stop and report the error to
the user. Do not advance to the next phase. Offer to retry or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
