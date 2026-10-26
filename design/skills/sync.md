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

This skill delegates deterministic file operations to a Python helper
script at `scripts/sync_helper.py` under the design package root. From
the built-in phase file `skills/sync.md`, the helper is at
`../scripts/sync_helper.py` — i.e. two directories up from this file,
then into `scripts/`.

To resolve the helper, record the absolute path of the **built-in**
`design/skills/sync.md` that you are reading — not `design/SKILL.md`
(which has a different directory depth) and not a project-level phase
override — and derive the helper from it:

```bash
BUILTIN_SYNC='<absolute path of the loaded built-in design/skills/sync.md>'
SYNC_HELPER="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().parents[1] / "scripts" / "sync_helper.py")' "$BUILTIN_SYNC")"
```

`Path.resolve()` follows symlinks, so this works for both the default
`~/.ai-workflows` install and a direct symlink from
`.claude/skills/design` to an arbitrary clone location (even without
`~/.ai-workflows`). If a project-level phase override provides a
replacement `skills/sync.md`, the helper still comes from the built-in
package — always use the built-in source path, not the override path.

The helper **never contacts Jira** and **never mutates external state**.
It reads and writes only local artifact files and the sync manifest.
All Jira API calls, user approvals, and error-handling decisions remain
your responsibility.

Available subcommands:

| Subcommand | Purpose |
|------------|---------|
| `detect-changes <artifacts-dir>` | Compare files against manifest; output JSON change plan |
| `prepare <file> <manifest> --type epic\|story [options]` | Read file once; return hash + rendered description (snapshot-consistent) |
| `resolve-refs <manifest-path> <text>` | Replace local refs (Story 1.01, Epic 1) with Jira keys |
| `render-description <file> <manifest> --type epic\|story [options]` | Render Jira-ready description with resolved refs |
| `update-manifest <manifest> --operation create\|update\|close --file <f> --jira-key <K> --content-hash <H> [--item-type epic\|story] [--epic-file <E>] [options]` | Record one successful Jira operation (`--epic-file` required for stories) |
| `compute-hash <file>` | Print SHA-256 of file content |
| `migrate-manifest <manifest>` | Upgrade v1 manifest to v2 in place |

The `prepare` subcommand is preferred over separate `compute-hash` +
`render-description` calls. It reads the file once and guarantees the
hash corresponds to exactly the content used in the description.  Pass
the returned `content_hash` to `update-manifest` after a successful
Jira write.

## Critical Rules

- **Dry-run first.** Always show what would be created, updated, or closed before doing anything.
- **Explicit approval required.** Never modify Jira without the user saying "yes."
- **Batch by operation.** Process epics first (confirm), then stories per epic (confirm). Not one giant batch.
- **Idempotent.** Track what was synced in a manifest with content hashes. If re-run with no changes, do nothing.
- **Manifest gate.** Before proceeding past Step 1, you **must** state aloud to the user what the manifest contains (or that none exists). This is mandatory — do not silently skip this acknowledgment. If a manifest exists and you cannot read it, stop and report the error.
- **Jira-side duplicate check.** Before creating each epic or story, query Jira for existing children under the parent with a matching summary. If a match is found, stop and present the match to the user — do not create a duplicate. This is a safety net independent of the manifest.
- **Jira hierarchy is fixed.** Feature → Epic → Story. Every epic's parent is the Feature issue; every story's parent is its epic. No operation may violate this hierarchy — no re-parenting, no creating issues outside this structure, no closing a Feature.
- **Sync-owned fields.** Sync owns: summary, description, T-shirt size (epics only), parent link (creation only), and issue links (dependencies). These are set from artifact content on creation and overwritten on updates (except parent link). Sync never touches: assignee, sprint, comments, labels, or any other Jira-managed field. Status transitions are permitted **only** for gated lifecycle operations: reopening a previously closed item (Step 4b/5b), closing a removed or user-selected orphaned item (Step 4c/5c), and closing active child stories as part of an approved parent epic closure cascade (Step 4c — the user's approval of the parent close covers its children). No other status changes are allowed.
- **Logical deletion via marker.** Stories and epics are closed (not deleted) when their artifact file contains `status: removed` in the YAML frontmatter. The file stays on disk so the manifest can still track it.
- **Link to source.** Every Jira issue description references the design document.
- **Jira-native references.** Local identifiers (`Story 1.01`, `Epic 1`) have meaning only within the `.artifacts/` directory. When constructing Jira issue descriptions, resolve all local references (in Dependencies, Documentation Inputs, Design Reference, and any other cross-references) to Jira issue keys using the sync manifest. Jira is the source of truth — readers of a Jira issue should never need to decode a local artifact numbering scheme.
- **Checkpoint only on success.** Call `update-manifest` only after a Jira operation succeeds. Pass the `content_hash` that was computed *before* the Jira call (the hash of the content actually submitted), not a freshly recomputed hash. Never record failed or unattempted operations.

## Reference Resolution

The helper's `resolve-refs` subcommand replaces local identifiers with
Jira keys from the manifest:

- `Story 1.01` → look up `story-01-*.md` under `epic-1/` in the manifest → `EDM-XXXX`
- `Epic 1` → look up `epic-1-*.md` in the manifest → `EDM-YYYY`
- `Stories 1.01, 2.01, 3.01` → resolve each → `EDM-XXXX, EDM-AAAA, EDM-BBBB`

The manifest is built incrementally: each issue's key is recorded immediately
after creation. Since epics are created first and stories are created in epic
order (Epic 1 stories before Epic 2 stories), dependencies — which reference
earlier stories — are always resolvable by the time they're needed.

If a reference cannot be resolved (the referenced item hasn't been created
yet or failed to create), the helper leaves the local identifier, annotates
it with `[unresolved]`, and you must flag it to the user.

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

### Step 3: Dry Run

Present a preview of all planned operations, using the change plan items:

```markdown
## Jira Sync Preview — {issue-key}

### Feature: {feature-key} — {title}

### To Create ({N} items)

#### Epic {X}: {title} (`epic-{X}-{slug}.md`)
- **Type:** Epic
- **Parent:** {feature-key}
- **T-Shirt Size:** {size}
- **Summary:** {1-2 sentences}
- **Stories:**
  - Story {X}.01: [{prefix}] {title} (`story-01-{slug}.md`)
  - Story {X}.02: [{prefix}] {title} (`story-02-{slug}.md`)

### To Update ({N} items)

| Jira Key | Local File | What Changed |
|----------|------------|--------------|
| {jira_key} | `{file}` | Content changed |
| {jira_key} | `{file}` | Reopened (closed → open), Content changed |

For items with `category: "reopened"`, prefix with "Reopened (closed →
open)" so the status transition is visible.

### To Close ({N} items)

| Jira Key | Local File | Title |
|----------|------------|-------|
| {jira_key} | `{file}` | {title} |
| {jira_key} | *(orphaned — no artifact file)* | {title} |

Include orphaned entries the user chose to close in Step 1 with the
note "*(orphaned — no artifact file)*" in the Local File column.

### Unchanged ({N} items — skipped)

### Totals
- To create: {N}
- To update: {N}
- To close: {N}
- Unchanged: {N}
```

**Wait for explicit user approval before proceeding.**

If the user wants changes, recommend `/revise` to update the decomposition
first — do not modify the decomposition during sync.

### Step 4: Sync Epics

Process epics in three passes: create new epics, update changed epics,
close removed epics. Use the change plan items filtered by `type: "epic"`.

#### 4a: Create New Epics

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

For each new epic, prepare the hash and description in one call
**before** the Jira call (so the hash reflects exactly the submitted
content):

```bash
PREP=$(python3 "$SYNC_HELPER" prepare \
  .artifacts/design/{issue-key}/06-stories/{epic-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type epic \
  --design-doc-link "{link}" \
  --feature-key "{feature-key}")
```

`PREP` is JSON with `content_hash`, `description`, `summary` (Jira-ready
title without numbering), `size` (T-Shirt size), and `title` (raw).

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
(before creating the next epic). Pass `--feature-key` on the first call
to populate the manifest's `feature_key` field:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation create \
  --file "{epic-file}" \
  --jira-key "{created-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type epic \
  --title "{epic title}" \
  --size "{size}" \
  --feature-key "{feature-key}"
```

**If creation fails:** Stop immediately. Report which epics were created
successfully (they are already recorded in the manifest) and which one
failed, including the error. Offer to: (a) retry the failed epic, or
(b) skip it and continue with the remaining epics. Do not silently
continue past a failure.

#### 4b: Update Changed Epics

For each epic categorized as **Changed** or **Reopened**, prepare the
updated description and hash in one call:

```bash
PREP=$(python3 "$SYNC_HELPER" prepare \
  .artifacts/design/{issue-key}/06-stories/{epic-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type epic \
  --design-doc-link "{link}" \
  --feature-key "{feature-key}")
```

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
**Orphaned** items to a closed status during the close passes (Steps 4c,
5c). Do not change status for any other reason.

After updating, record the new hash:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation update \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type epic
```

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 4c: Close Removed and Selected Orphaned Epics

For each epic categorized as **Removed** (file has `status: removed`)
or **Orphaned** where the user chose to close it in Step 1:

1. Close all stories under this epic that have `synced_status: "active"`
   in the manifest (stories before parent). For each child story:
   a. **Compute the hash first.** Use `compute-hash` if the file exists
      on disk; for orphaned entries (no file on disk), use an empty
      hash. Use a distinct variable per child to avoid overwriting
      sibling hashes (e.g., `CHILD_HASH_01`, `CHILD_HASH_02`).
   b. Transition the child story to Done/Closed in Jira.
   c. On success, checkpoint with `update-manifest --operation close`,
      passing the hash from step (a).
   d. **If any child operation fails** (hash-prep error, transition
      unavailable, Jira error, checkpoint save failure, or user
      skip): **stop the cascade immediately.** Do not proceed to the
      parent epic. Preserve all already-successful child checkpoints.
      Report: the parent epic and its Jira key; which children are
      closed and checkpointed (complete); which child failed and the
      error (note whether it is Jira-closed but uncheckpointed, or
      not yet attempted); and which children remain unattempted. Do
      not imply that already-closed children will be rolled back or
      reopened. Offer the user two choices: **retry after
      remediation** (resolve the reported error — Jira or local —
      then re-run) or **defer the entire parent cascade** (leave the
      epic and remaining children in their current state). Never skip
      a failing child and then close the parent.
   e. **Reconciliation on resume:** If a child's Jira transition
      succeeded but its checkpoint failed, retry the checkpoint using
      the hash captured in step (a) rather than repeating the Jira
      transition. Skip children whose checkpoints already recorded
      `synced_status: "closed"`.
2. After **all** child closures and their checkpoints have succeeded,
   compute the epic hash: use `compute-hash` if the file exists on
   disk; for orphaned entries (no file on disk), use an empty hash.
3. Transition the epic to Done/Closed in Jira.
4. On success, record the close with `update-manifest`, passing the
   hash from step 2:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{hash from step 2, or empty for orphans}" \
  --item-type epic
```

**Selecting the close transition:** Use the Jira API to query available
transitions for the issue and select the terminal/done-category
transition. If multiple terminal transitions are available, prefer
"Done" over "Closed." If no terminal transition is available from the
current status, report the error and let the user handle it in Jira.

**If epic close fails:** Report the error and offer to retry or defer.
Already-closed children remain closed.

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

### Step 5: Sync Stories

**Refresh the change plan** before processing stories. Epic operations
in Step 4 may have changed the manifest (e.g., closing an epic closes
its children, reopening an epic enables its children). Re-run
`detect-changes` to get an updated plan that reflects the current
manifest state:

```bash
STORY_PLAN=$(python3 "$SYNC_HELPER" detect-changes .artifacts/design/{issue-key}/)
```

Use the refreshed plan's `type: "story"` items for story operations.
This ensures:
- Children already closed by cascaded epic closure (Step 4c) are not
  re-closed
- Stories under a reopened epic are correctly categorized
- User orphan choices from Step 1 that were not acted on in Step 4 are
  preserved (orphan entries the user chose to ignore remain in the
  manifest and will still appear as orphaned in the refreshed plan)

If a parent epic's create or reopen operation failed/was skipped in
Step 4, do not create, update, or reopen stories under that epic —
skip them and report which stories were skipped due to the parent
failure.

If an epic's close cascade was deferred in Step 4c (the parent was
left unclosed because a child closure or checkpoint failed — whether
remaining children are open, Jira-closed but uncheckpointed, or
unattempted), do not retry closing those remaining children here.
They remain in their current manifest state. Report them as deferred
and inform the user that the parent cascade must be retried from
Step 4c after remediation.

Process stories per epic, in the same three passes: create, update, close.

#### 5a: Create New Stories

**Pre-creation duplicate check (per story).** Before creating each story,
search Jira for existing children of the epic whose summary matches the
story title. Use a JQL query like:

```
parent = {epic-jira-key} AND issuetype = Story AND summary ~ "{story title}"
```

If the query returns one or more matching issues, **do not create the
story.** Instead, stop and present the match to the user with the same
options as in Step 4a (skip and record, create anyway, or stop entirely).
Wait for the user's choice before continuing.

For each new story, prepare the hash and description in one call:

```bash
PREP=$(python3 "$SYNC_HELPER" prepare \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type story \
  --design-doc-link "{link}" \
  --epic-jira-key "{epic-jira-key}" \
  --story-type "{prefix}")
```

`PREP` is JSON with `content_hash`, `description`, `summary` (Jira-ready
`[PREFIX] title` without numbering), `story_type`, `dependencies`
(resolved text), and `title` (raw).

Create the Jira issue using fields from `PREP`:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {epic jira key} (from Step 4) — **set via the `fields` parameter: `{"parent": {"key": "{epic jira key}"}}`**
- **Summary:** `summary` from PREP (e.g. "[DEV] Scaffold Build Pipeline" — without "Story 1.01:" prefix)
- **Description:** `description` from PREP

After creating each story, verify the created issue has `parent.key`
equal to the epic's Jira key by reading the issue back. If the parent
is missing, stop and report the error — **do not silently defer parent
linking.** The Epic→Story hierarchy is a required outcome of this step.

Record the Jira key and content hash immediately. The `--epic-file`
flag is required to ensure the story is placed under the correct epic:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation create \
  --file "{story-file}" \
  --jira-key "{created-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type story \
  --title "{summary from PREP}" \
  --epic-file "{epic-file}"
```

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

#### 5b: Update Changed Stories

For each story categorized as **Changed** or **Reopened**, prepare the
updated description and hash in one call:

```bash
PREP=$(python3 "$SYNC_HELPER" prepare \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type story \
  --design-doc-link "{link}" \
  --epic-jira-key "{epic-jira-key}" \
  --story-type "{prefix}")
```

Update the Jira issue using fields from `PREP`:

- **Summary:** `summary` from PREP
- **Description:** `description` from PREP
- **Issue links:** read the Jira issue's current issue links and filter
  to only those matching the link type selected in Step 5a (either
  "Dependency" or "Blocks", whichever was used during creation).
  Compare these filtered links against the artifact file's dependency
  list. Remove links whose dependency stories no longer appear in the
  artifact and create new links for added dependencies, using the same
  link type and direction mapping as Step 5a. Do not touch issue links
  of other types.

Update only the sync-owned fields. Do not touch assignee or other
Jira-managed fields. For **Reopened** items, transition the Jira issue
back to an open status before updating content (see the status rule in
Step 4b). Do not change status for any other reason.

After updating, record the new hash:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation update \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{content_hash from PREP}" \
  --item-type story \
  --epic-file "{epic-file}"
```

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 5c: Close Removed and Selected Orphaned Stories

For each story categorized as **Removed** (file has `status: removed`)
or **Orphaned** where the user chose to close it in Step 1:

1. Compute the hash before the transition: use `compute-hash` if the
   file exists on disk; for orphaned entries, use an empty hash.
2. Transition the story to Done/Closed in Jira.
3. On success, record the close with `update-manifest`, passing the
   hash from step 1:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "{hash from step 1, or empty for orphans}" \
  --item-type story \
  --epic-file "{epic-file}"
```

**If close fails:** Report the error and offer to retry or skip.

Present the stories synced for each epic:

```markdown
### Stories for Epic 1 ({EDM-XXXX})
| Operation | Local Story | Jira Key | Title |
|-----------|-------------|----------|-------|
| Created | Story 1.01 | {EDM-AAAA} | [{prefix}] {title} |
| Updated | Story 1.02 | {EDM-BBBB} | [{prefix}] {title} |
| Closed | Story 1.03 | {EDM-CCCC} | [{prefix}] {title} |
```

### Step 6: Verify Sync Manifest

The manifest has been built/updated incrementally during Steps 4-5 (each
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

### Step 7: Report to User

Summarize:
- How many epics and stories were created, updated, closed, and unchanged
- Confirm the hierarchy was verified: every epic has parent = Feature (verified in Step 4), every story has parent = its epic (verified in Step 5)
- Link to the Feature issue in Jira (which now shows the full hierarchy)

**Do not suggest manual parent linking as a next step.** If any parent
link was not set during creation, that is a failure that should have been
caught in Steps 4-5.

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
