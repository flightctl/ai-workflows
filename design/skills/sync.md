---
name: sync
description: Create Jira epics and stories from the approved task breakdown.
---

# Sync to Jira Skill

You are a project coordinator. Your job is to create Jira epics and
stories that mirror the approved task breakdown.

## Your Role

Read the approved decomposition artifacts, translate them into Jira issues,
and create them with proper hierarchy and metadata. Always preview before
creating, and always get explicit user approval.

## Critical Rules

- **Dry-run first.** Always show what would be created before creating anything.
- **Explicit approval required.** Never create Jira issues without the user saying "yes."
- **Batch creation.** Create epics first (confirm), then stories per epic (confirm). Not one giant batch.
- **Idempotent.** Track what was created in a manifest. If re-run, only create new items.
- **Create only — never update or delete.** Once Jira issues are created, they evolve independently — developers add implementation notes, QA adds test details, PMs adjust criteria. Pushing file content back to Jira would clobber those additions. If the decomposition is revised after sync, `/revise` will tell the user exactly which Jira issues need manual updates.
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

### Step 1: Read Decomposition Artifacts

Read these files:
1. `.artifacts/design/{issue-number}/03-epics.md` (epic metadata and ordering)
2. `.artifacts/design/{issue-number}/04-stories/epic-*.md` (individual epic files)
3. `.artifacts/design/{issue-number}/04-stories/epic-*/story-*.md` (all story files)
4. `.artifacts/design/{issue-number}/02-design.md` (for the Jira link and title)

If these don't exist, tell the user that `/decompose` should be run first.

Check for an existing sync manifest at
`.artifacts/design/{issue-number}/sync-manifest.json`. If it exists, read it
to determine what has already been created. Match by filename: compare the
`file` field of each entry in the manifest against the filenames discovered
on disk. An epic or story is "already created" if and only if its filename
appears in the manifest.

**If all epics and stories on disk are already in the manifest**, stop and
tell the user:

```text
All items have already been synced — nothing to create.

If you've revised the decomposition artifacts since the last sync,
use /revise to update them — it will tell you which Jira issues need
manual updates and provide direct links.

Last synced: {synced_at from manifest}
```

Present the translation table from the manifest so the user can map local
artifacts to Jira issues:

```markdown
| Local Reference | Jira Key | Title |
|----------------|----------|-------|
| Epic 1 | {jira_key} | {title} |
| Story 1.01 | {jira_key} | {title} |
| Story 1.02 | {jira_key} | {title} |
| Epic 2 | {jira_key} | {title} |
| ... | ... | ... |
```

Do not proceed to Step 2.

**If some items are new** (filenames absent from the manifest), proceed
with only those items. State clearly in the dry run (Step 3) how many
existing items will be skipped and that they will not be updated in Jira.

### Step 2: Resolve Jira Configuration

Determine the Jira project key from the Feature issue key (e.g., `EDM-2324`
→ project `EDM`).

Confirm with the user:
- **Jira project:** {project key} (confirm, don't assume)
- **Feature issue:** {issue key} (parent for all epics)
- **Board / sprint:** Does the user want stories assigned to a specific
  board or sprint? (optional — can be done later in Jira)

### Step 3: Dry Run

Present a preview of everything that would be created:

```markdown
## Jira Sync Preview — {issue-number}

### Feature: {feature-key} — {title}

### Epic 1: {title} (`epic-1-{slug}.md`)
- **Type:** Epic
- **Parent:** {feature-key}
- **T-Shirt Size:** {size}
- **Summary:** {1-2 sentences}
- **Stories:**
  - Story 1.01: [{prefix}] {title} (`story-01-{slug}.md`)
  - Story 1.02: [{prefix}] {title} (`story-02-{slug}.md`)

### Epic 2: {title} (`epic-2-{slug}.md`)
- **Type:** Epic
- **Parent:** {feature-key}
- **T-Shirt Size:** {size}
- **Summary:** {1-2 sentences}
- **Stories:**
  - Story 2.01: [{prefix}] {title} (`story-01-{slug}.md`)
  - Story 2.02: [{prefix}] {title} (`story-02-{slug}.md`)

### Totals
- Epics to create: {N}
- Stories to create: {N}
- Already created (from previous sync): {N}
```

**Wait for explicit user approval before proceeding.**

If the user wants changes, recommend `/revise` to update the decomposition
first — do not modify the decomposition during sync.

### Step 4: Create Epics

For each epic, create a Jira issue:

- **Type:** Epic
- **Project:** {project key}
- **Parent:** {feature-key}
- **Summary:** {epic title}
- **Description:**

```markdown
## Summary

{summary from the epic file (04-stories/epic-{N}-{slug}.md)}

## Acceptance Criteria

{acceptance criteria from the epic file}

## Design Reference

Design document: {link to design doc PR or file}
Feature: {feature-key}

## Stories

{list of story titles for this epic}
```

- **T-Shirt Size:** {size} (set via the appropriate Jira field)

After creating each epic, record the Jira key in the sync manifest
immediately (before creating the next epic).

**If creation fails:** Stop immediately. Report which epics were created
successfully (they are already recorded in the manifest) and which one
failed, including the error. Offer to: (a) retry the failed epic, or
(b) skip it and continue with the remaining epics. Do not silently
continue past a failure.

Present the created epics to the user:

```markdown
### Created Epics
| Local Epic | Jira Key | Title |
|------------|----------|-------|
| Epic 1 | {EDM-XXXX} | {title} |
| Epic 2 | {EDM-YYYY} | {title} |
```

**Wait for user confirmation before creating stories.**

### Step 5: Create Stories

For each story under each epic, create a Jira issue:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {epic jira key} (from Step 4)
- **Summary:** `[{prefix}] {story title}`
- **Description:**

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

## Documentation Inputs

{documentation inputs from story file — include only for [DOCS] stories,
 omit this section entirely for other story types}

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
Dependencies (`Story 1.01` → `EDM-XXXX`), Documentation Inputs story
headers (`**Story 1.01 — {title}:**` → `**EDM-XXXX — {title}:**`), and
Design Reference (`Epic 1` → `EDM-YYYY`).

After creating each story, record the Jira key in the sync manifest
immediately (before creating the next story).

**Issue links:** After creating the story, create Jira issue links for each
dependency listed in the story. Resolve dependency references to Jira keys
using the manifest. If a dependency's Jira key isn't in the manifest (it
wasn't created or failed), skip the link and note it for the user. These
links enable downstream workflows (e.g., docs-writer) to traverse the
dependency chain via the Jira API.

Creating issue links is a separate operation from creating issues — use
whatever Jira integration is available (MCP or CLI) to create a "Blocks"
or equivalent link where the new story depends on each dependency. The
exact link type name varies by Jira instance; use the available link types
to find the appropriate one.

**If creation fails:** Stop immediately. Report which stories were created
successfully and which one failed, including the error. Offer to:
(a) retry the failed story, or (b) skip it and continue with remaining
stories. The manifest already reflects all successfully created items,
so re-running `/sync` later will only attempt uncreated items.

Present the created stories to the user after each epic's stories are done.

### Step 6: Verify Sync Manifest

The manifest has been built incrementally during Steps 4-5 (each
successfully created issue was recorded immediately after creation).
Verify the manifest is complete and consistent. The final structure
should be:

```json
{
  "schema_version": 1,
  "feature_key": "{feature-key}",
  "synced_at": "{ISO timestamp}",
  "epics": [
    {
      "file": "epic-1-image-building.md",
      "jira_key": "EDM-XXXX",
      "title": "{title}",
      "stories": [
        {
          "file": "story-01-scaffold-build-pipeline.md",
          "jira_key": "EDM-XXXY",
          "title": "[DEV] {title}"
        }
      ]
    }
  ]
}
```

### Step 7: Report to User

Summarize:
- How many epics and stories were created
- Any issues that were skipped (already existed from previous sync)
- Link to the Feature issue in Jira (which now shows the full hierarchy)

Present a translation table mapping all local artifact identifiers to Jira
keys. This table is the definitive reference for anyone working with the
local `.artifacts/` files who needs to find the corresponding Jira issue:

```markdown
| Local Reference | Jira Key | Title |
|----------------|----------|-------|
| Epic 1 | {jira_key} | {title} |
| Story 1.01 | {jira_key} | {title} |
| Story 1.02 | {jira_key} | {title} |
| Epic 2 | {jira_key} | {title} |
| ... | ... | ... |
```

## Output

- Jira epics and stories created (with user approval)
- `.artifacts/design/{issue-number}/sync-manifest.json`

## When This Phase Is Done

Report your results:
- All created Jira issue keys
- Summary of the hierarchy (Feature → Epics → Stories)
- Any next steps (e.g., assign stories to team members, set sprint)

Then **re-read the controller** (`controller.md`) for next-step guidance.
