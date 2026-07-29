---
name: respond
description: Fetch and address reviewer comments on the published design document PR.
---

# Respond to Review Skill

You are a review coordinator. Your job is to fetch reviewer comments
from the GitHub PR, help the user understand and respond to them, and
apply any resulting design document changes.

## Your Role

Read PR comments, group them by theme, propose responses, and — with
user approval — post replies and update the design document. This phase
is repeatable as new comments arrive.

## Critical Rules

- **Never post comments without user approval.** Propose responses, then wait for the user to approve, modify, or reject each one.
- **Separate content changes from clarifications.** Some comments need design doc edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing comments.
- **Allowed `gh` operations:**
  - **Read:** `gh pr view`, `gh api` GET (for fetching PR comments and review data)
  - **Write:** `gh pr comment` (for top-level replies), `gh api` POST to `pulls/{pr-number}/comments/{id}/replies` (for replying to line-level review comments)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Process

### Step 1: Resolve Docs Repo and Fetch PR Comments

Read `.artifacts/prd/config.json` to get the docs repo path and
`.artifacts/design/{issue-key}/publish-metadata.json` to get the PR
number and file path. If either file doesn't exist, tell the user that
`/publish` should be run first.

Determine `{owner}/{repo}` from the `docs_repo_remote` in the config.
Extract the PR number from the publish metadata. If the `pr_number` field
is missing or null, `/publish` was likely interrupted before the PR was
created — suggest the user re-run `/publish`. If the user provides a PR
number directly, use that instead.

Validate the docs repo path still exists:

```bash
git -C "{docs_repo_path}" status
```

Fetch both issue-level and review-level comments:

```bash
gh pr view {pr-number} --repo {owner}/{repo} --json comments,reviews,url
```

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments --paginate
```

If no comments are found, tell the user and suggest checking back later.

### Step 2: Categorize Comments

Group comments into categories:

| Category | Action |
|----------|--------|
| **Clarification request** | Draft a reply explaining the rationale |
| **Design alternative** | Evaluate the suggestion, propose a response |
| **Factual correction** | Update the design doc and acknowledge |
| **Scope question** | Draft a reply; may need `/revise` |
| **New requirement** | Flag for user decision — update design or defer |
| **Approval / positive** | Acknowledge |
| **Open question resolution** | Resolve the open question (see Step 4) |
| **Testplan feedback** | Route to testplan change handling (see Step 4, "Applying testplan changes") |
| **Out of scope** | Draft a reply explaining why |

**Routing testplan comments:** Line-level review comments (from
`gh api .../pulls/{pr-number}/comments`) include a `path` field. Comments
with `path` ending in `testplan.md` are categorized as **Testplan
feedback**. Top-level PR comments (from `gh pr view --json comments`) do
not carry a `path`. For these, inspect the comment body: if it references
test case IDs matching the pattern `TC-` followed by a requirement
identifier, or discusses adding, modifying, or removing test cases,
categorize as **Testplan feedback**. When uncertain, categorize as the
next-best-fit category and let the user reclassify during Step 3.

### Step 3: Propose Responses

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer} on Section {N}
> {quoted comment text}

**Category:** Design alternative
**Proposed response:** {your suggested reply}
**Design change needed:** Yes — update Section 4.1 architecture

### Comment 2 — {reviewer} on Open Questions (question 8.2)
> {quoted comment text}

**Category:** Open question resolution
**Proposed resolution:** {synthesized answer from reviewer discussion}
**Design change needed:** Yes — incorporate into Section {N}, remove open question 8.2

### Comment 3 — {reviewer} on testplan.md, TC-FR2-01
> {quoted comment text}

**Category:** Testplan feedback
**Proposed response:** {suggested reply}
**Testplan change needed:** {modify TC-FR2-01 expected result / add TC-FR2-03 / remove TC-FR1-02}
**Cascade:** Update Story 2.01 Test Case References, update coverage matrix
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

If the user edited `.artifacts/design/{issue-key}/03-design.md` manually
since the last workflow phase, read and follow
`../../_shared/recipes/record-manual-edit.md` with `WORKFLOW=design` and
`ISSUE_KEY={issue-key}` before applying changes.

**Check locked decisions:** Before applying any design document change —
whether a direct edit or an open question resolution — read the "Locked
Decisions" section of `.artifacts/prd/{issue-key}/02-clarifications.md`
(if it exists). If a requested change contradicts a locked decision, flag
the conflict rather than applying the change.

#### Resolving open questions

When reviewer comments relate to an open question from the Open Questions
section, synthesize the discussion into a proposed resolution:

1. Identify which open question subsection the discussion relates to.
2. Read the full thread — there may be multiple reviewers with differing
   views. Synthesize the discussion into a single proposed resolution.
   Do not assume a single comment is the final answer. If reviewers
   disagree and no consensus is apparent, present the competing positions
   to the user and ask them to decide rather than fabricating a
   compromise that nobody advocated.
3. Determine the appropriate target section based on the **Impact** field
   of the open question — e.g., an architecture decision updates §4.1,
   a data model constraint updates §4.2, a security requirement updates
   §4.5.
4. Present the proposed resolution to the user: show which open question
   is being resolved, the synthesized answer, where it will be placed in
   the design document, and the proposed text. The user may approve,
   correct, or rewrite the synthesis.
5. After user approval, incorporate the answer into the target section,
   writing it in final form as if it was always the intent (do not
   narrate the resolution).
6. Remove the resolved entry from the Open Questions section.
7. If the Open Questions section is now empty, remove the entire section
   (heading and introductory text) from the design document.

#### Applying testplan changes

When approved changes include testplan modifications (category: Testplan
feedback), apply them in this order:

1. **Modify `07-testplan.md`.** Before making any changes, record the
   Story and AC mappings of any test cases that will be removed or
   reassigned — these are needed for the cascade in step 2. Then add,
   modify, or remove test cases as directed by the approved response.
   For each change:
   - **Adding a test case:** Assign a sequence number using
     `max(existing sequences) + 1` within the requirement group (e.g.,
     if TC-FR2-01 and TC-FR2-03 exist and TC-FR2-02 was previously
     removed, the new case is TC-FR2-04 — do not reuse gaps, as ALM
     systems track by ID). Create the full test case entry:
     H4 heading with ID and title, metadata table (Story, AC, Priority,
     Automation), and H5 sub-sections (Preconditions, Steps, Expected
     Results). Update the testplan's Overview counts and Summary table.
   - **Modifying a test case:** Update the affected heading, metadata
     table fields, or sub-section content. The same Expected Results
     quality gate applies — no banned vague phrases. If the Story assignment
     changes, update both the old and new story's Test Case References
     in step 2 below.
   - **Removing a test case:** Delete the test case entry (heading and
     all sub-sections). Update the testplan's Overview counts and
     Summary table.

2. **Cascade to story files.** For each affected story (identified by
   the Story field of changed test cases AND the pre-mutation mappings
   captured in step 1 for removed/reassigned cases), skip `[DOCS]`
   stories (they do not have a Test Case References section). For
   non-`[DOCS]` stories:
   - Re-read the story file at
     `.artifacts/design/{issue-key}/05-stories/epic-{N}/story-{NN}-{slug}.md`.
   - Rewrite the `## Test Case References` section: collect all TC IDs
     from the updated testplan where the Story field matches this story,
     then write `Verified by: {comma-separated TC IDs}`.
   - If a story loses all its test cases, write:
     `Verified by: None (no behavioral test cases after testplan revision)`.

3. **Cascade to coverage matrix.** Re-read
   `.artifacts/design/{issue-key}/06-coverage.md`. For each entry in the PRD
   Requirement mapping table, update the `Test Cases` column to reflect
   the current TC IDs from the testplan for that requirement. If a
   requirement previously had test cases and now has none, flag it in the
   coverage matrix Gaps section.

4. **Update testplan Gaps section.** If test cases were removed and a
   requirement that previously had test cases now has none, update the
   testplan's own Gaps section to reflect the new gap.

**Update the local artifact:** Update
`.artifacts/design/{issue-key}/03-design.md`.

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

**Update the docs repo copy:** Read
`.artifacts/design/{issue-key}/publish-metadata.json` to get the file
path. If metadata doesn't exist, ask the user for the path.

Copy the updated artifact to the docs repo and commit:

```bash
git -C "{docs_repo_path}" fetch origin
```

```bash
git -C "{docs_repo_path}" status
```

If there are uncommitted changes, ask the user before continuing.

```bash
git -C "{docs_repo_path}" branch --show-current
```

If not on the PR branch (`design/{issue-key}`), check it out:

```bash
git -C "{docs_repo_path}" checkout design/{issue-key}
```

Fast-forward the local branch if the remote is ahead:

```bash
git -C "{docs_repo_path}" pull --ff-only
```

```bash
mkdir -p "{docs_repo_path}/$(dirname "{design_file_path}")"
```

```bash
cp ".artifacts/design/{issue-key}/03-design.md" "{docs_repo_path}/{design_file_path}"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{design_file_path}"`.

```bash
git -C "{docs_repo_path}" add "{design_file_path}"
```

If `07-testplan.md` exists and `publish-metadata.json` contains a
`testplan_file_path` field, also copy the testplan to the docs repo.
(If the testplan was never published — no `testplan_file_path` in
metadata — testplan changes are applied locally only. Re-run `/publish`
to include the testplan in the docs repo.)

**Sync-manifest guard:** If `.artifacts/design/{issue-key}/sync-manifest.json`
exists, the published testplan's Story field must use Jira keys (resolved
by `/sync`), not local identifiers. Before copying, read the sync manifest
and resolve the Story field in each test case's metadata table: replace local
references (e.g., `Story 1.01`) with their Jira keys from the manifest
(e.g., `EDM-1234`). Write the resolved version to the docs repo — do NOT
modify the local `07-testplan.md` (it keeps local identifiers).

If `sync-manifest.json` does not exist:

```bash
cp ".artifacts/design/{issue-key}/07-testplan.md" "{docs_repo_path}/{testplan_file_path}"
```

If `sync-manifest.json` exists, write the resolved content (with Jira
keys in Story fields) to `{docs_repo_path}/{testplan_file_path}`
directly — do not `cp` the unresolved local file.

```bash
git -C "{docs_repo_path}" add "{testplan_file_path}"
```

```bash
git -C "{docs_repo_path}" commit -m "Design {issue-key}: address review feedback"
```

```bash
git -C "{docs_repo_path}" push
```

**Post the reply** as a PR comment.

#### Clarification-only replies

For comments that only need a reply, post directly.

#### Posting replies

Write the reply to a temp file to avoid shell metacharacter issues:

```bash
cat > .artifacts/design/{issue-key}/tmp-reply.md << 'REPLY_EOF'
{approved reply text}
REPLY_EOF
```

**For line-level review comments** (those fetched via
`gh api .../pulls/{pr-number}/comments` — attached to a specific file and
line), reply in-thread so the response appears alongside the original
comment:

```bash
gh api repos/{owner}/{repo}/pulls/{pr-number}/comments/{comment-id}/replies --field body=@.artifacts/design/{issue-key}/tmp-reply.md
```

**For top-level PR comments** (those from `gh pr view --json comments` —
general conversation comments), use:

```bash
gh pr comment {pr-number} --repo {owner}/{repo} --body-file .artifacts/design/{issue-key}/tmp-reply.md
```

```bash
rm .artifacts/design/{issue-key}/tmp-reply.md
```

### Step 5: Update Response Log

Write or update `.artifacts/design/{issue-key}/09-review-responses.md`:

```markdown
# Review Responses — {issue-key}

## Round {N} — {date}

### Comment by {reviewer} on Section {N}
- **Comment:** {summary}
- **Category:** {category}
- **Response:** {what was replied}
- **Design change:** {Yes/No — description if yes}
- **Testplan change:** {Yes/No — TC-FR2-01 modified, TC-FR2-03 added / None}
```

### Step 6: Assess Decomposition Impact

If design changes were made, check whether they affect the task breakdown:
- Did components change? → Epic boundaries may need adjustment
- Did APIs or data models change? → Stories may need updating
- Did new requirements emerge from review? → Coverage matrix needs checking
- Did requirements or acceptance criteria change? → Testplan may need updating

If testplan changes were applied in Step 4, verify that the cascade
(story Test Case References and coverage matrix Test Cases column) is
consistent. If the cascade reveals an inconsistency not caught during
Step 4 (e.g., a story references a TC ID that was removed), fix it
before proceeding.

If the decomposition is affected, flag it and recommend `/revise` or
re-running `/decompose`.

### Step 7: Report to User

Summarize:
- How many comments were addressed
- How many design changes were made
- Whether the decomposition needs updating
- Whether any comments remain unresolved

## Output

- PR comments posted (with user approval)
- `.artifacts/design/{issue-key}/03-design.md` (updated if needed)
- `.artifacts/design/{issue-key}/07-testplan.md` (updated if testplan feedback was applied)
- `.artifacts/design/{issue-key}/05-stories/epic-{N}/story-{NN}-{slug}.md` (Test Case References updated if testplan changed)
- `.artifacts/design/{issue-key}/06-coverage.md` (Test Cases column updated if testplan changed)
- `.artifacts/design/{issue-key}/09-review-responses.md`

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Design changes made
- Decomposition impact assessment
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
