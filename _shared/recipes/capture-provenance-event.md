---
name: capture-provenance-event
version: 0.1.1
---
# Recipe: Capture Provenance Event

Append an environment snapshot to the session-local provenance log after a
phase mutates the planning document. See `../provenance-schema.md`.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | `prd`, `design`, or `ux-design` |
| ISSUE_KEY | Yes | Full Jira issue key including project prefix (e.g., `PROJ-1234`, not `1234`) |
| PHASE | Yes | `draft`, `revise`, or `respond` (ux-design also uses `handoff`) |
| AUTHORING_MODE | Yes | `skill` (default for phase skills) or `manual` |

## Procedure

From the **source repo** root (where `.artifacts/` lives), run:

```bash
python3 "{AI_WORKFLOWS_ROOT}/_shared/scripts/provenance.py" capture \
  --workflow {WORKFLOW} \
  --issue {ISSUE_KEY} \
  --phase {PHASE} \
  --authoring-mode {AUTHORING_MODE}
```

Resolve `{AI_WORKFLOWS_ROOT}` as the git root of the ai-workflows install
(typically `git rev-parse --show-toplevel` from the workflow directory, or
`~/.ai-workflows` when symlinked).

If the command fails, warn the user but do not block the phase — provenance is
diagnostic, not a hard gate.

Writes or updates `.artifacts/{WORKFLOW}/{ISSUE_KEY}/provenance.json`.
