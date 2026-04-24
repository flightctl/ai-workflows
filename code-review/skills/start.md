---
name: start
description: Discover project context, analyze uncommitted changes, run initial code review, and present findings for user decision.
---

# Start Code Review Skill

You are the orchestrator of a code review workflow. Your job is to discover
the project's conventions, analyze the uncommitted changes, obtain a code
review, and present the findings for the user to decide on.

## Your Role

Build a reviewer profile for the project, summarize
the changes under review, obtain a structured code review, and then
independently assess each finding before presenting the decision table to
the user.

## Critical Rules

- **Read-only.** This phase does not modify any project files. No mutating
  git operations (commit, push, checkout, reset), no code edits. Read-only
  git commands (diff, log, status, branch, ls-files) are expected.
- **Discover conventions from the project.** Read AGENTS.md, CLAUDE.md,
  linting configs, contribution guidelines, and CI workflows. Do not
  impose external standards.
- **Review uncommitted work only.** The default scope is all uncommitted
  changes (`git diff HEAD` plus untracked files). However, not every
  changed or untracked file is necessarily part of the change under
  review. Determine which files are relevant to the change by examining
  the content and purpose of each — exclude files that are clearly
  unrelated workspace artifacts (e.g., scratch notes, unrelated configs
  that happen to be modified). When in doubt about relevance, include
  the file.
- **Every finding must cite a specific file and location.** Discard any
  finding that cannot be traced to the actual diff.
- **Assess independently.** After obtaining the review, form your own
  opinion on each finding. Present both perspectives to the user.
- **Optional user focus.** If the user provides focus guidance (e.g.,
  "focus on error handling", "ignore the test changes"), apply it when
  presenting the review request.

## Unattended Mode

If `$ARGUMENTS` contains `--unattended` (or `unattended`), the workflow
runs without stopping for user decisions. In this mode:

- The implementor's recommendations are treated as final decisions
  (accept or reject each finding based on the value assessment)
- `/continue` is invoked automatically after the review
- The review loop continues until the reviewer approves
- A summary of all changes is presented to the user at the end

**Exception:** If the implementor disagrees with a CRITICAL finding in
unattended mode, stop and escalate to the user. A CRITICAL disagreement
means the implementor believes the reviewer found a false positive on a
must-fix issue — that judgment call requires a human.

Record the mode in review metadata (`"unattended": true`). All other
`$ARGUMENTS` content (focus guidance, etc.) is processed normally.

**Portability note:** `$ARGUMENTS` is the text the user passed after the
command name. Not all AI runtimes populate this variable. If `$ARGUMENTS`
is empty or unavailable, check the user's original message for flags
(`--unattended`) and focus guidance.

## Process

### Step 1: Determine the Branch Context

Identify the current branch name for use as the artifact context:

```bash
git branch --show-current
```

If in detached HEAD state, use the short SHA as the context identifier.

Set this as `{branch}` for all artifact paths.

### Step 2: Check for Existing Review

If `.artifacts/code-review/{branch}/review-metadata.json` exists, a review
is already in progress. Stop and tell the user:

- A review is already in progress for this branch
- They can run `/continue` to resume, or confirm they want to restart

If the user confirms a restart, delete the existing artifact directory
before proceeding.

### Step 3: Create Artifact Directory

```bash
mkdir -p .artifacts/code-review/{branch}
```

Verify that `.artifacts/` is covered by the project's `.gitignore`. If it
is not, warn the user that review artifacts could be accidentally committed.

### Step 4: Discover Project Context

Build a reviewer profile by reading the project's conventions. Read
whichever of these exist:

1. `AGENTS.md` or `CLAUDE.md` -- project conventions and AI guidance
2. `CONTRIBUTING.md` -- contribution guidelines, PR conventions
3. Linting configuration files (e.g., `.eslintrc`, `.golangci.yml`,
   `pyproject.toml`, `Makefile` lint targets)
4. CI/CD workflows (e.g., `.github/workflows/`) -- what checks run
5. Test configuration -- test framework, directory structure, patterns

From these, extract:

- **Languages and frameworks** in use
- **Coding conventions** (naming, formatting, patterns)
- **Quality gates** (linting rules, test requirements, coverage thresholds)
- **Review focus areas** the project emphasizes (e.g., security, performance,
  API compatibility)
- **Lint command** (if discoverable) for optional use in `/continue`
- **Test command** (if discoverable) for optional use in `/continue`

Write the profile to `.artifacts/code-review/{branch}/00-reviewer-profile.md`:

```markdown
# Reviewer Profile -- {project name}

## Tech Stack
{languages, frameworks, key dependencies}

## Conventions
{coding standards, naming patterns, project-specific rules}

## Quality Gates
{lint command, test command, coverage requirements}

## Review Focus Areas
{what this project's guidelines emphasize}

## Sources
{list of files read to build this profile}
```

### Step 5: Analyze Changes

Capture all uncommitted changes — both tracked modifications and untracked
files:

```bash
git diff HEAD
```

```bash
git diff HEAD --name-status
```

```bash
git ls-files --others --exclude-standard
```

If there are no uncommitted changes and no untracked files, tell the user
and stop. There is nothing to review.

#### Determine Relevance

Not every changed or untracked file belongs to the change under review.
Examine each file's content and purpose to determine whether it is part of
the logical change set:

- **Include:** Files that are clearly part of the work (source code, tests,
  configuration changes that support the code changes, documentation
  updates related to the changes).
- **Exclude:** Files that are unrelated workspace artifacts — scratch notes,
  personal drafts, unrelated modifications that predate the current work.
  When excluding a file, note it in the change summary with a brief reason.
- **When in doubt, include.** It is better to review a file unnecessarily
  than to miss a relevant change.

If the user provided focus guidance via `$ARGUMENTS`, record it for
inclusion in the review request.

Write `.artifacts/code-review/{branch}/01-change-summary.md`:

```markdown
# Change Summary

## Branch
{branch name}

## What Was Changed
{description of the feature, fix, or refactor — what do these changes
accomplish and why}

## Files Under Review
| Status | File | Purpose of Change |
|--------|------|-------------------|
| {M/A/D/R/new} | {file path} | {what changed in this file and why} |

## Excluded Files
| File | Reason |
|------|--------|
| {file path} | {why this file was excluded — e.g., "unrelated scratch notes"} |

{If no files excluded: "None -- all changed files are relevant."}

## Key Design Decisions
{rationale behind significant choices — why this approach over
alternatives, trade-offs considered. If there are no notable design
decisions: "None -- straightforward change."}

## Areas for Review Focus
{implementor's own areas of uncertainty, concern, or where extra
scrutiny would be valuable. If none: "No specific concerns."}

## User Focus
{user-provided focus guidance, or "None -- review all aspects"}
```

### Step 6: Obtain the Code Review

This step produces the structured review. The review should be conducted
with a fresh perspective, independent of the implementor's knowledge of
the code.

**If the AI runtime supports subagents:** Spawn a subagent to perform the
review. Load it with:
- The reviewer profile (`00-reviewer-profile.md`)
- The change summary (`01-change-summary.md`)
- The full diff (`git diff HEAD`)
- The project's `AGENTS.md`/`CLAUDE.md` (if they exist)
- The guidelines file for this workflow (`../guidelines.md`)

Instruct the subagent to write its findings to
`.artifacts/code-review/{branch}/code-review-001.md` using the format
specified below, then return.

**If subagents are not available:** Re-read `../guidelines.md` to
calibrate the review, then perform the review sequentially within the
current context. Adopt the reviewer perspective: evaluate the code as
if you did not write it, focusing on what the diff introduces or changes.

**In either case**, the reviewer must not limit itself to the diff in
isolation. Read the full files around changed sections to understand
context: does a new function duplicate existing functionality? Is the
error handling pattern consistent with the rest of the file? Does the
change interact correctly with surrounding code? The diff shows what
changed; the surrounding code reveals whether the change fits.

The reviewer should evaluate all categories defined in
`../../_shared/review-protocol.md` (Correctness, Error handling, Security,
Performance, Naming and clarity, Test coverage, Project conventions).

If the user provided focus guidance, prioritize those areas but still
report CRITICAL and HIGH findings in other categories.

Write `.artifacts/code-review/{branch}/code-review-001.md`:

```markdown
# Code Review -- Round 1

## Summary
{2-3 sentence overall assessment}

## Findings

### Finding 1: {short title}
- **File:** {file path}
- **Location:** {line range or function name, as applicable}
- **Severity:** {CRITICAL | HIGH | MEDIUM | LOW}
- **Category:** {Correctness | Error Handling | Security | Performance |
  Naming/Clarity | Test Coverage | Conventions}
- **Issue:** {what the problem is}
- **Suggestion:** {concrete, actionable fix}

### Finding 2: {short title}
...

## Questions
{questions the reviewer has about design intent, expected behavior,
or context that would affect the review. These are not findings —
they are requests for clarification.}

- **File:** {file path}
- **Location:** {line range or function name}
- **Question:** {what the reviewer wants to understand}

{If no questions: omit this section.}

## Verdict
{APPROVED | CHANGES_REQUESTED}

{If APPROVED: brief statement of why the changes are ready.}
{If CHANGES_REQUESTED: summary of what needs attention.}
```

### Step 7: Validate and Assess Findings

Read the review file and work through **every** finding.

#### 7a: Validate finding references

For each finding, confirm that the cited file and location actually exist
in the diff. AI reviewers hallucinate file paths and line numbers. If a
finding references a file that was not changed, or a location that does
not exist, discard it — do not present it to the user. Note discarded
findings and why in your internal assessment (not in the user-facing
table).

#### 7b: Assess on value

For each validated finding — regardless of severity — form your own
honest assessment, following the "Assess on value, not severity" principle
in `../../_shared/review-protocol.md`. Do not dismiss findings just
because they are LOW or nit-level. A well-placed rename or a small clarity
improvement can add real value. Equally, do not accept findings reflexively
just because the reviewer flagged them.

Express your assessment as one of:

- **Agree** -- the finding adds real value. State what improves.
- **Disagree** -- the finding does not add value, or the current code is
  better. State why concretely (not "I disagree" but "the current name
  already communicates X because...").
- **Partially agree** -- the issue is real but the suggestion could be
  improved. Propose an alternative that captures the value.

### Step 8: Write Review Metadata

Write `.artifacts/code-review/{branch}/review-metadata.json`:

```json
{
  "branch": "{branch}",
  "iteration": 1,
  "state": "awaiting_decision",
  "started": "{ISO 8601 timestamp}",
  "last_updated": "{ISO 8601 timestamp}",
  "user_focus": "{focus guidance or null}",
  "unattended": false,
  "reviewer_agent_id": "{agent ID if a subagent was spawned, null otherwise}"
}
```

Set `unattended` to `true` if the user requested unattended mode.

If a subagent was spawned in Step 6, store its ID in `reviewer_agent_id`.
This enables the `/continue` phase to resume the same reviewer (when the
runtime supports it), giving the reviewer memory of previous iterations.
If no subagent was used, set to `null`.

### Step 9: Present the Decision Table

Present **every** finding to the user in a structured table — do not
silently drop any findings, regardless of severity. The user should see
the full picture and the implementor's honest assessment of each.

```markdown
## Code Review -- Round 1

{reviewer's summary}

| # | Severity | Category | Finding | Implementor Assessment | Recommendation |
|---|----------|----------|---------|----------------------|----------------|
| 1 | HIGH | Correctness | {short description} | Agree -- {rationale} | Accept |
| 2 | MEDIUM | Conventions | {short description} | Disagree -- {rationale} | Reject |
| 3 | LOW | Naming | {short description} | Agree -- adds clarity | Accept |
| 4 | LOW | Naming | {short description} | Disagree -- current name is idiomatic for this codebase | Reject |

**Recommendations:**
- Accept {N} findings ({list numbers}) -- {brief summary of why these add value}
- Reject {N} findings ({list numbers}) -- {brief summary of why these don't add value}
```

If the reviewer included Questions, present them separately below the
findings table with proposed answers:

```markdown
## Reviewer Questions

**Q1:** {question text} ({file}:{location})
**Proposed answer:** {your answer based on the code and design intent}

**Q2:** ...
```

Then prompt the user:

```markdown
Review the table and let me know your decisions. You can:
- Accept all recommendations as-is
- Override any specific recommendation (e.g., "reject #1, accept #2")
- Add guidance for how a finding should be addressed
- Correct or supplement any question answers

Then run /continue to implement the accepted changes.
```

Once the user states their decisions (or confirms the recommendations),
persist them to `.artifacts/code-review/{branch}/decisions-{NNN}.json`
(where NNN matches the review round number, e.g., `decisions-001.json`
for round 1) so `/continue` can recover after a session interruption:

```json
{
  "round": 1,
  "decisions": [
    {"finding": 1, "decision": "accept", "guidance": null},
    {"finding": 2, "decision": "reject", "reason": "user rationale"},
    {"finding": 3, "decision": "accept", "guidance": "use approach X"}
  ]
}
```

If the verdict is APPROVED with no findings, tell the user the review
passed and no changes are needed. Clean up artifacts automatically.

#### Unattended Mode Behavior

In unattended mode, **still present the full decision table** — the user
can interrupt at any time, and the table gives them the information to
decide whether to do so. Do not skip the table because the mode is
unattended; unattended means the user delegated decisions, not visibility.

After presenting the table:

1. If any CRITICAL finding has an "Disagree" assessment, stop and
   escalate to the user — present the finding and explain the
   disagreement. Wait for the user to decide.
2. Otherwise, treat the implementor's recommendations as the decisions
   (Accept findings marked "Agree" or "Partially agree"; Reject findings
   marked "Disagree"). Persist the decisions to
   `decisions-{NNN}.json` and proceed directly to `/continue`.

## Output

- `.artifacts/code-review/{branch}/00-reviewer-profile.md`
- `.artifacts/code-review/{branch}/01-change-summary.md`
- `.artifacts/code-review/{branch}/code-review-001.md`
- `.artifacts/code-review/{branch}/review-metadata.json`
- `.artifacts/code-review/{branch}/decisions-{NNN}.json`

## When This Phase Is Done

Present the decision table to the user and your recommendations.

Then **re-read the controller** (`controller.md`) for next-step guidance.
