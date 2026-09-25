---
name: prototype
description: Generate design prototypes informed by research findings for evaluation.
---

# Prototype — Design Exploration

Generate prototypes that let the researcher react to a design direction and
iterate before handoff. A prototype should focus on the riskiest user flows and
states rather than polish that cannot yet be validated.

## Dependencies

This phase requires `uxd-prototype-create` from the `uxd-prototype` plugin. If
the skill is unavailable, stop and ask the researcher to run `./install.sh`.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/01-discovery.md` for the problem, user
groups, and competitive landscape. If it is missing, ask for an equivalent
problem framing. If none is available, recommend `/ingest` and stop.

When returning from `/evaluate`, read `04-evaluation.md` and use the
researcher-approved findings to guide the next iteration.

## Process

The create skill conducts its own onboarding and extracts user stories. This
phase sets a strategic direction from discovery and research, supplies the
answers already agreed with the researcher, and maps the generated artifacts
into the UX Design namespace.

### Step 1: Set the Design Direction

Using `01-discovery.md` and `02-research.md` when present, propose one or two
design directions. For each, identify the user needs it prioritizes, the core
interaction pattern, its tradeoffs, and how it compares with patterns from
discovery. Present the directions and wait for the researcher to choose or
suggest another.

Settle the create skill's onboarding answers with the researcher:

- **Source:** Jira RFE, Figma link, feature description, or idea from discovery.
  Pass a Figma link directly to `uxd-prototype-create`; it reads Figma itself.
  Do not also run `uxd-figma-read` for the same source.
- **Workspace:** `standalone` or a local path / Git URL for the codebase to
  prototype in. The create skill clones a workspace into its artifact area.
- **Decisions:** use `human` for an initial prototype so the researcher chooses
  among design options; use `auto` for a refinement when the researcher wants
  the skill to recommend options. `skip` is the upstream default and means no
  decision kit, so pass a choice explicitly.

### Step 2: Generate the Prototype

Invoke the skill with the source and agreed choices. For example:

```text
uxd-prototype-create "{source}" --workspace "{path-or-standalone}" --decisions human
```

For a refinement, use the same prototype ID and `--decisions auto` after
staging the evaluator artifacts described below. `--workspace` is the codebase
to build in; `--target` is only a later MR/PR destination. Do not pass a target
unless the researcher requested publishing and approved the destination.

Keep the scope focused on:

- The primary user flow
- Important empty, loading, error, and populated states
- The user need with the greatest uncertainty or risk

The new create skill also records user journeys and page scenarios. Preserve
those artifacts because its evaluate and export skills consume them.

**Runtime paths:** Upstream skill files refer to `CLAUDE_SKILL_DIR` and
`CLAUDE_PLUGIN_ROOT`. Claude Code supplies those variables. In other runtimes,
resolve the installed create skill at
`${HOME}/.uxd-ai-skills/plugins/uxd-prototype/skills/uxd-prototype-create` and
the plugin root at `${HOME}/.uxd-ai-skills/plugins/uxd-prototype`. Set the
expected variable for a helper invocation or substitute its absolute path.
Do not assume a plugin path based on another runtime.

### Refinement After `/evaluate`

`uxd-prototype-create refine {ID}` now reads
`.artifacts/{ID}/eval/evaluation-report.csv` and
`.artifacts/{ID}/eval/refinement-suggestions.json`. It no longer reads
`reviews/summary.md` or accepts the former `--mode` flag.

Before refining:

1. Restore the prototype's native layout under `.artifacts/{ID}/` from the
   mirrored files in `03-prototype/` as described in Step 3.
2. If Full evaluation ran, copy `evaluation-report.csv` and
   `refinement-suggestions.json` from the private evaluator run directory
   (`04-eval-raw/prototype-evaluate/{run-id}/.artifacts/{ID}/eval/`) into
   `.artifacts/{ID}/eval/`.
3. If those evaluator inputs do not exist, do not invent them. Start a new
   `uxd-prototype-create` run with the source and researcher-approved feedback
   as context instead of using `refine`.

Invoke refinement as:

```text
uxd-prototype-create refine {ID} --decisions auto
```

After it finishes, mirror the updated outputs and remove the temporary native
`.artifacts/{ID}/` directory. Do not leave the only copy of the refined
prototype in native skill scratch.

### Step 3: Map Skill Output Into Our Artifact Structure

The create skill writes to `.artifacts/{ID}/`, where `{ID}` is the Jira key or a
slug. Mirror its output under
`.artifacts/ux-design/{issue-key}/03-prototype/`, preserving the prototype's
native layout so a refinement can restore it without flattening files.

**Standalone prototype:**

- `.artifacts/{ID}/prototype/` → `03-prototype/prototype/`

**Workspace prototype:**

- `.artifacts/{ID}/code/` contains the cloned codebase and prototype changes.
  Preserve it under `03-prototype/code/` or record its durable path; note the
  prototype's app entry point in `prototype-notes.md`.
- Mirror `changeset.md` and `workspace-analysis.json` to `03-prototype/`.

**Create metadata:** mirror each file when the skill produces it:

- `rfe-snapshot.md`
- `metadata.json`
- `user-stories.json`
- `journeys.json`
- `scenarios.json`
- `prototype-summary.yaml`
- `prototype-bar.json`
- `verification.json`
- `decisions/` and `exports/`, when present

`rfe-snapshot.md` and `metadata.json` are required. If either is missing, stop
and report that prototype creation did not complete. The new evaluator can
consume `rfe-snapshot.md` and `decisions/` when staged into its private run
root. Record the create skill's `{ID}` in `prototype-notes.md`.

Once the canonical copies are mirrored, remove the native `.artifacts/{ID}/`
created by the create skill. The evaluator uses a separate private run root
under `04-eval-raw/`; do not move its outputs into `.artifacts/{ID}/` except
for the two temporary refinement inputs described above.

## Step 4: Document Design Rationale

For each significant design decision, connect it to a research finding or
researcher direction. If neither supports it, identify it as an assumption.
Do not invent research evidence.

## Output

`.artifacts/ux-design/{issue-key}/03-prototype/`

```text
03-prototype/
├── prototype-notes.md        # Direction, rationale, and open questions
├── iteration-{N}.md          # Notes for each iteration
├── prototype/                # Standalone prototype, when applicable
├── code/                     # Workspace clone and prototype, when applicable
├── user-stories.json         # User stories and acceptance criteria
├── journeys.json             # Primary user journeys
├── scenarios.json            # On-load scenarios per page
├── rfe-snapshot.md           # Frozen source requirements
├── metadata.json             # Prototype metadata and decision mode
├── prototype-summary.yaml    # Machine-readable summary
├── prototype-bar.json        # Prototype Bar configuration
├── changeset.md              # Workspace mode only
├── workspace-analysis.json   # Workspace mode only
├── verification.json         # Workspace mode only
├── decisions/                # When decisions are auto or human
└── exports/                  # When export was requested
```

`prototype-notes.md` records:

```markdown
# Prototype — {issue-key}

**Date:** {date}
**Iteration:** {N}
**Skill prototype ID:** {ID}
**Design direction:** {chosen direction}
**Prototype mode:** {standalone / workspace}
**Decision mode:** {skip / auto / human}
**Input source:** {Jira RFE / Figma / feature description / idea}

## Design Decisions

| Decision | Rationale | Research Reference |
|----------|-----------|-------------------|
| {what} | {why} | {finding or researcher direction} |

## User Stories Covered

| Story | Acceptance Criteria | Status |
|-------|-------------------|--------|
| {story} | {criteria} | {covered / partial / deferred} |

## Scope

**Covered in this prototype:**
- {flow or interaction covered}

**Not yet covered:**
- {flow or interaction not represented}

## Open Questions for Evaluation

- {What should the evaluator focus on?}
- {Where is the design most uncertain?}
```

Present the prototype and its scope to the researcher. Wait for feedback before
revising or recommending `/evaluate`, then re-read `controller.md` for
next-step guidance.
