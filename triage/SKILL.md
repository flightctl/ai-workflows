---
name: triage
description: >-
  Bulk-triage unresolved Jira bugs with AI-driven recommendations and an
  interactive HTML report. Scan also loads recently resolved bugs for regression
  matching in analyze. Use when triaging a project backlog, prioritizing bug
  fixes, identifying candidates for automated fixing, or reviewing stale issues.
  For one bug in depth (no artifacts), use /assess. Activated by commands:
  /run, /start, /scan, /analyze, /report, and /assess.
---
# Triage Workflow Orchestrator

## Quick Start

1. If the user invoked `/run`, read `skills/run.md` and follow it — this drives all phases end-to-end without pausing
2. If the user invoked `/assess`, read `skills/assess.md` and follow it — full single-issue triage in chat (does not write `analyzed.json` / `report.html`)
3. If the user invoked a specific bulk phase command (`/start`, `/scan`, `/analyze`, `/report`), read the corresponding skill file from `skills/{phase}.md` and execute it
4. If the user provided a Jira project key but no specific command, start with `skills/scan.md`
5. If no project key was provided, start with `skills/start.md` to gather it

Each phase skill (e.g. `skills/scan.md`) follows this pattern:

1. Announce the phase: *"Starting /scan."*
2. Execute the skill's steps — query Jira, analyze issues, write artifacts
3. Write output to the artifact directory and present on-completion recommendations

## Example: Running /scan

To execute the scan phase without opening external files:

1. `mkdir -p .artifacts/triage/EDM`
2. Call the MCP tool `jira_search` (server: `user-mcp-jira`) with JSON arguments:
   ```json
   {"jql": "project = EDM AND issuetype = Bug AND resolution = Unresolved ORDER BY key ASC", "fields": "summary,status,priority,assignee,reporter,created,updated,labels,components,description", "limit": 50}
   ```
3. Paginate with JQL cursor: add `AND key > '{last_key}'` to the JQL using the last issue key from the previous page. Stop when a page returns fewer than 50 issues.
4. Write unresolved issues to `.artifacts/triage/EDM/issues.json`
5. Run the resolved-bug JQL from `skills/scan.md` (Fetch Recently Resolved Bugs step) and write `.artifacts/triage/EDM/resolved.json`

## Example Session

```text
User: "Triage unresolved bugs in EDM"

/start   → validates Jira access for project EDM
/scan    → fetches unresolved bugs + recently resolved bugs (90d window)
           → writes .artifacts/triage/EDM/issues.json and resolved.json
/analyze → categorizes each bug; error signatures, duplicate confidence, regressionOf
           → reads resolved.json for regression hints; writes analyzed.json
/report  → generates interactive HTML dashboard
           → writes .artifacts/triage/EDM/report.html

/assess  → (separate) full triage of one issue in chat — read skills/assess.md
```

## Phases

- **Run** (`/run`) — Execute all bulk phases below end-to-end without pausing

1. **Start** (`/start`) — Validate Jira access, confirm project key
2. **Scan** (`/scan`) — Fetch all unresolved bugs and recently resolved bugs via JQL with pagination; write `issues.json` and `resolved.json`
3. **Analyze** (`/analyze`) — Categorize each bug with recommendation, error signature, `duplicateConfidence`, `regressionOf` (using `resolved.json`), reason, confidence, and auto-fix likelihood where applicable
4. **Report** (`/report`) — Generate a self-contained interactive HTML report

- **Assess** (`/assess`) — Not part of the bulk sequence. Deep triage for **one** issue (see `skills/assess.md`); no `analyzed.json` / `report.html` unless the user runs bulk `/analyze` / `/report` afterward.

## Phase Transitions

Each phase must meet its exit criteria before the next. If a phase fails, stop and report the error.

- `/start` → proceed when Jira access is validated and project key is confirmed. If access fails (auth error, unknown project), stop and report.
- `/scan` → proceed when all unresolved bugs are fetched and `issues.json` is saved, and `resolved.json` is written (may be empty). Verify: unresolved count in `issues.json` matches Jira. If **zero unresolved** issues, stop — the project key or issue type may be wrong.
- `/analyze` → proceed when every issue has a recommendation and `analyzed.json` is written. Verify: the number of analyzed issues matches the scanned unresolved count. If `issues.json` is missing, run `/scan` first. If `resolved.json` is missing, analyze may still run (regression matching uses an empty resolved list).
- `/report` → done when the HTML report is written. If `analyzed.json` is missing, run `/analyze` first.

## File Layout

Phase skills are at `skills/{name}.md`. Each skill is self-contained with its own instructions, allowed tools, and on-completion recommendations.
The HTML template is at `templates/report.html`.
Artifacts go in `.artifacts/triage/{project}/`.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
