---
name: completion
description: Recommend next steps after one attended implement phase.
---

# Implement Phase Completion

After the completed `PHASE` reports its results, recommend the best next step
for the actual outcome, mention relevant alternatives briefly, and stop for the
user.

- **ingest:** Recommend `/plan` unless the story context has blocking gaps. If
  the story is contradictory or incomplete, recommend clarification from the
  story author before planning.
- **plan:** Recommend `/revise` for user-requested changes, or `/code` when the
  user has already reviewed and accepted the plan.
- **revise:** Recommend `/code` when the user is satisfied, or another
  `/revise` round when further changes remain.
- **code:** Recommend `/validate`. If implementation exposed a plan gap, note
  the inline plan update or offer `/plan` when redesign requires user review.
- **validate:** Recommend `/publish` only when validation passed. When failures
  remain, recommend fixing them and rerunning `/validate`; offer `/plan` for a
  design concern or ambiguous acceptance criterion that requires re-scoping.
- **publish:** Recommend `/respond` when review comments arrive; otherwise the
  workflow is complete for now.
- **respond:** Recommend `/validate` after code changes, another `/respond`
  round while comments remain, or note completion when the PR is approved and
  no work remains.

The user may start at `/code` with an existing plan or partial implementation,
and may skip `/publish` and `/respond` when working locally. Never auto-advance
between attended phases.
