---
name: bugfix
description: Diagnostic and repair workflow that analyzes error logs, traces root causes, implements fixes, and verifies with regression tests. Use when fixing bugs, debugging runtime errors or exceptions, investigating test failures or crashes, or submitting bug-fix pull requests.
---
# Bugfix Workflow Orchestrator

## Quick Start

1. If the user invoked a specific command (e.g. `/unattended`, `/diagnose`, `/fix`), read the matching file in `commands/{command}.md` and follow it.
2. Otherwise, read `skills/controller.md` to load the workflow controller:
   - If the user provided a bug report or issue URL, execute the `/assess` phase
   - Otherwise, execute `/start` to present available phases

Each phase skill (e.g. `skills/diagnose.md`) follows this pattern:

1. Announce the phase: *"Starting /diagnose."*
2. Execute the skill's steps — search code, run commands, collect evidence
3. Write findings to the artifact directory and return to the controller

```bash
# Artifact directory setup and example commands during investigation
mkdir -p .artifacts/bugfix/421
rg "NullPointerException" --type java -l
git log --oneline -10 -- src/auth/AuthService.java
git blame src/auth/AuthService.java | head -100
```

## Example: Running /diagnose

To execute the diagnose phase:

1. Create the artifact dir: `mkdir -p .artifacts/bugfix/421`
2. Find the failure location: `rg "NullPointerException" --type java -l`
3. Trace when it was introduced: `git blame <file>` and `git log --oneline -10 -- <file>`
4. Write `.artifacts/bugfix/421/root-cause.md` using this structure:

```markdown
# Root Cause — Issue #421

## Root Cause Summary
`AuthService.java:87` calls `session.getUserId()` before null-check.

## Evidence
- Stack trace: `AuthService.authenticate():87`
- `git blame` shows null-check removed in commit `a1b2c3d`

## Affected Components
- `AuthService.java:87` — missing null guard

## Impact Assessment
- Severity: High
- Blast radius: All unauthenticated login attempts

## Recommended Fix
Add null-check before `getUserId()` call.

## Confidence: High (95%)
```

See `skills/diagnose.md` for the full process and additional fields.

## Example Session

```text
User: "Fix issue #421 — NullPointerException on login"

/assess    → reads bug report, proposes plan (inline; no artifact)
/reproduce → confirms the failure with a test
             → writes .artifacts/bugfix/421/reproduction.md
/diagnose  → traces root cause to AuthService.java:87
             → writes .artifacts/bugfix/421/root-cause.md
/fix       → adds null-check, minimal diff
/test      → regression test passes ✓
             → if tests fail → return to /fix
/pr        → pushes branch, creates draft PR
```

## Phases

Systematic bug resolution through these phases:

0. **Start** (`/start`) — Present available phases and help choose where to begin
1. **Assess** (`/assess`) — Read the bug report, explain understanding, propose a plan
2. **Reproduce** (`/reproduce`) — Confirm and document the bug
3. **Diagnose** (`/diagnose`) — Identify root cause and impact
4. **Fix** (`/fix`) — Implement the solution
5. **Test** (`/test`) — Verify the fix, create regression tests
6. **Review** (`/review`) — *(Optional)* Critically evaluate fix and tests
7. **Document** (`/document`) — Release notes and documentation
8. **PR** (`/pr`) — Submit a pull request

## Phase Transitions

Each phase must meet its exit criteria before the next phase begins. If a later phase reveals problems, loop back:

- `/assess` → proceed when the bug report is understood and a plan is proposed
- `/reproduce` → proceed when the bug is reliably triggered with documented steps
- `/diagnose` → proceed when a root cause is confirmed with supporting evidence (stack trace, git blame, code path)
- `/fix` → proceed when the implementation addresses the confirmed root cause
- `/test` → proceed when all new and existing tests pass; if tests fail, return to `/fix`
- `/review` → if the fix is inadequate or edge cases are missed, return to `/diagnose` or `/fix`

## File Layout

The workflow controller lives at `skills/controller.md`.
It defines how to execute phases, recommend next steps, and handle transitions.
Phase skills are at `skills/{name}.md`.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
