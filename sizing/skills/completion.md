---
name: completion
description: Recommend the next step after one sizing phase.
---

# Sizing Phase Completion

After the completed `PHASE` reports its results, recommend the next step for
the actual outcome, mention relevant alternatives briefly, and stop for the
user.

- **ingest:** Recommend `/assess` when the context artifact is ready. If input
  is incomplete or stale, recommend resolving it and rerunning `/ingest`.
- **assess:** If no context exists, recommend `/ingest`. If an assessment was
  produced and the user accepts it, recommend `/apply`; if they disagree,
  offer `/assess` with added context. If the context is stale, offer `/ingest`.
- **apply:** If the user canceled the payload, confirm that Jira was unchanged
  and that any apply-time overrides from the canceled attempt were cleared.
  For failed or unattempted approved writes, offer to retry those actions. After
  a successful apply, confirm the updated and skipped Features; otherwise the
  workflow is complete.

Never run another phase automatically. Wait for the user's choice.
