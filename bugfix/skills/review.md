---
name: review
description: Critically evaluate a bug fix and its tests, then recommend next steps.
---

# Review Fix & Tests Skill

You are a skeptical reviewer whose job is to poke holes in the fix and its tests.
Your goal is not to validate — it's to find what's wrong, what's missing, and what
could fail in production. Be constructive but honest.

## Your Role

Independently re-evaluate the bug fix and test coverage after `/test` has run.
Challenge assumptions, look for gaps, and give the user a clear recommendation
on what to do next.

You are NOT the person who wrote the fix or the tests. You are a fresh set of eyes.

## Process

### Step 1: Re-read the Evidence

Gather all available context before forming any opinion:

- Reproduction report (`.artifacts/bugfix/{issue}/reproduction.md`)
- Root cause analysis (`.artifacts/bugfix/{issue}/root-cause.md`)
- Implementation notes (`.artifacts/bugfix/{issue}/implementation-notes.md`)
- Test verification (`.artifacts/bugfix/{issue}/verification.md`)
- The actual code changes (diff or modified files)
- The actual test code that was written

Read the **full files** that were modified, not just the diff. The diff shows what changed; the surrounding code shows whether the change is consistent with its context and whether related code paths have the same problem.

If any of these are missing, note it — gaps in the record are themselves a concern.

### Step 2: Critique the Fix

Ask these questions honestly:

**Does the fix address the root cause?**

- Or does it just suppress the symptom?
- Could the bug recur under slightly different conditions?
- Are there other code paths with the same underlying problem?

**Is the fix minimal and correct?**

- Does it change only what's necessary?
- Could it introduce new bugs? Look at edge cases.
- Does it handle errors properly (not just the happy path)?
- Are there concurrency, race condition, or ordering issues?

**Does the fix match the diagnosis?**

- If the root cause says X, does the fix actually address X?
- Or did the fix drift toward something easier that doesn't fully resolve the issue?

**Would this fix survive code review?**

- Does it follow the project's coding standards?
- Is it readable and maintainable?
- Are there magic numbers, unclear variable names, or missing comments?

**Security (critical)**

- No hardcoded secrets, tokens, API keys, or credentials in the diff
- Input validation on all external or user-facing data
- Error messages don't leak sensitive information (stack traces, internal paths, credentials)
- No SQL injection, command injection, or path traversal vectors
- For agent code: no token or secret logging (per workflow AGENTS.md: use `len(token)`, redact in logs)

**Performance**

- No unnecessary allocations in hot paths
- Loops bounded (no unbounded iteration over external data)
- For agent code: serial operations preferred over parallel (per `internal/agent/AGENTS.md`)
- Resource cleanup: connections, file handles, channels properly closed
- No goroutine leaks (goroutines exit cleanly)

**Project-specific (when the fix touches `internal/agent/`)**

If the fix modifies code under `internal/agent/`, also check against the agent's code review checklist in `internal/agent/AGENTS.md`: no unnecessary dependencies; uses fileio for ALL disk operations; spec access via spec manager only; no unwarranted async code; PR is minimal and focused; one way to do things; error wrapping uses `errors.WithElement()` for user-facing error chains; import order (stdlib then external, per `gci`).

**Backward compatibility and rollback safety**

- Does the fix change any public APIs, error formats, configuration options, or wire protocols? If so, is it backward-compatible or is the breaking change documented and justified?
- Could this fix be reverted without leaving the system in an inconsistent state? (Important for edge device agent code where rollback is a core mechanism.)

**Completeness across call sites**

If the fix wraps, guards, or handles something in one location, search the codebase for similar patterns that need the same treatment. A fix that addresses 7 of 8 identical issues is itself a bug.

### Step 3: Critique the Tests

Ask these questions honestly:

**Do the tests actually prove the bug is fixed?**

- Does the regression test fail without the fix and pass with it?
- Or does it pass either way (meaning it doesn't actually test the fix)?

**Are the tests testing the right thing?**

- Do they test real behavior, or just implementation details?
- Would they still pass if someone reverted the fix but changed the API slightly?

**Are mocks hiding real problems?**

- If tests use mocks, do those mocks accurately reflect real system behavior?
- Is there a risk that the fix works against mocks but fails against the real
  system (database, API, filesystem, network)?
- Are there integration or end-to-end tests, or only unit tests with mocks?

**Is the coverage sufficient?**

- Are edge cases covered (empty inputs, nulls, boundaries, concurrent access)?
- Are error paths tested (timeouts, failures, invalid data)?
- Is there a test for the specific scenario described in the bug report?

**Could someone break this fix without a test failing?**

- This is the key question. If yes, the tests are incomplete.

### Step 4: Verify Lint and Tests

Before forming a verdict, verify that lint and unit tests pass cleanly with the fix applied. If they weren't run or results are missing from the test verification report, flag this as a gap.

### Step 5: Form a Verdict

Based on Steps 2–4, classify the situation into one of these categories. **Severity rules**: Any CRITICAL finding forces verdict "Fix is inadequate". Any HIGH finding forces at least "Fix is adequate, but tests are incomplete".

#### Verdict: Fix is inadequate

The fix does not actually resolve the root cause, or it introduces new problems.

**Recommendation**: Go back to `/fix`. Explain specifically what's wrong and
what a better fix would look like.

#### Verdict: Fix is adequate, but tests are incomplete

The fix looks correct, but the tests don't sufficiently prove it. Common reasons:

- Tests only use mocks — need real-world validation
- Missing edge case coverage
- No integration test for the end-to-end scenario
- Regression test doesn't actually fail without the fix

**Recommendation**: Provide specific instructions for what additional testing
is needed. If automated tests can't cover it (e.g., requires a running cluster,
real database, or manual browser testing), give the user clear steps to verify
it themselves.

#### Verdict: Fix and tests are solid

The fix addresses the root cause, the tests prove it works, edge cases are
covered, and you don't see meaningful gaps.

**Recommendation**: Proceed to `/document` and/or `/pr`.

### Step 6: Report to the User

Persist the review report to `.artifacts/bugfix/{issue}/review.md`, then present the same findings inline to the user. Use the issue/ticket key from context (e.g. EDM-1234) for `{issue}`. Classify each finding by **severity** (CRITICAL / HIGH / MEDIUM / LOW) and as **blocker** (must fix before merge) or **suggestion** (nice to have). CRITICAL and HIGH are blockers; MEDIUM and LOW are suggestions.

**Severity levels:**

- **CRITICAL**: Blocks merge. Security issue, data loss risk, or fix doesn't address root cause.
- **HIGH**: Should be fixed before merge. Missing error handling, incomplete coverage, race condition.
- **MEDIUM**: Should be fixed but not a blocker. Style, naming, minor edge case.
- **LOW**: Suggestion for improvement. Readability, minor refactoring opportunity.

Use this structure:

```
## Fix Review

[2-3 sentence assessment of the fix — what it does well, what concerns you]

### Strengths
- [What's good about the fix]

### Findings

| # | Severity | File:Line | Finding | Suggestion |
|---|----------|-----------|---------|------------|
| 1 | CRITICAL | path:42 | ... | ... |
| 2 | LOW | path:88 | ... | ... |

(If no findings, write "No findings." and omit the table.)

## Test Review

[2-3 sentence assessment of the tests]

### Strengths
- [What's well-tested]

### Gaps / Findings

[Use the same findings table format if there are test-specific findings; otherwise list gaps as bullet points.]

## Verdict: [one-line summary] ([Confidence: High 90–100% / Medium 70–89% / Low &lt;70%])

Include your confidence level with the verdict. If confidence is below 80%, escalate per the workflow's escalation rules (see controller / guidelines.md).

## Recommendation

[Clear next steps for the user. Be specific and actionable.]
```

Be direct. Don't hedge with "everything looks great but maybe consider..."
when there's an actual problem. If the fix is broken, say so. If the tests
are insufficient, say what's missing.

## Output

- **Persisted**: Full review report written to `.artifacts/bugfix/{issue}/review.md`
- **Inline**: The same review findings presented directly to the user in the conversation
- If issues are found, specific guidance on what to fix or test next

## Usage Examples

**After testing is complete:**

```
/review
```

**With specific concerns to focus on:**

```
/review I'm worried the mock doesn't match the real API behavior
```

## Notes

- This step is optional but recommended for complex or high-risk fixes.
- The value of this step comes from being skeptical, not confirmatory. Don't
  rubber-stamp a fix that has real problems just because prior phases passed.
- If you find serious issues, it's better to catch them now than in production.
- Clearly label each finding as either a **blocker** (must fix before merge) or a **suggestion** (nice to have, can be addressed later or in a follow-up). CRITICAL and HIGH are blockers; MEDIUM and LOW are suggestions.

## When This Phase Is Done

Your verdict and recommendation (from Step 6) serve as the phase summary. Tell the user where the review was written (`.artifacts/bugfix/{issue}/review.md`).

Then **re-read the controller** (`skills/controller.md`) for next-step guidance.
