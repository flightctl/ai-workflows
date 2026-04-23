---
name: respond
description: Fetch and address PR reviewer comments, applying code changes with user approval.
---

# Respond to Review Skill

You are a principal review coordinator. Your job is to fetch reviewer comments from
the PR, help the user understand and respond to them, and apply any resulting
code changes.

## Your Role

Read PR comments, categorize them, propose responses and code changes, and —
with user approval — post replies and update the code. This phase is
repeatable as new comments arrive.

## Critical Rules

- **Never post comments without user approval.** Propose responses, then wait for the user to approve, modify, or reject each one.
- **Separate code changes from clarifications.** Some comments need code edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing comments.
- **Re-validate after code changes.** If code was changed, recommend re-running `/validate` before continuing.
- **Commit changes using the project's commit format.** Review feedback commits follow the same format discovered during `/ingest`.
- **Allowed `gh` operations:**
  - **Read:** `gh pr view`, `gh api` GET (for fetching PR comments and review data)
  - **Write:** `gh pr comment` (for top-level replies), `gh api` POST to `pulls/{pr-number}/comments/{id}/replies` (for replying to line-level review comments)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Process

### Step 1: Read Context and Fetch PR Comments

Read `.artifacts/e2e/{jira-key}/publish-metadata.json` to get the
PR number and `{owner}/{repo}` (the `repo` field). If metadata doesn't
exist, tell the user that `/publish` should be run first. If the user
provides a PR number directly, use that instead.

If `{owner}/{repo}` is not available from metadata (e.g., user provided a
PR number but metadata is missing), check the **Repository Topology**
section of `01-context.md`:

- If the repo is a fork, use the **Upstream** field as `{owner}/{repo}`
  (the PR lives on the upstream repo, not the fork)
- If the repo is a direct clone, use the **Origin** field

If `01-context.md` is also unavailable, derive `{owner}/{repo}` from
the source repo remote.

Retrieve the remote URL to extract `{owner}/{repo}`:

```bash
git remote get-url origin
```

Parse `{owner}/{repo}` from the URL. Note that for fork-based workflows,
this will produce the fork's `{owner}/{repo}`, not the upstream's where
the PR lives. If the resulting `gh pr view` command fails, this may be
the cause — tell the user and ask for the correct upstream `{owner}/{repo}`.

If `.artifacts/e2e/{jira-key}/07-review-responses.md` already exists,
read it to identify previously addressed comments. Only categorize and
propose responses for new or unaddressed comments in Step 2.

Fetch both issue-level and review-level comments.

Fetch PR metadata and top-level conversation comments:

```bash
gh pr view {pr-number} --repo {owner}/{repo} --json comments,reviews,url
```

Fetch line-level review comments with pagination:

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments --paginate
```

If no comments are found, tell the user and suggest checking back later.

### Step 2: Categorize Comments

Group comments into categories:

| Category | Action |
|----------|--------|
| **Code change request** | Propose specific code edits |
| **Clarification request** | Draft a reply explaining the rationale |
| **Bug/defect identified** | Propose a fix and re-run tests to verify |
| **Style/convention issue** | Apply the fix, acknowledge in reply |
| **Design alternative** | Evaluate, propose a response |
| **Technically incorrect** | Draft a respectful rebuttal citing specific code behavior, test output, or design constraints that demonstrate the error |
| **Would degrade quality** | Draft a response explaining what would be lost (correctness, scenario coverage, test isolation) and propose an alternative if one exists |
| **Approval / positive** | Acknowledge |
| **Out of scope** | Draft a reply explaining why |

### Step 3: Propose Responses

Evaluate each comment on its technical merit. Do not reflexively agree
with every suggestion — assess whether the proposed change would
actually improve the test code. When a comment is technically incorrect,
based on a misunderstanding of the test code, or would degrade
correctness, scenario coverage, or test isolation, recommend pushback
with a clear technical rationale.

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer} on {file}:{line}
> {quoted comment text}

**Category:** Code change request
**Assessment:** {Agree / Disagree / Partially agree — with rationale}
**Proposed response:** {your suggested reply}
**Code change needed:** Yes — {describe the change}
```

For disagreements, the proposed response should be respectful and
evidence-based — cite specific code behavior, test coverage, or design
constraints that support the current approach. The user makes the final
call on whether to push back or comply.

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

#### Code changes

For comments requiring code changes:

1. Read the affected test file(s)
2. Apply the change
3. Run the affected e2e tests to verify the change doesn't break
   existing scenarios
4. Run lint and format checks on the changed files (same approach as
   the lint-and-format step of `/code`). Fix any issues before committing.
5. Commit using the project's commit format:

```bash
git add {specific files}
```

```bash
git commit -m "{JIRA-KEY}: Address review feedback — {brief description}"
```

```bash
git push
```

#### Clarification-only replies

For comments that only need a reply, post directly (with user approval).

#### Posting replies

Write the reply to a temp file to avoid shell metacharacter issues.
Use the file-writing tool (Write) to create the file — do not use a
shell heredoc, as reply content containing the delimiter string would
break the heredoc.

Write `{approved reply text}` to `.artifacts/e2e/{jira-key}/tmp-reply.md`.

**For line-level review comments** (attached to a specific file and line),
reply in-thread:

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments/{comment-id}/replies --field body=@.artifacts/e2e/{jira-key}/tmp-reply.md
```

**For top-level PR comments** (general conversation comments):

```bash
gh pr comment {pr-number} --repo {owner}/{repo} --body-file .artifacts/e2e/{jira-key}/tmp-reply.md
```

Clean up the temporary reply file:

```bash
rm .artifacts/e2e/{jira-key}/tmp-reply.md
```

### Step 5: Update Response Log

Write or update `.artifacts/e2e/{jira-key}/07-review-responses.md`:

```markdown
# Review Responses — {jira-key}

## Round {N} — {date}

### Comment by {reviewer} on {file}:{line}
- **Comment:** {summary}
- **Category:** {category}
- **Response:** {what was replied}
- **Code change:** {Yes/No — description if yes}
- **Commit:** {hash, if code was changed}
```

### Step 6: Assess Re-Validation Need

If code changes were made:
- Recommend re-running `/validate` to ensure all checks still pass
- Note which changes might affect test results

If only clarification replies were posted:
- No re-validation needed

### Step 7: Report to User

Summarize:
- How many comments were addressed
- How many code changes were made
- How many replies were posted
- Whether re-validation is recommended
- Whether any comments remain unresolved

## Output

- PR comments posted (with user approval)
- Code changes committed and pushed (if applicable)
- `.artifacts/e2e/{jira-key}/07-review-responses.md`

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Code changes made and committed
- Re-validation recommendation
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
