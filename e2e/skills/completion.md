---
name: completion
description: Recommend next steps after one attended e2e phase.
---

# E2E Phase Completion

After the completed `PHASE` reports its results, recommend the best next step
for the actual outcome, mention relevant alternatives briefly, and stop for the
user.

- **ingest:** Recommend `/plan` unless the story context, [DEV] dependencies,
  or test infrastructure has blocking gaps. Recommend clarification or waiting
  for dependencies when planning cannot proceed safely.
- **plan:** Recommend `/revise` for user-requested changes, or `/code` when the
  user has already reviewed and accepted the plan.
- **revise:** Recommend `/code` when the user is satisfied, or another
  `/revise` round when further changes remain.
- **code:** Recommend `/validate`. If implementation exposed a plan gap, note
  the inline plan update or offer `/plan` when user review is needed. For a
  feature defect, report it without recommending an out-of-scope product-code
  fix. For missing test infrastructure, present the documented deviation
  options for user choice.
- **validate:** Recommend `/publish` only when validation passed. When failures
  or anti-patterns remain, recommend fixing them and rerunning `/validate`.
  Add missing scenarios when an acceptance-criteria gap is fixable; escalate
  ambiguous or non-e2e-testable criteria to the user.
- **publish:** Recommend `/respond` when review comments arrive; otherwise the
  workflow is complete for now.
- **respond:** Recommend `/validate` after code changes, another `/respond`
  round while comments remain, or note completion when the PR is approved and
  no work remains.

The user may start at `/code` with an existing plan or partial test
implementation, and may skip `/publish` and `/respond` when working locally.
Never auto-advance between attended phases.
