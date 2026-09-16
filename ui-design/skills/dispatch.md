---
name: dispatch
description: Resolve and execute one explicitly requested ui-design phase.
---

# UI Design Phase Dispatch

Require `PHASE` to be one of `ingest`, `plan`, `review-api`, `revise`,
`publish`, `respond`, or `sync`. If it is missing or unsupported, report
the valid phases and stop before resolving a filename.

## Phase File Mapping

UI design phase filenames use numeric prefixes. Map `PHASE` to the
corresponding skill filename before resolving overrides:

| PHASE | PHASE_FILE |
|-------|------------|
| `ingest` | `01-ingest.md` |
| `plan` | `02-plan.md` |
| `review-api` | `03-review-api.md` |
| `revise` | `04-revise.md` |
| `publish` | `05-publish.md` |
| `respond` | `06-respond.md` |
| `sync` | `07-sync.md` |

## Dispatch Procedure

Before dispatching, initialize `COMPLETION_CONSUMED=false` and read the
project's `AGENTS.md`, `CLAUDE.md`, or `UI-ARCHITECTURE.md` only if none
is already in the session. For `PHASE=ingest`, do not glob this workflow,
load `guidelines.md`, or call `GetDynamicTools`; these guards apply before
loading either a built-in phase or a project override. Ensure MCP tools are
available for phases that need them (`/ingest` needs Jira, `/publish` and
`/respond` need GitHub) but do not eagerly load tools for every phase.

Announce `Starting /{PHASE}.` and read and follow
`../../_shared/recipes/phase-override-resolution.md` with `WORKFLOW=ui-design`
and `PHASE_FILE={PHASE_FILE}` (from the mapping above). Read and execute the
resolved phase file, passing through the command context unchanged.

The built-in fallback is the phase file beside this dispatcher. Follow the
phase through its reporting step. Normalize the recipe's supported exits to a
return to this dispatcher: an invoking-router return, a request for this
workflow's completion guide, or a return to this workflow's controller. Map
`COMPLETION_HANDOFF=router-defined` to the invoking-router return. This mapping
applies during override validation as well as execution. Normalize the handoff
without executing its destination and leave `COMPLETION_CONSUMED=false`. Then
read `completion.md` once and follow its guidance for `PHASE`; the dispatcher
is the only component that reads the completion guide.

Legacy completion instructions may say to follow `controller.md` only if it
is already in the session. After such a phase finishes its steps and report,
treat it as a supported return even when that condition skips reading the
controller. Preserve the loading condition; do not load the controller just to
complete the phase.

Controller-return normalization preserves the completion contract of existing
project overrides and remains supported. Prefer an invoking-router return for
new ui-design phases and overrides; legacy exits do not require migration.

If the recipe rejects an override, continue with its built-in fallback. Stop
without reading `completion.md` only if that fallback cannot be resolved, an
operational error prevents the phase from completing, or the executing phase
lacks supported completion behavior. Report the specific failure. A completed
phase report with a failing verdict is a valid outcome: read `completion.md`
so it can provide appropriate guidance.
