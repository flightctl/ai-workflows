---
name: triage
description: >-
  Bulk-triage unresolved Jira bugs with AI-driven recommendations and an
  interactive HTML report. Use when triaging a project backlog, prioritizing
  bug fixes, identifying candidates for automated fixing, or reviewing stale
  issues.
  Activated by commands: /run, /start, /scan, /analyze, /report.
---
# Triage Workflow Orchestrator

## Quick Start

1. If the user invoked `/run`, read `skills/run.md` and follow it — this drives all phases end-to-end without pausing
2. If the user invoked a specific phase command (`/start`, `/scan`, `/analyze`, `/report`), read the corresponding skill file from `skills/{phase}.md` and execute it
3. If the user provided a Jira project key but no specific command, start with `skills/scan.md`
4. If no project key was provided, start with `skills/start.md` to gather it

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
4. Write all issues to `.artifacts/triage/EDM/issues.json`

## Example Session

```text
User: "Triage unresolved bugs in EDM"

/start   → validates Jira access for project EDM
/scan    → fetches 87 unresolved bugs via JQL pagination
           → writes .artifacts/triage/EDM/issues.json
/analyze → categorizes each bug: FIX_NOW, AUTO_FIX, BACKLOG, CLOSE, …
           → writes .artifacts/triage/EDM/analyzed.json
/report  → generates interactive HTML dashboard
           → writes .artifacts/triage/EDM/report.html
```

## Phases

- **Run** (`/run`) — Execute all phases below end-to-end without pausing

1. **Start** (`/start`) — Validate Jira access, confirm project key
2. **Scan** (`/scan`) — Fetch all unresolved bugs via JQL with pagination
3. **Analyze** (`/analyze`) — Categorize each bug with a recommendation, reason, confidence, and auto-fix likelihood where applicable
4. **Report** (`/report`) — Generate a self-contained interactive HTML report

## Phase Transitions

Each phase must meet its exit criteria before the next. If a phase fails, stop and report the error.

- `/start` → proceed when Jira access is validated and project key is confirmed. If access fails (auth error, unknown project), stop and report.
- `/scan` → proceed when all unresolved bugs are fetched and saved. Verify: issue count in `issues.json` matches the total from Jira. If scan returns zero results, stop — the project key or issue type may be wrong.
- `/analyze` → proceed when every issue has a recommendation and `analyzed.json` is written. Verify: the number of analyzed issues matches the scanned count. If `issues.json` is missing, run `/scan` first.
- `/report` → done when the HTML report is written. If `analyzed.json` is missing, run `/analyze` first.

## File Layout

Phase skills are at `skills/{name}.md`. Each skill is self-contained with its own instructions, allowed tools, and on-completion recommendations.
The HTML template is at `templates/report.html`.
Artifacts go in `.artifacts/triage/{project}/`.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
