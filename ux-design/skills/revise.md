---
name: revise
description: Incorporate stakeholder feedback into the handoff spec.
---

# Revise — Update Handoff Spec

Incorporate the user's feedback into the existing handoff spec while
maintaining consistency across all prior artifacts. This phase is
repeatable — the user may request multiple rounds of revision.

## Critical Rules

- **Change only what's requested.** Do not "improve" sections the user didn't mention.
- **Maintain consistency across artifacts.** If a handoff change contradicts research findings or evaluation results, flag it.
- **Show your changes.** After revising, summarize what changed so the user can verify.

## Process

### Step 1: Read Current Artifacts

Read the handoff spec and prior artifacts:
- `.artifacts/ux-design/{issue-key}/04-handoff.md` (the deliverable)
- `.artifacts/ux-design/{issue-key}/03-evaluation.md` (evaluation context)
- `.artifacts/ux-design/{issue-key}/01-discovery.md` (problem context)

### Step 2: Understand the Feedback

The user's feedback may target:
- Component mapping changes
- Interaction spec corrections
- State coverage gaps
- Acceptance criteria adjustments
- Research context clarifications

Clarify with the user if the feedback is ambiguous before making changes.

### Step 3: Apply Changes

Edit the handoff spec:
- For specific edits: apply them directly
- For directional feedback: propose concrete changes and confirm before applying
- For new information: add it to the appropriate sections

### Step 4: Consistency Check

After applying changes, verify:
- Do acceptance criteria still trace to research findings?
- Does the component mapping still align with the prototype?
- Are interaction specs consistent with evaluation findings?
- Are there contradictions with locked research decisions?

### Step 5: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Handoff Changes
- {Section}: {what changed and why}

### Consistency Updates
- {any cascading updates to maintain coherence}
```

## Output

- `.artifacts/ux-design/{issue-key}/04-handoff.md` (updated)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Any remaining open questions

Then **re-read the controller** (`controller.md`) for next-step guidance.
