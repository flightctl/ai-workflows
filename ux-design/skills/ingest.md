---
name: ingest
description: Problem framing, user group identification, and competitive landscape survey.
---

# Ingest — Discovery

Frame the problem, identify who it affects, and survey how others have
solved it. This phase produces the foundation that all downstream research
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

If any external operation fails (Jira fetch, PRD lookup, competitive search)
or returns zero results: note what failed, continue with available data, and
never fabricate context to fill the gap.

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

### Step 3: Frame Research Questions

Based on the problem and landscape, identify the open questions that
user research should answer:

- What do we not know about user needs?
- Where do our assumptions need validation?
- What usability risks exist in the current approaches?

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

## Research Questions

1. {Specific, answerable question}
2. {Specific, answerable question}
...

## Constraints

- {Technical, business, or timeline constraints}
```

## When This Phase Is Done

Present the discovery brief to the researcher:
"Here's the problem framing, user groups, and competitive landscape.
Does this capture the right scope? Any user groups, competitors, or
research questions missing?"

Wait for confirmation. Then **re-read the controller** (`controller.md`)
for next-step guidance.
