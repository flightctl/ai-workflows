---
name: triage:assess
description: "Deep-dive assessment of a single bug"
---
# /assess

Before any artifact access, follow [the shared artifact resolver](../../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

Read `../skills/assess.md` and follow it.

Announce: "Starting /assess (full single-issue triage)" before executing.

Context: the user may paste **only a Jira issue URL** (project is inferred from the issue key — `$ARGUMENTS` can be empty). Otherwise they provide a **project key** and error text in the message or in `$ARGUMENTS`.

$ARGUMENTS
