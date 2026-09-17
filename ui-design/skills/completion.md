---
name: completion
description: Recommend next steps after one attended ui-design phase.
---

# UI Design Phase Completion

After the completed `PHASE` reports its results, recommend the best next step
for the actual outcome, mention relevant alternatives briefly, and stop for the
user.

- **ingest:** Recommend `/plan` unless the context has blocking gaps (missing
  PRD, missing design document, codebase access failures). If upstream
  artifacts are incomplete, recommend resolving them before planning.
- **plan:** Recommend `/review-api` to validate the data flow mapping against
  the actual backend API. If no unresolved data annotations remain (purely
  frontend refactor), offer `/publish` directly. Offer `/revise` when the
  user wants changes before API review.
- **review-api:** Recommend `/revise` for user review of the complete UI
  design (design + API findings). If the user is confident in the output,
  offer `/publish` directly. If API gaps are so significant they require
  redesigning the component architecture, recommend `/revise` to update the
  plan first.
- **revise:** Recommend `/publish` when the user is satisfied, or another
  `/revise` round when further changes remain. If the revision changed data
  flow mappings, recommend `/review-api` to re-validate API coverage before
  publishing.
- **publish:** Recommend `/respond` when review comments arrive; otherwise
  the workflow is complete for now.
- **respond:** Recommend another `/respond` round while comments remain,
  or `/sync` when the PR is approved and API gap stories need creation.
  Note completion when the PR is approved and no sync is needed.
- **sync:** The workflow is complete.
  - If stories were synced: note that `[DEV]` stories have been synced and
    suggest assigning them to the backend team.
  - If tracked-only or nothing-to-do: "API gaps have been assessed; no Jira
    changes were needed."
  - If sync encountered errors: "Sync completed with issues; review the
    manifest for details."

The user may start at `/review-api` with an existing design, and may skip
`/publish`, `/respond`, and `/sync` when working locally or when no API gaps
exist. Never auto-advance between attended phases.
