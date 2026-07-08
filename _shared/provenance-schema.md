---
name: provenance-schema
version: 0.1.0
---
# Provenance Schema

Tracks environment context when PRD and design workflow phases mutate planning
documents. See `_shared/scripts/provenance.py` for capture and render logic.

## Published vs session-local

| Artifact | Location | Published? |
|----------|----------|------------|
| `## Provenance` footer | Docs-repo `prd.md` / `design.md` | **Yes** — durable triage contract |
| `provenance.json` | `.artifacts/{workflow}/{issue}/` in source repo | **No** — gitignored session log |
| `03-prd.md` / `03-design.md` | `.artifacts/` in source repo | **No** — working drafts without footer |

Fields required for merged-doc triage must appear in the **footer**. The JSON log
supports same-session drift analysis only.

## Limitations

- When `provenance.json` is missing at publish, render auto-captures a `commit` event
  and emits a `commit_only` footer (distinct from a full session). Re-rendering with a
  commit-only log appends a fresh `commit` event so SHAs stay current. Use
  `--allow-missing` only when the user explicitly declines provenance.
- `commits_behind_main` uses `origin/HEAD`, then `origin/main`, then
  `origin/master` — repos with nonstandard default branches may omit the count.
- Tier 3 manual-edit detection is heuristic (`record-manual-edit` recipe); undeclared
  edits between skill phases may be missed.
- The machine-readable `<!-- osac-provenance:{...} -->` comment is the stable hook
  for future metrics pipelines (e.g., OSAC-959). Human-readable lines above it are
  for reviewer triage, not programmatic parsing.

## `provenance.json` (schema_version 1)

```json
{
  "schema_version": 1,
  "workflow": "prd",
  "document": "03-prd.md",
  "events": [
    {
      "phase": "draft",
      "authoring_mode": "skill",
      "timestamp": "2026-07-08T10:00:00Z",
      "workflow_version": "0.5.0",
      "ai_workflows": "adfad68",
      "source_repo": "abc1234 (dirty)",
      "source_repo_branch": "main",
      "commits_behind_main": 47,
      "commits_ahead_main": 0,
      "main_ref": "main"
    }
  ],
  "drift": {
    "context_changed": false,
    "first_event_index": 0,
    "last_event_index": 0,
    "changed_fields": []
  }
}
```

### Event fields

| Field | Description |
|-------|-------------|
| `phase` | `draft`, `revise`, `respond`, `manual-edit`, or `commit` |
| `authoring_mode` | `skill` or `manual` |
| `timestamp` | ISO-8601 UTC |
| `workflow_version` | Semver from `{workflow}/SKILL.md` |
| `ai_workflows` | `git describe` from ai-workflows install root |
| `source_repo` | `git describe` from workspace (session) root |
| `source_repo_branch` | Current branch in workspace root |
| `commits_behind_main` | Commits behind default remote branch (optional) |
| `commits_ahead_main` | Commits ahead of default remote branch (optional) |
| `main_ref` | Resolved default branch name (e.g., `main`) |

### Drift

Recomputed after every capture. Compares the first and last events on:
`workflow_version`, `ai_workflows`, `source_repo`, `source_repo_branch`,
`commits_behind_main`, `commits_ahead_main`.

## Published footer format

### `provenance_kind` values

| Kind | When | Human footer |
|------|------|--------------|
| `session` | Log has draft/revise/respond/manual-edit events | Authored / Final / Phases lines |
| `commit_only` | Log has only `commit` events (auto-captured at publish) | Committed line + disclaimer |
| `declined` | User bypassed via `--allow-missing` | None — machine comment only |

**Session — single context** (no drift):

```markdown
---

## Provenance

Authored: draft @ prd 0.5.0 - adfad68, workspace main @ 00e78b8f

<!-- osac-provenance:{"schema_version":1,"workflow":"prd",...} -->
```

**Session — multiple phases, no environment drift:**

```markdown
Authored: revise @ prd 0.5.0 - adfad68, workspace main @ 00e78b8f
Phases: draft, revise
```

**Session — drift detected:**

```markdown
Authored: draft @ prd 0.5.0 - adfad68, workspace main @ abc1234 (47 behind origin/main, dirty)
Final:    revise @ prd 0.5.0 - adfad68, workspace main @ 00e78b8f

> Context changed between draft and revise.
```

**Commit-only** (no authoring phases recorded this session):

```markdown
Committed: commit @ prd 0.5.0 - adfad68, workspace main @ 00e78b8f

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- osac-provenance:{"schema_version":1,"provenance_kind":"commit_only","phases":["commit"],...} -->
```

**Declined** (`--allow-missing` only — no `## Provenance` heading):

```markdown
<!-- osac-provenance:{"schema_version":1,"provenance_kind":"declined"} -->
```

Format rules:
- Workflow: `{workflow} {version} - {hash}` (Andy/Eran triage: semver + exact commit)
- Workspace: `workspace {branch} @ {hash} ({N behind origin/{main_ref}}{, dirty})`
- Omit behind-main when zero; omit `dirty` when clean
- Manual-edit events show `[manual]` after the phase label
- Machine-readable metrics use the HTML comment (not the human lines)

## Tier mapping

| Tier | Features |
|------|----------|
| 1 | Capture on draft/revise/respond; render on docs-repo commits; footer |
| 2 | Main distance fields; drift block in JSON |
| 3 | `authoring_mode`; `manual-edit` phase via `record-manual-edit` recipe |
