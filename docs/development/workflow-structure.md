<!-- Edited by Claude Code -->
# Workflow Structure

Every workflow follows a canonical directory structure:

```text
workflow-name/
  SKILL.md              # Required — YAML frontmatter (name, description) + entry point
  guidelines.md         # Behavioral rules: principles, hard limits, safety, quality, escalation
  README.md             # Human-readable documentation
  skills/
    controller.md       # Optional — phase dispatch, transitions, next-step recommendations
    phase-name.md       # One file per phase
  commands/
    phase-name.md       # Thin wrappers that invoke the controller or SKILL.md
```

## SKILL.md

The entry point. Keep it thin — phase overview and a reference to `guidelines.md`.

```yaml
---
name: workflow-name
description: Brief description. Include trigger terms so the agent knows when to use it.
---
```

- `name`: lowercase, hyphens only, max 64 chars
- `description`: what the workflow does and when to use it, third person

## guidelines.md

Contains principles, hard limits, safety, quality standards, escalation criteria, and project-respect rules. Not auto-discovered by Cursor — only loads when the workflow explicitly references it.

## skills/controller.md (optional)

Manages phase execution and transitions. When present, it should:

- List all phases with references to sibling skill files (e.g. `assess.md`, not `skills/assess.md`)
- Define how to execute a phase (announce, read, execute, report, wait)
- Provide next-step recommendations after each phase
- Never auto-advance — always wait for the user

## skills/phase-name.md

Detailed steps for a phase. At the end, instructs the agent to report findings and re-read the controller.

## commands/phase-name.md

Thin wrappers:

```markdown
# /phase-name

Read `../skills/controller.md` and follow it.

Dispatch the **phase-name** phase. Context:

$ARGUMENTS
```

## Path Conventions

All internal file references must be **relative to the file's own location**:

- `commands/*.md` reference the controller as `../skills/controller.md` (or `../SKILL.md` if no controller)
- `skills/controller.md` references sibling skills as `assess.md`, `fix.md`, etc.
- `SKILL.md` references `guidelines.md` and optionally `skills/controller.md`

This ensures symlinks resolve paths correctly regardless of install location.

## Shared Resources

Cross-cutting concerns live in `_shared/`:

```text
_shared/
  review-protocol.md              # Shared code review criteria
  recipes/
    self-review-gate.md           # Pre-PR self-review quality gate
```

Recipes are referenced via relative path (e.g., `../../_shared/recipes/self-review-gate.md` from `skills/`).
