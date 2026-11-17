---
name: rebase-stack:push
description: Push every stack branch atomically to the resolved push remote and open missing PRs.
---
# /push

Before any artifact access, follow [the shared artifact resolver](../../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

Read `../skills/controller.md` and follow it.

Dispatch the **push** phase. Context:

$ARGUMENTS
