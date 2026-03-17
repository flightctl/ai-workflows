---
name: automated
description: Unattended bugfix pipeline that chains diagnose, fix, test, and review with self-correction loops. Designed for CI/CD bots and automated systems.
---

# Automated Bugfix Pipeline

You are an automated bugfix agent running without human interaction. Your job
is to diagnose a bug, implement a fix with tests, verify it, and self-review
the result — all in a single unattended session.

This pipeline reuses the individual phase skills (`diagnose.md`, `fix.md`,
`test.md`, `review.md`) but orchestrates them sequentially with
self-correction loops instead of waiting for human input between phases.

**This file replaces `controller.md` for automated runs.** When a skill says
"re-read the controller for next-step guidance," ignore that directive and
return here to continue with the next phase.

## When to Use This

- A bug report has already been prepared and placed in a known location
- A working branch has already been created
- No human will be available to guide phase transitions
- The calling system handles branch management, commits, and PR creation

For interactive sessions with a human, use `controller.md` instead.

## Configuration

Before starting, determine these values from your context (task file,
calling system instructions, or environment). Use the defaults if not
specified.

| Setting | Default | Description |
|---------|---------|-------------|
| `TASK_FILE` | `.ai-bot/task.md` | Bug report or task description |
| `ARTIFACT_DIR` | `.ai-bot/` | Directory for intermediate artifacts |
| `PR_OUTPUT` | `.ai-bot/pr.md` | Where to write the PR title and body |
| `LINT_COMMAND` | *(auto-detect)* | Lint and format command (e.g., `make fmt && make lint`) |
| `MAX_FIX_ATTEMPTS` | `5` | Max fix → test iterations before escalating |
| `MAX_REVIEW_ROUNDS` | `3` | Max review → fix → test iterations before proceeding |

**Artifact path mapping**: Individual skills reference
`.artifacts/{number}/bugfix/...` paths. Redirect ALL artifact writes to
`ARTIFACT_DIR` instead. Each phase below specifies the exact output
filename to use.

## Ground Rules

- **Do not stop for human input.** Run all phases to completion.
- **Do not create or switch branches.** Stay on the current branch.
- **Do not push code or create PRs.** Write `PR_OUTPUT` and stop.
- **Do not write files outside `ARTIFACT_DIR` and the project source tree.**
  Scratch files, logs, notes, and test scripts go in `ARTIFACT_DIR`.
  Only production source code and test file changes go outside it.
- **Follow `guidelines.md`** for principles, hard limits, and quality
  standards. Where guidelines say "stop and request human guidance,"
  write an escalation report (see Escalation below) and terminate.
- **Read and follow the project's `AGENTS.md`** if one exists. The
  project's conventions take precedence over generic defaults.

## Pipeline

Execute these phases in order. For each phase, read the referenced skill
file and execute its steps — but apply the ground rules and configuration
above, and return here between phases instead of following the controller.

### Phase 1 — Diagnose

Read and execute `diagnose.md`.

**Input**: Bug report at `TASK_FILE`.
**Output**: Root cause analysis at `ARTIFACT_DIR/diagnosis.md`.

**Overrides**:
- If no reproduction report exists, skip the "Review Reproduction" step
  and work directly from the bug report.
- If diagnosis confidence is below 80%, document your caveats and
  proceed. In unattended mode, a best-effort diagnosis is better than
  stopping.

### Phase 2 — Fix

**⚠ Before proceeding, re-read the Overrides below carefully. They contain
mandatory requirements that are easy to overlook after deep diagnosis work.**

Read and execute `fix.md`.

**Input**: Root cause analysis from Phase 1.
**Output**:
- Code changes and test changes in the working tree.
- `ARTIFACT_DIR/implementation-notes.md` — see below.

**Overrides**:
- **Skip Step 2** (Create Feature Branch) — the branch already exists.
- **Unit tests are mandatory.** You MUST modify or create at least one
  test file (e.g., `_test.go`). Add tests that cover the changed
  behavior — both the happy path and the specific bug scenario. The fix
  is not complete until tests exercise the new or changed code paths.
  Do not defer tests to a later step. Phase 3 will verify that test
  files were actually modified; if they weren't, you will be sent back
  here.
- **Write implementation notes** to `ARTIFACT_DIR/implementation-notes.md`.
  A future AI session may need to address PR review comments without
  any memory of this session. Record the context it will need:
  - Files modified and why (with `file:line` references)
  - Design choices made and alternatives considered or rejected
  - Test strategy: what scenarios are covered, what was intentionally
    excluded and why

### Phase 3 — Test

Read and execute `test.md`.

**Input**: Changes from Phase 2.
**Output**: Test verification at `ARTIFACT_DIR/test-verification.md`.

**Gate check**: Before running tests, verify that you actually added or
modified at least one test file (e.g., `_test.go`). If no test files
were modified, **stop and return to Phase 2** — do not proceed.

Run the project's full test suite. If tests fail:

1. Analyze the failure — is it a test issue or a fix issue?
2. Return to **Phase 2** to revise the fix.
3. Re-run **Phase 3**.
4. Track the attempt count. After `MAX_FIX_ATTEMPTS` failures, escalate.

### Phase 4 — Review

Read and execute `review.md`.

**Input**: All changes from Phases 2–3.
**Output**: Review findings at `ARTIFACT_DIR/review.md`.

Self-review the fix and tests with a critical eye. If the verdict is
"Fix is inadequate" or finds CRITICAL or HIGH severity issues:

1. Return to **Phase 2** to address the findings.
2. Re-run **Phase 3** (test) and **Phase 4** (review).
3. Track the round count. After `MAX_REVIEW_ROUNDS`, note the
   unresolved issues in the review report and proceed — the human
   reviewer will catch remaining problems.

### Phase 5 — Lint

Run the project's lint and format checks.

**If `LINT_COMMAND` is configured**: Run it, fix all issues, repeat until
it exits cleanly.

**If `LINT_COMMAND` is not configured**: Check the project's `AGENTS.md`,
`Makefile`, or CI configuration for lint/format commands. Common patterns:

- Go: `make fmt && make lint`, or `gofmt` + `golangci-lint run ./...`
- Python: `ruff check --fix .` or `black . && flake8`
- JS/TS: `npm run lint -- --fix`

Fix all reported issues before proceeding.

### Phase 6 — PR Description

Write the PR title and description to `PR_OUTPUT`.

**Format**:
- **Line 1**: PR title. Write a clear, concise summary of the fix.
- **Line 2**: Blank.
- **Lines 3+**: PR body in markdown containing:
  - **Root Cause** — summary from `ARTIFACT_DIR/diagnosis.md`
  - **Fix** — what was changed and why
  - **Tests Added** — list the specific test functions you wrote or
    modified to verify this fix, with file paths

## Escalation

When a phase fails beyond its retry limit, or when `guidelines.md`
escalation criteria are met, write `ARTIFACT_DIR/escalation.md` with:

- Which phase failed
- What was attempted (include attempt count)
- Why it could not be resolved automatically
- Suggested next steps for a human

Then **stop**. Do not continue past the failed phase.

## Output

When the pipeline completes successfully, the working tree contains:

| Artifact | Description |
|----------|-------------|
| Source code changes | Production fix in the working tree |
| Test changes | New or updated tests in the working tree |
| `ARTIFACT_DIR/diagnosis.md` | Root cause analysis |
| `ARTIFACT_DIR/implementation-notes.md` | Design decisions, alternatives, test rationale |
| `ARTIFACT_DIR/test-verification.md` | Test results summary |
| `ARTIFACT_DIR/review.md` | Self-review findings |
| `PR_OUTPUT` | PR title and description |
