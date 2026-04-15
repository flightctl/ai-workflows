---
name: handoff
description: Compose a handoff message for the support engineer with the KCS draft.
---

# Handoff to Support Engineer

You are preparing the KCS Solution draft for handoff to the support engineer
who will publish it on the customer portal.

## Your Role

Compose a concise, professional message that the user can send to the support
engineer via Slack, email, or another channel. The message should include
everything the engineer needs to create the article on the portal.

## Process

### Step 1: Get Contact Details

Ask the user for the support engineer's contact information:

- **Name** of the support engineer responsible for the product
- **Contact method** — Slack handle, email address, or other preferred channel

If the user already provided this information during the session, skip the
question and use what was given.

### Step 2: Load the Draft

Read the validated draft: `.artifacts/kcs/{issue-key}/02-kcs-draft.md`

If the draft has not been validated (no `/validate` was run), warn the user
and recommend running `/validate` first. Proceed only if the user explicitly
chooses to skip validation.

### Step 3: Compose the Message

Write a message that includes:

1. **Greeting** — Address the support engineer by name.
2. **Purpose** — A brief explanation of what the attachment is: a KCS Solution
   draft for a specific bug.
3. **Bug summary** — One sentence describing the issue (from the article Title
   or Issue section).
4. **Jira reference** — The issue key and link.
5. **KCS compliance note** — State that the draft follows the KCS Solutions
   Content Standard.
6. **Ask** — Request the engineer to create the article on the Red Hat Customer
   Portal and share the published link back.

Keep the message concise — 5-8 sentences. The draft file itself contains all
the detail.

### Step 4: Save the Handoff Artifact

Save the message to `.artifacts/kcs/{issue-key}/03-handoff-message.md`.

Use this structure:

```markdown
# Handoff Message — {ISSUE_KEY}

## Recipient

- **Name:** {engineer name}
- **Contact:** {Slack / email / etc.}

## Message

{The composed message text, ready to copy-paste.}

## Attachments

- KCS draft: `.artifacts/kcs/{issue-key}/02-kcs-draft.md`
```

### Step 5: Present to User

Show the composed message to the user for review before they send it.
Offer to adjust the tone, add details, or change the recipient.
