---
name: evaluate
description: Heuristic evaluation and usability assessment of prototypes.
---

# Evaluate — Heuristic Evaluation

Run systematic heuristic evaluation against the prototype to identify
usability issues before real user testing. AI-driven evaluation catches
systematic issues; only humans catch context-dependent problems.

## Dependencies

This phase requires the `uxd-workshop` skills. If any required skill is
not available, stop and tell the researcher to run `./install.sh` to set up
the uxd-workshop skills before proceeding.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/03-prototype/prototype-notes.md`
for design decisions and open questions. If `prototype-notes.md` doesn't
exist, tell the researcher that `/prototype` should run first and stop.

Also read `.artifacts/ux-design/{issue-key}/01-discovery.md` for user group
context and problem framing.

If `.artifacts/ux-design/{issue-key}/02-research.md` exists, read it for
user needs and insights — these inform impact descriptions in the evaluation
findings and the cross-reference step below.

## Process

### Step 1: Choose Evaluation Depth (Interactive)

Ask the researcher what depth of evaluation is appropriate:

| Depth | What it covers | Skills run |
|-------|---------------|-----------|
| **Quick** | Multi-evaluator heuristic inspection only (three independent AI evaluators surface usability violations against the chosen framework). No design scoring, no simulated usability. | `uxd-research-heuristic-eval` (Step 2) |
| **Standard** | Quick + structured design-heuristics scoring (accessibility, visual hierarchy, content, state coverage, goal alignment) + simulated usability testing with personas and 4-8 task scenarios, severity-ranked. | Steps 2, 3, 4 (`--depth standard`) |
| **Full** | Standard + desirability study (word association, emotional response mapping, desirability score 1-10). | Steps 2, 3, 4 (`--depth full`) |

Use Quick for early iterations and rapid feedback, Standard for most
evaluations, and Full for the final evaluation before handoff.

Default to **Standard** unless the researcher specifies otherwise.

**Naming caution:** this workflow's Quick/Standard/Full tier is *not* the same
thing as `uxd-prototype-evaluate`'s own `--depth quick|standard|full`. The
workflow tier decides *which skills run* (Quick runs no `uxd-prototype-evaluate`
at all); the skill's `--depth` only tunes that one skill once it does run. When
this phase runs `uxd-prototype-evaluate` (Standard/Full), it passes
`--depth standard` or `--depth full` accordingly (Step 4) — don't confuse the
two scales.

If the selected depth requires tools that are unavailable, stop and tell
the researcher to run `./install.sh` before proceeding.

### Step 2: Heuristic Evaluation

This is the primary evaluation tool — tested with an eval suite. It uses three
independent AI-simulated evaluators:
- **Evaluator A:** Visual inspection
- **Evaluator B:** Task flow analysis
- **Evaluator C:** Edge cases and accessibility

Findings are reconciled across evaluators and tagged by agreement level
(Unanimous, Majority, Single). Evaluators report **violations only** — they do
not make design recommendations.

**Framework selection first.** Ask the researcher which heuristic framework to
use before running the skill — do not default silently. Available frameworks:
- Nielsen's 10 Usability Heuristics
- Shneiderman's 8 Golden Rules
- ISO 9241-110 Interaction Principles
- Gerhardt-Powals' Cognitive Engineering Principles

**Produce the evaluation input first.** `uxd-research-heuristic-eval` inspects
screenshots, a URL, or a text description — **not** Figma links or raw HTML file
paths. So before invoking it, turn the prototype into something the skill can
see:

- **Standalone HTML** (`03-prototype/prototype/`): serve it and pass the URL.
  From the prototype directory, start a local server, e.g.
  `python3 -m http.server 8000` (run from
  `.artifacts/ux-design/{issue-key}/03-prototype/prototype/`), then pass
  `http://localhost:8000/<entry>.html`. Stop the server when the skill finishes.
- **Screenshots** (any mode, or when a server can't run): capture one image per
  key screen/state (empty, loading, error, populated) into
  `04-eval-raw/screenshots/` — via a browser automation tool if available, or
  ask the researcher to export them — and pass that directory.
- **Workspace mode:** the prototype runs inside the codebase; serve or run the
  app per the project's own instructions and pass the URL, or use screenshots.

**Screenshots are mandatory at Standard/Full depth.** A served URL alone
satisfies *this* step (Step 2), but Step 3's `uxd-evaluate-design-heuristics`
requires **screenshots specifically** and will stop and ask if none are provided
(it evaluates visual context and does not accept a URL). So whenever the chosen
depth is Standard or Full, capture the screenshots into `04-eval-raw/screenshots/`
now — even if you also serve a URL for Step 2 — so Step 3 has its required input
and can't block mid-phase after `uxd-prototype-evaluate` scratch is already set
up. At Quick depth (Step 2 only) a URL alone is sufficient.

**Gate — no fabricated input.** If you cannot produce the required input —
a URL *or* screenshots at Quick depth, and **screenshots** at Standard/Full depth
(e.g. an unattended run with no browser/serving capability and no exported
images) — **stop and tell the researcher** what is needed. Do not run any skill
against a Figma link or a raw file path, and do not describe the prototype from
memory in place of real input — either would produce an evaluation of something
other than the prototype.

**Invocation.** Run the skill in agent-operated mode so its own researcher gate
is deferred to this workflow's single combined gate in Step 7.

Capture the source-repository root before invoking the skill, then construct an
absolute `--project` path from that root so the path remains correct even if the
skill execution changes directory:

```bash
SOURCE_ROOT=$(pwd)
```

```
/uxd-research-heuristic-eval "<prototype URL or screenshots dir>" \
  --framework "<chosen>" --review none \
  --project "${SOURCE_ROOT}/.artifacts/ux-design/{issue-key}/04-eval-raw"
```

`--review none` requires `--framework` (it activates the skill's Mode B), so
always pass the framework the researcher chose. With `--review none` the skill
emits an **Unreviewed Draft** with AI-*suggested* severities and skips its own
review gate — this is intentional. We do **not** run two researcher gates; the
single human gate is Step 7 below, over the combined findings from all methods.

`--project` directs the skill's `.md`/`.html` reports to
`.artifacts/ux-design/{issue-key}/04-eval-raw/` (otherwise it writes them to
the current working directory). Read that report in Step 6 to fold the findings
into `04-evaluation.md`.

### Step 3: Design Heuristics Scoring (Standard and Full depth only)

Run the `uxd-evaluate-design-heuristics` skill for structured scoring
across dimensions:

- Accessibility compliance
- Visual hierarchy and scannability
- Content and microcopy clarity
- State coverage (empty, loading, error, populated)
- Goal alignment

**Input: the screenshots captured in Step 2.** This skill requires
**screenshots** (it evaluates visual context and, unlike
`uxd-research-heuristic-eval`, does not accept a served URL); it stops and asks
if none are given. Pass it the `04-eval-raw/screenshots/` directory produced in
Step 2. Since Step 2's gate makes screenshots mandatory at Standard/Full depth,
they are already present; if for any reason they are not, capture them (or ask
the researcher to export them) before invoking — do not run this skill against a
URL or from memory.

**Output is returned inline — there is no report file.** This skill is a pure
LLM skill (no `scripts/`, no `--project` flag): it *returns* the Pass/Fail
verdict, per-dimension scores (1-5), and critical issues directly (its `report`
flag, default `true`, adds the full write-up to the same returned output, it does
not write a file). Nothing lands on disk, so there is nothing to mirror or clean
up here. Capture the returned scores and critical issues in memory and fold them
into `04-evaluation.md` in Step 6.

### Step 4: Simulated Usability Assessment (Standard and Full depth only)

Skip this step at Quick depth.

`uxd-prototype-evaluate` reads its inputs from the **native skill layout**,
`.artifacts/{ID}/`, not from our `03-prototype/` directory. It reads different
files by mode:
- **Standalone mode:** the prototype files in `.artifacts/{ID}/prototype/`,
  `.artifacts/{ID}/rfe-snapshot.md`, and `.artifacts/{ID}/metadata.json`.
- **Workspace mode:** `.artifacts/{ID}/changeset.md` and
  `.artifacts/{ID}/workspace-analysis.json` (plus `metadata.json`).

If you invoke it without staging these, it silently finds nothing and produces
wrong or unevaluable results. Before running it:

1. Read the **skill prototype ID** (`{ID}`) recorded in
   `.artifacts/ux-design/{issue-key}/03-prototype/prototype-notes.md`.
2. Ensure `.artifacts/{ID}/` contains the skill's expected layout. In a
   continued session only our mirror under `03-prototype/` remains (Step 3 of
   `/prototype` removes the native copy), so recreate it. The mirror preserves
   the native layout, so this is a structure-preserving copy of whichever set
   applies:
   - **Standalone:** `03-prototype/prototype/` → `.artifacts/{ID}/prototype/`;
     `03-prototype/rfe-snapshot.md` → `.artifacts/{ID}/rfe-snapshot.md`;
     `03-prototype/metadata.json` → `.artifacts/{ID}/metadata.json`
   - **Workspace:** `03-prototype/changeset.md` → `.artifacts/{ID}/changeset.md`;
     `03-prototype/workspace-analysis.json` →
     `.artifacts/{ID}/workspace-analysis.json`;
     `03-prototype/metadata.json` → `.artifacts/{ID}/metadata.json`
   - Copy `03-prototype/reviews/summary.md` back to `.artifacts/{ID}/reviews/`
     too if it exists from a prior evaluation (so refinement can find it).
3. Invoke the skill with the ID and matching depth:

```
/uxd-prototype-evaluate {ID} --depth {standard|full}
```

- **Standard:** Rubric scoring + simulated usability testing with personas
  and task scenarios, severity-ranked issues (S1 critical through S4
  enhancement)
- **Full:** Standard + desirability study

The skill writes its outputs under `.artifacts/{ID}/` (`reviews/summary.md`,
`report-usability.md`, and for Full `report-desirability.md`) and a
`pipeline-report.html` at the **`.artifacts/` root** — both *outside* our
namespace. Read those in Step 6 to fold results into `04-evaluation.md`, then:

- **Mirror the canonical outputs into our namespace:** copy
  `.artifacts/{ID}/reviews/summary.md` → `03-prototype/reviews/summary.md`
  (refinement re-reads this), `report-usability.md` and any
  `report-desirability.md` → `04-eval-raw/`, and `.artifacts/pipeline-report.html`
  → `04-eval-raw/pipeline-report.html`.
- **Clean up skill scratch (artifact isolation).** Once mirrored, remove the
  native `.artifacts/{ID}/` and the stray `.artifacts/pipeline-report.html` so
  nothing is left outside `.artifacts/ux-design/` (`AGENTS.md` rule). A later
  session recreates `.artifacts/{ID}/` from the mirror as in step 2 above.

This skill's usability dimension also evaluates against Nielsen's heuristics,
which overlaps with Step 2 when the researcher chose Nielsen there. The overlap
is intentional — two independent passes (one violation-focused, one task/persona
-focused) raise confidence in findings both flag. Note convergent findings as
higher-confidence in Step 6 rather than deduplicating them away.

**Runtime note:** `uxd-prototype-evaluate` runs Python helper scripts via
`python3 ${CLAUDE_SKILL_DIR}/scripts/...`. `CLAUDE_SKILL_DIR` is set by Claude
Code; under Cursor or Gemini it is unset. Before the skill runs those helpers,
check it (`printenv CLAUDE_SKILL_DIR`). If it is empty, resolve the skill's
directory from the deterministic install path
`${HOME}/.uxd-ai-skills/plugins/uxd-workshop/skills/uxd-prototype-evaluate` and
substitute that path inline for every `${CLAUDE_SKILL_DIR}` in the command
(e.g. `CLAUDE_SKILL_DIR=<path> python3 <path>/scripts/<script>`). `./install.sh`
clones the skills to `${HOME}/.uxd-ai-skills`. An upstream change to how the
skill resolves its scripts would remove this workaround.

If **neither** `CLAUDE_SKILL_DIR` nor that install path resolves to a real
`scripts/` directory, or a required helper script is missing, **stop and report
the error** — do not silently continue and do not quietly downgrade a
Standard/Full evaluation to Quick. Tell the researcher the script could not be
found, and let them decide: fix the install, retry under Claude Code, or
explicitly re-run at Quick depth (heuristic evaluation only). Never present a
downgraded evaluation as if it were the depth they asked for.

### Step 5: Cross-Reference with Research

If `02-research.md` exists, compare evaluation findings against it:

- Do evaluation findings align with user needs from research?
- Are there usability issues that conflict with prioritized user needs?
- Do competitive patterns from discovery address any identified issues?

If `02-research.md` does not exist (research phase was skipped), cross-reference
against `01-discovery.md` user groups and pain points instead. Note in the
output that formal research findings were not available.

### Step 6: Reconcile and Prioritize

First, gather the raw outputs each skill wrote (use our mirrored copies from
Step 4 — the native `.artifacts/{ID}/` has been cleaned up):
- Heuristic evaluation: `.artifacts/ux-design/{issue-key}/04-eval-raw/heuristic-eval-*.md` (from Step 2)
- Design heuristics scoring: the Pass/Fail report from Step 3
- Usability/desirability (Standard/Full): `03-prototype/reviews/summary.md`,
  `04-eval-raw/report-usability.md`, `04-eval-raw/report-desirability.md` (from Step 4)

Then combine findings from all evaluation methods and rank by severity:

| Severity | Definition |
|----------|-----------|
| Critical | Prevents users from completing the primary task |
| Major | Causes significant confusion or extra effort |
| Minor | Noticeable friction but doesn't block task completion |
| Cosmetic | Aesthetic issue, no functional impact |

The methods use two severity scales. `uxd-prototype-evaluate` ranks issues
**S1–S4**; `uxd-research-heuristic-eval` and `uxd-evaluate-design-heuristics`
use **Critical/Major/Minor/Cosmetic**. Normalize everything to the
Critical/Major/Minor/Cosmetic scale above using this crosswalk before combining,
so reconciliation is deterministic:

| Skill severity | Workflow severity |
|----------------|-------------------|
| S1 (critical) | Critical |
| S2 (major/serious) | Major |
| S3 (minor) | Minor |
| S4 (enhancement/cosmetic) | Cosmetic |

The crosswalk sets the *starting* severity; the researcher can still adjust any
finding's final severity in Step 7.

Note the agreement level for each finding (how many evaluation methods
flagged it). Unanimous findings across methods carry highest confidence.

### Step 7: Researcher Review (Required)

**This is a hard gate — do not skip.** It is the workflow's *single* researcher
review. The upstream skills ran with their own review deferred
(`uxd-research-heuristic-eval` with `--review none`; `uxd-prototype-evaluate`
severities are AI-suggested), so every AI-suggested severity across all methods
is confirmed here, once, over the combined set — not method by method.

Present all candidate violations to the researcher. The researcher:
- Confirms or dismisses each finding
- Assigns final severity (AI-suggested severity is a starting point)
- Adds context the AI evaluation may have missed
- Decides which findings to address vs. accept

The AI identifies violations; the researcher makes judgment calls.

## Output

`.artifacts/ux-design/{issue-key}/04-evaluation.md`

**Omit sections for methods that did not run.** Depth determines which sections
appear: at Quick depth, only *Heuristic Evaluation Findings* and *Accessibility
Findings* are populated — omit *Design Heuristics Scores* and *Usability Testing
Results* entirely. Each template section below is annotated with the skill that
produces it; leave a section out when that skill did not run.

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

{From uxd-research-heuristic-eval (Step 2) — always present}

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

{From uxd-evaluate-design-heuristics (Step 3) — omit at Quick depth}

| Dimension | Score (1-5) | Notes |
|-----------|------------|-------|
| Accessibility | {score} | {notes} |
| Visual hierarchy | {score} | {notes} |
| Content clarity | {score} | {notes} |
| State coverage | {score} | {notes} |
| Goal alignment | {score} | {notes} |

**Verdict:** {Pass / Fail}

## Usability Testing Results

{From uxd-prototype-evaluate (Step 4) — omit at Quick depth}

**Personas tested:** {list}
**Task scenarios:** {count}

| Task | Primary User | Power User | Infrequent User |
|------|-------------|-----------|-----------------|
| {task} | {result} | {result} | {result} |

## Accessibility Findings

{Consolidated a11y issues — color contrast, keyboard navigation, screen reader
 support, ARIA usage. Drawn from Evaluator C in uxd-research-heuristic-eval and,
 when run, the accessibility dimension of uxd-evaluate-design-heuristics.

 Note whether the chosen design system/framework (e.g., PatternFly, Material UI)
 provides accessible building blocks (components with built-in WCAG compliance,
 keyboard navigation, ARIA attributes) as a baseline. The handoff should rely on
 the framework's accessibility primitives rather than requiring every attribute
 to be manually specified.}

## Readiness Assessment

**Ready for handoff:** {Yes / No — needs iteration}
**Confidence:** {HIGH / MEDIUM / LOW}
**Rationale:** {why}

## Iteration Recommendations

{If not ready: specific changes for the next prototype iteration}
{If ready: any minor improvements to note in handoff}
```

## When This Phase Is Done

Present the evaluation to the researcher:
"Evaluation complete. {N} issues found — {critical} critical, {major} major.
{Readiness assessment}. Want to iterate on the prototype, or move to handoff?"

**If iterating:** The researcher returns to `/prototype` to address findings.
Track the iteration count. After 3 cycles, prompt: "We've iterated 3 times.
Ready for handoff, or continue refining?" The researcher decides.

**If ready for handoff:** Recommend `/handoff` to the researcher.

Wait for the researcher's decision. Then **re-read the controller**
(`controller.md`) for next-step guidance.
