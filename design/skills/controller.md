---
name: controller
description: Top-level workflow controller that manages phase transitions for design document creation and task decomposition.
---

# Design Workflow Controller

You are the workflow controller. Your job is to manage the design workflow by
executing phases and handling transitions between them.

## Phases

1. **Ingest** (`/ingest`) — `ingest.md`
   Read the PRD, explore the codebase, and capture architectural context.

2. **Research** (`/research`) — `research.md`
   Investigate the external problem space — existing solutions, standards,
   integration constraints, and architecture patterns. Conditional: recommended
   when the PRD involves external integrations, standards, or unfamiliar domains.

3. **Draft** (`/draft`) — `draft.md`
   Draft the design/architecture document using the template and section guidance.

4. **Decompose** (`/decompose`) — `decompose.md`
   Break the design into Jira-ready epics and stories with a coverage matrix.

5. **Revise** (`/revise`) — `revise.md`
   Incorporate user feedback into the design document and/or task breakdown. Repeatable.

6. **Publish** (`/publish`) — `publish.md`
   Post the design document as a GitHub PR for external review.

7. **Respond** (`/respond`) — `respond.md`
   Fetch and address reviewer comments on the PR. Repeatable.

8. **Sync** (`/sync`) — `sync.md`
   Sync Jira epics and stories with the approved task breakdown — create,
   update, and close.

## Workspace

Drafting happens in the **source repo** — the AI needs codebase context to
write a good design document. Publishing and review happen in a **separate
docs repo** so planning artifacts don't pollute the source tree.

### Artifact directory

All working artifacts are stored in `.artifacts/design/{issue-key}/` within
the source repo (this directory should be gitignored in the source repo):

| Artifact | File | Written by |
|----------|------|------------|
| Architectural context | `01-context.md` | `/ingest` |
| Design research | `02-research.md` | `/research` |
| Design document | `03-design.md` | `/draft`, `/revise`, `/respond` |
| Testplan | `04-testplan.md` | `/draft`, `/revise`, `/respond` |
| Provenance log | `provenance.json` | `/draft`, `/revise`, `/respond` |
| Epic metadata | `05-epics.md` | `/decompose`, `/revise` |
| Epic files | `06-stories/epic-{N}-{slug}.md` | `/decompose`, `/revise` |
| Story files | `06-stories/epic-{N}/story-{NN}-{slug}.md` | `/decompose`, `/revise`, `/respond` |
| Coverage matrix | `07-coverage.md` | `/decompose`, `/revise` |
| PR description | `08-pr-description.md` | `/publish` |
| Publish metadata | `publish-metadata.json` | `/publish` |
| Review responses | `09-review-responses.md` | `/respond` |
| Jira sync manifest | `sync-manifest.json` | `/sync` |

### Docs repo configuration

The docs repo location is stored in `.artifacts/config.json` (workspace-level
config shared across all workflows for this source repo). This config is
created by whichever workflow's `/publish` or `/ingest` phase runs first.

If the config doesn't exist when a phase needs it, the workflow prompts for
the docs repo location and creates it:

```json
{
  "docs_repo_path": "/home/user/src/planning-docs",
  "docs_repo_remote": "git@github.com:org/planning-docs.git"
}
```

`/revise` and `/respond` also read this config when they need to update the
published copy in the docs repo.

## How to Execute a Phase

1. **Announce** the phase to the user: *"Starting /draft."*
2. **Locate** the skill file — read and follow
   `../../_shared/recipes/phase-override-resolution.md` with
   WORKFLOW=`design`, PHASE_FILE=`{phase}.md`.
3. **Read** the resolved skill file
4. **Execute** the skill's steps — the user should see your progress
5. When the skill is done, it will tell you to report findings and
   re-read this controller. Do that — then use "Recommending Next Steps"
   below to offer options.
6. Present the skill's results and your recommendations to the user
7. **Stop and wait** for the user to tell you what to do next.

## Recommending Next Steps

After each phase completes, present the user with **options** — not just one
next step. Use the typical flow as a baseline, but adapt to what actually
happened.

### Typical Flow

```text
ingest → [research] → draft → decompose → [revise loop] → publish → [respond loop] → sync
```

Research is in brackets because it is conditional — not every design needs it.

### What to Recommend

**Continuing forward:**

- `/ingest` completed → recommend `/research` or `/draft` (see "When to Recommend Research" below)
- `/research` completed → recommend `/draft`
- `/draft` completed → recommend `/decompose` (decomposition validates the design), unless deferral signals are present (see "When to Recommend Deferring `/decompose`" below), in which case recommend `/publish` directly. Note that the testplan was generated alongside the design document either way.
- `/decompose` completed → recommend `/revise` for user review of the decomposition
- `/revise` completed (user satisfied) → recommend `/publish`, or another `/revise` round
- `/publish` completed → recommend `/respond` when review comments arrive
- `/respond` completed → recommend another `/respond` round, or `/sync` if approved
- `/sync` completed → workflow is done

**When to recommend `/research`:**

After `/ingest` completes, analyze the PRD context and recommend `/research`
when any of these signals are present:
- The PRD references external tools, services, or platforms to integrate with
- The PRD references industry standards, specifications, or data formats
- The feature involves a problem domain the codebase hasn't addressed before
- The PRD mentions evaluating or selecting from multiple third-party solutions

When none of these signals are present (purely internal refactors, straightforward
features building on existing patterns), recommend `/draft` directly.

When recommending `/research`, briefly explain which signals you detected:

```text
Recommended next step: /research — the PRD references integrating with
vulnerability scanners (Trivy, Grype) and CSAF/VEX data formats. Investigating
these before drafting will produce better architectural decisions.

Other options:
- /draft — if you already have sufficient domain knowledge to draft the design
```

**When to recommend deferring `/decompose`:**

`/decompose` is expensive: it writes every epic and story file, then runs a
subagent review with up to 2 fix-and-re-review rounds. Running it right
after `/draft` pays that cost once as a design-validation step — but if the
design changes substantially during `/revise` or `/respond`, the controller
recommends re-running `/decompose` from scratch, paying that cost again.
Whether this is worth it depends on how much churn the design is likely to
see, which varies per feature.

After `/draft` completes, recommend deferring `/decompose` until after the
`/revise`/`/publish`/`/respond` loop stabilizes (i.e., recommend `/publish`
directly) when any of these signals are present:
- The design document has several unresolved `[Assumption: ...]` markers
  or Open Questions with significant **Impact** — these are likely to shift
  during review
- `02-research.md` exists and flagged multiple viable approaches with no
  clear winner, or the chosen approach deviates from the research
  recommendation
- This is the first design in the codebase for this problem domain, or the
  design proposes a new architectural pattern not yet established
- The user signals the design is contentious or likely to see significant
  review pushback

When none of these signals are present (few or no open items, a
straightforward extension of established patterns), recommend `/decompose`
directly — early decomposition catches structural design gaps before a
review cycle is spent on them, and reviewers can see the epic/story scope
alongside the design during `/respond`.

When recommending deferral, explain which signals you detected and note the
trade-off:

```text
Recommended next step: /publish — the design has 3 open questions with
architectural impact (§9.1, §9.2, §9.3) that reviewers are likely to weigh
in on. Decomposing now risks a full re-run if their answers change the
design. Recommend deferring /decompose until after /respond stabilizes.

Other options:
- /decompose — if you'd rather validate decomposability now and accept the
  risk of re-running it later
- /revise — if you want to resolve the open questions yourself first
```

**Looping back:**

- `/draft` reveals PRD gaps → suggest the user switch to the **prd** workflow and run its `/clarify` phase to resolve them
- `/draft` reveals research gaps (e.g., an integration approach turns out to be more complex than assumed) → offer `/research` to investigate before continuing
- `/decompose` reveals design gaps → offer `/revise` to fix the design before continuing
- `/revise` changes the design → offer `/decompose` to regenerate the task breakdown (or, if decomposition hasn't happened yet because it was deferred, no action needed — it will run fresh against the revised design)
- `/respond` reveals the need for significant design changes → offer `/revise`
- `/respond` stabilizes with `/decompose` still deferred → recommend `/decompose` now, immediately before `/sync`

**Skipping:**

- If the user already has a design document, they may start at `/decompose`
- `/research` is always skippable — the user can go directly to `/draft` if they have sufficient domain knowledge
- If the design is for internal use only, `/publish` and `/respond` may be skipped
- If Jira sync isn't needed, `/sync` may be skipped
- `/decompose` may be deferred past `/publish`/`/respond` and run just
  before `/sync` instead — see "When to recommend deferring `/decompose`"
  above. This is a per-feature judgment call, not a fixed position in the
  phase list.

### How to Present Options

Lead with your top recommendation, then list alternatives briefly:

```text
Recommended next step: /decompose — break the design into epics and stories
to validate the design's decomposability.

Other options:
- /revise — if you want to adjust the design first
- /publish — if you're confident the design is ready for review without decomposition
```

## Starting the Workflow

Before dispatching any phase, check if the project has its own `AGENTS.md`
or `CLAUDE.md`. If so, read it — it may contain project-specific conventions,
template paths, or other guidance that affects how the workflow operates.

When the user provides a Jira issue key or URL:
1. Execute the **ingest** phase
2. After ingestion, present results and wait

When the user provides a PRD or design context in another form (text, document, URL):
1. Capture the context into `01-context.md` in the artifact directory
2. Proceed as if `/ingest` completed

If the user invokes a specific command (e.g., `/decompose`), execute that phase
directly — don't force them through earlier phases.

## Error Handling

If any phase fails (Jira MCP errors, git failures, `gh` CLI errors, codebase
exploration failures):

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional), or escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors.

## Context Management

When output quality appears to be degrading (e.g., the AI misses details,
repeats itself, or loses track of earlier decisions), consider spawning the
next phase as a subagent with a fresh context window. Load the subagent with
the skill file for the phase being executed, the relevant artifact files from
`.artifacts/design/{issue-key}/`, and any template files referenced by that
skill (`draft.md`, `revise.md`, and `respond.md` each resolve and use
`design.md` and `section-guidance.md` — see `template-override-resolution.md`).

This is a recommendation, not a requirement — not all AI runtimes support
subagent spawning.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from this file, not from skills.** Skills report findings; this controller decides what to recommend next.
- **Template loading is shared across `/draft`, `/revise`, and `/respond`.** Each resolves project-level overrides before falling back to the workflow default via `../../_shared/recipes/template-override-resolution.md`; none is more canonical than another.
- **Jira is read-only until `/sync`.** The `/ingest` phase reads from Jira but never modifies it. Only `/sync` modifies Jira issues, and only with explicit user approval.
- **Design and decomposition co-evolve.** If `/revise` changes the design, recommend re-running `/decompose`. If `/decompose` reveals design gaps, recommend `/revise`.
