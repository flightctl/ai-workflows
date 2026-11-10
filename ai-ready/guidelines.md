# AI-Ready Workflow

Ensure a project has accurate, up-to-date AGENTS.md files and a clean set of AI convention files.

## Principles

- Accuracy over completeness: only document what you can verify from the codebase
- Project-specific over generic: no "write tests" or "handle errors" advice — document THIS project's actual approaches
- Surgical updates: change only what needs changing, preserve everything else
- Idempotent: running the workflow twice in a row produces no additional changes
- Show code, not concepts: reference specific file paths, not abstract descriptions

## Shared Content Rules

Read and follow `../_shared/content-rules.md` for generated-content rules. Those standards apply to all
artifacts and published output from this workflow.

## Hard Limits

- Never delete a file without first consolidating its unique content into AGENTS.md
- Never fabricate file paths, commands, or conventions that don't exist in the codebase
- Never add generic or aspirational advice — if it's not discoverable, don't document it
- Never modify source code, tests, or non-AI configuration — this workflow only touches documentation and AI convention files (AGENTS.md, CLAUDE.md, .cursorrules, .github/copilot-instructions.md, etc.)

## AGENTS.md Size Limits

- Target root AGENTS.md under 150 lines and keep every AGENTS.md at or below 300 lines
- Count current and final lines for every AGENTS.md instead of estimating
- When root AGENTS.md would reach 150 lines, preserve or create hierarchy for scoped guidance
- Preserve existing tool-specific rule directories when they provide scoped loading; otherwise use the nearest nested AGENTS.md for guidance that applies to a specific area
- Create tool-specific rule directories only when that convention already exists in the target project
- Prefer references to detailed docs over copying long explanations into AGENTS.md
- Do not report completion while any AGENTS.md exceeds 300 lines

## Safety

- Show your plan before making destructive changes (file deletions, merges)
- When merging AI convention files, display what will be consolidated before deleting originals
- Flag uncertainty: if you're unsure whether a pattern is intentional or accidental, ask rather than document it

## Quality

- Every file path referenced in AGENTS.md must exist in the project
- Every command referenced must be runnable
- No duplicate content across sections or across files
- Content must reflect the current state of the codebase, not a past version

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Adopt the project's existing terminology and naming conventions
- Preserve the project's existing AGENTS.md structure and voice when updating
- When in doubt about project conventions, check git history and existing code
