---
name: rebase-stack
version: 1.0.0
description: >-
  Rebases a gh-stack-tracked chain of stacked branches onto its updated base,
  guides conflict resolution, validates the stack, and pushes every branch
  with fork-aware PR creation. Requires the gh-stack extension and an existing
  tracked multi-branch stack; refuses to run otherwise. Do NOT use it to rebase
  a single branch onto main — plain git rebase does that.
  Activated by commands: /start, /continue, /validate, /push.
---
# Rebase Stack Workflow

Read `skills/controller.md` and follow it. It gates every phase, then routes:

| Command | Phase |
|---------|-------|
| `/start` | `commands/start.md` — rebase the whole stack |
| `/continue` | `commands/continue.md` — resume after a conflict |
| `/validate` | `commands/validate.md` — test the trunk-adjacent branch, or every branch with `--all` |
| `/push` | `commands/push.md` — push, then open missing PRs |

With no command, present the phases above and wait.

Refuses to run unless `gh stack` is installed and `gh stack view --json` exits
0. Neither has a fallback. See `guidelines.md` for scope and safety rules.
