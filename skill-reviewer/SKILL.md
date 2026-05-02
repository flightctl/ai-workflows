---
name: skill-reviewer
description: >-
  Deep review of an AI skill directory. Critically evaluates structure, clarity,
  completeness, and consistency of SKILL.md, skills/*.md, commands/*.md, and
  guidelines.md. Use when reviewing, auditing, or validating an AI workflow skill.
  Activated by commands: /review.
---
# Skill Reviewer Workflow Orchestrator

## Quick Start

1. If the user invoked `/review`, read `commands/review.md` and follow it.
2. Otherwise, if no skill directory was specified, ask the user which directory to review (e.g. `bugfix/`, `docs-writer/`). Then read `skills/review.md` to execute the review.

If a step fails or produces unexpected output, stop and report the error to the
user. Do not advance to the next phase. Offer to retry the failed step or
escalate.

For principles, hard limits, safety, quality, and escalation rules, see `guidelines.md`.
