---
name: feedback
description: Address PR review feedback by reading prior session context, implementing requested changes, verifying tests, and updating session artifacts for continuity across rounds.
---

# Address PR Review Feedback Skill

You are addressing review feedback on a pull request. Your job is to
understand what the reviewers are asking for, make targeted changes,
verify correctness, and record what you did so that future sessions
(including your own, if there are additional review rounds) have full
context.

## Your Role

Make focused, correct changes that address each review comment. You will:

1. Gather the review comments (from a PR, a task file, or user input)
2. Recover context from the prior session
3. Understand what each reviewer is asking for
4. Implement changes that address the feedback
5. Verify using **`pr.md` Step 5a** (project validation gates)
6. Update session artifacts with what you changed and why
7. Write comment responses for the PR (when applicable)
8. Commit, push, and post replies — **only when the user asks to submit**

## Process

### Step 1: Gather Review Comments

Determine where the review comments are coming from. Check these
sources in order and use the first one that applies:

1. **Task file**: If a task file or calling system has already provided
   the review comments inline (e.g., in a structured format with file
   paths, line numbers, and comment bodies), use those directly.
2. **PR URL or number**: If given a PR URL or number, use `gh pr view`
   to get an overview, then fetch review comments from both endpoints:
   - `gh api repos/{owner}/{repo}/pulls/{pr_number}/comments` —
     line-level review comments
   - `gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews` —
     review-level comments (the body text of each review)
   Filter to unresolved comments.
3. **User-provided context**: If the user describes feedback verbally
   or pastes comments, work from that.

If no review comments can be found from any source, stop and ask for
clarification.

### Step 2: Recover Prior Context

Check for session context from the prior session in
`.artifacts/bugfix/{issue}/`:

- **Session context** (`session-context.md`) — summarizes the original
  implementation decisions, test strategy, and known concerns
- **Implementation notes** (`implementation-notes.md`) — detailed
  file-by-file rationale
- **Root cause analysis** (`root-cause.md`) — the original root cause
  analysis

If none of these exist, work from the code and review comments directly.
Prior context is helpful but not required.

### Step 3: Understand the Feedback

For each review comment:

- Identify what the reviewer is asking for — a code change, a test
  addition, an explanation, or a design challenge
- Determine whether the request conflicts with the original design
  decisions (check session context from Step 2)
- If a reviewer's suggestion would undo an intentional decision, note
  this — you may need to explain the rationale rather than blindly
  adopting the suggestion

### Step 4: Implement Changes

For each actionable comment:

- Make the minimal change that addresses the feedback
- Follow the project's coding standards and conventions
- If you disagree with a suggestion (based on evidence from the prior
  session or your own analysis), document your reasoning — don't
  silently ignore the comment

### Step 5: Verify

**Gate: do not commit or push until all checks pass.**

Read and follow **`skills/pr.md` → Step 5a: Run Validation** in the
**project repo** (not the ai-workflows repo). Work from the target
project's directory when running validation commands.

Record the commands you ran in the session context under
`**Verification**` for the current feedback round.

**If any check fails:** Stop. Fix the failure and re-run Step 5a. Do not
commit or push broken code.

### Step 6: Update Session Context

**This step is critical for multi-round reviews.** A subsequent feedback
session will have no memory of what you did. Update the session artifacts
so the next session can pick up where you left off.

Append a feedback round section to `.artifacts/bugfix/{issue}/session-context.md`.
Determine the round number by counting existing headings that start
with `## Feedback Round` in the file and adding one.

```markdown
## Feedback Round N
**Comments addressed**: [@reviewer on file.go:42, @reviewer2 general, ...]
**Changes made**:
- [Description of change] (file.go:100-115) — [why this approach]
- [Description of change] (other.go:50) — [adopted reviewer suggestion]
**Suggestions declined**:
- [@reviewer on file.go:80]: [reason — e.g., "conflicts with backward
  compat requirement from original design"]
**Verification**: [commands from pr.md Step 5a]
**Tests updated**: [list any test changes, or "no test changes needed"]
```

If `session-context.md` does not exist, create it with a brief summary
section before adding the feedback round.

### Step 7: Write Comment Responses

Write a JSON file mapping each comment you addressed to a brief summary
of what you did (or chose not to do). Step 8 uses this file to post
replies on the PR.

Write to `.artifacts/bugfix/{issue}/comment-responses.json`:

```json
[
  {"comment_id": 123, "response": "Switched to Optional pattern as suggested."},
  {"comment_id": 456, "response": "Kept the fallback path — needed for v1 backward compat."}
]
```

Use the `comment_id` values from Step 1:
- **From `gh api`**: Use the `id` field from each comment object in the
  API response.
- **From a task file**: Use the comment ID if provided in the structured
  format.
- **From user-provided feedback**: If no IDs are available, skip posting
  replies in Step 8 (still write responses for the session record if
  helpful).

Keep responses concise (1-2 sentences).

### Step 8: Submit to PR (when requested)

Run this step **only** when the user asks to submit, push, or post
feedback to the PR (e.g. `/feedback submit`, "push the fix").

Read and follow **`skills/pr.md`** in the **project repo**, in order:

1. **Step 5a** — re-run validation immediately before commit
2. **Step 5b** — self-review gate
3. **Step 6** — stage and commit (exclude `.artifacts/` unless the user
   asks to commit them)
4. **Step 7** — push to the `fork` remote, never `origin`

Do **not** run `pr.md` Step 8 (Create the Draft PR) — the PR already
exists.

5. **Post review replies** from `comment-responses.json`:

```bash
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  -f body='Your reply text here.' \
  -F in_reply_to={comment_id}
```

Use the `comment_id` from each entry. Mention the commit SHA when helpful.

If push or reply posting fails, stop and report the error — do not claim
the feedback was submitted.

## Output

- **Modified code files**: Changes addressing review feedback
- **Updated session context**: `.artifacts/bugfix/{issue}/session-context.md`
  with a new feedback round section appended
- **Comment responses**: `.artifacts/bugfix/{issue}/comment-responses.json`
  with per-comment summaries
- **Pushed commit(s) and PR replies** — only when Step 8 was requested

## Best Practices

- **Use `pr.md` for gates.** Step 5 and Step 8 defer to `skills/pr.md`
  Step 5a–7 — do not invent alternate lint or test commands.
- **Read before writing.** Understand the original reasoning before
  changing code — a reviewer comment that says "do X" may conflict with
  a design constraint you'd only know from the prior session context.
- **Don't revert intentional decisions without cause.** If the original
  session rejected an approach for good reason (documented in
  implementation notes or session context), explain that reason to the
  reviewer rather than silently adopting their suggestion.
- **Record declined suggestions.** If you don't adopt a reviewer's
  suggestion, record why. This prevents the next round from
  re-evaluating the same trade-off.
- **Keep changes focused.** Address the review comments — don't
  refactor surrounding code or fix unrelated issues.

## Error Handling

If a review comment is ambiguous or contradicts another comment:

- Document the conflict
- Make your best-effort interpretation and explain it
- Flag it for human resolution in the session context

## When This Phase Is Done

Report your results:

- Which comments were addressed and how
- Which suggestions were declined and why
- Where the session context was updated
- **Verification commands run** and whether they passed
- If Step 8 ran: commit SHA, push result, and PR reply URLs

Then **stop and wait for further instructions** — unless Step 8 was
requested, in which case confirm submission is complete. Do not re-read
the controller. (If this skill was invoked by an automated orchestrator,
return control to it.)
