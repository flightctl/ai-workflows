---
name: assess
description: >-
  Analytical bug assessment combining error signature extraction, recommendation
  taxonomy, duplicate/regression search, and source-code exploration. Produces a
  structured assessment artifact and inline findings.
---

# Assess Bug Report Skill

You are performing a structured analytical assessment of a bug report. This is
the first phase of the bugfix workflow. Your job is to analyze the bug, explore
the source code, and produce a comprehensive assessment — not to start fixing
anything.

This assessment combines the triage analytical framework (error signatures,
recommendation taxonomy, duplicate/regression detection) with source-code
exploration that only a repo-local workflow can provide.

## Critical Rules

- **Do not start reproducing, diagnosing, or fixing.** This phase is analysis
  and planning only.
- **Do not run the project's code or tests.** Read code, don't execute it.
- **Be honest about uncertainty.** If the report is vague, say so.
- **No issue-tracker writes.** Read-only access to Jira and GitHub.

## Bug Report Sources

The bug report can come from three sources. The source repo is always the
local working directory.

| Source | Input | Issue-tracker search |
|--------|-------|----------------------|
| Jira URL | `https://{jira-host}/browse/KEY-NUM` | Jira MCP (read-only) for duplicates, regressions, priority mismatch |
| GitHub URL | `https://github.com/owner/repo/issues/NUM` | `gh issue list --search` for duplicates |
| Free text | Error text, stack trace, or description | Jira if a project key is provided; otherwise git-only |

**Parsing rules:**

- Jira keys match `[A-Z][A-Z0-9]+-\d+` from `/browse/` or `/issues/` URL
  paths. The project prefix is the part before the hyphen.
- GitHub URLs match `github.com/{owner}/{repo}/issues/{number}`.
- Unrecognized URLs (e.g., Bugzilla, GitLab): treat as free text and ask
  the user to paste the bug description.

## Process

### Step 1: Gather the Bug Report

Collect all available information about the bug:

- **Jira URL:** Fetch the issue via the Jira MCP (e.g., by key lookup or
  JQL `key = {KEY}`). Load summary, description, status, priority, components,
  labels, created, updated, and comments.
- **GitHub URL:** Fetch via:

```bash
gh issue view NUMBER --repo OWNER/REPO --json title,body,labels,comments,state,createdAt,updatedAt
```

- **Free text:** Use the text the user provided. If a Jira project key is
  mentioned, note it for duplicate/regression search in later steps.
- Check if prior artifacts exist in `.artifacts/bugfix/{issue}/` from a
  previous session and use them to inform your understanding.

### Step 2: Create Artifact Directory

Determine the issue identifier and create the artifact directory:

- Jira: use the full key (e.g., `EDM-1234`)
- GitHub: use the issue number (e.g., `421`)
- Free text: in interactive mode, ask the user for an identifier. In
  unattended/bot mode, derive one from the bug summary (e.g., `npe-on-login`)

```bash
mkdir -p .artifacts/bugfix/{issue}
```

### Step 3: Extract Error Signature

Derive these six fields from the bug report. Use `null` when a value cannot
be determined.

| Field | Meaning |
|-------|---------|
| `errorType` | Class of failure (e.g., `NullPointerException`, `HTTP 500`, `ValidationError`) |
| `errorCode` | Vendor or application code if present (e.g., `ORA-00001`, exit code) |
| `errorMessageExcerpt` | Short verbatim or paraphrased snippet (first line or key phrase) |
| `affectedComponent` | Logical component or module — refine using source code in Step 4 |
| `symptoms` | One-line user-visible symptom (e.g., "Save returns 500") |
| `environmentHint` | OS, browser, version, cluster — only if stated |

### Step 4: Source-Code Exploration

Explore the local repository to build source-level context for the bug. This
is what differentiates this assessment from a Jira-only triage.

#### 4a: Trace error paths

If the error signature identifies an affected component or error type, locate
it in the codebase. Use `grep`, file reading, and call-chain analysis to trace
the code path from entry point to the failure described in the bug. Record
specific `file:line` references.

#### 4b: Identify affected files

List the files and line ranges involved. If the bug mentions specific
functions, classes, or API endpoints, find them.

#### 4c: Check recent changes

```bash
git log --oneline -20 -- {affected files}
```

If the 20 most recent commits all postdate the bug report's creation date,
increase the range to reach commits before the bug appeared — the regression
window may be further back.

Run `git blame` on the relevant sections. Note any recent commits that touched
the affected code — these feed into regression analysis (Step 7).

#### 4d: Assess code complexity

For AUTO_FIX calibration, note:

- Is the fix area a single function or a multi-file interaction?
- Is there existing test coverage for the affected code?
- Are there complex state dependencies or concurrency concerns?

#### 4e: Refine error signature

If source-code exploration reveals a more specific `affectedComponent` or
`errorType` than the bug report alone provided, update those fields.

### Step 5: Single-Issue Assessment

Using the bug report, error signature, and source-code findings, evaluate:

#### Recommendation

Assign exactly one recommendation:

| Recommendation | When to use |
|---|---|
| **CLOSE** | Invalid, obsolete, cannot reproduce, or no activity for 12+ months with vague description |
| **FIX_NOW** | Critical or high priority with clear impact; blockers; recent regressions; quick wins with obvious fixes |
| **AUTO_FIX** | Well-described bug suitable for unattended fixing — clear repro steps, specific error details, identifiable component, bounded scope. Never assign if the issue would get NEEDS_INFO |
| **BACKLOG** | Valid bug, not urgent; keep for future prioritization |
| **NEEDS_INFO** | Missing reproduction steps, unclear description, no error details. Mutually exclusive with AUTO_FIX |
| **DUPLICATE** | Appears to duplicate another issue — set with duplicate search in Step 6 |
| **ESCALATE** | Needs architectural decision, cross-team coordination, or security review |
| **WONT_FIX** | Valid but out of scope, cost-prohibitive, or the affected feature is being deprecated |

Provide a **reason** (1–2 sentences) and **confidence** (High / Medium / Low).

#### AUTO_FIX Likelihood

Only when recommendation is AUTO_FIX. Score 0–100 using these bands, then
adjust based on source-code complexity from Step 4d:

| Band | Description-quality criteria | Code-level adjustments |
|------|----------------------------|----------------------|
| **80–100** | Exact error message with stack trace, single file/method, clear fix pattern (null check, off-by-one, missing validation) | Single function, good test coverage → keep high. Complex state → push down |
| **60–79** | Good description with error details, bounded to one component, fix may require context or multiple files | Well-structured code → keep. Recent refactoring churn → push down |
| **40–59** | Adequate description, identifiable component, fix scope unclear or may involve refactoring | Clear boundaries → keep. Tangled dependencies → push down |
| **Below 40** | Do not recommend AUTO_FIX — use FIX_NOW or BACKLOG instead | — |

Explicitly state which band the description quality places it in, then what
code-level factors adjusted the score.

#### Priority Mismatch (Jira-sourced issues only)

Compare the assigned Jira priority against the severity implied by the
description. Flag a mismatch when there is a gap of 1+ priority levels.

Signals for under-prioritization: description mentions data loss, security
vulnerability, crash, service outage, or blocking regression but priority is
Medium/Low.

Signals for over-prioritization: description mentions cosmetic issue, typo,
or minor UI glitch but priority is Critical/Blocker.

Set to `null` when the assigned priority reasonably matches the description,
or when the source is not Jira.

This recommendation is preliminary. Steps 6 and 7 may override it based on
duplicate or regression findings.

### Step 6: Search for Duplicates

Search the issue tracker for potential duplicates. Skip this step if no
tracker is accessible.

**Jira (project key available):** Search Jira via JQL using up to three
angles, limit ~20 results each:

1. **Error-focused:** match `errorType`, `errorCode`, or error message
   keywords in summary/description
2. **Component-focused:** same Jira components with similar summary phrases
3. **Symptom-focused:** match the user-visible symptom description

Exclude the current issue key when comparing. For each strong candidate,
assign a `duplicateConfidence`:

| Band | When to use |
|------|-------------|
| **85–100** | Same error signature and same repro path; or explicit duplicate reference in text |
| **70–84** | Strong component + symptom overlap and very similar description |
| **50–69** | Plausible duplicate; needs human confirmation |
| **Below 50** | Do not mark as duplicate |

**GitHub (repo available):** Search with `gh issue list --search` using 2–3
search-term angles. Apply the same confidence bands.

If a conclusive duplicate is found, update the recommendation to DUPLICATE.

### Step 7: Search for Regressions

Look for signs that this bug is a reappearance of a previously fixed issue.

**Git (primary — always available):** Use the `git log` findings from Step
4c. If recent commits modified the affected code and the timeline aligns with
when the bug appeared, describe the regression risk. Git history is the
strongest regression signal because it shows exactly what changed and when.

**Jira (supplementary — when project key available):** Search for recently
resolved bugs in the same area to find prior fix attempts:

```
project = {KEY} AND resolution = Done AND resolved >= -90d
AND (summary ~ "{keywords}" OR component = "{component}")
```

**Chronological constraint:** the resolved bug's resolution date must be
before the open bug's creation date. If the fix landed after the new bug was
filed, it is not a regression.

A regression signals functionality that was broken, fixed, and is now broken
again. Focus on the insight: what area keeps failing and whether the prior fix
was incomplete or was reintroduced.

If a strong regression is found, consider whether FIX_NOW is warranted.

### Step 8: Present Findings

Persist the assessment to `.artifacts/bugfix/{issue}/assessment.md`, then
present the same findings inline to the user.

Use this structure:

```markdown
## Bug Assessment

**Issue:** [title or one-line summary]
**Source:** [Jira URL / GitHub URL / conversation]
**Recommendation:** [TYPE] ([Confidence])
**Reason:** [1-2 sentences]

### Summary

[2-3 sentence understanding of the bug, incorporating source-code context]

### Error Signature

| Field | Value |
|-------|-------|
| Error Type | [value or —] |
| Error Code | [value or —] |
| Message Excerpt | [value or —] |
| Affected Component | [value or —] |
| Symptoms | [value or —] |
| Environment | [value or —] |

### Source-Code Context

- **Affected files:** [file:line references]
- **Error path:** [brief trace from entry point to failure]
- **Recent changes:** [relevant git log entries, if any]
- **Code complexity:** [assessment relevant to AUTO_FIX likelihood]

### AUTO_FIX Likelihood

[Only when recommendation is AUTO_FIX]
**Score:** [0-100]% — **Band:** [description]
**Factors:**
- [Description quality factor and band placement]
- [Code complexity adjustment from source exploration]
- [Scope factor]

### Priority Mismatch

[Only when detected; Jira-sourced issues only]
- **Assigned:** [priority]
- **Suggested:** [priority]
- **Reason:** [why]

### Duplicates

[Ranked candidates with confidence, or "No duplicate candidates found."]

| # | Issue | Summary | Confidence | Search Angle |
|---|-------|---------|------------|--------------|

### Regression / Fix History

[Regression candidates from Jira and/or git history, or "No regression
indicators found."]

### Available Information

- [What the report provides — repro steps, logs, environment, etc.]

### Gaps & Questions

- [What is missing or unclear]
- [Assumptions: "Assumed X because Y — confirm?"]
- [Questions for the user before proceeding]

### Proposed Plan

1. [Recommended next step]
2. [Further steps]
```

**Conditional sections:** Omit AUTO_FIX Likelihood when the recommendation is
not AUTO_FIX. Omit Priority Mismatch when none is detected or the source is
not Jira. Do not include empty placeholder sections.

**Conciseness:** Each section should be as short as the content warrants. A
clear bug with no duplicates and no regressions should produce a brief
assessment, not pad every section.

## Output

- Assessment persisted to `.artifacts/bugfix/{issue}/assessment.md`
- Same findings presented inline to the user
- No code is executed, no project source files are modified, no
  issue-tracker writes

## When This Phase Is Done

Report your assessment and state where the artifact was written. Then
**re-read the controller** (`skills/controller.md`) for next-step guidance.
