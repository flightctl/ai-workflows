---
name: decompose
description: Break the design into Jira-ready epics and stories with a testplan and coverage matrix.
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
1. `.artifacts/design/{issue-key}/03-design.md` (design document)
2. `.artifacts/design/{issue-key}/01-context.md` (architectural context)
3. `.artifacts/design/{issue-key}/02-research.md` (if exists — research findings and integration constraints)
4. The PRD — use the path recorded in `01-context.md`'s PRD Summary section,
   falling back to `.artifacts/prd/{issue-key}/03-prd.md`

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

5. **Size epics.** Read `../../_shared/sizing-rubric.md` for the size
   definitions and heuristics. Epic sizes map to dev-weeks within the
   cycle. Use T-shirt sizes (XS, S, M, L, XL). **XXL is not allowed
   in the final decomposition** — if an epic sizes to XXL, it must be
   split into smaller epics before proceeding. Split by user-value
   slice, not technical layer.

### Step 4: Write Epics

This step produces two things: a metadata index (`04-epics.md`) and one file
per epic. Each epic file has a 1:1 correspondence with a Jira Epic issue —
its content is what `/sync` will push to Jira.

#### 4a: Write Epic Metadata

Write `.artifacts/design/{issue-key}/04-epics.md`:

```markdown
# Epic Breakdown — {issue-key}

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
 (Step 8) is the authoritative source for requirement-to-story traceability.}

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
`.artifacts/design/{issue-key}/05-stories/epic-{N}-{slug}.md`:

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
mkdir -p .artifacts/design/{issue-key}/05-stories/epic-{N}
```

Write each story to
`.artifacts/design/{issue-key}/05-stories/epic-{N}/story-{NN}-{slug}.md`:

**For `[DEV]`, `[UI]`, `[UX]`, `[QE]`, and `[CI]` stories:**

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

Do NOT include a `## Test Case References` section when writing stories
in Step 5 — that section is added by Step 7c after the testplan is
generated.

**For `[DOCS]` stories** (see `[DOCS]` story requirements below for the
Documentation Inputs section):

```markdown
# Story {N}.{NN}: [DOCS] {title}

**As a** {role},
**I want to** {capability},
**So that** {benefit}.

## Acceptance Criteria

- [ ] {documentation outcome — what the reader can learn or do, verifiable by reading the documentation}
- [ ] {documentation outcome}

## Documentation Scope

{Which documentation surfaces this story affects and why. Focus on what
 the reader needs to understand — not how to write it or where to put it.
 Those decisions belong to the documentation workflow or author who picks
 up the ticket.

 Example: "This feature introduces a new CLI command for managing device
 rollbacks. Users need to understand when to use rollback vs. revert,
 the required preconditions, and how to verify success."}

## Documentation Inputs

{Inventories every user-facing artifact introduced or changed by the
 feature, grouped by the implementation story that delivers it.
 See the Documentation Inputs requirements below for format details.}

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
- `[DOCS]` — documentation; uses a dedicated template (see above) with **Documentation Scope** and **Documentation Inputs** sections

If unsure of the correct prefix, use `[DEV]` as the default and note it for
user review.

**`[DOCS]` story requirements:** `[DOCS]` stories use a different template
than other story types (see above). They replace `Implementation Guidance`
and `Testing Approach` with `Documentation Scope` and `Documentation Inputs`.

The **Documentation Scope** section describes what the reader needs to
understand about the feature — not how to write the docs or where to put
them. Those decisions belong to the documentation author or workflow that
picks up the ticket. See the template example above for illustration.

The **Documentation Inputs** section inventories every user-facing artifact
introduced or changed by the feature, grouped by the implementation story
that delivers it. At design time you have the complete picture of what's
new and what changed. Capture it so the documentation author (human or AI)
gets a concrete starting point — rather than reverse-engineering the
user-visible surface from code diffs after implementation. Note that
implementation may diverge from the design, so these inputs are guidance,
not authority. The documentation author should verify against the actual
implementation.

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
  For non-`[DOCS]` stories, implementation details belong in
  Implementation Guidance. For `[DOCS]` stories, implementation details
  belong in Documentation Scope.
- For non-`[DOCS]` stories: does the Implementation Guidance give enough
  direction for an AI agent or developer to build the right thing without
  cross-referencing the design document for every decision?
- For non-`[DOCS]` stories: does the Implementation Guidance reference
  code by identifier (function names, type names, struct names), not by
  line number? Line numbers shift as the codebase evolves between design
  time and implementation time. Identifiers are robust.
- If a story has more than ~8 acceptance criteria, examine whether it can
  be split along a natural boundary.
- For `[DOCS]` stories: does the Documentation Scope describe what the
  reader needs to understand without prescribing how to write or organize
  the documentation?
- For `[DOCS]` stories: does the Documentation Inputs section list every
  user-facing artifact from the implementation stories, with enough detail
  for a documentation author to know what to look for in the implementation?

**Filename stability:** Story filenames (e.g., `story-01-scaffold-build-pipeline.md`)
serve as idempotency keys in the sync manifest. Once stories have been synced
to Jira, their filenames must not change. When revising a decomposition,
append new stories with the next available number rather than inserting or
renumbering existing ones.

### Step 6: Sizing Consistency Check

After sizing all epics, verify plausibility:

1. Read the Feature's Size from `.artifacts/prd/{issue-key}/01-requirements.md`
   (the Size field captured during PRD ingest) or from
   `.artifacts/sizing/{issue-key}/02-assessment.md` (if the sizing
   workflow was run in single-Feature mode). If neither exists, skip this
   check. Note: batch-mode sizing stores assessments under a version slug
   (e.g., `.artifacts/sizing/1-3-0/`), not per-Feature — batch assessments
   are not automatically found by this lookup.

2. Verify that the epic sizes are collectively plausible given the
   Feature's overall size.
   For example, a Feature sized M should not decompose into three L
   epics. Flag any mismatch to the user.

3. Verify no epic is sized XXL. If any is, stop and require a split
   before proceeding to Step 7.

### Step 7: Generate Testplan

Generate `.artifacts/design/{issue-key}/07-testplan.md` containing
behavioral test cases anchored to PRD requirements. This artifact serves
dev teams (cross-reference against implemented tests for completeness),
QA teams (independent coverage review without reading every story), and
ALM export (structured for tools like Polarion).

#### 7a: Derive Test Cases

For each PRD requirement (FR-N, NFR-N), examine the stories that address
it (from the epic/story files written in Step 5). For each story:

1. Read the **Acceptance Criteria** — each criterion is a candidate test
   case or a grouping of related test cases.
2. Read the **Testing Approach** — use it to understand what scenarios
   are expected.
3. Generate test cases at the behavioral/scenario level. Each test case
   describes an observable outcome verifiable against a running system.
   Do not generate unit-test-level entries — tracing unit tests to
   testplan entries is impractical and fragile.
4. After generating test cases for a story, verify that every AC on that
   story appears in at least one test case's AC field (see AC mapping
   rules below). If an AC has no test case, either add one or flag it
   in the Gaps section.

**Test case ID scheme:** `TC-{requirement-id}-{sequence}`, where
`{requirement-id}` is the PRD requirement ID with the hyphen removed
(e.g., `FR-1` → `FR1`, `NFR-3` → `NFR3`) and `{sequence}` is a
two-digit zero-padded counter within that requirement. Examples:
`TC-FR1-01`, `TC-FR1-02`, `TC-NFR3-01`.

**Test case fields** (all required per test case; the requirement is
identified by the parent section heading):

| Field | Description |
|-------|-------------|
| Test Case ID and Title | H4 heading: `#### TC-{req}-{NN}: {one-line scenario description}` |
| Story, AC, Priority, Automation | Single metadata table beneath the H4 heading |
| Preconditions | H5 section: system state required before the test |
| Steps | H5 section: what the tester does — numbered steps |
| Expected Results | H5 section: observable outcomes the tester verifies |

**Priority assignment:**
- `critical` — core user workflows or data integrity
- `high` — important but non-core requirements
- `medium` — edge cases and secondary workflows
- `low` — cosmetic or informational scenarios

**Automation assignment:**
- `automated` — the scenario will be verified by automated tests (e2e
  or feature-level integration) produced by the implementing story
- `manual` — the scenario requires human verification (visual checks,
  hardware interaction, exploratory testing, or scenarios explicitly
  scoped as manual in a `[QE]` story)

**AC mapping:**
- `AC` lists the acceptance criteria from the implementing story that
  this test case validates (e.g., `AC-1`, `AC-1, AC-3`).
- Use the numbering from the story's Acceptance Criteria section
  (first criterion = AC-1, second = AC-2, etc.).
- A test case must map to at least one AC. A single test case may
  cover multiple ACs if they describe aspects of the same scenario.

**Coverage target:** Every FR and NFR covered by at least one story
should have at least one test case. Within each story, every acceptance
criterion should be referenced by at least one test case's AC field. A
story AC with no test case mapping is a gap — flag it in the testplan's
Gaps section.

**Negative scenarios:** Include negative/error test cases where the PRD
or design specifies error handling behavior. Do not invent error
scenarios beyond what the requirements and design describe.

#### 7b: Write the Testplan

Write `.artifacts/design/{issue-key}/07-testplan.md`:

```markdown
# Testplan — {issue-key}

## Overview

Feature: {feature-key} — {feature-title}
Total test cases: {N}
Requirements covered: {N} of {total FR + NFR count}

## Test Cases

### FR-1: {requirement description}

#### TC-FR1-01: {scenario title}

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.01 | AC-1 | high | automated |

##### Preconditions

- {system state required before the test}

##### Steps

1. {what the tester does}
2. {next action}

##### Expected Results

- {observable outcome the tester verifies}

#### TC-FR1-02: {scenario title}

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-2 | medium | automated |

##### Preconditions

- {precondition}

##### Steps

1. {step}
2. {step}

##### Expected Results

- {expected outcome}

### FR-2: {requirement description}

#### TC-FR2-01: {scenario title}

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-1, AC-3 | critical | automated |

##### Preconditions

- {precondition}

##### Steps

1. {step}
2. {step}

##### Expected Results

- {expected outcome}

### NFR-1: {requirement description}

#### TC-NFR1-01: {scenario title}

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-1 | high | automated |

##### Preconditions

- {precondition}

##### Steps

1. {step}
2. {step}

##### Expected Results

- {expected outcome}

## Gaps

{For each PRD requirement with stories but no test cases: why it lacks
 coverage and a recommendation. For requirements not covered by any
 story (already flagged in the coverage matrix): note "Not testable —
 no implementing story."

 For each story AC with no test case mapping: identify the story, the
 uncovered AC, and a recommendation (add a test case, or justify why
 the AC does not warrant a behavioral test case).

 If no gaps: "All covered requirements have test cases and all story
 ACs are mapped to test cases."}

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | {N} |
| Critical | {N} |
| High | {N} |
| Medium | {N} |
| Low | {N} |
| Automated | {N} |
| Manual | {N} |
| Requirements with test cases | {N} / {total} |
| Requirements without test cases | {N} (see Gaps) |
```

Test cases are grouped under requirement headings (not by epic) because
the testplan's purpose is requirement traceability. The Story field in
each test case's metadata table links back to the epic/story structure.

#### 7c: Add Test Case References to Stories

After writing the testplan, append a `## Test Case References` section
to each non-`[DOCS]` story file. For each test case in the testplan,
its Story field identifies the implementing story. Collect all TC IDs
for each story and write them into that story's file.

Re-read each story file before appending to ensure current content.
`[DOCS]` stories do not receive this section.

The section format is a single `Verified by:` line with comma-separated
TC IDs:

```markdown
## Test Case References

Verified by: TC-FR1-01, TC-FR1-02, TC-NFR1-01
```

For stories with no behavioral test cases (e.g., infrastructure
prerequisites):

```markdown
## Test Case References

Verified by: None (infrastructure — no behavioral test cases)
```

### Step 8: Write Coverage Matrix

Write `.artifacts/design/{issue-key}/06-coverage.md`:

```markdown
# Coverage Matrix — {issue-key}

## PRD Requirement → Epic/Story Mapping

| PRD Requirement | Epic | Story | Test Cases | Status |
|-----------------|------|-------|------------|--------|
| FR-1: {description} | Epic 1 | Story 1.01, 1.02 | TC-FR1-01, TC-FR1-02 | Covered |
| FR-2: {description} | Epic 2 | Story 2.01 | TC-FR2-01 | Covered |
| FR-3: {description} | — | — | — | **GAP** |
| NFR-1: {description} | Epic 1 | Story 1.02 | TC-NFR1-01 | Covered |
| NFR-2: {description} | Epic 2 | Story 2.01 | TC-NFR2-01 | Covered |

## Gaps

{For each uncovered requirement: why it's not covered and a recommendation.
 If no gaps: "All PRD requirements are covered by the decomposition."}

## Stories Without PRD Traceability

{Any stories that don't map to a specific PRD requirement. These may be
 legitimate (e.g., infrastructure prerequisites) but should be justified.
 If none: "All stories trace to PRD requirements."}
```

### Step 9: Verify Artifact Structure

Quick sanity check before invoking the decomposition review. Verify:

1. `04-epics.md` exists and references all epic files
2. Each epic file referenced in `04-epics.md` exists (e.g.,
   `05-stories/epic-1-{slug}.md`)
3. Each epic has a corresponding story directory with story files
4. `06-coverage.md` exists and contains at least one mapping row
5. `07-testplan.md` exists and contains at least one test case entry
6. Every non-`[DOCS]` story file has a `## Test Case References` section

If structural issues are found, fix them before proceeding. Do not
invoke a review on incomplete artifacts.

### Step 10: Review Decomposition

Review the decomposition for structural quality and requirement
coverage. This review operates independently from the design document —
the reviewer evaluates what the artifacts actually say, not what the
decomposer intended.

Read `../decomposition-review.md` for evaluation criteria, finding
format, and severity definitions.

**If the AI runtime supports subagents**, spawn the review in a
subagent for independence. Load it with:

- The decomposition review protocol (`../decomposition-review.md`)
- The PRD (use the path from `01-context.md`'s PRD Summary, falling back to
  `.artifacts/prd/{issue-key}/03-prd.md`)
- All decomposition artifacts: `04-epics.md`, all
  `05-stories/epic-{N}-{slug}.md` files, all
  `05-stories/epic-{N}/story-{NN}-{slug}.md` files, `06-coverage.md`,
  `07-testplan.md`
- NOT the design document (`03-design.md`) — the reviewer evaluates
  the artifacts on their own merits

Retain the subagent's ID for use in Step 12 — resuming the same
reviewer gives it memory of its previous findings and concerns,
producing more coherent follow-up reviews.

**If subagents are not available**, perform the review inline. Read the
decomposition review protocol and apply all evaluation criteria. Adopt
the reviewer perspective: evaluate the artifacts as if you did not write
them. Do not let your knowledge of the design document excuse issues
that a reviewer seeing only the PRD and artifacts would flag.

Both paths use the same evaluation criteria, finding format, and
severity definitions from the protocol. The subagent path provides
stronger independence; the inline path still catches issues by forcing
a perspective shift.

### Step 11: Validate and Assess Findings

For each finding from Step 10:

1. **Validate the reference.** Confirm the cited artifact file and
   section exist. Discard any finding that references a file or section
   that does not exist.

2. **Cross-check PRD claims.** For findings that assert a missing
   requirement or inadequate coverage, verify the claim against the
   actual PRD. Discard findings based on misidentified requirements.

3. **Assess on value.** Does this finding genuinely improve the
   decomposition? Would the artifacts be meaningfully better (clearer
   acceptance criteria, more complete coverage, better dependency
   ordering, more appropriate sizing) if the change were made?

   - If yes: fix the issue immediately. Re-read the affected artifact
     file before modifying it. Verify the fix after applying it.
   - If no: note why the finding was dismissed (structural preference,
     no real improvement, would add churn without value).

Only fix findings that add real value. Do not make changes for
structural preferences not grounded in the evaluation criteria.

### Step 12: Re-Review (if fixes were made)

If Step 11 produced changes to the decomposition artifacts:

1. Obtain a re-review of the updated artifacts:

   **If a subagent was used in Step 10 and the runtime supports agent
   resumption:** Resume the same reviewer agent. Send it the updated
   artifacts and a summary of fixes applied. This gives the reviewer
   memory of its original findings and lets it verify they were
   addressed correctly.

   **If resumption is not available:** Spawn a new subagent loaded with
   the decomposition review protocol, the updated artifacts, the PRD
   (but NOT the design document), and a summary of the previous round's
   findings and fixes so it has full context.

   **If subagents are not available:** Re-read all decomposition artifact
   files before re-reviewing — do not rely on your cached understanding
   from the previous round. Evaluate the full artifact set (not just the
   delta from the last round).

   The re-review should focus on:
   - Whether fixes were applied correctly
   - Whether fixes introduced new issues
2. If new issues are found, fix them following the same validate-and-
   assess procedure from Step 11
3. Cap at 2 review-fix rounds total. Decomposition fixes are structural
   and less likely than code fixes to need multiple iterations.

If no fixes were needed in Step 11, the review passes immediately.

### Step 13: Report Review Summary

```markdown
## Decomposition Review Summary

- **Findings:** {total identified} ({N} after validation)
- **Fixed:** {N} findings addressed
- **Dismissed:** {N} findings ({brief rationale for each})
- **Rounds:** {N} review-fix iterations
- **Gate:** PASS | FLAG

{If any CRITICAL or HIGH findings remain unfixed, set Gate to FLAG and
list them with their file, section, and issue description.}
```

### Step 14: Present to User

Present the decomposition and highlight:
- Number of epics and stories
- Epic dependency order
- Any coverage gaps
- Stories that might need size adjustment (too large or too small)
- Any assumptions or judgment calls in the decomposition
- Decomposition review summary (from Step 13)

If the decomposition review gate reported FLAG, present the unfixed
CRITICAL/HIGH findings and ask the user to decide how to handle them.
These may indicate genuine gaps requiring user judgment — the decomposer
should not resolve them unilaterally.

## Output

- `.artifacts/design/{issue-key}/04-epics.md` (epic metadata and ordering)
- `.artifacts/design/{issue-key}/05-stories/epic-{N}-{slug}.md` (one per epic)
- `.artifacts/design/{issue-key}/05-stories/epic-{N}/story-{NN}-{slug}.md` (one per story)
- `.artifacts/design/{issue-key}/06-coverage.md`
- `.artifacts/design/{issue-key}/07-testplan.md`

## When This Phase Is Done

Report your results:
- Summary of the decomposition (epics, stories, coverage)
- Highlight any gaps, sizing concerns, or judgment calls
- Whether the decomposition validates the design (or reveals gaps)

Then **re-read the controller** (`controller.md`) for next-step guidance.
