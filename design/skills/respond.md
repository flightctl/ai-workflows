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
  - **Read:** `gh pr view` (for PR discovery only — comment fetching is
    delegated to the shared script)
  - **Write:** delegated to `pr-comments.py reply` (do not call `gh api`
    or `gh pr comment` directly for review replies)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Shared Script

This skill delegates deterministic PR comment operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/pr-comments.py
```

The script provides subcommands: `fetch`, `reply`, and `log`. See the
script header for full usage.

## Process

### Step 1: Resolve Docs Repo and Fetch PR Comments

Read and follow `../../_shared/recipes/template-override-resolution.md`
with `WORKFLOW=design`, `TEMPLATE_FILE=design.md`. Per that recipe's
"Using the Resolved Files" guidance, treat the section-number examples
below (e.g., "§4.1") as illustrations of the built-in template only.

Read `.artifacts/config.json` to get the docs repo path and
`.artifacts/design/{issue-key}/publish-metadata.json` to get the PR
number, file path, and `{branch-name}` (from the `branch` field). If
either file doesn't exist, tell the user that
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

Resolve the shared script to an absolute path so it remains valid
regardless of working directory:

```bash
PR_COMMENTS_SCRIPT="${HOME}/.ai-workflows/_shared/scripts/pr-comments.py"
```

Use `$PR_COMMENTS_SCRIPT` instead of the relative path in all subsequent
commands.

Fetch all comments using the shared script. The script fetches line-level
review comments, top-level comments, and reviews in a single call and
outputs a unified JSON array to stdout:

```bash
python3 "$PR_COMMENTS_SCRIPT" fetch --owner {owner} --repo {repo} --pr {pr-number} --responses-log .artifacts/design/{issue-key}/responses.jsonl --include-review-threads
```

The `--responses-log` flag excludes comment IDs already addressed in
prior respond rounds. The `--include-review-threads` flag annotates
line comments with thread resolution status via GraphQL.

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

### Comment 2 — {reviewer} on Open Questions (question 9.2)
> {quoted comment text}

**Category:** Open question resolution
**Proposed resolution:** {synthesized answer from reviewer discussion}
**Design change needed:** Yes — incorporate into Section {N}, remove open question 9.2

### Comment 3 — {reviewer} on testplan.md, TC-FR2-01
> {quoted comment text}

**Category:** Testplan feedback
**Proposed response:** {suggested reply}
**Testplan change needed:** {modify TC-FR2-01 expected result / add TC-FR2-03 / remove TC-FR1-02}
**Cascade:** Update affected stories' Validated by in Design Reference
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

If the user edited `.artifacts/design/{issue-key}/03-design.md` manually
since the last workflow phase, read and follow
`../../_shared/recipes/record-manual-edit.md` with `WORKFLOW=design` and
`ISSUE_KEY={issue-key}` before applying changes.

**Check locked decisions:** Before applying any design document change —
whether a direct edit or an open question resolution — read the locked
decisions from the clarifications file (use the path from
`.artifacts/design/{issue-key}/01-context.md`'s PRD Summary section, if
one was recorded). Locked decisions appear as `#### Decision (D{N})`
sections within Q&A entries. If a requested change contradicts a locked
decision, flag the conflict rather than applying the change.

#### Resolving open questions

The resolved section guidance (from Step 1) determines whether the current
template tracks open questions as a distinct section (like the built-in
template's "Open Questions") or some other way. When reviewer comments
relate to an unresolved question or gap in the document, synthesize the
discussion into a proposed resolution:

1. If the template has a distinct open-questions section, identify which
   entry the discussion relates to. Otherwise, identify the gap directly
   from the comment thread.
2. Read the full thread — there may be multiple reviewers with differing
   views. Synthesize the discussion into a single proposed resolution.
   Do not assume a single comment is the final answer. If reviewers
   disagree and no consensus is apparent, present the competing positions
   to the user and ask them to decide rather than fabricating a
   compromise that nobody advocated.
3. If a distinct open-question entry exists, determine the target section
   based on its **Impact** field and the resolved template's actual
   structure — e.g., in the built-in template, an architecture decision
   updates §4.1, a data model constraint updates §4.2, a security
   requirement updates §4.5. A project override may number or name
   sections differently. Otherwise (no such entry — the gap was
   identified directly from the comment thread per item 1 above),
   determine the target section from the resolved section guidance and
   the nature of the gap; there is no **Impact** field to consult.
4. Present the proposed resolution to the user: show which open question
   is being resolved, the synthesized answer, where it will be placed in
   the design document, and the proposed text. The user may approve,
   correct, or rewrite the synthesis.
5. After user approval, incorporate the answer into the target section,
   writing it in final form as if it was always the intent (do not
   narrate the resolution).
6. If the resolved template tracks unresolved items in a structured
   location — a distinct open-questions section, or another location the
   section guidance identifies (e.g., an inline marker, a combined
   risks/open-items table) — remove or retire the resolved entry there
   once its answer has been incorporated into the target section. If
   removing the entry leaves a section empty, remove the section (heading
   and introductory text) only if the resolved template doesn't require it
   to remain present. Renumber subsequent sections to close the gap only
   if the resolved template numbers sections positionally; otherwise leave
   section numbers/headings as-is. Either way, fix any cross-references
   that pointed at the removed content.

#### Applying testplan changes

When approved changes include testplan modifications (category: Testplan
feedback), apply them in this order:

1. **Modify `04-testplan.md`.** Before making any changes:
   - Record the IC and requirement mappings of any test cases that
     will be removed, reassigned, or have their IC or requirement
     mapping changed (even if the TC ID is retained) — both are needed
     for the cascade in step 2 (IC mappings for IC-based matching,
     requirement mappings for cross-cutting TCs with `Interface
     Change: —`).
   - Build a **reserved-ID high-water mark** for each requirement
     group from the current testplan: scan all TC IDs under each
     `### FR-*` / `### NFR-*` heading (including any about to be
     removed) and record the highest sequence number per group. If
     the testplan's history section, provenance log, or review thread
     names previously retired IDs higher than any current ID, include
     those in the high-water mark. If historical allocation cannot be
     reliably determined and a gap might hide a retired ID, ask for
     the missing history before mutating — never guess. Deletion
     never releases a reserved sequence; new IDs are always allocated
     above the high-water mark.

   Then add, modify, or remove test cases as directed by the approved
   response. For all mutations, apply the test case format,
   setup-inheritance, and self-review rules from the draft skill's
   Step 9a and 9c — those are the canonical source for compact vs.
   full format eligibility, Shared and Additional Preconditions,
   parameterized cases, and the Expected Results quality gate. Older
   testplans using full-format Preconditions sections remain valid;
   match the testplan's existing conventions.

   For each change:
   - **Adding a test case:** Allocate the next sequence number above
     the requirement group's reserved high-water mark (e.g., if
     TC-FR2-01 and TC-FR2-03 exist and TC-FR2-02 was previously
     removed, the high-water mark is 03, so the new case is
     TC-FR2-04). Reserve the new ID immediately — subsequent adds in
     the same mutation round use the updated high-water mark. For a
     genuinely new requirement with no prior IDs, start at 01. Never
     reuse gaps or retired IDs; ALM systems track by ID. Create the
     test case entry: H4 heading with
     ID and title, metadata table (Interface Change, Priority,
     Automation), and Steps / Expected Results in the format matching
     the testplan's existing cases. If the requirement has a Shared
     Preconditions block, add case-specific setup under Additional
     Preconditions (or omit if none); otherwise include a standalone
     Preconditions section when the case needs setup.
   - **Modifying a test case:** Update the affected heading, metadata
     table fields, or content (sub-sections or compact inline fields).
     If the Interface Change or requirement mapping changes, update
     the affected stories' `Validated by` in step 2 below.
   - **Removing a test case:** Delete the test case entry (heading and
     all content).

   After all mutations, update the testplan's Overview counts and
   Summary table per the counting rules in the draft skill's Step 9a:
   parameterized rows count individually toward totals, priority, and
   automation counts; requirement and IC coverage ratios count distinct
   mapped values once each.

   After all mutations, rebuild the Test Case Index from the current
   test cases using the canonical schema from the draft skill's Step 9b
   template (`| ID | Scenario | IC | Priority |`): one row per TC ID
   (not per parameterized variation), with the scenario title from the
   H4 heading, IC and priority from the metadata table. Every current
   TC ID must appear exactly once; no missing, duplicate, extra, or
   deleted-case rows.

2. **Cascade to story files (if decomposition exists).** Skip this step
   if no decomposition artifacts exist (`06-stories/` directory not
   found). For each affected story, skip `[DOCS]` stories. For each
   changed TC, identify affected stories as the **union** of matches
   from pre-mutation mappings (recorded in step 1) and current
   mappings — apply each (IC, requirement) pair separately:
   - **Removed TCs:** match stories using pre-mutation mappings only
     (the TC no longer exists).
   - **Added TCs:** match stories using current mappings only.
   - **Remapped TCs** (IC or requirement changed): match stories using
     **both** pre-mutation and current mappings — pre-mutation finds
     stories that may lose the TC, current finds stories that may gain
     it.
   Each matching rule:
   - **IC-based:** the test case's Interface Change overlaps with the
     story's `Interface Changes` line in its Design Reference.
   - **Requirement-based (fallback for cross-cutting TCs):** the test
     case has `Interface Change: —` and its requirement overlaps with
     the story's PRD Requirements in its Design Reference.
   For each affected non-`[DOCS]` story:
   - Re-read the story file at
     `.artifacts/design/{issue-key}/06-stories/epic-{N}/story-{NN}-{slug}.md`.
   - Rewrite the `Validated by` line from the **current** (post-
     mutation) testplan state: collect all TC IDs that match this story
     (by IC overlap or requirement-based fallback for `—` TCs),
     then write `Validated by: {comma-separated TC IDs}`. This ensures
     old stories lose stale references and new stories gain them.
   - If a story loses all its test cases, write:
     `Validated by: None — no behavioral test cases after testplan revision`.

3. **Update testplan Gaps section.** After all mutations, rebuild the
   Gaps section from the current testplan state: update requirement
   coverage gaps and IC coverage gaps based on the current TC-to-
   requirement and TC-to-IC mappings.

**Update the local artifact:** Update
`.artifacts/design/{issue-key}/03-design.md`.

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/design/{issue-key}/03-design.md`.

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

If not on the PR branch (`{branch-name}`), check it out:

```bash
git -C "{docs_repo_path}" checkout {branch-name}
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

**Skip testplan docs-repo sync if any of these are true:**
- `04-testplan.md` does not exist AND `publish-metadata.json` does not
  contain a `testplan_file_path` field (no testplan anywhere)
- `publish-metadata.json` does not contain a `testplan_file_path` field
  (testplan was never published — changes are applied locally only; re-run
  `/publish` to include the testplan in the docs repo)

**If `04-testplan.md` does NOT exist but `publish-metadata.json`
contains `testplan_file_path`** (testplan was removed), remove the
published testplan from the docs repo if it is still tracked:

Check whether the file is tracked:

```bash
git -C "{docs_repo_path}" ls-files --error-unmatch "{testplan_file_path}"
```

- If exit 0 (file is tracked), remove it:

```bash
git -C "{docs_repo_path}" rm "{testplan_file_path}"
```

- If exit 1 with "did not match any file(s) known to git" (file is not
  tracked — already deleted by another process), skip the `git rm`.
- If any other non-zero exit (unexpected git error), stop and report
  the error to the user. Do not proceed with metadata cleanup until the
  error is resolved.

In either case, remove `testplan_file_path` from `publish-metadata.json`.

**If both `04-testplan.md` exists and `publish-metadata.json` contains
`testplan_file_path`**, copy the testplan to the docs repo:

```bash
cp ".artifacts/design/{issue-key}/04-testplan.md" "{docs_repo_path}/{testplan_file_path}"
```

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

Write the reply to a temp file to avoid shell metacharacter issues.
Use the file-writing tool (Write) to create the file — do not use a
shell heredoc, as reply content containing the delimiter string would
break the heredoc.

Write `{approved reply text}` to `.artifacts/design/{issue-key}/tmp-reply.md`.

Route each comment based on its `type` field from the fetch output:

**When `type` is `"line_comment"`**, reply in-thread using the comment's
`id`:

```bash
python3 "$PR_COMMENTS_SCRIPT" reply --owner {owner} --repo {repo} --pr {pr-number} --body-file .artifacts/design/{issue-key}/tmp-reply.md --comment-id {id}
```

**When `type` is `"review"` or `"top_level"`**, post a top-level PR
comment (omit `--comment-id`):

```bash
python3 "$PR_COMMENTS_SCRIPT" reply --owner {owner} --repo {repo} --pr {pr-number} --body-file .artifacts/design/{issue-key}/tmp-reply.md
```

If the reply command fails (non-zero exit), report the error and
continue to the next comment **without calling `log`** — the comment
must remain unaddressed so it is retried on the next respond round.

After each **successful** reply, record the `id` in the responses log:

```bash
python3 "$PR_COMMENTS_SCRIPT" log --responses-log .artifacts/design/{issue-key}/responses.jsonl --comment-id {id}
```

**If the log command fails (non-zero exit), stop immediately** — do not
post the next reply.  Continuing without logging would allow duplicate
replies on the next respond round.

Delete the temp file after posting:

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
(story `Validated by` in Design Reference) is consistent. If the cascade
reveals an inconsistency not caught during Step 4 (e.g., a story
references a TC ID that was removed), fix it before proceeding.

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
- `.artifacts/design/{issue-key}/04-testplan.md` (updated if testplan feedback was applied)
- `.artifacts/design/{issue-key}/06-stories/epic-{N}/story-{NN}-{slug}.md` (Validated by updated in Design Reference if testplan changed)
- `.artifacts/design/{issue-key}/09-review-responses.md`

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Design changes made
- Decomposition impact assessment
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
