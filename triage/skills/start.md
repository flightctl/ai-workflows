---
name: start
description: Validate Jira access and confirm the project key.
---

# Start Triage Skill

You are onboarding the user into the triage workflow. Your goal is to validate Jira access and confirm which project to triage.

## Allowed Tools

- **Jira CLI or Jira MCP (read-only):** validate project access only; prefer the global `jira` CLI
- **Local:** `mkdir` — create artifact directory
- **Prohibited:** all Jira write tools (create, update, delete, comment, transition)

## Process

Before the validation query, verify that the selected Jira access method is
available and authenticated. For the default CLI path, check that `jira` is
installed and executable. Jira MCP may be used for interactive validation,
but the deterministic bulk scan requires the CLI or its REST fallback.
If neither is available, stop and report the missing access method.

### Step 1: Present the Workflow

Briefly explain what the triage workflow does:

- Fetches all unresolved bugs from a Jira project
- Analyzes each bug and assigns a recommendation (FIX_NOW, AUTO_FIX, BACKLOG, CLOSE, NEEDS_INFO, DUPLICATE, ESCALATE, WONT_FIX)
- Generates an interactive HTML report with stats, filters, sorting, and simulation

### Step 2: Gather Parameters

You need one parameter. If it was provided in the user's message, use it directly — don't ask again.

1. **Project key** (required) — the Jira project key, e.g. `EDM`

### Step 3: Validate Jira Access

Before expanding `{PROJECT}` in any shell command, validate it against
`^[A-Z][A-Z0-9_]+$`. If it does not match, stop and ask for a valid Jira
project key.

Verify the project is accessible using the selected read-only Jira method. With
the preferred CLI:

```bash
jira issue list -p "{PROJECT}" -t Bug -R unresolved \
  --paginate 0:1 --plain --no-headers --columns KEY,SUMMARY
```

If the CLI command succeeds and returns at least one issue, Jira access is
confirmed. A successful empty result means there are no matching bugs. Any
non-zero exit code is a Jira CLI/configuration failure.

If Jira MCP was selected, perform the equivalent read-only project/bug access
check through the configured MCP server and record that the bulk scan must use
the CLI or REST fallback.

If the query fails, report the error and suggest:

- Verify the project key is correct
- Check that the global `jira` CLI is configured and authenticated
- Confirm the Jira user has access to the project

### Step 4: Create Artifact Workspace

Create the artifact directory for this triage run:

```bash
mkdir -p ".artifacts/triage/{PROJECT}"
```

### Step 5: Confirm Parameters

Present the resolved parameters back to the user:

```text
Triage parameters:
  Project:           EDM
  Jira access:       Confirmed
  Jira access method: CLI
  Artifacts:         .artifacts/triage/EDM/
```

## Output

- Validated project key and Jira access
- Artifact directory created
- Jira access method and project key

## On Completion

Present the validated parameters to the user, then recommend next steps:

**Recommended:** `/scan` — fetch all unresolved bugs from the confirmed project.

**Alternatives:**
- `/run` — execute the full workflow end-to-end without pausing
- Stop here if you only needed to verify Jira access
