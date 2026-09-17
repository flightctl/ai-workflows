---
name: ui-design
version: 0.1.2
description: >-
  UI design workflow that takes a [UI] Jira story and UX handoff artifact,
  produces a component decomposition with hook design, state management,
  route structure, and data flow mapping, reviews the API surface for gaps,
  and syncs [DEV] stories for backend work to Jira.
  Activated by commands: /ingest, /plan, /review-api, /revise, /publish, /respond, /sync.
---
# UI Design Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command, read `commands/{command}.md` and
   follow it. Phases: `ingest`, `plan`, `review-api`, `revise`, `publish`,
   `respond`, `sync`.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output (e.g., Jira MCP errors, network
failures, codebase exploration failures), stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
