---
name: dispatch
description: Lightweight dispatcher for explicit sizing commands.
---

# Sizing Phase Dispatch

Require `PHASE` to be `ingest`, `assess`, or `apply`. If it is missing or
unsupported, report the valid phases and stop before resolving a phase file.

Initialize `COMPLETION_CONSUMED=false`. Announce `Starting /{PHASE}.` and
inspect the consuming project's `AGENTS.md` or `CLAUDE.md` if it has not
already been read in this run. Read `../guidelines.md` if it has not already
been read in this run. Resolve the phase file by following
`../../_shared/recipes/phase-override-resolution.md` with `WORKFLOW=sizing` and
`PHASE_FILE={PHASE}.md`. Read and execute the resolved phase instructions,
passing through the command context unchanged.

Follow the phase through its result report. Treat a return to the invoking
router, a request for completion guidance, or a request to re-read the
controller as a return to this dispatcher. If the phase already reads
`completion.md`, set `COMPLETION_CONSUMED=true`. After the phase returns, read
`completion.md` once and follow it with `PHASE` only when
`COMPLETION_CONSUMED=false`.

If a phase cannot be resolved or an operational error prevents it from
producing a phase report, report the exact error and stop without reading
`completion.md`; offer a retry or escalation. For a reported partial outcome,
including failed Jira writes, read the guide so it can recommend recovery.
Never run another phase automatically.

Before any Jira write, apply the exact-payload approval rule in
`../guidelines.md`.
