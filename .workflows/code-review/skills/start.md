---
name: start
description: Code review with PatternFly compliance checks for UI changes.
---

# Code Review — with UXD Checks

This override wraps the built-in code review start phase and adds PatternFly
compliance checks for PRs that touch UI code.

## Step 1: Run Built-in Code Review

Read and execute the built-in code review skill at
`../../../code-review/skills/start.md`.

Complete the full review process as usual.

## Step 2: UXD Review (conditional)

After the built-in review completes, check whether the PR touches UI code:

**Run this step when ANY of the following are true:**
- Changed files include `.tsx`, `.jsx`, `.css`, or `.scss` extensions
- Changed files import from `@patternfly/*` packages

**Skip this step when:**
- No files match the above criteria

### If running:

Run `/pf-code-review:pf-review`. If this skill is not available, skip this step.

Add UXD findings as a separate section in the review output.

### If skipping:

Continue without UXD checks.

## When This Phase Is Done

Present combined review findings — standard code review plus UXD checks (if run).
Then **re-read the controller** (`controller.md`) for next-step guidance.
