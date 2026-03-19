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
2. Extract the issue key (e.g. `EDM-3467` from a Jira URL, `#421` from a GitHub issue)
3. Create the artifact directory immediately: `mkdir -p .artifacts/bugfix/{issue}`
4. Execute the phase loop below, starting at `/diagnose`
5. After each phase, proceed directly to the next — do not stop or wait

## Phase Loop

Run these phases in order. Read each skill from the same `skills/` directory:

| Order | Phase | Skill file | Done signal |
|-------|-------|------------|-------------|
| 1 | `/diagnose` | `diagnose.md` | Skill Output artifacts written |
| 2 | `/fix` | `fix.md` | Code changes in working tree; skill Output artifacts written |
| 3 | `/test` | `test.md` | All tests pass; skill Output artifacts written |
| 4 | `/review` | `review.md` | Skill Output artifacts written |
| 5 | `/document` | `document.md` | Skill Output artifacts written |

## How to Execute a Phase

1. Announce the phase: *"Starting /fix (unattended mode)."*
2. Read the skill file from the table above. While executing it, apply these overrides:
   - "Never auto-advance" / "Stop and wait" / "re-read the controller" — ignore; proceed to the next phase in this table
   - "Stop and request human guidance" (escalation) — make a best-effort decision, document it in the artifacts, and continue
3. Execute the skill's steps fully, including its Output section — every artifact the skill specifies must be written to disk
4. Proceed to the next phase in the Phase Loop

## Commit Policy

**Do NOT create git commits.** All code changes and artifacts remain in the working tree as an uncommitted diff. No phase in the unattended workflow may run `git add` or `git commit`.

Committing is the responsibility of the `/pr` phase, which the unattended workflow does not run. When `/pr` is invoked later (by the user or a separate step), it stages and commits all accumulated changes as a single squashed commit.

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
Result: <summary of changes or reason for early stop>
Retries: <any fix/test retry cycles>
Escalations: <decisions made autonomously, if any>
```

## Example Session

```text
Bot triggers: "Fix issue #421 — NullPointerException on login"

/diagnose  → traces root cause to AuthService.java:87
/fix       → adds null-check on fix/issue-421
/test      → tests fail → retry /fix → tests pass ✓
/review    → "fix and tests are solid"
/document  → writes changelog entry and pr-description.md
```

## Guidelines

For principles, hard limits, safety, and quality rules, follow `guidelines.md`.
