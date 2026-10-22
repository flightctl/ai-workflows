---
name: controller
description: Phase dispatcher for the rebase-stack workflow.
---

# Rebase Stack Controller

## Before Any Phase

1. Read `../guidelines.md`. The Scope section decides whether this workflow may
   run at all.
2. Run the shared gate in `preflight.md`. Every phase depends on it and no
   phase may skip it.
3. Announce the phase, then follow its file.
4. Stop and wait for the user. Never auto-advance.

## Refuse When

- `gh stack` is not installed — report and stop. Do not install it.
- `gh stack view --json` exits 2 — this is not a stack. Do not initialize one.
  Point the user at `git rebase` for a single branch.
- The request is "rebase my branch onto main" with no stack involved — this is
  the wrong workflow.

## Phases

1. **Start** (`/start`) — `start.md`
   Reports the starting state, snapshots every branch tip, then rebases the
   **entire** stack onto the updated base with
   `gh stack rebase --remote {base-remote}`. Exits early if nothing needs
   rebasing. Local-only. Hands off to `/validate`, or to `/continue` on
   conflict.

2. **Continue** (`/continue`) — `continue.md`. Repeatable.
   Needed only when a rebase paused on a conflict. Resumes after the user has
   staged the resolution. Local-only.

3. **Validate** (`/validate`) — `validate.md`
   Re-fetches, re-reads stack health, then runs the project's lint and test
   commands. Default: the trunk-adjacent branch only, the layer that merges
   first. `/validate --all`: every branch bottom-to-top, stopping at the first
   failure, for when the upper layers must be exercised too. Does not push.

4. **Push** (`/push`) — `push.md`
   Pushes every branch to `{push-remote}` with `--force-with-lease --atomic`,
   then opens PRs for branches that lack one, fork-aware.

### Typical Flow

```text
start → validate → push → done
start → (conflict) → continue … → validate → push → done
start → (already up to date) → done
```

## Rules

- Never auto-advance between phases.
- Resolve helper scripts relative to this package (`preflight.md` Step 1), never
  from a fixed install path.
- Pass phase arguments through. `/validate --all` changes validation scope;
  do not drop or invent flags.
- Never assume `origin`. Use `{base-remote}` and `{push-remote}` from preflight
  and pass `--remote` explicitly on every `gh stack` call that accepts it.
- Stop and report on any unexpected git or `gh stack` state. Do not guess.
