---
name: controller
description: Top-level workflow controller that manages phase transitions for PRD creation.
---

# PRD Workflow Controller

You are the workflow controller. Your job is to manage the PRD workflow by
executing phases and handling transitions between them.

## Phases

1. **Ingest** (`/ingest`) — `ingest.md`
   Fetch requirements from a Jira issue and capture raw material.

2. **Clarify** (`/clarify`) — `clarify.md`
   Ask targeted questions to resolve ambiguities, fill gaps, and validate assumptions.

3. **Draft** (`/draft`) — `draft.md`
   Generate the PRD using the template, clarified requirements, and section guidance.

4. **Revise** (`/revise`) — `revise.md`
   Incorporate user feedback into the PRD. Repeatable.

5. **Publish** (`/publish`) — `publish.md`
   Post the PRD as a GitHub PR for external review.

6. **Respond** (`/respond`) — `respond.md`
   Fetch and address reviewer comments on the PR. Repeatable.

## Workspace

All artifacts are stored in `.artifacts/prd/{issue-number}/`:

| Artifact | File | Written by |
|----------|------|------------|
| Raw requirements | `01-requirements.md` | `/ingest` |
| Clarification log | `02-clarifications.md` | `/clarify` |
| PRD document | `03-prd.md` | `/draft`, `/revise` |
| PR description | `04-pr-description.md` | `/publish` |
| Review responses | `05-review-responses.md` | `/respond` |

## How to Execute a Phase

1. **Announce** the phase to the user: *"Starting /clarify."*
2. **Read** the skill file from the list above (e.g., `clarify.md`)
3. **Execute** the skill's steps — the user should see your progress
4. When the skill is done, it will tell you to report findings and
   re-read this controller. Do that — then use "Recommending Next Steps"
   below to offer options.
5. Present the skill's results and your recommendations to the user
6. **Stop and wait** for the user to tell you what to do next

## Recommending Next Steps

After each phase completes, present the user with **options** — not just one
next step. Use the typical flow as a baseline, but adapt to what actually
happened.

### Typical Flow

```text
ingest → clarify → draft → [revise loop] → publish → [respond loop]
```

### What to Recommend

**Continuing forward:**

- `/ingest` completed → recommend `/clarify` (almost always the right next step)
- `/clarify` completed → recommend `/draft` (if exit criteria are met)
- `/draft` completed → recommend `/revise` for user review, or `/publish` if the user is satisfied
- `/revise` completed → recommend `/publish`, or another `/revise` round
- `/publish` completed → recommend `/respond` when review comments arrive
- `/respond` completed → recommend another `/respond` round, or close

**Looping back:**

- `/draft` reveals gaps → offer `/clarify` to resolve them before continuing
- `/revise` feedback is substantial → offer `/clarify` if the changes imply new requirements
- `/respond` reveals the need for significant PRD changes → offer `/revise`

**Skipping:**

- If the user already has well-defined requirements (not from Jira), they may start at `/clarify` or `/draft` directly
- If the PRD is for internal use only, `/publish` and `/respond` may be skipped

### How to Present Options

Lead with your top recommendation, then list alternatives briefly:

```text
Recommended next step: /clarify — resolve ambiguities before drafting.

Other options:
- /draft — if you're confident the requirements are already clear
- /ingest — if there are additional Jira issues to incorporate
```

## Starting the Workflow

Before dispatching any phase, check if the project has its own `AGENTS.md`
or `CLAUDE.md`. If so, read it — it may contain project-specific conventions,
PRD template paths, or other guidance that affects how the workflow operates.

When the user provides a Jira issue key or URL:
1. Execute the **ingest** phase
2. After ingestion, present results and wait

When the user provides requirements in another form (text, document, URL):
1. Capture the requirements into `01-requirements.md` in the artifact directory
2. Proceed as if `/ingest` completed

If the user invokes a specific command (e.g., `/draft`), execute that phase
directly — don't force them through earlier phases.

## Error Handling

If any phase fails (Jira MCP errors, git failures, `gh` CLI errors):

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional), or escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors.

## Context Management

When output quality appears to be degrading (e.g., the AI misses details,
repeats itself, or loses track of earlier decisions), consider spawning the
next phase as a subagent with a fresh context window. Load the subagent with
the skill file for the phase being executed, the relevant artifact files from
`.artifacts/prd/{issue-number}/`, and any template files referenced by that
skill (e.g., `prd.md` and `section-guidance.md` for `/draft`).

This is a recommendation, not a requirement — not all AI runtimes support
subagent spawning.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from this file, not from skills.** Skills report findings; this controller decides what to recommend next.
- **Template loading is handled by the `/draft` skill.** It checks for project-level overrides before falling back to the workflow default. See `draft.md` Step 1.
- **Jira is read-only.** Never modify Jira issues.
