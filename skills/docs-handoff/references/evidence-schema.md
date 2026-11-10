# Evidence Schema and Validation

Contract for DOCS issue validation, contributor extraction, and
delivery-evidence normalization.

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

The script `../scripts/evidence.py validate` validates the snapshot and
extracts structured data.

## Required Description Sections

A valid `[DOCS]` issue description must contain these `##` sections:

- **Documentation Inputs** — planned user-facing artifacts grouped by
  contributing story
- **Documentation Scope** — what the reader needs to understand
- **Acceptance Criteria** — reader-verifiable documentation outcomes

Missing sections produce validation errors.

## Contributor Extraction

Contributors are extracted from the `Contributing stories:` line in the
Design Reference section.  In a rendered (synced) issue, these are Jira
keys (e.g. `TEST-201`).  Unresolved `Story N.NN` placeholders are
extracted as qualified IDs and flagged as warnings.

**Contributors vs Dependencies**: the `Dependencies` section lists
prerequisite stories that must complete before documentation work begins.
Dependencies are NOT automatically direct contributors — they do not
produce user-facing artifacts that belong in Documentation Inputs.  The
script extracts these separately and the plan does not generate
missing-evidence findings for dependency-only references.

## Documentation Inputs Parsing

The Documentation Inputs section is parsed into structured items:

```
**JIRA-KEY -- title:**
- Input item text
- Another item [Assumption]
- Open item [Open: §9.2]
```

Each item records:
- `contributor`: the Jira key or qualified story ID from the header
- `text`: the input description
- `marker`: `planned` (default), `assumption`, or `open`
- `open_ref`: the referenced open question (when marker is `open`)

## PR Evidence Items

Each gathered PR evidence item must have:

| Field | Type | Required |
|---|---|---|
| `pr_url` | string | Yes — HTTP(S) PR/MR URL |
| `contributor_key` | string | Yes — Jira key of contributing story |
| `target_branch` | string | No — PR target branch |
| `state` | string | No — PR state (open, merged, closed) |
| `title` | string | No — PR title |
| `merged` | boolean | No — whether PR is merged |
| `merge_commit` | string | No — merge commit SHA |
| `observations` | array | No — AI-generated semantic observations |

The script `normalize-evidence` (internal to `build-plan`) validates
URLs, rejects embedded credentials, deduplicates by normalized URL,
and preserves distinct repository identities.

## Input Status Values

After comparing planned inputs against gathered evidence, each input
receives a status:

- `delivered` — contributor has at least one merged PR
- `in_progress` — contributor has PRs but none merged
- `missing` — no PR evidence found for this contributor

These are *delivery* statuses, not semantic confirmation.  A `delivered`
status means a merged PR exists — it does not prove the actual
implementation matches the planned input.  Semantic planned-vs-actual
assessment is an AI responsibility recorded in `observations`.
