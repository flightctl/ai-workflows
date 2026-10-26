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
  If `/code` paused for a pending scope decision (a `## Pending Scope
  Decision` section exists in `02-plan.md`), recommend `/revise` to update
  the plan with the user's decision before resuming `/code`. The user can
  invoke `/revise` directly even though `/code` did not complete — `/revise`
  requires `02-plan.md` and `01-context.md` (for acceptance criteria and
  validation profile), not the code/test/implementation reports that `/code`
  writes on completion. Do not recommend `/validate` or `/publish`
  while a scope decision is pending.
- **validate:** Recommend `/publish` only when validation passed and no scope
  decisions are pending. When failures remain, recommend fixing them and
  rerunning `/validate`; offer `/plan` for a design concern or ambiguous
  acceptance criterion that requires re-scoping. If `/validate` recorded a
  `## Pending Scope Decision` (material drift found before or during the
  review gate), recommend `/revise` — the user can invoke it with existing
  `01-context.md` and `02-plan.md`, without a completed validation report.
- **publish:** Recommend `/respond` when review comments arrive; otherwise the
  workflow is complete for now.
- **respond:** Recommend `/validate` after code changes, another `/respond`
  round while comments remain, or note completion when the PR is approved and
  no work remains. If `/respond` paused for a pending scope decision,
  recommend `/revise` — the user can invoke it directly even though
  `/respond` did not complete.

The user may start at `/code` with an existing plan or partial implementation,
and may skip `/publish` and `/respond` when working locally. Never auto-advance
between attended phases.
