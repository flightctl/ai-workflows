---
name: scan
description: Fetch all unresolved bugs and recently resolved bugs from a Jira project via JQL with pagination.
---

# Scan Jira Bugs Skill

You are fetching **every unresolved bug** and **recently resolved bugs** (for regression / fix-history context in `/analyze`) from the target Jira project. Your goal is to produce complete raw datasets for analysis.

## Allowed Tools

- **Jira MCP (read-only):** `jira_search` — fetch issues via JQL
- **Local:** write `issues.json` and `resolved.json` artifacts
- **Prohibited:** all Jira write tools (create, update, delete, comment, transition)

## Prerequisites

Before scanning, ensure you have:

- **Project key** (required) — from `/start` or the user's message

If the project key is missing, ask the user before proceeding.

## Process

### Step 1: Fetch Unresolved Bugs (JQL with Key-Based Cursor Pagination)

Use the `jira_search` MCP tool (server: `user-mcp-jira`) to fetch all unresolved bugs. The tool returns a maximum of 50 results per call, so you must paginate.

**Important:** The `start_at` parameter of the MCP tool is non-functional (the response always returns `total: -1` and ignores `start_at`). Use **JQL key-based cursor pagination** instead: sort by `key ASC` and add `AND key > '{LAST_KEY}'` to advance through pages.

**First call** — fetches the first 50 issues sorted by key:

```json
{
  "jql": "project = EDM AND issuetype = Bug AND resolution = Unresolved ORDER BY key ASC",
  "fields": "summary,status,priority,assignee,reporter,created,updated,labels,components,description",
  "limit": 50
}
```

**Pagination loop:**

```text
last_key = ""
all_issues = []

loop:
  1. Build JQL:
     - First call: "project = {PROJECT} AND issuetype = Bug AND resolution = Unresolved ORDER BY key ASC"
     - Subsequent calls: "project = {PROJECT} AND issuetype = Bug AND resolution = Unresolved AND key > '{last_key}' ORDER BY key ASC"
  2. Call jira_search with the JQL and limit=50
  3. Let page_issues = the returned issues array
  4. If page_issues is empty → stop (all issues fetched)
  5. Append page_issues to all_issues
  6. last_key = the key of the last issue in page_issues
  7. If len(page_issues) < 50 → stop (final partial page)
  8. Go to step 1
```

Important:
- Always set `ORDER BY key ASC` — this gives a deterministic sort for cursor pagination.
- Never use `start_at` for pagination — it is ignored by the MCP tool.
- Stop when a page returns fewer than 50 issues (final page) or zero issues.
- Deduplicate by key as a safety net before saving.

### Step 2: Fetch Recently Resolved Bugs (Regression Context)

After the unresolved scan completes, fetch **bugs resolved in the last 90 days** using the same key-based cursor pagination pattern.

**JQL (first call):**

```text
project = {PROJECT} AND issuetype = Bug AND resolution != Unresolved AND resolved >= -90d ORDER BY key ASC
```

**Pagination:** Same loop as Step 1, but substitute the unresolved JQL with the resolved JQL above, and use `AND key > '{last_key}'` on subsequent pages.

**Fields:** Include at minimum: `summary,status,priority,assignee,reporter,created,updated,labels,components,description,resolution`. Request resolution date if your Jira API exposes it (e.g. `resolutiondate` or equivalent) so `/analyze` can match fix timing.

If the resolved query returns **zero** issues (quiet project), still write `resolved.json` with an empty `issues` array — `/analyze` must be able to read the file.

### Step 3: Normalize Issue Data

For each **unresolved** issue, extract and normalize:

- `key` — Jira issue key (e.g. `EDM-1234`)
- `summary` — issue title
- `status` — current status name
- `priority` — priority name (Critical, High, Medium, Low, etc.)
- `assignee` — display name or "Unassigned"
- `reporter` — display name
- `created` — creation date (ISO 8601)
- `updated` — last update date (ISO 8601)
- `labels` — array of labels
- `components` — array of component names
- `description` — full description text (may be long; preserve it for analysis)

For each **resolved** issue, normalize the same fields plus when available:

- `resolution` — resolution name (e.g. Fixed, Done)
- `resolved` — resolution date (ISO 8601), if available from the API response

### Step 4: Extract Jira Base URL

Inspect the `jira_search` response for a `self` URL or similar field that contains the Jira instance domain (e.g. `https://mycompany.atlassian.net`). Save this so the `/report` phase can link issue keys without making additional Jira calls.

### Step 5: Save Raw Data

Write the normalized issues to the artifact file:

```
.artifacts/triage/{PROJECT}/issues.json
```

Format as a JSON object:

```json
{
  "project": "EDM",
  "jiraBaseUrl": "https://mycompany.atlassian.net",
  "scannedAt": "2026-03-19T12:00:00Z",
  "totalCount": 87,
  "issues": [ ... ]
}
```

Write the resolved-bug dataset to:

```
.artifacts/triage/{PROJECT}/resolved.json
```

Format:

```json
{
  "project": "EDM",
  "jiraBaseUrl": "https://mycompany.atlassian.net",
  "scannedAt": "2026-03-19T12:05:00Z",
  "windowDays": 90,
  "totalCount": 42,
  "issues": [ ... ]
}
```

Use the same `jiraBaseUrl` and a `scannedAt` timestamp when you finish the resolved pass. `windowDays` should be `90` when using the default `-90d` JQL window.

### Step 6: Present Summary

Display a summary of the scan results:

```text
Scan complete: 87 unresolved bugs in EDM
Resolved (last 90 days): 42 bugs — saved for regression context

By priority:
  Critical:  3
  High:     12
  ...

By status:
  Open:        52
  ...

Data saved to:
  .artifacts/triage/EDM/issues.json
  .artifacts/triage/EDM/resolved.json
```

## Output

- Scan summary displayed to the user
- `.artifacts/triage/{PROJECT}/issues.json` written
- `.artifacts/triage/{PROJECT}/resolved.json` written

## On Completion

Report your findings (total unresolved bugs, total resolved in window, breakdown by priority and status, artifact paths), then recommend next steps:

**Recommended:** `/analyze` — categorize the {N} unresolved bugs with AI recommendations (using `resolved.json` for regression hints).

**Alternatives:**
- `/scan` — re-scan if the data looks stale or parameters need changing
- Stop here if you only needed issue counts

**Edge case:** If zero **unresolved** issues were fetched, the workflow is done — there's nothing to triage. Suggest verifying the project key or issue type filter. (Resolved-only data can still exist; still write `resolved.json`.)
