---
name: review-protocol
version: 0.3.0
---
# Code Review Protocol

Shared evaluation criteria, finding format, and assessment model used by all
code review activities in this repository — both the standalone `code-review`
workflow and the self-review gates embedded in other workflows.

## Review Objective and Stopping Rule

The purpose of a code review is to judge whether the change is ready to
commit — not to find something to comment on. The review evaluates all
applicable criteria below and checks that mandatory quality gates
(lint, tests, required CI) have been satisfied.

- **Zero actionable findings with APPROVED is a successful review.** When
  the required evaluation and checks are complete and no substantiated
  blockers remain, approving without findings is a valid and expected
  outcome. Do not invent low-value comments merely to fill the findings
  section.
- **No minimum findings quota.** There is no duty to supply feedback.
  A clean change deserves a clean approval.
- **Mandatory gates still apply.** Do not issue an unqualified APPROVED
  while required verification (lint, tests, security checks, or other
  mandatory quality gates discovered from the project) is incomplete or
  failing. An approval means the review is complete *and* the change
  meets the project's commit-readiness bar.
- **Optional suggestions are welcome but nonblocking.** Clearly valuable
  improvements (better naming, a small safety margin, a useful test case)
  may be reported as findings with MEDIUM or LOW severity, but they
  are explicitly nonblocking. They cannot alone require CHANGES_REQUESTED
  or trigger another review round. If a human chooses to implement an
  optional suggestion, that is their prerogative — do not prohibit it,
  but do not force another review cycle solely because nonblocking
  advice exists.

## Core Principles

- **Challenge decisions, not just implementation.** Don't just verify that
  the code does what it intends — question whether the intent is right.
  Should this abstraction exist? Is this the right boundary between
  components? Would a different approach avoid the complexity being managed
  here? A review that only checks correctness is a linter with extra steps.
- **Review what the developer wrote, not what you would have written.** The
  above principle challenges decisions; this one constrains how. Evaluate
  the approach on its merits — does it work, is it clear, is it safe? Do
  not impose stylistic preferences or rewrite working code in your preferred
  idiom. Challenge the design, not the taste.
- **Findings must be actionable.** Every finding must include a concrete
  suggestion the developer can evaluate and apply. Vague observations
  ("consider improving this") are not findings.
- **Severity must be honest.** CRITICAL and HIGH are blockers that would cause
  bugs, security issues, or maintenance problems. MEDIUM and LOW are suggestions
  that improve quality but are not blocking. Inflating severity erodes trust;
  deflating it hides real problems.
- **Assess on value, not severity.** A LOW finding that genuinely improves the
  code (clearer naming, better readability, a small correctness improvement) is
  worth implementing. A MEDIUM finding that doesn't add real value (stylistic
  preference, churn without improvement) is not. Severity indicates impact;
  value determines whether the finding is worth acting on.
- **Discover, don't assume.** The project's tech stack, conventions, and quality
  standards are discovered from the codebase, not hardcoded. Every project gets
  a review tailored to its own standards.

## Evaluation Criteria

Evaluate changes against these categories, prioritized by impact:

1. **Correctness** — Does the code do what it intends? Are there logic errors,
   off-by-one mistakes, or unhandled edge cases?
2. **Error handling** — Are errors caught, propagated, and reported
   appropriately? Are failure modes handled?
3. **Security** — Are there injection risks, unsafe operations, exposed secrets,
   or other OWASP-category concerns?
4. **Design** — Does each new abstraction earn its complexity? Are
   responsibilities clearly divided — no god functions, no single type
   accumulating unrelated concerns? Do interfaces hide implementation details
   and expose coherent contracts? Are there implicit assumptions between
   components that should be explicit (shared constants, expected call order,
   assumed preconditions)? Signals: a function taking many parameters
   (missing intermediate type), a type importing from several unrelated
   packages (mixed concerns), identical error-handling blocks repeated
   across call sites (missing shared helper), a new interface that exposes
   internal types to callers.
5. **Performance** — Are there unnecessary allocations, N+1 queries, unbounded
   operations, or other efficiency concerns?
6. **Naming and clarity** — Are names descriptive? Is the intent clear from
   reading the code? Flag comments with these defects:
   - **Restates the signature.** A doc comment that only says what the
     function name and parameter types already say adds nothing.
   - **Narrates the journey.** References prior architectures, design-doc
     sections, refactoring provenance, or verification steps.
   - **Couples to callers.** Documents who calls a function or consumes
     an event — callers change; the comment rots.
   - **Cross-references internals from public docs.** A public doc
     comment that says "see privateHelper" sends the reader into
     implementation details the public API should abstract away.
   - **Repeats across call sites.** The same multi-sentence explanation
     copy-pasted into every function that uses a shared mechanism.
   Comments that exhibit any of these are defects, not documentation.
7. **Test coverage** — Are the changes tested? Are edge cases covered? Are
   tests testing contracts, not implementation?
8. **Project conventions** — Do the changes follow the conventions discovered
   from the project's AGENTS.md, CLAUDE.md, linting configs, and contribution
   guidelines?

## Finding Format

Each finding must include:

- **File:** The file path
- **Location:** Line range or function name
- **Severity:** CRITICAL | HIGH | MEDIUM | LOW
- **Category:** One of the evaluation criteria above
- **Issue:** What the problem is
- **Evidence:** What in the code, tests, or documented requirements
  substantiates the claim — including whether existing safeguards
  (error handling, validation, tests, type constraints) already address
  the concern. For a blocker (CRITICAL/HIGH), cite the concrete problem
  scenario or the specific requirement that is violated. For a
  nonblocking suggestion (MEDIUM/LOW), state why the change would be
  valuable but is not required before commit.
- **Suggestion:** Concrete, actionable fix
- **Commit-readiness impact:** `blocking` for CRITICAL/HIGH findings
  that must be resolved before commit, or `nonblocking` for MEDIUM/LOW
  suggestions that improve quality but do not prevent approval.

Findings that cannot cite a specific file and location in the actual diff must
be discarded — they indicate hallucinated references.

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Would cause bugs, security vulnerabilities, or data loss in production | Must fix before merge |
| HIGH | Missing error handling, race conditions, incomplete coverage that could cause failures | Should fix before merge |
| MEDIUM | Naming improvements, minor edge cases, convention violations | Fix if it adds value |
| LOW | Readability suggestions, minor refactoring opportunities | Fix only if clearly valuable |

## Blocker Substantiation

A finding marked as a blocker (CRITICAL or HIGH) must meet all of these
criteria:

1. **Concrete problem.** Identify a specific, triggerable failure
   scenario or a specific violated requirement — not a hypothetical
   that requires unsupported assumptions about how the code might be
   used.
2. **Evidence from the code.** Cite the relevant code path, test gap,
   or documented requirement. Account for existing safeguards — if
   the code already handles the concern (error checks, type
   constraints, upstream validation, tests), the finding is not a
   blocker.
3. **Necessity before commit.** Explain why the problem must be fixed
   before the change lands, not as a follow-up. A desirable
   alternative implementation, a discretionary polish item, or an
   unsupported hypothetical use case is insufficient to block.

**Disposition of unsubstantiated blockers.** A CRITICAL/HIGH finding
that fails the criteria above is not automatically converted to a
suggestion. If the finding identifies a validated, concrete, clearly
useful concern that simply does not rise to blocking severity,
downgrade it to MEDIUM/LOW (nonblocking). If the finding is
unsupported, already handled by existing safeguards, or based on
hypothetical scenarios without evidence, discard it — do not preserve
a finding merely to populate the feedback section. Substantive
design, testing, and maintainability concerns remain eligible as
blockers when all three criteria are met.

## Verdict Rules

Before routing on any verdict, apply the **commit-readiness check**:
APPROVED is valid only when **all three conditions hold**:

1. The required evaluation across all applicable criteria is complete.
2. All applicable mandatory quality gates (lint, tests, required CI,
   security checks discovered from the project) are passing — not
   merely unrun or incomplete.
3. No substantiated blockers (CRITICAL/HIGH meeting the Blocker
   Substantiation criteria) remain.

If any condition fails, the verdict is CHANGES_REQUESTED regardless
of the reviewer's label or the absence of code-level findings. An
unrun or incomplete mandatory gate is not "passing."

- **CHANGES_REQUESTED** requires at least one substantiated blocker
  (CRITICAL/HIGH meeting the criteria above) or at least one unmet,
  failing, or incomplete applicable mandatory quality gate.
- **APPROVED** is correct only when the commit-readiness check above
  is satisfied — regardless of whether nonblocking suggestions exist.
  Zero findings is a valid approved state.
- When issuing APPROVED with nonblocking suggestions, list them in the
  findings section. They inform the developer but do not prevent the
  approval and do not require another review round.

## Validation Rules

After obtaining a review (whether from a subagent, external tool, or inline
review), validate every finding:

1. **Verify file references.** Confirm the cited file exists and was part of
   the changes under review.
2. **Verify location references.** Confirm the cited line range or function
   exists in the current version of the file.
3. **Discard hallucinated findings.** If a finding references a file or
   location that does not exist, discard it silently. Do not present it.
4. **Read surrounding context.** The diff shows what changed; the surrounding
   code reveals whether the change fits. Read full files around changed
   sections to understand context.
5. **Verify applicability.** Confirm the finding applies to the actual
   code path and is not already addressed by existing guards, checks,
   type constraints, or tests. A finding about an error condition that
   is already handled is not valid.
6. **Verify blocker criteria.** For any CRITICAL or HIGH finding, confirm
   it meets the Blocker Substantiation requirements above. Downgrade to
   MEDIUM/LOW only if a validated, concrete, clearly useful nonblocking
   concern remains; discard if the finding is unsupported or already
   handled.
