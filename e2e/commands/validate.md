---
name: e2e:validate
description: "Run e2e tests, check for anti-patterns, verify scenario coverage, assess PR readiness"
---
# /validate

Before any artifact access, follow [the shared artifact resolver](../../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

Read `../skills/dispatch.md` and follow it with `PHASE=validate`.

Context:

$ARGUMENTS
