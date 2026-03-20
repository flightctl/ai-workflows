# Triage

Bulk-triage unresolved Jira bugs with AI-driven recommendations. Fetches all open bugs from a Jira project, analyzes each one, and generates a self-contained interactive HTML report.

## Prerequisites

- **Jira MCP server** — the `user-mcp-jira` MCP server must be configured and authenticated
- **Jira access** — the authenticated user must have read access to the target project

## Phases

| Phase   | Command    | What it does                                                                 |
|---------|------------|------------------------------------------------------------------------------|
| Run     | `/run`     | Execute all phases end-to-end without pausing                                |
| Start   | `/start`   | Validate Jira access, confirm project key, create artifact workspace         |
| Scan    | `/scan`    | Fetch all unresolved bugs via JQL with pagination                            |
| Analyze | `/analyze` | Categorize each bug with recommendation, reason, confidence                  |
| Report  | `/report`  | Generate interactive HTML report                                             |

Use `/run` for unattended end-to-end execution, or run individual phases for step-by-step control. The typical order is start → scan → analyze → report.

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

### Claude Code

> "Triage unresolved bugs in the EDM project"

## HTML Report Features

The generated report is a single self-contained HTML file (Material Design styling) with no external dependencies:

- **Total bugs card** — prominent count at the top; switches to "Remaining" in simulation mode
- **Stats dashboard** — color-coded tiles showing count per recommendation
- **Recommendation legend** — description of each recommendation type and its meaning
- **Key recommendations** — executive summary of top actions to take
- **Priority breakdown** — including bugs with undefined priority
- **Status distribution** — status vs. priority matrix
- **Assignee load** — bugs per assignee with critical-and-above count
- **Aging analysis** — bug age distribution by update date
- **Stale bugs table** — bugs not updated for more than 3 months
- **Priority mismatches** — bugs where the assigned priority doesn't match the severity implied by the description
- **Duplicate & related clusters** — grouped bugs with suggested Jira link types and next steps
- **Filters** — dropdown filters for recommendation, priority, and component; free-text search
- **Live counter** — shows filtered/total count, updates as filters change
- **Sortable table** — click any column header to sort
- **Simulation mode** — toggle to strike through CLOSE/WONT_FIX/DUPLICATE issues and recalculate stats
- **Auto-fix likelihood** — percentage shown inside the Auto Fix badge

## Artifacts

All outputs are saved for auditability:

```
.artifacts/triage/{project}/
  issues.json        — raw scanned data from Jira
  analyzed.json      — issues with recommendations, reasons, and confidence
  report.html        — interactive HTML dashboard
```

## Read-Only Workflow

This workflow never modifies Jira issues. It only reads data and generates reports. Users act on the recommendations manually in Jira.
