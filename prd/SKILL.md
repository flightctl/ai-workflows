---
name: prd
description: >-
  Requirements-to-PRD workflow that ingests requirements from Jira, clarifies
  ambiguities through iterative Q&A, drafts a Product Requirements Document,
  and manages review via GitHub PRs.
  Use when creating PRDs, analyzing requirements, or preparing feature
  specifications for review.
  Activated by commands: /ingest, /clarify, /draft, /revise, /publish, /respond.
---
# PRD Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/draft`, `/clarify`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output (e.g., Jira MCP errors, network
failures, invalid issue keys), stop and report the error to the user. Do not
advance to the next phase. Offer to retry the failed step or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
