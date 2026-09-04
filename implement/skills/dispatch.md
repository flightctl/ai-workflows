---
name: dispatch
description: Resolve and execute one explicitly requested implement phase.
---

# Implement Phase Dispatch

Before dispatching, read the project's `AGENTS.md` or `CLAUDE.md` only if
neither is already in the session. Then, given `PHASE`, announce
`Starting /{PHASE}.` and read and follow
`../../_shared/recipes/phase-override-resolution.md` with `WORKFLOW=implement`
and `PHASE_FILE={PHASE}.md`. Read and execute the resolved phase file, passing
through the command context unchanged.

The built-in fallback is the phase file beside this dispatcher. For this
workflow, the resolved phase must end by returning to the invoking workflow
router, matching the built-in phase contract. Follow the phase through its
reporting step and terminal return. Then read `completion.md` and follow its
guidance for `PHASE`; the dispatcher is the only component that reads the
completion guide.

If override resolution fails, an operational error prevents the phase from
completing, or the phase lacks a valid terminal return, report the failure and
stop without reading `completion.md`. A completed phase report with a failing
verdict, including `validate.md` reporting `FAIL`, is a valid outcome: read
`completion.md` so it can provide fix-and-rerun guidance.
