# Decomposition Review Protocol

Evaluation criteria, finding format, and assessment model used by the
decomposition review step in the `/decompose` phase. This protocol is
runtime-agnostic: it defines what to evaluate and how to report findings,
whether the reviewer is a subagent or the decomposer performing inline
self-review.

The reviewer receives the PRD and the decomposition artifacts (epics,
stories, coverage matrix) but intentionally does **not** receive the
design document. This is the independence property: the reviewer
evaluates what the artifacts actually say, not what the decomposer
intended. If a story's acceptance criteria are unclear without
cross-referencing the design document, that is a real finding — the
implementor needs self-contained acceptance criteria. Stories are
designed to be read alongside the design document during implementation
(Implementation Guidance sections may reference design sections by
number), so design-section references in Implementation Guidance are
expected and should not be flagged as a clarity problem.

## Core Principles

- **Challenge the decomposition structure, not just the content.** Don't
  just verify that each story describes work — question whether the epic
  boundaries are right, whether stories are right-sized, and whether the
  dependency order would actually produce a working feature. A review
  that only checks formatting is a linter with extra steps.
- **Evaluate against the PRD, not against assumed design intent.** The
  reviewer intentionally does not receive the design document. Evaluate
  whether the decomposition fully addresses the PRD's requirements. If a
  requirement appears missing, verify against the PRD before flagging —
  the design may have legitimately restructured how a requirement is
  addressed.
- **Findings must be actionable.** Every finding must cite a specific
  artifact file and section, and include a concrete suggestion the
  decomposer can evaluate and apply. Vague observations ("consider
  adding more detail") are not findings.
- **Severity must be honest.** CRITICAL and HIGH indicate problems that
  would cause incorrect implementation or significant rework. MEDIUM and
  LOW are suggestions that improve clarity or structure but are not
  blocking. Inflating severity erodes trust; deflating it hides real
  problems.
- **Assess on value, not severity.** A LOW finding that genuinely
  improves story clarity is worth implementing. A MEDIUM finding that is
  a structural preference without real impact is not. Severity indicates
  potential damage; value determines whether the finding is worth acting
  on.
- **Do not flag design-document cross-references in Implementation
  Guidance.** Stories are designed to be read alongside the design
  document during implementation. References like "See §4.3 of the
  design document" are intentional and expected. Flag instead: acceptance
  criteria that require the design document to understand, or
  Implementation Guidance that lacks enough direction for an implementor
  to start work. Note: `[DOCS]` stories use `Documentation Scope`
  instead of `Implementation Guidance` — evaluate those sections on
  whether they describe what the reader needs to understand, not on
  implementation direction.

## Evaluation Criteria

Evaluate the decomposition against these categories, prioritized by
impact:

1. **Requirement Coverage** — Does the coverage matrix (`06-coverage.md`)
   map every FR and NFR from the PRD? Do story acceptance criteria
   collectively cover the PRD's acceptance criteria, not just the FR/NFR
   descriptions? Are there stories without PRD traceability — and if so,
   are they justified (e.g., infrastructure prerequisites)? Has any
   requirement been silently dropped, deferred to "v2", or reduced in
   scope?

2. **Epic Structure** — Is each epic organized around user value, not
   technical layers? Does each epic deliver complete functionality
   independently? Are T-shirt sizes assigned and reasonable? Is the epic
   dependency order documented and logical? Could implementing the epics
   in the documented order actually work, or are there hidden
   dependencies?

3. **Story Completeness** — Are acceptance criteria behavioral outcomes
   (what the system does, testable from outside), not implementation
   specifications? Does each story have a title prefix assigned (`[DEV]`,
   `[QE]`, `[UI]`, `[CI]`, `[DOCS]`)? Is the story implementation order
   within each epic documented? Are stories right-sized — not so small
   they add process overhead, not so large they resist meaningful review?
   For non-`[DOCS]` stories, does the Implementation Guidance give
   enough direction to start work?
   If a story has more than approximately 8 acceptance criteria, should
   it be split?

4. **Testing Commitment** — Does every `[DEV]` story include both
   functionality AND testing? Do `[QE]` stories define concrete e2e test
   scenarios that validate user-facing behavior, not duplicate
   unit/integration tests from `[DEV]` stories? Does each epic with
   e2e-testable surface include at least one `[QE]` story? Does any
   story fall back to "manual validation" or "document procedure for QE"
   where an automated test could be written?

5. **Integration Stability** — Would implementing all stories in
   dependency order produce a working feature end-to-end? Does any
   integration work fall between stories — work that is needed but not
   captured in any story? Are story dependencies documented and
   complete? Does each story leave the system in a stable state (all
   tests passing after merge)?

6. **Documentation** — Do `[DOCS]` stories use the `[DOCS]` template
   (Documentation Scope and Documentation Inputs instead of
   Implementation Guidance and Testing Approach)? Does the Documentation
   Scope describe what the reader needs to understand without prescribing
   how to write or organize the documentation? Does the Documentation
   Inputs section inventory all user-facing artifacts from the
   implementation stories it references? Is the inventory detailed enough
   for a documentation author to know what to look for in the
   implementation?

## Finding Format

Each finding must include:

- **File:** artifact file path (e.g.,
  `05-stories/epic-1/story-02-add-validation.md`)
- **Section:** section within the artifact (e.g., "Acceptance Criteria",
  "Dependencies", "Testing Approach", "Documentation Scope")
- **Severity:** CRITICAL | HIGH | MEDIUM | LOW
- **Category:** one of the evaluation criteria above
- **Issue:** what the problem is
- **Suggestion:** concrete, actionable fix

Findings that cannot cite a specific file and section in the actual
artifacts must be discarded — they indicate hallucinated references.
Coverage matrix findings should cite `06-coverage.md` and the specific
row or gap.

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Would cause incorrect implementation — missing requirements, contradictory acceptance criteria, broken dependency chain, scope reduction | Must fix before presenting |
| HIGH | Would cause rework — story too large to review in a single PR, missing testing commitment, integration gap between stories, `[QE]` story duplicating `[DEV]` test scope | Should fix before presenting |
| MEDIUM | Would reduce clarity — vague acceptance criteria, imprecise implementation guidance or documentation scope, sizing concerns, minor coverage matrix inconsistencies | Fix if it adds value |
| LOW | Structural improvements — naming consistency, ordering suggestions, documentation clarity | Fix only if clearly valuable |

## Validation Rules

After obtaining a review (whether from a subagent or inline), validate
every finding:

1. **Verify file references.** Confirm the cited artifact file exists in
   the decomposition output (under
   `.artifacts/design/{issue-number}/`).
2. **Verify section references.** Confirm the cited section exists in
   the artifact file (e.g., an "Acceptance Criteria" heading actually
   appears in the story file).
3. **Discard hallucinated findings.** If a finding references an artifact
   file or section that does not exist, discard it silently. Do not
   present it.
4. **Cross-check against the PRD.** For findings that claim a
   requirement is missing or inadequately covered, verify the claim
   against the actual PRD. The PRD is the source of truth — if the
   reviewer misidentified a requirement or the requirement does not
   exist, discard the finding.
