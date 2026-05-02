---
name: docs-writer
description: Documentation workflow that converts requirements into structured AsciiDoc sections, runs Vale for style compliance, and produces merge-ready content. Use when creating or updating AsciiDoc documentation from Jira tickets, GitHub issues, or feature descriptions.
---
# Docs Writer Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g. `/draft`, `/validate`), read `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If a `ticket_id` is known, check `.artifacts/${ticket_id}/` for existing artifacts and resume from the next incomplete phase (see "Resuming Work" in the controller)
   - If the user provided a Jira ticket, GitHub issue URL, or feature description, execute the `/gather` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output, stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
