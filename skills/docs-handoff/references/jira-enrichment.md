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
- Modify `sprint`, `parent`, `labels`, `components`, `fixVersions`
- Add `comments`
- Set `priority` or `issuetype`
- Create new issues
- Trigger documentation authoring or publication
- Execute workflow hooks or batch operations

A consumer profile cannot override these restrictions.

## Allowed Metadata Catalog

Only fields in this catalog may be proposed as metadata changes.
Uncatalogued fields are rejected as forbidden:

| Canonical Name | Jira Binding | Requirement |
|---|---|---|
| `target_release` | `fixVersions` or project-specific custom field | Value must exist in project's actual Fix Version catalog |

Proposed values that have not been verified against the project's live
field catalog carry `catalog_verified: false`.  The runtime must verify
the value exists before applying.  Unknown or guessed values remain
gaps — no raw `proposed_*` placeholder is sent as a Jira field write.

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
the issue's current Remote Links (canonically ordered).  When an
`approved_baseline` is provided and differs from the current baseline,
the result is `stale` — writes are blocked until a fresh preview is
approved.

The plan also carries a `plan_digest` covering the issue key, target,
inputs, links, and metadata.  A tampered plan produces a different
digest.

## Readback and Receipts

After applying approved writes, the `verify_enrichment` function:

1. Checks the readback issue key matches the expected key
2. Produces link receipts: `confirmed` (found) or `uncertain` (missing)
3. Produces metadata receipts: `confirmed`, `different_value`, or
   `uncertain`
4. Distinguishes existing (no-op) links from newly applied links
5. Reports `all_confirmed` only when at least one add operation exists
   and all are confirmed — empty eligible lists are not success

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
