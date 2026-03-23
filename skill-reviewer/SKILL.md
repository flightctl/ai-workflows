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

Run `/review` to execute the full workflow. The user must specify which skill directory to review (e.g. `bugfix/`, `docs-writer/`). Executable without opening other files:

1. Read every file in the target skill directory: `SKILL.md`, `skills/*.md`, `commands/*.md`, `guidelines.md`, `README.md`. If the directory doesn't exist or has no skill files, report the error and stop. Note any missing files — gaps are themselves a finding.
2. Evaluate against 8 dimensions:
   - **Orchestration & Routing** — correct routing, no orphaned/dangling references, executable Quick Start
   - **Step Sequencing** — sequential numbering, correct cross-references, logical order
   - **Schema Consistency** — matching field names/types across files, schema visible before first use
   - **Cognitive Load** — flag skills with >10 steps, synthesis after heavy processing, missing batching
   - **Instruction Clarity** — unambiguous, first-try-correct, clear when-to-use vs when-to-skip
   - **Documentation Alignment** — README matches implementation, no undocumented features
   - **Command Naming** — consistent pattern (verbs vs nouns), self-explanatory
   - **Error Handling** — failure modes documented, escalation paths clear
3. Classify each finding by severity — **CRITICAL** / **HIGH** (blockers) or **MEDIUM** / **LOW** (suggestions).
4. Produce a structured report and write it to `.artifacts/skill-reviewer/{skill-name}/review.md`:

```
## Skill Review: {skill-name}

[2-3 sentence overall assessment]

### Strengths
- [What's well-done]

### Findings

| # | Severity | File | Finding | Suggestion |
|---|----------|------|---------|------------|
| 1 | HIGH | skills/scan.md | ... | ... |

### Summary

- **Blockers**: {count}
- **Suggestions**: {count}
- **Verdict**: [one-line summary]
```

## Example Session

```text
User: "Review the bugfix skill"

/review  → reads all files in bugfix/
         → evaluates 8 review dimensions
         → produces findings table with severities
         → writes .artifacts/skill-reviewer/{skill-name}/review.md
```

## Phases

1. **Review** (`/review`) — Read all files in a skill directory, evaluate against 8 dimensions, produce a structured findings report

## File Layout

```text
skill-reviewer/
  SKILL.md              # This file — workflow overview and routing
  guidelines.md         # Principles, hard limits, safety, quality standards
  README.md             # User-facing documentation
  commands/
    review.md           # /review command — loads guidelines + skill
  skills/
    review.md           # The review skill (detailed steps and output format)
```
