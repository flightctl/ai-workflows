# Evidence Schema and Validation

Contract for DOCS issue validation, contributor extraction, and
delivery-evidence normalization used by `../scripts/evidence.py`.

## DOCS Issue Snapshot

The skill operates on a single `[DOCS]` Jira issue at a time.  The
caller provides a JSON snapshot with at minimum:

| Field | Type | Required | Source |
|---|---|---|---|
| `key` | string | Yes | Jira issue key (e.g. `TEST-100`) |
| `summary` | string | Yes | Must contain `[DOCS]` prefix |
| `description` | string | Yes | Rendered Markdown from Jira |
| `status` | string | No | Current issue status |
| `parent` | object | No | Parent issue key and type |
| `remote_links` | array | No | Existing Remote Links |
| `issue_links` | array | No | Existing issue links |

The `validate` subcommand validates the snapshot and extracts structured
data.  An offline snapshot file is fully supported — the skill does not
require live Jira access for validation.

## Required Description Sections

A valid `[DOCS]` issue description must contain these `##` sections:

- **Documentation Inputs** — planned user-facing artifacts grouped by
  contributing story
- **Documentation Scope** — what the reader needs to understand
- **Acceptance Criteria** — reader-verifiable documentation outcomes

Missing sections produce validation errors.  An empty Documentation
Inputs section (present but no parseable structured items) produces a
warning.

## Contributor Extraction

Contributors are extracted from the `Contributing stories:` line in the
Design Reference section.  In a rendered (synced) issue, these are Jira
keys (e.g. `TEST-201`).  Unresolved `Story N.NN` placeholders are
extracted as qualified IDs and flagged as warnings — they are gaps, not
fabricated live identities.

**Contributors vs Dependencies**: the `Dependencies` section lists
prerequisite stories.  Dependencies are NOT automatically direct
contributors.  The script extracts these separately.  A contributor
that is *also* listed in Dependencies still requires evidence — the
dependency relationship does not exempt it from the contributor finding.

## Documentation Inputs Parsing

The Documentation Inputs section is parsed into structured items:

```text
**JIRA-KEY — title:**
- Input item text
- Another item [Assumption]
- Open item [Open: §9.2]
```

Each item records:
- `contributor`: the Jira key or qualified story ID from the header
- `text`: the original input description (markers preserved in text)
- `marker`: `planned` (default), `assumption`, or `open`
- `open_ref`: the referenced open question (when marker is `open`)

Missing or unparsed headers produce a visible warning, not a silent gap.

## PR Evidence Items

Each gathered PR evidence item must have:

| Field | Type | Required |
|---|---|---|
| `pr_url` | string | Yes — supported PR/MR URL (see URL validation) |
| `contributor_key` | string | Yes — Jira key of contributing story |
| `target_branch` | string | No — PR target branch |
| `state` | string | No — PR state (open, merged, closed) |
| `title` | string | No — PR title |
| `merged` | boolean/null | No — whether PR is merged |
| `merge_commit` | string | No — merge commit SHA |
| `observations` | string[] | No — AI-generated semantic observations |

The `normalize` subcommand validates URLs (requiring supported PR/MR
structure with numeric ID), rejects embedded credentials, deduplicates
by normalized URL, detects contradictory `merged` or `target_branch`
values on duplicate PRs (surfaced as conflicts rather than silently
taking the first value), and preserves distinct repository identities.

Non-PR URLs, non-boolean `merged` values, and non-string observations
are rejected with errors.

## Input Status Values

After comparing planned inputs against gathered evidence, each input
receives a per-PR evidence status — not a blanket delivery claim:

- `merged_pr_exists` — contributor has a merged PR targeting the
  expected branch
- `merged_wrong_target` — contributor has a merged PR but it targets a
  different branch than expected
- `in_progress` — contributor has PRs but none merged
- `no_evidence` — no PR evidence found for this contributor
- `evidence_unverified` — PRs exist but merge status is unknown (null)
- `conflicting` — contradictory evidence (e.g. merged=true and
  merged=false on the same PR)

These are *observation* statuses.  `merged_pr_exists` means a merged PR
exists — it does not prove the implementation matches the planned input
or that the feature is included in the target release.  Semantic
assessment is an AI responsibility recorded in `observations`.

## URL Validation

PR/MR URLs must:
- Use HTTPS scheme (`validate_pr_url` rejects http; the generic
  `validate_url` still accepts http for other URL types)
- Have no embedded credentials
- Match a supported forge pattern: GitHub `/owner/repo/pull/N` or
  GitLab `/owner[/subgroup]*/repo/-/merge_requests/N`
- Have a numeric PR/MR identifier
- Be the canonical PR page (trailing paths like `/files` rejected)

Canonical normalization lowercases the scheme and host while
preserving path case, so `HTTPS://GITHUB.COM/Org/Repo/pull/1`
and `https://github.com/Org/Repo/pull/1` are the same identity.
Query strings and fragments are stripped for identity normalization.
Synthetic `.example`/`.invalid` domains are supported for testing.

## Current State Contract

The `check-enrichment` subcommand requires a `current_state` object:

| Field | Type | Required | Notes |
|---|---|---|---|
| `key` | string | Yes | Must match plan's issue key |
| `summary` | string | Yes | For snapshot drift detection |
| `description` | string | Yes | Raw description for drift detection |
| `remote_links` | array | Yes | Current Remote Links |
| `fields` | object | No | Actual Jira field values |
| `fields.fixVersions` | array | No | Required for metadata writes; missing/null/non-list fails closed |

Unknown actual field values (missing `fields` or `fields.fixVersions`)
must NOT be fabricated as `[]` — they block metadata writes.  An
explicit empty list (`[]`) is a known absence and permits writes.
