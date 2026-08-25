---
name: ingest
description: Load upstream planning context (story, PRD, design doc, siblings), frame the problem, and survey the competitive landscape.
---

# Ingest — Discovery

Load the upstream planning context the design must honor, frame the problem,
identify who it affects, and survey how others have solved it. This phase
produces the foundation that all downstream work builds on.

A `[UX]` story says *what* to design. On its own it is not enough: the PRD
says *who it's for* and *why it matters*, and the design document says *what
the architecture can actually support*. `/ingest` follows the story's
references to load both, so the handoff reflects real personas, real
non-functional targets, and real data structures — not invented placeholders.

## Dependencies

This phase requires the `uxd-workshop` skills. If the `uxd-discovery` skill
is not available, stop and tell the researcher to run `./install.sh` to set up
the uxd-workshop skills before proceeding.

## Shared-input rule

The person running `ux-design` may not be the person who ran `prd` or
`design`. Every upstream input must be loaded from a **shared** location — the
published docs repo or Jira — never from another workflow's private
`.artifacts/` directory (`.artifacts/prd/`, `.artifacts/design/`). Those are
each workflow's working directories, not interfaces.

**Failure handling:** Distinguish fatal from non-fatal input failures:

- **Fatal (hard-stop):** The core input — the `[UX]` story or feature
  description — cannot be loaded or is invalid. Stop, report the exact error,
  and offer to retry or ask the researcher to supply the input directly.
- **Non-fatal (note and continue):** An optional input (a specific sibling
  story, one document, the design system reference) is missing. Note what is
  missing in the artifact, continue with what is available, and **never
  fabricate** context to fill the gap. A downstream phase that depends on
  missing context must flag it, not paper over it.

Examples: Jira story fetch failure → fatal. One sibling story inaccessible → non-fatal.
PRD not found after docs-repo search → non-fatal (record "Not found"). Docs repo
path invalid or unreadable → fatal (can't perform the search).

## Process

### Step 1: Identify the Story and Its References

The researcher provides one of:
- A `[UX]` Jira issue key or URL (the primary, expected input)
- A feature description or problem statement (no upstream artifacts exist yet)

Extract the full Jira issue key including the project prefix (e.g., `EDM-4109`,
not `4109`). Use it as `{issue-key}` throughout the workflow — it names the
artifact directory and all downstream phases.

**If a Jira story key was provided**, fetch the story (read-only — never
create or modify Jira issues) and read its **Design Reference** section. In the
`design` workflow's output, a `[UX]` story's Design Reference names:
- its **parent epic** (`Epic: Epic {N} — {title}`, resolved to the epic's Jira
  key), used to fetch sibling stories,
- the **PRD requirements** it traces to (FR-N / NFR-N IDs), and
- the relevant **design document sections**.

The story does **not** name the feature key, but the docs repo publishes
`prd.md`/`design.md` under the **feature** directory (named for the Feature
issue), so you must resolve the feature key before Step 2 can find them. The
Jira hierarchy is fixed: **Feature → Epic → Story**. Resolve the feature key by
one of:
- fetching the **parent epic** issue (read-only) and reading its Design
  Reference `Feature: {feature-key}` line (the epic file carries it, the story
  does not), or
- walking the Jira parent chain Story → Epic → Feature and using the Feature
  issue key.

Record **three distinct keys** — the `[UX]` story key (`{issue-key}`), the
parent **epic key** (for sibling traversal in Step 3), and the **feature key**
(for the docs lookup in Step 2) — along with the referenced requirement/section
IDs. Keep them separate; they are different Jira issues and conflating them
breaks the docs lookup.

If the story has no Design Reference (or no parent epic), or the feature key
cannot be resolved, note that upstream tracing is unavailable and continue;
Step 2 will fall back to asking the researcher for the docs paths.

**If only a feature description or problem statement was provided**, there is
no story to trace. Skip the reference-following in Steps 2–3, note in the
artifact that no PRD or design document was ingested, and proceed to Step 4.
Do not invent a PRD or design context that does not exist.

### Step 2: Load the PRD and Design Document

The published PRD and design document are the authoritative upstream inputs.
They live together in the docs repo under the **feature** directory (named for
the Feature issue, e.g., `v2.1/delta-updates-EDM-4867/`), as `prd.md`
and `design.md` — *not* under the epic key or the `[UX]` story key.

#### Resolve the docs repo

Read `.artifacts/config.json` for `docs_repo_path` and `docs_repo_remote`.

The `docs_repo_path` is stored **relative to the source-repository root** so
the config is portable across machines. Resolve it to an absolute path at
runtime for validation and use.

**If the config exists**, resolve the relative path to absolute (relative to
the source-repository root), then validate: the path exists, it is a git
repository, and its remote URL matches `docs_repo_remote`. If validation fails,
tell the researcher and re-ask for the correct path and remote. Convert the new
path to relative (from source-repository root) and persist **both** the
corrected `docs_repo_path` and replacement `docs_repo_remote` to
`.artifacts/config.json`.

**If the config does not exist**, ask the researcher for the docs repo local
path and remote, validate them (resolve `~` first), then convert the path to
relative (from source-repository root) and write `.artifacts/config.json`.

Example: if the source-repository root is `/home/user/src/myproject` and the
docs repo is at `/home/user/src/myproject-docs`, store `../myproject-docs` in
`.artifacts/config.json`, not the absolute path.

#### Find and read the documents

Search the docs repo for the feature directory using the **feature key**
resolved in Step 1 (not the epic key and not the `[UX]` story key — docs are
published under the feature directory only):

```bash
find "{docs_repo_path}" -type d -name "*{feature-key}*"
```

Filter matches to directories containing `prd.md` — the PRD is the anchor
document (the `design` workflow publishes `design.md` alongside it), mirroring
`design`'s own resolution. If exactly one matches, read `prd.md` and, when
present in the same directory, `design.md`. If multiple match, present them and
ask which holds the current feature docs. If none match — or the feature key
could not be resolved in Step 1 — ask the researcher for the docs directory (or
the `prd.md`/`design.md` paths) directly; do not guess. Verify each file exists
and is readable before reading it.

Read what you find:
- **`prd.md`** — extract the user personas, feature goals, and non-functional
  requirements that shape design decisions: accessibility targets, performance
  expectations, and supported browsers/devices. Preserve FR-N / NFR-N IDs so
  the handoff can trace acceptance criteria back to them.
- **`design.md`** — extract architecture context, API shapes, data models, and
  cross-component interactions. This is what grounds the handoff's data
  annotations in real structures and lets `/handoff` reality-check the design
  against what the architecture supports.
- **`clarifications.md`**, if present alongside the PRD — note any locked
  decisions; they are binding constraints on the design.

Record the resolved paths (PRD, design, clarifications) in the artifact so
downstream phases don't repeat the lookup. If a document is genuinely absent
(e.g., design not yet published), record that it was not found — do not
substitute assumptions for it.

### Step 3: Load Sibling Stories

Understand how this `[UX]` story fits into the broader feature so the design
neither duplicates nor conflicts with adjacent work. Using the parent epic
from Step 1, fetch the other stories in the same epic (read-only) — the
`[UX]`, `[UI]`, and `[DEV]` siblings.

For each sibling, capture just enough to map the boundaries:
- its type and one-line summary,
- whether it overlaps this story's surface, and
- any explicit blocking dependency (e.g., a `[UI]` story blocked by this one).

If Jira is unavailable or the epic cannot be traversed, note that sibling
context is missing and continue.

### Step 4: Read Project Configuration and Design System

Read these from the source repo if present — they tell you the project's
actual conventions and design system, so the deliverable uses real components
rather than generic ones:
- `AGENTS.md` and `CLAUDE.md` — project conventions and AI guidance
- `docs/` — existing architecture and UI documentation
- Design-system / component-library references (e.g., PatternFly usage in
  `package.json`, a local design-system doc, or a component index)

Capture the design system name, the component set available, and any design
tokens or patterns the project standardizes on.

### Step 5: Run UXD Discovery

Invoke the `uxd-discovery` skill with the input source (the `[UX]` story key,
feature description, or problem statement) **plus the upstream context loaded
above** — the PRD personas/goals/NFRs and the design document's constraints.
Feeding it that context grounds discovery in the real feature rather than
reframing the problem from scratch.

The skill handles:
- Problem statement framing
- User group identification (goals, pain points)
- Strategic decisions (themed, with business outcomes and timelines)
- Competitive landscape survey
- Constraints and assumptions

Wait for the skill to complete and present its output. Confirm understanding
with the researcher before proceeding.

### Step 6: Current State (Codebase Exploration)

The skill does not explore the codebase. Do this manually, focused on the
affected UI area and the design system:
- What pages or views exist today in this area?
- What components (from the project's design system) are already used?
- What user flows currently exist?

If an optional external operation fails (one sibling story inaccessible, one
codebase file unreadable): note what failed, continue with available data, and
never fabricate context to fill the gap. If a core operation fails (story
identity unresolvable, docs repo path invalid): stop per the failure-handling
rule above.

### Step 7: Assemble the Discovery Artifact

Combine the loaded upstream context, the skill's output, and the codebase
exploration into the artifact below. Preserve the skill's Strategic Decisions
structure exactly — do not flatten or reformat its themed format. Where an
upstream input was not found, write "Not found" (and why) rather than omitting
the section — a downstream phase needs to know the gap exists.

## Output

`.artifacts/ux-design/{issue-key}/01-discovery.md`

```markdown
# Discovery — {issue-key}

**Date:** {date}
**Source:** {[UX] story key, or "Feature description", or "Problem statement"}
**Parent epic:** {epic key, or "None / not traced"}
**Feature:** {feature key resolved via the epic, or "None / not resolved"}

## Upstream References

- **PRD:** {resolved docs-repo path, or "Not found — <reason>"}
- **Design document:** {resolved docs-repo path, or "Not found — <reason>"}
- **Clarifications:** {resolved path, or "None published"}
- **Traced requirements:** {FR-N / NFR-N IDs from the story's Design
  Reference, or "None traced"}

## Problem Statement

{From skill output — 1-2 paragraphs: what problem, for whom, why it matters}

## PRD Context

{From the PRD. If not found, state that and why.}

- **Personas:** {who the feature is for}
- **Feature goals:** {what success looks like}
- **Locked decisions:** {from clarifications, if any — binding constraints}

### Non-Functional Requirements

{Accessibility targets, performance expectations, supported browsers/devices —
 preserve NFR-N IDs. These flow into the handoff's accessibility requirements
 and acceptance criteria. If the PRD specifies none, say so.}

## Technical Design Context

{From the design document — this grounds the handoff and enables the
 feasibility check in /handoff. If not found, state that and why; /handoff
 will flag its feasibility check as unverified.}

- **Architecture:** {relevant components and how they interact}
- **API shapes:** {endpoints/contracts the UI will consume, at the structural
  level — do not invent fields}
- **Data models:** {existing structures the UI displays or manipulates}
- **Cross-component interactions:** {how this piece connects to adjacent work}

## Sibling Stories

{From the epic. If not traced, say so.}

| Story | Type | Summary | Overlap / Dependency |
|-------|------|---------|----------------------|
| {key} | {[UX]/[UI]/[DEV]} | {one line} | {shared surface, blocking dep, or none} |

## Design System

{Name of the design system, available component set, and tokens/patterns the
 project standardizes on. From Step 4. If none is defined, state that.}

## User Groups

### {Group Name}
- **Description:** {who they are}
- **Goals:** {what they want to accomplish}
- **Pain points:** {current frustrations}

## Current State

{What the product does today in this area. Include relevant file paths
 or component references from the codebase. Written in Step 6 above.}

## Strategic Decisions

{From skill output — themed, with business outcomes and timelines.
 Preserve the skill's structure exactly.}

## Competitive Landscape

{From skill output}

## Constraints

{From skill output, plus any binding constraints from the design document or
 PRD locked decisions.}

## Assumptions to Validate

{From skill output — framed as testable hypotheses}
```

## When This Phase Is Done

Present the discovery brief to the researcher:
"Here's the problem framing with the PRD and design context it's grounded in,
the user groups, and the competitive landscape. Does this capture the right
scope? Any user groups, competitors, strategic decisions — or upstream context
— missing or wrong?"

Call out explicitly any upstream input that was **not found**, so the
researcher can decide whether to supply it before proceeding.

Wait for confirmation. Then **re-read the controller** (`controller.md`)
for next-step guidance.
