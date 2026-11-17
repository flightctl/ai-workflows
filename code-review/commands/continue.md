---
name: code-review:continue
description: "Implement accepted changes, re-review, present findings or finalize"
---
# /continue

Before any artifact access, follow [the shared artifact resolver](../../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

Read `../skills/controller.md` only if it is not already in this session.
Resolve the continue skill via `../../_shared/recipes/phase-override-resolution.md`
(WORKFLOW=`code-review`, PHASE_FILE=`continue.md`). Read the resolved
`continue.md` and execute it. Do not glob this workflow. Do not call
`GetDynamicTools`.

Dispatch the **continue** phase. Context:

$ARGUMENTS
