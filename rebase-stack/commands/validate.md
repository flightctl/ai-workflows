---
name: rebase-stack:validate
description: Refresh remotes and run lint and tests on the stack — the trunk-adjacent branch by default, or every branch with --all.
---
# /validate

Read `../skills/controller.md` and follow it.

Dispatch the **validate** phase.

Options:

- (no arguments) — validate the trunk-adjacent branch only. Fastest; it covers
  the layer that merges first.
- `--all` — validate every branch in the stack, bottom to top, stopping at the
  first failure. Use when the layers above the bottom must also be exercised.

Context:

$ARGUMENTS
