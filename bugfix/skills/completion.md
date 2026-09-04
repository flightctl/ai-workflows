---
name: completion
description: Recommend next steps after one attended bugfix phase.
---

# Bugfix Phase Completion

After the completed `PHASE` reports its results, recommend the best next step
for the actual outcome, mention relevant alternatives briefly, and stop for the
user unless the `/start` guidance below applies.

- **start:** After the user selects a phase, read `dispatch.md` and follow it
  with the selected `PHASE`. Their selection is authorization to proceed; do not
  require them to enter a slash command.
- **assess:** Usually recommend `/reproduce`. Offer `/fix` when the root cause is
  already clear or `/diagnose` when existing evidence makes reproduction
  unnecessary.
- **reproduce:** Recommend `/diagnose` when reproduction succeeded or produced
  useful evidence. Recommend `/assess` if the problem definition must change.
- **diagnose:** Recommend `/fix` when the root cause is established. Otherwise
  offer another `/diagnose` when new evidence supports a revised hypothesis,
  `/reproduce` for missing evidence, or `/assess` for an incorrect premise.
- **fix:** Recommend `/test`. Offer `/diagnose` if implementation invalidated the
  root-cause analysis.
- **test:** Recommend `/review` after successful validation. Offer `/document`
  or `/pr` if review is intentionally skipped; recommend `/fix` for code failures.
- **review:** Recommend `/fix` and then `/test` when blockers remain. Otherwise
  recommend `/document`, or `/pr` if separate documentation is unnecessary.
- **document:** Recommend `/pr`; offer `/review` if review has not occurred.
- **pr:** Recommend `/feedback` when review comments arrive; otherwise the
  workflow is complete for now.
- **feedback:** Repeat `/feedback` while comments remain; otherwise the workflow
  is complete.

Never auto-advance between attended phases. The only exception is dispatching
the phase the user explicitly selected after `/start`.
