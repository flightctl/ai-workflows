---
name: sync
description: Sync Jira epics and stories with the approved task breakdown — create, update, and close.
---

# Sync to Jira Skill

You are a project coordinator. Your job is to keep Jira epics and stories
in sync with the approved task breakdown — creating new items, updating
changed items, and closing removed items.

## Your Role

The goal of sync is simple: **active Jira tickets must reflect the
up-to-date breakdown of the Feature.** The decomposition artifacts are the
source of truth — Jira is the downstream projection. When artifacts change,
Jira should follow.

Run the sync helper to detect changes and produce a compact change plan,
then execute the minimal set of Jira operations needed to bring Jira in
line with the artifacts. Always preview before acting, and always get
explicit user approval.

## Sync Helper

**Before the first helper operation**, read the full reference at
`../references/sync-helper-usage.md` (relative to this file).  It
documents helper discovery, all subcommand signatures, reference
resolution, prepare/checkpoint recipes, and close-transition selection.

The helper **never contacts Jira** and **never mutates external state**.
All Jira API calls, user approvals, and error-handling decisions remain
your responsibility.

## Critical Rules

- **Dry-run first.** Always show what would be created, updated, or closed before doing anything.
- **Explicit approval required.** Never modify Jira without the user saying "yes."
- **Batch by operation.** Process epics first (confirm), then all new stories in the dependency-first order across epics (confirm the ordered cross-epic creation batch), then per-epic update and close passes (confirm). Explicit approval is required for: the overall plan (Step 3), epic operations (Step 5), the ordered cross-epic new-story creation batch (Step 6a), and per-epic update/close passes (Steps 6b/6c).
- **Idempotent.** Track what was synced in a manifest with content hashes. If re-run with no changes, do nothing.
- **Manifest gate.** Before proceeding past Step 1, you **must** state aloud to the user what the manifest contains (or that none exists). This is mandatory — do not silently skip this acknowledgment. If a manifest exists and you cannot read it, stop and report the error.
- **Jira-side duplicate check.** Before creating each epic or story, query Jira for existing children under the parent with a matching summary. If a match is found, stop and present the match to the user — do not create a duplicate. This is a safety net independent of the manifest.
- **Jira hierarchy is fixed.** Feature → Epic → Story. Every epic's parent is the Feature issue; every story's parent is its epic. No operation may violate this hierarchy — no re-parenting, no creating issues outside this structure, no closing a Feature.
- **Sync-owned fields.** Sync owns: summary, description, T-shirt size (epics only), parent link (creation only), and issue links (dependencies). These are set from artifact content on creation and overwritten on updates (except parent link). Sync never touches: assignee, sprint, comments, labels, or any other Jira-managed field. Status transitions are permitted **only** for gated lifecycle operations: reopening a previously closed item (Step 5b/6b), closing a removed or user-selected orphaned item (Step 5c/6c), and closing active child stories as part of an approved parent epic closure cascade (Step 5c — the user's approval of the parent close covers its children). No other status changes are allowed.
- **Logical deletion via marker.** Stories and epics are closed (not deleted) when their artifact file contains `status: removed` in the YAML frontmatter. The file stays on disk so the manifest can still track it.
- **Link to source.** Every Jira issue description references the design document.
- **Jira-native references.** Local identifiers (`Story 1.01`, `Epic 1`) have meaning only within the `.artifacts/` directory. When constructing Jira issue descriptions, resolve all local references (in Dependencies, Documentation Inputs, Design Reference, and any other cross-references) to Jira issue keys using the sync manifest. Jira is the source of truth — readers of a Jira issue should never need to decode a local artifact numbering scheme.
- **Checkpoint only on success.** Call `update-manifest` only after a Jira operation succeeds. Pass the `content_hash` that was computed *before* the Jira call (the hash of the content actually submitted), not a freshly recomputed hash. Never record failed or unattempted operations.
- **Close-checkpoint recovery.** For every close path (child, epic, standalone story): retain the exact operation identity (file, Jira key, item type, parent, captured hash) until its checkpoint succeeds. If the Jira close succeeded but `update-manifest` failed, **pause in this run**, remediate the actual local error, and retry **only the exact saved checkpoint invocation** with the original hash. Never repeat a terminal Jira transition, recompute a newer hash, clear the captured state, start other Jira writes, or offer fresh-sync/defer/end while a completed close is uncheckpointed. Pre-transition failures (hash-prep error, transition unavailable, known-rejected Jira call) have no pending Jira success — normal retry/skip/defer choices remain valid. If the Jira outcome is uncertain (network timeout, server error), verify the issue's current status before retrying — do not assume the call was non-mutating. If the captured state is lost (forced abort, new run, lost context) and the manifest entry is still active but Jira is already terminal, **stop for manual reconciliation** rather than blindly repeating the terminal transition or fabricating a hash. Respect a user stop: report incomplete status and hand off rather than ignoring the stop or claiming success.

## Process

### Step 1: Read Decomposition Artifacts and Detect Changes

Read `.artifacts/design/{issue-key}/03-design.md` (for the Jira link and
title). If the decomposition artifacts directory does not exist or has no
`06-stories/` subdirectory, tell the user that `/decompose` should be run
first.

Run the sync helper to detect changes:

```bash
python3 "$SYNC_HELPER" detect-changes .artifacts/design/{issue-key}/
```

The helper reads all epic and story files under `06-stories/`, compares
them against `sync-manifest.json`, and outputs a JSON change plan:

```json
{
  "manifest_exists": true,
  "schema_version": 2,
  "v1_migration": false,
  "feature_key": "EDM-2324",
  "synced_at": "2026-01-15T10:00:00Z",
  "summary": {"new": 3, "changed": 1, "removed": 1, "unchanged": 5, "orphaned": 0, "reopened": 0},
  "items": [
    {
      "file": "epic-1-building.md",
      "type": "epic",
      "category": "new",
      "title": "...",
      "epic_index": 1,
      "jira_key": null,
      "content_hash": "abc123...",
      "old_hash": null,
      "synced_status": null
    }
  ],
  "warnings": []
}
```

The categorization rules the helper applies:

1. **New** — file exists on disk, no matching filename in the manifest,
   and no `status: removed` marker in its frontmatter.
   Action: create in Jira. (If a file has `status: removed` but no
   manifest entry, skip it — it was never synced and does not need to
   be closed.)

2. **Changed** — file exists on disk, filename is in the manifest with
   `synced_status: "active"`, the SHA-256 hash of the file's current
   content differs from the stored `content_hash`, and no
   `status: removed` marker in its frontmatter.
   Action: update the sync-owned fields in Jira.

3. **Removed** — file exists on disk with `status: removed` in its YAML
   frontmatter, and the manifest entry has `synced_status: "active"`.
   Action: close (transition to Done/Closed) in Jira.

4. **Unchanged** — file exists on disk, filename is in the manifest,
   content hash matches, and no `status: removed` marker.
   Action: skip.

5. **Reopened** — file has no `status: removed` marker but its manifest
   entry has `synced_status: "closed"`. The item was previously closed
   and has been brought back. Treat as **Changed** — transition the
   Jira issue back to an open status and update its content.

6. **Orphaned** — manifest entry with `synced_status: "active"` whose
   file no longer exists on disk. Closed entries whose files were
   deleted are silently ignored.

#### Handle the change plan

**If `manifest_exists` is false:** This is a fresh sync. Present:

*"No sync manifest found — this is a fresh sync. {N} epics and {M}
stories will be created; {R} removed-marked items will be skipped."*

(Counts come from the `summary` field.)

**If `v1_migration` is true:** Inform the user: *"Migrating manifest from
v1 to v2 — all existing items will be updated once to populate content
hashes."* Then run:

```bash
python3 "$SYNC_HELPER" migrate-manifest .artifacts/design/{issue-key}/sync-manifest.json
```

**If the plan has orphaned items** (`summary.orphaned > 0`): Present
orphaned entries (from items with `category: "orphaned"`) to the user:

```text
Warning: {N} manifest entries have no corresponding file on disk.
Their Jira tickets are still open but no artifact tracks them:

| Jira Key | Missing File | Title |
|----------|--------------|-------|
| {jira_key} | {file} | {title} |

Options:
  (a) Close these tickets (treat as removed)
  (b) Ignore for now (leave tickets open, keep manifest entries)
  (c) Stop sync so you can investigate
```

Wait for the user's choice before continuing.

**If the plan has warnings** (`warnings` is non-empty): Present each
warning to the user. These are informational (e.g., a removed story
still referenced in its active epic). They are not blockers — proceed
with the sync if the user confirms.

**Manifest acknowledgment (mandatory).** Before moving to Step 2, present
a summary to the user:

*"Manifest found (last synced {synced_at}): {N} items total — {A} new,
{B} changed, {C} to close, {D} unchanged."*

(Use `summary` counts. Include reopened in the changed count for display.)

**If nothing to do** (no new, changed, removed, reopened, or orphaned
items), stop and tell the user:

```text
All items are in sync — nothing to do.
Last synced: {synced_at from change plan}
```

Present the translation table from the manifest and do not proceed to
Step 2.

### Step 2: Resolve Jira Configuration

Determine the Jira project key from the Feature issue key (e.g., `EDM-2324`
→ project `EDM`).

Confirm with the user:
- **Jira project:** {project key} (confirm, don't assume)
- **Feature issue:** {issue key} (parent for all epics)
- **Board / sprint:** Does the user want stories assigned to a specific
  board or sprint? (optional — can be done later in Jira)

### Step 3: Plan Creation Order and Dry Run

**Plan creation order.** Run the sync helper to plan dependency-first
creation order across the entire feature.  Capture output and status
using the same fail-closed pattern as the Step 6a reference-availability
guard:

```bash
PLAN_ERR=$(mktemp) || { echo "FATAL: cannot create temp file" >&2; exit 1; }
PLAN_EXIT=0
PLAN_JSON=$(python3 "$SYNC_HELPER" plan-creation-order \
  .artifacts/design/{issue-key}/ 2>"$PLAN_ERR") || PLAN_EXIT=$?
PLAN_ERR_TEXT=$(cat "$PLAN_ERR")
rm -f "$PLAN_ERR"
```

**Interpret the result (fail-closed).** Only a valid structured
success may proceed to the preview.  Apply this three-branch
interpretation **before** presenting the preview or proceeding to
Step 4:

1. **Exit 0 + valid JSON containing all four required fields
   (`ordered`, `blocked`, `errors`, `satisfied_keys`) with correct
   types (lists/dict) + `errors` empty + `blocked` empty:** the plan
   is valid — `ordered` may be empty when no new stories need
   creation.  Continue to the preflight check below.
2. **Exit 1 + valid JSON containing all four required fields with
   non-empty `errors`:** structured planning errors.  **STOP** —
   present per-story diagnostics and recommend `/revise` to fix the
   decomposition.  Do not proceed to preview, approval, writes, or
   checkpoints.
3. **Any other result** — empty output, malformed JSON, missing or
   wrong-type required fields, unexpected exit code, or exit 1
   without parseable JSON: **STOP**.  Report `PLAN_EXIT`,
   `PLAN_ERR_TEXT`, and the raw `PLAN_JSON` (if any) as fatal
   diagnostics.  Do not proceed to preview, approval, writes, or
   checkpoints.

The helper reads Dependencies and Contributing stories from every new
story's artifact file, builds a dependency graph using existing
manifest keys to satisfy already-synced references, and produces a
topologically sorted creation plan. The output contains:

- `ordered`: new stories in prerequisite-first creation order (stories
  with no unsatisfied dependencies first, then their dependents).
- `blocked`: stories whose required references cannot be satisfied
  (missing local targets, removed/retired sources with no usable key,
  or cycle participants). Each entry lists the missing reference IDs.
- `errors`: human-readable diagnostics (cycles with qualified IDs,
  references to nonexistent artifacts).
- `satisfied_keys`: references already satisfied by manifest keys.

**Preflight check.** If `errors` is non-empty, the plan is invalid
— **stop**. Errors cover new stories with missing targets, cycles,
unreadable source files, AND changed/reopened stories whose edited
Dependencies or Contributing stories reference nonexistent or
unavailable items. Every `blocked` item has at least one root-cause
entry in `errors`, so a non-empty `errors` list is the single gate.
Present the diagnostics and recommend `/revise` to fix the
decomposition before re-running `/sync`. Do not proceed to any Jira
writes (including epic creation in Step 5) with an invalid plan. Do
not silently create extra issues to satisfy references or proceed
with `[unresolved]` placeholders.

**Cascade closure preview.** If the change plan includes parent
epics being closed (category `"removed"` or `"orphaned"` where the
user chose closure in Step 1), compute cascade child closures so the
preview truthfully reflects all operations Step 5c will perform.
Capture output and status using the same fail-closed pattern as the
plan-creation-order call above:

```bash
CASC_ERR=$(mktemp) || { echo "FATAL: cannot create temp file" >&2; exit 1; }
CASC_EXIT=0
CASC_JSON=$(python3 "$SYNC_HELPER" compute-cascade-closures \
  .artifacts/design/{issue-key}/ 2>"$CASC_ERR") || CASC_EXIT=$?
CASC_ERR_TEXT=$(cat "$CASC_ERR")
rm -f "$CASC_ERR"
```

Add `--close-orphans` after the artifacts path only if the user
selected option (a) for orphaned items in Step 1. Omit it when the
user chose (b) ignore — ignored orphan parents must not produce
cascades.

**Interpret the result (fail-closed).** Apply before the dry-run
preview:

1. **Exit 0 + valid JSON with a `cascades` list (may be empty) and
   no `errors` key (or `errors` empty):** cascade data is valid.
   Continue to the preview.
2. **Exit 0 + valid JSON with non-empty `errors` list:** manifest
   integrity problem (e.g., closing parent or child lacks a Jira
   key). **STOP** — present the diagnostics. Do not proceed to
   preview, approval, or writes.
3. **Any other result** — nonzero exit, empty output, malformed
   JSON, or missing `cascades` field: **STOP**. Report `CASC_EXIT`,
   `CASC_ERR_TEXT`, and raw `CASC_JSON` (if any) as fatal
   diagnostics.

Each cascade entry includes `file`, `jira_key`, `title`,
`parent_epic_file`, `parent_jira_key`, and `parent_reason`.

Include cascade closures in the **To Close** section of the preview
below. Adjust the To Close and Unchanged totals: add the cascade
count to To Close, and subtract from Unchanged any cascade items
that were categorized as `"unchanged"` in the change plan. Do not
double-count items that appear both as individually removed and as
cascade targets. Ignored orphan parents (user chose (b) in Step 1)
must not produce cascades — this is enforced by omitting
`--close-orphans` in the helper call.

**Dry-run preview.** Present all planned operations:

```markdown
## Jira Sync Preview — {issue-key}

### Feature: {feature-key} — {title}

### Story Creation Order ({N} stories)

Stories will be created in this dependency-first order so each
story's references resolve before it is written to Jira:

| # | Story | Epic | Dependencies |
|---|-------|------|-------------|
| 1 | Story {N}.{NN}: [{prefix}] {title} | Epic {X} | None |
| 2 | Story {M}.{MM}: [{prefix}] {title} | Epic {Y} | Story {N}.{NN} |

### Epics to Create ({N} items)

#### Epic {X}: {title} (`epic-{X}-{slug}.md`)
- **Type:** Epic
- **Parent:** {feature-key}
- **T-Shirt Size:** {size}
- **Summary:** {1-2 sentences}

### To Update ({N} items)

| Jira Key | Local File | What Changed |
|----------|------------|--------------|
| {jira_key} | `{file}` | Content changed |
| {jira_key} | `{file}` | Reopened (closed → open), Content changed |

For items with `category: "reopened"`, prefix with "Reopened (closed →
open)" so the status transition is visible.

### To Close ({N} items, including {C} cascade closures)

| Jira Key | Local File | Title |
|----------|------------|-------|
| {jira_key} | `{file}` | {title} |
| {jira_key} | *(orphaned — no artifact file)* | {title} |
| {jira_key} | `{file}` *(cascade: parent {parent_jira_key})* | {title} |

Cascade items are children of closing parent epics that Step 5c will
close before the parent. The parent's close approval covers them.
If no cascades exist, omit the cascade count and rows.

### Unchanged ({N} items — skipped)

### Totals
- To create (stories): {N}
- To create (epics): {N}
- To update: {N}
- To close: {N}
- Unchanged: {N}
```

**Wait for explicit user approval before proceeding.**

If the user wants changes, recommend `/revise` to update the decomposition
first — do not modify the decomposition during sync.

### Step 4: Validate `[DOCS]` Stories Before Sync

Before proceeding to Jira operations, validate `[DOCS]` stories
against the quality criteria below. Only stories whose source is
effectively active are eligible for the quality gate — check the
`source_active` field in the change plan items (from detect-changes).
A story with `source_active: false` has an inactive source (own
`status: removed` or parent epic removed/closed without approved
restoration) and is excluded from quality validation — it is
historical and will not be written to Jira as active content. If
`source_active` cannot be determined (no identifiable parent epic),
**stop the sync** and report the anomaly — do not silently exclude
the story from quality or proceed to writes. Restored parent
epics (category `"reopened"`) are active; their children are
eligible. Individually removed stories remain ineligible
regardless of parent status.

Validate every eligible (source-active) `[DOCS]` story that is
**new**, **changed**, or **reopened** in the change plan against all
seven criteria in `decompose.md`. Also include any eligible
`[DOCS]` story whose own hash is unchanged but whose contributor set
changed: a listed contributor was modified, removed, renamed, or
reopened, or a new/changed/reopened `[DEV]`/`[UI]` story's user-facing
surface falls within the `[DOCS]` story's documented scope. Determine
this from the change plan's full item list (new, changed, removed,
reopened), not only from existing references.

If any `[DOCS]` story fails validation, **stop the entire sync** —
do not proceed to Step 5 or any Jira writes (epic creates, story
creates, updates, reopens, closures), success checkpoints, or
content checkpoints for this plan. Present the findings, recommend
`/revise` to correct the source, and require a fresh
preflight/preview/approval cycle after correction.
Sync does not edit story source files.
Do not reuse a stale approval from before the correction.

Note: reference-availability checks for Dependencies and Contributing
stories are handled by the Step 3 creation-order plan (preflight) and
the Step 6a/6b reference-availability guards (runtime). Step 4
validates `[DOCS]` quality criteria only. This gate is distinct from
valid runtime missing-reference failures in Steps 6a/6b, which skip
only the affected story and continue independent eligible work.

### Step 5: Sync Epics

Process epics in three passes: create new epics, update changed epics,
close removed epics. Use the change plan items filtered by `type: "epic"`.

#### 5a: Create New Epics

**Pre-creation duplicate check (per epic).** Before creating each epic,
search Jira for existing children of {feature-key} whose summary matches
the epic title. Use a JQL query like:

```
parent = {feature-key} AND issuetype = Epic AND summary ~ "{epic title}"
```

If the query returns one or more matching issues, **do not create the
epic.** Instead, stop and present the match to the user:

```text
Duplicate detected — an epic with a matching summary already exists
under {feature-key}:

  {matching-key}: {matching summary}

This may indicate a previous sync that is not reflected in the manifest.
Options:
  (a) Skip this epic and record the existing key in the manifest
  (b) Create it anyway (will produce a duplicate)
  (c) Stop sync entirely so you can investigate
```

Wait for the user's choice before continuing.

For each new epic, prepare the hash and description using the epic
`prepare` recipe from the helper reference — **before** the Jira call
(so the hash reflects exactly the submitted content).  `PREP` is JSON
with `content_hash`, `description`, `summary` (Jira-ready title
without numbering), `size` (T-Shirt size), and `title` (raw).

Then create the Jira issue using fields from `PREP`:

- **Type:** Epic
- **Project:** {project key}
- **Parent:** {feature-key} — **mandatory; set via the `fields` parameter: `{"parent": {"key": "{feature-key}"}}`**
- **Summary:** `summary` from PREP (e.g. "Image Building" — without "Epic 1" prefix)
- **Description:** `description` from PREP
- **T-Shirt Size:** `size` from PREP — set via `additional_fields`:
  `{"customfield_10795": {"value": "{size from PREP}"}}`

After creating each epic, verify the created issue has `parent.key`
equal to `{feature-key}` by reading the issue back. If the parent is
missing, stop and report the error — **do not silently defer parent
linking to a "Next Steps" section.** The Feature→Epic hierarchy is a
required outcome of this step, not an optional follow-up.

Record the Jira key and content hash in the sync manifest immediately
(before creating the next epic) using the `update-manifest --operation
create` recipe from the helper reference. Pass `--feature-key` on the
first call to populate the manifest's `feature_key` field.

**If creation fails:** Stop immediately. Report which epics were created
successfully (they are already recorded in the manifest) and which one
failed, including the error. Offer to: (a) retry the failed epic, or
(b) skip it and continue with the remaining epics. Do not silently
continue past a failure.

#### 5b: Update Changed Epics

For each epic categorized as **Changed** or **Reopened**, prepare the
updated description and hash using the epic `prepare` recipe from the
helper reference.

Update the Jira issue using the Jira key from the change plan item.
All field values come from `PREP` (the same snapshot that produced the
hash):

- **Summary:** `summary` from PREP
- **Description:** `description` from PREP
- **T-Shirt Size:** `size` from PREP

Update only the sync-owned fields. Do not touch assignee or other
Jira-managed fields. Status transitions are permitted only for lifecycle
operations: transition **Reopened** items to an open status before
updating content, and transition **Removed** or user-selected
**Orphaned** items to a closed status during the close passes (Steps 5c,
6c). Do not change status for any other reason.

After updating, record the new hash using `update-manifest --operation
update` from the helper reference.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 5c: Close Removed and Selected Orphaned Epics

**Cascade scope guard.** Before starting child closures, verify
that the set of manifest-active children under each closing parent
matches the cascade closures approved in the Step 3 preview. Re-read
the manifest and compare against the approved cascade set (from
`compute-cascade-closures`). If new manifest-active children
appeared since approval (e.g., a concurrent operation added a child
between approval and execution), **stop** and require a fresh
preview/approval cycle — do not silently expand the approved writes.
Children whose manifest entry already has `synced_status: "closed"`
(from a resumed partial cascade) may be skipped per the resume rule
below.

For each epic categorized as **Removed** (file has `status: removed`)
or **Orphaned** where the user chose to close it in Step 1:

1. Close all stories under this epic that have `synced_status: "active"`
   in the manifest (stories before parent). For each child story:
   a. **Compute the hash first.** Use `compute-hash` if the file exists
      on disk; for orphaned entries (no file on disk), use an empty
      hash. Use a distinct variable per child to avoid overwriting
      sibling hashes (e.g., `CHILD_HASH_01`, `CHILD_HASH_02`).
   b. Transition the child story to Done/Closed in Jira.
   c. On success, checkpoint the child close using the child story
      close recipe from the helper reference (`update-manifest
      --operation close` with `--item-type story`, `--epic-file`,
      child file, key, and the hash from step (a)). Retain this
      exact parameter bundle for checkpoint-only retry per the
      close-checkpoint recovery rule.
   d. **If any child operation fails** — distinguish:
      - **Pre-transition failure** (hash-prep error, transition
        unavailable, known-rejected Jira call, user skip): no pending
        Jira success exists. Normal retry/skip/defer choices apply.
        If the Jira outcome is uncertain (network timeout, server
        error), verify the issue's current status before retrying.
      - **Post-success checkpoint failure** (`update-manifest` failed
        after Jira close succeeded): follow the close-checkpoint
        recovery rule — pause, remediate the local error, retry only
        the saved checkpoint invocation with the original hash.
      In either case: **stop the cascade immediately.** Do not
      proceed to the parent epic. Preserve all already-successful
      child checkpoints. Report: the parent epic and its Jira key;
      which children are closed and checkpointed (complete); which
      child failed and the error (note whether it is Jira-closed but
      uncheckpointed, or not yet attempted); and which children
      remain unattempted. Do not imply that already-closed children
      will be rolled back or reopened. For pre-transition failures,
      offer: **retry after remediation** or **defer the entire parent
      cascade** (leave the epic and remaining children in their
      current state). Never skip a failing child and then close the
      parent.
   e. **Resume:** Skip children whose checkpoints already recorded
      `synced_status: "closed"`. For a child whose Jira close
      succeeded but whose checkpoint is missing, apply the
      close-checkpoint recovery rule (retry checkpoint with the
      captured hash). If the captured state was lost (forced abort or
      new run), stop for manual reconciliation.
2. After **all** child closures and their checkpoints have succeeded,
   compute the epic hash: use `compute-hash` if the file exists on
   disk; for orphaned entries (no file on disk), use an empty hash.
3. Transition the epic to Done/Closed in Jira.
4. On success, record the close with `update-manifest`, passing the
   hash from step 2:

   Use the epic close recipe from the helper reference
   (`update-manifest --operation close` with `--item-type epic`).
   Select the close transition per the helper reference.

**If epic close fails:** For pre-transition failures, offer retry or
defer. For post-success checkpoint failure, follow the close-checkpoint
recovery rule. Already-closed children remain closed.

Present all epic operations to the user:

```markdown
### Epic Operations
| Operation | Local Epic | Jira Key | Title |
|-----------|------------|----------|-------|
| Created | Epic 1 | {EDM-XXXX} | {title} |
| Updated | Epic 2 | {EDM-YYYY} | {title} |
| Closed | Epic 3 | {EDM-ZZZZ} | {title} |
```

**Wait for user confirmation before syncing stories.**

### Step 6: Sync Stories

**Refresh the change plan** before processing stories. Epic operations
in Step 5 may have changed the manifest (e.g., closing an epic closes
its children, reopening an epic enables its children). Re-run
`detect-changes` to get an updated plan that reflects the current
manifest state:

```bash
STORY_PLAN=$(python3 "$SYNC_HELPER" detect-changes .artifacts/design/{issue-key}/)
```

Use the refreshed plan's `type: "story"` items for story operations.
This ensures:
- Children already closed by cascaded epic closure (Step 5c) are not
  re-closed
- Stories under a reopened epic are correctly categorized
- User orphan choices from Step 1 that were not acted on in Step 5 are
  preserved (orphan entries the user chose to ignore remain in the
  manifest and will still appear as orphaned in the refreshed plan)

If a parent epic's create or reopen operation failed/was skipped in
Step 5, do not create, update, or reopen stories under that epic —
skip them and report which stories were skipped due to the parent
failure.

If an epic's close cascade was deferred in Step 5c (the parent was
left unclosed because a child closure or checkpoint failed — whether
remaining children are open, Jira-closed but uncheckpointed, or
unattempted), do not retry closing those remaining children here.
They remain in their current manifest state. Report them as deferred
and inform the user that the parent cascade must be retried from
Step 5c after remediation.

Process stories in two phases: first create all new stories across
all epics in the planned dependency-first order from Step 3, then
run per-epic update and close passes.

#### 6a: Create New Stories (Dependency-First Order)

The user's Step 5 confirmation ("Wait for user confirmation before
syncing stories") covers the ordered cross-epic creation batch below.

Process the `ordered` list from the Step 3 creation plan. This list
spans all epics and is sorted so prerequisites are created before
their dependents.

**For each story in the ordered list:**

**Pre-creation duplicate check.** Before creating each story, search
Jira for existing children of its parent epic whose summary matches
the story title. Use a JQL query like:

```
parent = {epic-jira-key} AND issuetype = Story AND summary ~ "{story title}"
```

If a match is found, stop and present it to the user with the same
options as in Step 5a (skip and record, create anyway, or stop).
Wait for the user's choice before continuing.

**Reference-availability guard.** Before calling `prepare` for any
story, run the `check-ref-availability` subcommand against the current
on-disk manifest with this story's qualified ID:

```bash
REF_ERR=$(mktemp) || { echo "FATAL: cannot create temp file" >&2; exit 1; }
REF_EXIT=0
REF_CHECK=$(python3 "$SYNC_HELPER" check-ref-availability \
  .artifacts/design/{issue-key}/ \
  "story-{N}.{NN}" 2>"$REF_ERR") || REF_EXIT=$?
REF_ERR_TEXT=$(cat "$REF_ERR")
rm -f "$REF_ERR"
```

The `|| REF_EXIT=$?` idiom captures a nonzero exit without aborting
under `set -e`.  Stderr is captured to a per-guard temp file
(`$REF_ERR`) created fresh for this story.  The two lines after
the helper call read the stderr text and remove the temp file
immediately — before branch interpretation — so cleanup cannot be
forgotten on any exit path.  `REF_ERR_TEXT` is available for fatal
diagnostic reporting; on ready/blocked paths it is simply unused.

The helper checks Dependencies (Story and Epic refs) and Contributing
stories (for `[DOCS]` stories), verifies the owning epic has a key,
and treats native Jira keys as always available.

Interpret the result with fail-closed semantics.  Exactly ONE of these
branches must match; any other outcome is a catch-all failure:

1. **Ready:** `REF_EXIT` is 0, stdout is valid JSON, the `ready` list
   contains an entry whose `qid` equals THIS story's qualified ID, and
   the `blocked` list does NOT contain this QID.  → Proceed to
   `prepare`.
2. **Blocked:** `REF_EXIT` is 1, stdout is valid JSON, the `blocked`
   list contains an entry whose `qid` equals THIS story's qualified ID
   with `missing` (list of unresolved ref IDs) and `reason` (string).
   → **Skip** this story — do not call `prepare`, do not render a
   description, do not create the Jira issue, do not record a manifest
   checkpoint.  Record the story's qualified ID, the `missing` refs,
   and the `reason` for the Step 8 report.  Continue with the next
   story in the ordered list — do not abort independent eligible work.
3. **Catch-all failure** (every other outcome — including exit 0 with
   invalid JSON, exit 0 with this QID missing from `ready`, exit
   nonzero with no JSON, malformed or missing `ready`/`blocked` fields,
   this QID appearing in both lists, or unexpected exit codes):
   **Stop the sync** and report `REF_ERR_TEXT` and any stdout.  Do not
   skip the story or continue with others — the manifest state may be
   indeterminate.  Do not call `prepare`, render, write to Jira, or
   record a manifest checkpoint.

Keys recorded by earlier stories in this run (via `update-manifest`)
are immediately visible to subsequent `check-ref-availability` calls
because the manifest is reloaded fresh from disk.  Blocked stories
remain eligible for the next explicit `/sync` invocation.

For each new story (non-blocked), prepare the hash and description
using the story `prepare` recipe from the helper reference. `PREP`
is JSON with `content_hash`, `description`, `summary` (`[PREFIX]
title` without numbering), `story_type`, `dependencies` (resolved
text), and `title`.

Create the Jira issue using fields from `PREP`:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {epic jira key} (from Step 5) — **set via the `fields` parameter: `{"parent": {"key": "{epic jira key}"}}`**
- **Summary:** `summary` from PREP (e.g. "[DEV] Scaffold Build Pipeline" — without "Story 1.01:" prefix)
- **Description:** `description` from PREP

After creating each story, verify the created issue has `parent.key`
equal to the epic's Jira key by reading the issue back. If the parent
is missing, stop and report the error — **do not silently defer parent
linking.** The Epic→Story hierarchy is a required outcome of this step.

Record the Jira key and content hash immediately using the story
create recipe from the helper reference (`update-manifest --operation
create` with `--item-type story` and `--epic-file`).

**Issue links:** After creating the story, create Jira issue links for
each dependency. The `dependencies` field in `PREP` contains the
resolved dependency text (local refs already replaced with Jira keys).
Parse each Jira key from this text. If a dependency shows
`[unresolved]`, skip the link and note it for the user. These links enable downstream
workflows (e.g., docs-writer) to traverse the dependency chain via the
Jira API.

For each dependency, the semantic relationship is:

> The **current story** depends on the **dependency story**.
> Equivalently: the **dependency story** blocks the **current story**.

**Link type selection:** Try the "Dependency" link type first
(`"depends on"` / `"is depended on by"`). If the Jira instance does
not have this type, fall back to "Blocks"
(`"blocks"` / `"is blocked by"`).

**Example:** If Story 1.02's artifact lists `Dependencies: Story 1.01`,
then Story 1.01 must finish before Story 1.02 can begin. After link
creation, Jira should show (depending on which link type was used):

Using "Dependency":
- On Story 1.01's issue: **"is depended on by"** Story 1.02
- On Story 1.02's issue: **"depends on"** Story 1.01

Using "Blocks" (fallback):
- On Story 1.01's issue: **"blocks"** Story 1.02
- On Story 1.02's issue: **"is blocked by"** Story 1.01

**Getting the direction right:** Jira link-creation APIs use directional
fields (e.g., `inwardIssue` / `outwardIssue`) whose meaning varies by
link type. Using the link type definition already retrieved above, read
the chosen type's inward and outward descriptions and assign the
dependency story's key and the current story's key to whichever fields
produce the expected display above. **After creating the first
dependency link in a sync run, read the current story's issue links
back from Jira, find the link matching the dependency story's key and
the selected link type, and verify its direction matches the expected
display. If the direction is wrong, delete the link, swap the field
assignments, recreate it, and re-verify. If the retry also fails, log
the failure and continue with the remaining links (same as any other
link failure).**

Issue link creation is a separate Jira operation — use the Jira CLI or
MCP server to create the link.

If a specific link fails, log it and continue with the remaining links.
Include all failures in the per-epic story report so the user knows
exactly which links to create manually.

**If creation fails:** Stop immediately. Report which stories were created
successfully and which one failed, including the error. Offer to:
(a) retry the failed story, or (b) skip it and continue with remaining
stories. The manifest already reflects all successfully created items,
so re-running `/sync` later will only attempt uncreated items.

#### 6b: Update Changed Stories

Process changed and reopened stories per epic.

**Reference-availability guard.** Before calling `prepare` for a
changed or reopened story, run the same `check-ref-availability` guard
as in Step 6a with this story's qualified ID: create a per-guard temp
(`REF_ERR=$(mktemp)`), capture stderr and exit status with the
`|| REF_EXIT=$?` idiom, read stderr text and remove the temp
immediately after the helper call (same two-line cleanup as 6a), then
apply the same three-branch result interpretation (ready → proceed;
blocked → skip; catch-all → stop and report `REF_ERR_TEXT`).  Do not
call `prepare`, render a description, update or reopen the Jira issue,
or record a manifest checkpoint for a blocked or failed story.  Do not
retry a blocked story in the current run.

For each story categorized as **Changed** or **Reopened** (non-blocked),
prepare the updated description and hash using the story `prepare`
recipe from the helper reference.

Update the Jira issue using fields from `PREP`:

- **Summary:** `summary` from PREP
- **Description:** `description` from PREP
- **Issue links:** read the Jira issue's current issue links and filter
  to only those matching the link type selected in Step 6a (either
  "Dependency" or "Blocks", whichever was used during creation).
  Compare these filtered links against the artifact file's dependency
  list. Remove links whose dependency stories no longer appear in the
  artifact and create new links for added dependencies, using the same
  link type and direction mapping as Step 6a. Do not touch issue links
  of other types.

Update only the sync-owned fields. Do not touch assignee or other
Jira-managed fields. For **Reopened** items, transition the Jira issue
back to an open status before updating content (see the status rule in
Step 5b). Do not change status for any other reason.

After updating, record the new hash using `update-manifest --operation
update` with `--item-type story` and `--epic-file` from the helper
reference.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 6c: Close Removed and Selected Orphaned Stories

For each story categorized as **Removed** (file has `status: removed`)
or **Orphaned** where the user chose to close it in Step 1:

1. Compute the hash before the transition: use `compute-hash` if the
   file exists on disk; for orphaned entries, use an empty hash.
2. Transition the story to Done/Closed in Jira.
3. On success, record the close using the standalone story close recipe
   from the helper reference (`update-manifest --operation close` with
   `--item-type story`, `--epic-file`, and the hash from step 1).

**If close fails:** For pre-transition failures, offer retry or skip.
For post-success checkpoint failure, follow the close-checkpoint
recovery rule.

Present the stories synced for each epic:

```markdown
### Stories for Epic 1 ({EDM-XXXX})
| Operation | Local Story | Jira Key | Title |
|-----------|-------------|----------|-------|
| Created | Story 1.01 | {EDM-AAAA} | [{prefix}] {title} |
| Updated | Story 1.02 | {EDM-BBBB} | [{prefix}] {title} |
| Closed | Story 1.03 | {EDM-CCCC} | [{prefix}] {title} |
```

### Step 7: Verify Sync Manifest

The manifest has been built/updated incrementally during Steps 5-6 (each
operation was recorded via `update-manifest` immediately after success).
Verify the manifest is complete and consistent. The final structure should
be:

```json
{
  "schema_version": 2,
  "feature_key": "{feature-key}",
  "synced_at": "{ISO timestamp}",
  "epics": [
    {
      "file": "epic-1-image-building.md",
      "jira_key": "EDM-XXXX",
      "title": "{title}",
      "size": "{size}",
      "content_hash": "{sha256-of-raw-file}",
      "synced_status": "active",
      "stories": [
        {
          "file": "story-01-scaffold-build-pipeline.md",
          "jira_key": "EDM-XXXY",
          "title": "[DEV] {title}",
          "content_hash": "{sha256-of-raw-file}",
          "synced_status": "active"
        }
      ]
    }
  ]
}
```

Fields:
- `content_hash` — SHA-256 of the raw artifact file content at last sync.
  Used to detect changes on the next run.
- `synced_status` — `"active"` or `"closed"`. Tracks the last state
  sync pushed to Jira.
- `synced_at` — top-level only, not per-entry. Updated to the current
  timestamp at the end of each sync run.

### Step 8: Report to User

Summarize:
- How many epics and stories were created, updated, closed, unchanged, and **blocked**
- For each blocked story: the story file, which required keys were missing, and the reason. Blocked new stories were not created; blocked changed/reopened stories were not updated. Because no checkpoint was recorded for blocked stories, they remain eligible on the next `/sync` run. Do not claim complete synchronization while blocked stories remain
- Confirm the hierarchy was verified for every issue actually created or updated: every epic has parent = Feature (verified in Step 5), every story has parent = its epic (verified in Step 6). Blocked stories were not written to Jira; list them separately as work not applied
- Link to the Feature issue in Jira (which now shows the full hierarchy)

**Do not suggest manual parent linking as a next step.** If any parent
link was not set during creation, that is a failure that should have been
caught in Steps 5-6.

Present a translation table mapping all local artifact identifiers to Jira
keys. This table is the definitive reference for anyone working with the
local `.artifacts/` files who needs to find the corresponding Jira issue:

```markdown
| Local Reference | Jira Key | Status | Title |
|----------------|----------|--------|-------|
| Epic 1 | {jira_key} | active | {title} |
| Story 1.01 | {jira_key} | active | {title} |
| Story 1.02 | {jira_key} | closed | {title} |
| Epic 2 | {jira_key} | active | {title} |
| ... | ... | ... | ... |
```

## Output

- Jira epics and stories created, updated, or closed (with user approval)
- `.artifacts/design/{issue-key}/sync-manifest.json` (v2 schema)

## When This Phase Is Done

Report your results:
- All Jira issue keys affected (created, updated, closed)
- Summary of the hierarchy (Feature → Epics → Stories)
- Any next steps (e.g., assign stories to team members, set sprint)

Then **re-read the controller** (`controller.md`) for next-step guidance.
