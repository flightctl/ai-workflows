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

Read `00-context.md` and confirm that the active prototype has been reviewed
against the current discovery revision. If not, stop and recommend `/prototype`
to review or revise it first. Every evaluation is tied to both the prototype
iteration and discovery revision it assessed. A prior evaluation does not
validate a later prototype or a prototype assessed against newer context.

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

During Feature-only or PRD-only work, Quick and Standard are available. Full is
available only when `00-context.md` contains the linked `[UX]` story key;
never pass the Feature key in its place.

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
source repository root. Pass `prototype_input`, `chosen_framework`, and
`project_dir` as argument data; do not interpolate raw input values into shell
source. Supply the prototype and framework through the runtime's structured
argument interface, and set the project path from the validated issue key:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel) || { echo "Failed to find repository root"; exit 1; }
cd "$REPO_ROOT"
project_dir=".artifacts/ux-design/{issue-key}/04-eval-raw"
uxd-research-heuristic-eval "$prototype_input" \
  --framework "$chosen_framework" --review none \
  --project "$project_dir"
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

`uxd-prototype-evaluate` requires the linked `[UX]` Jira story key, Atlassian
MCP access, a reachable prototype URL, Node/npm, and Playwright Chromium. It runs acceptance-
criteria validation and persona-based browser walkthroughs. It may fix failed
criteria by default, so always pass `--no-fix`; never pass `--reset` or omit
`--no-fix` in this workflow. It has no `--depth` flag. With a prototype URL but no
workspace or MR URL, its own rules require the researcher to confirm before
continuing.

The upstream skill writes into `.artifacts/{KEY}/eval/` and `.artifacts/eval/`
under the consumer repository's Git root. Keep those files inside this
workflow's private namespace by giving the evaluator a private Git root for
each run:

1. Generate a unique `{run-id}`. Apply § Run-ID and Path Safety
   (steps 1–4) to validate, create, and post-check the run directory.
   Store the validated value as `evaluation_run_id`.
2. Initialize a local Git repository in that directory. This makes the
   evaluator's `.artifacts/` output paths resolve inside the UX Design
   workflow's private artifact directory.
3. Stage the prototype's `rfe-snapshot.md` at
   `{run-directory}/.artifacts/{story-key}/rfe-snapshot.md`. Stage any
   `decisions/` artifacts there when available. If the consumer project has
   `config/product-overlay.yaml`, copy it to the same path under the run
   directory; do not invent a product overlay if it is absent.
4. Read the **Skill prototype ID** from
   `.artifacts/ux-design/{issue-key}/03-prototype/prototype-notes.md` and call
   it `{prototype-id}`. Keep this ID separate from the linked `[UX]` story key:
   the evaluator needs the story key for Jira, while prototype refinement
   needs the prototype ID for its native artifact path.
5. Run the evaluator from the run directory with `{story-key}`, prototype URL,
   `--no-fix`, and `--workspace=<path>` when a workspace clone exists:

   ```text
   uxd-prototype-evaluate {story-key} "{prototype URL}" --no-fix [--workspace="{workspace path}"]
   ```

6. Read the resulting report and evidence from
   `{run-directory}/.artifacts/{story-key}/eval/`. The cross-key files are
   isolated under `{run-directory}/.artifacts/eval/`. Keep those files at
   their current path if `{prototype-id}` equals `{story-key}`. Otherwise,
   copy `evaluation-report.csv` and `refinement-suggestions.json` into
   `{run-directory}/.artifacts/{prototype-id}/eval/`, preserving the original
   reports. Use the ID recorded in `prototype-notes.md`; do not substitute the
   story key. If either refinement file is absent, leave it absent and let
   `/prototype` follow its no-input path. Keep the run directory for review;
   do not copy evaluator files to `.artifacts/{issue-key}/` at the repository
   root.

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

#### Input Snapshot

Before running any evaluation method, read `00-context.md` and record the
current context revision, prototype iteration, and discovery revision as
the assessment's **input snapshot**. These assessed values are persisted
in the report header and all binding checks. Never backfill with a later
value; if context changes during evaluation the assessment is stale.

#### Saving the Canonical Assessment

Before presenting findings, durably write `04-evaluation.md` with
`Researcher review: Pending` and `Authorized fixes: None`. Assign stable
IDs (EVL-1, EVL-2, …) across all actionable findings from every method
that ran — heuristic evaluation, design heuristics (issues, not scores
alone), and Full acceptance-criteria/persona results (flagged verdicts).
Back-reference each ID to its source evidence. Record the input-snapshot
values (evaluation revision, prototype iteration, discovery revision,
context revision) and Full evaluation run ID (or "N/A") in the header.
Save the file, then present the same saved IDs.

A new assessment (new evaluation run) archives the prior canonical
`04-evaluation.md` per the existing history rules, increments the
evaluation revision, and assigns its own IDs with default
`Authorized fixes: None`. Do not rebind an old assessment to a new
prototype iteration or discovery revision.

Human annotations on the **same** assessment — selected fix authorization,
per-finding severity endorsement, finding confirmation or
rejection/deferral — update the saved report in place, preserving its
evaluation revision, IDs, and underlying evidence references. Do not
rerun the evaluation merely to record human decisions.

#### Researcher Review

Present the saved findings. The researcher confirms, dismisses, or defers
each one, endorses severity per finding, and adds missing context. Do not
make these decisions for the
researcher. Do not infer severity from acceptance-criteria verdicts,
persona scores, or fix requests. Report confirmation alone is not fix
permission; fix authorization alone is not severity endorsement or report
confirmation.

Each saved finding carries two per-ID fields:

- **Severity:** endorsed (researcher confirmed) or provisional (proposed,
  not yet endorsed). Unknown severity is not zero.
- **Disposition:** Pending (default for new findings before presentation),
  Confirmed, Dismissed, or Deferred. The researcher sets each finding's
  disposition during review; fix authorization does not change it.

Display unendorsed severity as provisional. Severity counts in the
Summary reflect only endorsed ratings; provisional findings show their
count separately as unconfirmed.

`Researcher review` tracks the overall report state:

- **Pending** — some findings have Pending disposition or unendorsed
  severity.
- **Confirmed** — all finding dispositions are decided (Confirmed,
  Dismissed, or Deferred — no Pending remains) and all severity ratings
  are endorsed. This is a human decision, not an automatic promotion.

Every non-Confirmed report displays readiness as "No — pending review"
regardless of how many individual severities are endorsed. A zero-findings
report or all-dismissed report still requires explicit human confirmation.

#### Remediation Authorization

Before or after severity endorsement, the researcher may explicitly
authorize fixing identified findings — either "fix all currently presented
findings" or specific IDs (e.g., "fix EVL-1, EVL-3"). This authorization:

- Applies ONLY to the finite set of saved IDs from the current assessment,
  bound to this evaluation revision, prototype iteration, discovery
  revision, and context revision. Expand "fix all" to actual current
  IDs — not future, raw, or
  unpresented findings.
- Does NOT constitute report confirmation, severity endorsement, finding
  disposition (confirmation/dismissal/deferral), or authority to fix
  unselected items.
- Requires clarification for ambiguous selection, consequential or
  underspecified fixes, malformed or empty requests, stale reports, or
  changed context. Fix authorization with zero findings is a no-op, not
  an approval.

When fix authorization is given, update only the `Authorized fixes` field
in the saved report. Fix authorization on an already-Confirmed report
updates `Authorized fixes` without resetting the Confirmed status — the
endorsed severity and finding dispositions stand.

After fix authorization, recommend `/prototype` to address the authorized
findings. The revised prototype requires a new evaluation before handoff;
the prior authorization does not carry forward to the new iteration.

#### Run-ID and Path Safety for Full Evaluation Artifacts

Apply this rule in the evaluate producer (Step 4) BEFORE creating the
run directory and in the prototype consumer (refinement gate) BEFORE
reading, composing, or copying any path. Use the same validated
`evaluation_run_id` value in both producer and consumer.

1. **Component validation.** Full-match the entire `{run-id}` against
   `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Reject empty, `.`, `..`, absolute
   paths, or any value containing `/` or `\`.
2. **Planned-path validation (pre-create).** Starting from the known
   workflow-private namespace `.artifacts/ux-design/{issue-key}/`, walk
   each ancestor toward `04-eval-raw/prototype-evaluate/{run-id}`.
   For each existing component: `lstat` to confirm it is a non-symlink
   directory (reject symlinks including broken ones, regular files, or
   other non-directories). A non-existent component is a safe planned
   path — not unsafe. If the resolved path of each existing ancestor
   remains within the resolved private namespace, the planned path is
   safe. A symlinked `04-eval-raw/` inside the namespace that resolves
   outside it fails.
3. **Creation (producer only).** After planned-path validation passes,
   create missing base directories and the new run directory. Do not
   overwrite an existing run directory.
4. **Post-create validation.** Confirm the created run directory is a
   non-symlink directory whose resolved parent is exactly the resolved
   base. Confirm the resolved base is within the resolved private
   namespace. Perform this check before `git init`, evaluator
   invocation, or any artifact writes.
5. **Input containment (producer read + consumer read/copy).** Each raw
   input (`evaluation-report.csv`, `refinement-suggestions.json`) under
   `{run-dir}/.artifacts/{ID}/eval/` must resolve within the resolved
   run directory. A symlinked input pointing to a sibling run or outside
   the tree fails. Apply before reading or copying.
6. **Failure handling.** Unsafe path (symlink escape, non-directory,
   containment failure) → stop and report; leave artifacts intact. Do
   not fall back or mask the failure. A safe planned path where the run
   or input file does not exist is a valid-missing condition (not unsafe)
   and follows existing scoped-fallback rules.

## Output

`.artifacts/ux-design/{issue-key}/04-evaluation.md`

Before replacing an existing `04-evaluation.md`, preserve it under
`.artifacts/ux-design/{issue-key}/history/evaluation-r{N}.md`, where `{N}` is
the prior evaluation revision, unless that exact report is already preserved
in the current context-revision snapshot. Increment the evaluation revision
for every new assessment; same-assessment annotations retain the existing
revision per the rules above. Keep each raw evaluator run in its unique `04-eval-raw/`
directory.

Omit sections for methods that did not run. Use this structure:

```markdown
# Evaluation Report — {issue-key}

**Date:** {date}
**Evaluation revision:** {revision number}
**Prototype iteration:** {N}
**Discovery revision:** {revision evaluated}
**Context revision:** {from 00-context.md at assessment time}
**Depth:** {Quick / Standard / Full}
**Framework:** {heuristic framework}
**Methods:** {methods run}
**Full evaluation run:** {run-id from Step 4, or "N/A" if Full did not run}
**Researcher review:** {Pending / Confirmed}
**Authorized fixes:** {ID list, or "None"}

## Summary

**Total issues:** {count}
**Endorsed severity:** Critical: {n} | Major: {n} | Minor: {n} | Cosmetic: {n}
**Provisional (unconfirmed):** {count remaining}
{All counts reflect per-finding endorsed vs provisional status. Unknown
severity is not zero; unendorsed findings appear under Provisional.}

## Findings

{Unified register from Steps 2, 3, and 4. Each finding entry includes:
ID (EVL-1, …), Severity (endorsed or provisional), Disposition (Pending
before presentation; set by researcher to Confirmed/Dismissed/Deferred),
source back-reference, heuristic or method, agreement, description,
user impact, recommendation, and component.}

## Design Heuristics Scores

{From Step 3; omit at Quick depth. Actionable issues from design heuristics
receive EVL-IDs in the Findings section above; this table holds the
non-actionable numeric dimension scores.}

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

**Ready for handoff:** {Yes / No — needs iteration / No — pending review / No — repairs pending}
**Confidence:** {HIGH / MEDIUM / LOW}
**Rationale:** {why; pending review or outstanding authorized repairs cannot be ready}

## Iteration Recommendations

{Researcher-approved changes for the next prototype iteration, or minor items
to carry into handoff.}
```

## When This Phase Is Done

Present the evaluation and readiness assessment. Ask whether the researcher
wants to iterate or move to handoff. Wait for the answer, then re-read
`controller.md` for next-step guidance.

Update `00-context.md` only after the researcher confirms the final report
(`Researcher review: Confirmed`, `Authorized fixes: None`) AND the
assessment's input-snapshot bindings (prototype iteration, discovery
revision, context revision) match the current active values. Record the
evaluation in the `Active evaluation` field with its assessed context
revision; do not increment the context revision — `/ingest` controls
source-input revisions. A Pending evaluation or one with outstanding
authorized repairs does not qualify. A Confirmed evaluation whose
bindings are stale requires a current evaluation, not retagging.
Historical reports missing the review or context-revision fields require
provable assessed-current context and matching explicit confirmation;
otherwise require a current evaluation — do not assume latest or retag.
