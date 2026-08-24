---
name: handoff
description: Synthesize research, prototype, and evaluation into an implementation-ready handoff spec.
---

# Handoff — Implementation Spec

Synthesize all prior artifacts into a spec that a developer can implement
from. This is the contract between the ux-design workflow and `ui-design`.

## Dependencies

This phase requires the `uxd-workshop` skills. If the `uxd-design-handoff` skill
is not available, stop and tell the researcher to run `./install.sh` to set up
the uxd-workshop skills before proceeding.

## Prerequisites

Verify these artifacts exist before generating:
- `.artifacts/ux-design/{issue-key}/01-discovery.md` — problem context
- `.artifacts/ux-design/{issue-key}/03-prototype/` — design prototype
- `.artifacts/ux-design/{issue-key}/04-evaluation.md` — evaluation results

If any are missing, stop and ask whether to run the owning phase or proceed
with an explicit partial-handoff caveat in the output.

Read all available artifacts before proceeding. If `02-research.md` exists,
read it — it is required for the Data Annotations and Persona-Specific Views
sections below.

Read `01-discovery.md` in full — in particular its **Technical Design
Context** and **Non-Functional Requirements** sections. The design context
(architecture, API shapes, data models) is the basis for the feasibility check
in Step 4; the NFRs (accessibility targets, performance, supported browsers)
feed the Accessibility Requirements and acceptance criteria. If either section
reads "Not found," the feasibility check falls back to the evidence the phase
holds — `01-discovery.md`'s Current State and the Step 2 data classifications
(see Step 4) — and its results must be marked **unverified against the technical
design**. Do not skip the check, and do not fabricate design constraints to
satisfy it.

## Process

### Step 1: Run UXD Design Handoff

Invoke the `uxd-design-handoff` skill with the prototype files and prior
artifacts as input.

The skill handles:
- Component mapping (UI element → design system component → props/variants)
- State matrix (empty, loading, error, populated, partial, responsive)
- Interaction specs (user flows, keyboard navigation, focus management)
- Acceptance criteria in Given/When/Then format, traced to design decisions
- Accessibility requirements (WCAG, ARIA, keyboard, screen reader)
- Open questions

Pass `--design-system patternfly` if the project uses PatternFly (check
`package.json` for `@patternfly/react-core`); otherwise omit and let the
skill auto-detect.

Wait for the skill to complete. Review the output before proceeding.

**Locate and read back the skill's output.** `uxd-design-handoff` writes its
result as `design-handoff-{slug}.md` (or `.json`) into the **current working
directory** — the source-repo root — with no flag to redirect it. It does not
write into our artifact namespace. So:

1. Find the file the skill just wrote (e.g. `ls design-handoff-*.md
   design-handoff-*.json` in the repo root). If more than one matches, use the
   most recently modified.
2. Read it — this is the input for Steps 2-4.
3. After you have assembled `05-handoff.md` (Step 4), **move the skill's raw
   output into our namespace** so it is not left untracked at the repo root:
   `mv design-handoff-{slug}.md .artifacts/ux-design/{issue-key}/03-prototype/`
   (the source-repo `.gitignore` covers `.artifacts/` but not the repo root, so
   a stray `design-handoff-*.md` there can be committed by accident). If the
   file cannot be found after the skill reports success, stop and report it —
   do not fabricate the handoff content from the other artifacts alone.

### Step 2: Data Annotations

The skill does not annotate data requirements per UI element. Do this manually
using the research artifacts:

For each UI element in the component map, identify:
- What data does it display?
- Where does that data conceptually come from? Classify each into one of these
  source types — do **not** invent specific API endpoint names, service names,
  or schema fields that you have not confirmed exist in the codebase:
  - **API** — fetched from a backend service
  - **User input** — entered or selected by the user in this flow
  - **Configuration** — settings, feature flags, or environment values
  - **Computed** — derived on the client from other data
  - **Static** — hardcoded labels, copy, or constants
  - **Unknown** — source is unclear and `ui-design` must determine it
- Flag any UI state that likely has no backend support (for `ui-design` to
  investigate at implementation level)

Describe the source conceptually (e.g., "API — the list of active sessions").
Only name a concrete endpoint or field when you have verified it in the
codebase during `/ingest`; otherwise use the conceptual type and leave the
specifics for `ui-design`.

Use `02-research.md` user needs and `01-discovery.md` to inform which data
gaps are most likely to affect the design.

### Step 3: Persona-Specific Views

The skill does not document persona-specific views. Do this manually:

Check `02-research.md` for persona notes (or `01-discovery.md` user groups
if research was skipped). If multiple user groups interact differently:
- Identify which components or flows are shared vs. persona-specific
- Document persona-specific states, actions, or views
- Note permission-gated interactions

If all user groups interact identically, state that explicitly.

### Step 4: Feasibility and Phasing Check

A design that the feature's architecture cannot support is not
implementation-ready. Reality-check the proposed design against the
**Technical Design Context** captured in `01-discovery.md` (architecture, API
shapes, data models, cross-component interactions) before finalizing.

Start from the backend gaps already flagged in Step 2 (Data Annotations) — do
not re-derive them independently. Step 2 flags, per UI element, data whose
source is uncertain or likely unsupported; Step 4 reconciles those flags
against the technical design and presents the single, authoritative backend-gap
list. If Step 4 surfaces a gap Step 2 missed, add it back to the Data
Annotations table so the two sections stay consistent.

For each major design element (from the component map, interaction specs, and
the Data Annotations gaps), determine whether the technical design supports it:

- **Supported** — the architecture, an existing API shape, or an existing data
  model backs it. No action.
- **Needs backend support** — the element implies data, an endpoint, or a field
  the design document does not describe (e.g., "the list needs a child-resource
  count, but no aggregation field exists"). Record it as a structural
  observation for `ui-design`/`design` to turn into a `[DEV]` item — do **not**
  invent the endpoint or field here.
- **Requires a design change** — the gap reshapes the UX itself (e.g., a filter
  the API cannot express). Flag it; the researcher decides whether to adjust
  the design or accept it as a backend requirement.

If the collected constraints mean the full design cannot be delivered in one
feature, do **not** silently drop scope. Following the workflow's no-scope-
reduction rule, record a **Final Vision** (the complete intended UX) and a
proposed **MVP / Phase 1** (what is deliverable now given the constraints),
and present the split to the researcher. The researcher owns the phasing
decision.

If `01-discovery.md` has no Technical Design Context (design document was not
ingested), still perform the check — but against the evidence the workflow
actually holds: the **Current State** section of `01-discovery.md` (the
codebase exploration from ingest Step 6) and the data-source classifications in
Step 2 above. `/handoff` does no codebase exploration of its own, so do not
imply verification the phase cannot perform. Mark every finding **unverified
against the technical design** so reviewers know it rests on codebase
inference, not the design document.

### Step 5: Assemble the Handoff Artifact

Combine the skill's output with Steps 2, 3, and 4 into the artifact below, and
save it to `.artifacts/ux-design/{issue-key}/05-handoff.md`.
Preserve the skill's Given/When/Then acceptance criteria format — it is
more precise than a flat table and `ui-design` can consume it.

Then move the skill's raw output into the namespace and clean up the repo
root as described in Step 1.

### Step 6: Capture Provenance

`05-handoff.md` is a planning document published to the docs repo (via
`/publish`), so it carries the same provenance contract as `prd`/`design`.
Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`, `PHASE=handoff`,
`AUTHORING_MODE=skill`.

## Output

- `.artifacts/ux-design/{issue-key}/05-handoff.md`
- `.artifacts/ux-design/{issue-key}/provenance.json` (provenance log)

```markdown
# Implementation Handoff — {issue-key}

**Date:** {date}
**Research cycle:** {number of prototype-evaluate iterations}
**Design system:** {detected or specified}

## Summary

{One paragraph: what the feature is, who it's for, and the core UX rationale}

## Component Mapping

| # | UI Element | Component | Variants/Props | Notes |
|---|------------|-----------|----------------|-------|
| 1 | {element} | {component name} | {key props} | {customization needed} |

## State Matrix

| Component | Empty | Loading | Error | Populated | Partial | Responsive |
|-----------|-------|---------|-------|-----------|---------|------------|
| {name} | {behavior} | {behavior} | {behavior} | {behavior} | {behavior} | {behavior} |

## Interaction Specs

### User Flows

{Step-by-step flows from skill output}

### Keyboard Navigation

{Tab order, arrow key behavior, shortcuts}

### Focus Management

{Where focus moves after modals close, async operations, etc.}

## Data Annotations

{Written in Step 2 above — not from the skill}

| UI Element | Data Needed | Source Type | Notes / Gaps |
|------------|-------------|-------------|--------------|
| {element} | {what it displays} | {API / User input / Configuration / Computed / Static / Unknown} | {flag if backend support is uncertain} |

## Persona-Specific Views

{Written in Step 3 above — not from the skill.
 If all user groups interact identically, state that here.}

| User Group | Distinct Views or Actions | Permission Notes |
|------------|--------------------------|-----------------|
| {group} | {what's different} | {what's gated} |

## Accessibility Requirements

{From skill output — WCAG, ARIA, keyboard, screen reader notes per component.
 Reconcile against the accessibility, performance, and supported-browser NFRs
 captured in `01-discovery.md`; call out any NFR the design does not yet
 satisfy, preserving its NFR-N ID.}

## Acceptance Criteria

{From skill output — Given/When/Then format, traced to design decisions}

AC-1: {Component} — {State/Behavior}
  Given {precondition}
  When {action}
  Then {expected outcome}
  Trace: {design decision, research finding, or "Design spec"}

## Feasibility and Phasing

{Written in Step 4 above. State whether the design is verified against the
 technical design context or "unverified against the technical design" if no
 design document was ingested.}

| Design Element | Support | Notes / Backend Requirement |
|----------------|---------|-----------------------------|
| {element} | {Supported / Needs backend support / Requires design change} | {structural observation for ui-design, or the design change} |

{If constraints force a split, include both:}

**Final Vision:** {the complete intended UX}

**MVP / Phase 1 (proposed):** {what is deliverable now, and why the rest is
deferred — the researcher confirms this split}

{If the full design is deliverable as-is, state: "No phasing required — the
technical design supports the full design."}

## Open Questions

{From skill output — ambiguities or gaps needing clarification}

## Research Context

- **Discovery:** `01-discovery.md`
- **Research:** `02-research.md` (if available)
- **Prototype:** `03-prototype/`
- **Evaluation:** `04-evaluation.md`
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
