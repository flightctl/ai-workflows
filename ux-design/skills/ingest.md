---
name: ingest
description: Problem framing, user group identification, and competitive landscape survey.
---

# Ingest — Discovery

Frame the problem, identify who it affects, and survey how others have
solved it. This phase produces the foundation that all downstream work
builds on.

## Process

### Step 1: Gather Context

Read the Jira issue, PRD, or feature description provided by the researcher.
Extract:

- **Problem statement** — what problem does this feature solve?
- **User groups** — who experiences this problem? What are their goals?
- **Existing state** — what does the product do today? What's the gap?
- **Constraints** — technical, business, or timeline constraints mentioned

If a Jira issue key was provided, fetch the issue details. If a PRD exists
at `.artifacts/prd/{issue-key}/03-prd.md`, read it for additional context.

If any external operation fails (Jira fetch, PRD lookup): note what failed,
continue with available data, and never fabricate context to fill the gap.

Explore the codebase to understand the current UI:
- What pages/views exist in the affected area?
- What components are used?
- What user flows currently exist?

### Step 2: Competitive Landscape

Search for how other products solve this problem:

- Direct competitors (similar products in the same space)
- Adjacent products (different domain, similar UX pattern)
- Design system references (PatternFly, Material, Atlassian patterns)

For each relevant example, note:
- What they do well
- What they do poorly
- Patterns worth considering or avoiding

### Step 3: Frame Strategic Decisions

Based on the problem and landscape, identify the design decisions that
need to be made to move this work forward:

- What design decisions depend on understanding user needs?
- Which assumptions need validation before the team can commit to a direction?
- What usability risks could change the approach?

### Step 4: UXD Discovery Enhancement (optional)

If `/uxd-workshop:uxd-discovery` is available, run it with the same
input source. Compare its output with the results above and merge any
additional findings into the discovery artifact:
- User groups the manual phase missed
- Competitive examples the skill surfaced
- Strategic decisions worth adding

If the skill is not available, skip this step.

## Output

`.artifacts/ux-design/{issue-key}/01-discovery.md`

```markdown
# Discovery — {issue-key}

**Date:** {date}

## Problem Statement

{1-2 paragraphs: what problem, for whom, why it matters}

## User Groups

| Group | Goals | Pain Points |
|-------|-------|-------------|
| {group} | {what they're trying to do} | {what's hard today} |

## Current State

{What the product does today in this area. Include relevant file paths
 or component references from the codebase.}

## Competitive Landscape

### {Product/Pattern A}
- **Approach:** {how they solve it}
- **Strengths:** {what works}
- **Weaknesses:** {what doesn't}

### {Product/Pattern B}
...

## Strategic Decisions

1. {Decision the team needs to make, framed as "We need to decide..."}
2. {Decision the team needs to make, framed as "We need to decide..."}
...

## Constraints

- {Technical, business, or timeline constraints}
```

## When This Phase Is Done

Present the discovery brief to the researcher:
"Here's the problem framing, user groups, and competitive landscape.
Does this capture the right scope? Any user groups, competitors, or
strategic decisions missing?"

Wait for confirmation. Then **re-read the controller** (`controller.md`)
for next-step guidance.
