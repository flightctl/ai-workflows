---
name: sizing
version: 0.5.0
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
Before any artifact access, follow [the shared artifact resolver](../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

## Quick Start

1. If the user invoked a specific command (e.g., `/assess`, `/apply`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to discover the input and route it
   through the phase dispatcher.

If a step fails or produces unexpected output (e.g., Jira MCP errors, network failures,
invalid issue keys), stop and report the error to the user. Do not advance to the next phase. Offer to retry the failed step or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`. The `scripts/` helpers compact source data, validate AI judgments, calculate derived values, and render artifacts; use JSON artifacts between phases.
