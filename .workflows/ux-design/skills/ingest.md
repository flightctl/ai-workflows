---
name: ingest
description: Problem framing with UXD discovery skill enhancement.
---

# Ingest — with UXD Discovery

This override wraps the built-in ingest phase and enhances problem framing
with the UXD discovery skill when available.

## Step 1: Run Built-in Ingest Phase

Read and execute the built-in ingest skill at
`../../../ux-design/skills/ingest.md`.

Complete the full discovery process as usual — problem framing, user group
identification, competitive landscape, and research questions.

## Step 2: UXD Discovery Enhancement (conditional)

After the built-in ingest completes, check whether the UXD discovery skill
is available:

Run `/uxd-workshop:uxd-discovery` with the same input (Jira issue, feature
description, or problem statement). If this skill is not available, skip
this step.

### If running:

Compare the skill's output with the built-in ingest results. Merge any
additional findings into `01-discovery.md`:
- User groups the built-in phase missed
- Competitive examples the skill surfaced
- Research questions worth adding

### If skipping:

Continue with the built-in ingest output — it covers the same ground.

## When This Phase Is Done

Present the discovery brief to the researcher.
Then **re-read the controller** (`controller.md`) for next-step guidance.
