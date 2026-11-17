---
name: code-review:start
description: "Discover project context, review uncommitted changes, present findings for decision"
---
# /start

Before any artifact access, follow [the shared artifact resolver](../../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

Read `../skills/controller.md` only if it is not already in this session.
Resolve the start skill via `../../_shared/recipes/phase-override-resolution.md`
(WORKFLOW=`code-review`, PHASE_FILE=`start.md`). Read the resolved
`start.md` and execute it. Do not glob this workflow. Do not call
`GetDynamicTools`.

Dispatch the **start** phase. Context:

$ARGUMENTS
