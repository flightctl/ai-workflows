---
name: e2e
description: >-
  Story-to-e2e-test workflow that takes a Jira [QE] Story, discovers the
  project's e2e testing infrastructure, plans test scenarios, writes e2e
  tests matching project conventions, validates them, and manages review
  via GitHub PRs. Use when implementing [QE] stories produced by the
  design workflow.
  Activated by commands: /ingest, /plan, /revise, /code, /validate, /publish, /respond.
---
# E2E Test Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/plan`, `/code`), read
   `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output (e.g., Jira MCP errors, test
failures, build errors), stop and report the error to the user. Do not
advance to the next phase. Offer to retry the failed step or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
