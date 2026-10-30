# Sync Helper Usage Reference

This reference documents the deterministic Python helper used by the
`/sync` phase.  Read this file in full **before** the first helper
operation in any sync run.

## Helper Discovery

The helper script lives at `scripts/sync_helper.py` under the design
package root.  From the built-in phase file `skills/sync.md`, it is at
`../scripts/sync_helper.py` — two directories up, then into `scripts/`.

To resolve the helper, record the absolute path of the **built-in**
`design/skills/sync.md` that you are reading — not `design/SKILL.md`
(which has a different directory depth) and not a project-level phase
override — and derive the helper from it:

```bash
BUILTIN_SYNC='<absolute path of the loaded built-in design/skills/sync.md>'
SYNC_HELPER="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().parents[1] / "scripts" / "sync_helper.py")' "$BUILTIN_SYNC")"
```

`Path.resolve()` follows symlinks, so this works for both the default
`~/.ai-workflows` install and a direct symlink from
`.claude/skills/design` to an arbitrary clone location (even without
`~/.ai-workflows`).  If a project-level phase override provides a
replacement `skills/sync.md`, the helper still comes from the built-in
package — always use the built-in source path, not the override path.

The helper **never contacts Jira** and **never mutates external state**.
It reads and writes only local artifact files and the sync manifest.
All Jira API calls, user approvals, and error-handling decisions remain
your responsibility.

## Subcommands

| Subcommand | Purpose |
|------------|---------|
| `detect-changes <artifacts-dir>` | Compare files against manifest; output JSON change plan |
| `prepare <file> <manifest> --type epic\|story [options]` | Read file once; return hash + rendered description (snapshot-consistent) |
| `resolve-refs <manifest-path> <text>` | Replace local refs (Story 1.01, Epic 1) with Jira keys |
| `render-description <file> <manifest> --type epic\|story [options]` | Render Jira-ready description with resolved refs |
| `update-manifest <manifest> --operation create\|update\|close --file <f> --jira-key <K> --content-hash <H> [--item-type epic\|story] [--epic-file <E>] [options]` | Record one successful Jira operation (`--epic-file` required for stories) |
| `compute-hash <file>` | Print SHA-256 of file content |
| `migrate-manifest <manifest>` | Upgrade v1 manifest to v2 in place |

The `prepare` subcommand is preferred over separate `compute-hash` +
`render-description` calls.  It reads the file once and guarantees the
hash corresponds to exactly the content used in the description.  Pass
the returned `content_hash` to `update-manifest` after a successful
Jira write.

## Reference Resolution

The helper's `resolve-refs` subcommand replaces local identifiers with
Jira keys from the manifest:

- `Story 1.01` → look up `story-01-*.md` under `epic-1/` in the manifest → `EDM-XXXX`
- `Epic 1` → look up `epic-1-*.md` in the manifest → `EDM-YYYY`
- `Stories 1.01, 2.01, 3.01` → resolve each → `EDM-XXXX, EDM-AAAA, EDM-BBBB`

The manifest is built incrementally: each issue's key is recorded
immediately after creation.  Since epics are created first and stories
are created in epic order (Epic 1 stories before Epic 2 stories),
dependencies — which reference earlier stories — are always resolvable
by the time they're needed.

If a reference cannot be resolved (the referenced item hasn't been
created yet or failed to create), the helper leaves the local
identifier, annotates it with `[unresolved]`, and you must flag it to
the user.

## Prepare — Snapshot-Consistent Hash + Description

For each new or changed epic:

```bash
PREP=$(python3 "$SYNC_HELPER" prepare \
  .artifacts/design/{issue-key}/06-stories/{epic-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type epic \
  --design-doc-link "{link}" \
  --feature-key "{feature-key}")
```

`PREP` is JSON with `content_hash`, `description`, `summary`
(Jira-ready title without numbering), `size` (T-shirt size), and
`title` (raw).

For each new or changed story:

```bash
PREP=$(python3 "$SYNC_HELPER" prepare \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type story \
  --design-doc-link "{link}" \
  --epic-jira-key "{epic-jira-key}" \
  --story-type "{prefix}")
```

`PREP` is JSON with `content_hash`, `description`, `summary`
(`[PREFIX] title` without numbering), `story_type`, `dependencies`
(resolved text), and `title` (raw).

## Checkpoint — update-manifest

Record each successful Jira operation immediately after it succeeds.
Pass the `content_hash` from the `PREP` call that produced the content
actually submitted to Jira.

Epic create:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation create \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type epic \
  --title "{title}" \
  --size "{size}" \
  --feature-key "{feature-key}"
```

Epic update (same args, `--operation update`; `--feature-key` optional
after first call):

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation update \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type epic
```

Story create:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation create \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type story \
  --title "{summary from PREP}" \
  --epic-file "{epic-file}"
```

Story update (same args, `--operation update`):

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation update \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type story \
  --epic-file "{epic-file}"
```

Child story close (within parent cascade):

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{child-story-file}" \
  --jira-key "{child-story-jira-key}" \
  --content-hash "{child hash from step (a)}" \
  --item-type story \
  --epic-file "{parent-epic-file}"
```

Epic close:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{hash from step 2, or empty for orphans}" \
  --item-type epic
```

Standalone story close:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{hash from step 1, or empty for orphans}" \
  --item-type story \
  --epic-file "{epic-file}"
```

Retain the exact parameter bundle (file, key, hash, type, parent) for
checkpoint-only retry per the close-checkpoint recovery rule in the
sync phase.

## Selecting the Close Transition

Use the Jira API to query available transitions for the issue and
select the terminal/done-category transition.  If multiple terminal
transitions are available, prefer "Done" over "Closed."  If no terminal
transition is available from the current status, report the error and
let the user handle it in Jira.
