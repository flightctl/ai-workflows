---
name: handoff
description: Synthesize research, prototype, and evaluation into an implementation-ready handoff spec.
---

# Handoff — Implementation Spec

Synthesize all prior artifacts into a spec that a developer can implement
from. This is the contract between the ux-design workflow and `ui-design`.

## Prerequisites

Verify these artifacts exist before generating:
- `.artifacts/ux-design/{issue-key}/01-discovery.md` — problem context
- `.artifacts/ux-design/{issue-key}/03-prototype/` — design prototype
- `.artifacts/ux-design/{issue-key}/04-evaluation.md` — evaluation results

If any are missing, stop and ask whether to run the owning phase or proceed
with an explicit partial-handoff caveat in the output.

Read all available artifacts before proceeding.

## Process

### Step 1: Component Mapping

Map each UI element in the validated prototype to specific design system
components:

- If the project uses PatternFly, map to PatternFly components
- Reference the component's documented API/props
- Note any customization or composition required

### Step 2: Interaction Specification

Document every user interaction:

- What happens on click, hover, focus, blur
- Form validation behavior (when, how, error messages)
- Loading states and transitions
- Navigation flow between views
- Keyboard interaction and shortcuts

### Step 3: State Enumeration

List every state the UI can be in:

- **Empty** — no data yet, first-time experience
- **Loading** — data being fetched
- **Populated** — normal use with data
- **Error** — something went wrong (inline, toast, page-level)
- **Partial** — some data loaded, some failed
- **Responsive** — behavior at each breakpoint

### Step 4: Data Annotations

For each UI element that displays data, annotate what data it needs:

- What information does this element display?
- Where does that data come from conceptually (not a specific API field —
  that is `ui-design`'s job)
- Flag any data that may not exist in the backend — elements the UI
  needs that the API may not currently support

This gives `ui-design` the information it needs to map UI elements to API
endpoints and identify gaps.

### Step 5: Persona-Specific Views

Check `02-research.md` for persona notes. If multiple user groups interact
differently with the feature:

- Identify which components or flows are shared vs. persona-specific
- Document persona-specific states, actions, or views
- Note permission-gated interactions (actions available to admins but
  not viewers, etc.)

If all user groups interact identically, note that explicitly rather than
omitting this section.

### Step 6: Acceptance Criteria

Write testable acceptance criteria derived from research findings:

- Each criterion traces to a user need from research
- Each criterion is verifiable (pass/fail, not subjective)
- Include accessibility criteria from evaluation findings
- Cover persona-specific acceptance criteria where user groups differ

### Step 7: Research Context Summary

Summarize the key research decisions so developers understand *why*,
not just *what*:

- Why this pattern over alternatives
- Which user needs drove each major decision
- What tradeoffs were made and why

### Step 8: UXD Enhancement (optional)

If `/uxd-workshop:uxd-design-handoff` is available, run it with the
handoff artifact (`05-handoff.md`) as input. Compare its output with the
spec above and strengthen the artifact with any additions:
- Missing state enumerations
- Acceptance criteria gaps
- Component mapping refinements

If the skill is not available, skip this step.

## Output

`.artifacts/ux-design/{issue-key}/05-handoff.md`

```markdown
# Implementation Handoff — {issue-key}

**Date:** {date}
**Research cycle:** {number of prototype-evaluate iterations}

## Summary

{One paragraph: what the feature is, who it's for, and the core UX rationale}

## User Stories

{Derived from research insights — what users need and why}

- As a {user group}, I need to {action} so that {outcome}.
- ...

## Component Mapping

| UI Element | Component | Props/Config | Notes |
|------------|-----------|-------------|-------|
| {element} | {component name} | {key props} | {customization needed} |

## Page Layout

{Description of the page structure — sections, regions, responsive behavior.
 Reference prototype files for visual context.}

## Interaction Specs

### {Interaction area}
| Trigger | Action | Result |
|---------|--------|--------|
| {user action} | {system behavior} | {outcome} |

### Form Behavior
| Field | Validation | Error Message |
|-------|-----------|---------------|
| {field} | {rule} | {message} |

## States

| State | What to show | Behavior |
|-------|-------------|----------|
| Empty | {description} | {interactions available} |
| Loading | {description} | {skeleton, spinner, etc.} |
| Error | {description} | {recovery actions} |
| Populated | {description} | {standard interactions} |

## Responsive Behavior

| Breakpoint | Layout Changes |
|-----------|---------------|
| Desktop (>1200px) | {behavior} |
| Tablet (768-1200px) | {behavior} |
| Mobile (<768px) | {behavior} |

## Data Annotations

{For each UI element that displays data, describe what information it
 shows and where that data conceptually comes from. Flag anything the
 UI needs that may not exist in the backend.}

| UI Element | Data Needed | Notes / Gaps |
|------------|-------------|--------------|
| {element} | {what it displays} | {flag if backend support is uncertain} |

## Persona-Specific Views

{If multiple user groups interact differently with this feature, document
 those differences here. If all groups interact identically, state that.}

| User Group | Distinct Views or Actions | Permission Notes |
|------------|--------------------------|-----------------|
| {group} | {what's different} | {what's gated} |

## Accessibility Requirements

{From evaluation findings — specific a11y requirements}

- {requirement with WCAG reference}
- ...

## Acceptance Criteria

| # | Criterion | Personas | Traces to |
|---|-----------|----------|-----------|
| AC1 | {testable criterion} | {all / specific group} | {Insight #N / User Need #N} |
| AC2 | {testable criterion} | {all / specific group} | {Insight #N / User Need #N} |

## Research Context

{Why these decisions were made — link to prior artifacts for full detail}

- **Discovery:** `01-discovery.md`
- **Research:** `02-research.md`
- **Prototype:** `03-prototype/`
- **Evaluation:** `04-evaluation.md`

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| {what} | {why, traced to research} | {what was rejected and why} |
```

## When This Phase Is Done

Present the handoff spec to the researcher:
"Here's the implementation handoff. Does this capture everything a developer
needs to build this feature? Any interaction details, data requirements,
or edge cases missing?"

Wait for confirmation. The researcher may:
- Request additions or corrections → update the spec
- Approve → the workflow is complete

When approved, report:
- Summary of the research cycle (phases completed, iterations)
- The handoff artifact location
- Any open questions or risks for implementation

Then **re-read the controller** (`controller.md`) for next-step guidance.
