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

Read the approved decomposition artifacts, compare them against the sync
manifest and Jira state, and execute the minimal set of Jira operations
needed to bring Jira in line with the artifacts. Always preview before
acting, and always get explicit user approval.

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

## Reference Resolution

When Jira descriptions reference other issues (Dependencies, Documentation
Inputs, Design Reference), replace local identifiers with Jira issue keys:

- `Story 1.01` → look up `story-01-*.md` under `epic-1/` in the manifest → `EDM-XXXX`
- `Epic 1` → look up `epic-1-*.md` in the manifest → `EDM-YYYY`
- `Stories 1.01, 2.01, 3.01` → resolve each → `EDM-XXXX, EDM-AAAA, EDM-BBBB`

The manifest is built incrementally: each issue's key is recorded immediately
after creation. Since epics are created first and stories are created in epic
order (Epic 1 stories before Epic 2 stories), dependencies — which reference
earlier stories — are always resolvable by the time they're needed.

If a reference cannot be resolved (the referenced item hasn't been created
yet or failed to create), leave the local identifier, annotate it with
`[unresolved]`, and flag it to the user.

## Process

### Step 1: Read Decomposition Artifacts and Detect Changes

Read these files:
1. `.artifacts/design/{issue-number}/04-epics.md` (epic metadata and ordering)
2. `.artifacts/design/{issue-number}/05-stories/epic-*.md` (individual epic files)
3. `.artifacts/design/{issue-number}/05-stories/epic-*/story-*.md` (all story files)
4. `.artifacts/design/{issue-number}/03-design.md` (for the Jira link and title)

If these don't exist, tell the user that `/decompose` should be run first.

Check for an existing sync manifest at
`.artifacts/design/{issue-number}/sync-manifest.json`.

#### If no manifest exists

This is a fresh sync. All items will be created. Present:

*"No sync manifest found — this is a fresh sync. All {N} epics and {M}
stories will be created."*

Proceed to Step 2.

#### If a manifest exists

Read it and categorize every item into one of four buckets by comparing
the manifest against the files on disk:

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

**Edge case — reopened:** If a file has no `status: removed` marker but
its manifest entry has `synced_status: "closed"`, the item was previously
closed and has been brought back. Treat it as **Changed** — transition the
Jira issue back to an open status and update its content.

**Edge case — already closed:** If a file has `status: removed` and its
manifest entry has `synced_status: "closed"`, the item was already closed
in a previous sync run. Skip it — no Jira operation needed.

**Edge case — orphaned manifest entries:** After categorizing all files
on disk, scan the manifest for entries with `synced_status: "active"`
whose files no longer exist on disk (the file was deleted rather than
marked with `status: removed`). Only flag active entries — closed
entries whose files were deleted are expected cleanup and can be silently
ignored. Present orphaned active entries to the user:

```text
Warning: {N} manifest entries have no corresponding file on disk.
Their Jira tickets are still open but no artifact tracks them:

| Jira Key | Missing File | Title |
|----------|--------------|-------|
| {EDM-XXXX} | epic-2/story-03-foo.md | [{prefix}] {title} |

Options:
  (a) Close these tickets (treat as removed)
  (b) Ignore for now (leave tickets open, keep manifest entries)
  (c) Stop sync so you can investigate
```

Wait for the user's choice before continuing.

**Edge case — removed story under active epic:** If a story is marked
`status: removed` but its parent epic is still active, check whether the
epic file's Stories section still references the removed story. If it
does, warn the user:

```text
Note: Story {X}.{NN} is marked for closure but is still listed in
Epic {X}'s description. Consider running /revise to update the epic
file before syncing, so the epic's Jira description stays accurate.
```

This is a warning, not a blocker — proceed with the sync if the user
confirms.

**Manifest v1 migration:** If the manifest has `schema_version: 1`
(no `content_hash` or `synced_status` fields), treat all existing items as
`synced_status: "active"` with no stored hash. This means every existing
item will be categorized as **Changed** on the first CRUD sync, which
populates the hashes. Inform the user: *"Migrating manifest from v1 to
v2 — all existing items will be updated once to populate content hashes."*
If any v1 entries have no corresponding file on disk, the
orphaned-entries check (above) will flag them separately.

**Manifest acknowledgment (mandatory).** Before moving to Step 2, present
a summary to the user:

*"Manifest found (last synced {synced_at}): {N} items total — {A} new,
{B} changed, {C} to close, {D} unchanged."*

**If nothing to do** (no new, changed, or removed items), stop and tell
the user:

```text
All items are in sync — nothing to do.
Last synced: {synced_at from manifest}
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

Present a preview of all planned operations:

```markdown
## Jira Sync Preview — {issue-number}

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
| {EDM-XXXX} | `epic-1-{slug}.md` | Summary, Description |
| {EDM-XXXY} | `story-01-{slug}.md` | Description, Dependencies |
| {EDM-XXZZ} | `story-02-{slug}.md` | Reopened (closed → open), Content changed |

To populate "What Changed", compare the current file's title and
sections against the Jira issue's current fields. If this comparison
is impractical, use "Content changed" as the value. For reopened items
(previously closed, now brought back), prefix with "Reopened (closed →
open)" so the status transition is visible.

### To Close ({N} items)

| Jira Key | Local File | Title |
|----------|------------|-------|
| {EDM-XXXX} | `story-03-{slug}.md` | [{prefix}] {title} |
| {EDM-YYYY} | *(orphaned — no artifact file)* | [{prefix}] {title} |

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
close removed epics.

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

For each new epic, create a Jira issue:

- **Type:** Epic
- **Project:** {project key}
- **Parent:** {feature-key} — **mandatory; set via the `fields` parameter: `{"parent": {"key": "{feature-key}"}}`**
- **Summary:** {epic title}
- **Description:**

```markdown
## Summary

{summary from the epic file (05-stories/epic-{N}-{slug}.md)}

## Acceptance Criteria

{acceptance criteria from the epic file}

## Design Reference

Design document: {link to design doc PR or file}
Feature: {feature-key}

## Stories

{list of story titles for this epic}
```

- **T-Shirt Size:** {size} — set via `additional_fields`:
  `{"customfield_10795": {"value": "{size}"}}`

After creating each epic, verify the created issue has `parent.key`
equal to `{feature-key}` by reading the issue back. If the parent is
missing, stop and report the error — **do not silently defer parent
linking to a "Next Steps" section.** The Feature→Epic hierarchy is a
required outcome of this step, not an optional follow-up.

Record the Jira key and content hash in the sync manifest immediately
(before creating the next epic). Set `synced_status: "active"`.

**If creation fails:** Stop immediately. Report which epics were created
successfully (they are already recorded in the manifest) and which one
failed, including the error. Offer to: (a) retry the failed epic, or
(b) skip it and continue with the remaining epics. Do not silently
continue past a failure.

#### 4b: Update Changed Epics

For each epic categorized as **Changed**, update the Jira issue using
the Jira key from the manifest:

- **Summary:** re-read the epic title from the current file
- **Description:** re-render the full description from the current file
  content (same template as creation above), resolving all references
- **T-Shirt Size:** re-read from the current file

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields.

After updating, record the new `content_hash` in the manifest.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 4c: Close Removed Epics

For each epic categorized as **Removed** (file has `status: removed`):

1. First, close all stories under this epic that have `synced_status:
   "active"` in the manifest (stories before parent). For each closed
   story, set its `synced_status: "closed"` and update its
   `content_hash` to the current file hash.
2. Then transition the epic to Done/Closed in Jira.
3. Update the manifest entry: set `synced_status: "closed"` and update
   `content_hash` to the current file hash.

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

For each new story under each epic, create a Jira issue:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {epic jira key} (from Step 4) — **set via the `fields` parameter: `{"parent": {"key": "{epic jira key}"}}`**
- **Summary:** `[{prefix}] {story title}`
- **Description:**

**For `[DEV]`, `[UI]`, `[UX]`, `[QE]`, and `[CI]` stories:**

```markdown
## User Story

**As a** {role},
**I want to** {capability},
**So that** {benefit}.

## Acceptance Criteria

{acceptance criteria from story file}

## Implementation Guidance

{implementation guidance from story file}

## Testing Approach

{testing approach from story file}

## Dependencies

{dependencies from story file, with local references resolved to Jira keys
 per the Reference Resolution section}

## Design Reference

Design document: {link to design doc PR or file}
Epic: {epic jira key}
PRD Requirements: {requirement IDs}
Design section: {§reference}
```

**For `[DOCS]` stories:**

```markdown
## User Story

**As a** {role},
**I want to** {capability},
**So that** {benefit}.

## Acceptance Criteria

{acceptance criteria from story file}

## Documentation Scope

{documentation scope from story file}

## Documentation Inputs

{documentation inputs from story file, with story references resolved to
 Jira keys: "**Story 1.01 — {title}:**" → "**EDM-XXXX — {title}:**"}

## Dependencies

{dependencies from story file, with local references resolved to Jira keys
 per the Reference Resolution section}

## Design Reference

Design document: {link to design doc PR or file}
Epic: {epic jira key}
PRD Requirements: {requirement IDs}
Design section: {§reference}
```

**Reference resolution:** Before submitting the description, resolve all
local identifiers to Jira keys (see Reference Resolution). This applies to
Dependencies (`Story 1.01` → `EDM-XXXX`), Documentation Inputs
(`Story 1.01` → `EDM-XXXX`), and Design Reference
(`Epic 1` → `EDM-YYYY`).

After creating each story, verify the created issue has `parent.key`
equal to the epic's Jira key by reading the issue back. If the parent
is missing, stop and report the error — **do not silently defer parent
linking.** The Epic→Story hierarchy is a required outcome of this step.

Record the Jira key and content hash in the sync manifest immediately
(before creating the next story). Set `synced_status: "active"`.

**Issue links:** After creating the story, create Jira issue links for each
dependency listed in the story. Resolve dependency references to Jira keys
using the manifest. If a dependency's Jira key isn't in the manifest (it
wasn't created or failed), skip the link and note it for the user. These
links enable downstream workflows (e.g., docs-writer) to traverse the
dependency chain via the Jira API.

For each dependency, create a link where the current story **depends on**
the dependency story. Try the Jira "Dependency" link type first
(relationship `"depends on"` / `"is depended on by"`). If the API
returns an error indicating the link type is not available, fall back to
"Blocks" (where the dependency story **blocks** the current story).
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

For each story categorized as **Changed**, update the Jira issue using
the Jira key from the manifest:

- **Summary:** re-read the `[{prefix}] {story title}` from the current file
- **Description:** re-render the full description from the current file
  content (same template as creation above), resolving all references
- **Issue links:** read the Jira issue's current issue links and compare
  against the artifact file's dependency list. Remove links that no
  longer appear in the artifact and create new links for added
  dependencies.

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields.

After updating, record the new `content_hash` in the manifest.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 5c: Close Removed Stories

For each story categorized as **Removed** (file has `status: removed`):

1. Transition the story to Done/Closed in Jira.
2. Update the manifest entry: set `synced_status: "closed"` and update
   `content_hash` to the current file hash.

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
operation was recorded immediately after success). Verify the manifest is
complete and consistent. The final structure should be:

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
- `.artifacts/design/{issue-number}/sync-manifest.json` (v2 schema)

## When This Phase Is Done

Report your results:
- All Jira issue keys affected (created, updated, closed)
- Summary of the hierarchy (Feature → Epics → Stories)
- Any next steps (e.g., assign stories to team members, set sprint)

Then **re-read the controller** (`controller.md`) for next-step guidance.
