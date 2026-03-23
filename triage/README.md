# Triage

Bulk-triage unresolved Jira bugs with AI-driven recommendations. Fetches all open bugs and **recently resolved** bugs (for regression matching), analyzes each open bug (including error signatures, duplicate confidence, and possible regressions), and generates a self-contained interactive HTML report. For **one issue** in depth without bulk artifacts, use **`/assess`** (see `skills/assess.md`).

## Prerequisites

- **Jira MCP server** — the `user-mcp-jira` MCP server must be configured and authenticated
- **Jira access** — the authenticated user must have read access to the target project

## Phases

| Phase   | Command    | What it does                                                                 |
|---------|------------|------------------------------------------------------------------------------|
| Run     | `/run`     | Execute all bulk phases end-to-end without pausing                         |
| Start   | `/start`   | Validate Jira access, confirm project key, create artifact workspace         |
| Scan    | `/scan`    | Fetch unresolved bugs + recently resolved bugs (regression context); write `issues.json` and `resolved.json` |
| Analyze | `/analyze` | Categorize each bug; error signature, `duplicateConfidence`, `regressionOf`  |
| Report  | `/report`  | Generate interactive HTML report                                             |
| Assess  | `/assess`  | Full triage of **one** issue in chat — not part of the bulk pipeline         |

Use `/run` for unattended end-to-end execution, or run individual bulk phases for step-by-step control. The typical order is start → scan → analyze → report. **`/assess`** is separate: use it when the user wants deep triage on a single bug without writing bulk artifacts.

## Recommendation Types

| Type       | Description                                                                 |
|------------|-----------------------------------------------------------------------------|
| CLOSE      | Invalid, obsolete, or no activity for 12+ months with vague description     |
| FIX_NOW    | Critical/high priority, blockers, regressions, or quick wins                |
| AUTO_FIX   | Well-described bug suitable for the unattended bugfix bot; includes success likelihood (0-100%) |
| BACKLOG    | Valid but not urgent; keep for future prioritization                         |
| NEEDS_INFO | Missing reproduction steps or unclear description                           |
| DUPLICATE  | Appears to duplicate another issue                                          |
| ESCALATE   | Needs architectural decision or cross-team coordination                     |
| WONT_FIX   | Valid but out of scope or cost-prohibitive                                  |

AUTO_FIX and NEEDS_INFO are mutually exclusive — a bug without sufficient detail cannot be a candidate for automated fixing.

## Usage

### Cursor

```
@triage/commands/run EDM
```

Or step by step:

```
@triage/commands/start EDM
@triage/commands/scan
@triage/commands/analyze
@triage/commands/report
```

Single-issue triage (issue URL or project + text):

```
@triage/commands/assess
```

### Claude Code

> "Triage unresolved bugs in the EDM project"

## HTML Report Features

The generated report is a single HTML file (Material Design styling) with inline CSS/JS and embedded data. **Google Fonts** load when online; offline, the browser falls back to system fonts.

### Overview

- **Total bugs card** — prominent count at the top; switches to "Remaining" in simulation mode
- **Stats dashboard** — color-coded tiles showing count per recommendation
- **Executive summary** — 3–5 bullet-point health assessment for stakeholders (synthesized during `/report` from analyzed data)
- **Release risk assessment** — color-coded risk level (High/Medium/Low) with risk factors, mitigations, and scope disclaimer (synthesized during `/report`)

### Analysis

- **Recommendation legend** — description of each recommendation type and its meaning
- **Key recommendations** — top actionable items for the team
- **Priority breakdown** — including bugs with undefined priority
- **Status distribution** — status vs. priority matrix
- **Assignee load** — bugs per assignee with critical-and-above count
- **Aging analysis** — bug age distribution by update date

### Issue Details

- **Stale bugs table** — bugs not updated for more than 3 months
- **Priority mismatches** — bugs where the assigned priority doesn't match the severity implied by the description
- **Possible regressions** — table when analysis sets `regressionOf` (resolved-bug relationship)
- **Duplicate & related clusters** — grouped bugs ranked by urgency score (computed from member-issue priorities), with suggested Jira link types and next steps
- **All Issues table** — **Signature** (error signature / excerpt), **Duplicate of**, **Duplication %** (`duplicateConfidence` when DUPLICATE), **Regression** (`regressionOf`), plus existing columns

### Interactivity

- **Filters** — dropdown filters for recommendation, priority (including **Unassigned** when Jira has no priority), component, **assignee** (including **Unassigned** for no assignee); free-text search also matches duplicate/regression keys
- **Live counter** — shows filtered/total count, updates as filters change
- **Sortable table** — click any column header to sort
- **Simulation mode** — toggle to strike through CLOSE/WONT_FIX/DUPLICATE issues and recalculate stats
- **Auto-fix likelihood** — percentage shown inside the Auto Fix badge

## Artifacts

All outputs are saved for auditability:

```
.artifacts/triage/{project}/
  issues.json        — raw scanned unresolved bugs from Jira
  resolved.json      — recently resolved bugs (default 90d) for regression matching in analyze
  analyzed.json      — issues with recommendations, signatures, duplicate/regression fields
  report.html        — interactive HTML dashboard
```

## Read-Only Workflow

This workflow never modifies Jira issues. It only reads data and generates reports. Users act on the recommendations manually in Jira.
