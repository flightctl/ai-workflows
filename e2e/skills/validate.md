---
name: validate
description: Run e2e tests, check for anti-patterns, verify scenario coverage, and assess PR readiness.
---

# Validate E2E Tests Skill

You are a principal QE engineer reviewing test quality. Your job is to run
the e2e tests, check for test anti-patterns, verify scenario coverage
against acceptance criteria, and assess whether the tests are ready for
PR creation.

## Your Role

Execute the e2e tests, analyze the test code for anti-patterns, verify
that every acceptance criterion is covered by a test scenario, and iterate
until quality standards are met. This phase may loop — you fix issues,
re-run checks, and repeat until everything passes.

## Critical Rules

- **Run the project's actual commands.** Use the validation profile from `01-context.md`, not hardcoded commands.
- **Fix issues, don't skip them.** If linting fails, fix the code. If tests fail, diagnose and fix. If the user asks to skip a failing check, evaluate the risk: explain what the failing check is testing, what would go unverified if skipped, and whether skipping could mask a real problem. Present this assessment so the user can make an informed decision.
- **Anti-patterns are defects.** Hardcoded sleeps, brittle selectors, missing cleanup, and test infrastructure bypass are test quality issues that will cause flaky tests in CI. Fix them.
- **Commit fixes separately.** Validation fixes get their own commits following the project's commit format.
- **Do not modify code outside the story's scope** to fix pre-existing lint or test issues. Note them in the validation report.

## Process

### Step 1: Read Context

Read:
1. `.artifacts/e2e/{jira-key}/01-context.md` (validation profile and e2e infrastructure)
2. `.artifacts/e2e/{jira-key}/02-plan.md` (what was planned)
3. `.artifacts/e2e/{jira-key}/04-impl-report.md` (implementation status)

Extract the validation profile's pre-PR checks list and the e2e test
execution command.

### Step 2: Check Base Branch Currency

Before running checks, verify the branch is current with its base.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field.

If the repo is a fork, sync the fork with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {base}
```

If `gh repo sync` fails, warn the user and record the failure in the
validation report. Do not silently skip — this is the last gate before
`/publish`.

Then, regardless of topology:

```bash
git fetch origin
```

If `git fetch` fails, warn the user. Record the failure in the validation
report under Branch Currency as "Unable to verify — fetch failed."

```bash
git rev-list --count HEAD..origin/{base}
```

If the branch is behind base, check whether a PR has already been
created by looking for `.artifacts/e2e/{jira-key}/publish-metadata.json`.

**If no PR exists yet**, offer to rebase:

```bash
git rebase origin/{base}
```

Follow the same conflict handling as the sync-with-base step of `/code`
(stop, show conflicts, offer to resolve, proceed only with user approval).

**If a PR already exists**, offer to merge instead:

```bash
git merge origin/{base}
```

If the user declines either operation, continue but note the staleness
in the validation report.

### Step 3: Run Pre-PR Checks

Execute each check from the validation profile in order. For each check:

1. **Run the command**
2. **Capture the output**
3. **Assess the result:** pass, fail, or warning

Typical checks for e2e test code (discovered, not hardcoded):
- Linting (on the test files)
- E2e test execution (scoped to the new suite)

**If a check fails:**

1. Diagnose the failure — is it caused by the new test code or pre-existing?
2. If caused by the new test code: fix it, commit the fix, re-run the check
3. If pre-existing: note it in the validation report, do not fix it
4. If the test is correct but the feature behaves differently than the AC
   describes: this is a feature defect, not a test bug. Mark the test as
   xfail or skip with a reason referencing the AC, note the defect in the
   validation report, and continue. Do not fix the feature implementation —
   that is a [DEV] scope issue (see deviation rules in `/code`).
5. If unclear: report to the user

### Step 4: Anti-Pattern Check

Read the base branch from the `## Branch` section of `02-plan.md`.
Then read the diff of all new test files:

```bash
git diff {base}..HEAD -- {test file paths from the plan}
```

Focus on the test files created or modified by this story — ignore
unrelated changes in the diff.

Check for each anti-pattern. For each finding, fix the issue, commit,
and re-run the affected tests.

| Anti-Pattern | How to Detect | Fix |
|---|---|---|
| **Hardcoded sleeps** | Fixed delay calls (e.g., `time.Sleep()` in Go, `asyncio.sleep()` in Python, `page.waitForTimeout()` in Playwright) used to wait for system state | Replace with the project's async polling/retry mechanism (e.g., Eventually in Ginkgo, polling helpers in pytest, expect with toPass in Playwright) |
| **Brittle selectors** | Hardcoded element IDs, CSS classes, XPath (UI tests) | Use semantic locators: roles, labels, text content, test infrastructure methods |
| **Order-dependent tests** | Tests that reference state created by a prior test in the same file (not in per-test setup). Detection heuristic: check whether any test case references a variable that is assigned in a prior test case rather than in the per-test setup hook | Make each test independent — create needed state in the test or per-test setup hook |
| **Shared mutable state** | Package-level variables mutated by tests, global state without per-test reset. Detection heuristic: look for variables declared outside test functions that are assigned inside test cases without per-test reinitialization in the per-test setup hook | Use per-test state via test infrastructure, test context, or local variables |
| **Missing cleanup** | Resources created in tests without corresponding cleanup in teardown hooks or defer | Add cleanup matching the reference suite's pattern |
| **Test infrastructure bypass** | Direct HTTP calls, CLI exec, or API client instantiation instead of using the project's test abstractions | Replace with the project's test infrastructure methods |
| **Missing labels** | Test blocks without CI-filtering labels/tags | Add labels/tags following the project's convention |
| **Hardcoded values** | Inline timeout durations, polling intervals, resource names instead of constants | Use the project's test utility constants |
| **Missing async polling** | Direct assertions on results of async operations (no polling/retry) | Wrap in the project's async polling mechanism with appropriate timeout and polling interval |
| **Missing failure diagnostics** | No log collection or diagnostic output when tests fail | Add diagnostic output in teardown hooks (matching reference suite pattern) |

If no anti-patterns are found, record "No anti-patterns detected" in the
validation report.

### Step 5: Regression Check

Verify that the new test suite doesn't interfere with existing tests:

1. If the project has a "sanity" or "smoke" label filter, run that subset
   as a fast check
2. If no fast subset exists, run the e2e tests for adjacent suites (suites
   in the same feature area) to check for interference
3. Check for test isolation issues: verify that the suite-level teardown
   cleans up all resources created by suite-level setup. Compare
   against the reference suite's cleanup pattern. Ensure the new suite
   does not leave state (running services, created resources, modified
   configuration) that could affect other suites.

If regressions are found:
- Diagnose whether the new test code caused them
- Fix regressions caused by the new tests, commit separately
- Note pre-existing failures in the validation report

### Step 6: Code Quality Review

After automated checks pass, review the new test code for issues that
automated tooling does not catch. Read the base branch from the `## Branch`
section of `02-plan.md`, then diff against it:

```bash
git diff {base}..HEAD
```

**Test quality:**
- Do tests actually verify what the AC describes? (not asserting something tangentially related)
- Are assertions specific enough? (not just "no error" — verify the actual outcome)
- Are step annotations (if the project uses them) clear and meaningful?
- Will these tests break only when real behavior changes, not when unrelated details change?

**Maintainability:**
- Are test names descriptive of what they verify?
- Is the test structure consistent with the reference suite?
- Are helper functions used appropriately (not duplicating existing utilities)?

**Safety:**
- No test code that could leak credentials or modify production state
- No test code that creates resources without cleanup
- No test code that could interfere with other test suites

If this review surfaces issues:

1. Fix issues in the new test code, commit each fix separately
2. Note pre-existing issues in the validation report (do not fix them)

### Step 7: Acceptance Criteria Verification

After automated checks and code quality review, verify that every
acceptance criterion from the story has been covered by a test scenario.
This is the workflow's primary contract.

1. Read the **Acceptance Criteria** from `01-context.md`
2. Read the **Acceptance Criteria Coverage** matrix from `02-plan.md`
3. For each acceptance criterion:
   - **Trace to test scenario:** Is there a test that exercises this
     criterion's behavior? Follow the task mapping —
     check that the task is marked Done and that the corresponding test
     code exists.
   - **Verify the test runs:** Does the test pass when executed?
   - **Assess coverage:** Is the criterion fully covered by the test
     scenarios, partially covered, or not addressed?

Record the result for each criterion. If any criterion is not fully
covered:

1. If it's a gap in test scenarios — write the missing test, commit,
   and re-run
2. If it's ambiguous whether the criterion is covered — flag it to the
   user with your assessment
3. If the criterion cannot be verified through e2e tests (e.g., it
   describes internal behavior or a non-functional requirement that
   requires manual measurement) — note it as "not e2e-testable" with
   an explanation of why

### Step 8: Write Validation Report

Write `.artifacts/e2e/{jira-key}/05-validation-report.md`:

```markdown
# Validation Report — {jira-key}

## Branch Currency

{Current with base / N commits behind {base} — rebased before validation
 / N commits behind {base} — user chose to continue without rebasing}

## Check Results

| Check | Command | Result | Notes |
|-------|---------|--------|-------|
| {name} | `{command}` | {pass/fail/warning} | {brief note} |

## Anti-Pattern Check

| Anti-Pattern | Found | Fixed | Notes |
|---|---|---|---|
| Hardcoded sleeps | {yes/no} | {yes/n/a} | {details} |
| Brittle selectors | {yes/no} | {yes/n/a} | {details} |
| Order-dependent tests | {yes/no} | {yes/n/a} | {details} |
| Shared mutable state | {yes/no} | {yes/n/a} | {details} |
| Missing cleanup | {yes/no} | {yes/n/a} | {details} |
| Test infrastructure bypass | {yes/no} | {yes/n/a} | {details} |
| Missing labels | {yes/no} | {yes/n/a} | {details} |
| Hardcoded values | {yes/no} | {yes/n/a} | {details} |
| Missing async polling | {yes/no} | {yes/n/a} | {details} |
| Missing failure diagnostics | {yes/no} | {yes/n/a} | {details} |

{If no anti-patterns found: "No anti-patterns detected."}

## Regressions

{Any test failures in existing tests. Distinguish between:
 - Caused by the new test code (should be fixed)
 - Pre-existing (noted but not fixed)
 If none: "No regressions detected."}

## Acceptance Criteria Verification

| AC | Description | Test Scenario | Test File | Status |
|----|-------------|--------------|-----------|--------|
| AC-1 | {brief} | {scenario name} | {file:line} | {covered/partial/not addressed/not e2e-testable} |

{If all covered: "All acceptance criteria verified."
 If any gaps: describe what's missing and what was done about it.
 If any not e2e-testable: list them with rationale.}

## Quality Review Findings

{Findings from the test quality, maintainability, and safety review.
 Distinguish between:
 - Issues fixed during validation (with commit hashes)
 - Pre-existing issues noted but not fixed
 If none: "No quality review findings."}

## Pre-existing Issues

{Lint warnings, test failures, or other issues that existed before this
 story and were not fixed. If none: "No pre-existing issues observed."}

## Validation Commits

| Hash | Message |
|------|---------|
| {short hash} | {commit message} |

{If no validation commits: "No additional commits needed during
 validation."}

## Result

{PASS — all checks pass, no anti-patterns, all acceptance criteria
 covered, no regressions.
 OR
 FAIL — with explanation of what still needs fixing.}
```

### Step 9: Present Results

Summarize for the user:
- Which checks passed and which failed
- Anti-pattern check results (clean or what was fixed)
- Acceptance criteria coverage (all covered, or which ones have gaps)
- Any regressions found (and whether they were fixed)
- Overall verdict: ready for `/publish` or not

## Output

- `.artifacts/e2e/{jira-key}/05-validation-report.md`
- Additional test fixes (if anti-patterns or gaps were found)
- Fix commits (if issues were found and fixed)

## When This Phase Is Done

Report your results:
- Validation check results (all pass / some fail)
- Anti-pattern check results
- Acceptance criteria coverage
- Regression status
- Overall verdict

Then **re-read the controller** (`controller.md`) for next-step guidance.
