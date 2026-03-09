---
name: bugfix
description: Multi-step diagnostic and repair workflow. Use when fixing bugs, debugging issues, investigating failures, or submitting bug-fix pull requests.
---
# Bugfix Workflow Orchestrator

Systematic bug resolution through these phases:

1. **Assess** (`/assess`) — Read the bug report, explain understanding, propose a plan
2. **Reproduce** (`/reproduce`) — Confirm and document the bug
3. **Diagnose** (`/diagnose`) — Identify root cause and impact
4. **Fix** (`/fix`) — Implement the solution
5. **Test** (`/test`) — Verify the fix, create regression tests
6. **Review** (`/review`) — *(Optional)* Critically evaluate fix and tests
7. **Document** (`/document`) — Release notes and documentation
8. **PR** (`/pr`) — Submit a pull request

The workflow controller lives at `skills/controller.md`.
It defines how to execute phases, recommend next steps, and handle transitions.
Phase skills are at `skills/{name}.md`.
Artifacts go in `.artifacts/{number}/bugfix/{issue}`.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
