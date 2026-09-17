---
name: analyze
description: Categorize scanned bugs with compact AI decisions and deterministic Python post-processing.
---

# Analyze Bugs

Analyze every unresolved bug from the scan and produce `analyzed.json` for the
HTML report. Python owns normalization, signal extraction, candidate matching,
validation, merging, and aggregation. AI owns semantic judgments: issue
recommendations, reasons, duplicate/regression decisions, topics, cluster
meaning and actions, and prioritized recommendations.

## Allowed Tools

- **Jira MCP:** none
- **Local:** run the triage Python scripts; read/write phase artifacts
- **Prohibited:** all Jira tools

## Prerequisites

`.artifacts/triage/{PROJECT}/issues.json` must exist. If it does not, stop and
ask the user to run `/scan` first. `resolved.json` is optional.

## Process

### 1. Prepare compact input

Resolve `{AI_WORKFLOWS_ROOT}` to the ai-workflows install root (the checkout
root, or the symlink target), then run from the target project's root:

```bash
PROJECT_ROOT="$PWD"
(
  cd "{AI_WORKFLOWS_ROOT}"
  python3 triage/scripts/prepare_analysis.py \
    --issues "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/issues.json" \
    --resolved "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/resolved.json" \
    --output "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/analysis-input.json"
)
```

If `resolved.json` is absent, omit `--resolved`; the script uses an empty
resolved set. Read only `analysis-input.json` for AI analysis. It contains
compact issue text, deterministic signatures and age/activity signals, stale
`CLOSE` candidates, and at most three bounded match candidates per issue.

If preparation exits non-zero, stop and report stderr. Do not read or reuse an
existing `analysis-input.json`. If `sourceCount` is zero, write
`{"decisions": []}`, omit clusters and recommendations, run the finalizer,
and report an empty result without inventing AI judgments.

### 2. Produce compact AI decisions

Process issues in batches of 25–30. After each batch, merge its decisions into
the existing `ai-decisions.json`; never replace decisions from earlier batches.
After all per-issue batches are complete, read the existing
`ai-decisions.json` and make a separate fresh synthesis call. Pass only its
compact `decisions` array (keys, topics, recommendations, reasons, confidence,
and relationship judgments) to that call. The fresh call returns only:

```json
{
  "clusters": [],
  "keyRecommendations": []
}
```

Merge those aggregate fields into the existing `ai-decisions.json`; preserve
the complete `decisions` array. Return only this final artifact shape, with one
decision for every issue:

```json
{
  "decisions": [
    {
      "key": "EDM-1234",
      "topic": "authentication timeout",
      "recommendation": "AUTO_FIX",
      "reason": "Clear reproduction and bounded component scope.",
      "confidence": "High",
      "suggestedPriority": null,
      "priorityMismatch": null,
      "autoFixLikelihood": 80,
      "duplicateOf": null,
      "duplicateConfidence": null,
      "regressionOf": null
    }
  ],
  "clusters": [
    {
      "id": "cluster-1",
      "theme": "Authentication timeout errors in login flow",
      "issues": ["EDM-101", "EDM-234"],
      "suggestedLinkType": "relates to",
      "nextSteps": ["Link the issues", "Investigate the shared root cause"]
    }
  ],
  "keyRecommendations": ["...", "...", "...", "...", "..."]
}
```

`topic` must be a short common-topic label of no more than six words. Use the
same label for issues sharing a user-facing feature, failure mode, or likely
root-cause area, even when their Jira components differ. Use null when no
meaningful relationship exists. The top-level clusters and recommendations are
semantic judgments, not Python templates: provide 2-4 concrete next steps per
cluster and 5-10 actionable recommendations.

Write or update `.artifacts/triage/{PROJECT}/ai-decisions.json` after each
batch. Do not repeat metadata, descriptions, signatures, or match candidates.
Return no prose outside JSON.

Allowed recommendations are `CLOSE`, `FIX_NOW`, `AUTO_FIX`, `BACKLOG`,
`NEEDS_INFO`, `DUPLICATE`, `ESCALATE`, and `WONT_FIX`. Use `NEEDS_INFO` when
reproduction, impact, or error detail is insufficient; it is mutually
exclusive with `AUTO_FIX`. Use `AUTO_FIX` only for a bounded, testable fix.
Use `FIX_NOW` for critical/high-impact issues, `ESCALATE` for architectural,
cross-team, or security decisions, and `BACKLOG` for valid non-urgent bugs.
Use `CLOSE` for invalid/obsolete bugs or stale vague bugs, `DUPLICATE` only
with a convincing supplied candidate, and `WONT_FIX` for valid out-of-scope
or deprecated functionality.

For missing Jira priority, set `suggestedPriority`; otherwise set it to null.
For every issue with an assigned Jira priority, compare the description's
severity and impact against that priority. When there is a significant gap,
populate `priorityMismatch` with exactly
`{"assigned":"...","suggested":"...","reason":"..."}`; otherwise use
null. Never put an `Undefined` or missing priority in `priorityMismatch`.
Set `autoFixLikelihood` only for `AUTO_FIX`. Select `duplicateOf` only
from that issue's `matchCandidates`. Select `regressionOf` only from a
resolved candidate whose resolution predates the open issue's creation.

An issue with `deterministicRecommendation: CLOSE` may omit `recommendation`
and `reason`; the finalizer supplies both deterministic values. Every decision
must still include `confidence` as `High`, `Medium`, or `Low`. All other
decisions require a recommendation and a short reason.

### 3. Finalize deterministically

Run from the target project's root, using the package-root subshell:

```bash
PROJECT_ROOT="$PWD"
(
  cd "{AI_WORKFLOWS_ROOT}"
  python3 triage/scripts/finalize_analysis.py \
    --issues "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/issues.json" \
    --prepared "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/analysis-input.json" \
    --decisions "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/ai-decisions.json" \
    --output "$PROJECT_ROOT/.artifacts/triage/{PROJECT}/analyzed.json"
)
```

The finalizer fails if the decision set does not exactly match the scan or
contains invalid targets. It merges original issue metadata with Python
signals, validates AI cluster/recommendation/priority-mismatch structure, and
computes only mechanical fields such as counts and membership. If semantic
aggregate fields are absent, it uses a deterministic fallback.

If the finalizer exits non-zero, stop immediately, report its stderr, and do
not continue to report generation or treat an existing `analyzed.json` as
current.

### 4. Present completion

Read the finalizer output and report the total, recommendation counts, cluster
count, and `.artifacts/triage/{PROJECT}/analyzed.json` path.
