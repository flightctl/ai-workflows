---
name: code
description: Implementation with PatternFly component generation for UI stories.
---

# Implement Code — with PatternFly Generation

This override wraps the built-in implement code phase and adds PatternFly
component generation for stories that involve UI work.

## Step 1: Run Built-in Code Phase

Read and execute the built-in code skill at
`../../../implement/skills/code.md`.

Follow the full TDD cycle — write contract-based tests, then production code.

## Step 2: PatternFly Component Generation (conditional)

After the built-in code phase completes, check whether the story involves
PatternFly UI components:

**Run this step when ANY of the following are true:**
- The story requires new forms, tables, or chart components
- The codebase imports from `@patternfly/*` packages
- The implementation plan references PatternFly components

**Skip this step when:**
- No UI components are needed
- The story is backend-only

### If running:

Use the appropriate PatternFly generator for the component type.
If a skill is not available, skip it.

- **Forms:** `/pf-react:pf-form-gen`
- **Tables:** `/pf-react:pf-table-gen`
- **Charts:** `/pf-react:pf-chart-gen`

Run the generator that matches the component type, then integrate the output
into the implementation.

### If skipping:

Continue without PatternFly generation.

## When This Phase Is Done

Report the implementation with any generated components.
Then **re-read the controller** (`controller.md`) for next-step guidance.
