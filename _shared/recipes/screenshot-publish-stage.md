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

### 2. Stage owned paths

Stage every path in the allowlist. For paths that still exist on disk,
use `git add`. For tracked deletions (removed screenshots, removed
manifest), `git rm` will have already staged them — include them in the
array so the `--only` commit sees them.

```bash
for p in "${owned_paths[@]}"; do
  if [ -f "{DOCS_REPO_PATH}/$p" ]; then
    git -C "{DOCS_REPO_PATH}" add -- "$p"
  elif git -C "{DOCS_REPO_PATH}" ls-files --error-unmatch "$p" >/dev/null 2>&1; then
    # Tracked file that no longer exists on disk — already staged by git rm
    :
  fi
  # Skip paths that are neither on disk nor tracked (optional paths not present)
done
```

### 3. Check for changes and commit

Use `--only` with the full allowlist so only owned paths are committed.
Unrelated staged/index and unstaged/worktree changes survive untouched.

```bash
git -C "{DOCS_REPO_PATH}" diff --cached --quiet -- "${owned_paths[@]}"
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "No changes to owned paths; skipping commit."
elif [ "$rc" -eq 1 ]; then
  git -C "{DOCS_REPO_PATH}" commit --only \
    -m "{COMMIT_MESSAGE}" \
    -- "${owned_paths[@]}"
else
  echo "Git error (exit $rc); stopping." >&2; exit "$rc"
fi
```

This procedure handles text-only (array contains only the handoff),
lfs/git (handoff + manifest + each image), external (handoff + manifest),
removal runs (handoff + manifest + removed paths), and final-screenshot
removal (handoff + removed manifest + removed images) identically.
