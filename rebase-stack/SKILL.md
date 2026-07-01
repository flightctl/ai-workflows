---
name: rebase-stack
version: 0.1.0
description: >-
  Rebases a stacked-branch chain onto an updated base branch using gh-stack,
  guides through conflict resolution if needed, validates each branch, and
  pushes all updated branches. Creates PRs for any branch that lacks one,
  with fork-aware targeting. Works on repos with or without Stacked PRs enabled.
  Use when rebasing stacked stories or PRs onto main or another updated branch.
  Activated by commands: /start, /continue, /validate, /push.
---
# Rebase Stack Workflow

## Quick Start

1. If the user invoked `/start`, read `commands/start.md` and follow it.
2. If the user invoked `/continue`, read `commands/continue.md` and follow it.
3. If the user invoked `/validate`, read `commands/validate.md` and follow it.
4. If the user invoked `/push`, read `commands/push.md` and follow it.
5. Otherwise, read `skills/controller.md` and present the available phases to the user.

If a step fails or produces unexpected output, stop and report to the user.
Always wait for the user before advancing to the next phase.

For safety rules, see `guidelines.md`.
