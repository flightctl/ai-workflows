---
name: dispatch
description: Resolve and execute one explicitly requested implement phase.
---

# Implement Phase Dispatch

Require `PHASE` to be one of `ingest`, `plan`, `revise`, `code`, `validate`,
`publish`, or `respond`. If it is missing or unsupported, report the valid
phases and stop before resolving a filename.

Before dispatching, read the project's `AGENTS.md` or `CLAUDE.md` only if
neither is already in the session. For `PHASE=ingest`, do not glob this workflow,
load `guidelines.md` or `gh-stack`, or call `GetDynamicTools`; these guards apply
before loading either a built-in phase or a project override.

Announce `Starting /{PHASE}.` and read and follow
`../../_shared/recipes/phase-override-resolution.md` with `WORKFLOW=implement`
and `PHASE_FILE={PHASE}.md`. Read and execute the resolved phase file, passing
through the command context unchanged.

The built-in fallback is the phase file beside this dispatcher. Follow the
phase through its reporting step. Normalize the recipe's supported exits to a
return to this dispatcher: an invoking-router return, a request for this
workflow's completion guide, or a return to this workflow's controller. This
mapping applies during override validation as well as execution. Then read
`completion.md` and follow its guidance for `PHASE`; the dispatcher is the only
component that reads the completion guide.

Legacy completion instructions may say to follow `controller.md` only if it
is already in the session. After such a phase finishes its steps and report,
treat it as a supported return even when that condition skips reading the
controller. Preserve the loading condition; do not load the controller just to
complete the phase.

Controller-return normalization preserves the completion contract of existing
project overrides and remains supported. Prefer an invoking-router return for
new implement phases and overrides; legacy exits do not require migration.

If the recipe rejects an override, continue with its built-in fallback. Stop
without reading `completion.md` only if that fallback cannot be resolved, an
operational error prevents the phase from completing, or the executing phase
lacks supported completion behavior. Report the specific failure. A completed phase
report with a failing verdict, including `validate.md` reporting `FAIL`, is a
valid outcome: read `completion.md` so it can provide fix-and-rerun guidance.
