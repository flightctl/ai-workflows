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
- **Jira-side duplicate check.** Before creating each story, query Jira for existing children under the parent with a matching gap_id marker. If a match is found, stop and present the match to the user — do not create a duplicate.
- **Sync-owned fields.** Sync owns: summary, description, and parent link (creation only). Sync never touches: assignee, sprint, comments, labels, or any other Jira-managed field.
- **Parent immutability.** The parent link is set only at story creation and is not updated on subsequent syncs. If the resolved `{parent-key}` differs from the `parent_key` stored in the manifest, warn the user about the mismatch but do not attempt to change the parent link on existing stories — Jira parent links may be creation-only depending on the project configuration.
- **Status transitions are limited.** Sync may only perform two status transitions: (1) transition resolved issues to Done/Closed, and (2) reopen previously closed issues when a gap reappears. Sync must not edit status for any other reason.
- **Logical deletion via status.** Gaps are closed (not deleted) when they are resolved — the gap entry is removed from the API findings or marked as resolved. The manifest tracks the closure.
- **Link to source.** Every Jira story description references the UI design document.

## Prerequisites

**Jira-backed workspace required.** Before any other check, read
`.artifacts/ui-design/{workspace-id}/01-context.md` and check the
`Origin` field in the Story Summary section.

- If `01-context.md` is missing, unreadable, or cannot be parsed,
  stop immediately and report:

  *"Workspace metadata is invalid or unavailable —
  `01-context.md` could not be read. Re-run `/ingest` to
  re-initialize the workspace before using `/sync`."*

- If `Origin: Non-Jira`, `/sync` cannot proceed — there is no Jira
  project to sync stories to. Stop immediately and report:

  *"The `/sync` phase requires a Jira-backed workspace (a Jira issue
  key as workspace-id). This workspace (`{workspace-id}`) was created
  from non-Jira input (Origin: Non-Jira). To sync API gap stories to
  Jira, re-run `/ingest` with a Jira issue key."*

- If `Origin: Jira`, proceed.

- If the `Origin` field is missing (older `01-context.md` without the
  field), fall back to validating `{workspace-id}` against the Jira
  key regex `^[A-Z][A-Z0-9]+-[0-9]+$`. If it matches, proceed. If it
  does not match, treat the workspace as non-Jira and stop with the
  same error message above.

- If the `Origin` field is present but contains an unrecognized value
  (neither `Jira` nor `Non-Jira`), stop immediately and report:

  *"Workspace metadata is invalid — the `Origin` field in
  `01-context.md` has an unrecognized value (`{value}`). Re-run
  `/ingest` to re-initialize the workspace before using `/sync`."*

Do not proceed to Step 1 unless the workspace is confirmed Jira-backed.

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
1. `.artifacts/ui-design/{workspace-id}/02-ui-design.md` — for the API Findings
   section (or the reference to `03-api-findings.md`)
2. `.artifacts/ui-design/{workspace-id}/03-api-findings.md` — if the API findings
   are in a separate file
3. `.artifacts/ui-design/{workspace-id}/01-context.md` — for the parent story
   and feature context

If no API findings exist (no API Findings section in `02-ui-design.md` and
no `03-api-findings.md`), stop and tell the user that `/review-api` should
be run first. If the API Findings section exists but contains only the
pending-findings marker (no gaps table), stop and report that the findings
are incomplete. If any required file is unreadable, stop and report the
error before performing any Jira operations.

Extract every gap from the API Gaps table and its corresponding Gap
Details block (produced by the `/review-api` phase). The summary table
row provides `gap_id`, `title`, `category`, `severity`, and
`affected_components` (as "UI Impact"). The Gap Details block provides
the remaining fields. Read both sources for each gap:

| Field | Source | Required | Used in |
|-------|--------|----------|---------|
| `gap_id` | API Gaps row | Yes | Matching key for manifest entries |
| `title` (gap title) | API Gaps row / Gap Details heading | Yes | Jira summary, content_hash |
| `category` | API Gaps row + Gap Details | Yes | Jira description, content_hash |
| `severity` | API Gaps row + Gap Details | Yes | Sync eligibility (critical/high/medium), content_hash |
| `ui_need` | Gap Details block | Yes | Jira description, content_hash |
| `whats_missing` | Gap Details block | Yes | Jira description, content_hash |
| `current_state` | Gap Details block | Yes | Jira description, content_hash |
| `suggested_approach` | Gap Details block | Yes | Jira description, content_hash |
| `affected_components` | API Gaps row ("UI Impact") + Gap Details | Yes | Jira description, content_hash |

**Canonical field formats.**

- `affected_components` — comma-separated PascalCase names matching
  Component Architecture headings in `02-ui-design.md` (e.g.,
  `DeviceList, DeviceDetailPanel, FleetOverview`). Each name must
  correspond to a heading under the Component Architecture section.
- `ui_need` — category-prefixed format: `{category}: {description}`
  where `{category}` is one of `loading-state`, `data-display`,
  `error-handling`, `pagination`, `filtering`, `sorting`, `form-input`,
  `permission-gate`, `real-time`, `batch-operation` (e.g.,
  `loading-state: skeleton placeholder while device list loads`,
  `data-display: show device health score in summary card`). If no
  category fits, use `other: {description}`.

**Cross-source mismatch handling.** Fields sourced from both the API
Gaps row and the Gap Details block (`category`, `severity`,
`affected_components`) may diverge if the findings were hand-edited.
Before using any of these fields for classification, hashing, or
description rendering, compare the two values. If they differ for any
gap, **stop and report the conflict to the user** — do not choose
either value silently:

*"Conflict detected for gap `{gap_id}`: `{field}` is `{row_value}` in
the API Gaps table but `{details_value}` in the Gap Details block.
Please reconcile the values in the API findings before re-running
/sync."*

Do not proceed with Jira operations until all cross-source conflicts
are resolved.

**Missing field handling.** If any gap is missing `gap_id`, stop and
ask the user to re-run `/review-api` — the findings pre-date the
gap_id requirement. If any other required field is missing or empty
after reading both the table row and the Gap Details block, use the
canonical fallback value `"Not specified"` for that field. This
fallback must be used consistently in **both** the `content_hash`
computation and the Jira description rendering — do not use an empty
string in one and the fallback in the other. Warn the user which
gaps have fallback values so they can fix the findings if desired.

Use the producer-provided `gap_id` as the sole matching key when
comparing findings with the manifest; do not re-derive or recompute
it during sync, and do not match by `gap_number` or title alone.
Continue using `content_hash` only to detect changes for matched
active entries.

**Zero-gap guard:** If the API findings section is non-empty (contains
a gaps table or narrative content) but parsing produces zero extracted
gaps, do not silently proceed. Stop and warn the user:

*"The API Findings section contains content but no gaps could be
extracted. This may indicate a formatting issue in the findings table.
Please verify the API Findings section and re-run /sync."*

Wait for the user to confirm before proceeding — either they fix the
findings or explicitly confirm that zero gaps is correct.

**Load `pr_url` (optional — used in Jira descriptions).** Before
proceeding, attempt to load `pr_url` from
`.artifacts/ui-design/{workspace-id}/publish-metadata.json`. Apply
HTTPS URL validation (non-empty string, parseable HTTPS URL with a
valid host and at least one path segment).

- If the file exists and `pr_url` is valid, use it in Jira description
  templates and closure comments.
- If the file does not exist, `pr_url` is absent, null, empty, or
  invalid, set `pr_url` to `"Pending — design PR not yet published"`
  and warn the user:

  *"`publish-metadata.json` not found or `pr_url` is missing/invalid.
  Jira descriptions will use a placeholder link. Run `/publish` and
  then `/sync` again to update the link in Jira descriptions."*

  Proceed with sync — the content hash does not include `pr_url`, so
  gap tracking and change detection work without it. The placeholder
  will be replaced on the next sync after `/publish` is run (which
  will change the description template, triggering a content update
  via the description diff even though the hash is unchanged).

**Canonical content_hash computation.** To ensure `content_hash`
changes whenever a Jira-rendered field changes, define the hash
payload as the sorted JSON serialization of exactly these fields:

**Title normalization.** Before computing the hash, define
`title = trim(gap_title)` — strip leading and trailing whitespace
from the raw gap title. Use this normalized `title` for both the
content_hash payload below and the Jira summary (`[DEV] {title}`).
This ensures that a whitespace-only title change does not produce a
different hash while rendering an identical Jira summary.

```json
{
  "affected_components": "{affected components}",
  "category": "{gap category}",
  "current_state": "{current state}",
  "prd_requirements": "{PRD requirement IDs or fallback text}",
  "severity": "{severity}",
  "suggested_approach": "{suggested approach}",
  "title": "{title}",
  "ui_design_section": "{resolved section reference}",
  "ui_need": "{UI need}",
  "whats_missing": "{what's missing}"
}
```

**Note:** `pr_url` is intentionally excluded from the content hash. It is
used in the Jira description template but changes whenever a new PR is
opened (e.g., after `/publish`), which would cause every hash to become
stale and trigger unnecessary Jira updates. The hash tracks only gap
content fields that represent actual changes to the gap's substance.

Compute the content hash using the helper script for deterministic
results:

```bash
python3 "../../ui-design/scripts/compute-hash.py" content-hash \
  --json-file "{path-to-payload.json}"
```

Or pipe the JSON payload via stdin:

```bash
echo '{ ... }' | python3 "../../ui-design/scripts/compute-hash.py" content-hash --json-stdin
```

The script computes `SHA-256(JSON.stringify(payload))` where keys
are sorted alphabetically and values are trimmed of leading/trailing
whitespace. The `title` field uses the
pre-normalized `title = trim(gap_title)` (see above) so the hash
input matches the Jira summary (`[DEV] {title}`) — a title-only
change must trigger an update, but a whitespace-only difference that
renders identically in Jira must not. This set of fields matches
exactly what gets rendered into the Jira issue — any change to a
rendered field triggers an update.

Each gap that has severity
`critical`, `high`, or `medium` is a candidate for a `[DEV]` story.
Low-severity gaps are tracked in the manifest but not synced to Jira
unless the user explicitly requests it.

Check for an existing sync manifest at
`.artifacts/ui-design/{workspace-id}/sync-manifest.json`.

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

   **Changed (Tracked)** — gap exists in the findings, matching entry in
   the manifest with `synced_status: "tracked"`, severity still `low`,
   and the content hash differs from the stored `content_hash`.
   Action: update `content_hash` in the manifest — no Jira changes.

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

**Parent immutability check (mandatory — runs before any early exit).**
When the manifest has a `parent_key` value, resolve the current parent
from `01-context.md` (already read above) using the same logic as
Step 2: use the parent epic if present, otherwise the parent feature.
Compare the resolved parent against `manifest.parent_key`. If they
differ, stop immediately and report:

*"Parent mismatch: the manifest records parent `{manifest.parent_key}`
but the current context resolves to `{resolved parent}`. Existing Jira
stories are linked to the manifest parent and cannot be automatically
re-linked. Options: (1) update `01-context.md` to restore the original
parent, (2) manually re-parent the existing Jira stories to the new
parent and then delete the manifest to start a fresh sync, or
(3) manually re-parent the existing stories in Jira and update the
manifest's `parent_key` to match."*

Do not allow deleting the manifest as a standalone reset — the existing
stories would remain under the old parent with no gap-to-Jira mapping,
and the duplicate check (which searches only under the selected parent)
would not find them, risking duplicate story creation.

Do not proceed to the dry run, the "nothing to do" exit, or any Jira
operations until the parent is reconciled.

**Promotion check (tracked → active, runs before early exit).** Before
evaluating the "nothing to do" condition, scan manifest entries with
`synced_status: "tracked"`. For each tracked entry, compare its current
severity in the findings:
- If the severity has increased to `medium`, `high`, or `critical`,
  reclassify the entry — set its bucket to **New** so it will receive a
  Jira story in pass 4a. A tracked gap that now qualifies for Jira must
  not be suppressed by the early exit.
- If the severity is still `low`, leave it tracked. If the content hash
  differs from the stored `content_hash`, update it in the manifest to
  keep the tracked entry current.
- If the gap is no longer in the findings, route it to the **Resolved**
  bucket to mark it closed in the manifest.

**If nothing to do** (no new, changed, resolved, or promoted items, and
no entries with `blocks_link: "failed"` or `adopted: "failed"`):

Before exiting, check for entries that need recovery (pass 4d work):
scan manifest entries with `synced_status: "active"` for any with
`blocks_link: "failed"` or `adopted: "failed"`. If found, skip the
early exit and proceed to Step 2 so that pass 4d can retry them.

If no recovery work is needed, stop and tell the user:

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

Read the `[UI]` story's parent from `01-context.md` (the parent
immutability check in Step 1 already verified this matches
`manifest.parent_key` when a manifest exists):
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
## Jira Sync Preview — {workspace-id}

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

Use the `pr_url` loaded and validated in Step 1. (If `pr_url` was
invalid, Step 1 already stopped.)

Process stories in four passes: promote tracked (reclassified in
Step 1), create new, update changed, close resolved.

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

**Exclude resolved manifest entries from duplicate matching.** When
evaluating query results, cross-reference each match against the sync
manifest. If a matching Jira issue corresponds to a manifest entry with
`synced_status: "resolved"`, exclude it from duplicate detection — a
resolved entry represents a previously completed gap, and a reappearance
of the same `gap_id` is intentionally treated as a new occurrence (per
the Resolved entry lifecycle rule). Only flag matches that correspond to
`"active"` or `"tracked"` manifest entries (or have no manifest entry
at all) as potential duplicates.

If the query returns exactly one matching issue (after excluding resolved
entries), present it to the user:

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

**Adoption path.** If the user chooses to link an existing story (option
`a` in the duplicate check above), adopt it: record the existing story's
`jira_key` and current content in the manifest entry with
`synced_status: "active"` and `adopted: "adopted"`. Then attempt to
create the `blocks` link (same as new-creation link logic below). If
adoption succeeds, skip creation for this gap. If the adoption fails
(e.g., the selected story cannot be read or linked), set
`adopted: "failed"` in the manifest and continue — the adoption will be
retried in pass 4d.

For each new story (not adopted), create a Jira issue:

- **Type:** Story
- **Project:** {project key}
- **Parent:** {parent key} — **set via the `fields` parameter: `{"parent": {"key": "{parent-key}"}}`**
- **Summary:** `[DEV] {title}` (using the normalized `title = trim(gap_title)` from hash computation)
- **Description:**

Use the `pr_url` loaded at the start of Step 4. The URL must be a
non-empty, valid HTTPS URL with a host and at least one path segment
(e.g., `https://github.com/org/repo/pull/123`). Values like
`https://`, `https://placeholder`, or URLs without a path after the
host are invalid — if validation failed, Step 4 already stopped.

```markdown
<!-- gap_id: {gap_id} -->

## Summary

{Gap description — what the UI needs and what the backend currently provides.}

## Context

- **UI Story:** {workspace-id}
- **UI Design:** {pr_url from publish-metadata.json}
- **Gap ID:** {gap_id}
- **Gap Category:** {data / field / state / pagination / filtering / sorting / shape / permission}
- **Gap Severity:** {critical / high / medium}

## Design Reference

Source: ui-design/sync
Epic: {parent-key}
UI Design section: {component section reference in ui-design-{workspace-id}.md}
PRD Requirements: {FR/NFR IDs from parent story's Design Reference, or "Discovered during UI design — no PRD requirement"}
Interface Changes: {API change specification from gap's "What's missing" + "Suggested approach"}

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

**Canonical description rendering.** To ensure consistent Jira
descriptions across sync runs (preventing spurious diffs from
formatting variation), follow these normalization rules when rendering
the description template above:

1. **Field order:** Always render sections in the order shown in the
   template: Summary → Context → Design Reference → What's Needed →
   UI Impact → Suggested Approach → Acceptance Criteria.
2. **Context list items:** Render in the fixed order shown (UI Story,
   UI Design, Gap ID, Gap Category, Gap Severity). Use exactly one
   space after the colon separator.
3. **Design Reference fields:** Render in the fixed order: Source,
   Epic, UI Design section, PRD Requirements, Interface Changes.
4. **Whitespace:** No trailing whitespace on any line. Exactly one
   blank line between sections. No trailing blank lines at end of
   description.
5. **Component lists:** `affected_components` values are rendered as
   comma-separated PascalCase names in a fixed alphabetical order
   (e.g., `DeviceDetailPanel, DeviceList, FleetOverview`).
6. **Trim all field values** before rendering to prevent
   leading/trailing whitespace from varying between runs.

**Design Reference field derivation.** The `prd_requirements` and
`ui_design_section` fields are included in the `content_hash`
computation (see "Canonical content_hash computation" above), so changes
to these values trigger a Jira update. The remaining Design Reference
fields (`source`, `epic`, `interface_changes`) are static metadata and
are not hashed. Populate each field as follows:

1. **Source** — Always the literal string `ui-design/sync`.
2. **Epic** — The `{parent-key}` already resolved in Step 2 (the epic
   or feature under which the `[DEV]` story is created).
3. **UI Design section** — Derived from the gap's component mapping.
   Prepend the published filename to form a full cross-reference:
   - If the gap's affected component appears in the Component
     Architecture section of `02-ui-design.md`, use
     `ui-design-{workspace-id}.md#§Component Architecture > {ComponentName}`.
   - If the gap maps to an entry in the Data Flow Mapping section, use
     `ui-design-{workspace-id}.md#§Data Flow Mapping > {entry-name}`.
   - If neither applies, use `ui-design-{workspace-id}.md#§API Findings`.
4. **PRD Requirements** — Copy the FR/NFR IDs from the parent `[UI]`
   story's Design Reference section. If the parent story has no Design
   Reference section (or no PRD requirement IDs), use:
   `Discovered during UI design — no PRD requirement`.
5. **Interface Changes** — Combine the gap's "What's missing" and
   "Suggested approach" fields into a brief API change specification
   (e.g., `Add status field to GET /api/v1/devices response`).

After creating each story, verify the parent link by reading the issue
back. If the parent is missing, stop and report the error.

**Issue link to [UI] story.** After verifying the parent link, create a
Jira issue link between the newly created `[DEV]` story and the `[UI]`
story (`{workspace-id}`). The semantic relationship is:

> The **[UI] story** depends on the **[DEV] story**.
> Equivalently: the **[DEV] story** blocks the **[UI] story**.

The [DEV] backend work must be completed before the [UI] story's
frontend implementation can proceed.

**Link type selection:** Try the "Blocks" link type first (`"blocks"` /
`"is blocked by"`). If the Jira instance does not have this type, fall
back to "Dependency" (`"depends on"` / `"is depended on by"`).

After link creation, Jira should show:
- On the [DEV] story: **"blocks"** {workspace-id}
- On the [UI] story: **"is blocked by"** {DEV story key}

**Getting the direction right:** Jira link-creation APIs use directional
fields (e.g., `inwardIssue` / `outwardIssue`) whose meaning varies by
link type. Read the chosen type's inward and outward descriptions and
assign the [DEV] and [UI] story keys to produce the expected display.
After creating the first link in a sync run, read the [DEV] story's
issue links back from Jira and verify the direction. If wrong, delete
the link, swap the field assignments, recreate, and re-verify.

After link creation, record the result in the manifest entry:
- On success: set `blocks_link: "created"`.
- On failure: set `blocks_link: "failed"` and log the error. Continue
  to the next story — the link will be retried on the next sync run.

A story with `blocks_link: "failed"` is not considered fully in sync.

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

Use the `pr_url` loaded at the start of Step 4.

For each story categorized as **Changed**, update the Jira issue using
the Jira key from the manifest:

- **Summary:** re-derive `[DEV] {title}` using `title = trim(gap_title)` from the current gap
- **Description:** re-render the full description from the current gap
  content (same template as creation above, including the `pr_url`)

Update only the sync-owned fields. Do not touch status, assignee, or
other Jira-managed fields — except for reopened entries (those whose
prior `synced_status` was `"closed"`): also transition the Jira issue
back to an open status before updating content.

After updating, record the new `content_hash` in the manifest.

**If update fails:** Report the error with the Jira key and offer to
retry or skip.

#### 4c: Close Resolved Stories

For each entry categorized as **Resolved**:

**If the entry has a `jira_key`** (active Jira story):

1. Before adding the closure comment, check the issue's existing comments
   for the marker `<!-- ui-design-sync-close: {gap_id} -->`. If found,
   skip the comment and proceed directly to the status transition.

   Add a comment to the Jira story explaining the closure:
   *"Closing — the API gap '{gap title}' is no longer present in the UI
   design findings (resolved during /revise or /respond). See the UI
   design PR for details: {pr_url}."*
   Append the idempotency marker to the comment body:
   `<!-- ui-design-sync-close: {gap_id} -->`
2. Transition the story to Done/Closed in Jira.
3. Update the manifest entry: set `synced_status: "closed"` and record
   `closed_at` with the current ISO timestamp. Preserve the prior
   `content_hash` — do not replace it. This allows deterministic reopen
   detection: if a gap with the same `gap_id` reappears in a future sync,
   the preserved hash enables detecting whether the content changed since
   the issue was closed.

**If the entry has no `jira_key`** (tracked entry, never synced to Jira):

Remove the entry from the manifest — no Jira operations are needed.

**Selecting the close transition:** Use the Jira API to query available
transitions for the issue and select the terminal/done-category
transition. Prefer "Done" over "Closed." If no terminal transition is
available, report the error and let the user handle it in Jira.

**If close fails:** Report the error and offer to retry or skip.

#### 4d: Retry Failed Links and Reconcile Adoption/Recovery

**Retry failed links.** Scan manifest entries with
`synced_status: "active"` and `blocks_link: "failed"`. For each,
re-attempt the issue link creation between the `[DEV]` story
(`jira_key`) and the `[UI]` story (`{workspace-id}`) using the same
link type logic as Step 4a. On success, update `blocks_link` to
`"created"`. On failure, leave `blocks_link` as `"failed"` and log the
error.

**Retry failed adoptions.** Scan manifest entries with
`synced_status: "active"` and `adopted: "failed"`. For each, re-attempt
the adoption: query Jira for an existing story under the parent with a
matching `gap_id` marker. If found, present the match to the user (same
as the duplicate-check flow in 4a). If the user confirms adoption,
update the manifest entry with the adopted story's `jira_key` and set
`adopted: "adopted"`. On failure, leave `adopted: "failed"`.

**Recovery for stories with missing links.** Scan manifest entries with
`synced_status: "active"` that have a `jira_key` but no `blocks_link`
field (or `blocks_link: "failed"`). Before attempting link creation,
verify the story still exists in Jira by reading it. If the story does
not exist (deleted externally), remove the `jira_key` from the manifest
and reclassify the entry as **New** for the next sync run. If the story
exists, proceed with the link retry.

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
  "ui_story_key": "{workspace-id}",
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
      "synced_status": "active",
      "blocks_link": "created",
      "adopted": false
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
  of `{affected_components, category, current_state,
  prd_requirements, severity, suggested_approach, title,
  ui_design_section, ui_need, whats_missing}` (see "Canonical
  content_hash computation" above). `pr_url` is intentionally excluded
  — it changes on every `/publish` cycle and would cause spurious
  updates. The `title` value is normalized via `trim(gap_title)` before
  hashing so whitespace-only title changes do not produce spurious hash
  differences. Used to detect changes on the next run. Preserved (not
  replaced) when closing an issue, to support deterministic reopen
  detection.
- `synced_status` — One of `"active"`, `"closed"`, `"tracked"`, or
  `"resolved"`. State transitions:
  - `"active"` — Jira story exists and is open. Set on creation and
    when reopening a previously closed entry.
  - `"closed"` — Jira story was closed **by sync** (gap removed from
    findings or marked as resolved during `/revise`/`/respond`).
    If the same `gap_id` reappears in findings, transition back to
    `"active"` and reopen the Jira story (see Edge case — reopened).
  - `"tracked"` — Low-severity gap recorded in the manifest but not
    synced to Jira. When severity increases to medium/high/critical,
    promote to `"active"` and create a Jira story.
  - `"resolved"` — Jira story was closed **externally** (outside of
    sync — e.g., by the backend team completing the work). Set during
    manifest reading in Step 1 when an active entry's Jira story has
    `status=Closed` or `resolution=Done`. If the same `gap_id`
    reappears in findings, create a **new** Jira story (do not reopen
    the resolved one). See the lifecycle rule below.
- **Resolved entry lifecycle.** When reading the manifest during
  Step 1, check each active entry's Jira story status. If the Jira
  story has `status=Closed` or `resolution=Done`, set
  `synced_status: "resolved"` in the manifest. Resolved entries are
  excluded from future sync diffs — they do not appear in the new,
  changed, or unchanged buckets. If a resolved entry's `gap_id`
  reappears in a later version of the API findings (e.g., after a
  subsequent `/review-api` run), reclassify it as **New** — create a
  fresh Jira story rather than reopening the resolved one, since the
  Jira story was closed externally (not by sync).
- `blocks_link` — Link creation status: `"created"` if the `blocks`
  link between the [DEV] story and the [UI] story was successfully
  created, `"failed"` if creation failed. Omitted for `"tracked"` and
  `"closed"` entries. Stories with `blocks_link: "failed"` are not
  considered in sync — the link will be retried on the next sync run.
- `adopted` — Adoption status: `false` (default) for stories created
  by sync, `"adopted"` for stories that were pre-existing in Jira and
  adopted by sync (linked in the manifest without creating a new
  story), `"failed"` if adoption was attempted but failed. When
  `adopted: "failed"`, pass 4d retries the adoption on the next sync
  run. Omitted for `"tracked"` entries.
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
- `.artifacts/ui-design/{workspace-id}/sync-manifest.json` (v2 schema)

## When This Phase Is Done

Report your results:
- All Jira issue keys affected (created, updated, closed)
- Summary of the gap → story mapping
- Any next steps (e.g., assign stories to backend team, prioritize critical gaps)

Then return to the invoking workflow router for completion guidance.
