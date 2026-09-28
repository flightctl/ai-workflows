---
name: ingest
description: Start Feature-scoped exploration, then enrich it with the PRD, design document, and linked UX story.
---

# Ingest — Discovery and Context Enrichment

Load the available feature context, frame the problem, identify who it affects,
and survey how others have solved it. A Feature can seed early research and
exploratory prototyping before a PRD or design document exists. Those artifacts
remain exploratory until `/ingest` enriches the same Feature context with the
published PRD, design document, and linked `[UX]` story.

Use the Feature key as the stable artifact key for all work on that feature.
When ingest starts from a `[UX]` story, resolve its Feature key and use that
Feature's artifact directory; keep the story key as a separate linked input.

## Dependencies

This phase requires `uxd-discovery` from the `uxd-research` plugin. If the
skill is unavailable, stop and ask the researcher to run `./install.sh` before
proceeding.

## Shared-input rule

The person running `ux-design` may not be the person who ran `prd` or
`design`. Every upstream input must be loaded from a **shared** location — the
published docs repo or Jira — never from another workflow's private
`.artifacts/` directory (`.artifacts/prd/`, `.artifacts/design/`). Those are
each workflow's working directories, not interfaces.

**Failure handling:** Distinguish fatal from non-fatal input failures:

- **Fatal (hard-stop):** The core input — a Jira Feature, a `[UX]` story, or a
  feature description — cannot be loaded or is invalid. Stop, report the exact error,
  and offer to retry or ask the researcher to supply the input directly.
- **Non-fatal (note and continue):** An optional input (a specific sibling
  story, one document, the design system reference) is missing. Note what is
  missing in the artifact, continue with what is available, and **never
  fabricate** context to fill the gap. A downstream phase that depends on
  missing context must flag it, not paper over it.

Examples: Jira Feature or story fetch failure → fatal. One sibling story
inaccessible → non-fatal. PRD not found after docs-repo search → non-fatal
(record "Not found"). A docs-repo path that is invalid during enrichment is
fatal; during initial Feature-only exploration it is optional, so record that
planning documents could not be checked and continue.

## Process

### Step 1: Identify the Feature Context

The researcher provides one of:
- A Jira Feature issue key or URL
- A `[UX]` Jira story key or URL
- A feature description or problem statement

Fetch Jira issues read-only and inspect their issue type before following
references. Keep the Feature key (`{issue-key}`) separate from any linked
`[UX]` story key (`{story-key}`). `{issue-key}` names the stable artifact
directory for every phase in this feature context. If the input is a Jira
Feature, use its key. If the input is a `[UX]` story, resolve the Feature key
through the parent chain or the epic's `Feature:` Design Reference, as below.
For a description without a Jira Feature, ask for a stable artifact key and
prefer a supplied Feature key; otherwise use a descriptive key such as
`description-<slug>`.

**If a Jira Feature key was provided**, fetch the Feature and use its title,
description, goals, and acceptance information as the initial source. Do not
look for a parent epic or sibling stories. If no context directory exists, this
is an initial ingest. Load published planning documents in Step 2 when a docs
repo is already configured. If no docs repo is configured, continue without
setting one up; record that PRD/design documents were not checked and skip
Steps 2–3. If the documents are not published, record that and skip Step 3.
Continue with Step 4 and produce an exploratory brief. Do not imply that a
missing PRD or design document was reviewed.

**If a Jira `[UX]` story key was provided**, fetch the story (read-only — never
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

Record the Feature key as `{issue-key}`, the `[UX]` story key as `{story-key}`,
and the parent epic key separately. Also record the referenced requirement and
design-section IDs. These are distinct issues; do not use the story key or epic
key as the artifact-directory key or docs lookup key.

If the story has no Design Reference (or no parent epic), or the Feature key
cannot be resolved, note that upstream tracing is unavailable and ask the
researcher for the Feature key or the PRD/design paths. Do not silently create a
story-key artifact directory when this feature already has a context directory.

**If only a feature description or problem statement was provided**, there is
no Jira issue to trace. Skip reference-following and sibling lookup, record that
the PRD and design document were not ingested, and continue with an exploratory
brief. Do not use a descriptive artifact key for Jira queries or imply that a
Jira issue exists.

**When a context directory already exists**, treat this invocation as context
enrichment only when it adds a newly available PRD, design document, or linked
`[UX]` story. Read `00-context.md` and the current discovery, research,
prototype, and evaluation artifacts before writing. If the same sources are
already recorded and their contents are unchanged, resume the current context
without incrementing its revision. Compare document content and available
version or last-updated metadata, not only paths. When inputs have changed,
increment the context revision and preserve the previous active artifacts under
`history/context-r{N}/` before replacing any current artifact. Never overwrite
a history snapshot.

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
repository, and its remote URL matches `docs_repo_remote`. If validation fails
during initial Feature-only exploration, record that the docs repo could not
be checked and continue. Otherwise, tell the researcher and re-ask for the
correct path and remote. Revalidate the new path and remote using the same
checks (path exists, is a git repository, remote URL matches). After successful
validation, convert the new path to relative (from source-repository root) and
persist **both** the corrected `docs_repo_path` and replacement
`docs_repo_remote` to `.artifacts/config.json`.

**If the config does not exist**, an initial Jira Feature ingest can continue
without docs-repo setup: record that planning documents were not checked and
skip this step. For a `[UX]` story ingest or context enrichment, ask for the
docs repo local path and remote, validate them (resolve `~` first), then
convert the path to relative (from source-repository root) and write
`.artifacts/config.json`.

Example conversion:
```
Source repository root: /home/user/src/myproject
Docs repository path:   /home/user/src/myproject-docs
Store in config.json:   ../myproject-docs
```

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
ask which holds the current feature docs. If none match during an initial
Feature ingest, record that the planning documents are not published and
continue exploratory work. Otherwise, if no match exists or the Feature key
could not be resolved, ask the researcher for the docs directory (or the
`prd.md`/`design.md` paths) directly; do not guess. For enrichment, verify each
required file exists and is readable before reading it.

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

For a `[UX]` story input, understand how it fits into the broader feature so
the design neither duplicates nor conflicts with adjacent work. Using the
parent epic from Step 1, fetch the other stories in the same epic (read-only) —
the `[UX]`, `[UI]`, and `[DEV]` siblings. If the input is a Feature or a
description without a linked story, record that story-level scope is not yet
available and skip this step.

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
Feature key, feature description, or problem statement) **plus the upstream
context loaded above**. In an initial Feature-only ingest, use only the Feature
content and clearly label resulting assumptions and strategic decisions as
exploratory. When enriching an existing context, use the newly loaded PRD,
design document, story, and sibling context to update the prior framing rather
than treating discovery as a fresh feature.

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
never fabricate context to fill the gap. If a core operation fails (Feature or
story identity unresolvable, docs repo path invalid during enrichment): stop
per the failure-handling rule above.

### Step 7: Assemble the Discovery Artifact

Combine the loaded upstream context, the skill's output, and the codebase
exploration into the artifact below. Preserve the skill's Strategic Decisions
structure exactly — do not flatten or reformat its themed format. Where an
upstream input was not found, write "Not found" (and why) rather than omitting
the section — a downstream phase needs to know the gap exists.

## Output

`.artifacts/ux-design/{issue-key}/01-discovery.md`

Maintain `.artifacts/ux-design/{issue-key}/00-context.md` as the context
manifest. It records the Feature key, linked `[UX]` story key(s), current
context revision, context state (`exploratory` or `enriched`), source-document
paths, the active research basis, and the prototype iteration and evaluation
that have been reviewed against the current context.

Use the Feature key as `{issue-key}` for all artifacts in this feature context.
For a description without a Jira Feature, use the stable key agreed in Step 1.
Create context revision 1 on the first ingest. Mark the context `exploratory`
when the PRD, design document, or linked `[UX]` story has not been ingested.
Mark it `enriched` only after the PRD and design document are loaded and a
linked `[UX]` story is recorded. Add `Context revision` and `Context state` to
`01-discovery.md`.

When enriching an existing context, preserve the previous active artifacts
under `.artifacts/ux-design/{issue-key}/history/context-r{N}/` before replacing
any current artifact. Include the current manifest, discovery brief, research
findings, prototype, and evaluation when present. Do not overwrite a history
snapshot. Include an existing handoff in the snapshot and mark it stale in the
current manifest after the revision changes. After comparing old and new inputs, add a context-change assessment
to `00-context.md`: list what changed and whether prior research findings and
prototype decisions are retained, need revalidation, or are superseded. Mark
research as requiring review until its findings are reconciled, keep the
prototype's latest-reviewed revision unchanged until `/prototype` reviews it,
and mark evaluation and any prior handoff stale for the new revision. A prior
evaluation becomes current only after `/evaluate` assesses the active prototype
against the current revision. The assessment guides the next phase; it does not
make carry-forward decisions for the researcher.

Use this structure for `00-context.md`:

```markdown
# UX Design Context — {feature-key-or-stable-key}

- **Feature key:** {key or "None — description-based context"}
- **Linked [UX] story keys:** {keys or "None yet"}
- **Context revision:** {number}
- **Context state:** {exploratory / enriched}
- **PRD:** {path or status}
- **Design document:** {path or status}
- **Active research:** {research revision, discovery revision, current/review required}
- **Active prototype:** {iteration, original discovery revision, latest reviewed revision}
- **Active evaluation:** {evaluation revision, prototype iteration, discovery revision, depth, current/stale}
- **Active handoff:** {discovery revision, pending/approved/stale or "Not generated"}

## Context Change Assessment

{For each enrichment, summarize the new inputs and their impact on prior
research, prototype decisions, and evaluation results.}
```

```markdown
# Discovery — {issue-key}

**Date:** {date}
**Source:** {Feature key, [UX] story key, feature description, or problem statement}
**Context revision:** {revision number}
**Context state:** {exploratory / enriched}
**Parent epic:** {epic key, or "None / not traced"}
**Feature:** {feature key, or "None / not resolved"}

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

{From the design document — this grounds the feasibility check in /handoff.
 If not found, state that and why; the context remains exploratory and the
 handoff gate stays closed.}

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

Wait for confirmation. Then write the approved revision and context state to
`00-context.md`, and **re-read the controller** (`controller.md`) for next-step
guidance. When this was an enrichment, present the context-change assessment
and wait for the researcher to confirm the carry-forward plan before
recommending further research, prototyping, or evaluation.
