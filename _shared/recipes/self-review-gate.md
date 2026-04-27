# Recipe: Self-Review Gate

A quality gate that reviews code changes before they are pushed or submitted
as a PR. Used by workflows that make code changes (bugfix, implement, cve-fix,
e2e) to catch issues before external review.

This gate is one peer in a defence-in-depth chain: self-review catches
mechanical issues that automated checks are good at finding (convention
violations, obvious bugs, missing error handling, inconsistencies with
surrounding code), while downstream reviewers (coderabbit, human reviewers)
provide genuinely independent perspectives on design, architecture, and
subtle correctness issues. A same-model subagent improves review quality
over inline review but does not replace independent review.

## Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| DIFF_COMMAND | No | Must be a `git diff` invocation (the gate appends `--name-status` to it). Note: `git diff` only shows tracked file changes — if the workflow creates new untracked files, the calling workflow should stage them first or use a DIFF_COMMAND that captures them. | `git diff HEAD` |
| MAX_ROUNDS | No | Maximum fix-and-re-review iterations | `3` |
| CONTEXT_FILES | No | Workflow artifacts providing review context (e.g., design docs, requirements, implementation notes) | None |

## Procedure

### Step 1: Discover Review Tool

Check the project's AGENTS.md and CLAUDE.md for an explicit code review tool
or process. Look for:

- Non-interactive CLI tools (e.g., `coderabbit`, `codeclimate`, `semgrep`)
- Project-specific review commands or scripts that can run without user input
- Explicit instructions about how code should be reviewed before PR submission

Only use tools that can run non-interactively. If the discovered tool is a
workflow-style command that requires user interaction (e.g., multi-phase
workflows with decision points), skip it and continue to Step 2.

**If a non-interactive review tool is specified:**

1. Run the tool against the current changes
2. If the tool reports findings, assess each on value (using the criteria in
   `../review-protocol.md`) and fix issues that add real value
3. Re-run the tool to confirm fixes pass
4. Report results and return to the calling workflow

**If no suitable review tool is found**, continue to Step 2.

### Step 2: Perform Self-Review

Read `../review-protocol.md` for evaluation criteria and finding format.

Produce the diff:

```bash
{DIFF_COMMAND}
```

Also get the file list for reference:

```bash
{DIFF_COMMAND} --name-status
```

Check for untracked files that may be part of the change:

```bash
git ls-files --others --exclude-standard
```

If untracked files exist, read them and include them in the review scope.
The diff alone won't show new files unless they've been staged.

Review the changes using all evaluation criteria from the review protocol.
For each changed file, read the full file to understand context — not just
the diff in isolation. Check whether:

- New functions duplicate existing functionality
- Error handling is consistent with the rest of the file
- The change interacts correctly with surrounding code
- Test coverage matches the project's testing conventions

**If the AI runtime supports subagents**, spawn the review in a subagent for
independence. Load it with:

- The review protocol (`../review-protocol.md`)
- The diff output
- The project's AGENTS.md/CLAUDE.md (if they exist)
- Any CONTEXT_FILES provided by the calling workflow

Retain the subagent's ID for use in Step 4 — resuming the same reviewer
gives it memory of its previous findings and concerns, producing more
coherent follow-up reviews.

**If subagents are not available**, perform the review inline. Adopt the
reviewer perspective: evaluate the code as if you did not write it.

### Step 3: Validate and Assess Findings

For each finding from Step 2:

1. **Validate the reference.** Confirm the cited file and location exist in
   the diff or in the untracked files discovered in Step 2. Discard any
   finding that references a file or location that does not exist in either.

2. **Assess on value.** Does this finding genuinely improve the code? Would
   the code be meaningfully better (clearer, safer, more maintainable, more
   correct) if this change were made?

   - If yes: fix the issue immediately. Read the file before modifying it.
     Verify the fix after applying it.
   - If no: note why the finding was dismissed (stylistic preference, no
     real improvement, would introduce churn).

Only fix findings that add real value. Do not make changes for stylistic
preferences or subjective taste not grounded in project conventions.

### Step 4: Re-Review (if fixes were made)

If Step 3 produced code changes:

1. Re-run the diff to capture the updated state
2. Obtain a re-review of the updated diff:

   **If a subagent was used in Step 2 and the runtime supports agent
   resumption:** Resume the same reviewer agent. Send it the updated diff
   and a summary of fixes applied. This gives the reviewer memory of its
   original findings and lets it verify they were addressed correctly.

   **If resumption is not available:** Spawn a new subagent loaded with the
   review protocol, the updated diff, and a summary of the previous round's
   findings and fixes so it has full context.

   **If subagents are not available:** Re-review inline, focusing on the
   current state of the diff (not just the delta from last round).

   The re-review should focus on:
   - Whether fixes were applied correctly
   - Whether fixes introduced new issues
3. If new issues are found, fix them and re-review
4. Cap iterations at MAX_ROUNDS to prevent unbounded loops

If no fixes were needed in Step 3, the gate passes immediately.

### Step 5: Report

Report a brief summary to the calling workflow:

```markdown
## Self-Review Summary

- **Findings:** {total identified} ({N} after validation)
- **Fixed:** {N} findings addressed
- **Dismissed:** {N} findings ({brief rationale for each})
- **Rounds:** {N} review-fix iterations
- **Gate:** PASS | FLAG

{If any CRITICAL or HIGH findings remain unfixed, set Gate to FLAG and list
them. The calling workflow decides whether to proceed or stop.}
```

The calling workflow is responsible for any git operations needed after the
gate (staging, committing review fixes, etc.). The gate only makes code
changes — it does not commit or push.
