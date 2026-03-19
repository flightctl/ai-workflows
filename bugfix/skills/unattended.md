---
name: unattended
description: Autonomous bugfix workflow that runs diagnose, fix, test, review, and document phases end-to-end without human interaction. Use when a bot or CI pipeline needs to diagnose a bug, implement a fix, verify it with tests, and produce documentation automatically.
---
# Unattended Bugfix Workflow

Runs the bugfix phases from `/diagnose` through `/document` without stopping
for human input. Designed for bots and CI pipelines where no interactive
feedback is available.

This workflow reuses the individual phase skills (`diagnose.md`, `fix.md`,
`test.md`, `review.md`, `document.md`) but orchestrates them sequentially
with self-correction loops instead of waiting for human input between phases.

## Input

The bot provides a bug report, issue URL, or description. No prior phases
(`/assess`, `/reproduce`) are required — `/diagnose` works directly from the
provided input.

## Configuration

Before starting, determine these values from your context (task file,
calling system instructions, or environment). Use the defaults if not
specified.

| Setting | Default | Override by stating in input |
|---------|---------|------------------------------|
| `branch` | *(none — `/fix` creates one)* | e.g. "branch: fix/EDM-3511" |
| `max_retries` | 3 | e.g. "max_retries: 5" |
| `lint_command` | *(auto-detect)* | e.g. "lint_command: make lint" |

If `branch` is provided, the `/fix` phase must use that branch as-is — do
not create a new branch or switch away from it. If the current working tree
is not already on the given branch, check it out first
(`git checkout <branch>`), but do not create it.

`max_retries` applies to feedback loops (see below).

## Ground Rules

- **Do not stop for human input.** Run all phases to completion.
- **Do not create git commits.** All code changes remain in the working tree
  as an uncommitted diff. Committing is the responsibility of the `/pr`
  phase, which this workflow does not run.
- **Do not push code or create PRs.** The calling system handles this.
- **Do not write files outside `.artifacts/bugfix/{issue}/` and the project
  source tree.** Scratch files, logs, and notes go in the artifact directory.
  Only production source code and test file changes go outside it.
- **Follow `guidelines.md`** for principles, hard limits, and quality
  standards. Where guidelines say "stop and request human guidance," write
  an escalation report (see Escalation below) and terminate.
- **Read and follow the project's `AGENTS.md`** if one exists. The project's
  conventions take precedence over generic defaults.

## Quick Start

1. Read the bug report / issue URL / description provided as input
2. Extract the issue key (e.g. `EDM-3467` from a Jira URL, `#421` from
   a GitHub issue)
3. Create the artifact directory immediately:
   `mkdir -p .artifacts/bugfix/{issue}`
4. Execute the phase loop below, starting at `/diagnose`
5. After each phase, proceed directly to the next — do not stop or wait

## Phase Loop

Run these phases in order. Read each skill from the same `skills/` directory:

| Order | Phase | Skill file | Done signal |
|-------|-------|------------|-------------|
| 1 | `/diagnose` | `diagnose.md` | Root cause analysis written |
| 2 | `/fix` | `fix.md` | Code and test changes in working tree; implementation notes written |
| 3 | `/test` | `test.md` | All tests pass; verification report written |
| 4 | `/review` | `review.md` | Review findings written |
| 5 | Lint | *(see below)* | Lint passes cleanly |
| 6 | `/document` | `document.md` | Documentation artifacts written |
| 7 | Session context | *(see below)* | Session context manifest written |

## How to Execute a Phase

1. Announce the phase: *"Starting /fix (unattended mode)."*
2. Read the skill file from the table above. While executing it, apply
   these overrides:
   - "Never auto-advance" / "Stop and wait" / "re-read the controller" —
     ignore; proceed to the next phase in this table
   - "Stop and request human guidance" (escalation) — write an escalation
     report (see Escalation below) and terminate
   - "Create Feature Branch" (fix.md Step 2) — skip if `branch` is set or
     a branch already exists; stay on the current branch
3. Execute the skill's steps fully, including its Output section — every
   artifact the skill specifies must be written to disk
4. Proceed to the next phase in the Phase Loop

## Phase Overrides

These override instructions in the individual skills when running
unattended:

### /diagnose

- If no reproduction report exists, skip the "Review Reproduction" step
  and work directly from the bug report.
- If diagnosis confidence is below 80%, document your caveats and proceed.
  In unattended mode, a best-effort diagnosis is better than stopping.

### /fix

- **Unit tests are mandatory.** You MUST modify or create at least one test
  file (e.g., `*_test.go`, `test_*.py`, `*.test.js`, `*.spec.ts`). Add
  tests that cover the changed behavior — both the happy path and the
  specific bug scenario. Do not defer tests to a later step. The `/test`
  phase will verify that test files were actually modified; if they weren't,
  you will be sent back here.
  **Exception:** If the project has no test framework or the bug is in
  infrastructure/configuration where no testable code path exists, document
  why tests were not added in implementation notes and proceed.
- **Confidence threshold**: If you proceeded past a low-confidence diagnosis,
  the 80% escalation threshold from `guidelines.md` does not apply to the
  fix phase. Attempt the fix based on your best-effort diagnosis. The
  self-review in `/review` will catch inadequate fixes.
- **Write implementation notes** to
  `.artifacts/bugfix/{issue}/implementation-notes.md`. A future AI session
  may need to address PR review comments without any memory of this session.
  Record the context it will need:
  - Files modified and why (with `file:line` references)
  - Design choices made and alternatives considered or rejected
  - Test strategy: what scenarios are covered, what was intentionally
    excluded and why

### /test

**Gate check**: Before running tests, verify that you actually added or
modified at least one test file (e.g., `*_test.go`, `test_*.py`,
`*.test.js`, `*.spec.ts`). If no test files were modified, **stop and
return to /fix** — do not proceed. This gate-check return counts toward
the `/test` retry limit (`max_retries`).

### /document

If `max_retries` was exhausted during `/review` with unresolved findings,
include a **Known Issues** section in `pr-description.md` listing the
unresolved concerns so the human reviewer knows to look more carefully.

### Lint

Run the project's lint and format checks after `/review` passes.

**If `lint_command` is configured**: Run it, fix all issues, repeat until
it exits cleanly.

**If `lint_command` is not configured**, detect it using this priority
order:

1. Check the project's `AGENTS.md` for a lint command.
2. Check the `Makefile` for `lint` or `fmt` targets.
3. Check `package.json` scripts for a `lint` script.
4. Fall back to language-specific defaults based on file extensions present
   in the project:
   - Go: `gofmt -w . && golangci-lint run ./...`
   - Python: `ruff check --fix . && ruff format .` (if `ruff` is
     installed); otherwise `black . && flake8`
   - JS/TS: `npx eslint --fix .`

If no lint command can be detected by any of the above methods, skip
this phase and note "lint: skipped (no linter detected)" in the
completion report.

Fix all reported issues before proceeding.

### Session Context

Write a session context manifest to
`.artifacts/bugfix/{issue}/session-context.md`.

This file is the entry point for any future AI session that works on this
PR without memory of the current session (e.g., addressing PR review
feedback via `/feedback`). Keep it concise.

**Contents** (use this structure):

```markdown
# Session Context

## Summary
[1-2 sentence description of what was done and why]

## Key Design Decisions
[What approach was taken, what alternatives were rejected, and why.
Include file:line references for the core changes.]

## Test Strategy
[What scenarios are covered by tests, what was intentionally
excluded and why]

## Known Concerns
[Any risks, caveats, or unresolved issues from the self-review.
If the review was clean, say so.]

## Artifacts
- `root-cause.md` — Root cause analysis
- `implementation-notes.md` — Detailed file changes and rationale
- `verification.md` — Test results and coverage
- `review.md` — Self-review findings
```

## Feedback Loops

Even in unattended mode, phase failures trigger retries before continuing.
Each retry loop is capped at `max_retries` (default: 3):

- `/test` fails → return to `/fix`, rework the implementation, re-run
  `/test`. Repeat up to `max_retries` times; if still failing, document
  failures and continue to `/review`.
- `/review` verdict is "fix is inadequate" or finds CRITICAL/HIGH severity
  issues → return to `/fix`, revise, re-run `/test` and `/review` (both
  phases must pass on retry, since the review triggered the rework).
  Repeat up to `max_retries` times; if still inadequate, document
  concerns in the review artifact and continue to `/document`.

## Escalation

Retry-limit exhaustion (described above) does NOT trigger a hard stop —
those cases degrade gracefully as described in the Feedback Loops section.

However, when `guidelines.md` escalation criteria are triggered (security
concerns, architectural decisions, breaking API changes — except where
overridden in Phase Overrides above), write
`.artifacts/bugfix/{issue}/escalation.md` with:

- Which phase triggered escalation and why
- What was attempted
- Why it could not be resolved automatically
- Suggested next steps for a human

Then **stop**. Do not continue past the failed phase.

## Completion Report

When all phases finish, output:

```text
## Unattended Run Complete

Phases: diagnose ✓ → fix ✓ → test ✓ → review ✓ → lint ✓ → document ✓ → context ✓
Artifacts: .artifacts/bugfix/{issue}/
Result: <summary of changes or reason for early stop>
Retries: <any fix/test retry cycles>
Degraded phases: <phases that exhausted retries and continued with documented concerns, if any>
```

## Example Session

```text
Bot triggers: "Fix issue #421 — NullPointerException on login"

/diagnose  → traces root cause to AuthService.java:87
/fix       → adds null-check on fix/issue-421
/test      → tests fail → retry /fix → tests pass ✓
/review    → "fix and tests are solid"
lint       → gofmt + golangci-lint pass ✓
/document  → writes changelog entry and pr-description.md
context    → writes session-context.md for future sessions
```

## Guidelines

For principles, hard limits, safety, and quality rules, follow
`guidelines.md`. Where guidelines say "stop and request human guidance,"
write an escalation report and terminate (see Escalation above).
