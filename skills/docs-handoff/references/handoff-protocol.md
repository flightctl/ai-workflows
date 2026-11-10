# Handoff Protocol

Preview/apply two-phase workflow for the docs-handoff skill.

## Phase 1: Preview (No Side Effects)

### Step 1 — Validate Issue

Provide the DOCS issue snapshot (from Jira read or offline file) to
`evidence.py validate --input snapshot.json`.  The script validates
structure, extracts contributors, dependencies, and Documentation Inputs
items.  If validation fails (exit 1), stop and report errors.

### Step 2 — Gather Evidence (AI Responsibility)

For each extracted contributor (NOT dependencies):

1. Fetch the contributor's Jira issue to discover linked PRs.
2. For each PR: read metadata (URL, title, target branch, merge status,
   merge commit).
3. Read PR diffs and assess what user-facing surfaces changed.
4. Record semantic observations comparing planned inputs against actual
   implementation.

Evidence quality requirements:
- Merged PR status alone does not prove target-release inclusion.
- String equality is not semantic confirmation — actual code review is
  required.
- Partial evidence is a valid intermediate state — report honestly.
- Unknown or contradictory results are reported as findings.
- An observation like "as planned" does NOT produce a source update
  proposal — only divergent observations generate proposals.

### Step 3 — Normalize Evidence

Provide raw evidence items to `evidence.py normalize --input evidence.json`.
The script validates URLs (requiring supported PR/MR structure), rejects
credentials, deduplicates, and detects contradictory states.

### Step 4 — Build Plan

Provide validation result, normalized evidence, target, and optional
profile to `evidence.py build-plan --input plan-input.json`.  The input
is a JSON object with keys: `validation`, `evidence`, `target`, `profile`.

### Step 5 — Check Enrichment

Provide the plan and current issue state (with `key` and `remote_links`)
to `evidence.py check-enrichment --input check-input.json`.  The input
has keys: `plan`, `current_state`, `approved_baseline` (optional).

### Step 6 — Present Preview

Show the complete bounded preview including:
- Target issue key and baseline
- Per-input evidence status with PR references
- Findings (missing evidence, unresolved refs, non-contributor evidence)
- Eligible PR Remote Links (contributor PRs only)
- Metadata proposals with catalog verification status
- Source-change proposal (disabled, with proposed wording)
- Consumer readiness state

## Phase 2: Apply (Explicit Approval Required)

### On Approval

1. Re-read the issue from Jira (fresh snapshot).
2. Re-run `check-enrichment` with the `approved_baseline` from Phase 1.
3. If stale (baseline changed), regenerate with fresh preview.
4. Apply eligible links and metadata via approved runtime capabilities.
5. Re-read the issue; run `check-enrichment --readback` for receipts.

### On Rejection

No writes.  Artifacts remain for review.

## Source-Change Proposals

The skill produces structured proposals for updating Documentation
Inputs through the design workflow's `/revise` phase.  Each proposal
carries:

- `action`: `update` (divergent input) or `add_contributor` (new)
- `proposed_wording`: specific text or unresolved question
- `evidence_urls`: supporting PR URLs
- `source_location`: where in the source artifact
- `observations`: divergent observations from code review

Source/narrative apply is disabled.  This is an explicit design choice:
the design workflow owns Documentation Inputs, direct edits risk sync
manifest conflicts, and writer-managed content must not be overwritten.

## CLI Sequence

```bash
# 1. Validate offline snapshot
python3 evidence.py validate --input snapshot.json
# 2. Normalize raw evidence (from AI gathering)
python3 evidence.py normalize --input raw-evidence.json
# 3. Build change plan
python3 evidence.py build-plan --input plan-input.json
# 4. Check enrichment eligibility
python3 evidence.py check-enrichment --input check-input.json
# 5. After approved writes, verify with readback
python3 evidence.py check-enrichment --input check-input.json \
  --readback readback.json
```

All inputs are file paths via `--input`.  No stdin support.  Exit 0 on
success, exit 1 on validation/data errors, exit 2 on argument errors.
