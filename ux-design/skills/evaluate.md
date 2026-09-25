---
name: evaluate
description: Heuristic evaluation, design review, and prototype validation.
---

# Evaluate — Heuristic Evaluation

Evaluate the prototype before handoff. AI-driven reviews can identify systematic
issues; only people can validate context-dependent usability with real users.

## Dependencies

This phase uses skills from the `uxd-research` and `uxd-prototype` plugins. If a
required skill is unavailable, stop and ask the researcher to run `./install.sh`.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/03-prototype/prototype-notes.md` for
design decisions and open questions. If it does not exist, stop and recommend
`/prototype` first.

Read `.artifacts/ux-design/{issue-key}/01-discovery.md` for user groups and
problem framing. If `.artifacts/ux-design/{issue-key}/02-research.md` exists,
read it for user needs and insights.

## Process

### Step 1: Choose Evaluation Depth

Ask the researcher which coverage is appropriate:

| Depth | Coverage | Skills |
|-------|----------|--------|
| **Quick** | Three independent heuristic evaluators inspect the prototype against the selected framework. | Step 2 |
| **Standard** | Quick plus structured scoring for accessibility, hierarchy, content, state coverage, and goal alignment. | Steps 2–3 |
| **Full** | Standard plus Jira acceptance-criteria validation and persona-based browser walkthroughs. | Steps 2–4 |

Use Quick for early iterations, Standard for most reviews, and Full when the
prototype has Jira acceptance criteria and can be run in a browser. Default to
Standard.

The upstream `uxd-prototype-evaluate` skill is now an acceptance-criteria and
persona walkthrough pipeline. It no longer accepts `--depth` and no longer
produces the former desirability study. Full means that this pipeline is added
to the review; it does not mean a desirability study.

If Full's Jira, browser, or runtime prerequisites are unavailable, tell the
researcher which prerequisite is missing and ask whether to continue at Standard.
Do not silently downgrade the evaluation.

### Step 2: Heuristic Evaluation

Run `uxd-research-heuristic-eval` with three independent evaluators. The skill
covers usability heuristics; it is not an accessibility audit.

**Choose the framework first.** Ask which framework to use:

- Nielsen's 10 Usability Heuristics
- Shneiderman's 8 Golden Rules
- ISO 9241-110 Interaction Principles
- Gerhardt-Powals' Cognitive Engineering Principles

The skill accepts screenshots, image files, text descriptions, and URLs. For a
URL, inspect the rendered page in a live browser before invoking the skill. Do
not use curl, WebFetch, or page source as a substitute. If no live browser is
available, ask the researcher for screenshots. Do not evaluate a Figma link or
raw HTML path directly.

For a standalone prototype, serve `.artifacts/ux-design/{issue-key}/03-prototype/prototype/`
and pass its URL. For workspace mode, run the app using the project's own
directions. If serving is not possible, capture screenshots of the important
screens and states into
`.artifacts/ux-design/{issue-key}/04-eval-raw/screenshots/`.

Screenshots are required at Standard and Full depth because Step 3 needs them.
At Quick depth, a live URL or screenshots are sufficient. If the required input
cannot be produced, stop and explain what the researcher needs to provide.

Run the skill in agent-operated mode so its review gate is deferred to the
single combined researcher review in Step 7. `--project` must be relative to the
source repository root:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel) || { echo "Failed to find repository root"; exit 1; }
cd "$REPO_ROOT"
uxd-research-heuristic-eval "<prototype URL or screenshots directory>" \
  --framework "<chosen>" --review none \
  --project ".artifacts/ux-design/{issue-key}/04-eval-raw"
```

`--review none` requires `--framework`. It emits an Unreviewed Draft so the
researcher can confirm findings in Step 7. Read the generated report from
`.artifacts/ux-design/{issue-key}/04-eval-raw/`.

### Step 3: Design Heuristics Scoring (Standard and Full)

Run `uxd-evaluate-design-heuristics` with the screenshots from Step 2. It
requires screenshots rather than a URL and returns its scores and findings
inline; it does not write a report file. Capture the returned results for the
combined report.

This skill covers accessibility as one design-review dimension. The
`uxd-research-heuristic-eval` skill does not run accessibility scanners or score
WCAG conformance. Do not present heuristic observations as an accessibility
audit.

### Step 4: Acceptance-Criteria and Persona Evaluation (Full only)

`uxd-prototype-evaluate` now requires a Jira story key, Atlassian MCP access, a
reachable prototype URL, Node/npm, and Playwright Chromium. It runs acceptance-
criteria validation and persona-based browser walkthroughs. It may fix failed
criteria by default, so always pass `--no-fix`; never pass `--reset` or omit
`--no-fix` in this workflow. It has no `--depth` flag. With a prototype URL but no
workspace or MR URL, its own rules require the researcher to confirm before
continuing.

The upstream skill writes into `.artifacts/{KEY}/eval/` and `.artifacts/eval/`
under the consumer repository's Git root. Keep those files inside this
workflow's private namespace by giving the evaluator a private Git root for
each run:

1. Create a unique run directory at
   `.artifacts/ux-design/{issue-key}/04-eval-raw/prototype-evaluate/{run-id}/`.
2. Initialize a local Git repository in that directory. This makes the
   evaluator's `.artifacts/` output paths resolve inside the UX Design
   workflow's private artifact directory.
3. Stage the prototype's `rfe-snapshot.md` at
   `{run-directory}/.artifacts/{issue-key}/rfe-snapshot.md`. Stage any
   `decisions/` artifacts there when available. If the consumer project has
   `config/product-overlay.yaml`, copy it to the same path under the run
   directory; do not invent a product overlay if it is absent.
4. Run the evaluator from the run directory with the issue key, prototype URL,
   `--no-fix`, and `--workspace=<path>` when a workspace clone exists:

   ```text
   uxd-prototype-evaluate {issue-key} "{prototype URL}" --no-fix [--workspace="{workspace path}"]
   ```

5. Read the resulting report and evidence from
   `{run-directory}/.artifacts/{issue-key}/eval/`. The cross-key files are
   isolated under `{run-directory}/.artifacts/eval/`. Keep the run directory
   for review; do not copy these files to `.artifacts/{issue-key}/` at the
   repository root.

Use a fresh run directory for each evaluation. If the skill's required Jira
access, product configuration, URL, or browser runtime is unavailable, Full is
not available; ask whether to continue at Standard.

**Runtime paths:** Upstream scripts refer to `CLAUDE_SKILL_DIR` and
`CLAUDE_PLUGIN_ROOT`. Claude Code supplies those variables. In other runtimes,
resolve the installed skill directory under
`${HOME}/.uxd-ai-skills/plugins/uxd-prototype/skills/uxd-prototype-evaluate`
and its plugin root at `${HOME}/.uxd-ai-skills/plugins/uxd-prototype`. Set the
expected variable for a helper invocation or substitute its absolute path.
Do not run helper scripts from an assumed plugin location.

### Step 5: Cross-Reference with Research

If `02-research.md` exists, compare evaluation findings against it:

- Do findings align with researched user needs?
- Do usability issues conflict with prioritized needs?
- Do competitive patterns from discovery address any identified issues?

If formal research was skipped, cross-reference `01-discovery.md` and say that
formal research findings were not available.

### Step 6: Reconcile and Prioritize

Gather the outputs for methods that ran:

- Heuristic evaluation: reports under
  `.artifacts/ux-design/{issue-key}/04-eval-raw/`
- Design heuristics: inline scores and findings from Step 3
- Full prototype evaluation: `evaluation-report.html`,
  `evaluation-report.csv`, and `journey-log.json` under the private run
  directory from Step 4

Combine related findings, note how many methods identified each one, and give
unanimous findings the highest confidence. The upstream prototype evaluator
reports acceptance-criteria verdicts and persona walkthrough evidence; it no
longer assigns the previous S1–S4 severity scale. Do not infer a severity from
an acceptance-criteria verdict or persona score. The researcher sets the final
severity in Step 7.

| Severity | Definition |
|----------|------------|
| Critical | Prevents users from completing the primary task |
| Major | Causes significant confusion or extra effort |
| Minor | Noticeable friction that does not block task completion |
| Cosmetic | Aesthetic issue with no functional impact |

### Step 7: Researcher Review (Required)

This is the workflow's single review gate. The upstream heuristic evaluation
runs with its review deferred; the prototype evaluator's scores and verdicts
are evidence, not researcher-approved conclusions.

Present all findings. The researcher confirms or dismisses each one, assigns
severity, adds missing context, and chooses which issues to address or accept.
Do not make these decisions for the researcher.

## Output

`.artifacts/ux-design/{issue-key}/04-evaluation.md`

Omit sections for methods that did not run. Use this structure:

```markdown
# Evaluation Report — {issue-key}

**Date:** {date}
**Prototype iteration:** {N}
**Depth:** {Quick / Standard / Full}
**Framework:** {heuristic framework}
**Methods:** {methods run}

## Summary

**Total issues:** {count}
**Critical:** {count} | **Major:** {count} | **Minor:** {count} | **Cosmetic:** {count}

## Heuristic Evaluation Findings

{From Step 2. Group findings by researcher-confirmed severity. Include the
heuristic, agreement, description, user impact, recommendation, and component.}

## Design Heuristics Scores

{From Step 3; omit at Quick depth.}

| Dimension | Score | Notes |
|-----------|-------|-------|
| Accessibility | {score} | {notes; do not claim WCAG conformance} |
| Visual hierarchy | {score} | {notes} |
| Content clarity | {score} | {notes} |
| State coverage | {score} | {notes} |
| Goal alignment | {score} | {notes} |

## Acceptance-Criteria and Persona Results

{From Step 4; omit unless Full ran. Summarize AC pass/fail/flagged verdicts,
personas and tasks, and link to the HTML evidence report.}

## Accessibility Findings

{From the design heuristics review only. State when no accessibility audit was
conducted; do not derive conformance claims from the heuristic evaluator.}

## Readiness Assessment

**Ready for handoff:** {Yes / No — needs iteration}
**Confidence:** {HIGH / MEDIUM / LOW}
**Rationale:** {why}

## Iteration Recommendations

{Researcher-approved changes for the next prototype iteration, or minor items
to carry into handoff.}
```

## When This Phase Is Done

Present the evaluation and readiness assessment. Ask whether the researcher
wants to iterate or move to handoff. Wait for the answer, then re-read
`controller.md` for next-step guidance.
