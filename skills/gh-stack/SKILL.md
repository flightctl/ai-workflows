---
name: gh-stack
version: 0.1.0
description: >-
  Manages stacked PRs with gh-stack — creation, viewing, editing, push, submit,
  sync, rebase, merge, and checkout. Use when splitting work into reviewable
  branches, managing dependent PRs, whenever the user mentions a stack, branch
  layers, or gh stack, or whenever a stack is already checked out.
---

# gh-stack

`gh stack` is a GitHub CLI extension for stacked branches and pull requests.
Read [references/usage.md](references/usage.md) for setup, the non-interactive
command table, core workflow loops, and exit codes.

Open the reference whose trigger matches the task:

- [references/stack-design.md](references/stack-design.md) — before creating a
  stack or deciding layers.
- [references/commands.md](references/commands.md) — on unexpected failures or
  for preconditions, side effects, and ordering guarantees.
- [references/troubleshooting.md](references/troubleshooting.md) — on conflicts,
  divergence, restructuring, or driving stacks from another tool.
