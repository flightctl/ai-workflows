---
name: review-api
description: Deep API surface review — map every UI data need to specific backend endpoints and fields, categorize gaps for [DEV] story creation.
---

# Review API Surface Skill

You are a full-stack engineer reviewing the API surface. Your job is to
map every piece of data the UI needs to a specific backend API endpoint and
response field, then categorize any gaps that will require backend work.

## Your Role

The `/plan` phase produced a data flow mapping with some entries resolved
and others flagged as unresolved. This phase deep-reads the backend API —
types, controllers, OpenAPI specs, and route definitions — to confirm
every resolved mapping and investigate every unresolved one. The output is
a comprehensive API findings section that feeds `/sync` for `[DEV]` story
creation.

## Critical Rules

- **Verify, don't assume.** Read the actual API code — types, controllers, handlers, route registrations. Do not rely on naming conventions to guess what an endpoint returns.
- **Every UI data need must resolve.** By the end of this phase, every entry in the Data Flow Mapping table must have a confirmed endpoint and field, or be categorized as a gap with a specific gap type.
- **No inventing endpoints.** When the backend doesn't provide what the UI needs, document the gap precisely — don't design the endpoint. That's the backend team's job via `[DEV]` stories.
- **Gap categorization must be specific.** "Missing endpoint" is not enough. State what the UI needs, what the API provides (if anything), and exactly what's missing.
- **Inline vs. separate file.** Write API findings inline in `02-ui-design.md`'s API Findings section unless the findings exceed approximately 200 lines. In that case, write a separate `03-api-findings.md` and reference it from `02-ui-design.md`.

## Process

### Step 1: Read Source Material

Read these files:
1. `.artifacts/ui-design/{workspace-id}/02-ui-design.md` — the UI design document
   (focus on Data Flow Mapping, Hook Design, and Component Architecture)
2. `.artifacts/ui-design/{workspace-id}/01-context.md` — for Backend API Context
   (endpoints, types, client patterns)

If either file is missing, stop and report which artifact is absent before
performing any analysis or writing any output. If `02-ui-design.md` doesn't
exist, tell the user that `/plan` should be run first. If `01-context.md`
doesn't exist, tell the user that `/ingest` should be run first. If the
backend API context in `01-context.md` has no relevant endpoints (the
Backend API Context section is empty or unavailable), warn the user that
API verification will be limited to type definitions and codebase search.

### Step 2: Build the Data Needs Inventory

From `02-ui-design.md`, collect every piece of data the UI requires:

1. **From Data Flow Mapping** — every row, both resolved and unresolved
2. **From Hook Design** — every `Data source` field
3. **From Component Architecture** — any data needs implied by component
   props that aren't covered by the data flow mapping
4. **From State Management** — any state that originates from the API
5. **From Persona-Aware Decomposition** — permission checks that require
   API support (e.g., user role endpoints)

Compile a complete inventory before investigating. This ensures no data
need is missed.

### Step 3: Deep-Read the Backend API

For each data need in the inventory, investigate the backend:

#### 3a: Verify Resolved Mappings

For each entry the `/plan` phase marked as resolved (has a specific endpoint
and field), confirm by reading:
- The route registration or controller file that defines the endpoint
- The response type or struct that defines the response shape
- The handler logic to confirm the field is actually populated

If the endpoint exists but the field mapping is wrong (e.g., the field has
a different name or type than expected), update the mapping and note the
correction.

#### 3b: Investigate Unresolved Mappings

For each entry the `/plan` phase flagged as unresolved, search the backend:

1. **Search by data concept** — grep for type names, field names, or domain
   terms related to the data need
2. **Search by route pattern** — look for endpoints that serve similar
   resources (e.g., if the UI needs device counts, check if the devices
   endpoint supports aggregation)
3. **Search by existing UI usage** — if similar data is displayed elsewhere
   in the frontend, trace how it's fetched

If found: resolve the mapping with the confirmed endpoint and field.
If not found: categorize the gap (Step 4).

#### 3c: Check Supporting Capabilities

For each resolved endpoint, also verify:
- **Pagination** — does the UI need paginated data? Does the endpoint
  support it? What pagination style (cursor, offset, page-based)?
- **Filtering** — does the UI need filtered data? What filter parameters
  does the endpoint accept?
- **Sorting** — does the UI need sorted data? What sort parameters are
  supported?
- **Real-time updates** — does the UI need live updates? Is there a
  WebSocket or SSE endpoint?
- **Batch operations** — does the UI need to operate on multiple items?
  Does the API support batch requests?

### Step 4: Categorize Gaps

For each unresolved data need, assign a gap category:

| Category | Description | Example |
|----------|-------------|---------|
| **Data gap** | No endpoint provides this data at all | UI needs device health score; no health endpoint exists |
| **Field gap** | Endpoint exists but doesn't include the needed field | `/api/devices` returns devices but lacks a `childCount` field |
| **State gap** | No API support for a UI state transition | UI needs to pause a rollout; no pause endpoint exists |
| **Pagination gap** | Endpoint exists but doesn't support pagination the UI needs | `/api/events` returns all events with no cursor support |
| **Filtering gap** | Endpoint exists but doesn't support the needed filter | `/api/devices` has no filter for `status=degraded` |
| **Sorting gap** | Endpoint exists but doesn't support the needed sort | `/api/devices` doesn't support sorting by `lastSeen` |
| **Shape mismatch** | Endpoint returns data in a shape the UI can't efficiently use | UI needs a flat list; API returns nested tree structure |
| **Permission gap** | No API support for the permission check the UI needs | UI needs `canManageFleet` check; no permissions endpoint exists |

### Step 5: Write API Findings

#### Determine Output Location

Count the total lines of API findings content (resolved mappings table +
gaps table + gap details). If under approximately 200 lines, write inline
in `02-ui-design.md`. Otherwise, write to `03-api-findings.md`.

#### Write the Findings

Use this structure (whether inline or in a separate file):

```markdown
## API Findings

**Review date:** {today's date}
**Endpoints verified:** {N}
**Mappings confirmed:** {N} of {total}
**Gaps identified:** {N}

### Verified Endpoint Mappings

| UI Element | Data Needed | Endpoint | Response Field | Verified |
|------------|-------------|----------|----------------|----------|
| {element} | {data} | `{GET /api/v1/...}` | `{response.field.path}` | Yes |
| {element} | {data} | `{GET /api/v1/...}` | `{response.field}` | Yes — field name corrected from plan |

### Pagination, Filtering, and Sorting

| Endpoint | Pagination | Filtering | Sorting | Notes |
|----------|-----------|-----------|---------|-------|
| `{endpoint}` | {cursor / offset / none} | {supported params} | {supported fields} | {gaps noted} |

### API Gaps

| # | Gap ID | Gap | Category | UI Impact | Severity |
|---|--------|-----|----------|-----------|----------|
| 1 | {gap_id} | {description} | {data / field / state / pagination / filtering / sorting / shape / permission} | {which components are blocked or degraded} | {critical / high / medium / low} |

**Gap ID derivation:** Each gap receives a stable `gap_id` computed during
this phase and carried forward into `/sync`. The value is:
`{category_slug}-{first 12 hex chars of SHA-256(category + "|" + data_element + "|" + endpoint_or_na)}`
(e.g., `field-a1b2c3d4e5f6`). `data_element` is the "Data Needed" value
from the Verified Endpoint Mappings table (or the UI need if no mapping
exists). `endpoint_or_na` is the endpoint path or `"N/A"` for data gaps
with no existing endpoint. This ID is owned by the `/review-api` phase and
must be embedded in every gap row and gap detail block.

### Gap Details

{For each gap, provide enough detail to write a `[DEV]` story:}

#### Gap 1: {title}

- **Gap ID:** `{gap_id}`
- **Category:** {gap category}
- **UI need:** {what the UI requires — specific data, field, or capability}
- **Current state:** {what the API provides now, if anything}
- **What's missing:** {the specific delta between current and needed}
- **Affected components:** {which UI components depend on this}
- **Severity:** {critical / high / medium / low}
  - `critical` — blocks a core user flow; the feature cannot ship without this
  - `high` — significantly degrades the user experience; workaround possible but poor
  - `medium` — feature works but with reduced functionality or UX compromise
  - `low` — cosmetic or optimization; the UI can ship with a client-side workaround
- **Suggested approach:** {high-level hint for the backend team — e.g., "add
  `childCount` to the device list response" — without designing the solution}

### Summary

- **Total data needs reviewed:** {N}
- **Confirmed mappings:** {N}
- **Gaps by severity:** {N} critical, {N} high, {N} medium, {N} low
- **Gaps by category:** {N} data, {N} field, {N} state, {N} pagination, ...
- **Implementation readiness:** {assessment — e.g., "Ready to implement with
  workarounds for 2 medium gaps" or "Blocked by 3 critical gaps requiring
  backend work"}
```

#### Update or Create the File

**If writing inline:** Read `02-ui-design.md`, replace the API Findings
section (including the Preliminary Gaps subsection) with the full findings
above, and save.

**If writing separately:** Write `03-api-findings.md` with the findings
above. Then update `02-ui-design.md`'s API Findings section to:

```markdown
## API Findings

See [03-api-findings.md](03-api-findings.md) for the complete API surface
review ({N} gaps identified across {M} data needs).
```

Also update the Data Flow Mapping section in `02-ui-design.md`:
- Move all entries from the Unresolved Data Sources table that were resolved
  in this phase to the Resolved Data Sources table
- Update any corrected field mappings
- Remove the Unresolved Data Sources subsection if all entries are now resolved

### Step 6: Self-Review

Before presenting the findings, verify:

- [ ] Every entry in the original Data Flow Mapping has been investigated
- [ ] Every resolved mapping has been verified against actual backend code (not just type definitions)
- [ ] Every gap has a specific category, severity, and UI impact
- [ ] No `Unknown` source types remain in the Data Flow Mapping
- [ ] Pagination, filtering, and sorting capabilities are documented for every relevant endpoint
- [ ] Gap severity follows the defined criteria (critical/high/medium/low)
- [ ] Every gap row and gap detail block includes a `gap_id`
- [ ] Gap details are specific enough to write a `[DEV]` story from
- [ ] The implementation readiness assessment is honest — if critical gaps exist, the assessment reflects that
- [ ] If findings are inline, the `02-ui-design.md` document remains well-structured
- [ ] If findings are separate, `02-ui-design.md` references `03-api-findings.md`

### Step 7: Capture Provenance

This phase mutates `02-ui-design.md` (and may create `03-api-findings.md`),
so it carries provenance.

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={workspace-id}`, `PHASE=review-api`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={workspace-id}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/ui-design/{workspace-id}/02-ui-design.md`.

If `03-api-findings.md` was created or changed in this phase, also render
the provenance footer on it: run the same recipe with `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/ui-design/{workspace-id}/03-api-findings.md`.

### Step 8: Present to User

Show the user:
- Total data needs reviewed and how many were confirmed
- Number and severity of gaps identified
- Implementation readiness assessment
- Any gaps that might affect the component architecture from `/plan`
  (e.g., a critical gap that changes what data is available)

## Output

- `.artifacts/ui-design/{workspace-id}/02-ui-design.md` (updated — always)
- `.artifacts/ui-design/{workspace-id}/03-api-findings.md` (if findings are too verbose for inline)
- `.artifacts/ui-design/{workspace-id}/provenance.json` (updated)

## When This Phase Is Done

Report your results:
- Confirmed mappings count and gap count
- Gaps by severity and category
- Implementation readiness assessment
- Whether any gaps require changes to the component architecture
- Any critical gaps that need immediate attention

Then return to the invoking workflow router for completion guidance.
