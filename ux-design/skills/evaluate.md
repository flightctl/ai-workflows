---
name: evaluate
description: Heuristic evaluation and usability assessment of prototypes.
---

# Evaluate — Heuristic Evaluation

Run systematic heuristic evaluation against the prototype to identify
usability issues before real user testing. AI-driven evaluation catches
systematic issues; only humans catch context-dependent problems.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/03-prototype/prototype-notes.md`
for design decisions and open questions. If `prototype-notes.md` doesn't
exist, tell the researcher that `/prototype` should run first and stop.

Also read `.artifacts/ux-design/{issue-key}/01-discovery.md` for user group
context and problem framing.

## Process

### Step 1: Choose Evaluation Depth (Interactive)

Ask the researcher what depth of evaluation is appropriate:

| Depth | What it covers | When to use |
|-------|---------------|-------------|
| **Quick** | Rubric scoring only (Completeness, Usability, Feasibility — 0-2 each, max 6, pass >= 5 with no zeros) | Early iterations, rapid feedback |
| **Standard** | Rubric + simulated usability testing with personas (primary, power, infrequent user) + 4-8 task scenarios + severity-ranked issues | Most evaluations |
| **Full** | Standard + desirability study (word association, emotional response mapping, desirability score 1-10) | Final evaluation before handoff |

Default to **Standard** unless the researcher specifies otherwise.

If a selected depth's tools are unavailable, note "Tool unavailable — depth
downgraded to Standard" and confirm with the researcher before proceeding.

### Step 2: Heuristic Evaluation

Run `/uxd-workshop:uxd-research-heuristic-eval` against the prototype.
This is the primary evaluation tool — tested with an eval suite.

This skill uses three independent AI-simulated evaluators:
- **Evaluator A:** Visual inspection
- **Evaluator B:** Task flow analysis
- **Evaluator C:** Edge cases and accessibility

Findings are reconciled across evaluators and tagged by agreement level
(Unanimous, Majority, Single). Evaluators report **violations only** —
they do not assign severity or make design recommendations. The researcher
assigns severity during review.

**Framework selection:** The skill will ask which heuristic framework to
use — do not default silently. Available frameworks:
- Nielsen's 10 Usability Heuristics
- Shneiderman's 8 Golden Rules
- ISO 9241-110 Interaction Principles
- Gerhardt-Powals' Cognitive Engineering Principles

If this skill is not available, perform a manual heuristic inspection
using Nielsen's 10 as the default framework.

### Step 3: Design Heuristics Scoring (Optional)

If available, run `/uxd-workshop:uxd-evaluate-design-heuristics` for
structured scoring across dimensions:

- Accessibility compliance
- Visual hierarchy and scannability
- Content and microcopy clarity
- State coverage (empty, loading, error, populated)
- Goal alignment

Returns a Pass/Fail verdict with per-dimension scores (1-5), a critical
issues list, and an optional full report.

If this skill is not available, skip this step.

### Step 4: Simulated Usability Assessment

If the chosen depth is **Standard** or **Full**, run
`/uxd-workshop:uxd-prototype-evaluate` at the matching depth:

- **Standard:** Rubric scoring + simulated usability testing with personas
  and task scenarios, severity-ranked issues (S1 critical through S4
  enhancement)
- **Full:** Standard + desirability study

If this skill is not available, simulate usability scenarios manually:
define 3 personas (primary, power, infrequent user), 4-6 task scenarios,
and walk through each against the prototype.

### Step 5: Cross-Reference with Research

Compare evaluation findings against research data:

- Do evaluation findings align with user needs from research?
- Are there usability issues that conflict with prioritized user needs?
- Do competitive patterns from discovery address any identified issues?

### Step 6: Reconcile and Prioritize

Combine findings from all evaluation methods and rank by severity:

| Severity | Definition |
|----------|-----------|
| Critical | Prevents users from completing the primary task |
| Major | Causes significant confusion or extra effort |
| Minor | Noticeable friction but doesn't block task completion |
| Cosmetic | Aesthetic issue, no functional impact |

Note the agreement level for each finding (how many evaluation methods
flagged it). Unanimous findings across methods carry highest confidence.

### Step 7: Researcher Review (Required)

**This is a hard gate — do not skip.**

Present all candidate violations to the researcher. The researcher:
- Confirms or dismisses each finding
- Assigns final severity (AI-suggested severity is a starting point)
- Adds context the AI evaluation may have missed
- Decides which findings to address vs. accept

The AI identifies violations; the researcher makes judgment calls.

## Output

`.artifacts/ux-design/{issue-key}/04-evaluation.md`

```markdown
# Evaluation Report — {issue-key}

**Date:** {date}
**Prototype iteration:** {N}
**Depth:** {Quick / Standard / Full}
**Framework:** {which heuristic framework was used}
**Methods:** {heuristic eval, design scoring, simulated usability, desirability}

## Summary

**Total issues:** {count}
**Critical:** {count} | **Major:** {count} | **Minor:** {count} | **Cosmetic:** {count}

## Heuristic Evaluation Findings

### Critical

#### {Finding title}
- **Heuristic:** {which heuristic violated}
- **Agreement:** {Unanimous / Majority / Single}
- **Description:** {what the issue is}
- **Impact:** {how it affects users, traced to user group from research}
- **Recommendation:** {specific remediation}
- **Component:** {which part of the prototype}

### Major
...

### Minor
...

### Cosmetic
...

## Design Heuristics Scores

| Dimension | Score (1-5) | Notes |
|-----------|------------|-------|
| Accessibility | {score} | {notes} |
| Visual hierarchy | {score} | {notes} |
| Content clarity | {score} | {notes} |
| State coverage | {score} | {notes} |
| Goal alignment | {score} | {notes} |

**Verdict:** {Pass / Fail}

## Usability Testing Results

**Personas tested:** {list}
**Task scenarios:** {count}

| Task | Primary User | Power User | Infrequent User |
|------|-------------|-----------|-----------------|
| {task} | {result} | {result} | {result} |

## Accessibility Findings

{Specific a11y issues: color contrast, keyboard navigation, screen reader
 support, ARIA usage}

## Readiness Assessment

**Ready for handoff:** {Yes / No — needs iteration}
**Confidence:** {HIGH / MEDIUM / LOW}
**Rationale:** {why}

## Iteration Recommendations

{If not ready: specific changes for the next prototype iteration}
{If ready: any minor improvements to note in handoff}
```

Sections for unused methods (e.g., Design Heuristics Scores when that
skill was unavailable) should be omitted entirely.

## When This Phase Is Done

Present the evaluation to the researcher:
"Evaluation complete. {N} issues found — {critical} critical, {major} major.
{Readiness assessment}. Want to iterate on the prototype, or move to handoff?"

**If iterating:** The researcher returns to `/prototype` to address findings.
Track the iteration count. After 3 cycles, prompt: "We've iterated 3 times.
Ready for handoff, or continue refining?" The researcher decides.

**If ready for handoff:** Proceed to `/handoff`.

Wait for the researcher's decision. Then **re-read the controller**
(`controller.md`) for next-step guidance.
