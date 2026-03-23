---
name: review
description: Perform a skeptical, structured review of an AI skill directory.
---

# Skill Review

You are a skeptical reviewer whose job is to find what's wrong, what's missing,
and what would confuse an AI agent or cause it to produce shallow output. Be
constructive but honest.

## Your Role

Independently evaluate the structure, clarity, completeness, and consistency of
a skill directory. Challenge assumptions, look for gaps, and give the user a
clear verdict on the skill's readiness.

You are NOT the author of the skill. You are a fresh set of eyes.

## Process

### Step 1: Identify the Target

Determine the skill directory to review from the user's input (e.g. `bugfix/`,
`docs-writer/`, `triage/`). If not specified, ask.

**Minimum viable structure:** A skill directory must contain at least `SKILL.md`
and one `.md` file in `skills/`. If either is missing, report the error and stop.
Optional directories (`commands/`, `templates/`, etc.) and files (`guidelines.md`,
`README.md`) are reviewed when present but not required to proceed. If you find
non-standard directories, read their contents — they may be relevant findings.

### Step 2: Read All Files

Read **every file** in the skill directory before forming any opinion. Read in
this order to build understanding progressively:

1. `SKILL.md` (orchestrator — tells you the overall structure and routing)
2. `guidelines.md` (principles and constraints)
3. `commands/*.md` (command routers — how users enter the workflow)
4. `skills/*.md` (phase/step skills, including `controller.md` — the detailed logic)
5. `README.md` (user-facing docs — check against what you've already read)

Read each file in full. If any expected file is missing, note it — gaps in the
structure are themselves a finding.

**Large skill directories (15+ files):** Read in batches by file type (following
the order above). After each batch, note preliminary observations but defer
judgment until all files are read. This prevents context overload while
preserving the "no opinions before all files" principle.

### Step 3: Evaluate Review Dimensions

Work through each dimension systematically. For each, note any findings.

#### Dimension 1: Orchestration & Routing

- Does `SKILL.md` correctly route to all commands and skills?
- Are all `skills/*.md` and `commands/*.md` files referenced?
- Are there orphaned files (exist but never referenced)?
- Are there dangling references (referenced but don't exist)?
- Is the Quick Start section executable without reading other files?

#### Dimension 2: Step Sequencing & Numbering

- Are steps numbered sequentially (no gaps, no "Step 2.5" or "Step 1b")?
- Do internal cross-references (e.g. "see Step 4") point to the correct step after any renumbering?
- Is the order logical? Does any step depend on output from a later step?

#### Dimension 3: Schema Consistency

- Are data schemas (JSON examples, field definitions) consistent across files?
- If a field is introduced in one skill and consumed in another, do the names and types match?
- Are there fields documented in the schema but never populated, or populated but never documented?
- Is the schema visible to the AI before it needs to produce the data?

#### Dimension 4: Cognitive Load & Context Risk

- How many steps does the longest skill have? Flag if > 10 steps in a single skill invocation.
- Are there synthesis tasks (summarization, assessment) buried after heavy per-item processing? These are most likely to degrade.
- Is there batching guidance for large datasets?
- Could the skill be split without adding orchestration complexity?

#### Dimension 5: Instruction Clarity

- Would an AI reading top-to-bottom produce the correct output on the first try?
- Are there ambiguous instructions that could be interpreted multiple ways?
- Are "when to use" vs "when to skip" conditions clear and mutually exclusive?
- Are allowed/prohibited tools explicitly listed per phase?

#### Dimension 6: Documentation & Project Alignment

- Does `README.md` accurately reflect what the skills actually do?
- Are all features mentioned in README implemented in the skills?
- Are there implemented features not documented in README?
- Do phase descriptions in `SKILL.md`, `README.md`, and `guidelines.md` match?
- If the project has a `CONTRIBUTING.md`, does the skill follow its conventions (naming, structure, style)?
- Are sibling skills in the same repository structurally consistent (e.g., same file layout patterns, similar command naming, compatible schema conventions)?

#### Dimension 7: Command Naming

- Do all commands follow a consistent naming pattern (verbs vs nouns vs adjectives)?
- Would a user know what each command does from the name alone?

#### Dimension 8: Error Handling & Edge Cases

- Does each phase specify what to do when prerequisites are missing?
- Are failure modes documented (e.g., "If zero results, stop and report")?
- Are escalation paths clear?

### Step 4: Classify Findings

Assign a severity to each finding:

- **CRITICAL**: Skill would produce wrong output or fail. Routing error, missing schema, dangling reference.
- **HIGH**: Skill would produce degraded output. Context risk, ambiguous instructions, schema mismatch.
- **MEDIUM**: Quality issue. Documentation drift, naming inconsistency, missing edge case.
- **LOW**: Polish. Readability, minor wording, suggestions for improvement.

### Step 5: Form a Verdict

Count blockers (CRITICAL + HIGH) and suggestions (MEDIUM + LOW). Determine the
overall verdict:

- **Blockers found** → Skill needs fixes before it can be relied on
- **Suggestions only** → Skill works but could be improved
- **Clean** → Skill is well-structured and ready for use

### Step 6: Report to the User

Persist the review report to `.artifacts/skill-reviewer/{skill-name}/review.md`,
then present the same findings inline to the user.

Use this structure:

```
## Skill Review: {skill-name}

[2-3 sentence overall assessment]

### Strengths
- [What's well-done]

### Findings

| # | Severity | File | Finding | Suggestion |
|---|----------|------|---------|------------|
| 1 | HIGH | skills/analyze.md | ... | ... |
| 2 | MEDIUM | SKILL.md | ... | ... |

(If no findings, write "No findings." and omit the table.)

### Summary

- **Blockers**: {count} (CRITICAL + HIGH — should fix before relying on the skill)
- **Suggestions**: {count} (MEDIUM + LOW — improve quality but not blocking)
- **Verdict**: [one-line summary]
```

Be direct. Don't hedge with "everything looks great but maybe consider..."
when there's an actual problem. If a skill is broken, say so.

## Output

- **Persisted**: Full review report written to `.artifacts/skill-reviewer/{skill-name}/review.md`
- **Inline**: The same review findings presented directly to the user in the conversation

## Usage Examples

**Review a specific skill:**

```
/review bugfix
```

**Review with specific concerns:**

```
/review docs-writer — I'm worried the schema between gather and draft is inconsistent
```

## Notes

- Read every file in full before forming opinions. Skimming leads to missed findings.
- The value of this review comes from being skeptical, not confirmatory.

## When This Phase Is Done

Your verdict and recommendations (from Step 6) serve as the phase summary. Tell
the user where the review was written (`.artifacts/skill-reviewer/{skill-name}/review.md`).

The review itself is complete. If the user subsequently asks to fix findings,
work through them from highest severity to lowest — this is normal editing, not
part of the review phase.
