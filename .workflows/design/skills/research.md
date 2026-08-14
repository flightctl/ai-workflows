---
name: research
description: Design research with UXD heuristic evaluation for UI-facing features.
---

# Design Research — with UXD Evaluation

This override wraps the built-in design research phase and adds a UXD
heuristic evaluation step for features with a user-facing interface.

## Step 1: Run Built-in Research

Read and execute the built-in research skill at
`../../../design/skills/research.md`.

Follow every stage — scope, plan, iterative research execution, synthesis,
and user presentation. Write findings to
`.artifacts/design/{issue-key}/02-research.md` as usual.

Do not skip or abbreviate any part of the built-in process.

## Step 2: UX Heuristic Evaluation (conditional)

After the built-in research completes and the user approves the findings,
check whether this feature has a user-facing interface:

**Run this step when ANY of the following are true:**
- The PRD describes new screens, pages, or views
- The PRD modifies existing UI workflows or navigation
- Wireframes, mockups, or screenshots exist in the artifacts or PRD
- The context doc (`01-context.md`) references frontend components

**Skip this step when:**
- The feature is entirely backend (API, data pipeline, infrastructure)
- No UI surface is described or implied in the PRD

### If running:

Gather UI artifacts from the research and PRD — wireframes, mockups,
screenshots, or detailed text descriptions of the proposed interface.

Run `/uxd-workshop:uxd-research-heuristic-eval` against the gathered
artifacts. If this skill is not available, skip this step.

When the evaluation completes, append the findings to the research artifact:

```markdown
## UX Heuristic Evaluation

{evaluation findings from the heuristic eval skill}
```

Save to `.artifacts/design/{issue-key}/02-research.md`.

Present the combined findings to the user — standard research results plus
heuristic evaluation. Note which usability violations may affect
architectural decisions in the design phase.

### If skipping:

Continue without UXD evaluation.

## When This Phase Is Done

Report combined findings (standard research + heuristic evaluation if run).
Then **re-read the controller** (`controller.md`) for next-step guidance.
