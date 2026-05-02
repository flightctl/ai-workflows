---
name: triage
description: >-
  Bulk-triage unresolved Jira bugs with AI-driven recommendations and an
  interactive HTML report. Scan also loads recently resolved bugs for regression
  matching in analyze. Use when triaging a project backlog, prioritizing bug
  fixes, identifying candidates for automated fixing, or reviewing stale issues.
  For one bug in depth (no artifacts), use /assess. Activated by commands:
  /run, /start, /scan, /analyze, /report, and /assess.
---
# Triage Workflow Orchestrator

## Quick Start

1. If the user invoked `/run`, read `skills/run.md` and follow it — this drives all phases end-to-end without pausing
2. If the user invoked `/assess`, read `skills/assess.md` and follow it — full single-issue triage in chat (does not write `analyzed.json` / `report.html`)
3. If the user invoked a specific bulk phase command (`/start`, `/scan`, `/analyze`, `/report`), read the corresponding skill file from `skills/{phase}.md` and execute it
4. If the user provided a Jira project key but no specific command, start with `skills/scan.md`
5. If no project key was provided, start with `skills/start.md` to gather it

If a step fails or produces unexpected output, stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
