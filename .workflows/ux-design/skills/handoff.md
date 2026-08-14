---
name: handoff
description: Implementation handoff with UXD design-handoff skill enhancement.
---

# Handoff — with UXD Design Handoff

This override wraps the built-in handoff phase and enhances the
implementation spec with the UXD design-handoff skill when available.

## Step 1: Run Built-in Handoff Phase

Read and execute the built-in handoff skill at
`../../../ux-design/skills/handoff.md`.

Complete the full handoff process — component mapping, interaction specs,
state enumeration, acceptance criteria, and research context.

## Step 2: UXD Design Handoff Enhancement (conditional)

After the built-in handoff completes, check whether the UXD design-handoff
skill is available:

Run `/uxd-workshop:uxd-design-handoff` with the handoff artifact
(`04-handoff.md`) as input. If this skill is not available, skip this step.

### If running:

Compare the skill's output with the built-in handoff results. Strengthen
`04-handoff.md` with any additions:
- Missing state enumerations the skill identified
- Acceptance criteria gaps
- Component mapping refinements

### If skipping:

Continue with the built-in handoff output — it covers the same ground.

## When This Phase Is Done

Present the handoff spec to the researcher.
Then **re-read the controller** (`controller.md`) for next-step guidance.
