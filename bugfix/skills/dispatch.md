---
name: dispatch
description: Resolve and execute one explicitly requested bugfix phase.
---

# Bugfix Phase Dispatch

Given `PHASE`, announce `Starting /{PHASE}.` Then read and follow
`../../_shared/recipes/phase-override-resolution.md` with `WORKFLOW=bugfix` and
`PHASE_FILE={PHASE}.md`. Read and execute the resolved phase file, passing
through the command context unchanged.

The built-in fallback is the phase file beside this dispatcher. Follow the
phase through its reporting step. Treat any valid phase exit—returning to the
invoking router, requesting completion guidance, or re-reading the
controller—as a return to this dispatcher. Then read `completion.md` and follow
its guidance for `PHASE`.

If override resolution fails, an operational error prevents the phase from
completing, or the phase lacks a supported terminal exit, report the failure
and stop without reading `completion.md`. A completed phase report with a
failing verdict is a valid outcome: read `completion.md` so it can provide
recovery guidance.
