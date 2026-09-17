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
- **Sync-owned fields.** Sync owns: summary, description, and parent link (creation only). Sync never touches: assignee, sprint, comments, labels, or any other Jira-managed field.
- **Status transitions are limited.** Sync may only perform two status transitions: (1) transition resolved issues to Done/Closed, and (2) reopen previously closed issues when a gap reappears. Sync must not edit status for any other reason.
- **Logical deletion via status.** Gaps are closed (not deleted) when they are resolved — the gap entry is removed from the API findings or marked as resolved. The manifest tracks the closure.
- **Link to source.** Every Jira story description references the UI design document.

## Prerequisites

**Jira access required.** This phase creates, updates, and closes Jira
issues. Before starting, verify that Jira MCP tools are available by
confirming you can read an issue (e.g., the parent story from
`01-context.md`). If Jira tools are unavailable or return authentication
errors, **stop immediately** and report the issue to the user — do not
fall back to a no-op or skip Jira operations silently. The user must
resolve the Jira connectivity issue before `/sync` can proceed.

## Process

### Step 1: Read API Findings and Detect Changes

Read these files:
1. `.artifacts/ui-design/{issue-key}/02-ui-design.md` — for the API Findings
   section (or the reference to `03-api-findings.md`)
2. `.artifacts/ui-design/{issue-key}/03-api-findings.md` — if the API findings
   are in a separate file
3. `.artifacts/ui-design/{issue-key}/01-context.md` — for the parent story
   and feature context

If no API findings exist (no API Findings section in `02-ui-design.md` and
no `03-api-findings.md`), stop and tell the user that `/review-api` should
be run first. If the API Findings section exists but contains only the
pending-findings marker (no gaps table), stop and report that the findings
are incomplete. If any required file is unreadable, stop and report the
error before performing any Jira operations.

Extract every gap from the API Gaps table. Each gap row must contain a
`gap_id` field produced by the `/review-api` phase (see
`03-review-api.md` — Gap ID derivation). Use this producer-provided
`gap_id` as the sole matching key when comparing findings with the
manifest; do not re-derive or recompute it during sync, and do not
match by `gap_number` or title alone. If any gap row is missing a
`gap_id`, stop and tell the user to re-run `/review-api` — the
findings pre-date the gap_id requirement. Continue using
`content_hash` only to detect changes for matched active entries.

**Zero-gap guard:** If the API findings section is non-empty (contains
a gaps table or narrative content) but parsing produces zero extracted
gaps, do not silently proceed. Stop and warn the user:

*"The API Findings section contains content but no gaps could be
extracted. This may indicate a formatting issue in the findings table.
Please verify the API Findings section and re-run /sync."*

Wait for the user to confirm before proceeding — either they fix the
findings or explicitly confirm that zero gaps is correct.

**Canonical content_hash computation.** To ensure `content_hash`
changes whenever a Jira-rendered field changes, define the hash
payload as the sorted JSON serialization of exactly these fields:

```json
{
  "affected_components": "{affected components}",
  "category": "{gap category}",
  "current_state": "{current state}",
  "severity": "{severity}",
  "suggested_approach": "{suggested approach}",
  "ui_need": "{UI need}",
  "whats_missing": "{what's missing}"
}
```

Compute `content_hash = SHA-256(JSON.stringify(payload))` where keys
are sorted alphabetically (as shown above) and values are trimmed of
leading/trailing whitespace. This set of fields matches exactly what
gets rendered into the Jira description template — any change to a
rendered field triggers an update.

Each gap that has severity
`critical`, `high`, or `medium` is a candidate for a `[DEV]` story.
Low-severity gaps are tracked in the manifest but not synced to Jira
unless the user explicitly requests it.

Check for an existing sync manifest at
`.artifacts/ui-design/{issue-key}/sync-manifest.json`.

#### If the manifest is unreadable or invalid

If the file exists but cannot be parsed as JSON, or the parsed content
does not match the expected schema (missing `schema_version`, `gaps`
array, or required fields per gap entry), **stop immediately** and
report the error to the user:

*"Sync manifest exists but is unreadable or contains invalid data:
{error details}. Please fix or delete the manifest before re-running
/sync."*

Do not fall back to a fresh sync when the manifest is corrupt — the
user must decide whether to repair it or start fresh.

#### If no manifest exists

This is a fresh sync. Present:

*"No sync manifest found — this is a fresh sync. {N} API gaps qualify
for [DEV] stories ({C} critical, {H} high, {M} medium). {L} low-severity
gaps will be tracked but not synced."*

Proceed to Step 2.

#### If a manifest exists

Read it and categorize every gap into one of four buckets by comparing
the manifest against the current API findings:

1. **New** — gap exists in the findings with severity `critical`, `high`,
   or `medium`, and no matching entry in the manifest.
   Action: create a `[DEV]` story in Jira.

   **New (Tracked)** — gap exists in the findings with severity `low`
   and no matching entry in the manifest.
   Action: create a manifest entry with `synced_status: "tracked"` — no
   Jira story is created.

2. **Changed** — gap exists in the findings, matching entry in the manifest
   with `synced_status: "active"`, and the SHA-256 hash of the gap's
   content differs from the stored `content_hash`.
   Action: update the sync-owned fields in Jira.

3. **Resolved** — a gap should be closed when its manifest entry has
   `synced_status: "active"` and either condition is met:
   - Its `gap_id` is no longer present in the current API findings (the
     gap was removed during `/revise` or `/respond`), OR
   - Its row in the findings table has a resolved marker — a `status`
     column value of "resolved" or "fixed". Check each gap row for this
     resolved marker before active-gap matching; resolved-marker rows are
     routed to this bucket using the same close workflow as absent gaps.

   Action: close (transition to Done/Closed) the Jira story.

   **Empty-findings guard:** If the current findings section has no gaps
   at all but the manifest has active entries, do not automatically treat
   all entries as resolved. Stop and ask the user to confirm: *"The API
   Findings section is now empty, but {N} stories are active in the
   manifest. Close all of them, or investigate first?"* Only proceed
   with closures after explicit confirmation.

4. **Unchanged** — gap exists in both findings and manifest, content hash
   matches.
   Action: skip.

**Edge case — reopened:** If a gap reappears in the findings but its
manifest entry has `synced_status: "closed"`, the gap was previously
resolved and has returned. Treat it as **Changed** — transition the
Jira issue back to an open status, update its content, and set
`synced_status` back to `"active"` in the manifest. Without this
reset, the next sync run would see `synced_status: "closed"` and
attempt to reopen the issue again.

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

**Promotion check (tracked → active).** Before processing the three
passes below, scan manifest entries with `synced_status: "tracked"`.
For each tracked entry, compare its current severity in the findings:
- If the severity has increased to `medium`, `high`, or `critical`,
  promote the entry to the **New** bucket — it will receive a Jira
  story in pass 4a.
- If the severity is still `low`, leave it tracked.
- If the gap is no longer in the findings, route it to the **Resolved**
  bucket to mark it closed in the manifest.

Process stories in four passes: promote tracked, create new, update
changed, close resolved.

#### 4a: Create New Stories

**Pre-creation duplicate check (per story).** Before creating each story,
query by the `gap_id` value embedded in the description rather than
fuzzy-matching the summary. The HTML comment marker
(`<!-- gap_id: {gap_id} -->`) remains in the description for display
purposes, but Jira's `~` text-search operator does not index
punctuation characters (`<`, `!`, `-`, `>`), so the JQL query must use
exact-phrase syntax on the plain-text portion instead.

Compute `jql_escaped_gap_id` by escaping any backslashes and
double-quotes in `gap_id` (e.g., `\` → `\\`, `"` → `\"`). Then query:

```
parent = {parent-key} AND issuetype = Story AND description ~ "\"gap_id: {jql_escaped_gap_id}\""
```

If the query returns exactly one matching issue, present it to the user:

```text
Duplicate detected — a story matching gap_id "{gap_id}" already exists
under {parent-key}:

  {matching-key}: {matching summary}

Options:
  (a) Skip this gap and link the existing story in the manifest
  (b) Stop sync entirely so you can investigate
```

If the query returns **multiple** matching issues, list ALL matches and
require the user to select one before proceeding:

```text
Multiple stories matching gap_id "{gap_id}" found under {parent-key}:

  1. {key-1}: {summary-1}
  2. {key-2}: {summary-2}
  ...

Options:
  (a) Select one to link in the manifest (provide the number)
  (b) Stop sync entirely so you can investigate
```

Do NOT bind the manifest to an arbitrary single match — the user must
choose which existing story to link.

Never offer a "create anyway" option — creating a duplicate story
contradicts the critical rule against duplicate creation. The only
paths forward are to link to an existing story or stop to investigate.

Wait for the user's choice before continuing.

For each new story, create a Jira issue:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {parent key} — **set via the `fields` parameter: `{"parent": {"key": "{parent-key}"}}`**
- **Summary:** `[DEV] {gap title}`
- **Description:**

Before rendering the description, load `pr_url` from
`.artifacts/ui-design/{issue-key}/publish-metadata.json`. Validate
that `pr_url` is a non-empty string containing a parseable HTTPS URL
with a non-empty host and at least one path segment — i.e., it must
match the pattern `https://{host}/{path}` where `{host}` is a valid
hostname (e.g., `github.com`) and `{path}` contains at least one
non-empty segment. Values like `https://`, `https://placeholder`, or
any URL without a `/`-separated path after the host are invalid. If
the file does not exist, `pr_url` is absent, null, empty, or does not
satisfy this validation, stop and tell the user that `/publish` should
be run first — do not create stories with an unresolved or invalid
design link.

```markdown
<!-- gap_id: {gap_id} -->

## Summary

{Gap description — what the UI needs and what the backend currently provides.}

## Context

- **UI Story:** {issue-key}
- **UI Design:** {pr_url from publish-metadata.json}
- **Gap ID:** {gap_id}
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
successfully and which one failed. Offer to retry or skip. Before retrying
a failed create, re-run the JQL duplicate check (the same `gap_id` query
from the pre-creation check above). If the issue now exists — e.g., Jira
committed the story but the response timed out — treat it as a successful
create: present the found issue to the user, record its key and content
hash in the manifest with `synced_status: "active"`, and continue to the
next gap. Only attempt a fresh create if the duplicate check confirms no
matching issue exists.

#### 4b: Update Changed Stories

Before updating any stories, load `pr_url` from
`.artifacts/ui-design/{issue-key}/publish-metadata.json`. Apply the
same validation as step 4a: `pr_url` must be a non-empty string
containing a parseable HTTPS URL with a non-empty host and at least
one path segment (matching `https://{host}/{path}`). Values like
`https://`, `https://placeholder`, or any URL without a `/`-separated
path after the host are invalid. If the file does not exist, `pr_url`
is absent, null, empty, or does not satisfy this validation, stop and
tell the user that `/publish` should be run first — the description
template requires the design PR link.

For each story categorized as **Changed**, update the Jira issue using
the Jira key from the manifest:

- **Summary:** re-derive `[DEV] {gap title}` from the current gap
- **Description:** re-render the full description from the current gap
  content (same template as creation above, including the `pr_url`)

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields.

After updating, record the new `content_hash` in the manifest.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 4c: Close Resolved Stories

For each story categorized as **Resolved** (gap no longer in findings):

1. Add a comment to the Jira story explaining the closure:
   *"Closing — the API gap '{gap title}' is no longer present in the UI
   design findings (resolved during /revise or /respond). See the UI
   design PR for details: {pr_url}."*
2. Transition the story to Done/Closed in Jira.
3. Update the manifest entry: set `synced_status: "closed"` and record
   `closed_at` with the current ISO timestamp. Preserve the prior
   `content_hash` — do not replace it. This allows deterministic reopen
   detection: if a gap with the same `gap_id` reappears in a future sync,
   the preserved hash enables detecting whether the content changed since
   the issue was closed.

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
      "gap_id": "{category}-{hash12}",
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
- `gap_id` — Producer-owned stable identifier emitted by the
  `/review-api` phase and embedded in each gap row of the API findings.
  Format: `{category_slug}-{first 12 hex chars of SHA-256(category +
  "|" + data_element + "|" + endpoint_or_na)}` (e.g.,
  `field-a1b2c3d4e5f6`). Sync reads this value from the findings and
  stores it verbatim — it never re-derives or recomputes the hash.
  Used as the sole matching key between findings and manifest entries.
- `jira_key` — The Jira story key. Present for entries with
  `synced_status: "active"` or `"closed"`. Omitted for entries with
  `synced_status: "tracked"` (low-severity gaps not synced to Jira).
- `content_hash` — SHA-256 of the canonical gap payload: sorted JSON
  of `{affected_components, category, current_state, severity,
  suggested_approach, ui_need, whats_missing}` (see "Canonical
  content_hash computation" above). Used to detect changes on the next
  run. Preserved (not replaced) when closing an issue, to support
  deterministic reopen detection.
- `synced_status` — One of `"active"`, `"closed"`, or `"tracked"`.
  `"active"` and `"closed"` are for Jira-synchronized entries.
  `"tracked"` is for low-severity gaps that are recorded in the
  manifest but not synced to Jira. When a closed issue is reopened,
  reset to `"active"`. When a tracked gap's severity increases to
  medium/high/critical, promote to `"active"` and create a Jira story.
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

Then return to the invoking workflow router for completion guidance.
