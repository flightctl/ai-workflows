---
name: sync
description: Create, update, or close [DEV] Jira stories for API gaps identified during the UI design review.
---

# Sync API Gap Stories to Jira

You are a project coordinator. Your job is to keep Jira `[DEV]` stories
in sync with the API gaps identified during the UI design review —
creating new stories for new gaps, updating stories for changed gaps, and
closing stories for resolved gaps.

## Your Role

The API findings in the UI design document are the source of truth. Jira
is the downstream projection. When findings change, Jira should follow.

Read the API findings, compare them against the sync manifest and Jira
state, and execute the minimal set of Jira operations needed to bring Jira
in line with the findings. Always preview before acting, and always get
explicit user approval.

## Critical Rules

- **Dry-run first.** Always show what would be created, updated, or closed before doing anything.
- **Explicit approval required.** Never modify Jira without the user saying "yes."
- **Idempotent.** Track what was synced in a manifest with content hashes. If re-run with no changes, do nothing.
- **Manifest gate.** Before proceeding past Step 1, you **must** state aloud to the user what the manifest contains (or that none exists). This is mandatory — do not silently skip this acknowledgment.
- **Jira-side duplicate check.** Before creating each story, query Jira for existing children under the parent with a matching summary. If a match is found, stop and present the match to the user — do not create a duplicate.
- **Sync-owned fields.** Sync owns: summary, description, and parent link (creation only). Sync never touches: status, assignee, sprint, comments, labels, or any other Jira-managed field.
- **Logical deletion via status.** Gaps are closed (not deleted) when they are resolved — the gap entry is removed from the API findings or marked as resolved. The manifest tracks the closure.
- **Link to source.** Every Jira story description references the UI design document.

## Process

### Step 1: Read API Findings and Detect Changes

Read these files:
1. `.artifacts/ui-design/{issue-key}/02-ui-design.md` — for the API Findings
   section (or the reference to `03-api-findings.md`)
2. `.artifacts/ui-design/{issue-key}/03-api-findings.md` — if the API findings
   are in a separate file
3. `.artifacts/ui-design/{issue-key}/01-context.md` — for the parent story
   and feature context

If no API findings exist (no API Findings section and no `03-api-findings.md`),
tell the user that `/review-api` should be run first.

Extract every gap from the API Gaps table. Each gap that has severity
`critical`, `high`, or `medium` is a candidate for a `[DEV]` story.
Low-severity gaps are tracked in the manifest but not synced to Jira
unless the user explicitly requests it.

Check for an existing sync manifest at
`.artifacts/ui-design/{issue-key}/sync-manifest.json`.

#### If no manifest exists

This is a fresh sync. Present:

*"No sync manifest found — this is a fresh sync. {N} API gaps qualify
for [DEV] stories ({C} critical, {H} high, {M} medium). {L} low-severity
gaps will be tracked but not synced."*

Proceed to Step 2.

#### If a manifest exists

Read it and categorize every gap into one of four buckets by comparing
the manifest against the current API findings:

1. **New** — gap exists in the findings, no matching entry in the manifest.
   Action: create a `[DEV]` story in Jira.

2. **Changed** — gap exists in the findings, matching entry in the manifest
   with `synced_status: "active"`, and the SHA-256 hash of the gap's
   content differs from the stored `content_hash`.
   Action: update the sync-owned fields in Jira.

3. **Resolved** — gap was in the manifest with `synced_status: "active"`,
   but is no longer in the current API findings (the gap was resolved
   during `/revise` or `/respond`).
   Action: close (transition to Done/Closed) the Jira story.

4. **Unchanged** — gap exists in both findings and manifest, content hash
   matches.
   Action: skip.

**Edge case — reopened:** If a gap reappears in the findings but its
manifest entry has `synced_status: "closed"`, the gap was previously
resolved and has returned. Treat it as **Changed** — transition the
Jira issue back to an open status and update its content.

**Edge case — already closed:** If a manifest entry has
`synced_status: "closed"` and the gap is still absent from the findings,
the issue was already closed in a previous sync run. Skip it.

**Manifest acknowledgment (mandatory).** Before moving to Step 2, present
a summary to the user:

*"Manifest found (last synced {synced_at}): {N} items total — {A} new,
{B} changed, {C} to close, {D} unchanged."*

**If nothing to do** (no new, changed, or resolved items), stop and tell
the user:

```text
All items are in sync — nothing to do.
Last synced: {synced_at from manifest}
```

Present the translation table from the manifest and do not proceed to
Step 2.

### Step 2: Resolve Jira Configuration

Determine the parent for the `[DEV]` stories. The stories should be
created under the same parent epic as the `[UI]` story, or under the
Feature if the `[UI]` story has no parent epic.

Read the `[UI]` story's parent from `01-context.md`:
- If the `[UI]` story has a parent **epic**, use that epic as the parent
  for `[DEV]` stories.
- If the `[UI]` story has a parent **feature** but no epic, use the
  feature as the parent. The `[DEV]` stories will be top-level stories
  under the feature.

Confirm with the user:
- **Jira project:** {project key}
- **Parent issue:** {epic or feature key} (parent for all `[DEV]` stories)

### Step 3: Dry Run

Present a preview of all planned operations:

```markdown
## Jira Sync Preview — {issue-key}

### Parent: {parent-key} — {parent title}

### To Create ({N} stories)

| # | Gap | Severity | Story Summary |
|---|-----|----------|---------------|
| 1 | {gap title} | {severity} | [DEV] {proposed story title} |
| 2 | {gap title} | {severity} | [DEV] {proposed story title} |

### To Update ({N} stories)

| Jira Key | Gap | What Changed |
|----------|-----|--------------|
| {key} | {gap title} | {description of what changed} |

### To Close ({N} stories)

| Jira Key | Gap | Reason |
|----------|-----|--------|
| {key} | {gap title} | Gap resolved — {brief reason} |

### Unchanged ({N} stories — skipped)

### Low-Severity Gaps (not synced)

| # | Gap | Severity | Notes |
|---|-----|----------|-------|
| {n} | {gap title} | low | {why it's low — e.g., "client-side workaround available"} |

### Totals
- To create: {N}
- To update: {N}
- To close: {N}
- Unchanged: {N}
- Low-severity (tracked, not synced): {N}
```

**Wait for explicit user approval before proceeding.**

If the user wants changes, recommend `/revise` to update the API findings
first — do not modify the findings during sync.

### Step 4: Sync Stories

Process stories in three passes: create new, update changed, close resolved.

#### 4a: Create New Stories

**Pre-creation duplicate check (per story).** Before creating each story,
search Jira for existing children of the parent with a matching summary:

```
parent = {parent-key} AND issuetype = Story AND summary ~ "[DEV] {gap title}"
```

If the query returns one or more matching issues, **do not create the
story.** Stop and present the match to the user:

```text
Duplicate detected — a story with a matching summary already exists
under {parent-key}:

  {matching-key}: {matching summary}

Options:
  (a) Skip this story and record the existing key in the manifest
  (b) Create it anyway (will produce a duplicate)
  (c) Stop sync entirely so you can investigate
```

Wait for the user's choice before continuing.

For each new story, create a Jira issue:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {parent key} — **set via the `fields` parameter: `{"parent": {"key": "{parent-key}"}}`**
- **Summary:** `[DEV] {gap title}`
- **Description:**

```markdown
## Summary

{Gap description — what the UI needs and what the backend currently provides.}

## Context

- **UI Story:** {issue-key}
- **UI Design:** {link to UI design PR or published doc}
- **Gap Category:** {data / field / state / pagination / filtering / sorting / shape / permission}
- **Gap Severity:** {critical / high / medium}

## What's Needed

{Specific description of what the backend needs to provide — the "What's
missing" field from the gap detail.}

## UI Impact

{Which UI components depend on this and how they are affected.}

## Suggested Approach

{High-level hint from the gap detail, if one was provided.}

## Acceptance Criteria

- The API provides {specific data/field/capability} as described above
- The response shape is compatible with the UI's data flow mapping
- {Additional criteria based on the gap type}
```

After creating each story, verify the parent link by reading the issue
back. If the parent is missing, stop and report the error.

Record the Jira key and content hash in the sync manifest immediately
(before creating the next story). Set `synced_status: "active"`.

**If creation fails:** Stop immediately. Report which stories were created
successfully and which one failed. Offer to retry or skip.

#### 4b: Update Changed Stories

For each story categorized as **Changed**, update the Jira issue using
the Jira key from the manifest:

- **Summary:** re-derive `[DEV] {gap title}` from the current gap
- **Description:** re-render the full description from the current gap
  content (same template as creation above)

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields.

After updating, record the new `content_hash` in the manifest.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 4c: Close Resolved Stories

For each story categorized as **Resolved** (gap no longer in findings):

1. Transition the story to Done/Closed in Jira.
2. Update the manifest entry: set `synced_status: "closed"` and update
   `content_hash`.

**Selecting the close transition:** Use the Jira API to query available
transitions for the issue and select the terminal/done-category
transition. Prefer "Done" over "Closed." If no terminal transition is
available, report the error and let the user handle it in Jira.

**If close fails:** Report the error and offer to retry or skip.

Present the results:

```markdown
### Sync Results

| Operation | Gap | Jira Key | Title |
|-----------|-----|----------|-------|
| Created | {gap title} | {key} | [DEV] {title} |
| Updated | {gap title} | {key} | [DEV] {title} |
| Closed | {gap title} | {key} | [DEV] {title} |
```

### Step 5: Verify Sync Manifest

The manifest has been built/updated incrementally during Step 4. Verify
it is complete and consistent. The final structure should be:

```json
{
  "schema_version": 2,
  "ui_story_key": "{issue-key}",
  "parent_key": "{parent-key}",
  "synced_at": "{ISO timestamp}",
  "gaps": [
    {
      "gap_number": 1,
      "title": "{gap title}",
      "category": "{gap category}",
      "severity": "{severity}",
      "jira_key": "{DEV story key}",
      "content_hash": "{sha256-of-gap-content}",
      "synced_status": "active"
    }
  ]
}
```

Fields:
- `content_hash` — SHA-256 of the gap's content (title + category +
  severity + description + what's missing + UI impact + suggested approach).
  Used to detect changes on the next run.
- `synced_status` — `"active"` or `"closed"`. Tracks the last state sync
  pushed to Jira.
- `synced_at` — top-level only. Updated to the current timestamp at the
  end of each sync run.

### Step 6: Report to User

Summarize:
- How many stories were created, updated, closed, and unchanged
- Confirm the hierarchy: every story has parent = {parent-key}
- Link to the parent issue in Jira

Present a translation table mapping gap numbers to Jira keys:

```markdown
| Gap # | Gap Title | Jira Key | Status | Severity |
|-------|-----------|----------|--------|----------|
| 1 | {title} | {key} | active | {severity} |
| 2 | {title} | {key} | active | {severity} |
| 3 | {title} | {key} | closed | {severity} |
```

## Output

- Jira `[DEV]` stories created, updated, or closed (with user approval)
- `.artifacts/ui-design/{issue-key}/sync-manifest.json` (v2 schema)

## When This Phase Is Done

Report your results:
- All Jira issue keys affected (created, updated, closed)
- Summary of the gap → story mapping
- Any next steps (e.g., assign stories to backend team, prioritize critical gaps)

Then **re-read the controller** (`controller.md`) for next-step guidance.
