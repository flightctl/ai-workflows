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
script. Locate the helper relative to this file:

```
SYNC_HELPER="$(cd "$(dirname "$0")" && pwd)/../scripts/sync_helper.py"
```

Or, when running from an installed layout (symlinked skill directory),
resolve the real path first:

```
SKILL_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SYNC_HELPER="${SKILL_DIR}/../scripts/sync_helper.py"
```

The helper **never contacts Jira** and **never mutates external state**.
It reads and writes only local artifact files and the sync manifest.
All Jira API calls, user approvals, and error-handling decisions remain
your responsibility.

Available subcommands:

| Subcommand | Purpose |
|------------|---------|
| `detect-changes <artifacts-dir>` | Compare files against manifest; output JSON change plan |
| `resolve-refs <manifest-path> <text>` | Replace local refs (Story 1.01, Epic 1) with Jira keys |
| `render-description <file> <manifest> --type epic\|story [options]` | Render Jira-ready description with resolved refs |
| `update-manifest <manifest> --operation create\|update\|close --file <f> --jira-key <K> --content-hash <H> [options]` | Record one successful Jira operation |
| `compute-hash <file>` | Print SHA-256 of file content |
| `migrate-manifest <manifest>` | Upgrade v1 manifest to v2 in place |

## Critical Rules

- **Dry-run first.** Always show what would be created, updated, or closed before doing anything.
- **Explicit approval required.** Never modify Jira without the user saying "yes."
- **Batch by operation.** Process epics first (confirm), then stories per epic (confirm). Not one giant batch.
- **Idempotent.** Track what was synced in a manifest with content hashes. If re-run with no changes, do nothing.
- **Manifest gate.** Before proceeding past Step 1, you **must** state aloud to the user what the manifest contains (or that none exists). This is mandatory — do not silently skip this acknowledgment. If a manifest exists and you cannot read it, stop and report the error.
- **Jira-side duplicate check.** Before creating each epic or story, query Jira for existing children under the parent with a matching summary. If a match is found, stop and present the match to the user — do not create a duplicate. This is a safety net independent of the manifest.
- **Jira hierarchy is fixed.** Feature → Epic → Story. Every epic's parent is the Feature issue; every story's parent is its epic. No operation may violate this hierarchy — no re-parenting, no creating issues outside this structure, no closing a Feature.
- **Sync-owned fields.** Sync owns: summary, description, T-shirt size (epics only), parent link (creation only), and issue links (dependencies). These are set from artifact content on creation and overwritten on updates (except parent link). Sync never touches: status, assignee, sprint, comments, labels, or any other Jira-managed field.
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

For each new epic, first compute the hash and render the description
**before** the Jira call (so the hash reflects what was submitted):

```bash
HASH=$(python3 "$SYNC_HELPER" compute-hash .artifacts/design/{issue-key}/06-stories/{epic-file})

DESCRIPTION=$(python3 "$SYNC_HELPER" render-description \
  .artifacts/design/{issue-key}/06-stories/{epic-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type epic \
  --design-doc-link "{link}" \
  --feature-key "{feature-key}")
```

Then create the Jira issue:

- **Type:** Epic
- **Project:** {project key}
- **Parent:** {feature-key} — **mandatory; set via the `fields` parameter: `{"parent": {"key": "{feature-key}"}}`**
- **Summary:** {epic title from the change plan item}
- **Description:** the rendered description from above
- **T-Shirt Size:** {size} — set via `additional_fields`:
  `{"customfield_10795": {"value": "{size}"}}`

After creating each epic, verify the created issue has `parent.key`
equal to `{feature-key}` by reading the issue back. If the parent is
missing, stop and report the error — **do not silently defer parent
linking to a "Next Steps" section.** The Feature→Epic hierarchy is a
required outcome of this step, not an optional follow-up.

Record the Jira key and content hash in the sync manifest immediately
(before creating the next epic):

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation create \
  --file "{epic-file}" \
  --jira-key "{created-key}" \
  --content-hash "$HASH" \
  --item-type epic \
  --title "{epic title}" \
  --size "{size}"
```

**If creation fails:** Stop immediately. Report which epics were created
successfully (they are already recorded in the manifest) and which one
failed, including the error. Offer to: (a) retry the failed epic, or
(b) skip it and continue with the remaining epics. Do not silently
continue past a failure.

#### 4b: Update Changed Epics

For each epic categorized as **Changed** or **Reopened**, render an
updated description and compute the current hash before updating:

```bash
HASH=$(python3 "$SYNC_HELPER" compute-hash .artifacts/design/{issue-key}/06-stories/{epic-file})

DESCRIPTION=$(python3 "$SYNC_HELPER" render-description \
  .artifacts/design/{issue-key}/06-stories/{epic-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type epic \
  --design-doc-link "{link}" \
  --feature-key "{feature-key}")
```

Update the Jira issue using the Jira key from the change plan item:

- **Summary:** re-read the epic title from the current file
- **Description:** the rendered description
- **T-Shirt Size:** re-read from the current file

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields. For **Reopened** items, transition the Jira
issue back to an open status before updating content.

After updating, record the new hash:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation update \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "$HASH" \
  --item-type epic
```

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 4c: Close Removed Epics

For each epic categorized as **Removed** (file has `status: removed`):

1. First, close all stories under this epic that have `synced_status:
   "active"` in the manifest (stories before parent). For each closed
   story, checkpoint with `update-manifest --operation close`.
2. Then transition the epic to Done/Closed in Jira.
3. Record the close:

```bash
HASH=$(python3 "$SYNC_HELPER" compute-hash .artifacts/design/{issue-key}/06-stories/{epic-file})

python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{epic-file}" \
  --jira-key "{jira-key}" \
  --content-hash "$HASH" \
  --item-type epic
```

**Selecting the close transition:** Use the Jira API to query available
transitions for the issue and select the terminal/done-category
transition. If multiple terminal transitions are available, prefer
"Done" over "Closed." If no terminal transition is available from the
current status, report the error and let the user handle it in Jira.

**If close fails:** Report the error and offer to retry or skip.

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

Process stories per epic, in the same three passes: create, update, close.
Use the change plan items filtered by `type: "story"`.

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

For each new story, compute the hash and render the description before
the Jira call:

```bash
HASH=$(python3 "$SYNC_HELPER" compute-hash \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file})

DESCRIPTION=$(python3 "$SYNC_HELPER" render-description \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type story \
  --design-doc-link "{link}" \
  --epic-jira-key "{epic-jira-key}" \
  --story-type "{prefix}")
```

Create the Jira issue:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {epic jira key} (from Step 4) — **set via the `fields` parameter: `{"parent": {"key": "{epic jira key}"}}`**
- **Summary:** `[{prefix}] {story title}`
- **Description:** the rendered description from above

After creating each story, verify the created issue has `parent.key`
equal to the epic's Jira key by reading the issue back. If the parent
is missing, stop and report the error — **do not silently defer parent
linking.** The Epic→Story hierarchy is a required outcome of this step.

Record the Jira key and content hash immediately:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation create \
  --file "{story-file}" \
  --jira-key "{created-key}" \
  --content-hash "$HASH" \
  --item-type story \
  --title "[{prefix}] {story title}" \
  --epic-file "{epic-file}"
```

**Issue links:** After creating the story, create Jira issue links for each
dependency listed in the story. Use `resolve-refs` to resolve dependency
references to Jira keys:

```bash
python3 "$SYNC_HELPER" resolve-refs \
  .artifacts/design/{issue-key}/sync-manifest.json \
  "Story 1.01"
```

If a dependency's Jira key isn't in the manifest (it
wasn't created or failed), the helper annotates it with `[unresolved]` —
skip the link and note it for the user. These links enable downstream
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

For each story categorized as **Changed** or **Reopened**, render an
updated description and compute the hash before updating:

```bash
HASH=$(python3 "$SYNC_HELPER" compute-hash \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file})

DESCRIPTION=$(python3 "$SYNC_HELPER" render-description \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file} \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --type story \
  --design-doc-link "{link}" \
  --epic-jira-key "{epic-jira-key}" \
  --story-type "{prefix}")
```

Update the Jira issue:

- **Summary:** re-read the `[{prefix}] {story title}` from the current file
- **Description:** the rendered description
- **Issue links:** read the Jira issue's current issue links and filter
  to only those matching the link type selected in Step 5a (either
  "Dependency" or "Blocks", whichever was used during creation).
  Compare these filtered links against the artifact file's dependency
  list. Remove links whose dependency stories no longer appear in the
  artifact and create new links for added dependencies, using the same
  link type and direction mapping as Step 5a. Do not touch issue links
  of other types.

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields. For **Reopened** items, transition the Jira
issue back to an open status before updating content.

After updating, record the new hash:

```bash
python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation update \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "$HASH" \
  --item-type story \
  --epic-file "{epic-file}"
```

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 5c: Close Removed Stories

For each story categorized as **Removed** (file has `status: removed`):

1. Transition the story to Done/Closed in Jira.
2. Record the close:

```bash
HASH=$(python3 "$SYNC_HELPER" compute-hash \
  .artifacts/design/{issue-key}/06-stories/{epic-dir}/{story-file})

python3 "$SYNC_HELPER" update-manifest \
  .artifacts/design/{issue-key}/sync-manifest.json \
  --operation close \
  --file "{story-file}" \
  --jira-key "{jira-key}" \
  --content-hash "$HASH" \
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
