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

### Step 2: Analyze Each Issue

For every issue, evaluate the following signals and assign a recommendation.

#### Analysis Signals

- **Issue age** — days since creation
- **Last activity** — days since last update
- **Priority** — as set in Jira
- **Description quality** — length, presence of reproduction steps, error details, expected vs actual behavior
- **Comment count** — indicator of engagement and discussion
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
| **DUPLICATE** | Appears to duplicate another issue — note the target issue key in `duplicateOf`, and set `duplicateConfidence` (see Step 4) |
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

### Step 3: Extract Error Signature (Per Issue)

For each unresolved issue, derive structured fields from the title, description, and any stack traces. Use null when a value cannot be determined.

| Field | Meaning |
|-------|---------|
| `errorType` | Class of failure (e.g. `NullPointerException`, `HTTP 500`, `ValidationError`) |
| `errorCode` | Vendor or app code if present (e.g. `ORA-00001`, exit code) |
| `errorMessageExcerpt` | Short verbatim or paraphrased snippet (first line or key phrase) |
| `affectedComponent` | Logical component or module if clearer than Jira components alone |
| `symptoms` | One-line user-visible symptom (e.g. "Save returns 500") |
| `environmentHint` | OS, browser, version, cluster — only if stated |

These fields power the report **Signature** column and improve duplicate/regression matching.

### Step 4: Detect Duplicates (Multi-Angle + Confidence)

Before finalizing recommendations, evaluate duplicate candidates using **multiple angles** across the **unresolved** backlog (and optionally titles in `resolved.json` for narrative only):

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

### Step 5: Detect Possible Regressions (Using `resolved.json`)

Compare each unresolved issue’s **error signature** and **symptoms** to **recently resolved** bugs in `resolved.json` (same project, from `/scan`).

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

### Step 6: Cluster Similar Bugs

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

### Step 7: Generate Key Recommendations

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

### Step 8: Generate Executive Summary

Produce an `executiveSummary` array — 3–5 bullet-point strings that give stakeholders a 30-second health assessment of the backlog. Each bullet synthesizes data across sections rather than repeating raw counts.

Focus on:

- **Backlog size & actionable reduction** — how many bugs exist, what percentage can be closed or merged (CLOSE + WONT_FIX + DUPLICATE), and what the effective backlog would be after cleanup
- **Severity snapshot** — how many critical/high-priority clusters or issues need immediate attention
- **Quality signal** — duplicate density, how many bugs lack priority or info, aging trends
- **Regression risk** — whether resolved bugs are reappearing
- **Key takeaway** — one sentence on the single most impactful action the team can take

Write in plain language suitable for a delivery manager or engineering lead who has not read the full report. Avoid Jira keys; use counts and themes instead.

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

### Step 9: Generate Release Risk Assessment

Produce a `releaseRiskAssessment` object that answers: "Based on the bug backlog alone, what is the risk of shipping now?"

**Important:** This assessment covers **bug-backlog risk only**. It does not account for test coverage, feature completeness, or deployment readiness — note this scope limitation in the output.

#### Schema

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
    "Assign the 2 unresolved Blocker/Critical bugs (EDM-3454, EDM-3491) to the current sprint."
  ]
}
```

Field details:

- `riskLevel` — **High**, **Medium**, or **Low**
- `summary` — one sentence overall risk statement
- `factors` — array of risk signals, each with `signal` (short label), `severity` (High / Medium / Low), and `detail` (one sentence explaining the signal)
- `mitigations` — array of 2–5 actionable strings that would reduce the risk level

#### Risk Level Criteria

| Level | When to assign |
|-------|---------------|
| **High** | Any of: open regressions ≥ 5, unresolved Blocker/Critical bugs ≥ 3, high-urgency clusters with no owner, or > 40% of bugs lack priority |
| **Medium** | Moderate regression count (1–4), a few high-priority bugs remain, some stale critical-path bugs, or significant NEEDS_INFO backlog |
| **Low** | No open regressions, few high-priority bugs, clusters are manageable, backlog is well-triaged |

#### Risk Factor Signals

Evaluate these signals and include only those that are **present and material**:

- **Open regressions** — bugs matching recently resolved fixes (`regressionOf` set)
- **Unresolved Blocker/Critical bugs** — FIX_NOW bugs at the top of the severity scale
- **Unowned high-urgency clusters** — clusters with high urgency scores but no assignees on member issues
- **Priority blind spots** — large percentage of bugs without assigned priority
- **Stale critical-path bugs** — old bugs in critical components that haven't been investigated
- **NEEDS_INFO blockers** — bugs that can't be triaged until more information is gathered
- **Duplicate noise** — high duplicate density suggesting the backlog doesn't reflect true scope

Set `releaseRiskAssessment` to **null** when there is insufficient data to make a meaningful assessment (e.g. very small backlog with < 5 issues).

### Step 10: Save Analyzed Data

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
  "executiveSummary": [
    "The EDM backlog contains 87 open bugs; 17 (20%) are duplicates or closure candidates.",
    "Three high-urgency clusters share overlapping root causes in auth and checkout.",
    "3 bugs appear to regress recently resolved fixes — verify before next deployment."
  ],
  "releaseRiskAssessment": {
    "riskLevel": "High",
    "summary": "30 potential regressions and 2 unresolved Critical bugs present significant release risk.",
    "factors": [
      { "signal": "Open regressions", "severity": "High", "detail": "30 bugs may regress recently resolved fixes." },
      { "signal": "Critical bugs unresolved", "severity": "High", "detail": "2 Critical FIX_NOW bugs remain open." }
    ],
    "mitigations": [
      "Verify and resolve the 30 regression candidates before deployment.",
      "Assign the 2 Critical bugs to the current sprint."
    ]
  },
  "issues": [ ... ]
}
```

#### Output Fields Per Issue (Full Schema)

For each issue, produce:

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

Field details:

- `recommendation` — one of: CLOSE, FIX_NOW, AUTO_FIX, BACKLOG, NEEDS_INFO, DUPLICATE, ESCALATE, WONT_FIX
- `reason` — 1-2 sentence explanation of why this recommendation was chosen
- `confidence` — High (90-100%), Medium (70-89%), Low (<70%) — how confident you are in the recommendation
- `autoFixLikelihood` — integer 0-100, only present when recommendation is AUTO_FIX. Estimate the bugfix bot's chance of success based on: description clarity, scope of the expected change, complexity of the fix, and how well-isolated the component is
- `duplicateOf` — Jira issue key of the suspected duplicate target, or null
- `duplicateConfidence` — integer 0-100 when `duplicateOf` is set; **null** when not DUPLICATE or no scored candidate
- `regressionOf` — object or null. When set, see Step 5
- `errorType`, `errorCode`, `errorMessageExcerpt`, `affectedComponent`, `symptoms`, `environmentHint` — nullable strings from Step 3
- `suggestedPriority` — only present when `priority` is null/undefined/empty/`Undefined` (per your Jira normalization). Recommend a priority (Critical, High, Medium, Low) based on the issue's description. Set to null when the issue already has a real priority in Jira
- `clusterId` — the cluster this issue belongs to (e.g. `"cluster-1"`), or null if the issue is not part of any cluster
- `priorityMismatch` — object or null. Set when the bug's assigned priority doesn't match the severity implied by its description

### Step 11: Present Summary

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
