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
- **Discover conventions from the project.** Do not impose external standards.
  Use the reviewer-profile cache when valid. Skip `AGENTS.md` / `CLAUDE.md`
  if already in this session.
- **Review uncommitted work only.** Default scope is uncommitted changes.
  Exclude files that are clearly unrelated workspace artifacts. When in
  doubt, include the file.
- **Index the diff; do not dump it.** Capture `--stat` and `--name-status`.
  Never paste full `git diff HEAD` into this conversation or a subagent
  prompt. Read hunk neighborhoods (`offset`/`limit` ~80 lines), not whole
  files. Skip generated/vendor/lock paths. Cap **≤20** hunk Reads.
- **Every finding must cite a specific file and location.** Discard any
  finding that cannot be traced to the name-status list.
- **Assess independently.** After obtaining the review, form your own
  opinion on each finding. Present both perspectives to the user.
- **Write each artifact path once.** No Delete+rewrite of the same file.
- **Do not glob this workflow. Do not call `GetDynamicTools`.**
- **Optional user focus.** If the user provides focus guidance, apply it
  when presenting the review request.

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

```bash
git branch --show-current
```

If in detached HEAD state, use the short SHA as the context identifier.
Set this as `{branch}` for all artifact paths.

### Step 2: Check for Existing Review

If `.artifacts/code-review/{branch}/review-metadata.json` exists, a review
is already in progress. Stop and tell the user they can `/continue` or
confirm a restart. If they confirm restart, delete the existing artifact
directory before proceeding.

### Step 3: Create Artifact Directory

```bash
mkdir -p .artifacts/code-review/{branch}
```

Warn if `.artifacts/` is not gitignored.

### Step 4: Discover Project Context

**Cache:** If `.artifacts/code-review/_reviewer-profile.md` exists and
`.artifacts/code-review/.meta.json` hashes/mtimes for `AGENTS.md`/`CLAUDE.md`,
`CONTRIBUTING.md`, Makefile (or equivalent), and CI workflow filenames
still match, copy the cache into `{branch}/00-reviewer-profile.md` and
skip convention Reads.

**Miss:** One discovery pass. Skip `AGENTS.md`/`CLAUDE.md` if already in
this session. Makefile/CI: filenames and one lint/test grep — not full
workflow bodies. `git ls-files '.github/workflows/*.yml'` (or project
equivalent). Read `../templates/00-reviewer-profile.md` **once**, fill it,
Write `{branch}/00-reviewer-profile.md` **once**, and Write the cache
files **once**.

Extract: languages/frameworks, conventions, quality gates (lint + test
commands), review focus areas.

### Step 5: Analyze Changes

Capture an **index**, not a patch dump:

```bash
git diff HEAD --stat
git diff HEAD --name-status
git ls-files --others --exclude-standard
```

Do **not** run unfiltered `git diff HEAD` into the transcript.

If there are no uncommitted changes and no untracked files, tell the user
and stop.

Exclude unrelated workspace artifacts (scratch notes, unrelated configs).
When in doubt, include. Skip generated/vendor/lock paths from hunk Reads.
Record user focus from `$ARGUMENTS`.

Read `../templates/01-change-summary.md` **once**, fill it, Write
`{branch}/01-change-summary.md` **once**.

### Step 6: Obtain the Code Review

Review with a fresh perspective, independent of the implementor.

**Hunk Reads (reviewer and sequential fallback):** For each relevant path,
Read ~80 lines around changed lines (`offset`/`limit`). Cap **≤20** hunk
Reads. Do not Read whole large files.

**If the AI runtime supports subagents:** Spawn a subagent. Load **only**:
- `00-reviewer-profile.md`
- `01-change-summary.md`
- the name-status / stat index (not the patch)
- `../../_shared/review-protocol.md`

Do **not** pass `AGENTS.md`, `guidelines.md`, or raw `git diff HEAD`.
Parent Reads `../templates/code-review.md` **once**. Instruct the
subagent to write findings to
`.artifacts/code-review/{branch}/code-review-001.md` using that
skeleton, then return.

**If subagents are not available:** Read `../../_shared/review-protocol.md`
(not `guidelines.md`) and review sequentially. Same hunk-Read rules.

Evaluate all categories in `_shared/review-protocol.md`. If the user
provided focus guidance, prioritize those areas but still report CRITICAL
and HIGH findings elsewhere.

Write `code-review-001.md` **once** from the template.

### Step 7: Validate and Assess Findings

Read the review file and work through **every** finding.

#### 7a: Validate finding references

Confirm each cited file is on the name-status / untracked list and the
location exists. Discard hallucinated paths. Note discards internally,
not in the user-facing table.

#### 7b: Assess on value

For each validated finding, follow "Assess on value, not severity" in
`../../_shared/review-protocol.md`:

- **Agree** -- the finding adds real value. State what improves.
- **Disagree** -- the finding does not add value, or the current code is
  better. State why concretely.
- **Partially agree** -- the issue is real but the suggestion could be
  improved. Propose an alternative that captures the value.

### Step 8: Write Review Metadata

Write `.artifacts/code-review/{branch}/review-metadata.json` **once**:

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
Store the subagent ID in `reviewer_agent_id` when one was spawned.

### Step 9: Present the Decision Table

Present **every** finding — do not silently drop any.

```markdown
## Code Review -- Round 1

{reviewer's summary}

| # | Severity | Category | Finding | Implementor Assessment | Recommendation |
|---|----------|----------|---------|----------------------|----------------|
| 1 | HIGH | Correctness | {short description} | Agree -- {rationale} | Accept |
| 2 | MEDIUM | Conventions | {short description} | Disagree -- {rationale} | Reject |

**Recommendations:**
- Accept {N} findings ({list numbers}) -- {brief summary of why these add value}
- Reject {N} findings ({list numbers}) -- {brief summary of why these don't add value}
```

If the reviewer included Questions, present them below the table with
proposed answers.

Then prompt the user to accept, override, or add guidance, and run
`/continue`.

Once the user states decisions, persist them to
`.artifacts/code-review/{branch}/decisions-{NNN}.json`:

```json
{
  "round": 1,
  "decisions": [
    {"finding": 1, "decision": "accept", "guidance": null},
    {"finding": 2, "decision": "reject", "reason": "user rationale"}
  ]
}
```

If the verdict is APPROVED with no findings, tell the user the review
passed and clean up artifacts automatically.

#### Unattended Mode Behavior

Still present the full decision table. After presenting:

1. If any CRITICAL finding has a "Disagree" assessment, stop and escalate.
2. Otherwise treat Agree / Partially agree as Accept and Disagree as
   Reject, persist `decisions-{NNN}.json`, and proceed to `/continue`.

## Output

- `.artifacts/code-review/{branch}/00-reviewer-profile.md`
- `.artifacts/code-review/{branch}/01-change-summary.md`
- `.artifacts/code-review/{branch}/code-review-001.md`
- `.artifacts/code-review/{branch}/review-metadata.json`
- `.artifacts/code-review/{branch}/decisions-{NNN}.json`
- `.artifacts/code-review/_reviewer-profile.md` (+ `.meta.json`) on cache miss

## When This Phase Is Done

Present the decision table to the user and your recommendations.

Then **re-read the controller** (`controller.md`) for next-step guidance.
