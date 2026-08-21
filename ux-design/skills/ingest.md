---
name: ingest
description: Problem framing, user group identification, and competitive landscape survey.
---

# Ingest — Discovery

Frame the problem, identify who it affects, and survey how others have
solved it. This phase produces the foundation that all downstream work
builds on.

## Dependencies

This phase requires the `uxd-workshop` skills. If the `uxd-discovery` skill
is not available, stop and tell the researcher to run `./install.sh` to set up
the uxd-workshop skills before proceeding.

## Process

### Step 1: Run UXD Discovery

Invoke the `uxd-discovery` skill with the input source (Jira issue key,
feature description, or problem statement).

The skill handles:
- Problem statement framing
- User group identification (goals, pain points)
- Strategic decisions (themed, with business outcomes and timelines)
- Competitive landscape survey
- Constraints and assumptions

If a Jira issue key was provided, pass it directly. If a published PRD exists
for this issue in the docs repo (the prd workflow publishes there), provide it
as additional context. Do **not** read another workflow's private artifacts
under `.artifacts/prd/` — the shared interfaces between workflows are Jira and
the published docs repo, not each other's working directories.

Wait for the skill to complete and present its output. Confirm understanding
with the researcher before proceeding.

### Step 2: Current State (Codebase Exploration)

The skill does not explore the codebase. Do this manually:

Explore the repository to understand what exists today in the affected area:
- What pages or views exist?
- What components are used?
- What user flows currently exist?

If any external operation fails (Jira fetch, codebase read): note what failed,
continue with available data, and never fabricate context to fill the gap.

### Step 3: Assemble the Discovery Artifact

Combine the skill's output with the codebase exploration into the artifact
below. Preserve the skill's Strategic Decisions structure exactly — do not
flatten or reformat its themed format. Add the `## Current State` section
from Step 2.

## Output

`.artifacts/ux-design/{issue-key}/01-discovery.md`

```markdown
# Discovery — {issue-key}

**Date:** {date}
**Source:** {Jira issue key, or "Feature description", or "Problem statement"}

## Problem Statement

{From skill output — 1-2 paragraphs: what problem, for whom, why it matters}

## User Groups

### {Group Name}
- **Description:** {who they are}
- **Goals:** {what they want to accomplish}
- **Pain points:** {current frustrations}

## Current State

{What the product does today in this area. Include relevant file paths
 or component references from the codebase. Written in Step 2 above.}

## Strategic Decisions

{From skill output — themed, with business outcomes and timelines.
 Preserve the skill's structure exactly.}

## Competitive Landscape

{From skill output}

## Constraints

{From skill output}

## Assumptions to Validate

{From skill output — framed as testable hypotheses}
```

## When This Phase Is Done

Present the discovery brief to the researcher:
"Here's the problem framing, user groups, and competitive landscape.
Does this capture the right scope? Any user groups, competitors, or
strategic decisions missing?"

Wait for confirmation. Then **re-read the controller** (`controller.md`)
for next-step guidance.
