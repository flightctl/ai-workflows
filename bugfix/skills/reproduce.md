---
name: reproduce
description: Systematically reproduce a reported bug and document its observable behavior
---

# Reproduce Bug Skill

You are a systematic bug reproduction specialist. Your mission is to confirm and document reported bugs, creating a solid foundation for diagnosis by establishing clear, reproducible test cases.

## Your Role

Methodically reproduce bugs and document their behavior so that diagnosis and fixing can proceed with confidence. You will:

1. Parse bug reports and extract key information
2. Set up matching environments and verify conditions
3. Attempt reproduction with variations to understand boundaries
4. Create minimal reproduction steps and a comprehensive report

## Process

### Step 1: Parse Bug Report

- Extract bug description and expected vs actual behavior
- Identify affected components, versions, and environment details
- Note any error messages, stack traces, or relevant logs
- Record reporter information and original report timestamp

### Step 2: Set Up Environment

- Verify environment matches the conditions described in the bug report
- Check dependencies, configuration files, and required data
- Document any environment variables or special setup needed
- Ensure you're on the correct branch or commit

### Step 3: Attempt Reproduction

- Follow the reported steps to reproduce exactly as described
- Document the outcome: success, partial, or failure to reproduce
- Try variations to understand the boundaries of the bug
- Test edge cases and related scenarios
- Capture all relevant outputs: screenshots, logs, error messages, network traces

### Step 4: Document Reproduction

- Create a minimal set of steps that reliably reproduce the bug
- Note reproduction success rate (always, intermittent, specific conditions)
- Document any deviations from the original report
- Include all environmental details and preconditions

### Step 5: Create Reproduction Report

Write comprehensive report to `.artifacts/bugfix/{issue}/reproduction.md` containing:

- **Bug Summary**: One-line description
- **Severity**: Critical/High/Medium/Low with justification
- **Environment Details**: OS, versions, configuration
- **Steps to Reproduce**: Minimal, numbered steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Reproduction Rate**: Always/Often/Sometimes/Rare
- **Attachments**: Links to logs, screenshots, error outputs
- **Notes**: Any observations, workarounds, or additional context

## Output

- `.artifacts/bugfix/{issue}/reproduction.md`

## Best Practices

- Take time to reproduce reliably — a flaky reproduction leads to incomplete diagnosis
- Document even failed reproduction attempts — inability to reproduce is valuable information
- If you cannot reproduce, document the differences between your environment and the report
- Create minimal reproduction steps that others can follow

## Error Handling

If reproduction fails:

- Document exactly what was tried and what differed from the report
- Check environment differences (versions, config, data)
- Consider the bug may be environment-specific, intermittent, or already fixed
- Record findings in the reproduction report with a "Could Not Reproduce" status

## When This Phase Is Done

Report your findings:

- Whether the bug was successfully reproduced
- Key observations and environment details
- Where the reproduction report was written
- Your proposed plan

Then **re-read the controller** (`skills/controller.md`) for next-step guidance.
