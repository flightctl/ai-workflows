---
name: phase-override-resolution
version: 0.2.0
---
# Recipe: Phase Override Resolution

Resolves the skill file for a phase, checking for a project-level override
before falling back to the workflow's built-in default.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | Workflow name (e.g., `bugfix`, `design`, `docs-writer`) |
| PHASE_FILE | Yes | The filename to resolve — typically `{phase}.md`, but some workflows use different filenames (e.g., docs-writer maps `/gather` to `gather-context.md`). The caller supplies the mapped filename. |

## Procedure

1. Locate `.workflows/{WORKFLOW}/skills/{PHASE_FILE}` at the consuming repo
   root. Resolve the built-in fallback as
   `../../{WORKFLOW}/skills/{PHASE_FILE}` relative to this recipe, independent
   of the caller's location.
2. If no override exists, select the built-in phase without loading validation
   instructions. Only when an override exists, read and follow
   [phase-override-validation.md](phase-override-validation.md) with the supplied
   parameters and the invoking router's completion contract.
3. If validation rejects the override, warn with the specific reason and select
   the built-in phase. Rejection is recoverable; it is not a resolution failure.
4. If using a project override, announce it: *"Using project override:
   {WORKFLOW}/{PHASE_FILE}."* Identify the file using these supplied values;
   do not infer a command name from the filename.
5. Return the selected file's location and any `COMPLETION_HANDOFF`
   classification to the invoking router with the file's instructions
   unchanged, whether it is an override or the built-in fallback.

The invoking router executes the selected phase and handles its complete
handoff. It preserves required waits and user selections, applies its documented
normalization, and executes each authorized continuation once. This recipe does
not execute phase steps, completion guides, waits, or continuations.

Completion handling must occur exactly once. Initialize
`COMPLETION_CONSUMED=false`. A router that executes a phase's completion-guide
handoff sets `COMPLETION_CONSUMED=true` and skips its default follow-up
completion read. A router that normalizes the handoff without executing its
destination leaves it false and performs its normal completion read once.

Resolution fails only when the selected built-in fallback cannot be located,
read, or contains no executable phase instructions. Report that failure and
stop. Once the invoking router starts phase execution, it must not switch
implementations; it reports operational errors through the workflow's error
handling.
