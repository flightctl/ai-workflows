---
name: validate
description: Validation with PatternFly-aware test generation for UI components.
---

# Implement Validate — with PatternFly Test Generation

This override wraps the built-in implement validate phase and adds
PatternFly-aware test generation for UI components.

## Step 1: Run Built-in Validate Phase

Read and execute the built-in validate skill at
`../../../implement/skills/validate.md`.

Complete the full validation — run tests, check CI expectations, verify coverage.

## Step 2: PatternFly Test Generation (conditional)

After the built-in validation completes, check whether the implementation
includes PatternFly components that need test coverage:

**Run this step when ANY of the following are true:**
- New `.tsx` components import from `@patternfly/*` packages
- Existing PatternFly components were modified as part of the story
- Test coverage for PatternFly components is below project thresholds

**Skip this step when:**
- No PatternFly components were added or modified
- Tests already cover the PatternFly components adequately

### If running:

Run `/pf-react:pf-test-gen`. If this skill is not available, skip this step.

Run the generated tests and verify they pass.

### If skipping:

Continue without PatternFly test generation.

## When This Phase Is Done

Report validation results including any generated tests.
Then **re-read the controller** (`controller.md`) for next-step guidance.
