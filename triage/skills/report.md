---
name: report
description: Generate a self-contained interactive HTML report from analyzed triage data.
---

# Generate Report

Generate the single-file HTML dashboard from `analyzed.json`. Python prepares a
compact context and renders the dashboard. AI supplies only the semantic
stakeholder judgment: the executive summary and release-risk assessment.

## Allowed Tools

- **Jira MCP:** none
- **Local:** run `prepare_report.py` and `render_report.py`; read/write phase artifacts
- **Prohibited:** all Jira tools

## Prerequisites

`.artifacts/triage/{PROJECT}/analyzed.json` must exist. If it does not, stop
and ask the user to run `/analyze` first. The scan's
`.artifacts/triage/{PROJECT}/issues.json` must contain a non-empty
`jiraBaseUrl`; never invent one.

## Process

### 1. Prepare compact synthesis context

Resolve `{AI_WORKFLOWS_ROOT}` to the ai-workflows install root (the checkout
root, or the symlink target), then run from the target project's root:

```bash
PROJECT_ROOT="$PWD"
(
  cd "{AI_WORKFLOWS_ROOT}"
  python3 triage/scripts/prepare_report.py \
    --analyzed "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/analyzed.json" \
    --output "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/report-input.json"
)
```

Read only `report-input.json` for the synthesis call. Write the existing
renderer contract to `ai-synthesis.json`:

```json
{
  "executiveSummary": ["..."],
  "releaseRisk": null
}
```

When non-null, `releaseRisk` must be an object with `riskLevel` set to
`High`, `Medium`, or `Low`; a non-empty string `summary`; `factors` as an
array of objects containing non-empty string `signal`, `severity`, and
`detail` fields; and `mitigations` as an array of non-empty strings.

Use the complete compact context to preserve the original report value. Write
3-5 executive-summary bullets covering backlog reduction, severity, quality
signals, regressions, and the most impactful action. Write a release-risk
object with a calibrated High/Medium/Low level, material factors, and 2-5
mitigations; set it to null for fewer than five issues. Do not invent counts,
keys, themes, or risks absent from the input. Return only JSON.

If `report-input.json` has zero issues, skip AI synthesis and run the
deterministic fallback below. If the AI synthesis call fails, returns invalid
JSON, or the renderer rejects its semantic schema, run:

```bash
PROJECT_ROOT="$PWD"
(
  cd "{AI_WORKFLOWS_ROOT}"
  python3 triage/scripts/synthesize_report.py \
    --analyzed "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/analyzed.json" \
    --output "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/ai-synthesis.json"
)
```

Stop if that deterministic fallback also fails.
After a successful fallback, rerun the renderer with the generated
`ai-synthesis.json`.

### 2. Render the report

Run:

```bash
PROJECT_ROOT="$PWD"
(
  cd "{AI_WORKFLOWS_ROOT}"
  python3 triage/scripts/render_report.py \
    --analyzed "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/analyzed.json" \
    --template triage/templates/report.html \
    --issues "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/issues.json" \
    --ai-input "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/ai-synthesis.json" \
    --output "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/report.html"
)
```

The renderer validates JSON inputs, replaces all template placeholders, and
fails if any placeholder remains. Stop and report stderr on a non-zero exit.

### 3. Present completion

Report `.artifacts/triage/{PROJECT}/report.html` and note that it is
self-contained with embedded data. Mention the dashboard's existing filters,
sorting, simulation, clusters, signatures, regressions, and risk sections.
