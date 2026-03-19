---
name: assess
description: Understand the bug report and propose a plan before taking action.
---

# Assess Bug Report Skill

You are reviewing a bug report to build a shared understanding with the user
before any work begins. This is the first phase of the bugfix workflow. Your
job is to read, think, and explain — not to start fixing anything.

## Your Role

Read the bug report (issue, description, conversation context, attachments) and present
your understanding back to the user. Identify gaps. Propose a plan. Let the
user correct you before you invest effort in the wrong direction.

## Critical Rules

- **Do not start reproducing, diagnosing, or fixing.** This phase is analysis
  and planning only.
- **Do not run the project's code or tests.** You may clone and read code, but
  do not execute it yet.
- **Be honest about uncertainty.** If the report is vague, say so.

## Process

### Step 1: Gather the Bug Report

Collect all available information about the bug:

- If the user provided a GitHub issue URL, fetch it:

```bash
gh issue view NUMBER --repo OWNER/REPO --json title,body,labels,comments,state
```

- If the user described the bug in conversation, use that context
- Check if any prior artifacts exist (from a previous session, attached files or phase) and use them to inform your understanding

### Step 2: Ensure the Repository Is Available

If the project repo is already the current workspace (e.g., opened in Cursor or
the IDE), skip this step — you're already in it.

Otherwise (sandboxed environments, CI pipelines), check if the repo is accessible:

```bash
ls /workspace/repos/ 2>/dev/null
```

- If present (e.g., mounted via `add_dirs`), note its path
- If not, clone it:

```bash
gh repo clone OWNER/REPO /workspace/repos/REPO
```

- If the issue references specific PRs, files, or code paths, read them now
  to inform your assessment

This is read-only exploration — understand the code, don't change it.

### Step 3: Summarize Your Understanding

Present a clear, concise summary to the user covering:

- **What the bug is:** One or two sentences describing the problem as you
  understand it
- **Where it occurs:** Which component, service, or area of the codebase is
  affected (if identifiable)
- **Who reported it and when:** Context about the report (issue number,
  reporter, date, labels)
- **Severity/impact:** Your assessment of how serious this is, based on the
  information available

### Step 4: Identify What You Know vs. What's Missing

Be explicit about gaps:

- **Available information:** What the report tells you (steps to reproduce,
  error messages, environment details, screenshots, logs)
- **Missing information:** What you'd need to know but don't have (e.g., "The
  report doesn't mention which version this occurs on" or "No error message
  was provided")
- **Assumptions:** Any assumptions you're making — call them out so the user
  can confirm or correct them

### Step 5: Propose a Reproduction Plan

Based on your understanding, outline how you would approach reproduction:

- What environment or setup is needed
- What specific steps you would follow
- What you would look for to confirm the bug exists
- Any tools, test data, or access you'll need

If the bug seems straightforward, the plan can be brief. If it's complex or
ambiguous, be thorough.

### Step 6: Present to the User

Deliver your assessment in this structure:

```markdown
## Bug Assessment

**Issue:** [title or one-line summary]
**Source:** [issue URL, conversation, etc.]

### Understanding
[Your 2-3 sentence summary of the bug]

### Available Information
- [What you know]

### Gaps
- [What's missing or unclear]

### Assumptions
- [Any assumptions you're making]

### Proposed Reproduction Plan
1. [Step one]
2. [Step two]
3. ...

### Questions
- [Anything you'd like the user to clarify before proceeding]
```

Be direct. If the bug report is clear and complete, say so. If it's vague or
missing critical details, say that too.

## Output

- Assessment presented directly to the user (inline, not a file artifact)
- The project repository cloned and available for subsequent phases
- No code is executed, no files in the project are modified

## When This Phase Is Done

Report your assessment:

- Your understanding of the bug
- Key gaps or risks identified
- Your proposed plan

Then **re-read the controller** (`skills/controller.md`) for next-step guidance.
