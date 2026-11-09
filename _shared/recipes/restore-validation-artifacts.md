---
name: restore-validation-artifacts
version: 0.1.0
---
# Recipe: Restore Validation Artifacts

Restores local validation artifacts from project history or published
copies when the local index and artifact files are absent. Used by
`design/skills/respond.md` when routing validation artifact comments
requires local file presence.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| ISSUE_KEY | Yes | Jira issue key (e.g., `EDM-1471`) |
| VALIDATION_INDEX_SCRIPT | Yes | Resolved path to `validation_index.py` |
| DOCS_REPO_PATH | Yes | Path to the docs repo checkout |
| FEATURE_DIR | Yes | Feature directory within the docs repo (e.g., `v2.1/feature-slug`) |

## Procedure

Restore in order — each step requires the previous step to succeed:

### 1. Prefer trusted project history

Check `git log` for the last committed `validation-index.json` and
artifact files in `.artifacts/design/{ISSUE_KEY}/`. If available,
restore from that commit and validate with:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{ISSUE_KEY}"
```

If restore and validation succeed, skip to step 5.

### 2. If history is unavailable — map published entries

The published index uses `file` entries (not `published_as` — the
published schema forbids that field). Present the published `file`
entries to the user and ask for explicit confirmation of the
published-to-local filename mapping. Do not silently derive local
filenames or assume the published `file` basename is the original
local name.

Propose canonical local names following the `04-{slug}.md` convention
(e.g., `04-testplan.md`, `04-testplan-nfr.md`) only as suggestions
for user confirmation. Verify proposed companion slugs match the
local naming rules — the slug portion (after `04-` and before `.md`)
must not be `testplan` for companions.

### 3. Create local index

Once the user confirms the mapping, create a local
`validation-index.json` with the confirmed local filenames and
`published_as` destinations derived from the published `file` values
(the local schema uses `local`/`published_as` per artifact). Copy the
published file contents as the restored local artifacts.

### 4. Validate before editing

Run `resolve --local` on the artifact directory (not the index file)
and verify all file paths, ownership, and content integrity:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{ISSUE_KEY}"
```

Do not apply any primary or companion edits until validation passes.

### 5. Compare with current published set

After restoration and local validation, run `resolve --published` on
the published feature directory and compare the restored local mapping
and file content against the current published set. If they differ
(e.g., a companion was added or content changed since the local
commit), present the differences to the user and reconcile before
proceeding.

Do not silently overwrite published content with stale restored
content or delete companions that exist only in the published set.

## Routing while local files are absent

While local files are absent (before restoration completes), route
feedback comments by the published `file` entry path or by searching
the published artifact files for exact TC definition headings
(`## TC-xxx` sections) — do not look up TC IDs from index metadata
or table mentions, as the published index contains artifact metadata
(file, type, purpose), not TC IDs.

Do not require a local filename for routing. Assign the local filename
tag only after restoration and mapping validation in steps 2–4 above.

Do not edit published copies directly, perform broad restore
overwrites, or introduce new manifest fields that leak local paths
into the published index.
