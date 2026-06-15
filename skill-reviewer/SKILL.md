---
name: skill-reviewer
version: 0.2.0
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

1. Read every file in the target skill directory: `SKILL.md`, `skills/*.md`, `commands/*.md`, `guidelines.md`, `README.md`. If the directory doesn't exist or has no skill files, report the error and stop. Note any missing files — gaps are themselves a finding.
2. Run automated pre-review checks: `python3 {skill-reviewer-dir}/scripts/pre-review-checks.py {target-dir}` — captures structural, frontmatter, reference, sequencing, and content-quality issues deterministically. Treat `FAIL` results as pre-validated findings; apply judgment to `WARN` results. If the script is not present, skip and check manually.
3. Evaluate against 8 dimensions (use automated check results as pre-validated evidence where available):
   - **Orchestration & Routing** — correct routing, no orphaned/dangling references, executable Quick Start
   - **Step Sequencing** — sequential numbering, correct cross-references, logical order
   - **Schema Consistency** — matching field names/types across files, schema visible before first use
   - **Cognitive Load** — flag skills with >10 steps, synthesis after heavy processing, missing batching
   - **Instruction Clarity** — unambiguous, first-try-correct, clear when-to-use vs when-to-skip
   - **Documentation & Project Alignment** — README matches implementation, consistent with sibling skills and project conventions
   - **Command Naming** — consistent pattern (verbs vs nouns), self-explanatory
   - **Error Handling** — failure modes documented, escalation paths clear
4. Classify each finding by severity — **CRITICAL** / **HIGH** (blockers) or **MEDIUM** / **LOW** (suggestions).
5. Validate findings: verify each finding cites a specific file, includes a concrete suggestion, and that blocker/suggestion counts are accurate. Drop any finding you cannot substantiate from the files you read.
6. Produce a structured report and write it to `.artifacts/skill-reviewer/{skill-name}/review.md`:

```text
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

## File Layout

```text
skill-reviewer/
  SKILL.md              # This file — workflow overview and routing
  guidelines.md         # Principles, hard limits, safety, quality standards
  README.md             # User-facing documentation
  commands/
    review.md           # /review command — loads guidelines + skill
  prompts/
    analyze-skill.md    # Prompt template for Explore sub-agent (large skill reading)
  skills/
    review.md           # The review skill (detailed steps and output format)
  scripts/
    pre-review-checks.py  # Automated structural/reference/sequencing/content-quality checks
```
