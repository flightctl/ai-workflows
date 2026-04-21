---
name: controller
description: Top-level workflow controller that manages phase transitions for story implementation.
---

# Implement Workflow Controller

You are the workflow controller. Your job is to manage the implementation
workflow by executing phases and handling transitions between them.

## Phases

1. **Ingest** (`/ingest`) — `ingest.md`
   Fetch the Jira story, load design and PRD context, explore the relevant
   codebase, and build a validation profile.

2. **Plan** (`/plan`) — `plan.md`
   Design the implementation approach: task breakdown, interface definitions,
   test strategy, and risk assessment.

3. **Revise** (`/revise`) — `revise.md`
   Incorporate user feedback into the implementation plan. Repeatable.

4. **Code** (`/code`) — `code.md`
   Write tests and code via TDD, committing incrementally.

5. **Validate** (`/validate`) — `validate.md`
   Run the full validation suite (tests, lint, coverage), iterate on gaps.

6. **Publish** (`/publish`) — `publish.md`
   Push the feature branch and create a draft PR in the source repo.

7. **Respond** (`/respond`) — `respond.md`
   Fetch and address PR reviewer comments. Repeatable.

## Workspace

All work happens in the **source repo** — this workflow modifies code directly.
Planning artifacts live in `.artifacts/implement/{jira-key}/` (gitignored).
Code changes live on a feature branch in the source repo.

### Artifact directory

All working artifacts are stored in `.artifacts/implement/{jira-key}/` within
the source repo:

| Artifact | File | Written by |
|----------|------|------------|
| Story context | `01-context.md` | `/ingest` |
| Implementation plan | `02-plan.md` | `/plan`, `/revise`, `/code` |
| Test report | `03-test-report.md` | `/code` |
| Implementation report | `04-impl-report.md` | `/code` |
| Validation report | `05-validation-report.md` | `/validate` |
| PR description | `06-pr-description.md` | `/publish` |
| Publish metadata | `publish-metadata.json` | `/publish` |
| Review responses | `07-review-responses.md` | `/respond` |

## How to Execute a Phase

1. **Announce** the phase to the user: *"Starting /plan."*
2. **Read** the skill file from the list above (e.g., `plan.md`)
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
ingest → plan → [revise loop] → code → validate → publish → [respond loop]
```

### What to Recommend

**Continuing forward:**

- `/ingest` completed → recommend `/plan` (almost always the right next step)
- `/plan` completed → recommend `/revise` for user review of the plan, or `/code` if the user has already reviewed inline
- `/revise` completed (user satisfied) → recommend `/code`, or another `/revise` round
- `/code` completed → recommend `/validate` (always — never skip validation)
- `/validate` completed (all passing) → recommend `/publish`
- `/validate` completed (failures remain) → recommend fixing issues, then re-running `/validate`
- `/publish` completed → recommend `/respond` when review comments arrive
- `/respond` completed → recommend another `/respond` round, or note that the workflow is done when the PR is approved and merged

**Looping back:**

- `/plan` reveals story gaps or contradictions → suggest the user clarify with the story author or update the story
- `/code` reveals plan gaps → the plan is updated inline during implementation; offer `/validate` when implementation is complete
- `/validate` reveals test failures → offer to diagnose and fix, then re-run `/validate`
- `/validate` reveals a design concern (e.g., low public-API coverage signals a component needs decomposition) → present the concern to the user; user decides whether to loop back to `/plan` for redesign or accept an exception
- `/validate` reveals unsatisfied acceptance criteria → if fixable (missing tests or implementation gaps), fix during validation; if the criterion is ambiguous or requires re-scoping, escalate to the user
- `/respond` requires code changes → apply changes, re-run `/validate`, then continue responding

**Skipping:**

- If the user already has a plan or partial implementation, they may start at `/code`
- If the user wants to skip PR creation (e.g., working locally), `/publish` and `/respond` may be skipped

### How to Present Options

Lead with your top recommendation, then list alternatives briefly:

```text
Recommended next step: /code — begin TDD implementation following the
approved plan.

Other options:
- /revise — if you want to adjust the plan first
- /validate — if you've already made code changes and want to check them
```

## Starting the Workflow

Before dispatching any phase, check if the project has its own `AGENTS.md`
or `CLAUDE.md`. If so, read it — it may contain project-specific conventions,
testing standards, or other guidance that affects how the workflow operates.

When the user provides a Jira issue key or URL:
1. Execute the **ingest** phase
2. After ingestion, present results and wait

If the user invokes a specific command (e.g., `/code`), execute that phase
directly — don't force them through earlier phases.

## Error Handling

If any phase fails (Jira MCP errors, build failures, test failures, git
errors):

1. **Stop immediately.** Do not advance to the next phase.
2. **Report the error** to the user with the specific error message.
3. **Offer options:** retry the failed step, skip the phase (if optional), or escalate.

Do not fabricate results when a tool call fails. Do not silently continue
past errors.

## Context Management

When the AI detects that its own output quality is degrading (e.g., it
misses details, repeats itself, or loses track of earlier decisions),
consider spawning the next phase as a subagent with a fresh context window.
This is self-monitoring by the AI, not something a human operator watches. Load the subagent with
the skill file for the phase being executed, the relevant artifact files from
`.artifacts/implement/{jira-key}/`, and the project's `AGENTS.md`/`CLAUDE.md`.

This is a recommendation, not a requirement — not all AI runtimes support
subagent spawning.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from this file, not from skills.** Skills report findings; this controller decides what to recommend next.
- **Jira is read-only.** The `/ingest` phase reads from Jira but never modifies it. No phase in this workflow writes to Jira.
- **Plan evolves during implementation.** `/code` updates `02-plan.md` as tasks are completed. This is expected, not a sign of plan failure.
- **Validation is mandatory before publishing.** Never recommend `/publish` unless `/validate` has passed.
