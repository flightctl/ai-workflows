---
name: phase-override-resolution
version: 0.4.2
---
# Recipe: Phase Override Resolution

Resolves the skill file for a phase, checking for a project-level override
before falling back to the workflow's built-in default.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | Workflow name (e.g., `bugfix`, `design`, `docs-writer`) |
| PHASE_FILE | Yes | The filename to resolve — typically `{phase}.md`, but some workflows use different filenames (e.g., docs-writer maps `/gather` to `gather-context.md`). The caller supplies the mapped filename. |

## Shared Script

This recipe delegates the deterministic file-existence check and path
validation to a shared script:

```
{AI_WORKFLOWS_ROOT}/_shared/scripts/resolve-phase.py
```

Resolve `{AI_WORKFLOWS_ROOT}` to the ai-workflows installation directory
(`${HOME}/.ai-workflows` for user-level installs). Keep the target
repository as the process CWD so that `.workflows/` override lookup
uses the project root.

The script checks `.workflows/{WORKFLOW}/skills/{PHASE_FILE}` at the repo
root (CWD), falls back to the built-in default, validates path safety, and
prints the resolved path to stdout. See the script header for full usage.

## Procedure

1. Run the shared script to locate the phase file:
   ```bash
   python3 "{AI_WORKFLOWS_ROOT}/_shared/scripts/resolve-phase.py" \
     {WORKFLOW} {PHASE_FILE}
   ```
   The script prints the resolved path to stdout. If the path starts with
   `.workflows/`, an override was found; the script already announced it on
   stderr. If the script exits non-zero, report the failure and stop.
2. If the resolved path is a project override (starts with `.workflows/`),
   read and follow
   [phase-override-validation.md](phase-override-validation.md) with the supplied
   parameters and the invoking router's completion contract.
   If no override exists, skip validation — the built-in phase is selected.
3. If validation rejects the override, warn with the specific reason and
   re-run the script with `--builtin-only` to resolve the built-in fallback:
   ```bash
   python3 "{AI_WORKFLOWS_ROOT}/_shared/scripts/resolve-phase.py" \
     --builtin-only {WORKFLOW} {PHASE_FILE}
   ```
   Rejection is recoverable; it is not a resolution failure.
4. Return the selected file's location and any `COMPLETION_HANDOFF`
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
