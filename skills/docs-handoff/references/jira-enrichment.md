# Jira Enrichment Protocol

Approved metadata and PR Remote Link write protocol for the docs-handoff
skill.  All writes require explicit user approval of the complete bounded
plan — ONE confirmation for the full finite preview.

## Approved Operations

| Operation | Scope | Confirmation |
|---|---|---|
| Add PR Remote Links | Contributor PRs on the target DOCS issue | One plan approval |
| Apply metadata fields | From allowed catalog with verified values | One plan approval |

## Forbidden Operations

The skill must NEVER perform these operations, regardless of profile:

- Modify `summary`, `description`, `reporter`
- Change `status`, `resolution`
- Set or change `assignee`
- Modify `sprint`, `parent`, `labels`, `components`
- Directly set `fixVersions` (use `target_release` catalog alias)
- Add `comment` or `comments` (both synonyms are forbidden)
- Set `priority` or `issuetype`
- Create new issues
- Trigger documentation authoring or publication
- Execute workflow hooks or batch operations

Forbidden field checks are case-insensitive — `fixVersions`,
`FIXVERSIONS`, and `fixversions` are all blocked.  The ONLY
authorized path to the Jira `fixVersions` field is through the
`target_release` catalog alias.

A consumer profile cannot override these restrictions.  Profile
fields that are forbidden produce `forbidden_field` findings; fields
that are valid strings but not in the allowed catalog produce
`uncatalogued_field` findings.

## Allowed Metadata Catalog

Only fields in this catalog may be proposed as metadata changes.
Uncatalogued fields are rejected with `uncatalogued_field` findings:

| Canonical Name | Jira Binding | Requirement |
|---|---|---|
| `target_release` | `fixVersions` (via `target_release` alias in `_METADATA_CATALOG_V1`) | Catalog entry with version `id` and `name` from observed project catalog |

Proposed values require a `catalog_entry` with non-empty `id` and
`name` matching the requested release value, gathered from the
project's actual Fix Version catalog via approved runtime capabilities.
The metadata payload is additive — existing versions from the actual
current `fixVersions` field state are preserved; the new version is
appended.  A version already present is a no-op.  The current field
value must be retrievable and well-formed: if `fixVersions` is
missing, null, not a list, or contains entries without a valid `id`,
the metadata write is blocked (fail-closed) to prevent data loss.  An
explicit empty list (`[]`) is legitimate and allows the write.
Unknown, uncatalogued, or malformed catalog entries remain gaps with
no metadata write.  No raw `proposed_*` placeholder or arbitrary
`catalog_entry` value is sent as a Jira field write.

## PR Remote Links

Remote Links connect the DOCS issue to implementation PRs.  Only PRs
attributed to *actual contributors* are eligible — PRs from
non-contributors produce `non_contributor_evidence` findings and source
proposals, not automatic link enrichment.

### Idempotency

Before proposing links, the skill checks existing Remote Links.  Links
whose normalized URL already exists are `existing` and skipped.  Only
genuinely new links are `eligible`.  Link ordering is canonicalized
(sorted by URL) to avoid false baseline drift from reordering.

### Approval Flow

1. Preview shows ALL proposed operations (links + metadata) as a single
   bounded plan.
2. The user approves or rejects the entire plan.  Approval is a genuine
   user decision — not a trusted `approved: true` JSON toggle.
3. **Before writes**: re-read the issue's current Remote Links and
   metadata from Jira.  Compare the baseline fingerprint against the
   approved snapshot.  If the baseline changed (concurrent modification),
   the plan is stale and must be regenerated with a fresh preview.
4. **Apply**: add eligible links and metadata via approved capabilities.
5. **Readback**: re-read the issue after writes and produce per-operation
   receipts.

## Baseline Drift Detection

The `check-enrichment` subcommand computes a baseline fingerprint from
the issue's current Remote Links (canonically ordered) and metadata
fields from the catalog (e.g. `fixVersions`).  When an
`approved_baseline` is provided and differs from the current baseline,
the result is `stale` — writes are blocked until a fresh preview is
approved.

The plan carries a `plan_digest` covering the issue key, target,
inputs, links, metadata, and `snapshot_fingerprint` (a hash of the
original issue key, summary, raw description, contributors, and
dependencies at plan time).  The builder requires the validated source
context (summary and raw description) — a `valid: true` flag alone
is insufficient.  A tampered or stale plan produces a different
digest.  An empty `plan_digest` is invalid.  An
`approved_plan_digest` parameter detects plan changes since
approval — e.g. when the writer edits the summary, description, or
contributors between preview and apply.  The fresh-check comparison
uses the same projection (key, summary, raw description, contributors,
dependencies) so any edit, including outside parsed sections or in
the summary, is detected with zero writes.

## Readback and Receipts

After applying approved writes, the `verify_enrichment` function:

1. Checks the readback issue key matches the expected key
2. Produces link receipts: `confirmed` (found), `uncertain` (missing),
   or `disappeared` (existing link no longer present)
3. Produces metadata receipts: `confirmed`, `partial` (some expected
   IDs missing), `different_value`, or `uncertain`
4. Distinguishes existing (no-op) links from newly applied links
5. Reports `all_confirmed` only when at least one add operation exists
   and all add operations are confirmed — empty eligible lists are
   not success; existing link receipts (including `disappeared`) do
   not affect the `all_confirmed` boolean

A `disappeared` existing link is reported as a user-visible finding
without changing `all_confirmed` semantics — it indicates an
unexpected external change, not a failed write operation.

On uncertain results, the skill reports the discrepancy.  It does NOT
automatically retry or claim rollback.

## Consumer Profile

An optional caller-supplied consumer profile may specify:

- `readiness_dimensions`: list of assessment dimension names
- `readiness_results`: dict of dimension → `{"assessed": bool, ...}`
- `allowed_fields`: list of `{"name": ..., "value": ...}` for metadata

Missing dimensions or unassessed results stay visibly incomplete — never
silently universal readiness.  Forbidden fields in `allowed_fields` are
rejected with findings.
