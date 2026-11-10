---
name: sync-validation-artifacts
version: 0.1.0
---
# Recipe: Sync Validation Artifacts to Docs Repo

Synchronizes local validation artifacts to the docs repository.
Used by `design/skills/publish.md`, `design/skills/revise.md`, and
`design/skills/respond.md` to copy, index, and retire validation
artifacts in the docs repo.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| ISSUE_KEY | Yes | Jira issue key (e.g., `EDM-1471`) |
| VALIDATION_INDEX_SCRIPT | Yes | Resolved path to `validation_index.py` — each fresh shell must re-resolve this before use |
| DOCS_REPO_PATH | Yes | Path to the docs repo checkout |
| FEATURE_DIR | Yes | Feature directory within the docs repo (e.g., `v2.1/feature-slug`) |
| DESIGN_FILE_PATH | No | Published path of the design file — not used by the recipe itself but accepted for caller convenience when passing the same parameter block |

## Phases

The procedure is split into two phases — PREFLIGHT and APPLY.
Callers must complete PREFLIGHT and obtain user approval of any
removals (including empty-set retirement) before beginning APPLY.
A state change (restoration, artifact edit, new publish) between
PREFLIGHT and APPLY invalidates the preflight — restart from
PREFLIGHT.

---

### PREFLIGHT Phase

All source artifact, destination, and retirement checks run here,
BEFORE any `mkdir`, design copy, artifact copy, staging, published
index write, or publication metadata mutation in the docs repo.
Local PROJECT snapshot/candidate files are allowed during preflight.

#### 1. Build CURRENT set

Resolve the current local artifacts:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{ISSUE_KEY}" || {
  echo "ERROR: resolve --local failed" >&2; exit 1
}
```

If exit 0, parse the JSON array (may be empty `[]`). If exit
non-zero, **stop and report** — do not fall back to legacy behavior
when a malformed index is present.

If `validation-index.json` does not exist in
`.artifacts/design/{ISSUE_KEY}` and `04-testplan.md` exists (legacy
layout), build a normalized index first with `build-legacy`, then
re-run `resolve --local`.

#### 2. Snapshot PREVIOUS state

Remove any existing snapshot from a previous run:

```bash
rm -f -- ".artifacts/design/{ISSUE_KEY}/prev-published-index.json" || {
  echo "ERROR: cannot remove stale snapshot" >&2; exit 1
}
```

If `{DOCS_REPO_PATH}/{FEATURE_DIR}/validation-index.json` exists,
validate it before copying:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" validate --published "{DOCS_REPO_PATH}/{FEATURE_DIR}/validation-index.json" || {
  echo "ERROR: published index validation failed — stop" >&2; exit 1
}
cp "{DOCS_REPO_PATH}/{FEATURE_DIR}/validation-index.json" ".artifacts/design/{ISSUE_KEY}/prev-published-index.json" || {
  echo "ERROR: snapshot copy failed" >&2; exit 1
}
```

If the index does not exist but
`{DOCS_REPO_PATH}/{FEATURE_DIR}/testplan.md` exists (legacy),
create a minimal published snapshot:

```json
{
  "schema_version": "1.0",
  "primary_testplan": "testplan.md",
  "artifacts": [{"file": "testplan.md", "type": "testplan"}]
}
```

Save to `.artifacts/design/{ISSUE_KEY}/prev-published-index.json`.
If neither exists, no previous set — skip snapshot.

#### 3. Removal preflight (non-empty AND empty)

**Non-empty current set with previous snapshot:** Identify proposed
removals before any docs-repo write:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{ISSUE_KEY}/validation-index.json" ".artifacts/design/{ISSUE_KEY}/candidate-published-index.json" --trusted-output-base "." || {
  echo "ERROR: transform failed" >&2; exit 1
}
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{ISSUE_KEY}/prev-published-index.json" ".artifacts/design/{ISSUE_KEY}/candidate-published-index.json" || {
  echo "ERROR: diff failed" >&2; exit 1
}
```

If `removed` is non-empty, present each removal with full published
path `{FEATURE_DIR}/{filename}` and require named confirmation.
Generic update approval does not constitute named removal approval.
Clean up the candidate file after preflight:

```bash
rm -f -- ".artifacts/design/{ISSUE_KEY}/candidate-published-index.json" || {
  echo "ERROR: cannot remove candidate" >&2; exit 1
}
```

**Empty current set with previous snapshot (empty-set retirement):**
This approval MUST happen during PREFLIGHT, before any docs-repo
mutation. Validate the previous snapshot, then present the exact
removal list with full published paths `{FEATURE_DIR}/{filename}`.
Require named confirmation of each artifact for retirement. An
empty current set caused by missing local sources (not explicit user
intent) must not silently remove — stop and report.

If the previous publication included a
`validation-index.json`, include it in the retirement list. Do not
retire the published index for legacy-only snapshots that had only
`testplan.md`.

**First publish (no previous snapshot):** No removal approval
needed — skip this step.

#### 4. Validate current set

For each artifact in the current set, verify ALL source and
destination checks:
- Local file exists and is not a symlink
- No symlink ancestor in destination path between
  `{DOCS_REPO_PATH}` and target file
- Destination is not a symlink
- Any existing destination file is in the previous validation set
  (unowned files must not be overwritten)

If any check fails, **stop and report**. Do not proceed to APPLY.

---

### APPLY Phase

Only proceed after PREFLIGHT passes and user approves any removals
(including empty-set retirement). The approved removal set, input
artifacts, and context must be unchanged since PREFLIGHT — if
anything changed, restart from PREFLIGHT.

#### 5. Create directory and copy artifacts

When the current set is non-empty:

```bash
mkdir -p "{DOCS_REPO_PATH}/{FEATURE_DIR}" || {
  echo "ERROR: cannot create feature directory" >&2; exit 1
}
```

Copy ALL current artifacts (not just previously tracked):

```bash
cp ".artifacts/design/{ISSUE_KEY}/{LOCAL}" "{DOCS_REPO_PATH}/{FEATURE_DIR}/{PUBLISHED_AS}" || {
  echo "ERROR: artifact copy failed" >&2; exit 1
}
git -C "{DOCS_REPO_PATH}" add "{FEATURE_DIR}/{PUBLISHED_AS}"
```

When the current set is empty, skip artifact copy but still create
the feature directory so the caller can copy the design file after
this recipe completes.

#### 6. Update published index

If the current set is non-empty, transform and write:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{ISSUE_KEY}/validation-index.json" "{DOCS_REPO_PATH}/{FEATURE_DIR}/validation-index.json" --trusted-output-base "{DOCS_REPO_PATH}" || {
  echo "ERROR: final transform failed" >&2; exit 1
}
git -C "{DOCS_REPO_PATH}" add "{FEATURE_DIR}/validation-index.json"
```

#### 7. Remove retired artifacts

**Non-empty current set with previous snapshot:** Re-diff using the
final published index to verify the removal set is unchanged from
preflight:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{ISSUE_KEY}/prev-published-index.json" "{DOCS_REPO_PATH}/{FEATURE_DIR}/validation-index.json" || {
  echo "ERROR: re-diff failed" >&2; exit 1
}
```

The `removed` list must match the preflight result. If sets differ,
stop. For each confirmed filename:

```bash
git -C "{DOCS_REPO_PATH}" ls-files --error-unmatch "{FEATURE_DIR}/{STALE_FILENAME}"
```

- Exit 0 (tracked): `git -C "{DOCS_REPO_PATH}" rm -- "{FEATURE_DIR}/{STALE_FILENAME}"`
- Exit 1 (untracked) AND the file was previously owned by this
  publication (confirmed in the approved retirement list): remove
  from disk with `rm -f "{DOCS_REPO_PATH}/{FEATURE_DIR}/{STALE_FILENAME}"` —
  do not use `git clean` or follow symlinks.
- Any other exit code: stop and report the unexpected state.

**Empty current set (retirement approved in preflight step 3):**
Execute the approved retirement. For each confirmed artifact:

```bash
git -C "{DOCS_REPO_PATH}" ls-files --error-unmatch "{FEATURE_DIR}/{FILENAME}"
```

- Exit 0 (tracked): `git -C "{DOCS_REPO_PATH}" rm -- "{FEATURE_DIR}/{FILENAME}"`
- Exit 1 (untracked, previously owned): `rm -f "{DOCS_REPO_PATH}/{FEATURE_DIR}/{FILENAME}"`
- Other: stop and report.

If the previous publication included a published
`validation-index.json` (not legacy-only), also retire it using the
same `git ls-files` / tracked-or-owned removal logic.

Staged deletions must be committed even with an empty current set.

#### 8. Update metadata

Update `publish-metadata.json`: set `validation_artifacts` to match
the current published set (preserving existing keys and types, with
stable key ordering), update `testplan_file_path` to the primary
testplan's full published path (or remove if no primary testplan).

## Invariants

- All source and destination checks (PREFLIGHT) complete BEFORE any
  directory creation, file copy, or staging (APPLY)
- Empty-set retirement approval happens in PREFLIGHT, before any
  docs-repo mutation
- User-approved removal set is verified unchanged before execution
- Callers copy the design file and render provenance AFTER this
  recipe's APPLY phase completes (the directory exists), then stage it
  themselves — design staging is independent of artifact existence
- A state change between PREFLIGHT and APPLY invalidates and restarts
- Empty/non-empty/first-publish/copy-failure/invalid-index states are
  distinct and handled separately
- Untracked previously-owned files are removed with exact `rm -f`
  (no broad clean or symlink following), not skipped
- Fresh shell `VALIDATION_INDEX_SCRIPT` resolution required per
  execution — do not assume variable persists from prior context
