# Triage Workflow

Bulk-triage unresolved Jira bugs through these phases:

- **Run** (`/run`) — Execute all bulk phases end-to-end without pausing

1. **Start** (`/start`) — Validate Jira access, confirm project key
2. **Scan** (`/scan`) — Fetch unresolved bugs and recently resolved bugs; write `issues.json` and `resolved.json`
3. **Analyze** (`/analyze`) — Categorize each bug; read `resolved.json` for regression hints; write `analyzed.json`
4. **Report** (`/report`) — Generate interactive HTML report

**Single-issue triage** (`/assess`) — Not sequential with the bulk pipeline. Read `skills/assess.md`: read-only Jira search, optional read of `issues.json`, full triage in chat (no `analyzed.json` unless the user later runs bulk `/analyze`).

Phase skills are at `skills/{name}.md`. Each skill is self-contained with its own instructions, allowed tools, and on-completion recommendations.
Use `/run` for end-to-end bulk execution, or individual commands for step-by-step control.
Artifacts go in `.artifacts/triage/{project}/`.

## Principles

- Read-only: this workflow never modifies Jira issues — it only reads and reports
- Every recommendation must include a reason — never categorize without explanation
- Present the full picture before recommending action — don't hide inconvenient data
- When uncertain, say so — use confidence levels honestly
- AUTO_FIX and NEEDS_INFO are mutually exclusive — a bug without sufficient detail can never be a candidate for automated fixing
- AUTO_FIX likelihood percentages reflect honest assessment of bot success probability, not optimism

## Hard Limits

- **No Jira writes** — this workflow must not create, update, close, or comment on any Jira issue
- **No fabricated data** — if a field is missing from the Jira response, report it as missing; never invent values
- **No skipping issues** — every unresolved bug in the scan results must appear in the analysis and report
- **Read-only MCP tools only** — each phase declares its allowed tools; never call a tool outside that list. No phase may use write-oriented Jira tools (`jira_create_issue`, `jira_update_issue`, `jira_delete_issue`, `jira_transition_issue`, `jira_add_comment`, `jira_add_worklog`, `jira_create_issue_link`, etc.)

## Allowed Tools Per Phase

| Phase   | Jira MCP tools (read-only)         | Local tools                    |
|---------|-------------------------------------|--------------------------------|
| Run     | Per phase below                     | Per phase below                |
| Start   | `jira_search`                       | `mkdir` (create artifact dir)  |
| Scan    | `jira_search`                       | Write `issues.json` and `resolved.json` |
| Analyze | none                                | Read `issues.json`, read `resolved.json` (if present), write `analyzed.json` |
| Report  | none                                | Read `analyzed.json`, read `templates/report.html`, write `report.html` |
| Assess (`/assess`) | `jira_search`              | Optionally read `issues.json`; no required artifact writes |

Any tool not listed above is **prohibited** in that phase. If a phase needs data not available through its allowed tools, stop and ask the user.

## Safety

- Validate Jira access before scanning — fail fast if authentication is broken
- Handle pagination carefully — verify the total count matches the number of fetched issues
- If the project has more than 500 unresolved bugs, warn the user before proceeding — the batching strategy in `/analyze` will checkpoint progress, but the full run may take significant time

## Quality

- Recommendations must be consistent — similar bugs should receive similar treatment
- Duplicate detection should reference the specific target issue key, not just say "duplicate"
- The HTML report must ship as one file with inline CSS/JS and embedded JSON; optional Google Fonts load when online (system fonts offline)
- Artifact JSON files must be valid, parseable JSON

## Escalation

Stop and request human guidance when:

- Jira access fails or returns unexpected errors
- The scan returns zero **unresolved** bugs (possibly wrong project key or issue type)
- More than 30% of issues lack descriptions (data quality problem, not a triage problem)
- The user asks to modify Jira issues (out of scope for this workflow)
