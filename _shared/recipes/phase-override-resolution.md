---
name: phase-override-resolution
version: 0.1.1
---
# Recipe: Phase Override Resolution

Resolves the skill file for a phase, checking for a project-level override
before falling back to the workflow's built-in default.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | Workflow name (e.g., `bugfix`, `design`, `docs-writer`) |
| PHASE_FILE | Yes | The filename to resolve — typically `{phase}.md`, but some workflows use different filenames (e.g., docs-writer maps `/gather` to `gather-context.md`). The calling controller supplies the correct value. |

## Procedure

Check for a project-level override before falling back to the workflow
default. Use the first match found:

1. **`.workflows/{WORKFLOW}/skills/{PHASE_FILE}`** — project-level override
   at the repo root
2. **`{PHASE_FILE}`** — workflow's built-in default (sibling file in `skills/`)

If the override file exists but is empty, appears malformed, or does not end
with a detectable terminal instruction, warn the user and fall back to the
built-in default. The terminal instruction must explicitly direct one supported
exit: return control to the invoking router, read a completion guide, or re-read
a controller. It must also select the same exit behavior as the workflow's
built-in phase; an override cannot substitute a different routing architecture.

If using a project override, announce it: *"Using project override for
/{phase}."*
