---
name: sizing
version: 0.1.0
description: >-
  Pre-cycle Feature sizing workflow that assesses Features from Jira using
  T-shirt sizes (XS–XXL), produces per-team effort breakdowns (DEV, QE, UX, UI, DOCS),
  and writes results back to Jira. Accepts a single Feature or all Features
  in a Fix Version for batch sizing.
  Use when sizing Features for cycle planning, prioritizing a release backlog,
  or evaluating whether a Feature fits in a cycle.
  Activated by commands: /ingest, /assess, /apply.
---
# Sizing Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/assess`, `/apply`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
     in single-Feature mode
   - If the user provided a release identifier (e.g., `release:EDM:1.3.0`),
     execute the `/ingest` phase in batch mode
   - Otherwise, ask the user for a Feature key or release identifier

If a step fails or produces unexpected output (e.g., Jira MCP errors, network
failures, invalid issue keys), stop and report the error to the user. Do not
advance to the next phase. Offer to retry the failed step or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
