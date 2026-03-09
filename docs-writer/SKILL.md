---
name: docs-writer
description: Multi-step documentation workflow. Use when creating or updating AsciiDoc documentation from Jira tickets, GitHub issues, or feature descriptions.
---
# Docs Writer Workflow Orchestrator

Systematic documentation creation through these phases:

1. **Gather Context** (`/gather`) — Research the feature from Jira, GitHub, or a description
2. **Plan Structure** (`/plan`) — Determine where content belongs in the repository
3. **Draft Content** (`/draft`) — Write style-compliant AsciiDoc content
4. **Validate** (`/validate`) — Run Vale and optionally AsciiDoctor
5. **Apply Changes** (`/apply`) — Write validated content to repository files
6. **Create Merge Request** (`/mr`) — Create a GitLab merge request for the changes

The workflow controller lives at `skills/controller.md`.
It defines how to execute phases, recommend next steps, and handle transitions.
Phase skills are at `skills/{name}.md`.
Artifacts go in `.artifacts/${ticket_id}/`.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
