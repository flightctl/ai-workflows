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

**Routing validation artifact comments:** Line-level review comments
(from `gh api .../pulls/{pr-number}/comments`) include a `path` field
containing the full feature-directory-relative path (e.g.,
`v2.1/feature-slug/testplan.md`). Build the published artifact path
map from `publish-metadata.json`:

- If `validation_artifacts` exists, build a map from each artifact's
  full published path (`{release}/{feature}/{file}`) to its local
  filename. Use `design_file_path` from publish-metadata to derive
  the `{release}/{feature}` prefix. Also read the local
  `validation-index.json` to get the validated `published_as` →
  `local` mapping — this ensures the local filename used for routing
  matches the actual local artifact file.
  If `validation-index.json` is listed but cannot be read, parsed, or
  validated (via `resolve --local`), stop and report the error — do
  not build a routing map from unvalidated metadata. If
  `validation_artifacts` in metadata lists files that do not match the
  local `validation-index.json` entries:
  - If the local index has **zero** artifacts (empty set) while
    metadata lists previously published artifacts, this is a proposed
    **empty-set retirement** — do not stop on inconsistency. Retain
    the previous validated set for comment routing and proceed to sync;
    the retirement confirmation step will require explicit approval of
    each named file removal before any deletion occurs.
  - If the local index is **non-empty** but its entries do not match
    metadata, stop and report the inconsistency — a mismatched
    non-empty set is a genuine error.
- If `validation_artifacts` is absent, fall back to `testplan_file_path`
  as the sole entry (maps to `04-testplan.md` locally).

Route comments using exact full-path matching against this map — not
basename matching, which would collide if multiple features share a
review or if non-artifact files share a basename:

- Comments with `path` exactly matching a published validation
  artifact path are categorized as **Testplan feedback** and tagged
  with the specific artifact's local filename for routing in Step 4.
- Top-level PR comments (from `gh pr view --json comments`) do not
  carry a `path`. For these, inspect the comment body: if it
  references test case IDs matching the pattern `TC-` followed by a
  requirement identifier, or discusses adding, modifying, or removing
  test cases, categorize as **Testplan feedback**. To resolve which
  artifact owns a referenced TC ID, search each validation artifact
  for the exact TC ID heading (`#### TC-{id}:`). If the TC ID is
  found in exactly one artifact, route to that artifact. If found in
  none, flag the unknown TC ID to the user. Do not use substring
  matching — require exact TC ID heading matches.
- When a top-level comment references TC IDs from multiple artifacts,
  or mentions artifact filenames explicitly, note all affected
  artifacts and present per-artifact changes in Step 3.
- When a comment could apply to multiple validation artifacts and the
  intent is ambiguous (e.g., a top-level comment says "add a security
  test case" but both a primary testplan and a security companion
  exist), present the ambiguity to the user in Step 3 and ask which
  artifact to modify. Do not guess or silently pick one.
- Comments on files NOT in the validation artifact set (e.g.,
  `design.md`, unrelated files) are routed to their normal categories
  — they are not discarded or reclassified. Out-of-set comments
  remain visible and correctly classified.

When uncertain, categorize as the next-best-fit category and let the
user reclassify during Step 3.

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
**Target artifact:** testplan.md (04-testplan.md)
**Proposed response:** {suggested reply}
**Testplan change needed:** {modify TC-FR2-01 expected result / add TC-FR2-03 / remove TC-FR1-02}
**Cascade:** Update affected stories' Validated by in Design Reference

### Comment 4 — {reviewer} (top-level, multi-artifact)
> {quoted comment text referencing TC IDs from multiple artifacts}

**Category:** Testplan feedback
**Target artifacts:** testplan.md (TC-FR2-01), hw-validation.md (TC-NFR3-02)
**Proposed response:** {suggested reply}
**Changes needed:** {per-artifact changes}
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
feedback), apply them to the correct artifact file based on the **Target
artifact** identified in Step 3. Each artifact is identified by its
published filename (e.g., `testplan.md`) and maps to its local filename
via `validation-index.json` (e.g., `04-testplan.md`). If
`validation-index.json` does not exist, the sole artifact is
`04-testplan.md` (legacy behavior).

Apply changes in this order:

1. **Modify the target artifact file.** Before making any changes:
   - Record the IC and requirement mappings of any test cases that
     will be removed, reassigned, or have their IC or requirement
     mapping changed (even if the TC ID is retained) — both are needed
     for the cascade in step 2 (IC mappings for IC-based matching,
     requirement mappings for cross-cutting TCs with `Interface
     Change: —`).
   - Identify which requirement groups will receive **new TC IDs** in
     this mutation round (additions or ID-reassignments). For each
     such group, build a **reserved-ID high-water mark** before
     applying any edits in the batch: scan all current TC IDs under
     that group's `### FR-*` / `### NFR-*` heading **across all
     validation artifacts** (including any about to be removed —
     deletion never releases a reserved sequence) and record the
     highest sequence number. If reliable
     context is available (e.g., prior document versions, review
     comments, or provenance metadata that names previously retired
     IDs), include any retired ID higher than the current maximum.
     When the historical high-water cannot be reliably established
     for an existing group receiving new IDs — even if the live IDs
     are contiguous or the group is currently empty — stop and ask
     for the missing history; do not infer that no retired IDs exist
     from the absence of visible gaps. All allocating-group
     high-water checks must pass before any mutations begin in the
     batch — do not partially apply edits to other groups while an
     allocation-blocker is unresolved. A genuinely new requirement
     group with confirmed no prior allocation may start at 01.
     Groups that receive no new IDs in this round (title edits,
     content changes, metadata updates, parameter-row edits, or
     deletion-only changes that preserve existing IDs) require no
     history or high-water validation. Missing history for a
     non-allocating group is not a prerequisite and must not block
     the batch. New IDs are always allocated above the high-water
     mark.

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
     genuinely new requirement group with confirmed no prior
     allocation, start at 01. Never
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
     mutation) state **across all validation artifacts** (primary
     testplan and companions): collect all TC IDs that match this
     story (by IC overlap or requirement-based fallback for `—` TCs),
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

**Sync all validation artifacts to the docs repo.**

Resolve the shared validation index script:

```bash
VALIDATION_INDEX_SCRIPT="${HOME}/.ai-workflows/design/scripts/validation_index.py"
```

Derive `{feature-dir}` from `design_file_path` in publish-metadata
(e.g., `v2.1/feature-slug` from `v2.1/feature-slug/design.md`).

**Build CURRENT set:** Resolve the current local artifacts:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{issue-key}"
```

If the command exits 0, parse the JSON array (may be empty `[]`).
If the command exits non-zero, a validation error occurred — **stop
and report the error.** Do not fall back to legacy behavior when a
malformed index is present.

If `validation-index.json` does not exist in
`.artifacts/design/{issue-key}` and `04-testplan.md` exists (legacy
layout), build a normalized index first with `build-legacy`, then
re-run `resolve --local`.

**Validate current set:** For each artifact in the current set,
verify its local file exists and is not a symlink. A listed
artifact whose local file is missing or is a symlink is an error —
stop and report to the user. Do not delete published content based
on a missing local file.

**Snapshot PREVIOUS state:** Before capture, remove any existing
`.artifacts/design/{issue-key}/prev-published-index.json`. If the
removal fails (non-zero exit other than file-not-found), stop and
report the error. Then: if
`{docs_repo_path}/{feature-dir}/validation-index.json` exists, copy
it to `.artifacts/design/{issue-key}/prev-published-index.json`. If
it does not exist but `{docs_repo_path}/{feature-dir}/testplan.md`
exists (legacy), create the minimal published snapshot:

```json
{
  "schema_version": "1.0",
  "primary_testplan": "testplan.md",
  "artifacts": [{"file": "testplan.md", "type": "testplan"}]
}
```

Save to `.artifacts/design/{issue-key}/prev-published-index.json`.
If neither exists, there is no previous set — skip the snapshot
and continue with an empty previous set.

**Distinguish absent from failed.** When copying an existing
published index or building a legacy snapshot, check that the copy
or write succeeded. If a published `validation-index.json` or
legacy `testplan.md` exists at the source but the snapshot file
could not be created (I/O error, permission denied), **stop and
report** — do not continue with an empty previous set when a
prior publication exists. An empty previous set is correct only
when no prior published state exists.

**Validate the snapshot if one was captured.** Before copying any
current artifacts or overwriting the published index, validate the
captured snapshot.

```bash
if [ -f ".artifacts/design/{issue-key}/prev-published-index.json" ]; then
  python3 "$VALIDATION_INDEX_SCRIPT" validate --published ".artifacts/design/{issue-key}/prev-published-index.json"
fi
```

If validation fails, **stop and report** — do not proceed with
sync using a malformed previous snapshot. The snapshot must be
corrected or removed before continuing.

**Skip sync entirely** if both current and previous sets are empty
and publish-metadata has no `validation_artifacts` or
`testplan_file_path`.

**Copy ALL current artifacts** to the docs repo (not just previously
tracked ones — this handles new companions added during respond).
Before each copy:
- Reject any symlink ancestor in the destination path between
  `{docs_repo_path}` and the target file. If any path component
  below the docs repo root is a symlink, stop and report — the
  destination could escape the docs checkout. Symlinks at or above
  `{docs_repo_path}` itself are permitted.
- Reject symlink destinations (the published filename itself).
- Verify that any existing destination file is in the previous
  validation set (an existing file not in the previous set is
  unowned and must not be overwritten).

```bash
cp ".artifacts/design/{issue-key}/{local}" "{docs_repo_path}/{feature-dir}/{published_as}"
```

```bash
git -C "{docs_repo_path}" add "{feature-dir}/{published_as}"
```

**Update the published validation-index.json:** If the current set
is non-empty, transform and write the updated index:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{issue-key}/validation-index.json" "{docs_repo_path}/{feature-dir}/validation-index.json" --trusted-output-base "{docs_repo_path}"
```

```bash
git -C "{docs_repo_path}" add "{feature-dir}/validation-index.json"
```

**Remove retired artifacts:** Compute the change set before
deleting anything. The comparison must use the new published index
when one was written, or an empty artifact list when the current
set is empty.

If the current set is **non-empty** and a previous snapshot exists:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{issue-key}/prev-published-index.json" "{docs_repo_path}/{feature-dir}/validation-index.json"
```

For each filename in the `removed` list:

```bash
git -C "{docs_repo_path}" ls-files --error-unmatch "{feature-dir}/{stale-filename}"
```

If tracked, stage its removal:

```bash
git -C "{docs_repo_path}" rm -- "{feature-dir}/{stale-filename}"
```

If not tracked (already removed), skip. If the check or removal
produces an unexpected error, stop and report.

If the current set is **empty** and the previous set had artifacts,
present the exact filenames from the previous snapshot to the user
and ask for explicit confirmation before proceeding:

List the filenames:
- For each artifact in the previous snapshot, show: `{feature-dir}/{filename}`
- Show: `{feature-dir}/validation-index.json` (if the previous
  publication included one)

Ask the user: **"The following published validation artifacts will
be removed. Confirm retirement, or restore the local artifact set
and re-run."** The user must explicitly confirm removal of these
specific filenames. Generic publish or review approval is not
sufficient — the user must acknowledge that these files are
intentionally being retired.

If the user declines or does not confirm, stop cleanup — preserve
published artifacts and metadata unchanged. Do not proceed with
deletion or metadata updates.

If the user confirms, validate the previous snapshot before removal:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" validate --published ".artifacts/design/{issue-key}/prev-published-index.json"
```

If validation fails, stop and report. If it passes, for each
listed artifact, check whether it is tracked and stage removal
with `git -C "{docs_repo_path}" rm -- "{feature-dir}/{filename}"`.
Skip untracked files. Remove the published `validation-index.json`
only if the previous publication included one (skip for legacy-only
snapshots that had only `testplan.md`). Use the same tracked-file
check and `git rm` for the index removal.

**Update publish-metadata.json:** Read, update `validation_artifacts`
to match the current published set, update `testplan_file_path` to
the primary testplan's full published path (or remove it if no
primary testplan), and write back.

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

**`[DOCS]` story re-evaluation:** If decomposition artifacts exist
(`06-stories/`), re-evaluate every affected `[DOCS]` story against
all seven criteria in `decompose.md`. A `[DOCS]` story is affected
when this round changed: (a) the `[DOCS]` file itself, (b) a listed,
newly relevant, removed, renamed, or reopened `[DEV]`/`[UI]`
contributor's artifacts, (c) design
content that alters the story's reader, scope, AC, assumptions, or
open-question markers — including resolved `[Open: §9.N]` items even
without API/CLI shape changes, or (d) ICs covered by the story.

When contributors change, update Documentation Inputs, Contributing
stories, and Dependencies to reflect the current contributor set —
add dependencies for newly required contributors, remove obsolete
contribution-only entries, but preserve legitimate unrelated
prerequisite dependencies. Apply all fixes before proceeding.

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
- `.artifacts/design/{issue-key}/04-{slug}.md` (companion artifacts updated if feedback was applied)
- `.artifacts/design/{issue-key}/validation-index.json` (updated if artifacts were added or removed)
- `.artifacts/design/{issue-key}/06-stories/epic-{N}/story-{NN}-{slug}.md` (Validated by updated in Design Reference if testplan changed)
- `.artifacts/design/{issue-key}/09-review-responses.md`

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Design changes made
- Decomposition impact assessment
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
