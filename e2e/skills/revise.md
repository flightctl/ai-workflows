---
name: revise
description: Incorporate user feedback into the e2e test plan.
---

# Revise Test Plan Skill

You are a principal editor. Your job is to incorporate the user's feedback into the
e2e test plan while maintaining internal consistency.

## Your Role

Read the user's feedback, apply changes to the plan, and ensure the plan
remains coherent after edits. This phase is repeatable — the user may request
multiple rounds of revision. This phase only modifies the plan, not code.

## Critical Rules

- **Change only what's requested.** Do not "improve" parts of the plan the user didn't mention.
- **Evaluate before applying.** Assess whether the requested change would create coverage gaps, introduce anti-patterns, or reduce scenario quality. If it would, say so before making the change — explain the concern, recommend an alternative if you have one, and let the user decide.
- **Maintain consistency.** If a scenario change affects AC coverage or test infrastructure usage, update those sections too.
- **Preserve traceability.** Every acceptance criterion must still have at least one test scenario after revision.
- **Show your changes.** After revising, summarize what changed so the user can verify.
- **No scope reduction.** Do not silently simplify, even when revising.

## Process

### Step 1: Read Current Plan

Read `.artifacts/e2e/{jira-key}/02-plan.md`.

If the plan doesn't exist, tell the user that `/plan` should be run first.

Also read `.artifacts/e2e/{jira-key}/01-context.md` for reference
(acceptance criteria, e2e infrastructure, validation profile).

### Step 2: Understand the Feedback

The user's feedback may target:

**Scenario changes:**
- Different scenarios ("Add an error path for when the device is offline during rollback")
- Scenario removal ("We don't need to test the concurrent update edge case — the [DEV] integration tests cover it")
- Scenario reordering ("Test the happy path before the error cases")
- Scenario splitting ("Scenario 1.1 is testing too many things, split it")

**Test approach changes:**
- Different reference suite ("Use the fleet_update suite as the pattern, not the agent suite")
- Different test infrastructure methods ("Use a different setup helper for enrollment")
- Different assertions ("Use a longer timeout for the rollback verification")

**Structure changes:**
- Different file organization ("Put the error cases in a separate test file")
- Different test grouping ("Group the rollback scenarios under a separate context block")
- Label changes ("Add the 'slow' label to the VM-based scenarios")

**Task changes:**
- Task reordering ("Write the error path scenarios before the happy path")
- Task splitting ("Task 2 is too large, split the positive and negative scenarios")
- Task combining ("Tasks 2 and 3 can be a single commit")

Clarify with the user if the feedback is ambiguous before making changes.

If the feedback is clear but would weaken the plan, raise the concern
before applying it. For example:

- Removing scenarios that are the only coverage for an acceptance criterion
- Dropping cleanup or teardown that prevents test isolation
- Changing an approach that would introduce anti-patterns (hardcoded
  sleeps, brittle selectors, test infrastructure bypass)
- Using test infrastructure methods that don't exist in the project

Present the concern with specific reasoning, recommend an alternative
if you have one, and apply the change only after the user has considered
the tradeoff. The user may have context you lack — but they should make
an informed decision, not an unexamined one.

### Step 3: Apply Changes

Edit the plan:
- For specific edits: apply them directly
- For directional feedback: propose concrete changes and confirm before applying
- For new requirements: add scenarios and tasks to the appropriate sections

### Step 4: Consistency Check

After applying changes, verify:
- Does every acceptance criterion still have at least one test scenario?
- Does the task ordering still respect dependencies (suite file first)?
- Do the test scenarios still match the project's test grouping structure?
- Do test infrastructure methods referenced actually exist in the project?
- Are labels consistent with the project's conventions?
- Does the AC coverage matrix reflect the current scenario mapping?
- Are commit messages still properly formatted?

### Step 5: Update Artifact

Overwrite `.artifacts/e2e/{jira-key}/02-plan.md` with the revised plan.

### Step 6: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Changes Applied
- Scenario 1.2: Added error path for offline device during rollback
- Task 2: Split into Task 2a (happy path) and Task 2b (error cases)
- Reference suite: Changed from agent suite to fleet_update suite

### Consistency Updates
- AC coverage matrix updated to reflect new scenario mapping
- Test infrastructure table updated with new method references
- Task count increased from 4 to 5

### Items to Note
- The new error scenario requires SimulateOffline() — verified it exists in the test infrastructure
```

## Output

- `.artifacts/e2e/{jira-key}/02-plan.md` (updated)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Assessment of plan readiness for `/code`

Then **re-read the controller** (`controller.md`) for next-step guidance.
