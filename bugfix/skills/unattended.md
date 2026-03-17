---
name: unattended
description: Autonomous bugfix workflow that runs diagnose, fix, test, review, and document phases end-to-end without human interaction. Use when a bot or CI pipeline needs to diagnose a bug, implement a fix, verify it with tests, and produce documentation automatically.
---
# Unattended Bugfix Workflow

Runs the bugfix phases from `/diagnose` through `/document` without stopping for human input.
Designed for bots and CI pipelines where no interactive feedback is available.

## Input

The bot provides a bug report, issue URL, or description. No prior phases (`/assess`, `/reproduce`) are required — `/diagnose` works directly from the provided input.

## Defaults

| Setting | Default | Override by stating in input |
|---------|---------|------------------------------|
| `max_retries` | 3 | e.g. "max_retries: 5" |
| `branch` | *(none — `/fix` creates one)* | e.g. "branch: fix/EDM-3511" |

`max_retries` applies to feedback loops (see below).

If `branch` is provided, the `/fix` phase must use that branch as-is — do not create a new branch or switch away from it. If the current working tree is not already on the given branch, check it out first (`git checkout <branch>`), but do not create it.

## Quick Start

1. Read the bug report / issue URL / description provided as input
2. Execute the phase loop below, starting at `/diagnose`
3. After each phase, proceed directly to the next — do not stop or wait

## Phase Loop

Run these phases in order. Read each skill from the same `skills/` directory:

| Order | Phase | Skill file | Done signal |
|-------|-------|------------|-------------|
| 1 | `/diagnose` | `diagnose.md` | `diagnose.md` artifact written |
| 2 | `/fix` | `fix.md` | Code changes committed on feature branch |
| 3 | `/test` | `test.md` | All tests pass |
| 4 | `/review` | `review.md` | Review verdict rendered |
| 5 | `/document` | `document.md` | Documentation artifacts written |

## How to Execute a Phase

1. Announce the phase: *"Starting /fix (unattended mode)."*
2. Read the skill file from the table above
3. Execute the skill's steps
4. **Override:** when the skill says "re-read the controller" or "stop and wait," ignore that — proceed directly to the next phase in the table

```bash
# Example: commands the workflow runs autonomously
mkdir -p .artifacts/bugfix/421
rg "NullPointerException" --type java -l
git checkout -b fix/issue-421
git commit -m "fix: add null-check in AuthService#authenticate"
```

## Overrides from Bugfix Controller

This skill reuses the phase skills in `skills/*.md` and `guidelines.md` with these overrides:

| Bugfix controller rule | Unattended override |
|------------------------|---------------------|
| "Never auto-advance. Always wait for the user between phases." | Auto-advance to the next phase immediately. |
| "Stop and wait for the user to tell you what to do next." | Proceed to the next phase in the loop. |
| "Re-read the controller for next-step guidance." | Return to this skill's Phase Loop and continue. |
| "Stop and request human guidance" (escalation) | Make the best-effort decision, document it in the artifacts, and continue. |

## Feedback Loops

Even in unattended mode, phase failures trigger retries before continuing.
Each retry loop is capped at `max_retries` (default: 3):

- `/test` fails → return to `/fix`, rework the implementation, re-run `/test`. Repeat up to `max_retries` times; if still failing, document failures and continue to `/review`.
- `/review` verdict is "fix is inadequate" → return to `/fix`, revise, re-run `/test` and `/review`. Repeat up to `max_retries` times; if still inadequate, document concerns in the artifacts and continue to `/document`.

## Completion Report

When all phases finish (or if the workflow stops early), output:

```text
## Unattended Run Complete

Phases: diagnose ✓ → fix ✓ → test ✓ → review ✓ → document ✓
Artifacts: .artifacts/bugfix/{issue}/
Result: <commit SHA or reason for early stop>
Retries: <any fix/test retry cycles>
Escalations: <decisions made autonomously, if any>
```

## Example Session

```text
Bot triggers: "Fix issue #421 — NullPointerException on login"

/diagnose  → traces root cause to AuthService.java:87
/fix       → adds null-check, commits on fix/issue-421
/test      → tests fail → retry /fix → tests pass ✓
/review    → "fix and tests are solid"
/document  → writes changelog entry and pr-description.md
```

## Guidelines

For principles, hard limits, safety, and quality rules, follow `guidelines.md`.
