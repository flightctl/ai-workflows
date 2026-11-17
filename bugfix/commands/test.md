---
name: bugfix:test
description: "Verify the fix and create regression tests"
---
# /test

Before any artifact access, follow [the shared artifact resolver](../../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

Read `../skills/dispatch.md` and follow it with `PHASE=test`.

Context:

$ARGUMENTS
