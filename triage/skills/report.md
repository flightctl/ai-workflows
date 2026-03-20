---
name: report
description: Generate a self-contained interactive HTML report from analyzed triage data.
---

# Generate Report Skill

You are generating an interactive HTML report from the analyzed triage data. Your goal is to produce a single, self-contained HTML file that can be opened in any browser — offline, emailed, or shared as-is with no additional files required.

## Allowed Tools

- **Jira MCP:** none — this phase works entirely from local artifact data
- **Local:** read `analyzed.json`, read `templates/report.html`, write `report.html`
- **Prohibited:** all Jira tools (no MCP calls in this phase)

## Prerequisites

Before generating, ensure:

- `.artifacts/triage/{PROJECT}/analyzed.json` exists (from `/analyze`)

If the file is missing, tell the user to run `/analyze` first.

## Process

### Step 1: Load Analyzed Data

Read the analyzed issues from `.artifacts/triage/{PROJECT}/analyzed.json`.

### Step 2: Read the HTML Template

Read the template from `templates/report.html` (relative to the triage workflow root directory). This template is self-contained: all CSS, JavaScript, and visual assets are inline — no external stylesheets, scripts, fonts, or images. The data is embedded directly into the HTML as a JSON literal.

### Step 3: Determine the Jira Base URL

The report links each issue key to its Jira page. To build these links, you need the Jira instance base URL (e.g. `https://mycompany.atlassian.net`).

The base URL should already be known from the `/scan` phase (extracted from `self` links in the `jira_search` response). Check if it was saved in `issues.json`. If not available, ask the user for their Jira instance URL. Do **not** call any Jira MCP tools in this phase.

### Step 4: Populate the Template

Replace the following placeholders in the template:

| Placeholder | Value |
|---|---|
| `{PROJECT_KEY}` | The Jira project key (e.g. `EDM`) |
| `{REPORT_DATE}` | Current date/time in ISO 8601 format |
| `{TOTAL_ISSUES}` | Total number of analyzed issues |
| `{JIRA_BASE_URL}` | The Jira instance base URL, without trailing slash |
| `{ISSUES_JSON}` | The full analyzed issues array serialized as JSON |
| `{CLUSTERS_JSON}` | The clusters array serialized as JSON |
| `{KEY_RECOMMENDATIONS_JSON}` | The key recommendations array serialized as JSON |

The `{ISSUES_JSON}` placeholder is replaced with the literal JSON array from `analyzed.json` (the `issues` field). The `{CLUSTERS_JSON}` placeholder is replaced with the `clusters` array. This embeds all data directly in the HTML so the file is completely self-contained.

Each issue object in the JSON should include these fields:

- `key`, `summary`, `status`, `priority`, `suggestedPriority`, `assignee`, `reporter`
- `created`, `updated` (ISO 8601 dates)
- `labels`, `components` (arrays)
- `recommendation`, `reason`, `confidence`
- `autoFixLikelihood` (integer 0-100, only for AUTO_FIX issues)
- `duplicateOf` (Jira key or null)
- `clusterId` (cluster identifier or null)
- `priorityMismatch` (object with `assigned`, `suggested`, `reason` — or null)

Each cluster object should include: `id`, `theme`, `issues` (array of keys), `suggestedLinkType`, `nextSteps` (array of strings).

The key recommendations array is a list of strings — actionable executive summary items.

### Step 5: Write the Report

Write the populated HTML to:

```
.artifacts/triage/{PROJECT}/report.html
```

Verify the output file is valid HTML by checking that:

- The `{ISSUES_JSON}` placeholder was replaced with actual JSON (not the literal string)
- The `{JIRA_BASE_URL}` placeholder was replaced with a real URL
- No other `{...}` placeholders remain in the output

### Step 6: Present Result

Tell the user where to find the report and what it contains:

```text
Report generated: .artifacts/triage/EDM/report.html

The file is fully self-contained — open it in any browser, no internet needed.

Features:
- Stats dashboard with counts per recommendation type
- Filters by recommendation, priority, and component; free-text search
- Sortable table (click column headers)
- Suggested priorities shown in italic purple for bugs missing a Jira priority
- Auto-fix likelihood bar for AUTO_FIX candidates
- Key Recommendations — executive summary of top actions
- Priority Breakdown including undefined-priority bugs
- Status Distribution — status vs priority cross-tabulation
- Assignee Load — bug count per assignee by priority
- Aging Analysis — bug age distribution with 6-month cutoff
- Priority Mismatches — bugs where assigned priority doesn't match description severity
- Bug Clusters with suggested Jira link types and next-step recommendations
- Simulation mode: toggle "Simulate cleanup" to preview the backlog
  after removing CLOSE/WONT_FIX/DUPLICATE issues
```

## Output

- `.artifacts/triage/{PROJECT}/report.html` — single self-contained file with all data embedded
- File path presented to the user

## On Completion

Present the report path and remind the user it's self-contained and can be shared as a single file. Note key features: stats, filters, sorting, simulation, suggested priorities, auto-fix likelihood.

The triage workflow is complete. Suggest:

- Open the report in a browser to review
- Share the HTML file with stakeholders — no additional files needed
- `/report` — regenerate if the template or data has changed
- `/analyze` — re-analyze with different criteria if the recommendations need adjustment
- `/scan` — re-scan if Jira data has changed and a fresh triage is needed
