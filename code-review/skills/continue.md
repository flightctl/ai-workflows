---
name: continue
description: Implement accepted review changes, re-review, and present new findings. Cleans up on final approval.
---

# Continue Code Review Skill

You are the implementor responding to code review feedback. Your job is to
implement the user's accepted changes, obtain a re-review, assess the new
findings, and present them for the next decision -- or finalize if approved.

## Your Role

Apply the changes the user accepted, write a response documenting what was
changed and why anything was rejected, obtain a fresh review of the updated
code, and present the results. When the review is approved and the user
confirms, clean up all artifacts.

## Critical Rules

- **Only implement what was decided.** In attended mode, implement only
  what the user accepted. In unattended mode, implement what the
  implementor's assessment recommends. Do not add improvements beyond
  what was decided.
- **Read before writing.** Before modifying any file, read it first to
  confirm the change is still valid.
- **Run validation if available.** If the reviewer profile includes lint or
  test commands, run them after making changes. Report failures.
- **Each round produces a new review file.** Round 2 produces
  `code-review-002.md`, round 3 produces `code-review-003.md`, etc.
- **Clean up on approval.** When the reviewer approves and the user
  confirms (or in unattended mode, when the reviewer approves), delete
  all artifacts in the review directory.

## Process

### Step 1: Read Context

Read `.artifacts/code-review/{branch}/review-metadata.json` to determine
the current iteration.

Read the latest review file (`code-review-{NNN}.md`) and the reviewer
profile (`00-reviewer-profile.md`).

Check for a decisions file (`decisions-{NNN}.json`) matching the current
iteration. If it exists, use those decisions — this enables recovery
after a session interruption. If it does not exist and the user's
decisions are not available in the conversation context, ask them to
review the findings table and state their decisions first.

### Step 2: Confirm Implementation Approach

For each accepted finding, determine the concrete action. Most findings
map to a single obvious change — for these, no user confirmation is
needed.

If any accepted finding has ambiguity in how to implement it (e.g.,
multiple valid approaches, a design choice the reviewer didn't specify,
or the user's modification leaves room for interpretation), present
those specific items for clarification before proceeding:

```markdown
Finding #{N} ({title}) — accepted, but implementation needs clarification:
- Option A: {approach}
- Option B: {approach}
Which do you prefer?
```

Do not present a full change plan for confirmation when the implementation
is straightforward. That adds friction without safety value — the user
already made their decisions in the previous step.

### Step 3: Create Response Skeleton

Increment the iteration counter. Create the response file
`.artifacts/code-review/{branch}/review-response-{NNN}.md` with the
skeleton structure before making any code changes:

```markdown
# Review Response -- Round {N}

## Summary
{will be added during polish pass}

## Changes Made

{entries will be added here as each change is applied}

## Items Not Changed

{entries will be added here for rejected findings}

## Questions Answered

{will be filled in during polish pass, if the review included questions}

## Validation Results
- **Lint:** {pending}
- **Tests:** {pending}
```

Populate the "Items Not Changed" section immediately with all rejected
findings and their rationales -- these are known before implementation
begins:

```markdown
### Finding {Z}: {title}
- **Decision:** Rejected
- **Rationale:** {why this finding was not implemented}
```

### Step 4: Implement Accepted Changes

This step is about making code changes, not planning them. Work through
every accepted finding and modify the actual codebase.

For each accepted finding, in order:

1. Read the affected file
2. Make the code change
3. Verify the change is correct (re-read the modified section)
4. **Immediately** append the change record to the "Changes Made" section
   of the response file:

```markdown
### Finding {X}: {title}
- **Decision:** Accepted
- **Change:** {what was actually modified -- describe the concrete edit}
- **Location:** {file path}:{line or range}
```

Document each change right after making it, not at the end. This captures
the change accurately while the details are fresh and provides a partial
record if the session is interrupted.

Do not batch changes blindly. After each file is modified, confirm the
edit was applied correctly before moving to the next.

Do not stop partway through the accepted findings to ask whether you
should continue. The user already approved these changes — implement all
of them. Do not describe what you would change — change it.

#### Checkpoint

Before proceeding to Step 5, verify:
- You have modified actual code files (not just documentation or plans)
- Every accepted finding has been implemented
- Every change has been documented in the response file
- The only unimplemented findings are those the user explicitly rejected

If any of these are incomplete, finish Step 4 before proceeding.

### Step 5: Run Validation (if available)

If the reviewer profile (`00-reviewer-profile.md`) includes a lint command
or test command, run them:

```bash
{lint command from reviewer profile}
```

```bash
{test command from reviewer profile}
```

If validation fails:
- Report the failures to the user
- Propose fixes for lint/test failures caused by the review changes
- Do not fix failures unrelated to the review changes -- report them
  as pre-existing

Update the "Validation Results" section of the response file with the
actual outcomes:

```markdown
## Validation Results
- **Lint:** {pass/fail -- summary of issues if any}
- **Tests:** {pass/fail -- summary of failures if any}
```

### Step 6: Polish and Cross-Check the Response

The response file now contains incremental documentation from Step 4.
Clean it up before handing it to the reviewer.

1. **Add an executive summary** at the top of the response file:

   ```markdown
   ## Summary
   {2-3 sentences: how many findings addressed, how many rejected
   and why, overall state of the changes}
   ```

2. **Fill in "Questions Answered"** — if the review included Questions,
   add a section with the user's confirmed answers:

   ```markdown
   ## Questions Answered

   ### Question: {question text}
   **Answer:** {the confirmed answer}
   ```

3. **Polish for consistency:**
   - All entries must use past tense ("Changed", "Fixed", "Added")
   - Verify file paths and location references are accurate
   - Remove any remaining placeholder text from the skeleton

4. **Cross-check against the original review.** Re-read the review file
   (`code-review-{NNN}.md`) and verify that **every** finding and
   question is accounted for in the response — either under "Changes
   Made", "Items Not Changed", or "Questions Answered". If anything was
   missed, add it now.

### Step 7: Obtain Re-Review

Obtain a fresh review of the current state, following the same approach
as Step 6 of `/start`:

**If the AI runtime supports subagents:** Check `review-metadata.json`
for a `reviewer_agent_id`. If one exists and the runtime supports agent
resumption, resume the same reviewer agent — this gives it memory of
previous reviews and concerns. If resumption is not available or there
is no stored agent ID, spawn a new subagent. Load it with the reviewer
profile, the updated diff (`git diff HEAD`), all previous review and
response files (so the reviewer has full history), the project's
`AGENTS.md`/`CLAUDE.md`, and the workflow's guidelines (`../guidelines.md`).
Store any new agent ID in the metadata.

**If subagents are not available:** Perform the review sequentially. Focus
on the current state of the diff, not just the delta from last round.
Re-evaluate previously flagged areas to confirm they were addressed.

The reviewer should evaluate all categories defined in
`../../_shared/review-protocol.md` and additionally:
- Verify that accepted findings were addressed correctly
- Check whether the changes introduced new issues
- Re-evaluate any previously rejected findings only if the code context
  changed in a way that affects them
- Issue a verdict: APPROVED or CHANGES_REQUESTED

Write `.artifacts/code-review/{branch}/code-review-{NNN}.md` using the
same format as the initial review.

### Step 8: Update Metadata

Update `.artifacts/code-review/{branch}/review-metadata.json`:

```json
{
  "branch": "{branch}",
  "iteration": {N},
  "state": "{awaiting_decision | approved}",
  "started": "{original timestamp}",
  "last_updated": "{ISO 8601 timestamp}",
  "user_focus": "{focus guidance or null}",
  "unattended": false,
  "reviewer_agent_id": "{current agent ID or null}"
}
```

### Step 9: Evaluate Verdict

Three paths through this step:

- **APPROVED, no findings** → present summary → Step 10 (cleanup)
- **APPROVED, remaining suggestions** → present table → user decides done or another round
- **CHANGES_REQUESTED** → present table → next round

**Unattended iteration cap:** In unattended mode, after completing the
current iteration's review, check the iteration count. If it has reached
5, stop looping regardless of verdict. Present a summary of all rounds
to the user and escalate: "The review has not converged after 5 rounds.
Please review the current state and decide how to proceed." This
prevents unbounded loops when the reviewer keeps introducing new
findings. Attended mode does not need this cap — the human is the
circuit breaker.

Determine the verdict by reading both the Verdict section and the full
review body. Do not rely solely on the Verdict label — reviewers
sometimes write "APPROVED" while still including findings in the body.
Scan the entire review for findings, suggestions, questions, or any
other feedback content regardless of section headings.

**If APPROVED with no findings anywhere in the review:**

Present the approval to the user:

Before cleanup, read all response files (`review-response-{NNN}.md`) and
compile an aggregated summary of every change made across all rounds.
This must happen before Step 10 deletes the artifacts.

```markdown
## Code Review -- Approved

The reviewer approved the changes after {N} rounds.

### Review History
| Round | Findings | Accepted | Rejected | New Issues |
|-------|----------|----------|----------|------------|
| 1 | {count} | {count} | {count} | -- |
| 2 | {count} | {count} | {count} | {count} |

### Changes Made (All Rounds)
{aggregated list of all changes from all review-response files,
grouped by round, showing what was changed and where}

All review artifacts have been cleaned up.
```

Then proceed to Step 10 (cleanup).

**If APPROVED with remaining suggestions:**

Assess the remaining suggestions using the same value-based criteria as
start.md's "Assess on value" section (Step 7b) — consider every finding
on its merits regardless of severity.

In **attended mode**, present the approval with your honest assessment:

```markdown
## Code Review -- Approved (with suggestions)

The reviewer approved the changes. There are {N} remaining suggestions.

| # | Severity | Category | Finding | Implementor Assessment | Recommendation |
|---|----------|----------|---------|----------------------|----------------|
...

You can:
- Accept this as done (artifacts will be cleaned up)
- Run another /continue round to address the suggestions you agree with
```

If the user says done, compile the aggregated change summary (same as
the "APPROVED with no findings" path above) before proceeding to Step 10.

In **unattended mode**, still present the approval and suggestions table
— the user can interrupt at any time, and the table gives them the
information to decide whether to do so. Then: if any remaining
suggestions have an "Agree" assessment, persist the decisions to
`decisions-{NNN}.json` and loop back to Step 3 to implement them. If all
remaining suggestions are assessed as "Disagree", compile
the aggregated change summary (same as the "APPROVED with no findings"
path) before proceeding to Step 10 (the review is approved and all
valuable feedback has been addressed).

**If CHANGES_REQUESTED:**

Assess the new findings independently (same as start.md's "Assess on
value" section, Step 7b) — every finding on its merits, honest
recommendation for each.

In **attended mode**, present the decision table and wait:

```markdown
## Code Review -- Round {N}

{reviewer's summary}

| # | Severity | Category | Finding | Implementor Assessment | Recommendation |
|---|----------|----------|---------|----------------------|----------------|
...

Review the table and let me know your decisions, then run /continue.
```

Once the user states decisions, persist them to
`decisions-{NNN}.json` where NNN is the current iteration number
(same format as in `/start`).

In **unattended mode**, still present the decision table — the user can
interrupt at any time, and the table gives them the information to decide
whether to do so. Then:

1. If any CRITICAL finding has a "Disagree" assessment, stop and
   escalate to the user (same guardrail as `/start`).
2. Otherwise, treat the implementor's recommendations as decisions,
   persist them to `decisions-{NNN}.json`, and loop back to Step 3 to
   implement the next round.

### Step 10: Clean Up Artifacts

When the review is complete (approved and user confirms, or approved with
no findings):

```bash
rm -rf .artifacts/code-review/{branch}
```

If the `.artifacts/code-review/` directory is now empty, remove it too:

```bash
rmdir .artifacts/code-review 2>/dev/null
```

Tell the user the review is complete and artifacts have been cleaned up.

## Output

- `.artifacts/code-review/{branch}/review-response-{NNN}.md`
- `.artifacts/code-review/{branch}/code-review-{NNN}.md`
- `.artifacts/code-review/{branch}/decisions-{NNN}.json`
- Updated `review-metadata.json`
- Cleaned-up artifact directory (on approval)

## When This Phase Is Done

Present the verdict and, if applicable, the decision table.

Then **re-read the controller** (`controller.md`) for next-step guidance.
