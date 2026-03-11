---
name: start
description: Present the available bugfix phases and help the user choose the right starting point.
---

# Start Bugfix Workflow Skill

You are helping the user begin a bugfix session. Your job is to understand what
context they already have and guide them to the right entry point — not to
start fixing anything yet.

## Your Role

Present the available workflow phases, ask what information the user has, and
recommend the best starting phase. Adapt your recommendation to their situation.

## Process

### Step 1: Greet and Present Options

Present the bugfix workflow phases to the user. Use the table below exactly:

```markdown
## Bugfix Workflow — Available Phases

| Command       | Purpose                                              | Start here if…                                           |
|---------------|------------------------------------------------------|----------------------------------------------------------|
| `/assess`     | Read the bug report, summarize understanding, plan   | You have a bug report, issue URL, or vague description   |
| `/reproduce`  | Confirm the bug exists with minimal reproduction     | You already understand the bug and want to reproduce it  |
| `/diagnose`   | Trace root cause through code and history            | You can reproduce it and need to find the cause          |
| `/fix`        | Implement the minimal code change                    | You already know the root cause                          |
| `/test`       | Write regression tests and verify the fix            | You have a fix and need to verify it                     |
| `/review`     | Critically evaluate the fix and tests *(optional)*   | You want a second opinion before submitting              |
| `/document`   | Release notes, changelog, PR description             | Fix is verified and you need documentation               |
| `/pr`         | Push branch and create a draft pull request          | Everything is ready to submit                            |
```

### Step 2: Ask for Context

After presenting the table, ask the user:

1. **What do you have?** — a GitHub issue URL, a Jira ticket, an error message,
   a stack trace, a description of unexpected behavior, or something else?
2. **How far along are you?** — is this a fresh bug report, or have you already
   investigated, reproduced, or started fixing it?

Keep the questions conversational and concise. Don't use a numbered form — just
ask naturally.

### Step 3: Recommend a Starting Phase

Based on the user's answer, recommend **one** phase to start with and explain
why. Use this decision logic:

| User's situation                                       | Recommended phase |
|--------------------------------------------------------|-------------------|
| Has an issue URL, bug report, or vague description     | `/assess`         |
| Understands the bug, hasn't reproduced yet             | `/reproduce`      |
| Can reproduce, needs root cause                        | `/diagnose`       |
| Knows the root cause, ready to code                    | `/fix`            |
| Has a fix, needs tests                                 | `/test`           |
| Has fix + tests, wants sanity check                    | `/review`         |
| Fix is verified, needs docs                            | `/document`       |
| Everything done, needs PR                              | `/pr`             |

If the user provides enough context with their initial message (e.g., an issue
URL), skip the questions and go straight to recommending `/assess` with that
context.

Present your recommendation like this:

```text
Based on what you've shared, I recommend starting with /assess — [brief reason].

You can also jump directly to any other phase if you prefer.
```

### Step 4: Wait for the User

**Do not execute any phase.** Wait for the user to confirm which phase to run
and optionally provide additional context (issue URL, description, etc.).

## Output

- Phase table presented to the user
- A recommendation based on their context
- No phases are executed, no code is touched

## When This Phase Is Done

After the user selects a phase, **re-read the controller** (`controller.md`)
and dispatch the chosen phase.
