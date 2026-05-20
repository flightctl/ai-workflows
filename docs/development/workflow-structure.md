<!-- Edited by Claude Code -->
# Workflow Structure

Every workflow follows the same directory layout:

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

The mandatory entry point. Keep it short — a phase overview and a pointer to `guidelines.md`.

```yaml
---
name: workflow-name
description: Brief description. Include trigger terms so the agent knows when to use it.
---
```

- `name`: lowercase, hyphens only, max 64 chars
- `description`: what the workflow does and when to use it, third person

## guidelines.md

Defines the behavioral rules for the workflow: principles, hard limits, safety checks, quality standards, and escalation criteria. This file is not auto-discovered — it only loads when the workflow's `SKILL.md` explicitly references it.

## skills/controller.md (optional)

An optional dispatcher that manages phase execution and transitions. When present, it should:

- List all phases with references to sibling skill files (e.g. `assess.md`, not `skills/assess.md`)
- Define how to execute a phase (announce, read, execute, report, wait)
- Provide next-step recommendations after each phase
- Never auto-advance — always wait for the user

## skills/phase-name.md

Contains the detailed steps for a single phase. Each file ends by instructing the agent to report its findings and re-read the controller for next-step guidance.

## commands/phase-name.md

Thin wrappers:

```markdown
# /phase-name

Read `../skills/controller.md` and follow it.

Dispatch the **phase-name** phase. Context:

$ARGUMENTS
```

## Path Conventions

All internal file references must be **relative to the referencing file's own location**:

- `commands/*.md` reference the controller as `../skills/controller.md` (or `../SKILL.md` if no controller)
- `skills/controller.md` references sibling skills as `assess.md`, `fix.md`, etc.
- `SKILL.md` references `guidelines.md` and optionally `skills/controller.md`

Relative paths ensure that symlinks resolve correctly regardless of where the workflows are installed.

## Shared Resources

Cross-cutting concerns live in `_shared/`:

```text
_shared/
  review-protocol.md              # Shared code review criteria
  recipes/
    self-review-gate.md           # Pre-PR self-review quality gate
```

Recipes are referenced via relative path (e.g., `../../_shared/recipes/self-review-gate.md` from `skills/`).
