---
name: scan
description: Fetch all unresolved bugs and recently resolved bugs from a Jira project via JQL with pagination.
---

# Scan Jira Bugs Skill

You are fetching **every unresolved bug** and **recently resolved bugs** (for regression / fix-history context in `/analyze`) from the target Jira project. Your goal is to produce complete raw datasets for analysis.

## Allowed Tools

- **Shell:** run `triage/scripts/scan.py` to fetch, normalize, and write artifacts
- **Local:** read script output (stdout, stderr, exit code)
- **Prohibited:** all Jira MCP tools — the script calls the Jira REST API directly

## Prerequisites

Before scanning, ensure you have:

- **Project key** (required) — from `/start` or the user's message
- **`JIRA_URL`** (required) — Jira instance base URL (e.g., `https://redhat.atlassian.net`)
- **`JIRA_TOKEN`** (required) — API token or Personal Access Token
- **`JIRA_EMAIL`** (optional) — account email; required when using an API token (Basic auth), omit for PATs (Bearer auth)

If the project key is missing, ask the user before proceeding. If the environment variables are not set, tell the user which ones to set and stop.

## Process

### Step 1: Verify Environment

Check that `JIRA_URL` and `JIRA_TOKEN` environment variables are set (do not print or echo their values). If either is missing, tell the user which variable to set and stop.

### Step 2: Run the Scan Script

Run the scan script to fetch and normalize all bugs. Resolve
`{AI_WORKFLOWS_ROOT}` by running `git rev-parse --show-toplevel` from
within the ai-workflows checkout (e.g., this skill file's directory).
The `--output-dir` path is relative to the project root (CWD).

```bash
python3 "{AI_WORKFLOWS_ROOT}/triage/scripts/scan.py" {PROJECT} --output-dir .artifacts/triage/{PROJECT}
```

The script handles pagination, normalization, and file output. It writes:

- `.artifacts/triage/{PROJECT}/issues.json` — all unresolved bugs
- `.artifacts/triage/{PROJECT}/resolved.json` — bugs resolved in the last 90 days

To change the resolved-bug lookback window (default 90 days):

```bash
python3 "{AI_WORKFLOWS_ROOT}/triage/scripts/scan.py" {PROJECT} --window-days 30 --output-dir .artifacts/triage/{PROJECT}
```

### Step 3: Handle Errors

If the script exits with a non-zero code, report the error from stderr to the user:

- Exit 1 — missing environment variables, invalid project key, or Jira API errors
- Exit 2 — invalid command-line arguments (e.g., missing project key)

### Step 4: Read the Summary

Read the script's stdout for the scan summary (issue counts by priority and status, artifact file paths).

### Step 5: Present Results

Display the summary from Step 4 to the user.

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
