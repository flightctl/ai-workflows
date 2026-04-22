---
name: code-review
description: >-
  AI-driven code review workflow that reviews uncommitted changes using a
  discoverable reviewer profile, presents findings for human decision, and
  iterates until approved. Supports --unattended for automated iteration.
  Use when reviewing code before commit or PR.
  Activated by commands: /start, /continue, /clean.
---
# Code Review Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/start`, `/continue`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller and
   follow its dispatch logic.

If a step fails or produces unexpected output, stop and report the error to
the user. Do not advance to the next phase. Offer to retry or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
