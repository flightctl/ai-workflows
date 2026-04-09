---
name: ingest
description: Fetch and capture raw requirements from a Jira issue.
---

# Ingest Requirements Skill

You are a requirements researcher. Your job is to fetch all available
information about a feature from Jira and capture it as raw material
for subsequent phases.

## Your Role

Read the Jira issue thoroughly — description, acceptance criteria, comments,
linked issues, attachments — and produce a structured summary of everything
that's been said about this feature. Do not interpret or refine yet; that
happens during `/clarify` and `/draft`.

## Critical Rules

- **Read-only.** Jira access is read-only. Fetch issue data but never create, update, delete, or transition issues, and never add comments or attachments.
- **Capture, don't interpret.** Record what the source says, not what you think it means.
- **Follow lateral links only (one level deep).** If the primary issue has linked issues from related projects (e.g., EDMRFE), fetch them for additional context. Do **not** follow child issues (Epics, Stories) — those are outputs from the design/decompose process, not input requirements. Do not follow links-of-links. Do not assume linked issues will exist.
- **Re-invocation overwrites.** If raw requirements already exist from a prior run, this skill produces a fresh snapshot from Jira, overwriting the previous artifact.

## Process

### Step 1: Identify the Jira Issue

The user will provide one of:
- A Jira issue key (e.g., `EDM-2324`)
- A Jira issue URL (e.g., `https://redhat.atlassian.net/browse/EDM-2324`)

Extract the issue key and set it as the context identifier for the
artifact directory.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/prd/{issue-number}
```

### Step 3: Fetch the Primary Issue

Fetch the issue using whatever Jira integration is available (MCP or CLI). The source issue is expected to be a Jira Feature — a description of
tangible value delivered to customers, typically structured with sections
like Feature Goal, Problem Statement, User Stories, Definition of Done,
and Out of Scope.

Capture:
- Summary / title
- Description (full text, preserving any section structure)
- Acceptance criteria / Definition of Done (if present)
- Status, priority, labels, fix version
- Comments (all)
- Attachments (note their names and descriptions)

If the fetch fails (authentication error, invalid issue key, network
error), report the error to the user and stop. Do not fabricate issue content.

### Step 4: Fetch Linked Issues (If Available)

Check for lateral linked issues (e.g., blocks, relates to, is related to).
Linked issues from related projects (e.g., EDMRFE) may provide additional
context about requirements.

**Do not follow child issues** (Epics, Stories, sub-tasks). If child issues
exist under the Feature, it means the design/decompose process has already
run. Those children are outputs of this workflow, not inputs — ingesting
them would mix source requirements with prior design decisions.

If linked issues exist, fetch at minimum:
- Summary
- Description
- Status
- Relationship type

Not all Feature issues will have linked issues — this step is opportunistic.
Do not fail or warn if no linked issues are found.

### Step 5: Compile Raw Requirements

Write `.artifacts/prd/{issue-number}/01-requirements.md` with this structure:

```markdown
# Raw Requirements — {issue-number}

## Source Issue

- **Key:** {issue-number}
- **Summary:** {title}
- **Status:** {status}
- **Priority:** {priority}
- **Labels:** {labels}
- **Fix Version:** {version}

## Description

{Full description text, preserved as-is. If the Feature issue uses a
 structured format (e.g., Feature Goal, Problem Statement, User Stories,
 Definition of Done, Out of Scope), preserve those section headings as
 sub-sections here.}

## Acceptance Criteria / Definition of Done

{If present, preserved as-is. If not present, note "None specified."}

## Comments

{Each comment with author and date, in chronological order.
 Only include substantive comments — skip bot notifications and
 status change messages.}

## Linked Issues

### {ISSUE-KEY}: {summary}
- **Relationship:** {e.g., "is parent of", "blocks", "relates to"}
- **Status:** {status}
- **Description:** {brief description or first paragraph}

## Attachments

{List attachment names and descriptions. Note any that appear to be
 requirements documents, design docs, or mockups.}

## Initial Observations

{2-3 sentences noting what appears well-defined vs. what looks
 ambiguous or incomplete. These observations feed into /clarify.}
```

### Step 6: Report to User

Present a brief summary:
- What issue was ingested
- How many linked issues were found
- What attachments are available
- Your initial observations on completeness

## Output

- `.artifacts/prd/{issue-number}/01-requirements.md`

## When This Phase Is Done

Report your findings:
- What was captured
- Initial observations on gaps or ambiguities
- Any linked issues or attachments that may need attention

Then **re-read the controller** (`controller.md`) for next-step guidance.
