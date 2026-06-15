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
- Offload mechanical checks to `scripts/pre-review-checks.py` when available — focus reviewer attention on judgment calls that require reading comprehension and context.

## Hard Limits

- No modifying the target skill's files during the review phase — the review itself is read-only. Fixing findings afterward is a separate user-initiated action.
- No skipping files — every file in the skill directory must be read
- No forming opinions before reading all files
- No rubber-stamping — if there are real problems, report them
- **No personal names in generated content.** Replace references to individuals with role-based descriptions or drop the attribution and state the finding directly.

## Safety

- Show the review dimensions you're evaluating before reporting findings
- Indicate confidence in your verdict
- Flag areas where you lack context to assess (e.g., domain-specific schemas)

## Quality

- Every finding must cite a specific file and include a concrete suggestion
- Findings must be classified by severity (CRITICAL / HIGH / MEDIUM / LOW)
- The report must follow the structured output format defined in the review skill
- Blocker and suggestion counts must be accurate
- Script `FAIL` results are pre-validated (verified against the filesystem) and can be cited directly as findings without re-verification
- Script `WARN` results require reviewer judgment — not all warnings are findings

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
