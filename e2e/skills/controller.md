---
name: controller
description: Discover and route ambiguous e2e test implementation requests.
---

# E2E Test Workflow Controller

Use this controller for workflow discovery and ambiguous-input routing. Once a
phase is selected, delegate its execution and completion guidance to the
lightweight dispatcher.

## Phases

1. **Ingest** (`/ingest`) — `ingest.md`
   Fetch the [QE] Jira story, verify [DEV] dependencies are merged, explore
   the project's e2e test infrastructure, and build a test-execution profile.

2. **Plan** (`/plan`) — `plan.md`
   Map acceptance criteria to e2e test scenarios, select the reference suite
   pattern, and design the test file structure.

3. **Revise** (`/revise`) — `revise.md`
   Incorporate user feedback into the test plan. Repeatable.

4. **Code** (`/code`) — `code.md`
   Write e2e test code following discovered patterns, committing incrementally.

5. **Validate** (`/validate`) — `validate.md`
   Run e2e tests, check for anti-patterns, verify scenario coverage, and
   assess PR readiness.

6. **Publish** (`/publish`) — `publish.md`
   Push the feature branch and create a draft PR in the source repo.

7. **Respond** (`/respond`) — `respond.md`
   Fetch and address PR reviewer comments. Repeatable.

## Workspace

All work happens in the **source repo** — this workflow modifies test code
directly. Planning artifacts live in `.artifacts/e2e/{issue-key}/` (gitignored).
Test code changes live on a feature branch in the source repo.

### Artifact directory

All working artifacts are stored in `.artifacts/e2e/{issue-key}/` within
the source repo:

| Artifact | File | Written by |
|----------|------|------------|
| Story context | `01-context.md` | `/ingest` |
| Test plan | `02-plan.md` | `/plan`, `/revise`, `/code` |
| Test report | `03-test-report.md` | `/code` |
| Implementation report | `04-impl-report.md` | `/code` |
| Validation report | `05-validation-report.md` | `/validate` |
| PR description | `06-pr-description.md` | `/publish` |
| Publish metadata | `publish-metadata.json` | `/publish` |
| Review responses | `07-review-responses.md` | `/respond` |

## How to Execute a Phase

Set `PHASE` to the selected phase, then read `dispatch.md` and follow it. The
dispatcher owns phase announcement, override resolution, execution, and
completion routing for both built-in phases and project overrides.

## Starting the Workflow

When the user provides a Jira issue key or URL:
1. Set `PHASE=ingest`.
2. Read `dispatch.md` and follow it.

If the user invokes a specific command (e.g., `/code`), set `PHASE` to that
command's phase, then read `dispatch.md` and follow it. Do not force the user
through earlier phases.

For any other input, summarize the available phases, ask the user for a Jira
issue key or URL or a specific phase command, and stop without reading
`dispatch.md`.

## Error Handling

If a phase cannot complete because of an operational error (for example, a
Jira MCP or git error):

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional), or escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors. A completed validation report with a failing verdict is a valid
phase outcome; route it through `completion.md` for fix-and-rerun guidance.

## Context Management

When the AI detects that its own output quality is degrading (e.g., it
misses details, repeats itself, or loses track of earlier decisions),
consider spawning the next phase as a subagent with a fresh context window.
This is self-monitoring by the AI, not something a human operator watches. Load the subagent with
the skill file for the phase being executed, the relevant artifact files from
`.artifacts/e2e/{issue-key}/`, and the project's `AGENTS.md`/`CLAUDE.md`.

This is a recommendation, not a requirement — not all AI runtimes support
subagent spawning.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from `completion.md`.** Phase skills report findings;
  the completion guide provides the authoritative next-step model.
- **Jira is read-only.** The `/ingest` phase reads from Jira but never modifies it. No phase in this workflow writes to Jira.
- **Plan evolves during implementation.** `/code` updates `02-plan.md` as tasks are completed. This is expected, not a sign of plan failure.
- **Validation is mandatory before publishing.** Never recommend `/publish` unless `/validate` has passed.
