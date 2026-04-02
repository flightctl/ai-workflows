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

- **Read-only.** Never modify Jira issues. Use only read tools: `get_issue`, `search_issues`, `get_epic_children`. Do not use `update_issue`, `create_issue`, `delete_issue`, `transition_issue`, `add_comment`, or `add_attachment`.
- **Capture, don't interpret.** Record what the source says, not what you think it means.
- **Follow links.** If the issue links to parent epics, child stories, or related issues, fetch those too.

## Process

### Step 1: Identify the Jira Issue

The user will provide one of:
- A Jira issue key (e.g., `EDM-2324`)
- A Jira issue URL (e.g., `https://issues.redhat.com/browse/EDM-2324`)

Extract the issue key and set it as the context identifier for the
artifact directory.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/prd/{issue-number}
```

### Step 3: Fetch the Primary Issue

Use the Jira MCP `get_issue` tool to fetch the issue. Capture:
- Summary / title
- Description (full text)
- Acceptance criteria (if present as a field or within the description)
- Status, priority, labels, fix version
- Comments (all)
- Attachments (note their names and descriptions)

If the Jira MCP call fails (authentication error, invalid issue key, network
error), report the error to the user and stop. Do not fabricate issue content.

### Step 4: Fetch Linked Issues

Check for linked issues (blocks, is blocked by, relates to, parent, subtasks).
For each linked issue, fetch at minimum:
- Summary
- Description
- Status
- Relationship type

If the issue is a subtask, fetch the parent epic or story for broader context.
If the issue has subtasks, fetch them to understand the full scope.

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

{Full description text, preserved as-is}

## Acceptance Criteria

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
