---
name: run
description: Orchestrate the full triage workflow from start to report without pausing between phases.
---

# Run — Full Workflow Orchestration

You are the end-to-end orchestrator. Your job is to drive the complete triage workflow through all four phases in a single session, without waiting for user input between phases.

## Allowed Tools

Same as the individual phase skills — each phase inherits its own tool permissions. See `../guidelines.md` for the full allowed-tools-per-phase table.

## Inputs

The user must provide a **Jira project key** (e.g., `EDM`). If not provided, ask for it before proceeding.

## Orchestration Flow

Execute the phases sequentially. After each phase, verify its exit criteria before moving to the next. If any phase fails, stop immediately and report the error — do not continue to subsequent phases.

### Phase 1 — Start

1. Read `start.md` and execute it with the provided project key
2. **Exit criteria:** Jira access validated, project confirmed, artifact directory created
3. On success → proceed to Phase 2

### Phase 2 — Scan

1. Read `scan.md` and execute it
2. **Exit criteria:** `issues.json` written with all unresolved bugs; `resolved.json` written (may be empty `issues` array); unresolved issue count > 0
3. On success → announce the counts and proceed to Phase 3
4. If zero **unresolved** issues found → stop and report (nothing to triage)

### Phase 3 — Analyze

1. Read `analyze.md` and execute it
2. **Exit criteria:** `analyzed.json` written, analyzed count matches scanned count
3. On success → announce the recommendation breakdown and proceed to Phase 4

### Phase 4 — Report

1. Read `report.md` and execute it
2. **Exit criteria:** `report.html` written, all placeholders replaced
3. On success → announce the report location and present a summary

## Progress Reporting

Between each phase transition, announce what just completed and what comes next. Keep it brief:

```text
Phase 1 complete — Jira access validated for project EDM.
Starting Phase 2: Scan...
```

## On Completion

After all four phases finish successfully, present a final summary:

- Total issues scanned
- Recommendation breakdown (count per category)
- Number of clusters identified
- Report file location
- Remind the user the report is self-contained and can be shared as-is

## Error Handling

- **Jira access failure (Phase 1):** Stop. Report the error and suggest checking credentials or project key.
- **Zero issues (Phase 2):** Stop. The project has no unresolved bugs — nothing to triage.
- **Analysis mismatch (Phase 3):** If the analyzed count doesn't match the scanned count, report which issues were missed and whether it's safe to continue.
- **Template or placeholder error (Phase 4):** Stop. Report which placeholders were not replaced.

## Rules

- **No pausing between phases.** `/run` drives through all phases automatically without waiting for user input.
- **Reuse existing skills.** Do not duplicate logic — read and execute each phase skill file directly.
- **Announce every transition.** The user should see clear progress markers.
- **All phases are read-only.** No Jira writes at any point (enforced by individual phase skills).
