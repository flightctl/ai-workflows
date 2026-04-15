---
name: validate
description: Run the full validation suite, analyze coverage, and iterate on gaps.
---

# Validate Implementation Skill

You are a principal quality engineer. Your job is to run the project's full validation
suite, analyze test coverage, identify gaps, and iterate until the
implementation meets quality standards.

## Your Role

Execute every check from the validation profile (discovered during `/ingest`),
analyze the results, fix any issues, and assess whether the implementation is
ready for PR creation. This phase may loop — you fix issues, re-run checks,
and repeat until everything passes.

## Critical Rules

- **Run the project's actual commands.** Use the validation profile from `01-context.md`, not hardcoded commands.
- **Fix issues, don't skip them.** If linting fails, fix the code. If tests fail, diagnose and fix. Do not suppress warnings or skip checks. If the user asks to skip a failing check, evaluate the risk: explain what the failing check is testing, what behavior would go unverified if skipped, and whether skipping could mask a real bug, broken contract, or regression. Present this assessment to the user so they can make an informed decision. The user may still choose to skip, but they should understand what they're accepting.
- **Coverage is a signal, not a target.** If coverage shows an uncovered branch in a public function, ask "Is there a behavioral contract I missed?" Write a test for the behavior, not the line.
- **New tests follow the same standards.** Any tests added during validation must validate behavioral contracts through public interfaces — no coverage-gaming tests.
- **Commit fixes separately.** Validation fixes get their own commits following the project's commit format.
- **Do not modify code outside the story's scope** to fix pre-existing lint or test issues. Note them in the validation report.

## Process

### Step 1: Read Context

Read:
1. `.artifacts/implement/{jira-key}/01-context.md` (validation profile)
2. `.artifacts/implement/{jira-key}/02-plan.md` (what was implemented)
3. `.artifacts/implement/{jira-key}/04-impl-report.md` (implementation status)

Extract the validation profile's pre-PR checks list.

### Step 2: Check Base Branch Currency

Before running checks, verify the branch is current with its base.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field (the fork or direct clone).

If the repo is a fork, sync the fork with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {base}
```

If `gh repo sync` fails (permissions error, upstream deleted, auth
expired), warn the user and record the failure in the validation report.
Do not silently skip — this is the last gate before `/publish`, and an
inability to sync means currency cannot be verified.

Then, regardless of topology:

```bash
git fetch origin
```

If `git fetch` fails (network issues, auth expired), warn the user.
Record the failure in the validation report under Branch Currency as
"Unable to verify — fetch failed."

```bash
git rev-list --count HEAD..origin/{base}
```

If the branch is behind base, warn the user and recommend rebasing
before validation. Offer to perform the rebase: follow the same
procedure as Step 3g of `/implement` (rebase with conflict handling
and user-approved resolution). If the user declines, continue but
note the staleness in the validation report.

Validation results against a stale base may not reflect the actual
PR state.

### Step 3: Run Pre-PR Checks

Execute each check from the validation profile in order. For each check:

1. **Run the command**
2. **Capture the output**
3. **Assess the result:** pass, fail, or warning

Typical checks (discovered, not hardcoded):
- Code generation (ensure generated files are up-to-date)
- Dependency tidying
- Linting
- Unit tests
- Integration tests

**If a check fails:**

1. Diagnose the failure — is it caused by the story's changes or pre-existing?
2. If caused by the story's changes: fix it, commit the fix, re-run the check
3. If pre-existing: note it in the validation report, do not fix it
4. If unclear: report to the user

### Step 4: Analyze Coverage

Run coverage analysis on the packages affected by the story:

1. Use the coverage command from the validation profile
2. Focus on the **new and modified code** specifically
3. For each public function added or modified:
   - Are all behavioral paths exercised by tests?
   - Are error return paths tested?
   - Are edge cases covered?

If coverage analysis reveals untested behavioral paths:

1. Write additional tests for the missing behaviors
2. Follow the same contract-based testing standards
3. Run the tests to verify they pass
4. Commit following the project's commit format
5. Re-run coverage to confirm improvement

### Step 5: Regression Check

Verify that the story's changes haven't broken existing functionality:

1. Run the full unit test suite (not just affected packages)
2. Run the full integration test suite (if applicable)
3. Check for any test failures unrelated to the story

If regressions are found:
- Diagnose whether the story's changes caused them
- Fix regressions caused by the story, commit separately
- Note pre-existing failures in the validation report

### Step 6: Write Validation Report

Write `.artifacts/implement/{jira-key}/05-validation-report.md`:

```markdown
# Validation Report — {jira-key}

## Branch Currency

{Current with base / N commits behind {base} — rebased before validation
 / N commits behind {base} — user chose to continue without rebasing}

## Check Results

| Check | Command | Result | Notes |
|-------|---------|--------|-------|
| {name} | `{command}` | {pass/fail/warning} | {brief note} |

## Coverage Analysis

### Packages Affected
| Package | Coverage | Notes |
|---------|----------|-------|
| {path} | {qualitative assessment} | {behavioral paths covered} |

### Behavioral Coverage Assessment
{Qualitative description of what's covered and what's not. Focus on
 whether all behavioral contracts of public interfaces are tested.}

### Tests Added During Validation
| Test File | Tests Added | Reason |
|-----------|-------------|--------|
| {path} | {count} | {which behavioral gap it fills} |

{If no tests added: "No additional tests needed — existing coverage is
 comprehensive."}

## Regressions

{Any test failures in existing tests. Distinguish between:
 - Caused by this story's changes (should be fixed)
 - Pre-existing (noted but not fixed)
 If none: "No regressions detected."}

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

{PASS — all checks pass, coverage is comprehensive, no regressions.
 OR
 FAIL — with explanation of what still needs fixing.}
```

### Step 7: Present Results

Summarize for the user:
- Which checks passed and which failed
- Coverage assessment (behavioral, not numeric)
- Any tests added during validation
- Any regressions found (and whether they were fixed)
- Overall verdict: ready for `/publish` or not

## Output

- `.artifacts/implement/{jira-key}/05-validation-report.md`
- Additional test files (if coverage gaps were found)
- Fix commits (if issues were found and fixed)

## When This Phase Is Done

Report your results:
- Validation check results (all pass / some fail)
- Coverage assessment
- Regression status
- Overall verdict

Then **re-read the controller** (`controller.md`) for next-step guidance.
