---
name: assess
description: >-
  Full single-issue triage: error signature, recommendation (same taxonomy as bulk),
  priority mismatch, AUTO_FIX likelihood, duplicates, regression hints, read-only.
  Invoked by /assess.
---

# Single-Issue Triage Skill

You perform **full triage on one bug** — the same analytical dimensions as bulk `/analyze` **where they apply to a single issue**, using **read-only** Jira access (no create, update, or comment).

## Scope: what to analyze vs. skip

**Include every applicable dimension for this one bug:**

- **Error signature** — `errorType`, `errorCode`, `errorMessageExcerpt`, `affectedComponent`, `symptoms`, `environmentHint` (same fields as bulk analyze)
- **Recommendation** — exactly one of: CLOSE, FIX_NOW, AUTO_FIX, BACKLOG, NEEDS_INFO, DUPLICATE, ESCALATE, WONT_FIX (same definitions as [`analyze.md`](analyze.md)); **reason** (1–2 sentences); **confidence** High / Medium / Low
- **AUTO_FIX** — when recommendation is AUTO_FIX, give **autoFixLikelihood** (0–100) using the same criteria as bulk analyze
- **NEEDS_INFO** — mutually exclusive with AUTO_FIX; call out what is missing
- **Priority mismatch** — compare Jira priority to severity implied by summary/description (same logic as bulk `priorityMismatch`)
- **Staleness / activity** — created/updated dates; whether CLOSE-style staleness applies (vague + inactive), without needing other issues for comparison
- **Duplicates** — multi-angle `jira_search` + **duplicateConfidence** (0–100) for candidates; if mode A, exclude self-key when comparing
- **Regression hint** — search resolved bugs (e.g. last 90 days) for same signature/symptoms; describe possible **regressionOf**-style relationship in prose (no `resolved.json` required if you query Jira). A regression signals functionality that was broken, fixed, and is now broken again — focus on the insight: what area keeps failing and whether the prior fix was incomplete or reintroduced. **Chronological constraint:** only flag a regression when the resolved bug was created *before* the open bug — an older bug cannot be a regression of a newer fix
- **ESCALATE / WONT_FIX** — when the text clearly warrants it (cross-team, security, out of scope)

**Skip only what inherently needs multiple open bugs:**

- **Clusters** — grouping 2+ issues by theme, suggested link types across a set, cluster `nextSteps`
- **Backlog-wide metrics** — assignee load, status×priority matrix, aging **distribution** across the project, executive **key recommendations** list for the whole team
- **Simulation** / HTML report / `analyzed.json` — those are bulk `/report` outputs

Optional: cross-reference `.artifacts/triage/{PROJECT}/issues.json` if present — useful for DUPLICATE/FIX_NOW context, not required.

## Allowed Tools

- **Jira MCP (read-only):** `jira_search` — server `user-mcp-jira`
- **Local:** optionally read `.artifacts/triage/{PROJECT}/issues.json`
- **Prohibited:** all Jira write tools

## Input modes

| Mode | What the user provides | Project key |
|------|------------------------|-------------|
| **A — Jira issue link** | A URL to an existing issue (e.g. `https://company.atlassian.net/browse/EDM-1234`) | **Not required** — parse the **issue key** from the URL; project = key prefix (`EDM-1234` → `EDM`) |
| **B — Free text** | Error message, stack trace, or bug description without a Jira URL | **Required** — ask for the project key unless unambiguous |

**Parsing issue links:** `/browse/KEY-NUM`, `/projects/.../issues/KEY-NUM`; keys match `[A-Z][A-Z0-9]+-\d+`.

After mode **A**, `jira_search` with JQL `key = {ISSUE_KEY}` (limit 1) to load fields needed for full analysis (summary, description, status, priority, components, labels, created, updated, assignee, etc.).

## Process

### Step 1: Load issue context

- **Mode A:** Fetch the issue by key; treat it as the bug under triage.
- **Mode B:** Use pasted text only; you may still search the project for similarly titled issues if the user gives a key in text.

### Step 2: Extract error signature

Derive: `errorType`, `errorCode`, `errorMessageExcerpt`, `affectedComponent`, `symptoms`, `environmentHint` (nulls OK).

### Step 3: Single-issue assessment (parallel to bulk analyze signals)

Using only this issue's fields + extracted signature:

- **Description quality** — repro steps, expected/actual, stack traces → NEEDS_INFO vs AUTO_FIX vs others
- **Priority vs severity** — set `priorityMismatch` object or null (same shape as bulk: `assigned`, `suggested`, `reason`)
- **Age / last activity** — support CLOSE or BACKLOG narrative when relevant
- **AUTO_FIX likelihood** — only if AUTO_FIX is in play; else omit
- Draft an initial **recommendation** + **reason** + **confidence**

### Step 4: Search Jira (duplicates + regression context)

Use **project key** `PROJECT`.

1. **Duplicate-oriented searches** (up to three angles): error-focused, component-focused, symptom-focused — limit ~20 each; dedupe keys; exclude the current issue key in mode A when listing "other" candidates.
2. **Resolved issues** — include JQL that surfaces recently **resolved** bugs in the same area (e.g. `resolved >= -90d`) to support regression narrative.

Assign **duplicateConfidence** (0–100) per strong candidate using bulk bands.

### Step 5: Integrate and finalize

- If a **duplicate** is conclusive, set recommendation to **DUPLICATE** with `duplicateOf` (target key) and **duplicateConfidence**; align reason.
- If a **resolved** issue strongly matches, describe regression risk and whether **FIX_NOW** is warranted.
- Reconcile with **ESCALATE**, **WONT_FIX**, **CLOSE** if signals demand.

### Step 6: Present findings (read-only)

Structure the answer so the user sees a **full triage** (not only duplicate search):

1. **Recommendation** — type, reason, confidence  
2. **Error signature** — extracted fields  
3. **Priority mismatch** — if any  
4. **AUTO_FIX likelihood** — if AUTO_FIX  
5. **Duplicates** — ranked candidates with duplicateConfidence and angles  
6. **Regression / fix history** — if relevant  
7. **Next actions** — comment/link/new issue (recommendations only; user acts in Jira)

Explicitly state that **no Jira changes** were made.

## Output

- Complete single-issue triage: recommendation taxonomy + all applicable sub-analyses above  
- No Jira writes

## On Completion

- Offer bulk `/scan` → `/analyze` → `/report` if they want project-wide artifacts  
- Remind: cluster cards, assignee load, and HTML dashboard require bulk workflow
