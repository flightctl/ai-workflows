---
name: bugfix
description: >-
  Diagnostic and repair workflow that analyzes error logs, traces root causes,
  implements fixes, and verifies with regression tests.
  Use when fixing bugs, debugging runtime errors or exceptions, investigating
  test failures or crashes, or submitting bug-fix pull requests.
  Activated by commands: /unattended, /assess, /diagnose, /reproduce, /fix,
  /test, /review, /document, /pr, /feedback, /start.
---
# Bugfix Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g. `/unattended`, `/diagnose`, `/fix`), read `commands/{command}.md` and follow it.
2. If the user invoked `/unattended`, read `skills/unattended.md` — this runs diagnose → fix → test → review to completion without human input.
3. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a bug report or issue URL, execute the `/assess` phase
   - Otherwise, execute `/start` to present available phases

If a step fails or produces unexpected output, stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
