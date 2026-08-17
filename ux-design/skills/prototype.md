---
name: prototype
description: Generate design prototypes informed by research findings for evaluation.
---

# Prototype — Design Exploration

Generate design prototypes based on research findings so the researcher
can react, refine, and evaluate. A rough prototype that sparks conversation
is more valuable than a polished one that can't be changed.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/01-discovery.md` for problem context,
user groups, and competitive landscape. If it doesn't exist, tell the
researcher that `/ingest` should run first and stop.

If this is a re-entry from `/evaluate`, read `03-evaluation.md` for the
issues to address in this iteration.

## Process

### Step 1: Gather Input (Interactive)

Determine what input is available for prototyping:

| Input Source | How to gather |
|-------------|--------------|
| **Jira RFE** | Fetch the issue, extract requirements and acceptance criteria |
| **Figma designs** | Run `/uxd-workshop:uxd-figma-read` to extract design context (pages, frames, tokens). If unavailable, ask the researcher to describe the relevant frames. |
| **Feature description** | Use the discovery brief and any research the researcher provides |
| **Existing prototype** | Read the current prototype for refinement (iteration from `/evaluate`) |

Ask the researcher to confirm the input source and scope before generating.

### Step 2: Extract User Stories

From the input source, extract or derive user stories:

- Map each discovery insight to one or more user stories
- Include acceptance criteria derived from discovery and any research provided
- Prioritize stories by user need priority from `01-discovery.md`

Save to `.artifacts/ux-design/{issue-key}/02-prototype/user-stories.json`.

### Step 3: Design Direction (Interactive)

Based on the research recommendations and user stories, propose 1-2
design directions:

For each direction:
- Which user needs does it prioritize?
- What's the core interaction pattern?
- What tradeoffs does it make?
- How does it compare to competitive approaches from discovery?

Present directions to the researcher. Wait for them to choose or suggest
an alternative before generating.

### Step 4: Generate Prototype

Generate a prototype of the chosen direction.

**If `/uxd-workshop:uxd-prototype-create` is available:**
Run it with the chosen input source. The skill supports two modes:
- **Auto mode:** Makes design decisions based on research findings and
  design system patterns
- **Interactive mode:** Presents design decision pages for researcher
  approval at each decision point

Ask the researcher which mode to use. Default to interactive for first
iterations, auto for refinements.

**If the skill is not available:**
Generate the prototype manually:
- If the project uses a design system (e.g., PatternFly), use documented
  components
- Create standalone HTML or integrate into the existing codebase based on
  the researcher's preference

The prototype should cover:
- Primary user flow (happy path)
- Key interaction states (empty, loading, error, populated)
- The most critical user need from research

Don't try to cover everything — prototype the riskiest or most uncertain
parts of the design first.

Always write prototype files, metadata, and rationale to
`.artifacts/ux-design/{issue-key}/02-prototype/` before or alongside any
codebase integration. The `/evaluate` phase depends on this directory.

### Step 5: Document Design Rationale

For each design decision in the prototype, trace it back to a research
finding:

- "This uses a wizard pattern because research showed users need step-by-step
  guidance (Insight #2)"
- "The empty state includes a quick-start guide because 3/5 participants
  struggled with initial setup"

## Output

`.artifacts/ux-design/{issue-key}/02-prototype/`

```
02-prototype/
├── prototype-notes.md      # Design rationale and decisions
├── user-stories.json       # Extracted user stories with acceptance criteria
├── rfe-snapshot.md          # Requirements snapshot (if sourced from Jira)
├── metadata.json            # Prototype metadata (mode, iteration, input source)
├── {prototype files}        # Generated prototype (HTML, React, screenshots)
└── iteration-{N}.md         # Notes from each iteration (if iterating)
```

`prototype-notes.md` structure:

```markdown
# Prototype — {issue-key}

**Date:** {date}
**Iteration:** {N}
**Design direction:** {chosen direction}
**Mode:** {auto / interactive}
**Input source:** {Jira RFE / Figma / feature description / refinement}

## Design Decisions

| Decision | Rationale | Research Reference |
|----------|-----------|-------------------|
| {what} | {why} | {Insight #N from research} |

## User Stories Covered

| Story | Acceptance Criteria | Status |
|-------|-------------------|--------|
| {story} | {criteria} | {covered / partial / deferred} |

## Scope

**Covered in this prototype:**
- {flow or interaction covered}

**Not yet covered:**
- {flow or interaction deferred}

## Open Questions for Evaluation

- {What should the evaluator focus on?}
- {Where is the design most uncertain?}
```

## When This Phase Is Done

Present the prototype to the researcher:
"Here's a prototype of {direction}. It covers {scope}. Review it — what
works, what doesn't, what's missing? We can iterate or move to evaluation."

Wait for confirmation. Then **re-read the controller** (`controller.md`)
for next-step guidance.
