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

If the branch is behind base, check whether a PR has already been
created by looking for `.artifacts/implement/{jira-key}/publish-metadata.json`.

**If no PR exists yet** (pre-publish), offer to rebase:

```bash
git rebase origin/{base}
```

Follow the same conflict handling as the sync-with-base step of `/code`
(stop, show conflicts, offer to resolve, proceed only with user approval).

**If a PR already exists** (post-publish), offer to merge instead:

```bash
git merge origin/{base}
```

Merging preserves the commit history that reviewers have already seen.
Do not rebase a branch that has an open PR — rebasing rewrites commit
SHAs, which requires a force-push, orphans review comments, and
disrupts the reviewer's context.

If the merge has conflicts, stop and report the conflicting files to
the user. Show the conflict markers, offer to resolve, and proceed
only with user approval.

If the user declines either operation, continue but note the staleness
in the validation report.

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
2. Focus on the **new and modified code** specifically — compare the
   coverage report's per-function or per-line breakdown against the
   story's diff to isolate new-code coverage from pre-existing code
   in the same package
3. For each public function added or modified:
   - Are all behavioral paths exercised by tests?
   - Are error return paths tested?
   - Are edge cases covered?

If coverage analysis reveals untested behavioral paths in new code:

1. Write additional tests for the missing behaviors
2. Follow the same contract-based testing standards
3. Run the tests to verify they pass
4. Commit following the project's commit format
5. Re-run coverage to confirm improvement

Read the **Minimum new-code coverage** percentage from the Coverage
Tooling section of `01-context.md` (discovered during `/ingest`,
defaults to 90% if the project does not specify one).

If new code coverage through public API tests remains below that
threshold after filling behavioral gaps, **do not write tests that
reach into internals to close the gap.** The default 90% threshold
accommodates a margin for genuinely untestable paths — panic recovery,
hardware error handlers, race condition guards — that exist for safety
but cannot be reliably triggered through a public interface. Coverage
below the threshold signals that the component is too coarse-grained —
too much behavior is hidden behind a narrow API. Escalate to the user:

- Report the current coverage and which code is unreachable through
  public interfaces
- Recommend decomposing the component into smaller units with more
  testable public APIs
- Note this in the validation report as a design concern, not a test
  gap

The user decides whether to decompose (which may require looping back
to `/plan`) or to accept the coverage level as an exception (e.g., a
thin wrapper over an external system).

### Step 5: Regression Check

Verify that the story's changes haven't broken existing functionality:

1. Run the full unit test suite (not just affected packages)
2. Run the full integration test suite (if applicable)
3. Check for any test failures unrelated to the story

If regressions are found:
- Diagnose whether the story's changes caused them
- Fix regressions caused by the story, commit separately
- Note pre-existing failures in the validation report

### Step 6: Code Quality Review

After automated checks pass, review the story's changes for issues that
automated tooling does not catch. Read the base branch from the `## Branch`
section of `02-plan.md`, then diff against it:

```bash
git diff {base}..HEAD
```

Evaluate each area below. Only flag concrete findings — do not pad with
generic observations.

**Security**

- No hardcoded secrets, tokens, API keys, or credentials in the diff
- Input validation on all external or user-facing data
- Error messages don't leak sensitive information (stack traces, internal
  paths, credentials)
- No injection vectors (SQL, command, path traversal) introduced

**Performance**

- No unnecessary allocations in hot paths
- Loops bounded — no unbounded iteration over external data
- Resource cleanup: connections, file handles, channels properly closed
- Concurrent work exits cleanly — no leaked goroutines, threads, or async tasks

**Backward Compatibility**

- Does the change modify any public APIs, error formats, configuration
  options, or wire protocols?
- If so, is it backward-compatible, or is the breaking change documented
  and justified?
- Could this change be reverted without leaving the system in an
  inconsistent state?

**Completeness Across Call Sites**

- If the story introduces a guard, wrapper, or handling pattern in one
  location, search the codebase for similar patterns that need the same
  treatment
- A pattern applied to 7 of 8 identical call sites is itself a bug

If this review surfaces issues:

1. Fix issues caused by the story's changes, commit each fix separately
2. Note pre-existing issues in the validation report (do not fix them)

### Step 7: Acceptance Criteria Verification

After automated checks and code quality review, verify that every
acceptance criterion from the story has been satisfied. This is the
workflow's primary contract — the acceptance criteria are what the story
promises to deliver, and this is the last gate before publishing.

1. Read the **Acceptance Criteria** from `01-context.md`
2. Read the **Acceptance Criteria Coverage** matrix from `02-plan.md`
   to see which tasks were mapped to each criterion
3. For each acceptance criterion:
   - **Trace to implementation:** Is there code that implements this
     criterion? Follow the task mapping — check that the task is marked
     Done and that the corresponding code exists.
   - **Trace to tests:** Is there at least one test that verifies this
     criterion's behavior through a public interface? The test should
     fail if the criterion were not implemented.
   - **Assess satisfaction:** Based on the implementation and tests,
     is the criterion fully satisfied, partially satisfied, or not
     addressed?

Record the result for each criterion. If any criterion is not fully
satisfied:

1. If it's a gap in implementation or tests — fix it, commit the fix,
   and re-run the relevant checks
2. If it's ambiguous whether the criterion is met — flag it to the
   user with your assessment and let them decide
3. If the criterion cannot be verified through automated means (e.g.,
   it requires manual verification or describes a UX quality) — note
   it as "requires manual verification" with an explanation of why

### Step 8: Write Validation Report

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

### Design Concern — Decomposition Needed
{If new code coverage through public API tests is below the minimum
 threshold from the validation profile (default 90%):
 - **Flagged:** Yes
 - **Threshold:** {N}% (from validation profile)
 - **Coverage:** {X}% of new code through public API tests
 - **Unreachable code:** {description of what cannot be reached
   through public interfaces}
 - **Recommendation:** Decompose into smaller components with more
   testable interfaces. Do not write tests that reach into internals.

 If coverage meets or exceeds the threshold: "No decomposition
 concern — public API coverage is sufficient."}

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

## Acceptance Criteria Verification

| AC | Description | Implementation | Tests | Status |
|----|-------------|----------------|-------|--------|
| AC-1 | {brief} | {file:line or commit} | {test file:test name} | {satisfied/partial/not addressed/manual verification} |

{If all satisfied: "All acceptance criteria verified."
 If any gaps: describe what's missing and what was done about it.
 If any require manual verification: list them with rationale.}

## Quality Review Findings

{Findings from the security, performance, backward compatibility, and
 completeness review. Distinguish between:
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

{PASS — all checks pass, coverage is comprehensive, all acceptance
 criteria satisfied, no regressions.
 OR
 FAIL — with explanation of what still needs fixing.}
```

### Step 9: Present Results

Summarize for the user:
- Which checks passed and which failed
- Coverage assessment (behavioral, not numeric)
- Acceptance criteria status (all satisfied, or which ones have gaps)
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
- Acceptance criteria status
- Regression status
- Overall verdict

Then **re-read the controller** (`controller.md`) for next-step guidance.
