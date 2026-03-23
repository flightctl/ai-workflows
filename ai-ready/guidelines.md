# AI-Ready Workflow

Ensure a project has accurate, up-to-date AGENTS.md files and a clean set of AI convention files.

## Principles

- Accuracy over completeness: only document what you can verify from the codebase
- Project-specific over generic: no "write tests" or "handle errors" advice — document THIS project's actual approaches
- Surgical updates: change only what needs changing, preserve everything else
- Idempotent: running the workflow twice in a row produces no additional changes
- Show code, not concepts: reference `file:line`, not abstract descriptions

## Hard Limits

- Never delete a file without first consolidating its unique content into AGENTS.md
- Never fabricate file paths, commands, or conventions that don't exist in the codebase
- Never add generic or aspirational advice — if it's not discoverable, don't document it
- Never modify source code, tests, or configuration — this workflow only touches documentation and AI convention files

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
