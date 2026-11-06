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
- **Every `[DEV]` story includes functionality AND testing.** Each `[DEV]` story adds a capability and the tests that validate it — or, for a justified behavior-preserving prerequisite, restructures existing code and includes tests demonstrating that existing behavior is preserved. Tests should validate the software's contract, not its implementation. `[DEV]` stories must include comprehensive unit tests; integration tests should be included when natural, but may be split into a separate `[DEV]` story when the integration test surface warrants it. Use the test types appropriate to what the story changes — unit tests for isolated logic, integration tests for component interactions (database, API, services), and e2e tests for user-facing workflows. Match the project's existing test infrastructure as captured in `01-context.md`.
- **`[QE]` stories track standalone e2e test automation.** The QE team owns e2e test automation, manual test execution, and negative test coverage as separate stories. These are not "just tests" — they represent dedicated QE work that tracks independently from the unit/integration tests embedded in `[DEV]` stories. Each epic should include at least one `[QE]` story when the feature has e2e-testable surface.
- **Every story leaves the system stable.** Code merges to main via CI/CD. All locally-executable tests must pass.
- **No scope reduction.** Never silently drop requirements, defer to "v2", or say "placeholder." If a requirement can't be decomposed cleanly, flag it.
- **Right-sized stories.** Not too small (process overhead) and not too large (hard to review). A story should represent a meaningful, reviewable unit of work.
- **Prerequisite refactoring stories.** Substantial, necessary, behavior-preserving refactoring that the feature depends on may be decomposed into separate stories when it is independently reviewable and mergeable. Each prerequisite story must explicitly justify why it is necessary for the feature, state which feature stories depend on it, and include tests demonstrating that existing behavior is preserved. Keep small, cohesive supporting cleanup within the feature story that motivates it — only extract a prerequisite when the refactoring is substantial enough to warrant independent review. Do not invent user-visible capabilities or requirement mappings to justify infrastructure work; prerequisite stories trace to the feature stories they enable, not directly to PRD functional requirements.
- **Documentation is integrated.** Each story evaluates and updates documentation as appropriate. `[DOCS]` stories are acceptable for cross-cutting documentation that requires a holistic view (e.g., architecture overview, migration guide). For larger features, consider per-epic `[DOCS]` stories when different epics introduce distinct user-facing surfaces that benefit from focused documentation. Choose whichever structure produces the highest-quality documentation.

## Process

### Step 1: Load Source Material and Identify Feature

Read these files:
1. `.artifacts/design/{issue-key}/03-design.md` (design document)
2. `.artifacts/design/{issue-key}/01-context.md` (architectural context)
3. `.artifacts/design/{issue-key}/02-research.md` (if exists — research findings and integration constraints)
4. The PRD — use the path recorded in `01-context.md`'s PRD Summary section
5. All validation artifacts (primary testplan and any companions)

Resolve the validation index script and discover artifacts:

```bash
VALIDATION_INDEX_SCRIPT="${HOME}/.ai-workflows/design/scripts/validation_index.py"
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{issue-key}"
```

The command outputs a JSON array of artifact entries. Read each
listed file. If the command exits non-zero (no index), fall back to
reading `04-testplan.md` directly (legacy single-testplan behavior).

If the design document doesn't exist, tell the user that `/draft` should be
run first.

If neither the validation index nor `04-testplan.md` exists, tell the user
that `/draft` should be run first.

Read the Jira Feature issue key from the PRD or context. This Feature is the
parent for all epics created by this workflow.

**If decomposition artifacts already exist** (`05-epics.md`,
`06-stories/`, or `07-coverage.md`), this is a repeat `/decompose`.
Load and reconcile existing artifacts before planning:

1. Read `05-epics.md`, all `06-stories/epic-{N}-{slug}.md` files, all
   `06-stories/epic-{N}/story-{NN}-{slug}.md` files, and
   `07-coverage.md` (if it exists — a prior run interrupted before
   Step 7 may not have produced coverage; it will be rebuilt in
   Step 7 from the retained decomposition artifacts).
2. Record all existing qualified identities (epic numbers, story
   numbers, filenames, containing paths) including files with
   `status: removed`.
3. Preserve existing numbers, qualified identities, paths, and removal
   markers — do not overwrite mismatched existing IDs, delete and
   recreate files, or reuse retired numbers. New stories and epics
   append strictly above the highest existing number (including
   retired).
4. If an existing identity conflicts with the new plan (e.g., the
   same epic number maps to a different slug), require clarification
   rather than silently repurposing.
5. Files with `status: removed` remain on disk with their numbers
   reserved. Do not silently re-activate retired work; explicit
   approved restoration is required to reopen a removed item.
6. Do not decide or apply retirement markers during inventory
   loading — the new plan does not exist yet. Existing `status:
   removed` markers discovered in sub-step 2 are preserved as-is;
   new retirement decisions wait until after planning (see the
   reconciliation sub-step at the end of Step 2).

The initial empty decomposition (no prior artifacts) still works
unchanged — these constraints apply only to repeat runs.

### Step 2: Plan the Decomposition

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

#### Per-story retention assessment (repeat `/decompose` only)

On a repeat `/decompose`, before reconciliation: for each existing
story loaded in Step 1, match its qualified ID, path, and
requirement mapping against the current verified PRD/design and the
epic plan above. Explicitly determine whether each story is
retained in the active plan or intentionally retired, with the
requirement mapping or reason for each decision.  Distinguish a
child's own disposition from inherited inactivity: a child whose
parent epic is being retired is not itself individually retired
unless the plan separately drops that child.

A retained epic alone is not sufficient input for reconciliation —
account for its child stories individually. Use current known
planned work only; do not anticipate future implementation facts.
Unclassified or ambiguous identity must not default to removal or
repurposing; complete the planning assessment or seek clarification
under existing rules before any status mutations.

Already-retired files (with `status: removed` discovered in
Step 1) stay retired unless explicit approved restoration is
required. Do not silently restore, move, or copy old IDs when
requirements return. Any retained child requires its original
parent epic to be active.

These are ordinary planning notes that feed the reconciliation
sub-step below — no new persistent retention artifact, manifest,
or status enum is required.

#### Reconcile retained inventory against the new plan

On a repeat `/decompose` only (existing artifacts were loaded in
Step 1): compare the retained inventory from Step 1 against the
plan produced above. For each artifact that the plan individually
and explicitly retires, add `status: removed` to its YAML
frontmatter (the `---`-delimited block at the very start of the
file — this is what `read_frontmatter` and `has_removed_status`
examine; a plain Markdown body line is not recognized).  When
only a parent epic is retired, mark the parent only — do not
add `status: removed` to its child stories; children inherit the
parent's inactive status through cascade without needing their
own markers.  Preserve each child's original frontmatter and
body unless the current plan separately retires that child.
Merge into any existing frontmatter; do not clobber other fields
or prepend a second frontmatter block. If the file has no
frontmatter, add a valid opening and closing `---` block before
the first Markdown heading. Example:

```yaml
---
status: removed
---
```

Keep an epic active if any of its child stories are retained in
the new plan — only mark an epic `status: removed` when all its
child work is intentionally retired. This preserves cascade
safety: marking an epic removed logically retires all its
children, so a partially-retained epic must stay active. Never
delete artifact files; do not reuse retired numbers. Missing or
incomplete inventory from Step 1 is never evidence that work
should be retired — only an explicit planning decision to drop
work from the active plan triggers retirement.

### Step 3: Write Epics

This step produces two things: a metadata index (`05-epics.md`) and one file
per epic. Each epic file has a 1:1 correspondence with a Jira Epic issue —
its content is what `/sync` will push to Jira.

#### 3a: Write Epic Metadata

Write `.artifacts/design/{issue-key}/05-epics.md`:

```markdown
# Epic Breakdown — {issue-key}

## Feature

- **Key:** {feature-key}
- **Title:** {feature-title}

## Epics

| # | Epic | T-Shirt Size | Stories | PRD Requirements | Dependencies |
|---|------|-------------|---------|-----------------|--------------|
| 1 | [{title}](06-stories/epic-1-{slug}.md) | {size} | [{N} stories](06-stories/epic-1/) | FR-1, FR-2, NFR-1 | None |
| 2 | [{title}](06-stories/epic-2-{slug}.md) | {size} | [{N} stories](06-stories/epic-2/) | FR-3, NFR-2 | Epic 1 |

{PRD Requirements column: list the primary requirements for quick reference.
 If an epic maps to more than ~8 requirements, list the most significant
 and add "See coverage matrix for full mapping." The coverage matrix
 (Step 7) is the authoritative source for requirement-to-story traceability.}

## Dependency Order

{Brief description of the recommended implementation order and why.
 E.g., "Epic 1 first (provides data model), then Epic 2 and Epic 3
 can proceed in parallel."}

## Story Implementation Notes

{Per-epic notes on story ordering. Stories are numbered in recommended
 implementation order (story-01 before story-02). Note any stories
 that can proceed in parallel.}
```

On a repeat `/decompose`, the index reflects the active plan from
Step 2 — list active epics only. Retired epic files are retained
on disk for identity audit but are not included in the active
index table.

#### 3b: Write Epic Files

For each active epic (no `status: removed`), write or update
`.artifacts/design/{issue-key}/06-stories/epic-{N}-{slug}.md`.
Do not rewrite retired epic files — their `status: removed`
frontmatter must be preserved:

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

### Step 4: Write Stories

For each active epic, create a story directory and write one file per
story. Do not fabricate directories or story files for retired epics.
Each story file has a 1:1 correspondence with a Jira Story issue — its
content is what `/sync` will push to Jira.

```bash
mkdir -p .artifacts/design/{issue-key}/06-stories/epic-{N}
```

Write each story to
`.artifacts/design/{issue-key}/06-stories/epic-{N}/story-{NN}-{slug}.md`:

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
Interface Changes: {IC-1, IC-2}
Validated by: {TC-FR1-01, TC-FR3-02}
```

`Interface Changes` lists the ICs from the design's §5 that this story
implements. `Validated by` lists the TCs from the testplan that validate
the behavior this story delivers. These references are populated in
Step 6 after stories are written.

**For `[DOCS]` stories** (see `[DOCS]` story quality criteria below):

```markdown
# Story {N}.{NN}: [DOCS] {product/feature/command — document title}

**As a** {specific reader — e.g., fleet administrator, application developer},
**I want to** {concrete task — what the reader will learn or accomplish},
**So that** {benefit — why this documentation matters to the reader}.

## Acceptance Criteria

- [ ] {reader-verifiable documentation outcome — what the reader can learn or do, verifiable by reading the documentation}
- [ ] {reader-verifiable documentation outcome}

## Documentation Scope

{Which documentation surfaces this story affects and why. Focus on what
 the reader needs to understand — not how to write it or where to put it.
 Those decisions belong to the documentation workflow or author who picks
 up the ticket.

 Example: "This feature introduces a new CLI command for managing device
 rollbacks. Operators need to understand when to use rollback vs. revert,
 the required preconditions, and how to verify success."}

## Documentation Inputs

{Inventories all known, planned user-facing inputs within this DOCS
 story's declared scope, grouped by the relevant DEV/UI story that
 delivers each artifact.
 See the Documentation Inputs requirements below for format details.}

## Dependencies

{Comma-separated list using the canonical format: "Story 1.01, Story 1.02"
 — always "Story" + space + epic.story number. Or "None" if no dependencies.
 This format is required for reliable reference resolution during /sync.}

## Design Reference

Epic: Epic {N} — {epic title}
PRD Requirements: {FR-1, NFR-1}
Design section: {§4.3 API Changes, or specific subsection}
Contributing stories: {Story 1.01, Story 1.02 — DEV/UI stories whose user-facing artifacts this DOCS story covers}
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

**`[DOCS]` story quality criteria:** `[DOCS]` stories use a different
template than other story types (see above). They replace `Implementation
Guidance` and `Testing Approach` with `Documentation Scope` and
`Documentation Inputs`. The criteria below define what a well-formed
`[DOCS]` story contains at design time. These same criteria are used by
the decomposition review (criterion #8), by `/revise` and `/respond`
when changes affect `[DOCS]` stories, and by `/sync` as a pre-sync
validation gate.

1. **Searchable title.** The title must keep the `[DOCS]` prefix and
   include recognizable product, feature, or command terms that make the
   story findable in Jira search and backlog views — e.g.,
   `[DOCS] Device rollback command reference` rather than
   `[DOCS] Feature documentation`. Use terms already established by the
   PRD or design; do not invent identifiers or version strings that are
   not yet known.

2. **Explicit reader and task.** The persona/goal/benefit statement must
   name the actual documentation reader (e.g., "fleet administrator,"
   "application developer") and a concrete task — not a generic role
   like "user" or a process-oriented goal like "have documentation."

3. **Reader-verifiable acceptance criteria.** Each AC must describe a
   documentation outcome verifiable by reading the published
   documentation — what the reader can learn, look up, or accomplish by
   following the documented procedure. Do not require implementation
   artifacts (merged PRs, CI status) that do not exist at design time.

4. **Documentation Scope.** Describes what the reader needs to understand
   about the feature — not how to write the docs or where to put them.
   Those decisions belong to the documentation author or workflow that
   picks up the ticket. See the template example above for illustration.

5. **Complete Documentation Inputs.** Inventories all known, planned
   user-facing inputs within this DOCS story's declared scope, grouped
   by the relevant `[DEV]` or `[UI]` implementation story that delivers
   each artifact. Include only contributing story types that are
   relevant — a feature with no `[UI]` stories should not reference UI
   stories, and vice versa. At design time the DOCS story's scope
   defines which inputs belong here. Capture them so the documentation
   author (human or AI) gets a concrete starting point — rather than
   reverse-engineering the user-visible surface from code diffs after
   implementation.

   Group items under bold story headers (e.g., **Story 1.01 — {title}:**)
   followed by bullet points listing each user-facing artifact: new or
   changed API fields/resources, CLI output or behavior, configuration
   options, status values and their meanings, error messages, and UI
   elements. Give enough detail that the writer knows what to look for in
   the implementation.

   **Fact/assumption distinction.** Mark each input's confidence level
   using the design document's source markers:
   - Items derived from the design document or PRD are **planned** (no
     marker needed — they are the default).
   - Items that fill gaps not specified by the PRD or design must be
     marked `[Assumption]`.
   - Items awaiting resolution of an open question must be marked
     `[Open: §9.N]` referencing the design document's open question.

   Implementation may diverge from the design, so these inputs are
   guidance, not authority. The documentation author should verify
   against the actual implementation.

6. **Contributing stories reference.** The Design Reference section must
   include a `Contributing stories` line listing every `[DEV]` and/or
   `[UI]` story whose user-facing artifacts this `[DOCS]` story covers.
   This must be consistent with the stories referenced in Documentation
   Inputs. Use the canonical `Story N.NN` format.

7. **Stable identity.** Once a story file is created, its qualified
   identity — epic number, story number, filename, and containing
   path — is fixed. Story content (title, AC, scope) may change; the
   file must not be renamed, renumbered, or moved to a different epic.
   New stories append strictly above the highest existing number in
   their epic, including retained removed files; gaps are allowed and
   retired numbers must not be reused. When planning the initial
   decomposition, prefer placing `[DOCS]` stories after their
   referenced contributors as a best-effort optimization for first-
   sync resolution, but this ordering is never a later gate or
   permission to renumber. `/sync` verifies that every story
   referenced in Contributing stories AND Dependencies has a Jira key
   in the manifest before rendering a `[DOCS]` story's description;
   if any key is missing, the write is deferred to the next explicit
   `/sync` invocation.

**Story quality checks:**
- For `[DEV]` stories: does this story add a capability AND testing for that capability? For a justified behavior-preserving prerequisite, does it restructure existing code AND include tests demonstrating preserved behavior?
- For `[QE]` stories: does this story define concrete e2e test scenarios that validate user-facing behavior from the associated `[DEV]` stories?
- For prerequisite refactoring stories: does this story justify why it is necessary, state which feature stories depend on it, and include tests demonstrating preserved behavior? Is the refactoring substantial enough to warrant independent review, or should it stay with the feature story that motivates it?
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
- For `[DOCS]` stories: does the story satisfy all seven `[DOCS]` story
  quality criteria above (searchable title, explicit reader/task,
  reader-verifiable AC, documentation scope, complete documentation
  inputs with fact/assumption distinction, contributing stories
  reference, stable identity)?

**Identity stability:** Story filenames (e.g., `story-01-scaffold-build-pipeline.md`)
serve as idempotency keys in the sync manifest. Once created, filenames
and story numbers are fixed — they must not be renamed, renumbered, or
moved regardless of whether `/sync` has been run. Append new stories with
the next available number (above any existing or removed file's number);
do not insert, reuse retired numbers, or renumber existing stories.

### Step 5: Sizing Consistency Check

After sizing all active epics, verify plausibility:

1. Read the Feature's Size from the Jira Feature issue (`{issue-key}`).
   Check the Size field (or Story Points, if Size is not set). If the
   Jira lookup fails (authentication error, network failure, issue not
   found), stop and report the error — do not skip silently. Skip this
   check only if the issue was retrieved successfully and neither field
   is set.

2. Verify that the epic sizes are collectively plausible given the
   Feature's overall size.
   For example, a Feature sized M should not decompose into three L
   epics. Flag any mismatch to the user.

3. Verify no epic is sized XXL. If any is, stop and require a split
   before proceeding to Step 6.

### Step 6: Add Implementation References to Stories

For each non-`[DOCS]` story written in Step 4, populate the `Interface
Changes` and `Validated by` fields in the Design Reference section.

**Map stories to Interface Changes.**

For each non-`[DOCS]` story, determine which Interface Changes (IC-N)
from the design's §5 the story implements. Use the story's Design
section reference and Implementation Guidance to identify which ICs
align with the story's scope.

A story implements an IC when it delivers part or all of the behavior
that IC describes. One story may implement multiple ICs, and one IC
may be implemented across multiple stories.

**Map stories to test cases.**

For each non-`[DOCS]` story, determine which test cases from the
validation artifacts (read in Step 1) validate the behavior the story
delivers. Search across ALL validation artifacts (primary testplan and
any companions) — a story's `Validated by` line collects TC IDs
regardless of which artifact file contains them.

**IC-based matching (primary):** If a test case exercises IC-3 and the
story implements IC-3, the story is validated by that test case.

**Requirement-based matching (fallback for cross-cutting TCs):** Test
cases with `Interface Change: —` have no IC to match on. For these,
match by requirement overlap: if the test case covers a requirement
and the story's PRD Requirements include that requirement, the story
is validated by that test case.

For stories that implement ICs with no corresponding test cases across
any validation artifact (identified in the testplan's IC coverage
gaps), note this — the story's `Validated by` line should read:
`Validated by: None — {reason from testplan gaps}`

**Write references.**

Re-read each active non-`[DOCS]` story file (written in Step 4). Update the `Interface Changes`
and `Validated by` lines in the Design Reference section:

```markdown
Interface Changes: IC-1, IC-2
Validated by: TC-FR1-01, TC-FR3-02, TC-FR7-01
```

For infrastructure prerequisite stories that implement no ICs:

```markdown
Interface Changes: None — infrastructure prerequisite
Validated by: None — infrastructure prerequisite
```

For behavior-preserving prerequisite refactoring stories that implement
no ICs:

```markdown
Interface Changes: None — behavior-preserving prerequisite
Validated by: None — behavior-preserving prerequisite; existing tests verify preserved behavior
```

### Step 7: Complete and Validate Artifacts

Write `.artifacts/design/{issue-key}/07-coverage.md`:

```markdown
# Coverage Matrix — {issue-key}

## PRD Requirement → Epic/Story Mapping

| PRD Requirement | Epic | Stories | Status |
|-----------------|------|---------|--------|
| FR-1: {description} | Epic 1 | Story 1.01, 1.02 | Covered |
| FR-2: {description} | Epic 2 | Story 2.01 | Covered |
| FR-3: {description} | — | — | **GAP** |
| NFR-1: {description} | Epic 1 | Story 1.02 | Covered |
| NFR-2: {description} | Epic 2 | Story 2.01 | Covered |

**Active-only coverage.** Only effectively active stories satisfy
coverage. A story is effectively active when it has no `status:
removed` marker and its parent epic is also active. Stories with
`status: removed`, and unmarked children of removed epics, do not
satisfy requirement coverage — they are retained for identity and
traceability audit only. Do not mask a coverage gap by counting
retired work, and do not silently drop requirements that lost their
only implementing story to retirement.

## Gaps

{For each uncovered requirement: why it's not covered and a recommendation.
 If no gaps: "All PRD requirements are covered by the decomposition."}

## Stories Without PRD Traceability

{Any stories that don't map to a specific PRD requirement. These may be
 legitimate (e.g., infrastructure prerequisites) but should be justified.
 If none: "All stories trace to PRD requirements."}
```

**Verify artifact structure.** Quick sanity check before invoking the
decomposition review. Verify:

1. `05-epics.md` exists and references all active epic files
2. Each epic file referenced in `05-epics.md` exists (e.g.,
   `06-stories/epic-1-{slug}.md`)
3. Each active epic (no `status: removed`) has a corresponding
   story directory containing at least one effectively active
   child story (no own `status: removed` and parent epic active)
   — a directory containing only `status: removed` files does not
   satisfy this check.  A retired epic from a partial run may
   lack a child directory and is retained as an identity record
4. `07-coverage.md` exists and contains at least one mapping row
5. Testplan was loaded in Step 1 (confirmed — source loading blocks if missing)
6. Every active non-`[DOCS]` story file (no `status: removed`,
   parent epic active) has `Interface Changes` and `Validated by`
   lines in its Design Reference section — retired partial stories
   are retained for identity audit only

If structural issues are found, fix them before proceeding. Do not
invoke a review on incomplete artifacts.

### Step 8: Review Decomposition

Review the decomposition for structural quality and requirement
coverage. This review operates independently from the design document —
the reviewer evaluates what the artifacts actually say, not what the
decomposer intended.

Read `../decomposition-review.md` for evaluation criteria, finding
format, and severity definitions.

**If the AI runtime supports subagents**, spawn the review in a
subagent for independence. Load it with:

- The decomposition review protocol (`../decomposition-review.md`)
- The PRD (use the path from `01-context.md`'s PRD Summary section)
- All decomposition artifacts: `05-epics.md`, all
  `06-stories/epic-{N}-{slug}.md` files, all
  `06-stories/epic-{N}/story-{NN}-{slug}.md` files, `07-coverage.md`
- All validation artifacts listed in `validation-index.json` (or
  `04-testplan.md` for legacy) — for cross-reference checking of
  story implementation references, not for testplan content review
  (content quality was verified during `/draft`)
- NOT the design document (`03-design.md`) — the reviewer evaluates
  the artifacts on their own merits

Retain the subagent's ID for use in the re-review sub-step — resuming the same
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

### Step 9: Validate Findings, Verify Provenance, and Re-Review

This step runs a validation procedure with two mandatory actions
followed by a conditional re-review. Every validation cycle — including
the first, and including cycles where the review produced zero
findings — executes both actions before deciding whether re-review
is needed. Cap at 2 review-fix rounds total across the entire step.

1. **Assess review findings.** For each finding from Step 8 (or from
   a re-review iteration), apply these checks:
   - **Validate the reference.** Confirm the cited artifact file and
     section exist. Discard any finding that references a file or
     section that does not exist.
   - **Cross-check PRD claims.** For findings that assert a missing
     requirement or inadequate coverage, verify the claim against the
     actual PRD. Discard findings based on misidentified requirements.
   - **Assess on value.** Does this finding genuinely improve the
     decomposition? If yes: fix the issue immediately — re-read the
     affected artifact file before modifying it, verify the fix, and
     do not rename, renumber, or move story files (criterion 7). If
     no: note why the finding was dismissed.

   Only fix findings that add real value. Do not make changes for
   structural preferences not grounded in the evaluation criteria.

2. **Verify `[DOCS]` input provenance.** This runs unconditionally —
   even when the review produced zero findings or all findings were
   dismissed. The independent reviewer intentionally lacks the design
   document and cannot verify this; it is author-only verification.

   For each effectively active `[DOCS]` story (no own
   `status: removed` and parent epic active), check every unmarked
   item in Documentation Inputs against the design document
   (`03-design.md`) and the PRD.  Retired or parent-inactive
   `[DOCS]` stories are retained for identity audit but their
   historical markers are not rewritten against the current design.
   An item that traces to a specific design section or PRD requirement
   is correctly unmarked (planned). An item that fills a gap not
   specified by either document must be marked `[Assumption]`. An item
   that depends on an unresolved open question must be marked
   `[Open: §9.N]` — use the existing open-question identifier from
   the design document; do not invent new identifiers for this purpose.
   Fix any incorrect markers.

#### Re-review (if artifacts changed)

If either finding fixes (action 1) or provenance corrections (action 2)
changed any decomposition artifacts, and the 2-round cap has not been
reached, obtain a re-review:

**If a subagent was used in Step 8 and the runtime supports agent
resumption:** Resume the same reviewer agent. Send it the updated
artifacts and a summary of changes applied.

**If resumption is not available:** Spawn a new subagent loaded with
the decomposition review protocol, the updated artifacts, the PRD,
the testplan (`04-testplan.md`), and a summary of the previous round's
changes (but NOT the design document) so it has full context.

**If subagents are not available:** Re-read all decomposition artifact
files before re-reviewing — do not rely on your cached understanding
from the previous round. Evaluate the full artifact set (not just the
delta from the last round).

The re-review should focus on whether changes were applied correctly
and whether they introduced new issues. If new issues are found, run
the full validation procedure (actions 1 and 2) again on the new
findings, then re-review again if more artifacts changed — subject to
the same 2-round cap.

If no artifacts were changed by either action in a cycle, the
validation passes and Step 9 is complete.

### Step 10: Summarize and Present

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

**Present to the user.** Present the decomposition and highlight:
- Number of epics and stories
- Epic dependency order
- Any coverage gaps
- Stories that might need size adjustment (too large or too small)
- Any assumptions or judgment calls in the decomposition
- Decomposition review summary (from above)

If the decomposition review gate reported FLAG, present the unfixed
CRITICAL/HIGH findings and ask the user to decide how to handle them.
These may indicate genuine gaps requiring user judgment — the decomposer
should not resolve them unilaterally.

## Output

- `.artifacts/design/{issue-key}/05-epics.md` (epic metadata and ordering)
- `.artifacts/design/{issue-key}/06-stories/epic-{N}-{slug}.md` (one per epic)
- `.artifacts/design/{issue-key}/06-stories/epic-{N}/story-{NN}-{slug}.md` (one per story)
- `.artifacts/design/{issue-key}/07-coverage.md`

## When This Phase Is Done

Report your results:
- Summary of the decomposition (epics, stories, coverage)
- Highlight any gaps, sizing concerns, or judgment calls
- Whether the decomposition validates the design (or reveals gaps)

Then **re-read the controller** (`controller.md`) for next-step guidance.
