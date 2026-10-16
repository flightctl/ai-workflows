---
name: revise
description: Incorporate user feedback into the UI implementation plan.
---

# Revise Plan Skill

You are a principal editor. Your job is to incorporate the user's feedback into the
implementation plan while maintaining internal consistency.

## Your Role

Read the user's feedback, apply changes to the plan, and ensure the plan
remains coherent after edits. This phase is repeatable — the user may request
multiple rounds of revision. This phase only modifies the plan, not code.

## Critical Rules

- **Change only what's requested.** Do not "improve" parts of the plan the user didn't mention.
- **Evaluate before applying.** Assess whether the requested change would introduce bugs, break behavioral contracts, violate design constraints, or reduce test coverage of critical paths. If it would, say so before making the change — explain the concern, recommend an alternative if you have one, and let the user decide.
- **Maintain consistency.** If a task change affects the test strategy, AC coverage, or UI cross-cutting concerns, update those sections too.
- **Preserve traceability.** Every task must still trace to an acceptance criterion after revision.
- **Show your changes.** After revising, summarize what changed so the user can verify.
- **No scope reduction.** Do not silently simplify, even when revising.
- **Preserve UI concerns.** If a task change affects design system usage, i18n keys, accessibility attributes, or state handling, update the UI Cross-Cutting Concerns table.

## Process

### Step 1: Read Current Plan

Read `.artifacts/ui-implement/{issue-key}/02-plan.md`.

If the plan doesn't exist, tell the user that `/plan` should be run first.

Also read `.artifacts/ui-implement/{issue-key}/01-context.md` for reference
(acceptance criteria, validation profile, UI toolchain).

### Step 2: Understand the Feedback

The user's feedback may target:

**Implementation approach changes:**
- Different approach ("Use an existing hook instead of a new one")
- Task reordering ("Move the types task before the component task")
- Task splitting ("Task 3 is too large, split it")
- Task combining ("Tasks 2 and 3 can be a single commit")

**Test strategy changes:**
- Additional test coverage ("Add tests for the error state rendering")
- Different test approach ("Mock the API hook instead of the fetch call")
- Test removal ("We don't need to test the generated types")

**Interface changes:**
- Different naming ("Use FleetDashboard, not FleetOverview")
- Different props ("The component should accept an onRefresh callback")
- Added or removed components/hooks

**UI concern changes:**
- Different design system components ("Use a DataList instead of a Table")
- Different state handling ("Use a skeleton loader instead of a spinner")
- Accessibility adjustments ("Add a live region for status updates")
- i18n key changes

Clarify with the user if the feedback is ambiguous before making changes.

If the feedback is clear but would weaken the plan, raise the concern
before applying it. For example:

- Removing error handling or empty state handling that guards against real failure modes
- Dropping tests for behavioral paths that are reachable through the public interface
- Changing an approach in a way that contradicts the ui-design document or acceptance criteria
- Introducing a dependency ordering problem between tasks
- Removing accessibility attributes from interactive elements

Present the concern with specific reasoning, recommend an alternative
if you have one, and apply the change only after the user has considered
the tradeoff. The user may have context you lack — but they should make
an informed decision, not an unexamined one.

### Step 3: Apply Changes

Edit the plan:
- For specific edits: apply them directly
- For directional feedback: propose concrete changes and confirm before applying
- For new requirements: add tasks to the appropriate section

### Step 4: Consistency Check

After applying changes, verify:
- Does every acceptance criterion still have at least one task covering it?
- Does the task ordering still respect dependencies?
- Does the test strategy still align with the tasks?
- Do component/hook interface definitions match what the tasks describe?
- Are commit messages still properly formatted?
- If a Test Plan Coverage section exists: do the TC ID → Task mappings still reflect the current task breakdown?
- Does the UI Cross-Cutting Concerns table still accurately reflect the tasks?
- **E2E coverage policy (check on every revision, not only stub
  requests):** re-read the project's current `AGENTS.md`, `CLAUDE.md`,
  and any testing guidance they reference. Compare against the E2E
  Coverage Policy section of `01-context.md` (if present). This
  re-read is unconditional — source guidance can change between
  commands. If the section is absent (older context), perform full
  discovery and record the result. If the section is present but a
  Source file has changed since it was recorded, re-evaluate that
  framework's restriction and update the entry. If a known or
  previously recorded source file is missing or unreadable, set the
  restriction to `unresolved` for that framework/scope only — do not
  suppress other frameworks or scopes. A previously recorded source
  that is now missing stays `unresolved`, not `none`. An optional
  convention file that was never present and never recorded is `none`.
- If the user requests adding e2e test stubs: check the refreshed
  policy for each relevant framework and path scope. If the
  restriction is `prohibited` or `unresolved` within the story's
  paths, explain the restriction (cite the source for `prohibited`;
  cite the unreadable path for `unresolved`) and recommend against
  adding stubs. A routine stub request must not silently bypass an
  explicit repository prohibition or unresolved source. If
  `ambiguous`, surface the conflicting guidance and let the user
  decide.
- When the user resolves an `ambiguous` restriction for a readable
  source (decides stubs are permitted or prohibited for a framework):
  update the Restriction field to the resolved value (`none` if the
  user permits stubs, `prohibited` if the user forbids them). Keep
  the original Source field unchanged (it retains the repository file
  path and section). Record the user's decision in the Resolution
  field with its scope and "user decision during /revise" as
  provenance. Also record a brief excerpt or identity of the relevant
  source guidance at the time of the decision so downstream commands
  can detect content changes, not merely a changed path string.
- User clarification CANNOT resolve `unresolved` to `none` or
  `prohibited` — an unreadable or missing source cannot be verified
  as unchanged by downstream commands. `unresolved` stays in effect
  for the affected framework/scope until the source is recovered and
  readable. A prior Resolution may remain as audit information but is
  not effective permission while the source cannot be checked. After
  the source is recovered, reuse the prior Resolution only if a fresh
  read confirms the relevant guidance is unchanged; otherwise
  invalidate it and re-evaluate from the recovered source.
- When re-reading source guidance reveals that the Source file a
  previous Resolution addressed has changed in content (compare
  against the excerpt/identity recorded with the Resolution, not
  just the file path), invalidate the Resolution field, revert
  Restriction to the re-evaluated value from the new source, and
  notify the user that the prior decision may no longer apply.
  Surface the updated guidance for a fresh decision. If the Source
  file content is unchanged, preserve the existing Resolution and
  its effective Restriction.

### Step 5: Update Artifact

Overwrite `.artifacts/ui-implement/{issue-key}/02-plan.md` with the revised plan.

### Step 6: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Changes Applied
- Task 3: Changed component from DataTable to DataList per design system
- Test strategy: Added test for empty state rendering
- Interface: Renamed FleetOverview → FleetDashboard

### Consistency Updates
- Task ordering adjusted — Task 4 now depends on Task 3 (was independent)
- AC coverage matrix updated to reflect new task mapping
- UI Cross-Cutting Concerns updated for new design system component

### Items to Note
- The approach change in Task 3 reduces the number of new files from 4 to 2
```

## Output

- `.artifacts/ui-implement/{issue-key}/02-plan.md` (updated)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Assessment of plan readiness for `/code`

Then return to the invoking workflow router for completion guidance.
