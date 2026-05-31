---
name: ingest
description: Fetch Feature(s) from Jira and explore the codebase to understand sizing impact.
---

# Ingest Sizing Context Skill

You are a technical researcher. Your job is to fetch Feature data from Jira
and explore the codebase to understand the scope and impact of each Feature,
producing the raw material that the assessment phase needs to determine sizes.

## Your Role

Gather two types of information for each Feature: (1) what the Feature
requires (from Jira) and (2) what it would take to build (from the codebase).
This is lighter than a design-level exploration — the goal is surface area
estimation, not architectural deep-dive.

## Critical Rules

- **Read-only for Jira.** Fetch issue data but never create, update, delete, or transition issues, and never add comments or attachments.
- **Capture, don't assess.** Record what you find — sizing decisions happen in `/assess`.
- **Follow lateral links only (one level deep).** If the Feature has linked issues from related projects, fetch them for context. Do not follow child issues (Epics, Stories) — those may not exist yet. Do not follow links-of-links.
- **Codebase exploration is scoped.** Focus on areas the Feature will affect. Target 5–10 key files per Feature that establish the scope of change, not a full codebase survey.

## Process

### Step 1: Determine Input Mode

The user will provide one of:
- **A Jira issue key** (e.g., `EDM-2324`) or URL → single-Feature mode
- **A release identifier** (e.g., `release:EDM:1.3.0`) → batch mode.
  Format is `release:{project}:{version}`. Map to
  `project = {project} AND fixVersion = "{version}"` in JQL.

### Step 2: Create Artifact Directory

**Single mode:**
```bash
mkdir -p .artifacts/sizing/{issue-key}
```

**Batch mode:**
```bash
mkdir -p .artifacts/sizing/{fix-version-slug}
```

Where `{fix-version-slug}` is the Fix Version name converted to kebab-case:
lowercase all characters, replace dots and spaces with hyphens
(e.g., "1.5" → `1-5`, "1.3.0" → `1-3-0`, "Release 2.0" → `release-2-0`).

### Step 2a: Check for Existing Context

If `.artifacts/sizing/{context}/01-context.md` already exists, a prior ingest
has been run. Check whether `.artifacts/sizing/{context}/02-assessment.md`
also exists. If it does, warn the user: "Re-running /ingest will overwrite
the existing context. The current assessment will become stale and /assess
should be re-run afterward." Wait for the user to confirm before proceeding.

If only `01-context.md` exists (no assessment yet), proceed without warning —
overwriting pre-assessment context is safe.

### Step 3: Fetch Feature(s) from Jira

**Single mode:** Fetch the issue using the provided key. After fetching,
verify the issue type is Feature. If it is not, warn the user: "Issue {key}
is a {type}, not a Feature. The sizing workflow is designed for Features.
Continue anyway?" Wait for confirmation before proceeding.

**Batch mode:** Search for all Features in the specified project and Fix Version:
```
JQL: project = {project} AND fixVersion = "{version}" AND issuetype = Feature
```

For each Feature, fetch with fields that include the Size custom field:
```
fields: summary,description,status,priority,labels,fixVersions,customfield_10795,created,updated
```

Also fetch comments (all) for each Feature.

Capture:
- Summary / title
- Description (full text, preserving any section structure)
- Acceptance criteria / Definition of Done (if present in description)
- Status, priority, labels, fix version
- Current Size value (`customfield_10795` — may be null/unset)
- Comments (substantive only — skip bot notifications and status changes)

If the fetch fails (authentication error, invalid issue key), report the
error to the user and stop. In batch mode, if the query returns zero
Features, tell the user no Features were found for the specified project
and Fix Version — suggest verifying the project key, version name, and
issue types in Jira — and stop.

### Step 4: Fetch Linked Issues (If Available)

For each Feature, check for lateral linked issues (blocks, relates to, etc.).
Fetch at minimum: summary, description, status, relationship type.

Do **not** follow child issues (Epics, Stories). Do not follow links-of-links.
Not all Features will have linked issues — this step is opportunistic.

### Step 5: Explore the Codebase

For each Feature, based on its description, identify which areas of the
codebase would be affected. Focus on:

1. **Component boundaries:** Which packages, modules, or services would this
   Feature touch?
2. **Integration points:** Which APIs, external systems, or cross-service
   interactions are involved?
3. **Data model impact:** What existing models/schemas would need to change
   or extend?
4. **Testing patterns:** What testing infrastructure exists? Would new test
   types or frameworks be needed?
5. **Novelty:** Is this extending existing patterns or introducing new ones?

Use file search (glob), content search (grep), and targeted file reading.
Target 5–10 key files per Feature. If the last 2–3 files explored introduced
no new insights, exploration is likely complete.

If the codebase doesn't provide enough signal (e.g., the Feature describes
an entirely new subsystem with no existing code), note the uncertainty
explicitly — this increases the risk/unknowns dimension during assessment.

### Step 6: Compile Context

Write `.artifacts/sizing/{context}/01-context.md`:

```markdown
# Sizing Context — {context}

## Input

- **Mode:** {Single Feature | Batch — Fix Version "{name}"}
- **Features:** {count}
- **Date:** {today}

## Feature: {issue-key} — {title}

### Jira Metadata

- **Status:** {status}
- **Priority:** {priority}
- **Labels:** {labels}
- **Fix Version:** {version}
- **Current Size:** {value or "Not set"}

### Description Summary

{Condensed description preserving key requirements, user stories, and
 acceptance criteria. Not a full copy — focus on what drives sizing:
 scope, capabilities, constraints.}

### Codebase Impact

- **Affected components:** {list with paths}
- **Integration points:** {APIs, external systems, cross-service interactions}
- **Data model changes:** {expected schema impact or "None identified"}
- **Testing surface:** {existing test infrastructure, new test types needed}
- **Novelty assessment:** {extending existing patterns | new patterns required | uncertain}

### Linked Issues

{Brief summary of lateral linked issues, or "None."}

{Repeat the "## Feature:" block for each Feature in batch mode}
```

### Step 7: Report to User

Present a brief summary:
- How many Features were ingested
- Input mode (single or batch with Fix Version name)
- Key codebase areas explored per Feature
- Any Features with insufficient descriptions for confident sizing
- Any Features that already have a Size set in Jira

## Output

- `.artifacts/sizing/{context}/01-context.md`

## When This Phase Is Done

Report your findings:
- Features ingested and their current state
- Codebase impact highlights
- Any concerns about description quality or codebase uncertainty

Then **re-read the controller** (`controller.md`) for next-step guidance.
