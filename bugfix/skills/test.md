---
name: test
description: Verify a bug fix with change-proportionate checks and meaningful regression coverage
---

# Test & Verify Fix Skill

Verify that the fix resolves the issue without introducing new problems, using checks proportionate to the changed behavior and risk.

## Your Role

Systematically verify fixes and build test coverage that prevents recurrence. You will:

1. Inspect the diff, affected behavior, and repository validation requirements
2. Select the smallest useful existing checks and add regression coverage where needed
3. Expand verification only when risk or repository requirements justify it
4. Report results and meaningful gaps honestly

## Process

### Step 1: Select Checks and Regression Coverage

- Inspect the diff and affected consumers; use the project's documented checks and test conventions
- Add or extend a meaningful regression test when changed behavior warrants it and existing coverage is insufficient
- For docs, configuration, or no testable code path, explain why no new test is needed; use applicable content, schema, lint, render, or consumer checks instead
- Reuse recorded results only while tested inputs and environment remain unchanged; after edits, rerun only affected checks
- Preserve repository-required security, authentication, tenant-isolation, release, generation, and safety checks
- When adding a regression test, reproduce the original bug
- Verify the test **fails** without your fix (proves it catches the bug)
- Verify the test **passes** with your fix (proves the fix works)
- Use descriptive test names that reference the issue (e.g., `TestStatusUpdateRetry_Issue425`)
- Follow project test conventions and patterns

### Step 2: Targeted Unit Testing (When Applicable)

- Test the specific functions/methods that were modified
- Cover all code paths in the fix
- Test edge cases identified during diagnosis
- Test error handling and validation logic
- Aim for high coverage of changed code
- **Test all states/phases/conditions**: If the fix involves state-dependent logic, ensure tests cover ALL possible states, not just the common ones. For example, if fixing polling that stops on terminal phases, test all terminal phases (Stopped, Completed, Failed, Error), not just one or two.
- **Test feature interactions**: If the fix involves multiple interacting features or configurations, test their combinations (e.g., pagination + polling together, not only separately)

### Step 3: Integration Testing (When Justified)

- Run when affected component interactions, specific bug risk, repository requirements, or an explicit request warrant it
- Test the fix in realistic scenarios with dependent components
- Verify end-to-end behavior matches expectations
- Test interactions with databases, APIs, or external systems
- Ensure the fix works in the full system context

### Step 4: Regression Testing

- Start with existing tests covering the changed behavior and affected consumers
- Run wider or full suites only for broad/shared blast radius, specific bug risk, repository-required contracts, or an explicit request
- Defer wider checks to CI only after verifying that CI covers them; do not assume it exists, is green, or will monitor and repair failures
- If tests fail, investigate whether:
  - The test was wrong (update it)
  - The fix broke something (revise the fix)
  - Test needs updating due to intentional behavior change (document it)

### Step 5: Manual Verification (When Justified)

- Use when automated checks do not establish the fix, or risk, repository requirements, or an explicit request warrant it
- Manually execute the original reproduction steps from the reproduction report
- Verify the expected behavior is now observed
- Test related functionality to ensure no side effects
- Test in multiple environments if applicable (dev, staging)

### Step 6: Performance Validation (When Applicable)

- If the fix touches performance-sensitive code, measure impact
- Profile before/after if the bug was performance-related
- Ensure no performance degradation introduced
- Document any performance changes in test report

### Step 7: Security Check

- Verify the fix doesn't introduce security vulnerabilities
- Check for common issues: SQL injection, XSS, CSRF, etc.
- Ensure error messages don't leak sensitive information
- Validate input handling and sanitization
- Focus on affected attack surfaces; run additional security checks when risk or repository requirements warrant them

### Step 8: Document Test Results

Write a concise report at `.artifacts/bugfix/{issue}/verification.md` containing applicable results:

- **Test Summary**: Overview of testing performed
- **Regression Coverage**: Existing or new tests, or why no new test was needed
- **Unit Test Results**: Commands and pass/fail status, coverage metrics if collected
- **Integration Test Results**: End-to-end validation results
- **Wider Checks**: Results, or concise reasons for skipping; distinguish verified CI coverage from local results
- **Manual Testing**: Steps performed and observations
- **Performance Impact**: Before/after metrics (if applicable)
- **Security Review**: Findings from security check
- **Known Limitations**: Relevant unavailable checks, unresolved failures, and unverified behavior
- **Recommendations**: Follow-up work or monitoring needed

### Step 9: Report Results to the User

After writing `.artifacts/bugfix/{issue}/verification.md`:

1. **Tell the user where the file was written** — include the full path
2. **Summarize the results inline** — don't make the user open the file to find out what happened. Include at minimum:
   - Overall pass/fail status
   - Applicable checks and results; test counts when available
   - Regression coverage added or reused, or why none was needed
   - Any failures or concerns that need attention
   - Recommended next steps (proceed to `/document`, revisit `/fix`, etc.)

## Output

- New or extended regression tests when needed
- `.artifacts/bugfix/{issue}/verification.md`

## Best Practices

- **Meaningful coverage** — add tests for uncovered changed behavior, not just to change a test file
- **Test the test** — verify your new test actually fails without the fix
- **Scale to risk** — full suites and manual checks are not automatic for every fix
- **Document failed tests** — if tests fail, that's valuable information

## Error Handling

If tests fail unexpectedly:

- Determine if the failure is in the new test or an existing test
- Check if the fix introduced a regression
- Gather evidence before attributing failures; compare with the unchanged baseline or inspect diagnostics. Do not label a failure unrelated merely to proceed, or fix unrelated bugs
- **Classify before retrying**: is this a code bug (your fix is wrong) or
  an infrastructure error — a failure outside your test assertions that
  reproduces without your changes (e.g., envtest conflicts, connection
  timeouts)
- Code bug: document the failure, revise the fix, and retry
- Infrastructure error: retry only when conditions changed or evidence suggests a transient failure, up to `max_retries`, without returning to `/fix`. Otherwise document the blocker and supporting evidence before proceeding; never report an unavailable check as passed

## When This Phase Is Done

Report your results:

- How many tests were added and their results
- Which applicable checks passed, failed, were reused, skipped, or unavailable, and why
- Where the verification report was written
- Your proposed plan

Then return to the invoking workflow router for completion guidance.
