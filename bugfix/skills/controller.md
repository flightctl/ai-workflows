---
name: controller
description: Top-level workflow controller that manages phase transitions.
---

# Bugfix Workflow Controller

You are the workflow controller. Your job is to manage the bugfix workflow by
executing phases and handling transitions between them.

## Phases

0. **Start** (`/start`) — `start.md`
   Present available phases, gather context, and help the user choose where to begin.

1. **Assess** (`/assess`) — `assess.md`
   Analytical bug assessment: error signature, recommendation, source-code exploration, duplicate/regression search. Writes `.artifacts/bugfix/{issue}/assessment.md`.

2. **Reproduce** (`/reproduce`) — `reproduce.md`
   Confirm the bug exists by reproducing it in a controlled environment.

3. **Diagnose** (`/diagnose`) — `diagnose.md`
   Trace the root cause through code analysis, git history, and hypothesis testing.

4. **Fix** (`/fix`) — `fix.md`
   Implement the minimal code change that resolves the root cause.

5. **Test** (`/test`) — `test.md`
   Write regression tests, run the full suite, and verify the fix holds.

6. **Review** (`/review`) — `review.md`
   Critically evaluate the fix and tests — look for gaps, regressions, and missed edge cases.

7. **Document** (`/document`) — `document.md`
   Create release notes, changelog entries, and team communications.

8. **PR** (`/pr`) — `pr.md`
   Push the branch to a fork and create a draft pull request.

9. **Feedback** (`/feedback`) — `feedback.md`
   Full review-feedback cycle: fetch comments, propose responses for user
   approval, implement approved changes, validate, commit, push, and post
   review replies. Clarification-only rounds skip to reply posting. Repeatable.

Phases can be skipped or reordered at the user's discretion.

## How to Execute a Phase

1. **Announce** the phase to the user before doing anything else, e.g., "Starting the /fix phase."
   This is very important so the user knows that the workflow is working and learns about the commands.
2. **Locate** the skill file — read and follow
   `../../_shared/recipes/phase-override-resolution.md` with
   WORKFLOW=`bugfix`, PHASE_FILE=`{phase}.md`.
3. **Read** the resolved skill file
4. **Execute** the skill's steps directly — the user should see your progress
5. When the skill returns control for completion guidance, read `completion.md`
   and follow the guidance for the completed phase. If a legacy project
   override instead tells you to re-read this controller, treat that as the
   same return and read `completion.md`.
6. **Stop and wait** for the user to tell you what to do next.

## Starting the Workflow

When the user runs `/start` or asks to begin without providing specific context:

1. Execute the **start** phase to present options and gather context
2. After the user selects a phase, dispatch it

When the user provides a bug report, issue URL, or description directly:

1. Execute the **assess** phase
2. After assessment, present results and wait

If the user invokes a specific command (e.g., `/fix`), execute that phase
directly — don't force them through earlier phases.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from `completion.md`.** Phase skills report findings;
  the completion guide provides the authoritative next-step model.
