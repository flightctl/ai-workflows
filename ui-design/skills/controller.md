---
name: controller
description: Discover and route ambiguous UI design requests.
---

# UI Design Workflow Controller

Use this controller for workflow discovery and ambiguous-input routing. Once a
phase is selected, delegate its execution and completion guidance to the
lightweight dispatcher.

## Phases

1. **Ingest** (`/ingest`) — `01-ingest.md`
   Fetch the `[UI]` story from Jira, load the UX handoff, PRD, and design
   document from the docs repo, explore the UI codebase and backend API.

2. **Plan** (`/plan`) — `02-plan.md`
   Component decomposition, hook design, state management approach, route
   structure, data flow mapping, persona-aware decomposition, accessibility,
   testing strategy, and acceptance criteria mapping. Produces `02-ui-design.md`.

3. **Review API** (`/review-api`) — `03-review-api.md`
   Deep API surface review — map every UI data need to a specific backend
   endpoint and field, categorize gaps. Updates `02-ui-design.md` with API
   findings (or writes separate `03-api-findings.md` if too verbose).

4. **Revise** (`/revise`) — `04-revise.md`
   Incorporate user feedback into the UI design document and API findings.
   Repeatable.

5. **Publish** (`/publish`) — `05-publish.md`
   Push the UI design document to the docs repo as a draft GitHub PR.

6. **Respond** (`/respond`) — `06-respond.md`
   Fetch and address PR reviewer comments. Repeatable.

7. **Sync** (`/sync`) — `07-sync.md`
   Create, update, or close `[DEV]` Jira stories for API gaps identified
   during review. Manifest-based with content hashes.

## Workspace

All work happens in the **source repo** — the AI needs codebase context to
write a good UI design document. Publishing and review happen in a **separate
docs repo** so planning artifacts don't pollute the source tree.

### Workspace identifier

Throughout this workflow, `{workspace-id}` is the single identifier used in
all artifact paths. When starting from a Jira issue, `{workspace-id}` is the
Jira issue key (e.g., `PROJ-1234`). When starting from non-Jira input,
`{workspace-id}` is a user-confirmed slug derived from the input.

### Artifact directory

All working artifacts are stored in `.artifacts/ui-design/{workspace-id}/`
within the source repo (this directory should be gitignored in the source
repo):

| Artifact | File | Written by |
|----------|------|------------|
| Ingestion context | `01-context.md` | `/ingest` |
| UI design document | `02-ui-design.md` | `/plan`, `/review-api`, `/revise`, `/respond` |
| API findings (overflow) | `03-api-findings.md` | `/review-api`, `/revise`, `/respond` |
| Provenance log | `provenance.json` | `/plan`, `/revise`, `/respond` |
| PR description | `04-pr-description.md` | `/publish` |
| Publish metadata | `publish-metadata.json` | `/publish` |
| Review responses | `05-review-responses.md` | `/respond` |
| Jira sync manifest | `sync-manifest.json` | `/sync` |

### Docs repo configuration

The docs repo location is stored in `.artifacts/config.json` (workspace-level
config shared across all workflows for this source repo). This config is
created by whichever workflow's `/publish` or `/ingest` phase runs first.

If the config doesn't exist when a phase needs it, the workflow prompts for
the docs repo location and creates it:

```json
{
  "docs_repo_path": "/home/user/src/planning-docs",
  "docs_repo_remote": "git@github.com:org/planning-docs.git"
}
```

## How to Execute a Phase

Set `PHASE` to the selected phase, then read `dispatch.md` and follow it. The
dispatcher owns phase announcement, override resolution, execution, and
completion routing for both built-in phases and project overrides.

## Starting the Workflow

When the user provides a Jira issue key or URL:
1. Set `PHASE=ingest`.
2. Read `dispatch.md` and follow it.

When the user provides a UI design context in another form (text, document):
1. Derive `{workspace-id}` from the input (e.g., a slug from the document
   filename or a short user-provided label). Confirm the identifier with
   the user.
2. Set `PHASE=ingest`.
3. Read `dispatch.md` and follow it.

The `/ingest` phase handles non-Jira input: it creates the artifact
directory, compiles the provided context into `01-context.md`, and skips
Jira retrieval. After `/ingest` completes, the user can run `/plan`.

If the user invokes a specific command (e.g., `/review-api`), set `PHASE` to
that command's phase, then read `dispatch.md` and follow it. Do not force the
user through earlier phases.

For any other input, summarize the available phases, ask the user for a Jira
issue key or URL or a specific phase command, and stop without reading
`dispatch.md`.

## Error Handling

If a phase cannot complete because of an operational error (for example, a
Jira MCP, git, or `gh` CLI error):

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional), or
   escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors.

## Context Management

When the AI detects that its own output quality is degrading (e.g., it
misses details, repeats itself, or loses track of earlier decisions),
consider spawning the next phase as a subagent with a fresh context window.
This is self-monitoring by the AI, not something a human operator watches.
Load the subagent with the skill file for the phase being executed, the
relevant artifact files from `.artifacts/ui-design/{workspace-id}/`, and the
project's `AGENTS.md`/`CLAUDE.md`/`UI-ARCHITECTURE.md`.

This is a recommendation, not a requirement — not all AI runtimes support
subagent spawning.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from `completion.md`.** Phase skills report findings;
  the completion guide provides the authoritative next-step model.
- **Jira is read-only until `/sync`.** The `/ingest` phase reads from Jira but
  never modifies it. Only `/sync` modifies Jira issues, and only with explicit
  user approval.
- **Design and API findings co-evolve.** If `/revise` changes the data flow
  mapping, recommend re-running `/review-api`. If `/review-api` reveals
  fundamental gaps, recommend `/revise` to update the component architecture.
- **UX handoff is optional.** The workflow must function for `[UI]` stories
  that have no UX handoff artifact (purely technical work). When no handoff
  exists, `/plan` works from the PRD, design document, and codebase context
  alone.
