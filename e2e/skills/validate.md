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
that every acceptance criterion is covered by the appropriate method
(automated test scenario, manual TC, or qualification gate), and iterate
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
1. `.artifacts/e2e/{issue-key}/01-context.md` (validation profile and e2e infrastructure)
2. `.artifacts/e2e/{issue-key}/02-plan.md` (what was planned)
3. `.artifacts/e2e/{issue-key}/04-impl-report.md` (implementation status)
4. `.artifacts/e2e/{issue-key}/testplan.md` (story-scoped testplan, if exists)

Extract the validation profile's pre-PR checks list and the e2e test
execution command.

### Step 2: Check Base Branch Currency

Before running checks, verify the branch is current with its base.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field.

If the repo is a fork, sync the fork with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {pr-target}
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
git rev-list --count HEAD..origin/{local-base}
```

Verify the working tree is clean before running any validation,
regardless of branch position relative to base:

```bash
git status --porcelain
```

If output is non-empty, stop and require the user to commit or stash
changes before continuing. Validation must not run against uncommitted
changes — the report binds its result to the current HEAD, and
uncommitted changes would not be covered by that binding.

If the branch is behind base, sync before continuing:

Check whether a PR has already been created by looking for
`.artifacts/e2e/{issue-key}/publish-metadata.json`.

**If no PR exists yet**, offer to rebase:

```bash
git rebase origin/{local-base}
```

Follow the same conflict handling as the sync-with-base step of `/code`
(stop, show conflicts, offer to resolve, proceed only with user approval).

**If a PR already exists**, offer to merge instead:

```bash
git merge origin/{local-base}
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

Read the Local Base from the `## Branch` section of `02-plan.md`.
Then read the diff of all new test files:

```bash
git diff {local-base}...HEAD -- {test file paths from the plan}
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
| **Missing async polling** | Direct assertions on results of async operations without polling/retry (e.g., bare `Expect` without `Eventually` in Ginkgo, bare `assert` without polling in pytest, bare `expect` without `toPass` in Playwright) | Wrap in the project's async polling mechanism with appropriate timeout and polling interval |
| **Missing failure diagnostics** | No log collection or diagnostic output when tests fail (e.g., no diagnostic log capture in Go teardown, no screenshot capture in Playwright `afterEach`, no log dump in pytest teardown) | Add diagnostic output in teardown hooks (matching reference suite pattern) |

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
automated tooling does not catch. Read the Local Base from the `## Branch`
section of `02-plan.md`, then run the self-review gate.

Read and follow `../../_shared/recipes/self-review-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff {local-base}...HEAD` |
| MAX_ROUNDS | `3` |
| CONTEXT_FILES | `.artifacts/e2e/{issue-key}/01-context.md`, `.artifacts/e2e/{issue-key}/02-plan.md` (if they exist) |
| SUPPLEMENTARY_CRITERIA | This is the full-branch validation review for e2e test code. Anti-pattern detection is already complete (Step 4) — skip those checks. Focus on test design depth: (1) **Assertion specificity** — do tests verify the actual behavioral outcome the AC describes, or just assert "no error"? (2) **Brittleness** — will tests break only when real behavior changes, or will they break when unrelated implementation details change? (3) **Test isolation** — could any test leak state (credentials, resources, configuration) that affects other suites or environments? (4) **Reference suite consistency** — does the test structure match the project's reference suite, or does it introduce divergent patterns that will confuse future contributors? |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user before proceeding.

If the gate made code fixes, commit them before continuing:

```bash
git add {fixed files}
```

```bash
git commit -m "{issue-key}: address validation review findings"
```

### Step 7: Acceptance Criteria Verification

After automated checks and code quality review, verify that every
acceptance criterion from the story has been covered by the appropriate
method from the approved plan. This is the workflow's primary contract.

1. Read the **Acceptance Criteria** from `01-context.md`
2. Read the **Acceptance Criteria Coverage** matrix from `02-plan.md`
3. For each acceptance criterion, check the plan-approved coverage
   method:

   **Automated test scenario:**
   - Trace to test scenario: is there a test that exercises this
     criterion's behavior? Follow the task mapping —
     check that the task is marked Done and that the corresponding test
     code exists.
   - Verify the test runs: does the test pass when executed?
   - Assess coverage: is the criterion fully covered by the test
     scenarios, partially covered, or not addressed?

   **Manual TC (from coverage matrix):**
   - Verify the TC's criteria and required evidence status. Evidence
     that is pending, not started, or unverified does not constitute a
     pass. Failed required criteria means the AC is failed.
   - Do not force an automated test scenario for an AC the plan
     designates as manual verification.

   **Qualification gate (from coverage matrix):**
   - Collect the gate's evidence status now: check whether external
     evidence has been provided for this gate's criteria. Determine
     the evidence status (not-started, pending, verified, or failed)
     from available evidence sources in the current run — do not
     read from a report section that has not yet been written.
     Reuse this same evidence result when writing the report in
     Step 8. Pending or not-started evidence does not constitute a
     pass. Failed required criteria means the AC is failed.
   - Do not force an automated test scenario for an AC the plan
     designates as a qualification gate.

Record the result for each criterion. If any criterion is not fully
covered:

1. If the plan designates an automated scenario and it is missing —
   write the missing test, commit, and re-run
2. If it's ambiguous whether the criterion is covered — flag it to the
   user with your assessment
3. If the criterion is covered by a manual TC or qualification gate —
   verify evidence status as above; do not write a substitute automated
   test

### Step 7b: Test Plan Verification

If `.artifacts/e2e/{issue-key}/testplan.md` exists, independently verify
that every **automatable** test case has been covered by the e2e tests.
Test cases marked with a `Qualification gate` marker in the story
testplan are **not** candidates for e2e test automation — they require
their designated execution environment (e.g., hardware lab, security
audit tooling) and are tracked as external validation evidence, not
automated test coverage. Exclude qualification-gate TCs from the
coverage check; verify they are listed in the validation report's
external evidence section instead.

This check re-derives the required TC ID list from `testplan.md`
directly — it does NOT rely on the plan's task-to-TC-ID mappings or
`/code`'s per-task reconciliation for determining which tests exist.
The only information carried forward from the plan is the N/A rationale
for test cases marked inapplicable. This is an intentional independent
verification: if the
plan's bookkeeping or the code phase's gate drifted from reality, this
step catches it.

If `testplan.md` does not exist and `02-plan.md` has no Test Plan
Coverage section, skip this step entirely. However, if `02-plan.md`
has TC mappings but `testplan.md` is missing, unreadable, or malformed
(no parseable TC IDs and no Qualification Gates section), stop and
report the inconsistency. A gate-only testplan (zero TC IDs but a
`## Qualification Gates` section) is valid only when `02-plan.md`
contains no TC mappings in its Test Plan Coverage section. If TC
mappings remain, stop and report the inconsistency — re-ingest may
have replaced TCs with gates while the plan retains stale mappings.
When consistent, check the testplan's freshness and discovery state
before skipping: if `testplan.md` contains `Freshness: unresolved-source`
or `Source-Discovery: unresolved`, the authority is unknown — report the
unresolved state and do not skip the authority assessment below. If the
testplan is freshly ingested or its freshness is verified/confirmed, skip
the automated coverage check and proceed directly to step 4 below.

**Testplan source authority:** Check the testplan's freshness
marker to determine its authority level. The cases are mutually
exclusive; evaluate in this order:

1. If `testplan.md` contains `Source-Discovery: unresolved` or
   `Freshness: unresolved-source`, the source could not be read or
   resolved during ingest. Report this state as "unresolved
   discovery — source unavailable" in the validation report. Do not
   treat it as confirmed absence or full coverage. AC-based work may
   continue, but unresolved required validation cannot be claimed as
   complete. The overall result cannot be PASS while this state
   persists — clear the unresolved state only upon a successful
   checked discovery (a subsequent `/ingest` that resolves the
   source).

2. If `testplan.md` contains `Freshness: unverified` (or the legacy
   bold form `**Freshness:** unverified`), the testplan was retained
   from a prior ingest. Check whether the Test Plan Coverage section
   in `02-plan.md` records a confirmed status for the TCs.

3. If `testplan.md` contains neither marker (the plan was freshly
   ingested from an authoritative source), its TCs are authoritative
   — verify all automatable TCs have been implemented without
   requiring user confirmation or SHA-256 binding. A stale
   confirmation hash from a prior retained plan does not invalidate
   a freshly ingested authoritative source.

For case 2, check the confirmed status:

- **Confirmed TCs** (plan records user confirmation, confirmed TC
  IDs, and SHA-256 of `.artifacts/e2e/{issue-key}/testplan.md` at
  confirmation time): compute the current SHA-256 of the
  story-scoped testplan (`sha256sum
  .artifacts/e2e/{issue-key}/testplan.md`) and compare against the
  recorded hash. A TC is effectively confirmed only when ALL of:
  (1) the plan records a "confirmed" status with a SHA-256 binding,
  (2) the current story-scoped testplan hash matches the recorded
  hash, and (3) the TC ID appears in the confirmed list. If the
  hash differs, the confirmation is stale — treat as unconfirmed.
  If the binding is missing (no SHA-256 recorded), treat as
  unconfirmed. Write gap-fill tests only for effectively confirmed
  TCs; report TC coverage normally for those.
- **Unconfirmed TCs** (no confirmed status in plan, or missing
  SHA-256 binding, or stale hash): coverage is provisional, not
  normative. Do not write mandatory gap-fill tests. Report as
  "unverified — source testplan not confirmed."

**Non-TC gate confirmation (gate-only testplans).** When a
gate-only testplan has `Freshness: unverified` (case 2) but no
`Source-Discovery: unresolved` marker, the retained qualification
gates also require explicit confirmation before being treated as
mandatory. For each non-TC gate entry, verify:

- The gate's source path and evidence criteria are present and
  legible in the retained testplan.
- The evidence criteria and expected status can be matched against
  the published source (if accessible) or the prior ingest record.
- If the gate's provenance and criteria are confirmed (user
  verification or matching published source), treat it as a
  mandatory gate with its current evidence status (verified,
  pending, or failed).
- If the gate cannot be confirmed (source unavailable, criteria
  unclear, or user declines), treat it as provisional — report its
  status as "unverified gate — retained from prior ingest, not
  confirmed" without forcing mandatory evidence or automated
  replacement.

Do not invent automated gate confirmation or silently treat
unverified gates as authoritative. Carry source freshness honestly
in the validation report.

When the user confirms TCs during validation, record the
confirmation in the Test Plan Coverage section of `02-plan.md`:
set the status to "confirmed — user verified TC applicability on
{date}", list the confirmed TC IDs, and record the SHA-256 of the
current story-scoped testplan bytes (computed as `sha256sum
.artifacts/e2e/{issue-key}/testplan.md`). This persistent record
allows subsequent `/validate` runs to distinguish confirmed TCs
from provisional ones without re-prompting and detects content
changes from re-ingestion.

In both cases, do not block the validation report or AC-based
work.

1. Read `testplan.md` and extract all TC IDs. Separate them into
   three groups:
   - **Automatable TCs** (`Automation: automated` without a
     `[Qualification gate]` marker): verify Preconditions, Steps,
     and Expected Results sections are present. If missing, stop
     and report the testplan as malformed.
   - **Manual verification TCs** (`[Manual verification]` marker):
     verify the TC entry is present. These do not require
     Preconditions/Steps/Expected Results sections (they describe
     human verification procedures).
   - **Qualification gate TCs** (`[Qualification gate]` marker):
     verify the TC entry is present. These do not require
     Preconditions/Steps/Expected Results sections.
2. For each **automatable** TC ID (except those the validate phase
   agrees are legitimately N/A based on the rationale in the plan's
   Test Plan Coverage matrix):
   - Search the e2e test files on the feature branch for a test
     scenario whose validations match the TC's Steps and Expected
     Results.
   - The match is behavioral, not textual — the test must exercise the
     described scenario and assert the described outcomes.
   - Record the test file and scenario name for each TC ID.
3. If any automatable TC ID lacks a corresponding test:
   - If the TC is NOT effectively confirmed (see criteria above:
     hash present + current story-scoped testplan hash matches
     recorded hash + TC ID in confirmed list) AND `testplan.md`
     contains `Freshness: unverified`, report the gap as
     provisional: "TC coverage gap — unconfirmed source, not
     normative until confirmed." Do not gate commits on
     unconfirmed TC gaps.
   - For effectively confirmed TCs or verified-source TCs: write
     the missing test following the reference suite's patterns.
     These TCs are normative — their gaps are real and should be
     filled.
   - Commit the test following the project's commit format.
   - Re-run the relevant checks from Step 3.
   After the last gap-fill commit, re-assess AC coverage and all
   external-evidence applicability on the final candidate HEAD before
   writing the report. A gap-fill commit changes the candidate; the
   earlier assessment may no longer apply. Reuse the Step 7 assessment
   procedure — do not bind a stale assessment to the new HEAD.
4. For manual verification TCs, qualification gate TCs, and non-TC
   qualification gates (from the `## Qualification Gates` section
   of the story testplan — these have no TC IDs), record their
   status in the External Validation Evidence section (see report
   template below).
5. Record results for the validation report.

### Step 8: Write Validation Report

Write `.artifacts/e2e/{issue-key}/05-validation-report.md`:

```markdown
# Validation Report — {issue-key}

## Branch Currency

{Current with base / N commits behind {local-base} — rebased before validation
 / N commits behind {local-base} — user chose to continue without rebasing}

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

## Test Plan Verification

{Include only if testplan.md exists. Omit entirely otherwise.}

| TC ID | Title | Test File | Scenario | Status |
|-------|-------|-----------|----------|--------|
| TC-FR1-01 | {title} | {file} | {scenario name} | covered |
| TC-FR1-02 | {title} | {file} | {scenario name} | gap-filled |
| TC-NFR1-01 | {title} | — | — | N/A |

{Status values:
 - covered: test scenario existed and had sufficient assertion depth
 - gap-filled: test scenario was written during validation
 - N/A: test case legitimately not applicable (rationale required)

 If all automatable TCs are covered: "All automatable test plan cases
 verified." (Qualification-gate and manual-verification TCs are tracked
 separately in External Validation Evidence.)
 If gaps were filled: "{N} test cases required additional tests during
 validation."
 If any N/A: list rationale for each.}

## External Validation Evidence

{Include if testplan.md contains qualification-gate TCs, manual
 verification TCs, or non-TC qualification gates (from the
 `## Qualification Gates` section). Omit entirely if none exist.

 These entries are excluded from the automated coverage check —
 they require a designated execution environment or human
 verification. This section tracks their evidence status
 separately. A pending or failed entry does NOT count as passed.}

| ID | Title | Source | Verification Method | Evidence | Status |
|----|-------|--------|--------------------|---------| -------|
| TC-NFR3-01 | {title} | {testplan.md or companion} | {designated environment} | {link or "pending"} | {not-started / pending / verified / failed} |
| {gate heading} | {gate name} | {source path §section} | {gate type} | {link or "pending"} | {not-started / pending / verified / failed} |

{The ID column uses TC IDs for qualification-gate and manual-
 verification TCs, and gate heading/source reference for non-TC
 gates — do not invent TC IDs for non-TC entries.

 Status values:
 - not-started: no evidence collection has begun
 - pending: evidence collection in progress
 - verified: evidence reviewed and accepted — verification method
   and source criteria compared with the provided evidence
 - failed: evidence shows the requirement is not met

 Before marking any external evidence `verified` (manual TCs,
 qualification-gate TCs, and non-TC gates alike), compare it with
 the entry's verification method and original source criteria, and
 verify the evidence basis applies to the current candidate (build,
 revision, or test run). If the evidence does not address the
 criteria, or if the evidence was collected against a different
 candidate or revision and applicability to the current candidate
 is unknown, keep it `pending`. Record the evidence basis
 (candidate identifier, date) alongside the status. An incomplete
 or inapplicable check must not contribute to an overall PASS.

 If all verified: "All external validation evidence verified."
 If any mandatory entry failed: "N mandatory entries FAILED —
 required evidence shows requirements not met." Overall result
 must be FAIL.
 If any mandatory entry is pending or not-started: "N mandatory
 entries awaiting external evidence — these are not discharged
 by automated test coverage." Overall result cannot be PASS.
 Mandatory entries are: source-verified authoritative TCs,
 effectively confirmed retained TCs, required non-TC qualification
 gates, and all current AC obligations. Unconfirmed provisional
 TCs do not block PASS — report them separately with their
 current evidence status (pending, not-started, or failed).
 A failed provisional entry is informational, not verdict-
 controlling; report it but do not force Overall: FAIL.
 If Source-Discovery is unresolved, Overall result cannot be PASS
 regardless of provisional TC exemptions.}

## Quality Review Findings

{Findings from the code quality review gate (protocol criteria plus
 e2e-specific supplementary criteria). Distinguish between:
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

## Validated Identity

Record after the last code commit during validation, before
writing the final result:

- **Branch HEAD:** {full 40-character SHA of the branch HEAD}
- **Context SHA-256:** {SHA-256 of `.artifacts/e2e/{issue-key}/01-context.md`,
  or "absent" if no context file exists}
- **Plan SHA-256:** {SHA-256 of `.artifacts/e2e/{issue-key}/02-plan.md`,
  or "absent" if no plan file exists}
- **Testplan SHA-256:** {SHA-256 of `.artifacts/e2e/{issue-key}/testplan.md`
  at validation time, or "absent" if no testplan}

{This section binds the validation result to the specific candidate
 code and input artifacts that were validated. The publish step
 compares these against current inputs to detect stale reports —
 a re-ingest, branch change, AC change, or gate addition
 invalidates the old PASS. Legacy reports without this section
 require re-validation.}

## Result

{Automated e2e coverage: PASS / FAIL — whether all automatable TC IDs
 have passing tests, no anti-patterns, and no regressions.

 External validation: COMPLETE / PENDING / FAILED / NOT STARTED —
 whether all manual verification, qualification gate, and non-TC
 gate evidence has been provided and accepted.

 Write `Overall: PASS` on its own line only when ALL of:
 (1) all acceptance criteria pass their approved verification
     method (automated scenario, manual TC, or qualification
     gate — as determined in Step 7),
 (2) all confirmed automatable TC IDs have passing tests with no
     anti-patterns or regressions,
 (3) all confirmed external validation entries (manual TCs and
     qualification gates) are verified.
 Unconfirmed TCs (from an unverified or unconfirmed testplan) are
 provisional — report them separately and exclude them from
 mandatory pass checks. An unconfirmed TC gap does not block
 Overall: PASS, but must be reported as provisional coverage.
 A failed or pending confirmed entry, an AC without approved
 coverage, or an unresolved Source-Discovery state always blocks
 Overall: PASS. Required non-TC qualification gates are mandatory
 and never exempt from the PASS criteria.
 Other outcomes:
 - If automated tests pass but mandatory entries are pending/
   not-started: "PASS (automated) — awaiting external validation
   for {N} mandatory entries." Overall is NOT PASS.
 - If any mandatory entry has FAILED evidence: "FAIL — external
   validation failed for {entry names}." Overall is FAIL.
 - If automated tests fail: "FAIL — automated tests failed."
 Follow the project's existing gating policy for merge readiness.
 Do not claim acceptance passed when evidence is outstanding,
 unverified, or failed.

 The report MUST end with an explicit verdict line on its own line:
 `Overall: PASS`, `Overall: FAIL`, or the qualified form above.
 `/publish` requires this exact line to determine readiness.}
```

### Step 9: Present Results

Summarize for the user:
- Which checks passed and which failed
- Anti-pattern check results (clean or what was fixed)
- Acceptance criteria coverage (all covered, or which ones have gaps)
- Test plan verification status (all automatable TCs covered / gaps
  filled / not applicable), if testplan exists — distinguish
  automatable coverage from overall readiness
- External validation evidence status: how many mandatory entries are
  verified, pending, not-started, or failed — these are not discharged
  by automated test coverage. Report provisional entries separately.
- Any regressions found (and whether they were fixed)
- Overall verdict: the `Overall:` line from the report (PASS only
  when both automated coverage and all mandatory external evidence
  are verified; otherwise state the specific gap)

## Output

- `.artifacts/e2e/{issue-key}/05-validation-report.md`
- Additional test fixes (if anti-patterns or gaps were found)
- Fix commits (if issues were found and fixed)

## When This Phase Is Done

Report your results:
- Validation check results (all pass / some fail)
- Anti-pattern check results
- Acceptance criteria coverage
- Regression status
- Overall verdict

Then return to the invoking workflow router for completion guidance.
