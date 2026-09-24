---
name: controller
description: Discover the default sizing input and route it to the phase dispatcher.
---

# Sizing Workflow Controller

Use this controller only for the default `/sizing` entry point. Explicit phase
commands already route through `dispatch.md`. The dispatcher owns phase
announcements, project guidance, override resolution, execution, and error
handling. `completion.md` owns next-step guidance after a phase; do not repeat
either file's instructions here.

## Discover and Route

- For a Jira issue key or URL, preserve the input, set `PHASE=ingest`, and read
  and follow `dispatch.md` with `PHASE=ingest`.
- For a release identifier such as `release:EDM:1.3.0`, preserve the input, set
  `PHASE=ingest`, and read and follow `dispatch.md` with `PHASE=ingest`.
- If input is absent or ambiguous, ask for a Jira issue key/URL or a release
  identifier. Then route it to `dispatch.md` with `PHASE=ingest`.
