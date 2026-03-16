---
name: docs-writer
description: Documentation workflow that converts requirements into structured AsciiDoc sections, runs Vale for style compliance, and produces merge-ready content. Use when creating or updating AsciiDoc documentation from Jira tickets, GitHub issues, or feature descriptions.
---
# Docs Writer Workflow Orchestrator

## Quick Start

1. Read `skills/controller.md` to load the workflow controller
2. If the user provided a Jira ticket, GitHub issue URL, or feature description, execute the `/gather` phase
3. Otherwise, execute the first phase the user requests (e.g. `/plan` if they already have context)

Each phase skill (e.g. `skills/gather-context.md`) follows this pattern:

1. Announce the phase: *"Starting /gather."*
2. Execute the skill's steps — fetch requirements, synthesize context, write artifact
3. Write output to the artifact directory and return to the controller

```bash
# Artifact directory and example validation
mkdir -p .artifacts/JIRA-123
vale .artifacts/JIRA-123/03-final-docs.adoc
```

## Example: Running /gather

To execute the gather phase without opening external files:

1. `mkdir -p .artifacts/JIRA-123`
2. Fetch the ticket (Jira MCP) or issue (`gh issue view <num> --repo <owner/repo>`); capture description, acceptance criteria, comments
3. Find linked PRs (e.g. titles with `[JIRA-123]`), fetch diffs with `gh pr diff <num> --repo <owner/repo>`
4. Synthesize Why, What, and technical changes; write `.artifacts/JIRA-123/01-context.md`

## Example: Running /validate

Fully executable without opening other files:

1. Parse `.artifacts/${ticket_id}/03-final-docs.adoc` for `// File: path/to/file.adoc` lines to get target paths
2. From repo root: `vale .artifacts/${ticket_id}/03-final-docs.adoc` (or run Vale on each path if you wrote temp `.adoc` files under `.artifacts/${ticket_id}/`)
3. If Vale reports errors: edit the draft to fix style/terminology, overwrite `03-final-docs.adoc`, run `vale` again; repeat until clean
4. Optional: from the guide directory run `./template_build.sh` or `./buildGuide.sh`; on build errors, fix draft and re-run Vale and build

## Example Session

```text
User: "Document feature from JIRA-456"
/gather   → .artifacts/JIRA-456/01-context.md
/plan     → .artifacts/JIRA-456/02-plan.md   [user must approve before /draft]
/draft    → .artifacts/JIRA-456/03-final-docs.adoc
/validate → vale; if fail → /draft then re-run /validate
/apply    → repo .adoc files updated
/mr       → merge request created
```

## Phases

Systematic documentation creation through these phases:

1. **Gather Context** (`/gather`) — Research the feature from Jira, GitHub, or a description
2. **Plan Structure** (`/plan`) — Determine where content belongs in the repository
3. **Draft Content** (`/draft`) — Write style-compliant AsciiDoc content
4. **Validate** (`/validate`) — Run Vale and optionally AsciiDoctor
5. **Apply Changes** (`/apply`) — Write validated content to repository files
6. **Create Merge Request** (`/mr`) — Create a GitLab merge request for the changes

## Phase Transitions

Each phase must meet its exit criteria before the next. If validation fails or the user requests changes, loop back:

- `/gather` → proceed when context is saved to `01-context.md`
- `/plan` → proceed when plan is saved to `02-plan.md`; **stop for user approval** before `/draft`
- `/draft` → proceed when `03-final-docs.adoc` is written
- `/validate` → proceed when Vale (and optional AsciiDoctor) pass; if they fail, return to `/draft` and re-run `/validate`
- `/apply` → proceed when repository files are updated
- `/mr` → create merge request from the applied changes

## File Layout

The workflow controller lives at `skills/controller.md`.
It defines how to execute phases, recommend next steps, and handle transitions.
Phase skills are at `skills/{name}.md`.
Artifacts go in `.artifacts/${ticket_id}/`.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
