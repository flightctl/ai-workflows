---
name: record-manual-edit
version: 0.1.1
---
# Recipe: Record Manual Edit

Record that the planning document was edited outside a skill phase (Tier 3
attribution). Delegates to `capture-provenance-event` with fixed parameters.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | `prd` or `design` |
| ISSUE_KEY | Yes | Jira issue key |

## When to invoke

- Before `/revise` or `/respond`, if the user states they edited the document
  manually outside the workflow
- On re-ingest when a diff shows `03-prd.md` or `03-design.md` changed since
  the last provenance event without a matching skill phase
- When `/revise` starts, optionally ask: "Did you edit the document manually
  since the last workflow phase?" — if yes, invoke this recipe first

## Procedure

Read and follow `capture-provenance-event.md` with:

| Parameter | Value |
|-----------|-------|
| WORKFLOW | `{WORKFLOW}` |
| ISSUE_KEY | `{ISSUE_KEY}` |
| PHASE | `manual-edit` |
| AUTHORING_MODE | `manual` |

Limitations: detection is heuristic. Undeclared manual edits between skill
phases may not be captured.
