---
name: kcs
description: >-
  KCS article workflow that gathers bug context from Jira and user input,
  drafts a KCS Solution article in markdown, validates it against the KCS
  Content Standard, and produces a handoff message for the support engineer.
  Use when writing KCS articles for known issues with workarounds.
  Activated by commands: /gather, /draft, /validate, /handoff.
---
# KCS Article Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/draft`, `/handoff`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/gather` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output (e.g., Jira MCP errors, network
failures, invalid issue keys), stop and report the error to the user. Do not
advance to the next phase. Offer to retry the failed step or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
