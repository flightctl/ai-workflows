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

### Scope-First Remediation Policy

This policy applies to every remediation action in Steps 4–8b, including
fixes proposed by the self-review gate's external-tool path (shared
recipe Step 1) and subagent/inline path (Steps 2–3). Before applying
any proposed fix — code edit, new test, or commit — assess whether it
stays within the approved Scope Baseline in `02-plan.md` (when present):

- **In-scope fix** (correctness, regression, coverage for code within
  baseline boundaries): apply using the existing step's behavior.
- **Material scope expansion** (fix would modify interfaces, components,
  or files outside baseline boundaries, or add substantial unplanned
  structural work): classify as blocking HIGH. Immediately record a
  `## Pending Scope Decision` section in `02-plan.md` with the delta,
  necessity, affected boundaries, and keep/extract/defer options. Stop
  the current step — do not apply the fix, commit, write or overwrite
  `05-validation-report.md`, or advance to later steps. Recommend
  `/revise`. Preserve valid in-scope work already committed.

For the self-review gate invocation (Step 7): only use a non-interactive
review tool (shared recipe Step 1) in non-mutating / findings-only
mode. If the tool cannot report findings without editing code, fall
back to the subagent or inline path (shared recipe Step 2). The review
tool or subagent produces findings; this validation caller consumes
and assesses them for scope before applying any fixes. The shared
recipe's caller-assessment path (Step 1) and inline-fix path (Step 3)
both return findings to the caller for this assessment. Approved
in-scope fixes are applied and re-reviewed through the bounded post-fix
cycle. Material unapproved scope findings remain unfixed HIGH → FLAG →
complete record → `/revise`. Optional unrelated nits can be declined
per existing value assessment.

Plans without a Scope Baseline skip this assessment — the existing
step-level remediation behavior applies unchanged.

### Step 1: Read Context and Check Entry Conditions

Read:
1. `.artifacts/implement/{issue-key}/02-plan.md` — check whether it
   contains a `## Pending Scope Decision` section or records an unmerged
   prerequisite dependency. If either condition holds, stop and recommend
   `/revise` — do not run checks, commit fixes, or write the validation
   report.
2. `.artifacts/implement/{issue-key}/01-context.md` (validation profile)
3. `.artifacts/implement/{issue-key}/04-impl-report.md` (implementation status)
4. `.artifacts/implement/{issue-key}/testplan.md` (story-scoped testplan, if exists)

Extract the validation profile's pre-PR checks list.

### Step 2: Check Base Branch Currency

Before running checks, verify the branch is current with its base.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field (the fork or direct clone).

If the repo is a fork, sync the fork with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {pr-target}
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
git rev-list --count HEAD..origin/{local-base}
```

If the branch is behind base, check whether a PR has already been
created by looking for `.artifacts/implement/{issue-key}/publish-metadata.json`.

**If no PR exists yet** (pre-publish), offer to rebase:

```bash
git rebase origin/{local-base}
```

Follow the same conflict handling as the sync-with-base step of `/code`
(stop, show conflicts, offer to resolve, proceed only with user approval).

**If a PR already exists** (post-publish), offer to merge instead:

```bash
git merge origin/{local-base}
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

### Step 3: Resolve Local Base and Verify Clean Worktree

Read the Local Base from the `## Branch` section of `02-plan.md`.
Verify the ref resolves:

```bash
git rev-parse --verify {local-base}
```

If the ref is missing, unresolvable, or the command fails, stop —
report the error with details. Do not substitute an empty diff, skip
the review, or invent a replacement base. The base must be repaired
(e.g., fetch the missing ref) before validation can continue.

Verify the worktree is clean:

```bash
git status --porcelain --untracked-files=normal
```

If the command fails (non-zero exit), stop and report the error — do
not assume an empty result means clean. Otherwise, ignore paths under
`.artifacts/` (workflow working state, gitignored). If any other
modified, staged, or untracked implementation files remain, stop —
report the affected paths. Do not auto-commit, stash, reset, or delete
them. The implementation must be completed and committed through normal
`/code` or user-approved `/revise` handling before rerunning `/validate`.

### Step 4: Run Pre-PR Checks

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

### Step 5: Analyze Coverage

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

### Step 6: Regression Check

Verify that the story's changes haven't broken existing functionality:

1. Run the full unit test suite (not just affected packages)
2. Run the full integration test suite (if applicable)
3. Check for any test failures unrelated to the story

If regressions are found:
- Diagnose whether the story's changes caused them
- Fix regressions caused by the story, commit separately
- Note pre-existing failures in the validation report

### Step 7: Code Quality Review

After automated checks pass, review the story's full diff for issues
that automated tooling does not catch.

Re-run Step 3 (resolve Local Base, verify clean worktree) before
proceeding — Steps 4–6 may have committed fixes that changed HEAD or
left the worktree dirty. Stop on any failure per Step 3's rules.

If `02-plan.md` has a Scope Baseline section, compare the branch diff
(`git diff {local-base}...HEAD`) against all baseline fields: Intended
Feature Changes, Known Supporting Refactoring (including Prerequisite
Rationale), Affected Interfaces and Components, and Expected Delivery
Boundaries. If the comparison command fails, stop and report the error.
Material unapproved work outside any baseline field — including
unapproved new behavior within an already-affected component — is
scope drift: record a complete `## Pending Scope Decision` per the
Scope-First Remediation Policy and stop. Recommend `/revise`. Ordinary
in-scope correctness fixes and small cohesive supporting cleanup within
baseline boundaries do not trigger this check.

Run the self-review gate. Read and follow
`../../_shared/recipes/self-review-gate.md` with these parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff {local-base}...HEAD` |
| MAX_ROUNDS | `3` |
| CONTEXT_FILES | `.artifacts/implement/{issue-key}/01-context.md`, `.artifacts/implement/{issue-key}/02-plan.md` (if they exist) |
| SUPPLEMENTARY_CRITERIA | Full-branch validation review — last quality gate before PR. Evaluate: (1) **Backward compatibility** — public APIs, error formats, configuration, wire protocols changed? Backward-compatible or is the break documented and justified? (2) **Completeness across call sites** — pattern applied in one location but needed in similar locations is a bug. (3) **Scope baseline compliance** — if `02-plan.md` has a Scope Baseline section, compare against all baseline fields (Intended Feature Changes, Known Supporting Refactoring, Affected Interfaces and Components, Expected Delivery Boundaries). Material unapproved work outside any field — including unapproved new behavior within an already-affected component — is HIGH scope drift; do not auto-fix, report unfixed so gate returns FLAG. Ordinary correctness fixes and small cohesive supporting cleanup within boundaries are not scope drift. A pending scope decision already in the plan must be resolved before publishing. |

If the gate reports FLAG, stop and present findings. For scope-drift
FLAG findings, record a complete `## Pending Scope Decision` in
`02-plan.md` per the Scope-First Remediation Policy and recommend
`/revise`.

If the gate made code fixes (the gate edits but does not commit —
shared recipe lines 174-176): re-run affected Step 4 pre-PR checks,
Step 5 coverage analysis when fixes touch covered packages, and full
Step 6 regression check when fixes change production code. Then commit.
After committing, re-run Step 3 (clean worktree, base), the scope
comparison, and the self-review gate on the new committed HEAD. This
re-run consumes remaining rounds from the original MAX_ROUNDS budget —
do not reset the counter. The cycle ends successfully only when the
committed clean HEAD passes re-review without further code fixes. If
MAX_ROUNDS is exhausted before a clean pass, stop with FLAG — do not
write the validation report or advance to Step 8.

The validation report (Step 9) must reflect the final committed and
reviewed HEAD.

### Step 8: Acceptance Criteria Verification

After automated checks and code quality review, verify that every
acceptance criterion from the story has been satisfied. This is the
workflow's primary contract — the acceptance criteria are what the story
promises to deliver, and this is the last gate before publishing.

1. Read the **Acceptance Criteria** from `01-context.md`
2. Read the **Acceptance Criteria Coverage** matrix from `02-plan.md`
   to see which tasks were mapped to each criterion
3. For each acceptance criterion, read the **Method** and **Evidence
   Reference** columns from the AC coverage matrix to determine the
   approved verification method and the recorded reference for
   locating evidence. Do not infer the method from which tests
   passed — use the planned method to select the verification path:
   - **automated-test:** Trace to implementation (code exists, task
     Done) and trace to tests (at least one test verifies this
     criterion's behavior through a public interface and would fail
     if the criterion were not implemented).
   - **manual-test:** Use the recorded **Evidence Reference** to
     locate and assess the manual verification evidence (see the
     evidence-status rule in the unsatisfied-criterion list below).
     If the reference is missing or unusable, ask the user for
     clarification rather than guessing from available sources.
     A passing automated test does not satisfy a criterion whose
     approved method is manual-test.
   - **qualification-gate:** Use the recorded **Evidence Reference**
     to locate the gate's evidence (see the evidence-status rule in
     the unsatisfied-criterion list below). If the reference is
     missing or unusable, ask for clarification.
     A passing automated test does not satisfy a criterion whose
     approved method is qualification-gate.
   - **external-evidence:** Use the recorded **Evidence Reference**
     to locate the external evidence (see the evidence-status rule
     in the unsatisfied-criterion list below). If the reference is
     missing or unusable, ask for clarification.
     A passing automated test does not satisfy a criterion whose
     approved method is external-evidence.
   - **unresolved:** The method was not determined during planning.
     Flag to the user for clarification before assessing; do not
     guess a method.
   - **Assess satisfaction:** Based on the approved method's evidence,
     is the criterion fully satisfied, partially satisfied, or not
     addressed?

Record the result for each criterion. If any criterion is not fully
satisfied:

1. If it's a gap in implementation or tests — fix it, commit the fix,
   then re-run Step 3 (clean/base), Step 4 affected checks, Step 5
   coverage when covered packages touched, Step 6 regression when
   production code changed, the Step 7 scope comparison and self-review
   gate (consuming remaining MAX_ROUNDS), and re-verify Step 8 AC on
   the new committed HEAD. Do not reuse acceptance judgments from before
   the fix.
2. If it's ambiguous whether the criterion is met — flag it to the
   user with your assessment and let them decide
3. If the criterion's approved verification method is manual
   verification, a qualification gate, or external evidence —
   use the recorded **Evidence Reference** to locate the evidence.
   If the reference is missing or unusable, ask the user for
   clarification rather than guessing from available sources.
   Before marking evidence `verified`, verify the evidence basis
   applies to the **current candidate** (build, revision, or test
   run). Evidence collected against a different candidate whose
   applicability to the current candidate is unknown must remain
   `pending`. Compare the evidence against the entry's original
   source criteria.
   Determine the status (not-started, pending, verified, or failed).
   If evidence status is `verified`, the AC passes its approved
   method. If `pending` or `not-started`, record the AC as "awaiting
   external evidence" with the entry ID. If `failed`, the AC fails.
   Reuse this same evidence result when writing the report in Step 9.
   Do not record manual ACs as merely "requires manual verification"
   without checking the evidence status

### Step 8b: Test Plan Verification

If `.artifacts/implement/{issue-key}/testplan.md` exists, independently
verify that every **automatable** test case has been implemented.

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
  IDs, and SHA-256 of `.artifacts/implement/{issue-key}/testplan.md`
  at confirmation time): compute the current SHA-256 of the
  story-scoped testplan (`sha256sum
  .artifacts/implement/{issue-key}/testplan.md`) and compare against
  the recorded hash. A TC is effectively confirmed only when ALL of:
  (1) the plan records a "confirmed" status with a SHA-256 binding,
  (2) the current story-scoped testplan hash matches the recorded
  hash, and (3) the TC ID appears in the confirmed list. If the
  hash differs, the confirmation is stale — treat as unconfirmed.
  Missing SHA-256 binding (no hash recorded) is treated as
  unconfirmed.
- **Source-Discovery: unresolved takes precedence.** If the testplan
  contains `Source-Discovery: unresolved`, ALL TCs from that source
  are provisional regardless of confirmation hash or ID matches.
  Do not write mandatory gap-fill tests or gate commits on
  unresolved-source TC gaps. Report as "source discovery unresolved
  — TCs provisional until source is resolved."
- Write gap-fill tests only for effectively confirmed TCs whose
  source discovery is resolved; report TC coverage normally for those.
- **Unconfirmed TCs** (no confirmed status in plan, or missing
  SHA-256 binding, or stale hash): coverage is provisional, not
  normative. Do not write mandatory gap-fill
  tests, do not gate commits or block AC-based work on unconfirmed
  TC gaps. Report as "unverified — source testplan not confirmed."

In both cases, do not block the validation report or AC-based
work.

**Non-TC gate confirmation (mixed and gate-only testplans).** When
the story testplan has a `## Qualification Gates` section and the
testplan has `Freshness: unverified` (case 2) but no
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

If `Source-Discovery: unresolved` is present, all retained gates are
provisional regardless of individual confirmation — source discovery
takes precedence and cannot be cleared by confirming gates alone.
Fresh verified source makes gates authoritative without manual
confirmation.

Do not invent automated gate confirmation or silently treat
unverified gates as authoritative. Current approved AC obligations
remain mandatory regardless of gate provenance. Carry source
freshness honestly in the validation report.

Test cases marked with a `Qualification gate` marker in the story
testplan are **not** candidates for unit/integration test generation —
they require their designated execution environment and are tracked as
external validation evidence. Exclude qualification-gate TCs from the
coverage check; verify they are listed in the validation report's
external evidence section instead.

This check re-derives the required TC ID list from `testplan.md`
directly — it does NOT rely on the plan's task-to-TC-ID mappings or
`/code`'s per-task reconciliation for determining which tests exist.
The only information carried forward from the plan is the N/A rationale
for test cases marked inapplicable. This is an intentional independent
verification: if the plan's
bookkeeping or the code phase's gate drifted from reality, this step
catches it.

If `testplan.md` does not exist and `02-plan.md` has no Test Plan
Coverage section, skip this step entirely. However, if `02-plan.md`
has TC mappings but `testplan.md` is missing, unreadable, or malformed
(no parseable TC IDs and no Qualification Gates section), stop and
report the inconsistency. A gate-only testplan (zero TC IDs but a
`## Qualification Gates` section) is valid only when `02-plan.md`
contains no TC mappings in its Test Plan Coverage section. If the
plan still maps TCs but the testplan is gate-only, stop and report
the inconsistency — re-ingest may have replaced TCs with gates
while the plan retains stale mappings. The user must re-plan or
confirm the removal before proceeding. When the gate-only plan is
consistent, skip the automated coverage check and proceed directly
to step 4 below.

1. Read `testplan.md` and extract all TC IDs. Separate them into
   three groups:
   - **Automatable TCs** (`Automation: automated` without a
     `[Qualification gate]` marker): verify Preconditions, Steps,
     and Expected Results sections are present. If missing, stop
     and report the testplan as malformed.
   - **Manual verification TCs** (`[Manual verification]` marker):
     verify the TC entry is present. These do not require
     Preconditions/Steps/Expected Results sections. When evidence
     is provided, compare it against the TC's verification method
     and any criteria from the source test case before marking the
     entry as verified. Evidence that does not address the original
     criteria remains pending, not verified.
   - **Qualification gate TCs** (`[Qualification gate]` marker):
     verify the TC entry is present. These do not require
     Preconditions/Steps/Expected Results sections.
2. For each **automatable** TC ID (except those the validate phase
   agrees are legitimately N/A based on the rationale in the plan's
   Test Plan Coverage matrix):
   - Search the test files on the feature branch for a test whose
     scenario matches the TC's Steps and whose assertions match the
     Expected Results.
   - The match is behavioral, not textual — the test must exercise the
     described scenario and assert the described outcomes.
   - Record the test file and test name for each TC ID.
3. If any automatable TC ID lacks a corresponding test:
   - If the testplan contains `Source-Discovery: unresolved`, ALL
     TCs from that source are provisional regardless of confirmation
     hash or ID matches. Report gaps as provisional: "TC coverage
     gap — source discovery unresolved, not normative until source
     is resolved." Do not write mandatory gap-fill tests or gate
     commits on unresolved-source TC gaps.
   - If the TC is NOT effectively confirmed (see criteria above:
     hash present + current story-scoped testplan hash matches
     recorded hash + TC ID in confirmed list) AND `testplan.md`
     contains `Freshness: unverified`, do NOT write tests for the
     missing TCs. Report the gap as provisional: "TC coverage gap —
     unconfirmed source, not normative until confirmed." AC-based
     validation and existing tests continue normally. Do not gate
     commits on unconfirmed TC gaps.
   - For effectively confirmed TCs or verified-source TCs (with
     resolved source discovery): write the missing test following
     contract-based testing standards. These TCs are normative —
     their gaps are real and should be filled.
   - Commit the test following the project's commit format.
   - Re-run Step 4 affected checks, Step 5 coverage when tests affect
     covered packages, Step 6 regression when production code changed,
     Step 3 (clean/base), the Step 7 scope comparison and self-review
     gate on the committed HEAD (consuming remaining MAX_ROUNDS), and
     re-verify Step 8 AC and applicable Step 8b TC consistency on the
     new HEAD. Reassess whether each external validation evidence entry
     still applies to the post-commit candidate — if applicability is
     unknown after the code change, keep the entry `pending`. If the
     review gate proposes production fixes, route them through the same
     post-fix cycle as Step 7.
4. For manual verification TCs, qualification gate TCs, and non-TC
   qualification gates (from the `## Qualification Gates` section
   of the story testplan — these have no TC IDs), record their
   status in the External Validation Evidence section (see report
   template below). Use gate heading/source reference as identity
   for non-TC entries instead of inventing TC IDs.
5. Record results for the validation report.

### Step 9: Write Validation Report

Write `.artifacts/implement/{issue-key}/05-validation-report.md`:

```markdown
# Validation Report — {issue-key}

## Branch Currency

{Current with base / N commits behind {local-base} — rebased before validation
 / N commits behind {local-base} — user chose to continue without rebasing}

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

## Test Plan Verification

{Include only if testplan.md exists. Omit entirely otherwise.}

| TC ID | Title | Test File | Test Name | Status |
|-------|-------|-----------|-----------|--------|
| TC-FR1-01 | {title} | {file} | {test name} | covered |
| TC-FR1-02 | {title} | {file} | {test name} | gap-filled |
| TC-NFR1-01 | {title} | — | — | N/A |

{Status values:
 - covered: test existed and had sufficient assertion depth
 - gap-filled: test was written during validation
 - N/A: test case legitimately not applicable (rationale required)

 If all automatable TCs are covered: "All automatable test plan cases
 verified." (Qualification-gate and manual-verification TCs are tracked
 separately in External Validation Evidence.)
 If gaps were filled: "{N} test cases required additional tests during
 validation."
 If any N/A: list rationale for each.}

## External Validation Evidence

{Include this section when any AC criterion uses a non-automated
 verification method (manual-test, qualification-gate, or
 external-evidence in the AC coverage matrix's Method column),
 when testplan.md contains qualification-gate or manual-verification
 TCs, or when non-TC qualification gates exist. Include AC-linked
 evidence even when testplan.md contains zero qualifying entries —
 ACs verified by qualification gates or external evidence must
 appear regardless.

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
 - verified: evidence reviewed and accepted — verification method,
   source criteria, and evidence basis (candidate build/revision)
   all confirmed applicable to the current candidate
 - failed: evidence shows the requirement is not met

 Before marking evidence `verified`, verify the evidence basis
 applies to the current candidate (build, revision, or test run).
 If the evidence was collected against a different candidate or
 revision and applicability is unknown, keep it `pending`. Record
 the evidence basis (candidate identifier, date) alongside the
 status.

 If all verified: "All external validation evidence verified."
 If any mandatory entry failed: "N mandatory entries FAILED —
 required evidence shows requirements not met." Overall result
 must be FAIL.
 If any mandatory entry is pending or not-started: "N mandatory
 entries awaiting external evidence — these are not discharged
 by automated test coverage." Overall result cannot be PASS.
 Mandatory entries are: source-verified authoritative TCs,
 effectively confirmed retained TCs (per Step 8b criteria, with
 resolved source discovery), source-verified authoritative
 non-TC qualification gates (fresh from verified source — mandatory
 without confirmation), effectively confirmed retained non-TC
 qualification gates (per Step 8b gate confirmation, with resolved
 discovery), and all current AC obligations verified by their
 approved Method and Evidence Reference. A fresh authoritative
 gate that is pending or not-started blocks PASS; a failed
 mandatory gate means FAIL without requiring confirmation first.
 Unconfirmed retained gates are provisional; report their
 pending status separately but do not block Overall: PASS on
 their account alone.
 A provisional old-TC or gate mention of an AC does not override
 the current approved verification method; equally it does not
 waive a genuine current AC obligation or required gate.
 Current AC obligations are always mandatory regardless of TC
 or gate provenance.
 Unconfirmed TC entries are provisional — report their pending
 status separately but do not block Overall: PASS on their
 account alone. A failed provisional entry is informational,
 not verdict-controlling.}

## Quality Review Findings

{Findings from the code quality review gate (protocol criteria plus
 validate-specific supplementary criteria). Distinguish between:
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
- **Context SHA-256:** {SHA-256 of
  `.artifacts/implement/{issue-key}/01-context.md`, or "absent" if
  no context file exists}
- **Plan SHA-256:** {SHA-256 of
  `.artifacts/implement/{issue-key}/02-plan.md`, or "absent" if no
  plan file exists}
- **Testplan SHA-256:** {SHA-256 of
  `.artifacts/implement/{issue-key}/testplan.md` at validation time,
  or "absent" if no testplan}

{This section binds the validation result to the specific candidate
 code and input artifacts that were validated. The publish step
 compares these against current inputs to detect stale reports —
 a re-ingest, branch change, AC change, or gate addition
 invalidates the old PASS. Legacy reports without this section
 require re-validation.}

## Result

{Automated test coverage: PASS / FAIL — whether all authoritative or
 individually confirmed automatable TC IDs have passing tests,
 coverage meets thresholds, and no regressions. Provisional
 (unconfirmed) TCs are reported separately and excluded from this
 line.

 External validation: COMPLETE / PENDING / FAILED / NOT STARTED —
 whether all manual verification, qualification gate, and non-TC
 gate evidence has been provided and accepted.

 Write `Overall: PASS` on its own line only when ALL of:
 (1) all acceptance criteria pass their approved verification
     method (automated scenario, manual TC, qualification gate,
     or manual verification — as determined in Step 8),
 (2) all authoritative or individually confirmed automatable TC
     IDs have passing tests, coverage meets thresholds, and no
     regressions,
 (3) all authoritative or individually confirmed external
     validation entries (manual TCs and qualification gates) are
     verified.
 Unconfirmed TCs (from an unverified or unconfirmed testplan) are
 provisional — report them separately and exclude them from
 mandatory pass checks. An unconfirmed TC gap does not block
 Overall: PASS, but must be reported as provisional coverage.
 A failed or pending confirmed entry, or an AC without approved
 coverage, always blocks Overall: PASS.
 Source-Discovery: if `testplan.md` contains
 `Source-Discovery: unresolved` or `Freshness:
 unresolved-source`, Overall cannot be PASS regardless of
 provisional TC exemptions — unresolved discovery means
 required validation gates may exist but are unknown.
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

### Step 10: Present Results

Summarize for the user:
- Which checks passed and which failed
- Coverage assessment (behavioral, not numeric)
- Acceptance criteria status (all satisfied, or which ones have gaps)
- Automatable test plan coverage (all automatable TCs covered / gaps
  filled / not applicable), if testplan exists — distinguish from
  overall readiness
- External validation evidence status: how many mandatory entries are
  verified, pending, not-started, or failed — these are not discharged
  by automated test coverage. Report provisional entries separately.
- Any tests added during validation
- Any regressions found (and whether they were fixed)
- Overall verdict: the `Overall:` line from the report (PASS only
  when both automated coverage and all mandatory external evidence
  are verified; otherwise state the specific gap)

## Output

- `.artifacts/implement/{issue-key}/05-validation-report.md`
- Additional test files (if coverage gaps were found)
- Fix commits (if issues were found and fixed)

## When This Phase Is Done

Report your results:
- Validation check results (all pass / some fail)
- Coverage assessment
- Acceptance criteria status
- Regression status
- Overall verdict

Then return to the invoking workflow router for completion guidance.
