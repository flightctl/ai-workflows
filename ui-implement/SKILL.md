---
name: ui-implement
version: 0.1.0
description: >-
  Story-to-code workflow for UI/front-end stories. Takes a Jira [UI] Story,
  plans the implementation using discovered design-system and testing
  conventions, writes contract-based unit tests and production code via TDD,
  validates against the project's CI expectations, and manages review via
  GitHub PRs. Use when implementing [UI] stories produced by the design
  workflow with a ui-design document.
  Activated by commands: /ingest, /plan, /revise, /code, /validate, /publish, /respond.
---
# UI Implement Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g., `/plan`, `/code`), read
   the matching file in commands/ and follow it.
1. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a Jira issue key or URL, execute the `/ingest` phase
   - Otherwise, execute the first phase the user requests

If a step fails or produces unexpected output (e.g., Jira MCP errors, test
failures, build errors), stop and report the error to the user. Do not
advance to the next phase. Offer to retry the failed step or escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
