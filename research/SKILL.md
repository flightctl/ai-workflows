---
name: research
version: 0.1.0
description: >-
  UX research workflow that takes a feature request through discovery,
  user research, prototyping, and heuristic evaluation to produce a
  validated design handoff artifact for implementation.
  Use when conducting UX research, creating prototypes for evaluation,
  running heuristic evaluations, or preparing design handoffs.
  Activated by commands: /ingest, /investigate, /prototype, /evaluate, /handoff.
---
# Research Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/prototype`, `/evaluate`),
   read `skills/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output, stop and report the error to
the user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, and escalation rules, see `guidelines.md`.
