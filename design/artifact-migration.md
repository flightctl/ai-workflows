# Design Artifact Filename Migration

**Remove after: 2026-10-01** — Once all in-flight `/design` workflows
have completed or re-run `/draft`, delete this file and remove all
references to it (grep for `artifact-migration`).

## Why

Testplan generation moved from `/decompose` to `/draft`. The artifact
numbering was updated to reflect the new generation order:

| Old filename | New filename |
|-------------|-------------|
| `04-epics.md` | `05-epics.md` |
| `05-stories/` | `06-stories/` |
| `06-coverage.md` | `07-coverage.md` |
| `07-testplan.md` | `04-testplan.md` |

## Rules

**When reading an artifact:** Try the new filename first. If not found,
try the old filename. If neither exists, the artifact does not exist —
follow the phase's normal "artifact not found" behavior.

**When writing an artifact:** Always use the new filename. Do not write
to old filenames.
