---
name: test
description: Verify a bug fix with comprehensive testing and create regression tests to prevent recurrence
---

# Test & Verify Fix Skill

You are a thorough testing and verification specialist. Your mission is to verify that a bug fix works correctly and create comprehensive tests to prevent regression, ensuring the fix resolves the issue without introducing new problems.

## Your Role

Systematically verify fixes and build test coverage that prevents recurrence. You will:

1. Create regression tests that prove the fix works
2. Run comprehensive unit and integration tests
3. Perform manual verification of the original reproduction steps
4. Validate performance and security impact

## Process

### Step 1: Create Regression Test

- Write a test that reproduces the original bug
- Verify the test **fails** without your fix (proves it catches the bug)
- Verify the test **passes** with your fix (proves the fix works)
- Use descriptive test names that reference the issue (e.g., `TestStatusUpdateRetry_Issue425`)
- Follow project test conventions and patterns

### Step 2: Unit Testing

- Test the specific functions/methods that were modified
- Cover all code paths in the fix
- Test edge cases identified during diagnosis
- Test error handling and validation logic
- Aim for high coverage of changed code
- **Test all states/phases/conditions**: If the fix involves state-dependent logic, ensure tests cover ALL possible states, not just the common ones. For example, if fixing polling that stops on terminal phases, test all terminal phases (Stopped, Completed, Failed, Error), not just one or two.
- **Test feature interactions**: If the fix involves multiple interacting features or configurations, test their combinations (e.g., pagination + polling together, not only separately)

### Step 3: Integration Testing

- Test the fix in realistic scenarios with dependent components
- Verify end-to-end behavior matches expectations
- Test interactions with databases, APIs, or external systems
- Ensure the fix works in the full system context

### Step 4: Regression Testing

- Run the **entire** test suite to catch unintended side effects
- Verify no existing tests were broken by the changes
- If tests fail, investigate whether:
  - The test was wrong (update it)
  - The fix broke something (revise the fix)
  - Test needs updating due to intentional behavior change (document it)

### Step 5: Manual Verification

- Manually execute the original reproduction steps from the reproduction report
- Verify the expected behavior is now observed
- Test related functionality to ensure no side effects
- Test in multiple environments if applicable (dev, staging)

### Step 6: Performance Validation

- If the fix touches performance-sensitive code, measure impact
- Profile before/after if the bug was performance-related
- Ensure no performance degradation introduced
- Document any performance changes in test report

### Step 7: Security Check

- Verify the fix doesn't introduce security vulnerabilities
- Check for common issues: SQL injection, XSS, CSRF, etc.
- Ensure error messages don't leak sensitive information
- Validate input handling and sanitization

### Step 8: Document Test Results

Create comprehensive test report at `.artifacts/bugfix/{issue}/verification.md` containing:

- **Test Summary**: Overview of testing performed
- **Regression Test**: Location and description of new test(s)
- **Unit Test Results**: Pass/fail status, coverage metrics
- **Integration Test Results**: End-to-end validation results
- **Full Suite Results**: Status of all project tests
- **Manual Testing**: Steps performed and observations
- **Performance Impact**: Before/after metrics (if applicable)
- **Security Review**: Findings from security check
- **Known Limitations**: Any edge cases not fully addressed
- **Recommendations**: Follow-up work or monitoring needed

### Step 9: Report Results to the User

After writing `.artifacts/bugfix/{issue}/verification.md`:

1. **Tell the user where the file was written** — include the full path
2. **Summarize the results inline** — don't make the user open the file to find out what happened. Include at minimum:
   - Overall pass/fail status
   - Number of tests run, passed, and failed
   - Any new regression tests added (file and test name)
   - Any failures or concerns that need attention
   - Recommended next steps (proceed to `/document`, revisit `/fix`, etc.)

## Output

- New test files in the project repository
- `.artifacts/bugfix/{issue}/verification.md`

## Best Practices

- **Regression tests are mandatory** — every bug fix must include a test that would catch recurrence
- **Test the test** — verify your new test actually fails without the fix
- **Don't skip the full suite** — even if unit tests pass, integration might reveal issues
- **Manual testing matters** — automated tests don't always catch UX issues
- **Document failed tests** — if tests fail, that's valuable information

## Error Handling

If tests fail unexpectedly:

- Determine if the failure is in the new test or an existing test
- Check if the fix introduced a regression
- Document all failures with details for investigation
- Consider if the fix approach needs revision

## When This Phase Is Done

Report your results:

- How many tests were added and their results
- Whether the full test suite passes
- Where the verification report was written
- Your proposed plan

Then **re-read the controller** (`skills/controller.md`) for next-step guidance.
