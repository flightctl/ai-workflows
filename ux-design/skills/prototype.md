---
name: prototype
description: Generate design prototypes informed by research findings for evaluation.
---

# Prototype — Design Exploration

Generate design prototypes based on research findings so the researcher
can react, refine, and evaluate. A rough prototype that sparks conversation
is more valuable than a polished one that can't be changed.

## Dependencies

This phase requires the `uxd-workshop` skills. If the `uxd-prototype-create`
skill is not available, stop and tell the researcher to run `./install.sh` to
set up the uxd-workshop skills before proceeding.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/01-discovery.md` for problem context,
user groups, and competitive landscape. If it doesn't exist, ask the
researcher if they have an equivalent problem framing (PRD, feature brief,
or description). If they do, use it as context. If not, tell the researcher
that `/ingest` should run first and stop.

If this is a re-entry from `/evaluate`, read `04-evaluation.md` for the
issues to address in this iteration.

## Process

The `uxd-prototype-create` skill runs its own conversational onboarding
(what to prototype, workspace mode, decision mode, decision depth) and extracts
user stories itself. This phase's job is **not** to duplicate that — it is to
(1) set the strategic design direction grounded in discovery and research,
(2) hand the skill the answers it needs so it does not re-ask what we already
know, and (3) map the skill's output into our artifact structure so `/evaluate`
and `/handoff` can find it.

### Step 1: Set the Design Direction (Interactive)

Using `01-discovery.md` (and `02-research.md` if it exists), propose 1-2
strategic design directions before generating anything:

For each direction:
- Which user needs does it prioritize?
- What's the core interaction pattern?
- What tradeoffs does it make?
- How does it compare to competitive approaches from discovery?

Present directions to the researcher. Wait for them to choose or suggest an
alternative. This is higher-level than the skill's per-decision "auto vs.
decide" choice — it sets the direction the skill then executes within.

Also settle, from context, the answers to the skill's onboarding questions so
you can supply them rather than making the researcher answer twice:
- **Source:** the input identified in discovery (Jira RFE, Figma link, or the
  feature description). If Figma is the source, pass the Figma link directly to
  the `uxd-prototype-create` skill — it reads Figma itself; do not pre-run
  `uxd-figma-read` (that would read the design twice with no defined handoff).
- **Workspace mode:** codebase integration vs. standalone HTML.
- **Decision mode:** interactive (`decide`) for first iterations, auto for
  refinements — confirm with the researcher.

### Step 2: Generate the Prototype

Invoke the `uxd-prototype-create` skill, supplying the answers settled in
Step 1 as flags/arguments (`--workspace`, `--mode`, and the source) so its
onboarding does not re-ask them. Let the skill drive its own user-story
extraction and design-decision workflow within the chosen direction.

Scope the prototype to the riskiest, most uncertain parts first:
- Primary user flow (happy path)
- Key interaction states (empty, loading, error, populated)
- The most critical user need from research

Don't try to cover everything — a rough prototype that sparks conversation
beats a polished one that can't change.

**Runtime note (script-backed steps).** Some `uxd-prototype-create` steps run
Python helpers via `python3 ${CLAUDE_SKILL_DIR}/scripts/...`. `CLAUDE_SKILL_DIR`
is set by Claude Code; under Cursor or Gemini it is unset. Before the skill runs
those helpers, check it (`printenv CLAUDE_SKILL_DIR`). If it is empty, resolve
the skill's directory from the deterministic install path
`${HOME}/.uxd-ai-skills/plugins/uxd-workshop/skills/uxd-prototype-create` and
substitute that path inline for every `${CLAUDE_SKILL_DIR}` in the command
(e.g. `CLAUDE_SKILL_DIR=<path> python3 <path>/scripts/<script>`). If neither the
variable nor that install path resolves to a real `scripts/` directory, **stop
and report it** — do not silently skip the script-backed step. (`./install.sh`
clones the skills to `${HOME}/.uxd-ai-skills`; an upstream change to how the skill
resolves its scripts would remove this workaround.)

#### Re-entry from `/evaluate` (refinement)

If this is a re-entry from `/evaluate`, use the skill's refinement mode instead
of regenerating. The refine mode does **not** read our `04-evaluation.md`; it
reads the skill's own native input, `.artifacts/{ID}/reviews/summary.md`. So two
things must be true before you invoke it:

1. **The native layout exists.** In a continued session only our mirrored copies
   under `.artifacts/ux-design/{issue-key}/03-prototype/` may remain. Recreate
   `.artifacts/{ID}/` from them exactly as `/evaluate` Step 4 describes (read
   `{ID}` from `prototype-notes.md`; stage the prototype artifacts and skill
   metadata back). Use the same file sets defined in Step 3 below.
2. **`reviews/summary.md` holds the findings to fix.** If `/evaluate` ran at
   Standard/Full depth, `uxd-prototype-evaluate` wrote `reviews/summary.md`,
   which `/evaluate` mirrored to `03-prototype/reviews/summary.md`; stage it
   back to `.artifacts/{ID}/reviews/summary.md`. If `/evaluate` ran at Quick
   depth, that file does
   **not** exist, so write it yourself from the researcher-confirmed findings in
   `04-evaluation.md`, using the skill's expected shape: a Markdown list of
   issues, each with a title, severity (S1-S4), the affected
   component/screen, and the recommended fix. (This input contract is implicit
   in the skill today.)

Then invoke refine against the same ID:

```
/uxd-prototype-create refine {ID}
```

Refine edits the native `.artifacts/{ID}/prototype/` in place. **After it
finishes, run Step 3** to re-mirror the refined output back into
`03-prototype/` and clean up the native scratch. Do not skip this — otherwise the
refined prototype is left only in native scratch (which the next `/evaluate`
would delete) while a stale copy lingers in `03-prototype/` and gets restored
over it.

### Step 3: Map Skill Output Into Our Artifact Structure

`uxd-prototype-create` writes to its own native location, `.artifacts/{ID}/`
(where `{ID}` is derived from the Jira key — the same value as our
`{issue-key}` — or a generated slug). Our workflow and `/evaluate` expect the
output under `.artifacts/ux-design/{issue-key}/03-prototype/`. **Mirror the
files listed below, preserving the native layout** so `/evaluate` can stage them
back losslessly — do not flatten the `prototype/` subdirectory into the metadata
files. Two distinct sets, kept separate:

**Prototype artifacts** — the contents of the skill's `prototype/` subdirectory
(HTML/React/CSS/JS and any screenshots):

- `.artifacts/{ID}/prototype/` → `.artifacts/ux-design/{issue-key}/03-prototype/prototype/`

**Skill metadata** — the files at the `{ID}` root (copy each to the
`03-prototype/` root, *not* into the `prototype/` subdir):

- `rfe-snapshot.md` — **always produced** (the skill's Step 3 saves it for
  every source, including the Figma-link and feature-description fallbacks, not
  only Jira) and a **required** input to `uxd-prototype-evaluate`. Never skip it.
- `metadata.json` — always produced; also required by `uxd-prototype-evaluate`.
- `user-stories.json`
- `prototype-summary.yaml` — the skill's designated machine-readable summary
  for downstream skills; mirror it even though `uxd-prototype-evaluate` doesn't
  require it today
- `reviews/` — if present (created by `/evaluate` when it stages evaluation
  findings back for refinement); preserves `reviews/summary.md` across refinement
  iterations

In **workspace mode** the prototype lives in the codebase, not in
`.artifacts/{ID}/prototype/`, so the `prototype/` subdir may be absent. In that
case also mirror the two workspace-mode files (both consumed by
`uxd-prototype-evaluate` in workspace mode) and record where the integrated
prototype lives:

- `changeset.md` → `03-prototype/changeset.md`
- `workspace-analysis.json` → `03-prototype/workspace-analysis.json`
- Note the in-codebase location of the integrated prototype in
  `prototype-notes.md`

"Omit any the skill did not produce" applies only to the **mode-specific** files
(the `prototype/` subdir and `changeset.md`/`workspace-analysis.json` are
mutually exclusive by mode). `rfe-snapshot.md`, `metadata.json`, and
`user-stories.json` are produced in **every** mode and every source, so always
mirror them; if one is missing, the skill run was incomplete, so stop and report
rather than proceeding. Of these, `rfe-snapshot.md` and `metadata.json` are
**required inputs** to `uxd-prototype-evaluate`; `user-stories.json` is mirrored
for completeness (no downstream skill reads it today). Record the skill's `{ID}`
in `prototype-notes.md` (see Output) — `/evaluate` needs it to re-invoke
`uxd-prototype-evaluate` against the same files.

**Clean up skill scratch (artifact isolation).** The skill's native
`.artifacts/{ID}/` is a sibling of our namespace, *outside*
`.artifacts/ux-design/`, and nothing else cleans it up. Once the canonical
copies are mirrored above, remove `.artifacts/{ID}/` so it does not leak
outside the workflow's private namespace (`AGENTS.md` artifact-isolation rule).
`/evaluate` and refinement recreate it on demand from the mirror when needed.

The mirror set above is what `uxd-prototype-evaluate` and `refine --mode=auto`
consume; it intentionally omits the skill's `decisions/` directory
(`decisions.json`, decision pages, `strategy-brief.md`) and `verification.json`,
which only `refine --mode=decide` reads. Because this workflow recommends `auto`
for refinements (Step 1), that history is not needed across the mirror round-trip.
If a researcher deliberately runs a `decide`-mode refinement, add `decisions/`
and `verification.json` to the mirror set so the decision history survives the
`.artifacts/{ID}/` cleanup.

### Step 4: Document Design Rationale

For each design decision in the prototype, trace it back to a research
finding:

- "This uses a wizard pattern because research showed users need step-by-step
  guidance (Insight #2)"
- "The empty state includes a quick-start guide because 3/5 participants
  struggled with initial setup"

## Output

`.artifacts/ux-design/{issue-key}/03-prototype/`

```
03-prototype/
├── prototype-notes.md        # Design rationale and decisions (this phase)
├── iteration-{N}.md          # Notes from each iteration, if iterating (this phase)
├── prototype/                # Generated prototype files (HTML/React/CSS/screenshots)
├── reviews/                  # Evaluation findings for refinement (from /evaluate)
│   └── summary.md            # Findings summary (created by uxd-prototype-evaluate)
├── user-stories.json         # User stories with acceptance criteria (from the skill)
├── rfe-snapshot.md           # Requirements snapshot (always produced; required by evaluator)
├── metadata.json             # Prototype metadata (mode, iteration, input source)
├── prototype-summary.yaml    # Machine-readable summary for downstream skills
├── changeset.md              # Workspace-mode only
└── workspace-analysis.json   # Workspace-mode only
```

The `prototype/` subdirectory and the metadata files (`user-stories.json`,
`rfe-snapshot.md`, `metadata.json`, `prototype-summary.yaml`, and in workspace
mode `changeset.md`/`workspace-analysis.json`) are produced by
`uxd-prototype-create` and mirrored here in Step 3, preserving the native
layout. `prototype-notes.md` and `iteration-{N}.md` are written by this phase.

`prototype-notes.md` structure:

```markdown
# Prototype — {issue-key}

**Date:** {date}
**Iteration:** {N}
**Skill prototype ID:** {ID from uxd-prototype-create — /evaluate needs this}
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
