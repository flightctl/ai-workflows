---
name: draft
description: Draft the design/architecture document from context using the template and section guidance.
---

# Draft Design Document Skill

You are a software architect. Your job is to synthesize the PRD requirements
and codebase context into a structured design document that details how the
feature will be implemented.

## Your Role

Read the source material, apply the template structure, follow the section
guidance, and produce a design document that gives technical reviewers a
clear, concise picture of the proposed implementation. Every design decision
must be traceable to a PRD requirement or explicitly flagged as an assumption.

## Critical Rules

- **Do not invent requirements.** Every design element must trace to the PRD, codebase context, or direct user instruction.
- **Follow the template.** Use the template resolved in Step 1. Do not add or remove sections without user approval. Sections with no impact should say so explicitly — do not omit them.
- **Follow the section guidance.** Use the section guidance resolved in Step 1 for content standards.
- **Be concise.** Every sentence should earn its place. A shorter document gets better reviews.
- **Be specific.** No vague language. Name the data structures, specify the error codes, define the validation rules.
- **No scope reduction.** Never simplify, defer to "v2", or use "placeholder" to reduce scope. If something won't fit, flag it explicitly and propose a split.
- **Explain diagrams.** Every Mermaid diagram must be accompanied by narrative explaining what it shows and what the reader should take away.

## Process

### Step 1: Locate the Template

Read and follow `../../_shared/recipes/template-override-resolution.md`
with `WORKFLOW=design`, `TEMPLATE_FILE=design.md`.

### Step 2: Read Source Material

Read these files in order:
1. `.artifacts/design/{issue-key}/01-context.md` (architectural context)
2. `.artifacts/design/{issue-key}/02-research.md` (if exists — design research findings)
3. The PRD — use the path recorded in `01-context.md`'s PRD Summary section
4. Clarifications — use the path recorded in `01-context.md`'s PRD Summary
   section (if it lists a clarifications path). Read for locked decisions.
5. The design document template (from Step 1)
6. The section guidance (from Step 1)

### Step 3: Map Requirements to Design

Before writing, create a mental map:
- Which PRD requirements drive which design sections?
- Which existing codebase patterns should the design follow?
- If research was conducted (`02-research.md` exists): which research findings
  inform which design sections? Where does the recommended approach apply?
  What integration constraints must the design respect?
- Which decisions have multiple viable approaches and need alternatives analysis?
  If research produced a comparison matrix, use it as the starting point for
  the Alternatives Considered section.
- Where are the remaining unknowns (sections that will need open questions)?
- Use the PRD's requirements, any architectural context from `/ingest`, and
  any research findings from `/research` as the starting point for §4.1 Architecture.

### Step 4: Write the Design Document

Generate the design document following the template structure. For each section:

1. Read the section guidance for that section
2. Draw content from the context and PRD
3. Apply specificity standards (no vague language)
4. Flag assumptions with an inline note: `[Assumption: ...]`
5. Use source markers (`[PRD: §4.1]`, `[PRD: FR-3]`, `[PRD: NFR-2]`, `[Locked: D{N}]`, `[Research: §{section}]`, `[User]`, `[Codebase: path/to/file]`), following the consolidation guidance in the section guidance General Rules

**Incorporating clarifications:** When a clarification or PRD revision
changed the scope or corrected an assumption, write the design decision
in its final form. Do not describe what the original PRD said, what was
removed, or why a previous position was abandoned. The clarification log
(`02-clarifications.md`) preserves the editorial history; the design
document states the current position as if it was always the intent.

Fill in the metadata header:
- **Author(s):** The human who owns or requested this feature — never
  the AI assistant. Derive from `git config user.name` if available;
  otherwise ask the user before continuing.
- **Jira:** Link to the source Feature issue
- **PRD:** `[prd.md](prd.md)` — relative link to the co-located PRD
- **Date:** Today's date

**Owner fields (Open Questions):** When populating Owner fields, derive
the owner from the source material (e.g., the responsible team evident
from the Jira ticket, PRD, or requirement context). If the owner is not
evident, write "To be determined" — do not default to the document's
Author(s). Step 5 will prompt the user to resolve any missing owners.

**Mermaid diagrams:** Use them where they add clarity — especially for
architecture (section 4.1) and data flow. Any Mermaid diagram type is
allowed; choose the one that best communicates the concept. Always follow
a diagram with a paragraph explaining what it illustrates.

### Step 5: Resolve Outstanding Items

Before the design document can be saved, the author must validate every
assumption and outstanding item. Collect the following from the document:

1. Every `[Assumption: ...]` marker
2. Every "To be determined" item
3. Every open question in the Open Questions section that lacks an owner
   or impact

If there are no items across all three categories, skip to Step 6.

Present the items to the user in conversation:

1. **Assumptions:** List each with its section reference and the
   assumption text.
2. **TBD markers:** List any "To be determined" items with their section
   references.
3. **Incomplete open questions:** List any open questions missing an owner
   or impact field.

Ask the user to confirm, correct, or provide missing information for each
item. Then apply the resolutions:

- **Confirmed assumptions:** Rewrite the statement in its final form and
  remove the `[Assumption: ...]` marker.
- **Corrected assumptions:** Rewrite with the corrected information and
  remove the marker.
- **Resolved TBDs:** Replace the "To be determined" text with the
  provided content.
- **Items the user cannot resolve now:** Convert each unresolved
  `[Assumption: ...]` into either an Open Question entry (with Owner and
  Impact) or a concrete "To be determined" statement, then remove the
  assumption marker. Leave the resulting TBD/open-question items in
  place — these are genuine gaps, not drafting artifacts.

After this step, the document should contain no `[Assumption: ...]`
markers. Any remaining TBD markers or open questions represent real
unknowns, not unvalidated AI judgment calls.

### Step 6: Verify Coverage

Before self-review, systematically verify that nothing was lost between
source material and design document:

1. **Requirements coverage:** Re-read the PRD (use the path from
   `01-context.md`'s PRD Summary section). For each functional
   requirement (FR-1, FR-2, ...) and non-functional requirement (NFR-1,
   NFR-2, ...), confirm it is addressed in the design document. If a
   requirement has no corresponding design element, either add it or
   note the gap in the Open Questions section with a reason.

2. **Clarification incorporation:** Re-read the clarifications file (use
   the path from `01-context.md`'s PRD Summary section, if one was
   recorded). For each answered question, confirm the answer is reflected
   in the design. Pay particular attention to answers that added
   constraints or changed scope — these may affect architectural decisions
   even if they weren't recorded as formal locked decisions.

3. **Locked decisions:** Verify every locked decision in the
   clarification log is faithfully respected in the design. These are
   non-negotiable — if a design choice conflicts with a locked decision,
   change the design choice and add a note referencing the locked decision.

4. **Context incorporation:** Re-read `01-context.md`. Confirm that
   codebase patterns and constraints identified during ingestion are
   reflected in the design (followed or explicitly overridden with
   rationale).

   **4a. Research incorporation:** If `02-research.md` exists, re-read it.
   Confirm the recommended approach is reflected in the design. Confirm
   integration constraints are respected. If a comparison matrix was
   produced, confirm it informed the Alternatives Considered section.
   If the design deviates from the research recommendation, explain why
   in the relevant section.

5. **Traceability completeness:** Every design decision should have a
   source marker (`[PRD: §3.1]`, `[PRD: FR-3]`, `[PRD: NFR-2]`, `[User]`,
   `[Locked: D{N}]`, `[Research: §{section}]`, `[Codebase: path/to/file]`)
   or be flagged as `[Assumption]`.

6. **Open risks and unresolved items:** Check the PRD's Risks and Open
   Questions section (§6). Import any with Status=Open into the design's
   Open Questions — these are unresolved issues that may affect design
   decisions. Also check for any remaining TBD markers in the PRD, which
   represent genuine unknowns that may affect design choices. Import
   relevant items into the design's Open Questions section.

If this step discovers new gaps, assumptions, or open questions, return
to Step 5 to resolve them with the user.

### Step 7: Self-Review

Before presenting the design document, verify:

- [ ] Every design decision traces to a PRD requirement, research finding, codebase pattern, or is flagged as `[Assumption]` — source markers follow the consolidation rule (no redundant tags for the primary PRD)
- [ ] Goals are design-scoped (implementation constraints, not product outcomes)
- [ ] No sections are empty — sections with no impact say so explicitly
- [ ] §5 Interface Changes enumerates every new or changed API endpoint, CLI command, UI behavior, configuration option, event surface, and data format, each mapped to its PRD requirement(s). Omitting a real interface surface here produces missing test cases in Step 9. (A requirement with no interface surface — a purely internal change — is not an omission; it needs no IC and is tested via the `—` path in Step 9a.)
- [ ] Every Mermaid diagram has accompanying narrative explanation
- [ ] API changes include validation rules and concrete examples where helpful
- [ ] Data model changes show field names, types, and constraints
- [ ] Alternatives Considered includes at least one alternative for each non-trivial decision
- [ ] Open Questions use numbered subsections, are clearly stated, include Owner and Impact fields, and are limited to design scope (no process-level actions)
- [ ] No narration of editorial history — decisions are stated in final form, not as changes from a prior position
- [ ] No vague language ("appropriate", "efficient", "standard" without specifics)
- [ ] No scope reduction language ("v2", "simplified", "placeholder", "future enhancement")
- [ ] Locked decisions from PRD clarification are respected
- [ ] Terminology matches the PRD and codebase conventions
- [ ] No unresolved `[Assumption: ...]` markers remain in the document
- [ ] The document is concise — no redundant paragraphs, no unnecessary repetition

### Step 8: Write Artifact

Save the design document to `.artifacts/design/{issue-key}/03-design.md`.

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`, `PHASE=draft`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/design/{issue-key}/03-design.md`.

### Step 9: Generate Testplan

Generate a behavioral testplan anchored to PRD requirements and derived
through the design's Interface Changes (§5). The testplan validates that
the design covers the PRD's specified behavior and that every interface
change is exercised by at least one test case. This artifact is reviewed
alongside the design document and does not reference stories (which do
not exist yet).

#### 9a: Derive Test Cases

For each PRD requirement (FR-N, NFR-N), derive test cases:

**Functional requirements with IC mapping:** Identify the Interface
Changes (IC-N) from §5 that satisfy the requirement. For each IC,
generate test cases that exercise the concrete system surface it
describes — the API endpoint, CLI command, UI behavior, or
configuration change. Use the IC description's inputs, outputs, and
key behaviors as the basis for test scenarios.

**Non-functional or cross-cutting requirements:** For requirements
without a direct IC mapping (performance, security, availability, or
requirements satisfied by internal changes with no new interface),
derive test cases from the requirement text and the relevant design
sections directly.

**Test case ID scheme:** `TC-{requirement-id}-{sequence}`, where
`{requirement-id}` is the PRD requirement ID with the hyphen removed
(e.g., `FR-1` → `FR1`, `NFR-3` → `NFR3`) and `{sequence}` is a
two-digit zero-padded counter within that requirement. Examples:
`TC-FR1-01`, `TC-FR1-02`, `TC-NFR3-01`.

**Shared preconditions:** When *all* test cases under the same
requirement share identical setup (e.g., same fleet enrollment state,
same configuration baseline), extract the common setup into a
`##### Shared Preconditions` block directly under the `### FR-N` /
`### NFR-N` heading, before the first test case. Individual test
cases then list only their *additional* preconditions (if any) under
`##### Additional Preconditions` — or omit that subsection entirely
when the shared preconditions are sufficient. If only a subset of
cases shares setup, keep inline preconditions on each case instead.

**Compact format for simple cases:** When a test case has ≤ 2 steps
and a single expected result, use inline format instead of subsection
headings:

```markdown
**Steps:** 1. {action} → 2. {action}
**Expected:** {observable outcome}
```

**Parameterized test cases:** When multiple test cases share identical
preconditions AND steps but differ only in a parameter value and its
expected result, express them as a single test case with a
parameterization table under Expected Results instead of duplicating
the entire case. All other required fields (metadata table, Steps)
remain present — the variation table supplements them, not replaces
them:

```markdown
#### TC-FR1-01: {scenario title} (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-{N} | {priority} | {automation} |

##### Steps

1. {action with `{parameter}` placeholder}
2. {next action}

##### Expected Results

| {Parameter} | Expected Result |
|-------------|-----------------|
| {value-1}   | {outcome-1}     |
| {value-2}   | {outcome-2}     |
```

Each row counts as one test case for the Summary counts. The TC ID
covers all rows (do not assign separate IDs to individual rows).

**Test case fields** (all required per test case; the requirement is
identified by the parent section heading):

| Field | Description |
|-------|-------------|
| Test Case ID and Title | H4 heading: `#### TC-{req}-{NN}: {one-line scenario description}` |
| Interface Change, Priority, Automation | Single metadata table beneath the H4 heading |

The metadata table uses this format:

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-{N} | {priority} | {automation} |

For any requirement without a direct IC mapping (cross-cutting NFRs
or FRs satisfied only by internal changes), use `—` in the Interface
Change field.

**Priority assignment:**
- `critical` — core user workflows or data integrity
- `high` — important but non-core requirements
- `medium` — edge cases and secondary workflows
- `low` — cosmetic or informational scenarios

**Automation assignment:**
- `automated` — the scenario can be verified by automated tests
- `manual` — the scenario requires human verification (visual checks,
  hardware interaction, exploratory testing)

**Coverage target:** Every FR and NFR should have at least one test
case. Every IC should be exercised by at least one test case. An IC
with no test case is either a testplan gap or an unnecessary interface
change in the design.

**Negative scenarios:** Include negative/error test cases where the PRD
or design specifies error handling behavior. Do not invent error
scenarios beyond what the requirements and design describe.

**Documentation-only requirements:** Requirements that are satisfied
by documentation delivery — not system behavior — should be listed in
the Requirement Coverage Gaps section as documentation-only with a
brief rationale. Do not generate test cases with Steps and Expected
Results for documentation deliverables.

**Expected Results quality gate:** The Expected Results section must
describe concrete, observable outcomes — not restatements of the
requirements in vaguer terms. Banned phrases in Expected Results:
- "works correctly", "works as expected", "works properly"
- "handles appropriately", "handles gracefully"
- "is validated", "is verified", "is processed"
- "behaves as expected", "behaves properly"
- "completes successfully", "responds correctly", "functions as expected"
- "returns the correct value" (state the specific value)
- "no issues", "no problems"
- "appropriate error", "proper error" (name the specific error or code)

Each expected result must state what the tester observes: a specific
return value, status code, UI state, log message, or data change. If
you cannot state the expected result concretely, the requirement or
design is underspecified — flag it in the testplan's Gaps section
rather than writing a vague test case.

**Observability rule:** Every Expected Results section must describe
an outcome observable through the product's *public interfaces* — API
responses, CLI output, device behavior, operator-visible conditions
or events, documented file formats. Internal state (database rows,
internal lookup keys, scheduler queue internals) must not be the
primary assertion. If a requirement can only be verified by inspecting
internal state, flag it as a testplan gap — the requirement itself may
need refinement to expose an observable surface.

**Final-state rule:** If a requirement's customer value is a final
outcome (device updated, delta applied, fallback succeeded), test the
final outcome. Do not generate test cases for intermediate condition
or event sequences (e.g., conditions flipping through phases, events
progressing through stages) unless the intermediate state is itself a
customer-facing feature such as a progress indicator the user actively
monitors.

**Redundancy rule:** If an API field's value is already verified by
an e2e test case whose assertions explicitly consume that field, do
not add a separate field-existence test case. For example, if a test
case reads the `owner` field from the API response and asserts it
matches the expected value, a separate test verifying that `owner`
is present in the response is redundant. Do not assume a behavioral
outcome proves a specific API field exists when the behavior can be
achieved through an alternative code path that does not depend on
that field — retain standalone assertions for documented API
contracts not actually established by another test.

#### 9b: Write the Testplan

Write `.artifacts/design/{issue-key}/04-testplan.md`:

```markdown
# Testplan — {issue-key}

## Overview

- **Feature:** {feature-key} — {feature-title}
- **Total test cases:** {N}
- **Requirements covered:** {N} of {total FR + NFR count}
- **Interface changes covered:** {N} of {total IC count}

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-FR1-01 | {one-line scenario} | IC-1 | high |
| TC-FR1-02 | {one-line scenario} | IC-1 | medium |
| TC-NFR1-01 | {one-line scenario} | — | high |

## Test Cases

### FR-1: {requirement description}

##### Shared Preconditions

- {common setup shared by all test cases under this requirement}

#### TC-FR1-01: {scenario title}

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Additional Preconditions

- {extra setup beyond the shared preconditions — omit section if none}

**Steps:** 1. {what the tester does} → 2. {next action}
**Expected:** {observable outcome the tester verifies}

#### TC-FR1-02: {compact-case scenario title}

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

**Steps:** 1. {action} → 2. {action}
**Expected:** {observable outcome}

### NFR-1: {requirement description}

#### TC-NFR1-01: {scenario title}

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | manual |

##### Steps

1. {step}
2. {step}
3. {compare or verify against a baseline or control}

##### Expected Results

- {expected outcome}

## Gaps

### Requirement Coverage Gaps

{For each PRD requirement with no test cases: why it lacks coverage and
 a recommendation (e.g., "FR-5 is satisfied by internal changes with no
 observable interface — no behavioral test case is applicable").

 If no gaps: "All PRD requirements have test cases."}

### Interface Change Coverage Gaps

{For each IC not exercised by any test case: why it lacks coverage and
 a recommendation. An untested IC is either a testplan gap or an
 unnecessary interface change in the design.

 If no gaps: "All interface changes are exercised by test cases."}

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
| Interface changes with test cases | {N} / {total} |
```

Test cases are grouped under requirement headings because the
testplan's purpose is requirement traceability. The Interface Change
field in each test case's metadata table links to the design's §5.
The Test Case Index gives reviewers a one-screen overview of all
scenarios before they read the full body. Shared Preconditions reduce
repetition when cases under the same requirement share identical
setup. The compact inline format (Steps/Expected on single lines) is
used for simple cases with ≤ 2 steps and one expected result.
Parameterized test cases collapse near-identical cases that differ
only in a parameter value into a single case with a variation table.

#### 9c: Self-Review

Before presenting the testplan, verify:

- [ ] Every FR and NFR has a test case or a documented Requirement Coverage Gap with rationale
- [ ] Every IC from §5 has a test case or a documented Interface Change Coverage Gap with rationale
- [ ] Every non-`—` Interface Change value matches an IC defined in §5, and that IC's `Requirements` line includes the test case's requirement
- [ ] Every `—` Interface Change value is used only for a requirement without a direct IC mapping
- [ ] Every IC named in an Interface Change Coverage Gap entry exists in §5
- [ ] Expected Results contain no banned vague phrases
- [ ] Every Expected Results section (or compact `**Expected:**` field) asserts outcomes observable through public interfaces; no test case's primary assertion references internal state (database rows, lookup keys, scheduler internals)
- [ ] No test case's Expected Results section (or compact `**Expected:**` field) describes intermediate condition/event sequences when only the final outcome is customer-relevant
- [ ] No test case duplicates an assertion already covered by an e2e behavior test (e.g., field-existence check redundant with a behavior test)
- [ ] Documentation-only requirements appear in Gaps, not as test cases
- [ ] Priority assignment follows the Step 9a criteria (`critical` = core workflows or data integrity; `high` = important non-core; `medium` = edge cases and secondary workflows; `low` = cosmetic or informational) and is not defaulted to `high` across the board
- [ ] All test case fields are present and non-empty — heading, metadata table, Steps, and Expected Results (full subsections or compact inline format) — with actionable content (not placeholder or empty headings)
- [ ] When all test cases under the same requirement share identical setup, a non-empty, actionable Shared Preconditions block is present under the requirement heading — individual cases use a non-empty, actionable Additional Preconditions block when case-specific setup exists, and omit Additional Preconditions entirely when no case-specific setup exists — if only a subset of cases shares setup, each case keeps its own inline preconditions instead
- [ ] Compact inline format (`**Steps:**` / `**Expected:**`) is used for every case with ≤ 2 steps and a single expected result, and never for cases that exceed those limits
- [ ] Parameterized test cases are used when cases share identical preconditions and steps but differ only in parameter values — the variation table has at least two rows with different parameter values and a concrete expected result in every row — each row counts toward the Summary totals
- [ ] The Test Case Index is complete — every TC ID appears exactly once, and the Scenario, IC, and Priority columns match the corresponding test case body
- [ ] Gap analysis is accurate — requirement and IC coverage gaps are identified with rationale
- [ ] Test case IDs follow the scheme (`TC-{req}-{NN}`) with no duplicates
- [ ] Each test case's `TC-{req}-{NN}` prefix matches the PRD requirement heading it is grouped under (a `TC-FR2-*` case never appears under `### FR-1`)
- [ ] Every `### FR-*` / `### NFR-*` requirement heading matches a real PRD requirement, and every PRD requirement appears exactly once — either as a requirement heading with test cases or in the Requirement Coverage Gaps section
- [ ] The Overview counts and Summary table are accurate (parameterized rows are counted individually)

#### 9d: Write Artifact

Save the testplan to `.artifacts/design/{issue-key}/04-testplan.md`.

The Overview counts, Gaps sections, and Summary table written in Step 9b
are the canonical testplan summary. Step 10 presents those already-written
values — it does not recompute counts or coverage after the fact.

Provenance was already captured in Step 8 for the entire `/draft` phase —
no additional provenance call is needed here.

### Step 10: Present to User

Show the user the complete design document and highlight:
- Key architectural decisions and their rationale
- Open questions that need resolution
- Areas where multiple approaches were viable and why you chose the one you did
- Sections where confidence is lower — suggest the user capture these as
  open questions or TBD markers if they warrant reviewer attention
- Testplan summary — read from the Overview and Summary table already
  written in Step 9b: total test cases, requirement coverage, IC coverage
- Any testplan gaps recorded in Step 9b (requirements or ICs without test cases)

## Output

- `.artifacts/design/{issue-key}/03-design.md`
- `.artifacts/design/{issue-key}/04-testplan.md`
- `.artifacts/design/{issue-key}/provenance.json`

## When This Phase Is Done

Report your results:
- The design document has been written and saved
- The testplan has been generated with {test-case-count} test cases covering {requirement-count} requirements and {interface-change-count} ICs
- Highlight key decisions, assumptions, and open questions
- Note overall confidence in the document's completeness

Then **re-read the controller** (`controller.md`) for next-step guidance.
