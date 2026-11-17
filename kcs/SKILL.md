---
name: kcs
version: 0.4.0
description: >-
  KCS article workflow that gathers bug context from Jira and user input,
  drafts a KCS Solution article in markdown, validates it against the KCS
  Content Standard, and produces a handoff message for the support engineer.
  Use when writing KCS articles for known issues with workarounds.
  Activated by commands: /gather, /draft, /validate, /handoff.
---

# KCS Article Workflow Orchestrator
Before any artifact access, follow [the shared artifact resolver](../_shared/recipes/resolve-artifacts.md); carry `ARTIFACTS_ROOT` across CWD changes.

## Quick Start

1. If the user invoked a specific command (e.g. `/draft`, `/validate`), read `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to determine which phase to execute based on the user's input.

If a step fails or produces unexpected output, stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, and quality rules, see `guidelines.md`.
