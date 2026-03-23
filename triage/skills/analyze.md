---
name: analyze
description: Categorize each unresolved bug with recommendations, error signatures, duplicate confidence, and regression hints for the HTML report.
---

# Analyze Bugs Skill

You are analyzing every unresolved bug from the scan results and assigning a triage recommendation to each. Your goal is to produce a categorized dataset ready for the HTML report, including **error signatures**, **duplicate confidence**, and **possible regressions** (using `resolved.json` from `/scan`).

## Allowed Tools

- **Jira MCP:** none — this phase works entirely from local artifact data
- **Local:** read `issues.json` and `resolved.json` (if present), write `analyzed.json`
- **Prohibited:** all Jira tools (no MCP calls in this phase)

## Prerequisites

Before analyzing, ensure:

- `.artifacts/triage/{PROJECT}/issues.json` exists (from `/scan`)

If `resolved.json` is missing (e.g. older scan), treat the resolved list as empty for regression matching — still run analysis; set `regressionOf` to null for all issues.

If `issues.json` is missing, tell the user to run `/scan` first.

## Process

### Step 1: Load Scanned Data

Read unresolved issues from `.artifacts/triage/{PROJECT}/issues.json`.

Read `.artifacts/triage/{PROJECT}/resolved.json` if it exists. If the file is missing or `issues` is empty, use an empty list for regression matching.

### Step 2: Plan Batching

Steps 3–6 are per-issue work. To avoid context degradation on large backlogs, process issues in **batches of 25–30**:

1. Take the next batch of unresolved issues
2. Run Steps 3–6 for each issue in the batch (recommendation, error signature, duplicate detection, regression detection)
3. Append the completed issue objects to a running results array
4. Write the partial results to `analyzed.json` after each batch (overwrite with the latest cumulative state) — this provides a checkpoint if the process is interrupted
5. Repeat until all issues are processed

After all batches complete, proceed to Steps 7–8 (clustering and key recommendations) which need the full result set.

For small backlogs (≤ 30 issues), a single batch is fine — skip the checkpointing.

### Per-Issue Output Schema

Steps 3–7 progressively populate the following fields for each issue. Refer to this schema throughout — all fields must be present in the final output (use `null` when not applicable).

```json
{
  "key": "EDM-1234",
  "summary": "...",
  "status": "Open",
  "priority": "High",
  "suggestedPriority": null,
  "assignee": "Jane Doe",
  "reporter": "John Smith",
  "created": "2025-06-15T10:30:00Z",
  "updated": "2026-01-20T14:00:00Z",
  "labels": ["backend"],
  "components": ["API"],
  "errorType": "NullPointerException",
  "errorCode": null,
  "errorMessageExcerpt": "at com.example.OrderTotals.apply",
  "affectedComponent": "checkout",
  "symptoms": "Checkout throws 500 on submit",
  "environmentHint": null,
  "recommendation": "AUTO_FIX",
  "reason": "Clear NullPointerException with stack trace, specific component, and reproduction steps provided.",
  "confidence": "High",
  "autoFixLikelihood": 75,
  "duplicateOf": null,
  "duplicateConfidence": null,
  "regressionOf": null,
  "clusterId": "cluster-3",
  "priorityMismatch": null
}
```

| Field | Set in | Description |
|-------|--------|-------------|
| `key`, `summary`, `status`, `priority`, `assignee`, `reporter`, `created`, `updated`, `labels`, `components` | Step 1 | Copied from scanned issue data |
| `recommendation` | Step 3 | One of: CLOSE, FIX_NOW, AUTO_FIX, BACKLOG, NEEDS_INFO, DUPLICATE, ESCALATE, WONT_FIX |
| `reason` | Step 3 | 1–2 sentence explanation of the recommendation |
| `confidence` | Step 3 | High (90–100%), Medium (70–89%), Low (<70%) |
| `suggestedPriority` | Step 3 | Priority recommendation when Jira priority is null/undefined/empty/`Undefined`; otherwise null |
| `priorityMismatch` | Step 3 | Object `{assigned, suggested, reason}` when assigned priority ≠ description severity; otherwise null |
| `autoFixLikelihood` | Step 3 | Integer 0–100, only when recommendation is AUTO_FIX |
| `errorType`, `errorCode`, `errorMessageExcerpt`, `affectedComponent`, `symptoms`, `environmentHint` | Step 4 | Nullable strings — error signature fields |
| `duplicateOf` | Step 5 | Jira key of the duplicate target, or null |
| `duplicateConfidence` | Step 5 | Integer 0–100 when `duplicateOf` is set; null otherwise |
| `regressionOf` | Step 6 | Object `{key, summary, resolved, reason}` or null |
| `clusterId` | Step 7 | Cluster identifier (e.g. `"cluster-1"`) or null |

### Step 3: Analyze Each Issue

For every issue, evaluate the following signals and assign a recommendation.

#### Analysis Signals

- **Issue age** — days since creation
- **Last activity** — days since last update
- **Priority** — as set in Jira
- **Description quality** — length, presence of reproduction steps, error details, expected vs actual behavior
- **Components** — which area of the system is affected
- **Labels** — any existing categorization
- **Similar titles** — scan for issues with near-identical summaries (potential duplicates)
- **Assignee** — assigned or unassigned

#### Recommendation Types

Assign exactly one recommendation per issue:

| Recommendation | When to use |
|---|---|
| **CLOSE** | Invalid, obsolete, cannot reproduce, or no activity for 12+ months with vague description |
| **FIX_NOW** | Critical or high priority with clear impact; blockers; recent regressions; quick wins with obvious fixes |
| **AUTO_FIX** | Well-described bug suitable for the unattended bugfix bot — clear repro steps, specific error details, identifiable component, and bounded scope. Never assign if the issue would get NEEDS_INFO |
| **BACKLOG** | Valid bug, not urgent; keep for future prioritization |
| **NEEDS_INFO** | Missing reproduction steps, unclear description, no error details; cannot determine root cause or impact from available information. Mutually exclusive with AUTO_FIX |
| **DUPLICATE** | Appears to duplicate another issue — note the target issue key in `duplicateOf`, and set `duplicateConfidence` (see Step 5) |
| **ESCALATE** | Needs architectural decision, cross-team coordination, or security review |
| **WONT_FIX** | Valid but out of scope, cost-prohibitive, or the affected feature is being deprecated |

#### Priority Mismatch Detection

For each issue that has an assigned priority, compare it against the severity implied by the description. Flag a mismatch when there is a significant gap (1+ priority levels). Skip issues without a priority (those already get `suggestedPriority`).

When a mismatch is detected, set `priorityMismatch` to:

```json
{
  "assigned": "Low",
  "suggested": "Critical",
  "reason": "Description reports complete data loss for all users on save — impact is critical, not low"
}
```

Signals that indicate the description severity differs from the assigned priority:

- **Under-prioritized**: description mentions data loss, security vulnerability, crash, service outage, or blocking regression but priority is Medium/Low/Minor
- **Over-prioritized**: description mentions cosmetic issue, typo, or minor UI glitch but priority is Critical/Blocker/Major
- **Impact keywords**: "all users", "production", "data corruption", "security", "crash" suggest high severity; "cosmetic", "minor", "edge case", "nice to have" suggest low severity

Set `priorityMismatch` to `null` when the assigned priority reasonably matches the description.

#### AUTO_FIX Likelihood Criteria

When assigning `autoFixLikelihood`, consider:

- **80-100%**: Exact error message with stack trace, single file/method, clear fix pattern (e.g. null check, off-by-one, missing validation)
- **60-79%**: Good description with error details, bounded to one component, but fix may require understanding context or multiple files
- **40-59%**: Adequate description, identifiable component, but fix scope is unclear or may involve refactoring
- **Below 40%**: Do not recommend AUTO_FIX — use FIX_NOW or BACKLOG instead

### Step 4: Extract Error Signature (Per Issue)

Populate the error signature fields from the schema above (`errorType`, `errorCode`, `errorMessageExcerpt`, `affectedComponent`, `symptoms`, `environmentHint`). For each unresolved issue, derive these from the title, description, and any stack traces. Use null when a value cannot be determined.

| Field | Meaning |
|-------|---------|
| `errorType` | Class of failure (e.g. `NullPointerException`, `HTTP 500`, `ValidationError`) |
| `errorCode` | Vendor or app code if present (e.g. `ORA-00001`, exit code) |
| `errorMessageExcerpt` | Short verbatim or paraphrased snippet (first line or key phrase) |
| `affectedComponent` | Logical component or module if clearer than Jira components alone |
| `symptoms` | One-line user-visible symptom (e.g. "Save returns 500") |
| `environmentHint` | OS, browser, version, cluster — only if stated |

These fields power the report **Signature** column and improve duplicate/regression matching.

### Step 5: Detect Duplicates (Multi-Angle + Confidence)

Populate `duplicateOf` and `duplicateConfidence` from the schema above. Before finalizing recommendations, evaluate duplicate candidates using **multiple angles** across the **unresolved** backlog (and optionally titles in `resolved.json` for narrative only):

1. **Error / signature angle** — same or highly similar `errorType`, `errorCode`, or overlapping `errorMessageExcerpt` / stack location
2. **Component + symptom angle** — same Jira component(s) and matching `symptoms` or summary phrases
3. **Description similarity** — same root cause described (not merely similar titles)

For each issue, pick the strongest non-self candidate. If two issues describe the **same** underlying bug, mark the **newer** (by `created` or `key`) as **DUPLICATE** with `duplicateOf` pointing to the older.

**`duplicateConfidence`** — integer **0–100** when there is a named duplicate target, reflecting how strong the match is:

| Band | When to use |
|------|-------------|
| **85–100** | Same error signature and same repro path; or explicit duplicate reference in text |
| **70–84** | Strong component + symptom overlap and very similar description |
| **50–69** | Plausible duplicate; needs human confirmation |
| **Below 50** | Do not mark DUPLICATE — prefer BACKLOG or cluster with a note in `reason` |

Set `duplicateOf` to **null** and `duplicateConfidence` to **null** when there is no duplicate target. If you keep DUPLICATE recommendation, both `duplicateOf` and `duplicateConfidence` must be set consistently.

### Step 6: Detect Possible Regressions (Using `resolved.json`)

Populate `regressionOf` from the schema above. Compare each unresolved issue’s **error signature** and **symptoms** to **recently resolved** bugs in `resolved.json` (same project, from `/scan`).

When a resolved issue likely fixed the **same area** and the open bug reads like a **reappearance** (same stack line, same API error, same workflow break), set `regressionOf` on the open issue:

```json
{
  "key": "EDM-900",
  "summary": "Fixed null dereference in checkout totals",
  "resolved": "2026-02-01T10:00:00.000+0000",
  "reason": "Same NPE in OrderTotals.java as EDM-900; reopened after release 3.2"
}
```

- `key` — resolved issue key (required)
- `summary` — short summary of the resolved bug (required)
- `resolved` — resolution date ISO string if known, else null
- `reason` — one sentence tying this open bug to that fix (required)

Set `regressionOf` to **null** when no plausible resolved match exists. This feeds the report **Regression** column and **Possible Regressions** section.

### Step 7: Cluster Similar Bugs

Group related (but not necessarily duplicate) bugs into clusters. Clusters identify issues that share a root cause, affect the same feature area, or would benefit from being linked in Jira.

#### How to Cluster

1. **Identify themes** — look for groups of 2+ issues that share: same error type, same component and similar symptoms, same user-facing feature, or related failure modes
2. **Assign each clustered issue** a `clusterId` (e.g. `"cluster-1"`, `"cluster-2"`, ...). Issues that don't belong to any cluster get `clusterId: null`
3. **Build a cluster object** for each group

#### Cluster Object

```json
{
  "id": "cluster-1",
  "theme": "Authentication timeout errors in login flow",
  "issues": ["EDM-101", "EDM-234", "EDM-567"],
  "suggestedLinkType": "relates to",
  "nextSteps": [
    "Link these 3 issues in Jira as 'relates to'",
    "Investigate shared root cause in auth service timeout configuration",
    "Fix EDM-101 first (most detailed description, highest priority) and verify if EDM-234 and EDM-567 are resolved"
  ]
}
```

Field details:

- `id` — unique cluster identifier
- `theme` — short description of what ties these issues together
- `issues` — array of Jira issue keys in the cluster
- `suggestedLinkType` — recommended Jira link type: `"relates to"` (same area), `"is caused by"` (shared root cause), `"is duplicated by"` (near-duplicates already marked DUPLICATE), or `"blocks"` (dependency chain)
- `nextSteps` — 2-4 actionable recommendations for the cluster, such as:
  - Which issues to link and with what relationship
  - Which issue to fix first and why (most detailed, highest priority, broadest impact)
  - Whether fixing one issue may resolve others in the cluster
  - Whether a single root-cause investigation should cover the cluster

#### Clustering Signals

- **Same error type** across different issues (e.g. multiple NullPointerExceptions in the same package)
- **Same component + similar symptoms** (e.g. three "upload fails" bugs in the File Service)
- **Regression chain** — a fix introduced new bugs, or an old fix regressed
- **Feature area overlap** — bugs affecting the same user flow even if different components
- **Temporal correlation** — bugs created or updated around the same date, suggesting a shared trigger

#### Cluster vs Duplicate

- **Duplicate**: the issues describe the exact same bug — mark the newer as DUPLICATE
- **Cluster**: the issues are related but distinct — they share a theme, root cause area, or feature, but each describes a different manifestation. Cluster members keep their own recommendation (FIX_NOW, AUTO_FIX, BACKLOG, etc.); clustering does not change individual recommendations

### Step 8: Generate Key Recommendations

After all issues are analyzed, clustered, and duplicates detected, produce a `keyRecommendations` array — the most important actions for the team. Each recommendation is a short, actionable sentence.

Generate 5-10 recommendations covering:

- **Immediate fixes** — which FIX_NOW or AUTO_FIX bugs to address first and why
- **Backlog hygiene** — how many issues to close, how many need info
- **Clustering actions** — which clusters to link in Jira, which to investigate for shared root cause
- **Aging concerns** — any patterns in old bugs (stale, neglected components)
- **Assignee balance** — overloaded or unassigned areas
- **Priority gaps** — how many bugs lack a priority and the impact
- **Regressions** — if any `regressionOf` cases exist, call them out

Example:

```json
[
  "Close 8 stale bugs with no activity in 12+ months to reduce backlog noise",
  "Submit 5 AUTO_FIX candidates (avg 78% likelihood) to the bugfix bot — start with EDM-1234 (95%)",
  "Link 3 authentication timeout bugs (cluster-1) as 'relates to' and investigate shared root cause",
  "Assign the 15 unassigned High-priority bugs — API component has the highest unassigned load",
  "Request more information on 15 NEEDS_INFO bugs before they can be triaged further",
  "Set priority on 12 bugs currently without one — 4 appear to be High based on description",
  "Review 3 possible regressions of recently resolved bugs — verify against release 3.2"
]
```

### Step 9: Save Analyzed Data

Write the analyzed issues to:

```
.artifacts/triage/{PROJECT}/analyzed.json
```

Format:

```json
{
  "project": "EDM",
  "analyzedAt": "2026-03-19T12:30:00Z",
  "totalCount": 87,
  "summary": {
    "CLOSE": 8,
    "FIX_NOW": 5,
    "AUTO_FIX": 12,
    "BACKLOG": 35,
    "NEEDS_INFO": 15,
    "DUPLICATE": 4,
    "ESCALATE": 3,
    "WONT_FIX": 5
  },
  "clusters": [
    {
      "id": "cluster-1",
      "theme": "Authentication timeout errors in login flow",
      "issues": ["EDM-101", "EDM-234", "EDM-567"],
      "suggestedLinkType": "relates to",
      "nextSteps": ["Link these issues as 'relates to'", "Investigate shared root cause", "Fix EDM-101 first"]
    }
  ],
  "keyRecommendations": [
    "Close 8 stale bugs with no activity in 12+ months",
    "Submit 5 AUTO_FIX candidates to the bugfix bot"
  ],
  "issues": [ ... ]
}
```

Each issue in the `issues` array must follow the Per-Issue Output Schema defined above.

**Note:** `executiveSummary` and `releaseRiskAssessment` are **not** part of the analyze output — they are synthesized during `/report` (see `report.md` Step 4).

### Step 10: Present Summary

Display a summary of the analysis:

```text
Analysis complete: 87 issues categorized

  CLOSE:      8   (9%)
  FIX_NOW:    5   (6%)
  AUTO_FIX:  12   (14%) — avg likelihood: 72%
  BACKLOG:   35   (40%)
  NEEDS_INFO: 15  (17%)
  DUPLICATE:  4   (5%)
  ESCALATE:   3   (3%)
  WONT_FIX:   5   (6%)

Possible regressions (regressionOf set): 3
Clusters: 6 clusters covering 22 issues
  cluster-1: "Authentication timeout errors" — 3 issues (relates to)
  cluster-2: "File upload failures" — 4 issues (is caused by)
  ...

Data saved to .artifacts/triage/EDM/analyzed.json
```

For AUTO_FIX issues, include a brief list showing key, summary, and likelihood percentage.
For each cluster, show the theme, issue count, and suggested link type.

## Output

- Analysis summary displayed to the user
- `.artifacts/triage/{PROJECT}/analyzed.json` written

## On Completion

Report your findings:

- Total issues categorized and breakdown by recommendation
- Number of AUTO_FIX candidates and their average likelihood
- Number of potential duplicates detected (with confidence distribution if useful)
- Number of issues with `regressionOf` set
- Number of clusters found and total issues covered by clusters
- Number of issues with missing priority and the suggested priorities assigned
- Any issues where confidence was Low (flag for human review)

Then recommend next steps:

**Recommended:** `/report` — generate the interactive HTML report from the analyzed data.

**Alternatives:**
- `/analyze` — re-analyze if the recommendations need adjustment (e.g. different criteria)
- `/scan` — re-scan if the underlying Jira data has changed since the last scan
