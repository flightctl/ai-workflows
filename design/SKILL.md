---
name: design
description: >-
  Design-and-decompose workflow that takes a PRD, researches the problem space,
  drafts a technical design document, decomposes work into Jira-ready epics and
  stories, and manages review via GitHub PRs.
  Use when creating design documents, researching external integrations or
  standards, breaking features into epics/stories, or syncing task breakdowns
  to Jira.
  Activated by commands: /ingest, /research, /draft, /decompose, /revise, /publish, /respond, /sync.
---
# Design Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/draft`, `/decompose`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output (e.g., Jira MCP errors, network
failures, codebase exploration failures), stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
