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

If the command exits 0 with a non-empty array, read each listed
file — the resolver already handles legacy layouts (a valid
`04-testplan.md` is included in the returned list), so only read
paths from the returned array. If the result is an empty array
`[]`, no validation artifacts exist. If the command exits non-zero,
stop and report the error.

Use the Step 1 validated artifact set only when the inputs and
context are unchanged. If the user edited artifacts, added or
removed files, or changed the design document between Step 1 and
Step 4, re-resolve before mutating — do not reuse a cached set
that may not reflect current state.

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

**Validation artifact docs-repo sync:**

Set `SKILL_DIR` to the canonical directory of this loaded skill file
(resolved from the path provided by the phase dispatcher or file-read
context, following symlinks). Each fresh shell must re-resolve this
independently:

```bash
VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
```

Derive `{feature-dir}` from `design_file_path` in publish-metadata
(e.g., `v2.1/feature-slug` from `v2.1/feature-slug/design.md`).

Read and follow `../../_shared/recipes/sync-validation-artifacts.md`
with `ISSUE_KEY={issue-key}`,
`VALIDATION_INDEX_SCRIPT="$VALIDATION_INDEX_SCRIPT"`,
`DOCS_REPO_PATH="{docs_repo_path}"`,
`FEATURE_DIR="{feature-dir}"`,
`DESIGN_FILE_PATH="{design_file_path}"`.

Complete both PREFLIGHT and APPLY phases of the recipe. The recipe
handles build/snapshot/preflight/copy/index/retirement/metadata as a
single canonical execution. Do not duplicate those steps inline.

**After the recipe's APPLY phase completes**, copy the design
document and render provenance. The recipe's APPLY created the
feature directory:

```bash
cp ".artifacts/design/{issue-key}/03-design.md" "{docs_repo_path}/{design_file_path}"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{design_file_path}"`.

Stage the design file independently of artifact existence:

```bash
git -C "{docs_repo_path}" add "{design_file_path}"
```

**Commit and push:**

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
