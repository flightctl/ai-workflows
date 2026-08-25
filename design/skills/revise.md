---
name: revise
description: Incorporate user feedback into the design document and/or task breakdown.
---

# Revise Design Skill

You are an editor. Your job is to incorporate the user's feedback into
the existing design document and/or task breakdown while maintaining
consistency across all artifacts.

## Your Role

Read the user's feedback, apply changes, and ensure all artifacts remain
coherent after edits. This phase is repeatable — the user may request
multiple rounds of revision.

## Critical Rules

- **Change only what's requested.** Do not "improve" sections the user didn't mention.
- **Maintain consistency across artifacts.** If a design change affects the decomposition, flag it. If a story change contradicts the design, flag it.
- **Preserve traceability.** If new content is added, note its source.
- **Show your changes.** After revising, summarize what changed so the user can verify.
- **No scope reduction.** Do not silently simplify, even when revising.
- **Filename stability after sync.** If `sync-manifest.json` exists, epic and story filenames are locked — they serve as idempotency keys in Jira. Do not rename, renumber, or delete synced files. New stories must use the next available number. New epics must use the next available number (gaps are fine).
- **Logical deletion via marker.** When the user wants to remove a synced story or epic, do not delete the file. Instead, add `status: removed` to the file's YAML frontmatter. The file stays on disk so `/sync` can detect the removal and close the corresponding Jira issue.

## Process

### Step 1: Read Current Artifacts

Read and follow `../../_shared/recipes/template-override-resolution.md`
with `WORKFLOW=design`, `TEMPLATE_FILE=design.md`. Per that recipe's
"Using the Resolved Files" guidance, treat the section-number examples
below (e.g., "Section 4.3") as illustrations of the built-in template only.

Determine which artifacts exist and read them:
- `.artifacts/design/{issue-key}/01-context.md` (requirements context with FR/NFR IDs)
- `.artifacts/design/{issue-key}/02-research.md` (if exists — research findings)
- Clarifications — use the path from `01-context.md`'s PRD Summary section
  (if one was recorded) — for locked decisions
- `.artifacts/design/{issue-key}/03-design.md` (design document)
- `.artifacts/design/{issue-key}/05-epics.md` (epic metadata, if exists)
- `.artifacts/design/{issue-key}/06-stories/` (epic and story files, if exist)
- `.artifacts/design/{issue-key}/07-coverage.md` (coverage matrix, if exists)
- `.artifacts/design/{issue-key}/04-testplan.md` (testplan, if exists)
- `.artifacts/design/{issue-key}/sync-manifest.json` (if exists — means
  epics/stories have been synced to Jira and filenames are locked)

If the user edited `03-design.md` manually since the last workflow phase, read
and follow `../../_shared/recipes/record-manual-edit.md` with `WORKFLOW=design`
and `ISSUE_KEY={issue-key}` before applying revisions.

### Step 2: Understand the Feedback

The user's feedback may target:

**Design document changes:**
- Specific edits ("Change section 4.3 to use a different API approach")
- Directional feedback ("The architecture section is too vague")
- New information ("We also need to handle X")
- Deletions ("Remove alternative Y, we already decided against it")

**Decomposition changes:**
- Epic restructuring ("Combine epics 2 and 3")
- Story adjustments ("Story 1.3 is too large, split it")
- Sizing corrections ("Epic 2 should be L, not M")
- Ordering changes ("Story 2.1 should come before 1.3")

**Pre-sync vs post-sync behavior:**

If `sync-manifest.json` does **not** exist (pre-sync), all restructuring
operations are allowed — rename files, renumber, combine, split freely.

If `sync-manifest.json` **exists** (post-sync), filenames are locked:
- **Combining epics:** Do not delete synced epic files or move stories
  to different directories. Keep synced story files at their original
  paths — `/sync` uses filenames as idempotency keys and path changes
  cause duplicate Jira creation. Instead, update the surviving epic's
  content to reflect the combined scope and add `status: removed` to
  the absorbed epic's YAML frontmatter so `/sync` will close it in
  Jira. Add any net-new work as new story files using the next
  available number in the target epic. If the user wants to reorganize
  epics and stories in Jira, that is a manual Jira operation (move
  stories between epics in Jira's UI). Note: stories under the absorbed
  epic remain tracked in the manifest under their original epic.
  `/sync` will continue to update them if their content changes, but
  their Jira parent link still points to the now-closed epic. Move
  them to the surviving epic in Jira's UI.
- **Splitting stories:** Keep the original story file. Add new stories
  with the next available number (e.g., if story-03 is the last, add
  story-04 and story-05).
- **Reordering:** Update `05-epics.md` implementation notes to reflect
  the new order. Do not rename files — the numbering no longer implies order.

Clarify with the user if the feedback is ambiguous before making changes.

### Step 3: Apply Changes

Edit the affected artifacts:
- For specific edits: apply them directly
- For directional feedback: propose concrete changes and confirm before applying
- For new information: add it to the appropriate sections
- For deletions: remove content cleanly, checking for orphaned references

### Step 4: Consistency Check

After applying changes, verify:

**If the design document changed:**
- Do the architectural decisions still support all PRD requirements?
- Does the data model still align with the API changes?
- Are alternatives still relevant, or do they need updating?
- Do any changes contradict a locked decision from the clarifications file
  (loaded in Step 1)? If so, flag the conflict — locked decisions are binding.
- If `02-research.md` exists, do any changes contradict research findings
  or integration constraints? If the revision switches to an approach the
  research evaluated unfavorably, flag the conflict and explain the tradeoff.
- **Does the decomposition need updating?** If the design changed in ways
  that affect the epic/story breakdown (e.g., new components, changed APIs,
  different data model), flag this to the user and recommend re-running
  `/decompose`.

**If the decomposition changed:**
- Does every epic still organize around user value?
- Is each epic still standalone?
- Does every story still include functionality AND testing?
- Is the coverage matrix still accurate? Update it if stories were
  added, removed, or reassigned.
- Do story dependencies still make sense?

**If the testplan exists (`04-testplan.md`):**
- Before modifying any test cases, record the IC and requirement
  mappings of any TCs that will be removed, reassigned, or have their
  IC or requirement mapping changed (even if the TC ID is retained) —
  these pre-mutation mappings are needed for the story cascade below
  to clear stale `Validated by` references on the old stories.
- If design Interface Changes (§5) changed: update any test cases whose
  IC reference, preconditions, steps, or expected results are affected by
  the IC change. If an IC was added, consider whether new test cases are
  needed. If an IC was removed, remove or reassign test cases that
  referenced it. The Expected Results quality gate applies — no banned
  vague phrases.
- If PRD requirements changed (rare — requires PRD revision): update
  test cases anchored to changed requirements. Update TC IDs if
  requirement IDs changed.
- If test cases were added, removed, or modified, **or** if design
  Interface Changes (§5) were added, removed, or renamed: recompute the
  testplan's Overview counts and Summary table. Rebuild the Gaps
  section from the current requirement-to-TC and IC-to-TC mappings.
  Adding, removing, or renaming an IC changes the "Interface changes
  covered" totals or the identifiers in the Interface Change Coverage
  Gaps even when no test case is edited.
- If design Interface Changes (§5) were added, removed, or renamed:
  first, record the affected story paths and their current `Interface
  Changes` mappings (needed for the `Validated by` cascade below —
  after IC mutation, a story that lost its only IC can no longer be
  found by IC overlap). Then update affected non-`[DOCS]` stories'
  `Interface Changes` line in their Design Reference section **before**
  the `Validated by` cascade (the cascade uses IC overlap, so stories
  must have current ICs for correct matching). For each case:
  - **Removed IC:** Remove the IC from every story that lists it. If a
    story's `Interface Changes` becomes empty, write
    `Interface Changes: None — infrastructure prerequisite` (or ask the
    user if the story should be removed).
  - **Renamed IC:** Replace the old IC identifier with the new one in
    every story that lists it.
  - **Added IC:** Determine which stories implement the new IC using
    the same criteria as `/decompose` Step 7a (the story delivers part
    or all of the behavior the IC describes). If ownership is unclear,
    ask the user which story should claim it.
- If test cases were added, removed, or had their IC or requirement
  mapping changed: update affected non-`[DOCS]` stories' `Validated
  by` line in their Design Reference section. Skip `[DOCS]` stories
  (they lack `Interface Changes` and `Validated by` fields). Identify
  affected stories using: the current mappings for added/modified TCs,
  the pre-mutation mappings for removed/reassigned/remapped TCs, and
  the pre-IC-mutation story paths recorded above (to catch stories
  that lost their IC mapping during the IC update). Re-read each
  affected story file at
  `.artifacts/design/{issue-key}/06-stories/epic-{N}/story-{NN}-{slug}.md`
  before modifying it. Collect all TC IDs from the updated testplan
  that match this story — by IC overlap with the story's (now-updated)
  `Interface Changes`, or by requirement overlap for cross-cutting TCs
  with `Interface Change: —` — then write the updated `Validated by`
  line. If a story loses all its test cases, write:
  `Validated by: None — no behavioral test cases after testplan revision`.

### Step 5: Update Artifacts

Overwrite the affected artifact files.

If `03-design.md` was updated, read and follow
`../../_shared/recipes/capture-provenance-event.md` with `WORKFLOW=design`,
`ISSUE_KEY={issue-key}`, `PHASE=revise`, `AUTHORING_MODE=skill`.

If the design document was published, also update the docs repo copy.
Check for `.artifacts/design/{issue-key}/publish-metadata.json` and
`.artifacts/config.json`. If either file does not exist, skip the
docs repo update steps — the design has not been published yet.

If both exist:

1. Read the config to get the docs repo path
2. Read publish metadata to get the file path and `{branch-name}` (from the `branch` field)
3. Determine `{owner}/{repo}` from the `docs_repo_remote` value in the config
4. Check whether a PR branch exists:

```bash
gh pr list --repo {owner}/{repo} --head {branch-name} --state open --json number,url
```

If a PR exists, update the docs repo:

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

**Testplan docs-repo sync:**

**Skip all testplan sync steps below if any of these are true:**
- `04-testplan.md` does not exist and `publish-metadata.json` does not
  contain a `testplan_file_path` field (no testplan anywhere)
- `04-testplan.md` exists but `publish-metadata.json` does NOT contain
  `testplan_file_path` (testplan was created after initial publish) —
  note to the user: "Testplan exists locally but was not included in
  the original publish. Re-run `/publish` to include it in the docs
  repo."

**If `04-testplan.md` does NOT exist but `publish-metadata.json`
contains `testplan_file_path`** (testplan was removed during revision),
remove the published testplan from the docs repo if it is still tracked:

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

**If `04-testplan.md` exists and `publish-metadata.json` contains
`testplan_file_path`**, copy the testplan to the docs repo:

```bash
cp ".artifacts/design/{issue-key}/04-testplan.md" "{docs_repo_path}/{testplan_file_path}"
```

```bash
git -C "{docs_repo_path}" add "{design_file_path}"
```

```bash
git -C "{docs_repo_path}" add "{testplan_file_path}"
```

```bash
git -C "{docs_repo_path}" commit -m "Design {issue-key}: revise — {brief description}"
```

```bash
git -C "{docs_repo_path}" push
```

### Step 6: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Design Changes
- Section 4.3: Changed API approach from X to Y
- Section 4.2: Added new field Z to the data model

### Decomposition Changes
- Epic 2: Split Story 2.3 into 2.3 and 2.4
- Coverage matrix: Updated to reflect new story mapping

### Testplan Changes
- {TC-FR1-03 added — new IC in design §5}
- {TC-NFR2-01 updated — expected result changed to match revised design}
- {TC-FR2-02 removed — IC-4 removed from design}
- {Omit this section if the testplan did not change or does not exist}

### Consistency Updates
- Section 9: Added open question about performance impact of new approach

### Decomposition Impact
- Design changes affect Epic 1 stories — recommend re-running /decompose
```

**If `sync-manifest.json` exists and any synced decomposition files were
modified**, append a Jira sync section to the revision summary. For each
modified file that appears in the manifest, look up its Jira key and
construct a browse URL using the Jira integration:

```markdown
### Jira Issues Pending Sync

The following artifacts were modified since the last sync. Re-run
`/sync` to push these changes to Jira:

| Artifact | Jira Issue | What Changed |
|----------|------------|--------------|
| `06-stories/epic-1-image-building.md` | [EDM-6789]({browse-url}) | Acceptance criteria updated |
| `06-stories/epic-1/story-02-add-validation.md` | [EDM-6842]({browse-url}) | Description revised |
```

## Output

- `.artifacts/design/{issue-key}/03-design.md` (updated, if design changed)
- `.artifacts/design/{issue-key}/05-epics.md` (updated, if decomposition changed)
- `.artifacts/design/{issue-key}/06-stories/epic-*.md` (updated, if epics changed)
- `.artifacts/design/{issue-key}/06-stories/epic-*/story-*.md` (updated, if stories changed)
- `.artifacts/design/{issue-key}/07-coverage.md` (updated, if coverage changed)
- `.artifacts/design/{issue-key}/04-testplan.md` (updated, if testplan changed)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Whether design changes require re-running `/decompose`
- Any remaining open questions or flagged assumptions

Then **re-read the controller** (`controller.md`) for next-step guidance.
