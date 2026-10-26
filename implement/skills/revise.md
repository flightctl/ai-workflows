---
name: revise
description: Incorporate user feedback into the implementation plan.
---

# Revise Plan Skill

You are a principal editor. Your job is to incorporate the user's feedback into the
implementation plan while maintaining internal consistency.

## Your Role

Read the user's feedback, apply changes to the plan, and ensure the plan
remains coherent after edits. This phase is repeatable — the user may request
multiple rounds of revision. By default this phase modifies the plan only, not
source code. The one exception is reconciling already-written source changes to
an approved scope decision (see Scope decisions below): the user must explicitly
approve any concrete source cleanup before it is applied.

## Critical Rules

- **Change only what's requested.** Do not "improve" parts of the plan the user didn't mention.
- **Evaluate before applying.** Assess whether the requested change would introduce bugs, break behavioral contracts, violate design constraints, or reduce test coverage of critical paths. If it would, say so before making the change — explain the concern, recommend an alternative if you have one, and let the user decide.
- **Maintain consistency.** If a task change affects the test strategy or AC coverage, update those sections too.
- **Preserve traceability.** Every task must still trace to an acceptance criterion after revision.
- **Show your changes.** After revising, summarize what changed so the user can verify.
- **No scope reduction.** Do not silently simplify, even when revising.
- **Source reconciliation requires explicit approval.** When a scope decision requires reconciling already-written source changes (revert declined scope, set aside extracted work), explain the concrete changes to the user and obtain explicit approval before modifying source files. Do not discard unrelated or user-owned work. If safe isolation is unclear, keep the `## Pending Scope Decision` section and stop for clarification rather than claiming the plan is ready.

## Process

### Step 1: Read Current Plan

Read `.artifacts/implement/{issue-key}/02-plan.md`.

If the plan doesn't exist, tell the user that `/plan` should be run first.

Also read `.artifacts/implement/{issue-key}/01-context.md` for reference
(acceptance criteria, validation profile).

### Step 2: Understand the Feedback

The user's feedback may target:

**Implementation approach changes:**
- Different approach ("Use the existing reconciler pattern instead of a new service")
- Task reordering ("Move the API types task before the test task")
- Task splitting ("Task 3 is too large, split it")
- Task combining ("Tasks 2 and 3 can be a single commit")

**Scope decisions (from `/code`, `/respond`, or `/validate` pause):**
The `## Pending Scope Decision` section of `02-plan.md` records the
unresolved decision (`/code`, `/respond`, and `/validate` create it;
`/revise` is the only phase that resolves or clears the recorded
decision or dependency marker). After applying the user's decision:
- **Approving scope expansion** — update the Scope Baseline, add or
  modify tasks. If already-written source changes need reconciliation
  (retain aligned work, revert or set aside declined scope), explain
  the concrete cleanup to the user and apply only after explicit
  approval. Remove the `## Pending Scope Decision` section only after
  approved reconciliation is complete (or the user confirms no cleanup
  is needed).
- **Extracting a prerequisite** — remove the expanded work from this
  plan, adjust remaining tasks. **Do not remove the `## Pending Scope
  Decision` section.** Instead, update it to record the extraction
  decision and the prerequisite identifier (story key or branch). The
  section acts as a durable dependency marker: entry guards in `/code`,
  `/validate`, `/respond`, and `/publish` observe it and block until
  the prerequisite has merged. If already-written source changes
  (committed or uncommitted) need cleanup to isolate the extracted
  work, explain the changes and obtain explicit user approval before
  modifying source. The section remains until BOTH: (a) any required
  source cleanup is approved and complete (or verified unnecessary),
  and (b) the user confirms the prerequisite has merged. A subsequent
  `/revise` removes the section only when both conditions hold.
- **Declining expansion** — document the rationale. If already-written
  declined-scope source changes exist (committed or uncommitted),
  explain what will be reverted or set aside and obtain explicit user
  approval before modifying source; preserve in-scope and unrelated
  edits. Declining expansion alone does not authorize discarding
  edits — the user must approve the concrete cleanup. If the user
  withholds cleanup approval, retain the `## Pending Scope Decision`
  section and stop; entry guards in `/code`, `/validate`, `/respond`,
  and `/publish` continue to block until the decision is fully
  resolved. If no declined-scope changes exist, confirm that
  explicitly. Remove the `## Pending Scope Decision` section only
  after approved cleanup is complete (or the user confirms no cleanup
  is needed after reviewing the current state), subject to all normal
  phase entry and validation requirements before resuming.

**Test strategy changes:**
- Additional test coverage ("Add tests for the concurrent update edge case")
- Different test approach ("Use integration tests instead of mocks for the store layer")
- Test removal ("We don't need to test the generated code")

**Interface changes:**
- Different naming ("Use FleetRollbackService, not RollbackManager")
- Different signatures ("The function should accept a context parameter")
- Added or removed types

Clarify with the user if the feedback is ambiguous before making changes.

If the feedback is clear but would weaken the plan, raise the concern
before applying it. For example:

- Removing error handling or nil checks that guard against real failure
  modes
- Dropping tests for behavioral paths that are reachable through the
  public interface
- Changing an approach in a way that contradicts the design document or
  acceptance criteria
- Introducing a dependency ordering problem between tasks

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
- Do interface definitions match what the tasks describe?
- Are commit messages still properly formatted?
- If a Test Plan Coverage section exists: do the TC ID → Task mappings still reflect the current task breakdown? If tasks were added, removed, split, or combined, update the Covered by Task column accordingly.
- If a Scope Baseline section exists: do the Intended Feature Changes, Known Supporting Refactoring (including Prerequisite Rationale), Affected Interfaces and Components, and Expected Delivery Boundaries still reflect the current plan? If scope was expanded or narrowed, update the baseline to match.
- `## Pending Scope Decision` lifecycle: on approve-expansion or decline, remove it only after any required source cleanup is approved and complete (or verified unnecessary). On extract-prerequisite, update it to record the extraction decision and keep it as a dependency marker until both required cleanup is done and the prerequisite has merged with user confirmation.

### Step 5: Update Artifact

Overwrite `.artifacts/implement/{issue-key}/02-plan.md` with the revised plan.

### Step 6: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Changes Applied
- Task 3: Changed approach from new service to existing reconciler pattern
- Test strategy: Added integration test for store layer interaction
- Interface: Renamed RollbackManager → FleetRollbackService

### Consistency Updates
- Task ordering adjusted — Task 4 now depends on Task 3 (was independent)
- AC coverage matrix updated to reflect new task mapping

### Items to Note
- The approach change in Task 3 reduces the number of new files from 4 to 2
```

## Output

- `.artifacts/implement/{issue-key}/02-plan.md` (updated)
- Source files (only when reconciling already-written changes to a
  user-approved scope decision; not for new feature implementation)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Whether source reconciliation was needed and completed (or confirmed unnecessary)
- Assessment of plan readiness for `/code`

Then return to the invoking workflow router for completion guidance.
