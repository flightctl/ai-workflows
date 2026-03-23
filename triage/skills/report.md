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

### Step 4: Synthesize Executive Summary & Release Risk Assessment

Using the complete `analyzed.json` data (issues, clusters, key recommendations, summary counts), generate two synthesis artifacts. These are produced here — during report generation — rather than during `/analyze`, because `/report` has the finalized dataset without context-window pressure.

#### 4a. Executive Summary

Produce an `executiveSummary` array — 3–5 bullet-point strings giving stakeholders a 30-second health assessment.

Focus on:

- **Backlog size & actionable reduction** — total bugs, percentage closeable (CLOSE + WONT_FIX + DUPLICATE), effective backlog after cleanup
- **Severity snapshot** — how many critical/high-priority clusters or issues need immediate attention
- **Quality signal** — duplicate density, bugs lacking priority or info, aging trends
- **Regression risk** — whether resolved bugs are reappearing
- **Key takeaway** — one sentence on the single most impactful action

Write in plain language suitable for a delivery manager or engineering lead. Avoid Jira keys; use counts and themes.

Example:

```json
[
  "The EDM backlog contains 145 open bugs, but 34 (23%) are duplicates or candidates for closure — cleaning them would reduce the active backlog to ~111.",
  "Three high-urgency clusters (auth timeouts, file upload failures, checkout NPEs) account for 28 bugs and share overlapping root causes.",
  "31 bugs have not been updated in over 3 months; 12 of those have no assigned priority, making them invisible to sprint planning.",
  "3 bugs appear to regress recently resolved fixes from the 3.2 release — verify before the next deployment.",
  "Submitting 12 AUTO_FIX candidates (avg 72% likelihood) to the bugfix bot would address the most clearly scoped issues without manual effort."
]
```

#### 4b. Release Risk Assessment

Produce a `releaseRiskAssessment` object that answers: "Based on the bug backlog alone, what is the risk of shipping now?"

**Important:** This covers **bug-backlog risk only** — not test coverage, feature completeness, or deployment readiness.

Schema:

```json
{
  "riskLevel": "High",
  "summary": "One sentence overall assessment.",
  "factors": [
    {
      "signal": "Open regressions",
      "severity": "High",
      "detail": "30 bugs appear to regress recently resolved fixes — shipping may re-introduce known issues."
    }
  ],
  "mitigations": [
    "Verify and resolve the 30 regression candidates before deployment.",
    "Assign the 2 unresolved Blocker/Critical bugs to the current sprint."
  ]
}
```

Fields:

- `riskLevel` — **High**, **Medium**, or **Low**
- `summary` — one sentence overall risk statement
- `factors` — array of risk signals (`signal`, `severity`, `detail`)
- `mitigations` — 2–5 actionable strings to reduce the risk level

Risk level criteria:

| Level | When to assign |
|-------|---------------|
| **High** | Open regressions ≥ 5, unresolved Blocker/Critical ≥ 3, high-urgency clusters with no owner, or > 40% of bugs lack priority |
| **Medium** | Moderate regression count (1–4), a few high-priority bugs remain, some stale critical-path bugs, or significant NEEDS_INFO backlog |
| **Low** | No open regressions, few high-priority bugs, clusters manageable, backlog well-triaged |

Risk factor signals to evaluate (include only those present and material):

- **Open regressions** — bugs with `regressionOf` set
- **Unresolved Blocker/Critical bugs** — FIX_NOW at the top of severity
- **Unowned high-urgency clusters** — clusters with no assignees on member issues
- **Priority blind spots** — large percentage without assigned priority
- **Stale critical-path bugs** — old bugs in critical components
- **NEEDS_INFO blockers** — bugs blocking triage decisions
- **Duplicate noise** — high duplicate density

Set to **null** when there is insufficient data (e.g. < 5 issues).

### Step 5: Populate the Template

Replace the following placeholders in the template (the executive summary and release risk come from Step 4; all other data from `analyzed.json`):

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

The `{ISSUES_JSON}` placeholder is replaced with the literal JSON array from `analyzed.json` (the `issues` field). The `{CLUSTERS_JSON}` placeholder is replaced with the `clusters` array. The `{EXECUTIVE_SUMMARY_JSON}` and `{RELEASE_RISK_JSON}` placeholders are replaced with the data generated in Step 4. This embeds all data directly in the HTML so the file is a single shareable artifact (no separate JSON files needed).

Each issue object in the `issues` array must conform to the per-issue output schema defined in `analyze.md` (Per-Issue Output Schema section).

Each cluster object should include: `id`, `theme`, `issues` (array of keys), `suggestedLinkType`, `nextSteps` (array of strings). The report computes an **urgency score** per cluster at render time (sum of priority weights across member issues, using the best of Jira priority / `suggestedPriority` / `priorityMismatch.suggested`). Clusters are sorted from highest to lowest urgency score and the score is displayed on each card.

The key recommendations array is a list of strings — actionable items for the team.

The executive summary and release risk assessment are generated in Step 4 during report generation — not stored in `analyzed.json`. If either is empty or null, the corresponding report section hides automatically.

### Step 6: Write the Report

Write the populated HTML to:

```
.artifacts/triage/{PROJECT}/report.html
```

Verify the output file is valid HTML by checking that:

- The `{ISSUES_JSON}` placeholder was replaced with actual JSON (not the literal string)
- The `{JIRA_BASE_URL}` placeholder was replaced with a real URL
- No other `{...}` placeholders remain in the output

### Step 7: Present Result

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
- Key Recommendations — top actionable items for the team
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
