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
- **Identity stability.** Epic and story filenames, numbers, and containing paths are fixed from creation — do not rename, renumber, or move files. New stories must use the next available number (above any existing or removed file's number in that epic; gaps are fine). New epics must likewise use the next available number. Do not rename or reparent an epic in a way that changes its existing stories' qualified identity or containing path.
- **Logical deletion via marker.** When the user wants to remove a story or epic, do not delete the file. Instead, add `status: removed` to the file's YAML frontmatter. The file stays on disk and its number is reserved. For already-synced items, `/sync` detects the marker and closes the corresponding Jira issue. For never-synced items, `/sync` skips them — no Jira issue exists to close, but the file is retained and its number remains reserved.

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
- **Validation artifacts:** Before reading any testplan or companion,
  resolve the validation index:
  Set `SKILL_DIR` to the canonical directory of this loaded skill file
  (resolved from the path provided by the phase dispatcher or file-read
  context, following symlinks). If the loaded file path is unavailable,
  stop and report — do not fall back to `$HOME`, `BASH_SOURCE`, or the
  current working directory:
  ```bash
  # SKILL_DIR: set by the agent to this skill file's canonical directory
  VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
  python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{issue-key}"
  ```
  If exit 0, parse the JSON array to discover all artifact paths.
  Read only the returned artifacts. If exit non-zero (malformed index,
  missing files, symlinks), stop and report. If the result is empty
  and `04-testplan.md` exists, fall back to reading it directly
  (legacy). This resolution happens here so the correct artifact set
  is known before any testplan content is read.
- `.artifacts/design/{issue-key}/sync-manifest.json` (if exists —
  records Jira key mappings and content-hash checkpoints from
  previous `/sync` runs; may be partial if sync was interrupted or
  not all items were created)

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

**Identity stability:** Story and epic filenames, numbers, and
containing paths are fixed from creation — do not rename, renumber,
or move files regardless of whether `/sync` has been run. This
matches criterion 7 in `/decompose` and ensures `/sync`'s filename-
based idempotency is always safe.

- **Combining epics:** Do not delete epic files or move stories to
  different directories. If any child work under the absorbed epic is
  intended to remain active, do **not** mark the absorbed epic
  `status: removed` — keep it as an active container and update its
  content, scope, and implementation notes to reflect the
  consolidation. Marking an epic `status: removed` retires it and
  all its children: `/sync` will cascade-close already-synced active
  children and skip never-synced ones. Only mark the epic removed
  when all its child work is intentionally retired too. Add any
  net-new work as new story files using the next available number in
  the target epic. Physical merge or reparenting of retained stories
  to a different epic directory is not supported by the current
  file-authoritative model — manual Jira reparenting does not update
  local file/manifest ownership used by `/sync` and is not a
  workaround for retaining children under a removed source epic. If
  the user requests a physical merge rather than logical
  consolidation, flag the constraint and request clarification.
- **Splitting stories:** Keep the original story file. Add new stories
  with the next available number (above any existing or removed
  file's number in that epic).
- **Reordering:** Update `05-epics.md` implementation notes to reflect
  the new order. Do not rename files — numbering does not imply order.

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

**`[DOCS]` story re-evaluation (if any `[DOCS]` story is affected):**

Re-evaluate every affected `[DOCS]` story against all seven criteria
in `decompose.md`. A `[DOCS]` story is affected when this revision
changed: (a) the `[DOCS]` file itself, (b) a listed or newly relevant
`[DEV]`/`[UI]` contributor's artifacts — including new, removed,
renamed, or reopened stories whose user-facing surface falls within the `[DOCS]`
story's scope, (c) design content that alters the story's reader,
scope, AC, assumptions, or open-question markers — including resolved
`[Open: §9.N]` items even without API/CLI shape changes, (d) ICs
covered by the story, (e) a listed contributor effectively retired
through its parent epic being marked `status: removed` — even when
the contributor's own story file is unchanged, its parent's removal
logically retires it, or (f) a parent epic explicitly restored
(approved removal of its `status: removed` marker) — children
without their own `status: removed` become effectively active
again and should be reconsidered as contributors, while children
with their own `status: removed` remain individually retired
regardless of parent restoration.

For each affected `[DOCS]` story, re-read the file and update
Documentation Inputs, Contributing stories, and Dependencies to
reflect the current contributor set — but preserve any existing
prerequisite dependencies (e.g., infrastructure stories) that are
not part of the contributing-story inventory.

**If validation artifacts exist:**

Resolve the validation index **before** reading any artifact files.
Use the CLI helper to validate and resolve paths:

Set `SKILL_DIR` as above (the agent's file-load context), then resolve:

```bash
VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{issue-key}"
```

If the command exits 0, parse the JSON array to discover all
validation artifacts. If it exits non-zero, stop and report the
error. If the result is empty and `04-testplan.md` exists, fall
back to reading it directly (legacy single-testplan behavior).

For **each** validation artifact (primary testplan and any companions):
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
  Interface Changes (§5) were added, removed, or renamed, OR Review
  and Qualification Gates were added, changed, or removed: recompute the
  artifact's Overview counts, Summary table, and Test Case Index per
  the counting rules in the draft skill's Step 9a: each parameterized
  row counts individually toward the total, priority, and automation
  counts; requirement and IC coverage ratios count distinct mapped
  values once each; the Index has one row per TC ID. Rebuild the Gaps
  section from the current requirement-to-TC and IC-to-TC mappings
  and the Review and Qualification Gates mappings. For requirements
  or ICs covered only by gates, reference the gate rather than
  listing them as uncovered. Treat ICs covered by qualification
  gates as covered — do not report a gap for gate-covered ICs.

**Cross-artifact consistency:** After updating all artifacts, verify
that TC IDs are unique across the full artifact set. If a revision
introduces a TC ID that conflicts with an existing ID in another
artifact, resolve the conflict by reallocating the new ID above the
feature-wide high-water mark for that requirement group.

**Adding or removing companion plans during revision:**

- **Adding:** If the user requests a new companion plan, create it
  following the companion rules from the draft skill's Step 9e.
  If `validation-index.json` does not exist and `04-testplan.md`
  exists, first create the index. Resolve the script path before
  each command — do not assume `VALIDATION_INDEX_SCRIPT` survives
  from a prior shell:

  Set `SKILL_DIR` as above (the agent's file-load context), then resolve:
  ```bash
  VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
  python3 "$VALIDATION_INDEX_SCRIPT" build-legacy ".artifacts/design/{issue-key}" ".artifacts/design/{issue-key}/validation-index.json"
  ```

  If the command fails, stop and report the error.
  Update `validation-index.json` to include the new entry. After
  adding, validate:

  ```bash
  VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
  python3 "$VALIDATION_INDEX_SCRIPT" validate --local ".artifacts/design/{issue-key}/validation-index.json" --artifact-dir ".artifacts/design/{issue-key}"
  ```

  If validation fails, correct the errors before proceeding.
- **Removing:** If the user requests removing a companion, delete its
  local file. Update `validation-index.json` to remove the entry.
  During the docs-repo sync below, the published copy is removed.
  Do not remove the primary testplan without explicit user confirmation.

The remaining story cascades apply only when decomposition artifacts
exist. If `.artifacts/design/{issue-key}/06-stories/` is absent (for
example, `/decompose` was deferred per the controller), skip the
`Interface Changes` and `Validated by` story updates below — the testplan
updates above are complete on their own.

- If design Interface Changes (§5) were added, removed, or renamed:
  first, record the affected story paths and their current `Interface
  Changes` mappings (needed for the `Validated by` cascade below —
  after IC mutation, a story that lost its only IC can no longer be
  found by IC overlap). Then update affected non-`[DOCS]` stories'
  `Interface Changes` line in their Design Reference section **before**
  the `Validated by` cascade (the cascade uses IC overlap, so stories
  must have current ICs for correct matching). For each case:
  - **Removed IC:** Remove the IC from every story that lists it. A story
    losing its last IC does not by itself make it an infrastructure
    prerequisite — it may still deliver PRD behavior or carry valid test
    cases. Do not auto-write the infrastructure marker. Instead, ask the
    user how to reclassify the story:
    - Keep it with a valid replacement `Interface Changes` mapping if it
      still implements an interface; or
    - Mark it `Interface Changes: None — infrastructure prerequisite`
      only after the user confirms that classification; or
    - Logically remove it. For a story already synced to Jira, set
      `status: removed` and retain the file on disk (never delete a
      synced story file).
  - **Renamed IC:** Replace the old IC identifier with the new one in
    every story that lists it.
  - **Added IC:** Determine which stories implement the new IC using
    the same criteria as `/decompose`'s IC-mapping sub-step (the story delivers part
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
  before modifying it. Collect all TC IDs **across all validation
  artifacts** (primary testplan and companions) that match this
  story — by IC overlap with the story's (now-updated) `Interface
  Changes`, or by requirement overlap for cross-cutting TCs with
  `Interface Change: —` — then write the updated `Validated by`
  line. If a story loses all its test cases, write:
  `Validated by: None — no behavioral test cases after testplan revision`.

**`[DOCS]` reconciliation after cascades.** After the IC and testplan
story cascades above complete, recompute the affected `[DOCS]` set
from the resulting post-cascade state — do not rely on the initial
affected set computed before the cascades, which may miss `[DOCS]`
stories newly affected by IC reassignment, contributor retirement
(including through parent epic removal), contributor restoration
(including through parent epic restoration), or testplan changes
discovered during the cascade.  For each `[DOCS]` story in the
recomputed set, re-read the file and reconcile its Documentation
Inputs, Contributing stories, and Dependencies against the current
contributor set.  Preserve unrelated prerequisite Dependencies,
existing IDs/paths, and existing removal/restore approval semantics.
After all reconciliation edits, reapply the canonical seven `[DOCS]`
criteria from `decompose.md` to each edited `[DOCS]` story before
proceeding to Step 5.

### Step 5: Update Artifacts

Overwrite the affected artifact files.

If `03-design.md` was updated, read and follow
`../../_shared/recipes/capture-provenance-event.md` with `WORKFLOW=design`,
`ISSUE_KEY={issue-key}`, `PHASE=revise`, `AUTHORING_MODE=skill`.

If `03-design.md` was updated, read and follow
`../../_shared/recipes/render-provenance-footer.md` with `WORKFLOW=design`,
`ISSUE_KEY={issue-key}`, and `TARGET_FILE` set to the absolute source-repo
path to `.artifacts/design/{issue-key}/03-design.md`.

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

**Validation artifact docs-repo sync:**

Set `SKILL_DIR` as above (the agent's file-load context), then resolve:

```bash
VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
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

Before capture, remove any existing snapshot from a previous run
(substitute the actual Jira issue key for `{issue-key}`):

```bash
rm -f -- ".artifacts/design/{issue-key}/prev-published-index.json"
```

If the removal command fails (non-zero exit other than file-not-found),
stop and report the error.

**Snapshot PREVIOUS state:** If
`{docs_repo_path}/{feature-dir}/validation-index.json` exists,
validate it at its source before copying — to ensure it conforms
to the published schema and is trustworthy for later removal
decisions:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" validate --published "{docs_repo_path}/{feature-dir}/validation-index.json" || { echo "Published index validation failed — aborting" >&2; exit 1; }
```

If validation fails, **stop and report** — do not copy or proceed
with a malformed published index. Only after validation passes,
capture the snapshot:

```bash
cp "{docs_repo_path}/{feature-dir}/validation-index.json" ".artifacts/design/{issue-key}/prev-published-index.json" || { echo "Snapshot copy failed" >&2; exit 1; }
```

If the index does not exist but
`{docs_repo_path}/{feature-dir}/testplan.md` exists (legacy), create
the minimal published snapshot:

```json
{
  "schema_version": "1.0",
  "primary_testplan": "testplan.md",
  "artifacts": [{"file": "testplan.md", "type": "testplan"}]
}
```

Save to `.artifacts/design/{issue-key}/prev-published-index.json`.
If neither exists, there is no previous set — no snapshot is captured
and the empty previous set is correct (first publish).

**Removal preflight (non-empty current set with previous snapshot):**
Before copying any artifacts or overwriting the published index,
identify proposed removals so the user can approve them first.
Transform the current local index to a candidate published index
under `.artifacts`:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{issue-key}/validation-index.json" ".artifacts/design/{issue-key}/candidate-published-index.json" --trusted-output-base "." || { echo "Transform failed — aborting" >&2; exit 1; }
```

If the transform exits non-zero, stop and report the error — do not
proceed to the diff. Remove any stale `candidate-published-index.json`
from a prior interrupted run before continuing.

Diff the previous snapshot against the candidate:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{issue-key}/prev-published-index.json" ".artifacts/design/{issue-key}/candidate-published-index.json" || { echo "Diff failed — aborting" >&2; exit 1; }
```

If the diff exits non-zero, stop and report the error — do not proceed
to artifact copy or metadata update.

If the `removed` list is non-empty, present each removal with its full
published path `{release}/{feature}/{filename}` and require named
confirmation of each removal before proceeding. The full path ensures
users can distinguish removals across features. An earlier explicit
named-artifact approval (from a prior `/revise` step that named these
specific files with full paths) counts as confirmation only if the
artifact's published state has not changed since approval — a new
publish cycle resets approvals. Generic update approval does not
constitute named removal approval. If the user declines, stop — preserve
published artifacts and metadata unchanged. Clean up the candidate file
after the preflight completes.

If no previous snapshot was captured or the current set is empty, skip
this preflight.

If both the current set and the previous set are empty and
publish-metadata has no `validation_artifacts` or
`testplan_file_path`, skip validation artifact sync below (copy,
index transform, and removal steps). The design file staging and
commit must still proceed — see the design staging step below.

If the docs repo has published artifacts but local
`validation-index.json` does not exist (artifacts were published
previously but no local index exists now), note to the user:
"Validation artifacts were previously published but no local index
exists. Re-run `/publish` to resync, or create a local index before
proceeding."

**Validate current set:** For each artifact in the current set,
verify its local file exists and is not a symlink. A listed
artifact whose local file is missing or is a symlink is an error —
stop and report. Do not delete published content based on a missing
local file.

**Copy ALL current artifacts** (not just previously tracked — handles
new companions added during revision). Before each copy:
- Reject symlink destinations (the published_as filename itself).
- Reject any symlink ancestor in the destination path between the
  configured `{docs_repo_path}` root and the target file. Walk each
  path component of `{feature-dir}/{published_as}` below
  `{docs_repo_path}` and verify it is not a symlink. If any ancestor
  is a symlink, stop and report — the destination could escape the
  docs checkout. Symlinks and aliases at or above `{docs_repo_path}`
  itself are permitted (the checkout root may be an alias).
- Verify that any existing destination file is in the previous
  validation set (an existing file not in the previous set is
  unowned and must not be overwritten).

```bash
cp ".artifacts/design/{issue-key}/{local}" "{docs_repo_path}/{feature-dir}/{published_as}"
```

```bash
git -C "{docs_repo_path}" add "{feature-dir}/{published_as}"
```

**Stage the design file** independently of validation artifacts —
a pure design update or retirement must commit the design change
even when both validation sets are empty:

```bash
git -C "{docs_repo_path}" add "{design_file_path}"
```

**Update published index:** If the current set is non-empty,
transform and write the updated index:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{issue-key}/validation-index.json" "{docs_repo_path}/{feature-dir}/validation-index.json" --trusted-output-base "{docs_repo_path}" || { echo "Transform failed — aborting" >&2; exit 1; }
```

```bash
git -C "{docs_repo_path}" add "{feature-dir}/validation-index.json"
```

**Remove retired artifacts:** Compute the change set before
deleting anything. The comparison must use the new published index
when one was written, or an empty artifact list when the current
set is empty.

If the current set is **non-empty** and a previous snapshot exists,
execute the removals confirmed during the removal preflight. Re-diff
using the final published index to verify the set is unchanged:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{issue-key}/prev-published-index.json" "{docs_repo_path}/{feature-dir}/validation-index.json" || { echo "Diff failed — aborting" >&2; exit 1; }
```

The `removed` list must match the preflight result. If the sets
differ, stop and report before deleting. Do not re-prompt — the user
already approved these filenames in the preflight.

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
validate the previous snapshot before removal:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" validate --published ".artifacts/design/{issue-key}/prev-published-index.json"
```

If validation fails, stop and report. If it passes, present the
exact list of previously published filenames from the validated
snapshot to the user and confirm that retirement of each named
artifact is intended (the user may choose to retire all, restore
specific files, or abort). An empty current set caused by missing
local sources (rather than explicit user intent) must not silently
remove published content — stop and report the missing sources
instead of proceeding to retirement.

**If the user restores any artifact** instead of confirming its
retirement, rebuild the valid local set from the restored files:
re-run `build-legacy` or re-create `validation-index.json` to
reflect the retained artifacts, then restart resolution and
validation from Step 4. Do not continue with the empty-set
retirement flow when files have been restored — the restored
files must be validated and synced as a non-empty set. If the
restored files cannot yield a valid primary testplan, stop and
preserve published files until the user resolves the issue.

Once the user confirms the named retirements (all remaining
after any restorations), for each confirmed artifact, check
whether it is tracked and stage removal with
`git -C "{docs_repo_path}" rm -- "{feature-dir}/{filename}"`.
Skip untracked files. Remove the published `validation-index.json`
only if **all** previously published artifacts are retired. If
any artifacts are retained (partial retirement), preserve the
index with its retained entries. Use the same tracked-file
check and `git rm` for the index removal when applicable.

Update `publish-metadata.json`: set `validation_artifacts` to match
the current published set, update `testplan_file_path` to the primary
testplan's full published path (or remove if no primary testplan).

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
- {TC-FR1-03 added in testplan.md — new IC in design §5}
- {TC-NFR2-01 updated in testplan.md — expected result changed to match revised design}
- {TC-FR2-02 removed from testplan.md — IC-4 removed from design}
- {hw-validation.md added as companion — hardware qualification for NFR-3}
- {Omit this section if no validation artifacts changed or exist}

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
- `.artifacts/design/{issue-key}/04-{slug}.md` (companion artifacts updated, if applicable)
- `.artifacts/design/{issue-key}/validation-index.json` (updated, if artifacts added or removed)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Whether design changes require re-running `/decompose`
- Any remaining open questions or flagged assumptions

Then **re-read the controller** (`controller.md`) for next-step guidance.
