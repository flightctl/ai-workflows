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
  requests):** read and follow `../../_shared/recipes/e2e-coverage-policy.md`
  with PRIOR_ENTRIES from the E2E Coverage Policy section of
  `01-context.md` and DISCOVERED_FRAMEWORKS from the E2E Framework
  section. Merge the returned entries into the E2E Coverage Policy
  section of `01-context.md`, preserving other sections. If the recipe
  returns diagnostics indicating invalidated Resolutions, notify the
  user that the prior decision may no longer apply and surface the
  updated guidance.
- If the user requests adding e2e test stubs: check the refreshed
  policy for each relevant framework and path scope. If the effective
  restriction is `prohibited` or `unresolved`, **do not add** the
  requested stubs — explain the restriction and cite the source.
  This is a hard gate, not a recommendation. If `ambiguous`, surface
  the conflicting guidance and let the user decide.
- When the user resolves a readable `ambiguous` restriction (decides
  stubs are permitted or prohibited): record the Resolution with its
  scope, the decision (`none` if permitted, `prohibited` if forbidden),
  provenance, and a brief excerpt/identity of the source guidance.
  - **Full-scope clarification** (Resolution.scope equals entry Scope):
    set the entry's Restriction to the resolved value.
  - **Partial-scope clarification** (Resolution.scope narrower than
    entry Scope): the entry's raw Restriction stays `ambiguous`;
    the Resolution provides an effective override only within
    Resolution.scope. Unclarified paths remain `ambiguous`.
  Keep the original Source field unchanged. After any new clarification,
  reapply the recipe's Step 4 using all entries — no new permission
  may release a separate applicable ban. Merge refreshed entries and
  Resolution into the E2E Coverage Policy section of `01-context.md`.
  The plan revision in Step 5 updates `02-plan.md` as usual.
- User clarification CANNOT resolve `unresolved` — the recipe enforces
  this invariant. `unresolved` stays until the source is recovered and
  readable. See the recipe's Step 3 for recovery and Resolution reuse
  rules.

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

- `.artifacts/ui-implement/{issue-key}/01-context.md` (E2E Coverage Policy section refreshed)
- `.artifacts/ui-implement/{issue-key}/02-plan.md` (updated)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Assessment of plan readiness for `/code`

Then return to the invoking workflow router for completion guidance.
