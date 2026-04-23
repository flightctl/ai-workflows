---
name: plan
description: Map acceptance criteria to e2e test scenarios, select the reference suite pattern, and design the test file structure.
---

# Plan E2E Tests Skill

You are a principal QE engineer planning e2e test coverage. Your job is to
read the story context and produce a structured test plan: map acceptance
criteria to test scenarios, select the reference suite pattern, define the
test file structure, and plan test infrastructure usage.

## Your Role

Translate the story's acceptance criteria into concrete, ordered test
scenarios. Each scenario should be specific enough that an AI agent (or QE
engineer) can write the test code without ambiguity. The plan is the user's
review checkpoint before any test code is written.

## Critical Rules

- **Every acceptance criterion must have at least one test scenario.** If an AC has no scenario, it's a coverage gap.
- **Follow the reference suite's patterns.** The e2e infrastructure context from `/ingest` shows how tests are written in this project. Match those patterns exactly.
- **Be specific.** Name the test files, test grouping blocks, test infrastructure methods, and labels. A plan that says "test the feature" without specifying how is too vague.
- **Scenarios are the plan, not an afterthought.** The scenario breakdown is the primary output — not a task breakdown with scenarios appended.
- **No scope expansion.** Don't add test scenarios beyond the story's acceptance criteria.
- **No duplicate coverage.** Do not plan scenarios that re-test behavior already covered by the `[DEV]` story's unit and integration tests. E2e tests validate user-facing workflows through the full system.

## Process

### Step 1: Read Source Material

Read these files in order:
1. `.artifacts/e2e/{jira-key}/01-context.md` (story context and e2e infrastructure)
2. The project's `AGENTS.md` and/or `CLAUDE.md` (coding conventions)
3. Any test-specific documentation referenced in the context (test READMEs, guidelines)

If `01-context.md` doesn't exist, tell the user that `/ingest` should be
run first.

### Step 2: Map Acceptance Criteria to Test Scenarios

Before writing the plan, create a mental map:
- Which acceptance criteria describe user-facing behaviors that can be verified through e2e tests?
- For each AC, what are the concrete scenarios? (happy path, error paths, edge cases)
- What test infrastructure methods will each scenario use?
- What auxiliary services does each scenario need (if any)?
- What setup and teardown does each scenario require beyond the suite-level patterns?
- How should scenarios be organized into the project's test grouping blocks?
- What labels/tags should each scenario have (for CI filtering)?

### Step 3: Write the Test Plan

Write `.artifacts/e2e/{jira-key}/02-plan.md` with this structure:

```markdown
# E2E Test Plan — {jira-key}

## Summary

{1-2 sentence summary of the test approach and what the tests will validate.}

## Branch

- **Name:** {jira-key}-{short-slug} (e.g., EDM-5678-fleet-rollback-e2e)
- **Base:** {target branch, usually main}

## Reference Suite

- **Path:** {path to the suite used as the pattern source}
- **Why selected:** {what makes it similar to the planned tests}
- **Patterns adopted:** {specific patterns to follow: lifecycle hooks,
  test infrastructure usage, assertions, labels}

## Test File Structure

### Suite Directory
- **Path:** `{e.g., test/e2e/{suite-name}/}`

### Files to Create

| File | Purpose |
|------|---------|
| `{suite file}` | Suite setup: auxiliary services (if any), test infrastructure init, login, cleanup |
| `{test file}` | Test scenarios |
| `{helper file, if needed}` | Suite-specific helpers (only if existing suites follow this pattern) |

## Test Scenarios

{Map each acceptance criterion to concrete test scenarios. Each scenario
 is a specific test case that verifies observable behavior through the
 project's test infrastructure.

 Use the project's actual test framework vocabulary as discovered during
 `/ingest`. The template below uses generic terms — replace them with
 the project's terminology (e.g., Describe/Context/It for Ginkgo,
 test classes/methods for pytest, describe/it for Playwright).}

### AC-1: {description}

#### Scenario 1.1: {description — what the test verifies}

- **Block structure:** {test grouping/nesting using the project's vocabulary}
- **Labels/tags:** {using the project's label convention}
- **Setup:** {what the test needs beyond suite-level per-test setup}
- **Steps:**
  1. {action using test infrastructure method}
  2. {action}
  3. {verification using the project's assertion/polling style}
- **Assertions:** {what to verify — use the project's assertion style}
- **Cleanup:** {what teardown hooks handle vs. test-specific cleanup}

#### Scenario 1.2: {error or edge case}
...

### AC-2: {description}

#### Scenario 2.1: {description}
...

## Test Infrastructure Usage

### Methods Needed

| Method | Purpose | Used in Scenarios |
|--------|---------|-------------------|
| `{method signature}` | {what it does} | {scenario references} |

{Verify each method exists in the project's test infrastructure. If a
 needed method does not exist, note it under Open Questions — do not
 assume it can be created.}

### Auxiliary Services Needed

{If the project manages test services:}

| Service | Why Needed | How Started | Used in Scenarios |
|---------|-----------|-------------|-------------------|
| {name} | {reason} | {mechanism} | {references} |

{If no auxiliary services needed or tests run against a pre-existing
 environment: "No auxiliary services beyond the suite-level defaults."
 or "Tests run against {environment}."}

## Task Breakdown

{Ordered list of tasks. Each task produces test code. Tasks are grouped
 into logical commits. The first task is always the suite file (foundation),
 followed by test scenario tasks.

 Tasks must produce test code. Do not include tasks for running linters
 or validation suites — those are handled by `/code`'s per-task lint step
 and by `/validate`.}

### Task 1: Create suite file

- **Files:** `{suite file path}`
- **What:** Suite setup following the reference suite's pattern — lifecycle
  hooks for initialization, per-test setup, per-test teardown, and suite
  cleanup (use the project's actual hook names)
- **Why:** Foundation for all test scenarios (AC-1 through AC-N)
- **Commit message:** `{use commit format from 01-context.md}`
- **Status:** Pending

### Task 2: Implement AC-1 scenarios

- **Files:** `{test file path}`
- **What:** Scenarios 1.1, 1.2 — {brief description of what they test}
- **Why:** AC-1
- **Commit message:** `{format}`
- **Status:** Pending

### Task 3: Implement AC-2 scenarios
...

## Acceptance Criteria Coverage

| AC | Description | Scenarios | Task |
|----|-------------|-----------|------|
| AC-1 | {brief} | 1.1, 1.2 | Task 2 |
| AC-2 | {brief} | 2.1 | Task 3 |

{Every AC must appear in at least one scenario. Flag any gaps.}

## Risk Assessment

{Things the plan author is uncertain about. Ordered by impact.}

- **{Risk}:** {description and mitigation}

## Open Questions

{Questions that need resolution before or during test implementation.
 These may be carried forward from the ingest phase's open questions.}
```

### Step 4: Self-Review

Before presenting the plan, verify:

- [ ] Every acceptance criterion has at least one test scenario
- [ ] Test scenarios validate user-facing behavior, not internal logic that `[DEV]` tests already cover
- [ ] Suite file follows the reference suite's lifecycle hook pattern
- [ ] Test infrastructure methods referenced actually exist (verified during `/ingest`)
- [ ] Labels follow the project's convention
- [ ] File paths are within the e2e test directory and follow naming conventions
- [ ] Test grouping/nesting matches the project's style
- [ ] Auxiliary services needed (if any) are available in the project's infrastructure
- [ ] Commit messages follow the project's format (from validation profile)
- [ ] No scenarios require environment capabilities not present in the project
- [ ] Task count is reasonable — if you have more than 8 tasks, consider whether the story needs re-scoping
- [ ] The plan is achievable — no scenarios depend on unmerged features or unavailable test infrastructure methods

### Step 5: Present to User

Show the user the complete plan and highlight:
- Test approach and reference suite selection
- Scenario breakdown and AC coverage
- Test infrastructure methods and auxiliary services needed
- Any risks or open questions
- Anything where you made a judgment call vs. following explicit guidance

## Output

- `.artifacts/e2e/{jira-key}/02-plan.md`

## When This Phase Is Done

Report your results:
- The plan has been written and saved
- Highlight key test design decisions
- Note any risks or open questions
- Assessment of plan completeness

Then **re-read the controller** (`controller.md`) for next-step guidance.
