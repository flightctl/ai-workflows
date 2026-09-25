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
- **apply:** Handle exactly one outcome:
  - If the user canceled, confirm Jira was unchanged. Confirm affected
    apply-time overrides match their pre-attempt values only if restoration
    succeeded. If it failed, report the exact error and recommend retrying
    `restore-overrides` with the saved map; do not claim the artifacts were
    restored.
  - If no actions were prepared, report that no committable Features are
    available. Use the assessment to identify any XXL Features, recommend
    splitting them, and rerunning `/assess`; do not infer XXL from an empty
    payload.
  - If the Jira write integration was unavailable, report that Jira is
    unchanged, include the prepared payload path, and offer to retry `/apply`
    after the integration is available.
  - If approved writes failed or remain unattempted, offer to retry only those
    operations; do not repeat writes that already succeeded. Do not mark the
    workflow complete until every approved write succeeds.
  - After every approved write succeeds, confirm updated and skipped Features
    and mark the workflow complete.

Never run another phase automatically. Wait for the user's choice.
