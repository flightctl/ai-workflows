---
name: render-provenance-footer
version: 0.1.0
---
# Recipe: Render Provenance Footer

Render the durable `## Provenance` footer into a docs-repo markdown file before
`git add`. See `_shared/provenance-schema.md` for format.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | `prd` or `design` |
| ISSUE_NUMBER | Yes | Jira issue key |
| TARGET_FILE | Yes | Absolute path to the docs-repo file about to be committed |
| ALLOW_MISSING | No | Set to `yes` only after the user explicitly declines provenance |

## Procedure

From the **source repo** root, after copying the artifact to the docs repo and
**before** `git add`:

```bash
python3 "{AI_WORKFLOWS_ROOT}/_shared/scripts/provenance.py" render \
  --workflow {WORKFLOW} \
  --issue {ISSUE_NUMBER} \
  --target "{TARGET_FILE}"
```

If `{ALLOW_MISSING}` is `yes`, append `--allow-missing` to the command. This strips
any existing provenance section and records `provenance_kind: declined`.

Resolve `{AI_WORKFLOWS_ROOT}` as in `capture-provenance-event.md`.

The footer is the **published** provenance contract — workflow version and hash,
workspace hash, behind-main counts, and a machine-readable `<!-- osac-provenance:... -->`
comment for future metrics ingestion.

**Missing log:** When `provenance.json` is absent, the script auto-captures a
`commit` event and renders a `commit_only` footer (replacing any stale section
copied from the artifact). When the log contains only `commit` events, each
render appends a fresh snapshot before writing the footer. Do not pass
`--allow-missing` unless the user explicitly declines provenance.

Strips standard provenance blocks (`---` + heading + comment), legacy blocks,
and heading-only `## Provenance` sections without a machine comment.
