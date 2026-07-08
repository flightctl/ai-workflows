---
name: capture-provenance-event
version: 0.1.0
---
# Recipe: Capture Provenance Event

Append an environment snapshot to the session-local provenance log after a
phase mutates the planning document. See `../provenance-schema.md`.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | `prd` or `design` |
| ISSUE_NUMBER | Yes | Jira issue key (e.g., `OSAC-1234`) |
| PHASE | Yes | `draft`, `revise`, or `respond` |
| AUTHORING_MODE | Yes | `skill` (default for phase skills) or `manual` |

## Procedure

From the **source repo** root (where `.artifacts/` lives), run:

```bash
python3 "{AI_WORKFLOWS_ROOT}/_shared/scripts/provenance.py" capture \
  --workflow {WORKFLOW} \
  --issue {ISSUE_NUMBER} \
  --phase {PHASE} \
  --authoring-mode {AUTHORING_MODE}
```

Resolve `{AI_WORKFLOWS_ROOT}` as the git root of the ai-workflows install
(typically `git rev-parse --show-toplevel` from the workflow directory, or
`~/.ai-workflows` when symlinked).

If the command fails, warn the user but do not block the phase — provenance is
diagnostic, not a hard gate.

Writes or updates `.artifacts/{WORKFLOW}/{ISSUE_NUMBER}/provenance.json`.
