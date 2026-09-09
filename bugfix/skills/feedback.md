---
name: feedback
description: >-
  Full-cycle PR review response: fetch comments, recover context, categorize
  and propose responses for user approval, implement approved changes, validate,
  then commit, push, and post review replies on the existing PR. Repeatable.
---

# Address PR Review Feedback Skill

You are handling the full review-feedback cycle for an existing pull request.
Your job is to fetch reviewer comments, understand what they're asking for,
propose responses for user approval, implement the approved changes, validate,
and submit (commit, push, post replies). This phase is repeatable — run it
again when new comments arrive.

## Your Role

1. Gather review comments from the PR
2. Recover context from the prior session and read project conventions
3. Categorize comments and propose responses for user approval
4. Implement the approved changes
5. Validate using the shared validation gate
6. Submit: self-review gate, commit, push, and post review replies
7. Update session context and report results

## Critical Rules

- **Never post review replies without user approval.** Propose responses,
  then wait for the user to approve, modify, or reject each one.
- **Separate code changes from clarifications.** Some comments need code
  edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing PR comments.
- **Use the validation-gate recipe.** Do not invent alternate lint or test
  commands, and do not substitute file-scoped tool runs for the project's
  documented CI command.
- **Commit changes using the project's commit conventions** from `AGENTS.md`
  or `CLAUDE.md`.
- **Allowed `gh` and `git` operations:**
  - **Read:** `gh pr view`, `gh pr list`, `gh api` GET (for fetching PR
    comments and review data)
  - **Write:** `gh pr comment` (for top-level replies), `gh api` POST to
    `pulls/{pr-number}/comments/{id}/replies` (for replying to line-level
    review comments)
  - **Git write:** `git push` (to fork remote only)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`,
    `gh pr create`

## Process

### Step 1: Gather Review Comments

**First, identify the push remote and `{owner}/{repo}`:**

Run `git remote -v` and examine the remotes. The fork remote is the one
whose URL contains the current user's GitHub username (not the upstream
org). Common patterns:

- A remote named `fork` pointing to the user's fork (set up by `/pr`)
- A remote named `origin` pointing to the user's fork, with an `upstream`
  remote pointing to the upstream org

If the repo is a fork, the PR lives on the upstream repo — use the
upstream's `{owner}/{repo}` for API calls. Use the fork remote for
pushing in Step 6.

If ambiguous, check `session-context.md` for the remote used in the prior
`/pr` phase. If no fork remote can be identified, ask the user.

**Then determine the PR number.** Check these sources in order:

1. **Session context**: `.artifacts/bugfix/{issue}/session-context.md` may
   contain the PR URL from a prior `/pr` or feedback round.
2. **Current branch**: Use `gh pr list --repo {owner}/{repo} --head {branch-name}`
   to find the PR for the current branch.
3. **User-provided**: The user gives a PR URL, number, or pastes comments.
4. **Task file**: A calling system has provided the review comments inline.

Fetch comments from both endpoints:

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments --paginate
```

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/reviews --paginate
```

Filter to comments that still need attention. The REST endpoints do not
expose thread resolution status directly — to check which threads are
resolved, use the GraphQL `pullRequest.reviewThreads` query with
`isResolved`. Alternatively, compare against previously addressed
comments in `session-context.md` (if a prior feedback round exists) and
focus on new or unaddressed ones.

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

Read the project's `AGENTS.md` (and `CLAUDE.md` if present) in the target
project directory for coding conventions, testing standards, and
contribution guidelines. Follow those over generic defaults.

### Step 3: Categorize and Propose Responses

Evaluate each comment on its technical merit. Do not reflexively agree with
every suggestion — assess whether the proposed change would actually
improve the code.

Group comments into categories:

| Category | Action |
|----------|--------|
| **Code change request** | Propose specific code edits |
| **Clarification request** | Draft a reply explaining the rationale |
| **Bug/defect identified** | Propose a fix with tests |
| **Style/convention issue** | Apply the fix, acknowledge in reply |
| **Design alternative** | Evaluate, propose a response |
| **Technically incorrect** | Draft a respectful rebuttal citing specific code behavior, test output, or design constraints |
| **Would degrade quality** | Draft a response explaining what would be lost and propose an alternative |
| **Approval / positive** | Acknowledge |
| **Out of scope** | Draft a reply explaining why |

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer} on {file}:{line}
**ID:** {comment_id or review_id from the API}
> {quoted comment text}

**Category:** Code change request
**Assessment:** {Agree / Disagree / Partially agree — with rationale}
**Proposed response:** {your suggested reply}
**Code change needed:** Yes — {describe the change}
```

For disagreements, the proposed response should be respectful and
evidence-based — cite specific code behavior, test coverage, or design
constraints that support the current approach. The user makes the final call
on whether to push back or comply.

**Wait for the user to approve, modify, or reject each response before
proceeding.**

### Step 4: Implement Approved Changes

For each comment the user approved for code changes:

- Make the minimal change that addresses the feedback
- Follow the project's coding standards and conventions from `AGENTS.md`
- If the change affects behavior, update or add tests
- Run the affected tests to verify

For comments the user approved as clarification-only (no code change),
no implementation is needed — the approved reply will be posted in Step 6.

If you disagree with a suggestion (based on evidence from the prior session
or your own analysis), and the user approved your pushback, document the
reasoning in the session context.

### Step 5: Verify

**If no code changes were made** (only clarification replies were approved
in Step 3), skip Step 5 and Step 6's self-review/commit/push sub-steps.
Go directly to Step 6's **Post Review Replies** to post the approved
clarification replies, then proceed to Step 7.

**Gate: do not proceed to Submit until all checks pass.**

Read and follow `../../_shared/recipes/validation-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| PROJECT_DIR | The target project directory (where the PR changes live) |
| SCOPE | `full` |

Record the commands run and results for inclusion in the session context.

**If any check fails:** Stop. Fix the failure and re-run **Verify**. Do
not proceed with broken code.

### Step 6: Submit

After verification passes, submit the changes and post review replies.

#### Self-Review Gate

Read and follow `../../_shared/recipes/self-review-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff HEAD` |
| MAX_ROUNDS | `3` |
| CONTEXT_FILES | `.artifacts/bugfix/{issue}/root-cause.md`, `.artifacts/bugfix/{issue}/implementation-notes.md` (if they exist) |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user. Do not commit until the user decides how
to handle them.

#### Stage and Commit

Stage changes selectively — exclude `.artifacts/` unless the user asks
to commit them:

```bash
git add {specific changed files}
```

```bash
git status
```

Commit with a structured message following the project's commit
conventions:

```bash
git commit -m "{scope}: address review feedback — {brief description}

Part of {owner}/{repo}#{pr-number}"
```

#### Push

Push to the fork remote (identified in Step 1), never to the upstream:

```bash
git push {fork-remote} {branch-name}
```

If push fails due to missing remote or auth, stop and report the error —
ask the user how to proceed.

#### Post Review Replies

For each approved response from Step 3 that has a `comment_id` or
`review_id`, post a reply on the PR.

Write the reply text to a temp file to avoid shell metacharacter issues.
Create `.artifacts/bugfix/{issue}/tmp-reply.md` using the host's
file-writing capability — do not use a shell heredoc, as reply content
containing the delimiter string would break it.

**For line-level review comments** (attached to a specific file and line),
reply in-thread:

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments/{comment-id}/replies --field body=@.artifacts/bugfix/{issue}/tmp-reply.md
```

**For top-level PR comments** (general conversation comments):

```bash
gh pr comment {pr-number} --repo {owner}/{repo} --body-file .artifacts/bugfix/{issue}/tmp-reply.md
```

Clean up the temporary reply file after each post:

```bash
rm .artifacts/bugfix/{issue}/tmp-reply.md
```

Skip feedback items that did not originate from a PR API fetch (e.g.,
user-provided text with no `comment_id` or `review_id`). For review-body
comments (from the `/reviews` endpoint, which have a `review_id` but no
`comment_id`), post as a top-level PR comment instead of an in-thread
reply.

If a reply fails, report which succeeded and which failed — do not claim
full success.

### Step 7: Update Session Context and Report

**This step is critical for multi-round reviews.** A subsequent feedback
session will have no memory of what you did. Update the session artifacts
so the next session can pick up where you left off.

Append a feedback round section to
`.artifacts/bugfix/{issue}/session-context.md`. Determine the round number
by counting existing headings that start with `## Feedback Round` in the
file and adding one.

```markdown
## Feedback Round N
**PR:** {owner}/{repo}#{pr-number}
**Comments addressed**: [@reviewer on file.go:42, @reviewer2 general, ...]
**Changes made**:
- [Description of change] (file.go:100-115) — [why this approach]
- [Description of change] (other.go:50) — [adopted reviewer suggestion]
**Suggestions declined**:
- [@reviewer on file.go:80]: [reason — e.g., "conflicts with backward
  compat requirement from original design"]
**Verification**: [commands run, pass/fail]
**Commit:** {SHA}
**Replies posted:** {N posted, M skipped (no comment_id)}
**Tests updated**: [list any test changes, or "no test changes needed"]
```

If `session-context.md` does not exist, create it with a brief summary
section before adding the feedback round.

Report to the user:

- How many comments were addressed and how
- How many suggestions were declined and why
- Validation result
- Commit SHA and push result
- How many replies were posted (and how many skipped)
- Whether any comments remain unresolved

## Output

- Modified code files addressing review feedback
- Pushed commit(s) on the existing PR branch
- Review replies posted on the PR (with user approval)
- Updated `.artifacts/bugfix/{issue}/session-context.md` with the new
  feedback round

## Best Practices

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

If the existing PR cannot be found (no PR for the current branch, no URL
in session context, user doesn't provide one):

- Stop and ask the user for the PR URL or number
- Do not create a new PR — that is `/pr`'s job

## When This Phase Is Done

Report your results as described in Step 7. This phase is repeatable — if
new comments arrive or existing responses need another round, run
`/feedback` again.

Then return to the invoking workflow router for completion guidance.
