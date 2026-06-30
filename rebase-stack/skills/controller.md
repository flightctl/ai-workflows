---
name: controller
description: Phase dispatcher for the rebase-stack workflow.
---

# Rebase Stack Controller

## Phases

1. **Start** (`/start`) — `start.md`
   Verify the `gh-stack` extension, detect or initialize the stack, then rebase
   it onto the updated base with `gh stack rebase`. Local-only — does not push.
   On success, hands off to `/validate`.

2. **Continue** (`/continue`) — `continue.md`. Repeatable.
   Only needed when `/start` (or a previous `/continue`) stopped due to a
   merge conflict. Resumes the rebase after the user resolves conflicts.
   Local-only — does not push. On success, hands off to `/validate`.

3. **Validate** (`/validate`) — `validate.md`
   Re-fetches to check remote currency, validates lint and unit tests on each
   branch independently, and shows a branch overview table. Does not push.
   On success, hands off to `/push`.

4. **Push** (`/push`) — `push.md`
   Pushes all branches atomically with `gh stack push`, then creates any
   missing PRs with fork-aware targeting.

### Typical Flow

```text
start → (success) → validate → push → done
start → (conflict) → [continue loop] → (success) → validate → push → done
```

## How to Execute a Phase

1. Read `../guidelines.md` for safety rules before executing any phase.
2. Announce the phase to the user.
3. Read and follow the corresponding skill file.
4. Stop and wait for the user between phases — do not auto-advance.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- Stop and report on any unexpected git or `gh stack` state. Do not guess or continue past errors.
