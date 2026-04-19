---
name: kcs
description: >-
  KCS article workflow that gathers bug context from Jira and user input,
  drafts a KCS Solution article in markdown, validates it against the KCS
  Content Standard, and produces a handoff message for the support engineer.
  Use when writing KCS articles for known issues with workarounds.
  Activated by commands: /gather, /draft, /validate, /handoff.
---

# KCS Article Workflow Orchestrator

When the user invokes a command, read `commands/{command}.md` for full
instructions. Otherwise, read `skills/controller.md` to determine which phase
to execute based on the user's input.

## Phases

| Phase | Command | Input | Output |
|-------|---------|-------|--------|
| Gather | `/gather` | Jira issue key/URL + user context | `01-context.md` |
| Draft | `/draft` | Context from Gather | `02-kcs-draft.md` |
| Validate | `/validate` | Draft from Draft | Updated draft with fixes |
| Handoff | `/handoff` | Validated draft | `03-handoff-message.md` |

All artifacts: `.artifacts/kcs/{issue-key}/`. Advance only after user confirms.
Resolve all `/validate` blockers before `/handoff`. On failure: stop, report,
offer retry.

## `/gather`

1. Call Jira MCP `get_issue(issue_key="{key}")` — extract summary, description,
   comments, linked issues. Read-only: never modify Jira.
2. Ask user for: symptoms, environment, workarounds, root cause.
3. Fill `templates/context.md` → write `01-context.md`.

## `/draft`

1. Load `01-context.md`.
2. Produce a markdown article with these sections and metadata:

```markdown
# KCS Solution Draft — {ISSUE_KEY}
> **Article Type:** Solution
> **Article Confidence:** Not-Validated (WIP)
> **Product:** {PRODUCT_NAME_AND_VERSION}

## Title
{Symptom + product name, one line, no brackets around product names}

## Issue
{Customer-visible problem. Error messages in backticks or fenced blocks.}

## Environment
- {Product and version per line, official names}

## Diagnostic Steps
1. {One action per step, commands in fenced blocks, `<PLACEHOLDER>` for values}

## Resolution
**Workaround** (if not a permanent fix)
1. {Numbered steps, fenced commands, ends with verification step}

## Root Cause
{Technical mechanism. Link Jira ticket tracking permanent fix.}
```

1. Style rules: present tense, no personal pronouns, backticks for paths /
   commands / config keys, fenced code blocks for commands and output, en-US
   spelling. See `templates/section-guidance.md` for full per-section rules.
2. Write `02-kcs-draft.md`.

## `/validate`

Load `02-kcs-draft.md` and check against `templates/validation-checklist.md`:

- All sections present and non-empty (Title, Issue, Environment, Diagnostic
  Steps, Resolution, Root Cause)
- Title: one line, describes symptom + product, no prefix
- Issue: customer perspective, no workaround content, no internal links
- Diagnostic Steps: numbered, one action each, commands in fenced blocks
- Resolution: workarounds labeled, ends with verification, no internal links
- Style: present tense, no pronouns, backticks for technical terms

Fix violations inline. List remaining issues for the user.

## `/handoff`

1. Load validated `02-kcs-draft.md`.
2. Compose message for the support engineer: article text, open items, next
   steps (publish to portal, set confidence level).
3. Write `03-handoff-message.md`, show to user before they send.

For principles, hard limits, and quality rules, see `guidelines.md`.
