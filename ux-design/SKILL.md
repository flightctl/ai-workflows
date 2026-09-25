---
name: ux-design
version: 0.1.0
description: >-
  UX design workflow that takes a [UX] story through discovery,
  prototyping, and heuristic evaluation to produce a validated design
  handoff artifact for implementation. Ingest loads the PRD, design
  document, and sibling stories from shared locations so the design is
  grounded in real personas, non-functional requirements, and technical
  constraints.
  Activated by commands: /ingest, /research, /prototype, /evaluate, /handoff, /revise, /publish, /respond.
---
# UX Design Workflow Orchestrator

## Quick Start

1. If the user invoked a command, read its wrapper:
   [ingest](commands/ingest.md), [research](commands/research.md), [prototype](commands/prototype.md),
   [evaluate](commands/evaluate.md), [handoff](commands/handoff.md), [revise](commands/revise.md),
   [publish](commands/publish.md), or [respond](commands/respond.md).
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output, stop and report the error to
the user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, and escalation rules, see `guidelines.md`.
