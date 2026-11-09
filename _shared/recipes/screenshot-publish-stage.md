---
name: screenshot-publish-stage
version: 0.1.0
---
# Recipe: Screenshot Publish Stage and Commit

Build the owned-path allowlist, stage, and commit screenshot-related
changes in the docs repo. Used by `ux-design` `/publish` and `/respond`
to ensure both phases handle the staging/commit identically.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| DOCS_REPO_PATH | Yes | Absolute path to the docs repo working tree |
| HANDOFF_FILE_PATH | Yes | Repo-relative POSIX path to `handoff.md` |
| HANDOFF_DIR | Yes | Repo-relative POSIX path to the handoff directory (dirname of HANDOFF_FILE_PATH) |
| COPIED_FILENAMES | No | Bash array of screenshot filenames copied/updated this run (lfs/git mode) |
| REMOVED_FILENAMES | No | Bash array of screenshot filenames removed via `git rm` this run |
| MANIFEST_WRITTEN | No | Set to `true` if `screenshot-manifest.json` was written or updated this run |
| MANIFEST_REMOVED | No | Set to `true` if the consumer manifest was removed (all screenshots deleted) |
| COMMIT_MESSAGE | Yes | The commit message to use |

## Procedure

### 1. Build the owned-path allowlist

Construct a Bash array of every path this run created, modified, or owns
(including tracked deletions). This array serves as the staging set, change
detector, and commit pathspec.

```bash
owned_paths=("{HANDOFF_FILE_PATH}")

# Consumer manifest — include when written OR removed (tracked deletion)
if [ "${MANIFEST_WRITTEN}" = "true" ] || [ "${MANIFEST_REMOVED}" = "true" ]; then
  owned_paths+=("{HANDOFF_DIR}/screenshot-manifest.json")
fi

# Each copied/updated screenshot (lfs/git mode):
for f in ${COPIED_FILENAMES[@]+"${COPIED_FILENAMES[@]}"}; do
  owned_paths+=("{HANDOFF_DIR}/screenshots/$f")
done

# Each removed screenshot (already staged by git rm):
for f in ${REMOVED_FILENAMES[@]+"${REMOVED_FILENAMES[@]}"}; do
  owned_paths+=("{HANDOFF_DIR}/screenshots/$f")
done
```

### 2. Validate and stage owned paths

Verify required paths exist on disk before staging: the handoff file,
each copied screenshot, and the manifest when `MANIFEST_WRITTEN` is
set. Missing required paths indicate an upstream error.

Stage every path in the allowlist. For paths that still exist on disk,
use `git add`. For tracked deletions (removed screenshots, removed
manifest), `git rm` will have already staged them — include them in the
array so the `--only` commit sees them.

```bash
# Required-path validation: handoff and each copied file must exist on disk.
# Written manifest must exist when MANIFEST_WRITTEN=true.
if [ ! -f "{DOCS_REPO_PATH}/{HANDOFF_FILE_PATH}" ]; then
  echo "Error: required handoff missing: {HANDOFF_FILE_PATH}" >&2; exit 1
fi
for f in ${COPIED_FILENAMES[@]+"${COPIED_FILENAMES[@]}"}; do
  if [ ! -f "{DOCS_REPO_PATH}/{HANDOFF_DIR}/screenshots/$f" ]; then
    echo "Error: required copied file missing: {HANDOFF_DIR}/screenshots/$f" >&2; exit 1
  fi
done
if [ "${MANIFEST_WRITTEN}" = "true" ]; then
  if [ ! -f "{DOCS_REPO_PATH}/{HANDOFF_DIR}/screenshot-manifest.json" ]; then
    echo "Error: MANIFEST_WRITTEN=true but manifest missing" >&2; exit 1
  fi
fi

for p in "${owned_paths[@]}"; do
  if [ -f "{DOCS_REPO_PATH}/$p" ]; then
    git -C "{DOCS_REPO_PATH}" add -- "$p"
  elif git -C "{DOCS_REPO_PATH}" ls-files --error-unmatch "$p" >/dev/null 2>&1; then
    # Tracked file that no longer exists on disk — already staged by git rm
    :
  fi
  # Removal paths neither on disk nor tracked are tolerated (already-committed deletions)
done
```

### 3. Check for changes and commit

Use `--only` with the full allowlist so only owned paths are committed.
Unrelated staged/index and unstaged/worktree changes survive untouched.
Include paths whose deletion is staged (present in HEAD but absent from
the index after `git rm`). Filter out already-committed deletions
(absent from disk, index, and HEAD) so `commit --only` does not fail
on unknown pathspecs.

```bash
commit_paths=()
for p in "${owned_paths[@]}"; do
  if [ -f "{DOCS_REPO_PATH}/$p" ] || git -C "{DOCS_REPO_PATH}" ls-files --error-unmatch "$p" >/dev/null 2>&1; then
    commit_paths+=("$p")
  elif git -C "{DOCS_REPO_PATH}" rev-parse --verify "HEAD:$p" >/dev/null 2>&1; then
    # Path in HEAD but not in index — staged deletion, first removal
    commit_paths+=("$p")
  fi
  # Path absent from disk, index, and HEAD — already-committed deletion; skip
done

if [ ${#commit_paths[@]} -eq 0 ]; then
  echo "No owned paths present; skipping commit."
else
  git -C "{DOCS_REPO_PATH}" diff --cached --quiet -- "${commit_paths[@]}"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "No changes to owned paths; skipping commit."
  elif [ "$rc" -eq 1 ]; then
    git -C "{DOCS_REPO_PATH}" commit --only \
      -m "{COMMIT_MESSAGE}" \
      -- "${commit_paths[@]}"
  else
    echo "Git error (exit $rc); stopping." >&2; exit "$rc"
  fi
fi
```

This procedure handles text-only (array contains only the handoff),
lfs/git (handoff + manifest + each image), external (handoff + manifest),
removal runs (handoff + manifest + removed paths), and final-screenshot
removal (handoff + removed manifest + removed images) identically.

### 4. Pending attempt record (push safety)

Callers (`/publish` Step 8, `/respond` push section) follow this
protocol to ensure push failures are recoverable without re-deriving
ownership or adopting unknown ahead commits.

**Before push.** Write a `pending_attempt` object into
`publish-metadata.json`, preserving all existing fields:

| Field | Value |
|-------|-------|
| `commit_sha` | Exact HEAD SHA after the commit above |
| `branch` | Feature branch name |
| `expected_base` | Remote branch SHA before push, or `null` for first push |
| `owned_paths` | Array of paths included in the commit |
| `pr_number` | PR number (existing PR) or `null` (new PR) |
| `docs_repo_remote` | Docs repo remote URL (from config) |
| `handoff_file_path` | Repo-relative handoff path |
| `candidate_screenshot_storage` | Storage mode for this attempt |
| `candidate_screenshot_assets` | Array of `{id, filename, sha256, published_path}` entries |
| `timestamp` | ISO 8601 when the attempt was recorded |

The `pending_attempt` record is private authoring state — do not copy
it into the consumer-facing published manifest.

**On retry (when `pending_attempt` exists).** Before any file copy,
`git rm`, or new commit:

1. Verify local HEAD equals `pending_attempt.commit_sha`. If HEAD
   differs, stop — unknown commits exist; do not force-push, reset,
   or re-derive ownership.
2. Verify the current branch matches `pending_attempt.branch`.
   Verify the docs repo remote URL matches `pending_attempt.docs_repo_remote`.
3. Check whether `pending_attempt.commit_sha` already exists on the
   remote (`git ls-remote origin {branch}`):
   - **Already pushed:** skip push; proceed to metadata finalization.
   - **Not pushed:** re-attempt push.

**Initial new attempt** (no `pending_attempt` exists): require the
local branch to be at a known synced base (equal to
`origin/{branch}`, or a fresh branch from `{base-branch}`). If the
local branch is ahead of the remote by commits not created by this
invocation, stop.

**After successful push.** Verify the remote ref matches
`pending_attempt.commit_sha` exactly (`git ls-remote`). Then:

1. Finalize metadata from `pending_attempt` candidate values:
   set `screenshot_storage` to `candidate_screenshot_storage`,
   set `screenshot_assets` to `candidate_screenshot_assets`.
2. Remove `pending_attempt` from `publish-metadata.json`.
3. For a new PR, record `pr_number`, `branch`, and `handoff_file_path`.

Write steps 1–3 atomically — if the write fails, retain
`pending_attempt` so the next retry can re-finalize without a new
commit.

**Already-pushed, metadata-write failure.** If push succeeded (remote
SHA matches) but the metadata write fails, finalize from the
`pending_attempt` candidate values (`candidate_screenshot_storage`,
`candidate_screenshot_assets`) and the committed consumer state at
the verified SHA — never from the mutable authoring manifest.
Retain `pending_attempt` until the metadata write succeeds. Do not
create a new commit or PR.

**Unexpected state.** If the remote branch HEAD is neither the
expected base nor the pending commit SHA, stop. Do not force-push,
reset, or re-derive ownership from unknown commits.
