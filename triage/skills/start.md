---
name: start
description: Validate Jira access and confirm the project key.
---

# Start Triage Skill

You are onboarding the user into the triage workflow. Your goal is to validate Jira access and confirm which project to triage.

## Allowed Tools

- **Jira MCP (read-only):** `jira_search` — validate project access only
- **Local:** `mkdir` — create artifact directory
- **Prohibited:** all Jira write tools (create, update, delete, comment, transition)

## Process

### Step 1: Present the Workflow

Briefly explain what the triage workflow does:

- Fetches all unresolved bugs from a Jira project
- Analyzes each bug and assigns a recommendation (FIX_NOW, AUTO_FIX, BACKLOG, CLOSE, NEEDS_INFO, DUPLICATE, ESCALATE, WONT_FIX)
- Generates an interactive HTML report with stats, filters, sorting, and simulation

### Step 2: Gather Parameters

You need one parameter. If it was provided in the user's message, use it directly — don't ask again.

1. **Project key** (required) — the Jira project key, e.g. `EDM`

### Step 3: Validate Jira Access

Verify the project is accessible by running a lightweight JQL query using the `jira_search` MCP tool (server: `user-mcp-jira`) with these exact JSON arguments:

```json
{
  "jql": "project = {PROJECT} AND issuetype = Bug AND resolution = Unresolved ORDER BY key ASC",
  "fields": "summary,status",
  "limit": 1
}
```

If the query succeeds and returns at least one issue, Jira access is confirmed.

If the query fails, report the error and suggest:

- Verify the project key is correct
- Check that the MCP server `user-mcp-jira` is configured and authenticated
- Confirm the Jira user has access to the project

### Step 4: Create Artifact Workspace

Create the artifact directory for this triage run:

```bash
mkdir -p .artifacts/triage/{PROJECT}
```

### Step 5: Confirm Parameters

Present the resolved parameters back to the user:

```text
Triage parameters:
  Project:           EDM
  Jira access:       Confirmed
  Unresolved bugs:   ~87 (estimate from validation query)
  Artifacts:         .artifacts/triage/EDM/
```

## Output

- Validated project key and Jira access
- Artifact directory created
- Estimated issue count

## On Completion

Present the validated parameters and estimated issue count to the user, then recommend next steps:

**Recommended:** `/scan` — fetch all unresolved bugs from the confirmed project.

**Alternatives:**
- `/run` — execute the full workflow end-to-end without pausing
- Stop here if you only needed to verify Jira access
