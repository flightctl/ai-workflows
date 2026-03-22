---
name: report
description: Generate a self-contained interactive HTML report from analyzed triage data.
---

# Generate Report Skill

You are generating an interactive HTML report from the analyzed triage data. Your goal is to produce a **single HTML file** that can be opened in any browser — emailed or shared as-is with no additional data files. The template uses optional **Google Fonts** when online; offline, browsers fall back to system fonts. All CSS, JS, and issue data are inline or embedded.

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

Read the template from `templates/report.html` (relative to the triage workflow root directory). CSS and JavaScript are inline; **Roboto** fonts may load from Google Fonts (optional). The data is embedded directly into the HTML as a JSON literal.

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
| `{EXECUTIVE_SUMMARY_JSON}` | The executive summary bullets array serialized as JSON |
| `{RELEASE_RISK_JSON}` | The release risk assessment object serialized as JSON (or literal `null`) |

The `{ISSUES_JSON}` placeholder is replaced with the literal JSON array from `analyzed.json` (the `issues` field). The `{CLUSTERS_JSON}` placeholder is replaced with the `clusters` array. The `{EXECUTIVE_SUMMARY_JSON}` placeholder is replaced with the `executiveSummary` array (empty array if absent — the section hides itself). This embeds all data directly in the HTML so the file is a single shareable artifact (no separate JSON files needed).

Each issue object in the JSON should include these fields:

- `key`, `summary`, `status`, `priority`, `suggestedPriority`, `assignee`, `reporter`
- `created`, `updated` (ISO 8601 dates)
- `labels`, `components` (arrays)
- `recommendation`, `reason`, `confidence`
- `autoFixLikelihood` (integer 0-100, only for AUTO_FIX issues)
- `duplicateOf` (Jira key or null)
- `duplicateConfidence` (integer 0–100 when a duplicate candidate is scored; else null)
- `regressionOf` (object with `key`, `summary`, optional `resolved`, `reason` — or null; possible regression of a resolved bug)
- Optional **error signature** fields for display and clustering: `errorType`, `errorCode`, `errorMessageExcerpt`, `affectedComponent`, `symptoms`, `environmentHint` (nullable strings)
- `clusterId` (cluster identifier or null)
- `priorityMismatch` (object with `assigned`, `suggested`, `reason` — or null)

Each cluster object should include: `id`, `theme`, `issues` (array of keys), `suggestedLinkType`, `nextSteps` (array of strings). The report computes an **urgency score** per cluster at render time (sum of priority weights across member issues, using the best of Jira priority / `suggestedPriority` / `priorityMismatch.suggested`). Clusters are sorted from highest to lowest urgency score and the score is displayed on each card.

The key recommendations array is a list of strings — actionable items for the team.

The executive summary array is a list of 3–5 bullet-point strings — a high-level health assessment of the backlog synthesized from all analysis sections (counts, aging, duplicates, regressions, clusters). It appears at the top of the report right after the stats tiles. If `executiveSummary` is missing or empty in `analyzed.json`, the section is hidden automatically.

The release risk assessment is an object with `riskLevel` (High/Medium/Low), `summary`, `factors` (array of `{signal, severity, detail}`), and `mitigations` (array of strings). It appears after the executive summary with a color-coded risk badge. If `releaseRiskAssessment` is missing or null, the section is hidden automatically. A scope disclaimer ("bug backlog only") is rendered at the bottom of the card.

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

Open the file in any browser. Data is embedded; fonts may require network once unless cached.

Features:
- Executive Summary — high-level backlog health assessment (when present in analyzed data)
- Release Risk Assessment — color-coded risk level with factors and mitigations (when present)
- Stats dashboard with counts per recommendation type
- Filters by recommendation, priority (including Unassigned for no Jira priority), component, and assignee (including Unassigned); free-text search (also matches duplicate/regression keys)
- Sortable table (click column headers) including Signature, Duplicate of, Duplication %, Regression
- Possible Regressions section when `regressionOf` is set
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

- `.artifacts/triage/{PROJECT}/report.html` — single file with all data embedded (optional Google Fonts)
- File path presented to the user

## On Completion

Present the report path and remind the user it's one file (embedded data) and can be shared as-is. Note key features: stats, filters, sorting, simulation, suggested priorities, auto-fix likelihood. Mention optional fonts if offline styling looks different.

The triage workflow is complete. Suggest:

- Open the report in a browser to review
- Share the HTML file with stakeholders — no additional files needed
- `/report` — regenerate if the template or data has changed
- `/analyze` — re-analyze with different criteria if the recommendations need adjustment
- `/scan` — re-scan if Jira data has changed and a fresh triage is needed
