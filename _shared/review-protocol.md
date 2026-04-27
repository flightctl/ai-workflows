# Code Review Protocol

Shared evaluation criteria, finding format, and assessment model used by all
code review activities in this repository — both the standalone `code-review`
workflow and the self-review gates embedded in other workflows.

## Core Principles

- **Review what the developer wrote, not what you would have written.** Evaluate
  correctness, clarity, safety, and adherence to project conventions. Do not
  impose stylistic preferences that are not codified in the project's linting
  or contribution guidelines.
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
4. **Performance** — Are there unnecessary allocations, N+1 queries, unbounded
   operations, or other efficiency concerns?
5. **Naming and clarity** — Are names descriptive? Is the intent clear from
   reading the code?
6. **Test coverage** — Are the changes tested? Are edge cases covered? Are
   tests testing contracts, not implementation?
7. **Project conventions** — Do the changes follow the conventions discovered
   from the project's AGENTS.md, CLAUDE.md, linting configs, and contribution
   guidelines?

## Finding Format

Each finding must include:

- **File:** The file path
- **Location:** Line range or function name
- **Severity:** CRITICAL | HIGH | MEDIUM | LOW
- **Category:** One of the evaluation criteria above
- **Issue:** What the problem is
- **Suggestion:** Concrete, actionable fix

Findings that cannot cite a specific file and location in the actual diff must
be discarded — they indicate hallucinated references.

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Would cause bugs, security vulnerabilities, or data loss in production | Must fix before merge |
| HIGH | Missing error handling, race conditions, incomplete coverage that could cause failures | Should fix before merge |
| MEDIUM | Naming improvements, minor edge cases, convention violations | Fix if it adds value |
| LOW | Readability suggestions, minor refactoring opportunities | Fix only if clearly valuable |

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
