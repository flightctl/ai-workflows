---
name: handoff
description: Synthesize research, prototype, and evaluation into an implementation-ready handoff spec.
---

# Design handoff — Implementation Spec

Synthesize all prior artifacts into a spec that a developer can implement
from. This is the contract between the ux-design workflow and `ui-design`.

## Dependencies

This phase requires `uxd-design-handoff` from the `uxd-design` plugin. If the
skill is unavailable, stop and ask the researcher to run `./install.sh` before
proceeding.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/00-context.md` first. The context must
be marked `enriched` and identify the Jira Feature, a linked `[UX]` story, the
published PRD, and the published design document. A context that started from
the Feature issue or PRD alone remains exploratory and is not ready for handoff
to `ui-design`.

Verify these artifacts exist and apply to the current context before generating:
- `.artifacts/ux-design/{issue-key}/01-discovery.md` — problem context
- `.artifacts/ux-design/{issue-key}/03-prototype/` — design prototype
- `.artifacts/ux-design/{issue-key}/04-evaluation.md` — evaluation results
  (must have `Researcher review: Confirmed` and explicit
  `Authorized fixes: None` with current prototype iteration, discovery
  revision, and context revision bindings; Pending evaluations, reports
  with outstanding authorized repairs, stale Confirmed evaluations, and
  reports missing the review or context-revision field without provable
  assessed-current context and matching explicit confirmation do not
  satisfy this prerequisite; missing or unknown fields are not `None`)

The discovery brief's context revision must match `00-context.md`. The current
prototype must be recorded as reviewed against that revision, and the
evaluation must cover that same revision and active prototype iteration. If
research was run, its findings must also have a context reconciliation for the
current revision.

If any prerequisite is missing or stale, stop before invoking
`uxd-design-handoff` and before writing `05-handoff.md`. Explain which upstream
input or phase is missing, then recommend `/ingest`, `/research`, `/prototype`,
or `/evaluate` as appropriate. Do not offer a partial handoff or allow a
researcher override of the exploratory-context gate. The researcher can
continue the exploratory research and prototyping loop until the context is
enriched.

Read all available artifacts before proceeding. If `02-research.md` exists,
read it — it is required for the Data Annotations and Persona-Specific Views
sections below. If it does not exist (research was skipped), record in the
Research Context section that formal research findings were unavailable and
that `01-discovery.md` supplied the evidence.

Read `01-discovery.md` in full — in particular its **Technical Design
Context** and **Non-Functional Requirements** sections. The ingested design
document grounds the feasibility check; the PRD's NFRs feed the accessibility
requirements and acceptance criteria. If either document is listed as missing
or not ingested, the prerequisite gate fails. If a loaded document does not
specify a particular constraint, record that gap and mark the affected finding
unverified. Do not invent design constraints.

## Process

### Step 1: Run the UXD design-handoff skill

Invoke the `uxd-design-handoff` skill with the prototype files and prior
artifacts as input.

The skill handles:
- Component mapping (UI element → design system component → props/variants)
- State matrix (empty, loading, error, populated, partial, responsive)
- Interaction specs (user flows, keyboard navigation, focus management)
- Acceptance criteria in Given/When/Then format, traced to design decisions
- Accessibility requirements (WCAG, ARIA, keyboard, screen reader)
- Open questions

Pass `--design-system patternfly` if the project uses PatternFly. Check the
top-level `package.json` for `@patternfly/react-core`; for monorepos, also
check workspace package.json files (e.g., `packages/*/package.json` or
`apps/*/package.json`). If PatternFly is found anywhere, pass the flag;
otherwise omit and let the skill auto-detect.

Wait for the skill to complete. Review the output before proceeding.

**Locate and read back the skill's output.** `uxd-design-handoff` writes its
result as `design-handoff-{slug}.md` (or `.json`) into the **current working
directory** — the source-repo root — with no flag to redirect it. It does not
write into our artifact namespace. So:

1. Find the file the skill just wrote (e.g. `ls design-handoff-*.md
   design-handoff-*.json` in the repo root). If more than one matches, use the
   most recently modified. Store the selected file's exact path in
   `handoff_output`. If no file matches after the skill reports success, stop
   and report it — do not fabricate the handoff content from the other
   artifacts alone.
2. Read the file at `$handoff_output` — this is the input for Steps 2-4.
3. After you have assembled `05-handoff.md` (Step 5), **move the skill's raw
   output into our namespace** so it is not left untracked at the repo root.
   Move only the selected file:
   `mv "$handoff_output" ".artifacts/ux-design/{issue-key}/03-prototype/"`
   (the source-repo `.gitignore` covers `.artifacts/` but not the repo root, so
   a stray `design-handoff-*` file there can be committed by accident).

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
- Note permission-gated interactions — but do **not** invent permission systems
  or specific permission names that you have not confirmed exist in the codebase
  or design document. Describe permission requirements conceptually (e.g., "admin-
  only action") unless you have verified the actual permission model.

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

If an ingested design document contains no relevant architecture, API, or data
model information, perform the check against the available **Current State**
and data-source classifications, and mark affected findings **unverified
against the technical design**. `/handoff` does no codebase exploration of its
own, so do not imply verification the phase cannot perform.

### Step 5: Curate Screenshots

Select screenshots that illustrate the approved design for implementation.
These are curated references for the handoff consumer (`ui-design`), not a
dump of all raw evaluation evidence.

**Source.** The `/evaluate` phase captures screenshots into
`.artifacts/ux-design/{issue-key}/04-eval-raw/screenshots/` at Standard
and Full depth. Check whether screenshots exist in that directory.

If no screenshots exist, determine why and require an explicit decision:

- Read `04-evaluation.md` to confirm the evaluation depth used.
- If the evaluation was Quick depth or URL-only: tell the researcher
  screenshots are not available because the evaluation depth did not
  capture them.
- If the evaluation was Standard or Full but no screenshots were saved:
  tell the researcher screenshots were expected but not produced.

In either case, present the options and **wait for an explicit choice**:

*"No screenshots are available for the handoff. Choose one:*
*1. Re-run `/evaluate` at Standard or Full depth with screenshot capture*
*2. Provide screenshots directly (the researcher supplies image files)*
*3. Proceed with a text-only handoff (record this as a documented decision — `ui-design` will operate from written spec only)"*

If the researcher chooses option 3, record in the Screenshot Index section:
`Screenshots: None — {reason from evaluation depth}. Text-only handoff
authorized by researcher.`

Do not silently proceed to Step 6 without this choice. Skip the rest of
this step only after the researcher confirms option 3.

**Per-image capture provenance.** The evaluation header binds to the
overall run but does not prove each file in `04-eval-raw/screenshots/`
was captured during that run. A Quick evaluation or re-evaluation may
leave old images. Verify each candidate individually:

1. Read `04-eval-raw/screenshot-captures.json` (written by `/evaluate`).
   Each entry records `filename`, `sha256`, `context_revision`,
   `discovery_revision`, and `prototype_iteration`.
2. For each candidate file in the screenshots directory, compute its
   SHA-256 and check whether its filename **and** digest appear in the
   capture index with all three bindings (`context_revision`,
   `discovery_revision`, `prototype_iteration`) matching the current
   context. Only images that match are verified as current-run captures.
3. If the index is absent (older evaluate run that predates this
   feature) or has an empty `captures` array (Quick/URL-only depth),
   no screenshots can be verified as current. Treat this the same as
   "no screenshots exist" — do not fall back to the evaluation header
   or assume directory contents are current.
4. If no images verify as current, present the three options above.

**Researcher-supplied images.** When the researcher provides images
directly (option 2), record the researcher-provided source path in the
manifest entry's `source` field (authoring-private; omitted from the
consumer manifest by `/publish`). Require the researcher to explicitly
confirm that each supplied image reflects the current context revision,
discovery revision, and prototype iteration. Record this confirmation
alongside the source. Do not assume currency from the file alone.

**Selection criteria.** From the verified current-context screenshots,
select images that show:

1. The **primary user flow** in its populated/happy-path state
2. Each **alternate state** relevant to implementation (empty, loading, error,
   partial — choose the states present in the State Matrix)
3. Any **persona-specific view** that differs visually from the default
4. **Responsive breakpoints** if the design adapts to screen size

Do not include redundant screenshots that show the same state from
different evaluation runs.

**Curated directory.** Copy selected screenshots to
`.artifacts/ux-design/{issue-key}/screenshots/` with stable filenames:

```
screenshots/
  SS-1-{short-description}.png     (e.g., SS-1-fleet-list-populated.png)
  SS-2-{short-description}.png     (e.g., SS-2-fleet-list-empty.png)
  ...
```

Use the `SS-N` prefix as the stable identifier referenced throughout the
handoff. The short description is lowercase-hyphenated and describes the
flow or state. Keep filenames under 80 characters.

**Screenshot manifest.** Write
`.artifacts/ux-design/{issue-key}/screenshot-manifest.json` recording each
curated screenshot. The manifest enables consumers and the publish phase to
validate references, detect visual-only changes, and verify asset identity
without re-inspecting the images:

```json
{
  "issue_key": "{issue-key}",
  "context_revision": "{current context revision}",
  "prototype_iteration": "{iteration evaluated}",
  "screenshots": [
    {
      "id": "SS-1",
      "filename": "SS-1-fleet-list-populated.png",
      "sha256": "{hex digest of the image file}",
      "caption": "{One sentence describing what the screenshot shows}",
      "alt_text": "{Accessible description of the visual content}",
      "flow": "{Which user flow or state this illustrates}",
      "state": "{populated | empty | loading | error | partial | responsive | persona-specific}",
      "source": "{path to the source screenshot in 04-eval-raw/screenshots/}"
    }
  ]
}
```

Compute `sha256` by hashing the curated image file's bytes:

```bash
sha256sum ".artifacts/ux-design/{issue-key}/screenshots/{filename}" | cut -d' ' -f1
```

If `sha256sum` is unavailable, use `shasum -a 256` on the same file
and record the full digest. If neither command is available or hashing
fails, stop and ask the researcher to provide a SHA-256 tool.

If the handoff is regenerated after a new evaluation cycle, re-curate
screenshots from the updated evaluation and regenerate the manifest. The
prior manifest is overwritten.

### Step 6: Assemble the handoff artifact

Combine the skill's output with Steps 2, 3, 4, and 5 into the artifact
below, and save it to `.artifacts/ux-design/{issue-key}/05-handoff.md`.
Preserve the skill's Given/When/Then acceptance criteria format — it is
more precise than a flat table and `ui-design` can consume it.

Then move the skill's raw output into the namespace and clean up the repo
root as described in Step 1.

### Step 7: Capture Provenance

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
**Feature key:** {feature-key}
**UX story key:** {story-key}
**Context revision:** {current enriched revision}
**Prototype iteration:** {iteration evaluated}
**Evaluation cycles:** {number of `/evaluate` runs}
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

{Step-by-step flows from skill output.

When screenshots are available, embed the primary-flow screenshot
adjacent to the flow it illustrates:

![SS-1: {alt_text from manifest}](screenshots/SS-1-{description}.png)
*{caption from manifest} — Prototype iteration {N}, context revision {R}*

Place each embed immediately after the flow step(s) it depicts. Use the
resolved reference for the storage mode: a relative path for `lfs`/`git`
mode, or the external HTTPS URL for `external` mode. Both must render as
visible images in standard Markdown viewers.}

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
 technical design context. Mark individual findings "unverified against the
 technical design" when an ingested source does not establish the needed
 constraint.}

| Design Element | Support | Notes / Backend Requirement |
|----------------|---------|-----------------------------|
| {element} | {Supported / Needs backend support / Requires design change} | {structural observation for ui-design, or the design change} |

{If constraints force a split, include both:}

**Final Vision:** {the complete intended UX}

**MVP / Phase 1 (proposed):** {what is deliverable now, and why the rest is
deferred — the researcher confirms this split}

{If the full design is deliverable as-is, state: "No phasing required — the
technical design supports the full design."}

## Screenshot Index

{From Step 5. If no screenshots were captured, record the researcher's
explicit text-only decision: `Screenshots: None — {reason}. Text-only
handoff authorized by researcher.`}

{If screenshots are available, this section is the identity/metadata
index. Each screenshot is embedded **once** at the relevant flow or
state section above (User Flows, State Matrix, or Persona-Specific
Views) using `![SS-N: {alt_text}]({ref})` with a caption. This index
provides the SHA-256 checksums and revision metadata for tooling and
consumer identity verification — it is not a duplicate gallery.}

| ID | Ref | SHA-256 | Caption | State | Embedded at |
|----|-----|---------|---------|-------|-------------|
| SS-1 | `screenshots/SS-1-{desc}.png` | `{12 hex}…` | {caption} | {state} | §User Flows |

**Context revision:** {revision} | **Prototype iteration:** {N}

**Note for `ui-design`:** Open and visually inspect each image at its
embed location during `/ingest`. Do not treat this index as a substitute
for image inspection.

## Open Questions

{From skill output — ambiguities or gaps needing clarification}

## Research Context

- **Discovery:** `01-discovery.md` (context revision {revision})
- **Research:** `02-research.md` (if available)
- **Prototype:** `03-prototype/` (iteration {N})
- **Evaluation:** `04-evaluation.md` (context revision {revision})
```

## When This Phase Is Done

Present the handoff spec to the researcher:
"Here's the implementation handoff. Does this capture everything a developer
needs to build this feature? Any interaction details, data requirements,
or edge cases missing?"

Wait for confirmation. The researcher may:
- Request additions or corrections → update the spec
- Approve → the workflow is complete

After approval, update `00-context.md` to record that `05-handoff.md` is
approved against the current enriched discovery revision.

When approved, report:
- Summary of the research cycle (phases completed, iterations)
- The handoff artifact location
- Any open questions or risks for implementation

Then **re-read the controller** (`controller.md`) for next-step guidance.
