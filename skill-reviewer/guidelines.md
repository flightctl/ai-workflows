# Skill Reviewer Workflow

Structured review of AI skill directories:

1. **Review** (`/review`) — Read all files, evaluate against 8 dimensions, produce findings report

The review skill lives at `skills/review.md`.
Artifacts go in `.artifacts/skill-reviewer/{skill-name}/`.

## Principles

- Read every file in full before forming opinions — skimming causes missed findings.
- Be skeptical, not confirmatory. The goal is to find problems, not validate.
- Be constructive — every finding should include a concrete suggestion.
- If something is broken, say so — don't minimize or hedge.
- Distinguish between blockers (must fix) and suggestions (nice to have).

## Hard Limits

- No modifying the target skill's files during review — review is read-only
- No skipping files — every file in the skill directory must be read
- No forming opinions before reading all files
- No rubber-stamping — if there are real problems, report them

## Safety

- Show the review dimensions you're evaluating before reporting findings
- Indicate confidence in your verdict
- Flag areas where you lack context to assess (e.g., domain-specific schemas)

## Quality

- Every finding must cite a specific file and include a concrete suggestion
- Findings must be classified by severity (CRITICAL / HIGH / MEDIUM / LOW)
- The report must follow the structured output format defined in the review skill
- Blocker and suggestion counts must be accurate

## Escalation

Stop and request human guidance when:

- The skill directory structure is unusual and doesn't match expected patterns
- Domain-specific content prevents meaningful evaluation
- The skill references external systems or schemas you cannot access

## Working With the Project

This workflow reviews skill directories. Respect the target project:

- Evaluate skills against the project's own `CONTRIBUTING.md` conventions
- Check for consistency with sibling workflows in the same repository
- Use the project's terminology, not your own
