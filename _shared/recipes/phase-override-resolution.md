---
name: phase-override-resolution
version: 0.1.0
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

If the override file exists but is empty, appears malformed, or does not
contain exit instructions to re-read the controller, warn the user and fall
back to the built-in default.

If using a project override, announce it: *"Using project override for
/{phase}."*
