---
name: decompose
description: Break the design into Jira-ready epics and stories with a coverage matrix.
---

# Decompose Skill

You are a technical project planner. Your job is to break a design document
into epics and stories that a development team can execute.

## Your Role

Read the design document and PRD, then produce a set of epics (with stories)
that decompose the work into right-sized, independently deliverable increments.
The decomposition must be traceable back to PRD requirements, and every story
must leave the system in a stable state.

## Critical Rules

- **Epics are user-value oriented.** Organize around user outcomes, not technical layers. "Image Building Workflow" is a good epic; "API Development" is not.
- **Each epic is standalone.** An epic delivers complete functionality and enables future epics without requiring them.
- **Every `[DEV]` story includes functionality AND testing.** Each `[DEV]` story adds a capability and the tests that validate it. Tests should validate the software's contract, not its implementation. `[DEV]` stories must include comprehensive unit tests; integration tests should be included when natural, but may be split into a separate `[DEV]` story when the integration test surface warrants it. Use the test types appropriate to what the story changes — unit tests for isolated logic, integration tests for component interactions (database, API, services), and e2e tests for user-facing workflows. Match the project's existing test infrastructure as captured in `01-context.md`.
- **`[QE]` stories track standalone e2e test automation.** The QE team owns e2e test automation, manual test execution, and negative test coverage as separate stories. These are not "just tests" — they represent dedicated QE work that tracks independently from the unit/integration tests embedded in `[DEV]` stories. Each epic should include at least one `[QE]` story when the feature has e2e-testable surface.
- **Every story leaves the system stable.** Code merges to main via CI/CD. All locally-executable tests must pass.
- **No scope reduction.** Never silently drop requirements, defer to "v2", or say "placeholder." If a requirement can't be decomposed cleanly, flag it.
- **Right-sized stories.** Not too small (process overhead) and not too large (hard to review). A story should represent a meaningful, reviewable unit of work.
- **Documentation is integrated.** Each story evaluates and updates documentation as appropriate. `[DOCS]` stories are acceptable for cross-cutting documentation that requires a holistic view (e.g., architecture overview, migration guide). For larger features, consider per-epic `[DOCS]` stories when different epics introduce distinct user-facing surfaces that benefit from focused documentation. Choose whichever structure produces the highest-quality documentation.

## Process

### Step 1: Read Source Material

Read these files:
1. `.artifacts/design/{issue-number}/03-design.md` (design document)
2. `.artifacts/design/{issue-number}/01-context.md` (architectural context)
3. `.artifacts/design/{issue-number}/02-research.md` (if exists — research findings and integration constraints)
4. `.artifacts/prd/{issue-number}/03-prd.md` (PRD — for requirement traceability)

If the design document doesn't exist, tell the user that `/draft` should be
run first.

### Step 2: Identify the Feature

Read the Jira Feature issue key from the PRD or context. This Feature is the
parent for all epics created by this workflow.

### Step 3: Plan the Decomposition

Before writing, plan:

1. **Identify natural boundaries.** Look at the design's architecture section
   for component boundaries. Each epic should align with a coherent slice
   of user-facing functionality — not a single component.

2. **Map PRD requirements to epics.** Each functional requirement from the
   PRD should have a home in at least one epic. Requirements that span
   multiple epics should be noted.

   **Requirement IDs:** If the PRD uses an explicit ID scheme (e.g., FR-1,
   FR-2 for functional; NFR-1, NFR-2 for non-functional), adopt it.
   Otherwise, assign sequential IDs to each distinct requirement extracted
   from the PRD. Reference these IDs consistently in epic/story mappings
   and the coverage matrix.

3. **Order epics by dependency.** Epic 2 may build on Epic 1, but Epic 1
   must deliver value independently. Identify the dependency chain.

4. **Distinguish dependencies from exclusions.** A PRD dependency ("X is
   delivered by another team") means this feature *uses* X but doesn't
   *build* X. An exclusion/non-goal means this feature doesn't do X at
   all. Stories should include work that uses dependencies — don't treat
   a dependency as an exclusion. For example, if test infrastructure is
   a dependency, stories still include the test code that runs on that
   infrastructure; the dependency is on *where* tests run, not *whether*
   tests exist.

5. **Size epics.** Each epic should be larger than a single sprint but fit
   within a release. Use T-shirt sizes (XS, S, M, L, XL).

### Step 4: Write Epics

This step produces two things: a metadata index (`04-epics.md`) and one file
per epic. Each epic file has a 1:1 correspondence with a Jira Epic issue —
its content is what `/sync` will push to Jira.

#### 4a: Write Epic Metadata

Write `.artifacts/design/{issue-number}/04-epics.md`:

```markdown
# Epic Breakdown — {issue-number}

## Feature

- **Key:** {feature-key}
- **Title:** {feature-title}

## Epics

| # | Epic | T-Shirt Size | Stories | PRD Requirements | Dependencies |
|---|------|-------------|---------|-----------------|--------------|
| 1 | [{title}](05-stories/epic-1-{slug}.md) | {size} | [{N} stories](05-stories/epic-1/) | FR-1, FR-2, NFR-1 | None |
| 2 | [{title}](05-stories/epic-2-{slug}.md) | {size} | [{N} stories](05-stories/epic-2/) | FR-3, NFR-2 | Epic 1 |

{PRD Requirements column: list the primary requirements for quick reference.
 If an epic maps to more than ~8 requirements, list the most significant
 and add "See coverage matrix for full mapping." The coverage matrix
 (Step 6) is the authoritative source for requirement-to-story traceability.}

## Dependency Order

{Brief description of the recommended implementation order and why.
 E.g., "Epic 1 first (provides data model), then Epic 2 and Epic 3
 can proceed in parallel."}

## Story Implementation Notes

{Per-epic notes on story ordering. Stories are numbered in recommended
 implementation order (story-01 before story-02). Note any stories
 that can proceed in parallel.}
```

#### 4b: Write Epic Files

For each epic, write
`.artifacts/design/{issue-number}/05-stories/epic-{N}-{slug}.md`:

```markdown
# Epic {N}: {title}

- **T-Shirt Size:** {XS|S|M|L|XL}

## Summary

{1-2 sentences describing what this epic delivers to users}

## Acceptance Criteria

- [ ] {behavioral outcome — what this epic delivers, testable from outside}
- [ ] {behavioral outcome}

## Design Reference

Feature: {feature-key}
PRD Requirements: {FR-1, FR-2, NFR-1, ...}
Design sections: {§4.1 Architecture, §4.3 API Changes, or relevant subsections}
```

**Naming conventions:**
- Epic number is not zero-padded: `epic-1`, `epic-2`
- Slug is kebab-case derived from the epic title: `epic-1-image-building.md`
- Gaps in epic numbering are acceptable (e.g., if epic-2 is removed during
  revision, epic-1 and epic-3 remain — do not renumber to close the gap)

### Step 5: Write Stories

For each epic, create a story directory and write one file per story. Each
story file has a 1:1 correspondence with a Jira Story issue — its content
is what `/sync` will push to Jira.

```bash
mkdir -p .artifacts/design/{issue-number}/05-stories/epic-{N}
```

Write each story to
`.artifacts/design/{issue-number}/05-stories/epic-{N}/story-{NN}-{slug}.md`:

```markdown
# Story {N}.{NN}: [{prefix}] {title}

**As a** {role},
**I want to** {capability},
**So that** {benefit}.

## Acceptance Criteria

- [ ] {behavioral outcome — what the system does, testable from outside}
- [ ] {behavioral outcome}

## Implementation Guidance

{Key design decisions, interface shapes, function/method names, patterns
 to follow, and relevant code paths from the design document. This
 section directs how to build it. Deviation is acceptable when the
 implementer discovers a better approach — provided all acceptance
 criteria are still met and the rationale for deviation is documented
 in the PR.}

## Testing Approach

{For each test type relevant to this story's changes:
 - Unit: isolated logic, mocked dependencies
 - Integration: component interactions (DB, API, services)
 - E2E: user-facing workflows in a full environment
 Match the project's test infrastructure from 01-context.md.}

## Dependencies

{Comma-separated list using the canonical format: "Story 1.01, Story 1.02"
 — always "Story" + space + epic.story number. Or "None" if no dependencies.
 This format is required for reliable reference resolution during /sync.}

## Design Reference

Epic: Epic {N} — {epic title}
PRD Requirements: {FR-1, NFR-1}
Design section: {§4.3 API Changes, or specific subsection}
```

**Naming conventions:**
- Story number is zero-padded: `story-01`, `story-02`
- Slug is kebab-case derived from the story title:
  `story-01-scaffold-build-pipeline.md`
- Stories are numbered in recommended implementation order within the epic

**Story title prefixes:** Use the appropriate prefix based on the nature of
the work:
- `[DEV]` — backend/service development
- `[UI]` — frontend/UI implementation
- `[UX]` — user experience design work
- `[QE]` — standalone e2e test automation, manual test execution, or negative test coverage owned by the QE team
- `[CI]` — CI/CD infrastructure and pipeline work
- `[DOCS]` — documentation; requires a **Documentation Inputs** section (see below)

If unsure of the correct prefix, use `[DEV]` as the default and note it for
user review.

**`[DOCS]` story requirements:** `[DOCS]` stories must include a
**Documentation Inputs** section (added between Testing Approach and
Dependencies) that inventories every user-facing artifact introduced or
changed by the feature, grouped by the implementation story that delivers it.

At design time you have the complete picture of what's new and what changed.
Capture it so the documentation author (human or AI) gets a concrete
checklist of what to cover — rather than reverse-engineering the user-visible
surface from code diffs after implementation.

Group items under bold story headers (e.g., **Story 1.01 — {title}:**)
followed by bullet points listing each user-facing artifact: new or changed
API fields/resources, CLI output or behavior, configuration options, status
values and their meanings, error messages, and UI elements. Give enough
detail that the writer knows what to look for in the implementation.

Place each `[DOCS]` story after all stories it references so that all
references are resolvable during `/sync`. For per-epic `[DOCS]` stories,
place them as the last story within their own epic. For a cross-cutting
`[DOCS]` story that spans multiple epics, place it as the last story in
the last epic.

**Story quality checks:**
- For `[DEV]` stories: does this story add a capability AND testing for that capability?
- For `[QE]` stories: does this story define concrete e2e test scenarios that validate user-facing behavior from the associated `[DEV]` stories?
- Does the system remain stable (all tests pass) after this story is merged?
- Is this story reviewable in a single PR? If not, it's too large — split it.
- Is this story meaningful? If the PR would be trivially small, consider
  combining it with an adjacent story.
- Are the acceptance criteria behavioral outcomes (what the system does),
  not implementation specifications (method names, internal structure)?
  Implementation details belong in Implementation Guidance.
- Does the Implementation Guidance give enough direction for an AI agent
  or developer to build the right thing without cross-referencing the
  design document for every decision?
- Does the Implementation Guidance reference code by identifier (function
  names, type names, struct names), not by line number? Line numbers
  shift as the codebase evolves between design time and implementation
  time. Identifiers are robust.
- If a story has more than ~8 acceptance criteria, examine whether it can
  be split along a natural boundary.
- For `[DOCS]` stories: does the Documentation Inputs section list every
  user-facing artifact from the implementation stories, with enough detail
  for a documentation author to know what to cover?

**Filename stability:** Story filenames (e.g., `story-01-scaffold-build-pipeline.md`)
serve as idempotency keys in the sync manifest. Once stories have been synced
to Jira, their filenames must not change. When revising a decomposition,
append new stories with the next available number rather than inserting or
renumbering existing ones.

### Step 6: Write Coverage Matrix

Write `.artifacts/design/{issue-number}/06-coverage.md`:

```markdown
# Coverage Matrix — {issue-number}

## PRD Requirement → Epic/Story Mapping

| PRD Requirement | Epic | Story | Status |
|-----------------|------|-------|--------|
| FR-1: {description} | Epic 1 | Story 1.01, 1.02 | Covered |
| FR-2: {description} | Epic 2 | Story 2.01 | Covered |
| FR-3: {description} | — | — | **GAP** |
| NFR-1: {description} | Epic 1 | Story 1.02 | Covered |
| NFR-2: {description} | Epic 2 | Story 2.01 | Covered |

## Gaps

{For each uncovered requirement: why it's not covered and a recommendation.
 If no gaps: "All PRD requirements are covered by the decomposition."}

## Stories Without PRD Traceability

{Any stories that don't map to a specific PRD requirement. These may be
 legitimate (e.g., infrastructure prerequisites) but should be justified.
 If none: "All stories trace to PRD requirements."}
```

### Step 7: Self-Review

Before presenting, verify:

- [ ] Every epic is organized around user value, not technical layers
- [ ] Each epic is standalone — delivers complete functionality independently
- [ ] Every `[DEV]` story includes functionality AND testing (at minimum, comprehensive unit tests)
- [ ] `[QE]` stories define concrete e2e test scenarios — they are not duplicating unit/integration tests from `[DEV]` stories
- [ ] Each epic with e2e-testable surface includes at least one `[QE]` story
- [ ] Story acceptance criteria are behavioral outcomes, not implementation specifications — implementation details are in Implementation Guidance
- [ ] Epic T-shirt sizes are assigned and reasonable
- [ ] Story title prefixes are assigned
- [ ] Coverage matrix shows all PRD requirements mapped
- [ ] No coverage gaps (or gaps are flagged explicitly)
- [ ] Story ACs collectively cover the PRD's acceptance criteria (§5), not just the FR/NFR descriptions
- [ ] Implementing all stories in dependency order would produce a working feature end-to-end — no integration work falls between stories
- [ ] No story falls back to "manual validation" or "document procedure for QE" where an automated test could be written — if the barrier is infrastructure availability (a dependency), the story includes the automated test; the dependency is on where it runs, not whether it exists
- [ ] Epic dependency order is documented
- [ ] Story implementation order within each epic is documented
- [ ] `[DOCS]` stories include a Documentation Inputs section inventorying all user-facing artifacts from implementation stories
- [ ] No scope reduction — every PRD requirement is represented

### Step 8: Present to User

Present the decomposition and highlight:
- Number of epics and stories
- Epic dependency order
- Any coverage gaps
- Stories that might need size adjustment (too large or too small)
- Any assumptions or judgment calls in the decomposition

## Output

- `.artifacts/design/{issue-number}/04-epics.md` (epic metadata and ordering)
- `.artifacts/design/{issue-number}/05-stories/epic-{N}-{slug}.md` (one per epic)
- `.artifacts/design/{issue-number}/05-stories/epic-{N}/story-{NN}-{slug}.md` (one per story)
- `.artifacts/design/{issue-number}/06-coverage.md`

## When This Phase Is Done

Report your results:
- Summary of the decomposition (epics, stories, coverage)
- Highlight any gaps, sizing concerns, or judgment calls
- Whether the decomposition validates the design (or reveals gaps)

Then **re-read the controller** (`controller.md`) for next-step guidance.
