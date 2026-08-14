---
name: draft
description: Design document drafting with PatternFly compliance check for PF-based UIs.
---

# Design Draft — with PatternFly Compliance

This override wraps the built-in design draft phase and adds a PatternFly
compliance check for features that use PatternFly components.

## Step 1: Run Built-in Draft

Read and execute the built-in draft skill at
`../../../design/skills/draft.md`.

Follow every stage — outline, draft, review, and revision. Write the design
document to `.artifacts/design/{issue-key}/03-design.md` as usual.

## Step 2: PatternFly Compliance Check (conditional)

After the design document is drafted, check whether the feature uses
PatternFly components:

**Run this step when ANY of the following are true:**
- The design references PatternFly components (Page, Table, Modal, Toolbar, etc.)
- The codebase imports from `@patternfly/*` packages
- The feature modifies existing PatternFly-based UI

**Skip this step when:**
- No PatternFly components are referenced or imported
- The feature is backend-only

### If running:

Run `/pf-code-review:pf-review`. If this skill is not available, skip this step.

Append findings to the design document:

```markdown
## PatternFly Compliance

{compliance findings from pf-review}
```

### If skipping:

Continue without PatternFly compliance check.

## When This Phase Is Done

Report the design document with compliance results (if run).
Then **re-read the controller** (`controller.md`) for next-step guidance.
