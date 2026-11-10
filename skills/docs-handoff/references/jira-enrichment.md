# Jira Enrichment Protocol

Approved metadata and PR Remote Link write protocol for the docs-handoff
skill.  All writes require explicit user approval of the complete bounded
plan — not per-operation prompts.

## Approved Operations

| Operation | Scope | Confirmation |
|---|---|---|
| Add PR Remote Links | Per-PR URL on the target DOCS issue | One plan approval |
| Propose metadata fields | Target release, when value is from approved catalog | One plan approval |

## Forbidden Operations

The skill must NEVER perform these operations, regardless of profile or
caller input:

- Modify `summary` or `description`
- Change issue `status` or `resolution`
- Set or change `assignee`
- Modify `sprint`, `parent`, or `labels`
- Add `comments`
- Set `priority` or `issuetype`
- Create new issues
- Trigger documentation authoring or publication
- Execute workflow hooks or batch operations

A consumer profile cannot override these restrictions.  The
`check-enrichment` subcommand rejects any plan that includes forbidden
fields.

## PR Remote Links

Remote Links connect the DOCS issue to implementation PRs.  Each link
has:

- **URL**: normalized PR/MR URL (validated, no credentials)
- **Title**: PR title for display
- **Relationship**: `implements` (the PR implements a contributing story)

### Idempotency

Before proposing links, the skill checks existing Remote Links on the
issue.  Links whose normalized URL already exists are reported as
`existing` and skipped.  Only genuinely new links are `eligible`.

### Approval Flow

1. The preview shows ALL proposed links, existing links, and the complete
   enrichment plan as a single bounded operation.
2. The user approves or rejects the entire plan.
3. On approval, eligible links are added via the runtime's available Jira
   write capability.
4. After writes, the skill re-reads the issue's Remote Links and produces
   a per-link receipt with `confirmed` or `uncertain` status.

The approval is a genuine user decision — not a trusted `approved: true`
JSON toggle.  The skill waits for the runtime's interactive confirmation.

## Metadata Fields

Metadata proposals require actual project field catalog and valid values.
Unknown or uncatalogued values remain gaps — the skill never guesses
release versions, priority values, or component names.

The `proposed_target_release` field is included when the caller provides
a target release.  Applying it requires verifying the value exists in the
project's Fix Version or Target Version catalog.

## Baseline Drift Detection

The `check-enrichment` subcommand computes a baseline fingerprint from
the issue's current Remote Links.  If the baseline changes between plan
creation and apply (concurrent modification), the plan is stale and must
be regenerated.

## Readback and Receipts

After applying approved writes, the skill:

1. Re-reads the issue's Remote Links from Jira
2. Compares expected links against the readback
3. Produces a receipt for each operation:
   - `confirmed`: link found in readback
   - `uncertain`: link not found — may indicate write failure or
     propagation delay

On uncertain results, the skill reports the discrepancy.  It does NOT
automatically retry or claim rollback.

## Consumer Profile

An optional caller-supplied consumer profile may specify:

- `readiness_dimensions`: list of assessment dimensions the consumer
  cares about (e.g. `["technical_accuracy", "completeness"]`).  These
  are recorded but NOT automatically evaluated — the caller must populate
  actual assessments.  Absent dimensions are a visible gap, not universal
  readiness.

The profile cannot:
- Override forbidden field restrictions
- Bypass the approval flow
- Enable automatic writes
- Provide internal service endpoints or credentials
