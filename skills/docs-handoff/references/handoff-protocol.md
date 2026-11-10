# Handoff Protocol

Preview/apply two-phase workflow for the docs-handoff skill.  This
protocol governs the end-to-end flow from issue intake to enrichment
and source-change proposals.

## Phase 1: Preview (No Side Effects)

All operations in the preview phase are read-only.  No Jira writes,
no source file modifications, no issue state changes.

### Step 1 — Validate Issue

Provide the DOCS issue snapshot to `evidence.py validate`.  The script
validates structure, extracts contributors, dependencies, and
Documentation Inputs items.  If validation fails (missing sections,
invalid key, no contributors), stop and report the errors.

### Step 2 — Gather Evidence (AI Responsibility)

For each extracted contributor (NOT dependencies):

1. Fetch the contributor's Jira issue to discover linked PRs
2. For each PR, read metadata: URL, title, target branch, merge status,
   merge commit
3. Read the PR diff and assess what user-facing surfaces changed
4. Record semantic observations comparing planned inputs against actual
   implementation

**Evidence quality requirements:**

- A merged PR status alone does not prove the feature is delivered to
  the target release.  Record the target branch and note ambiguity when
  it differs from the expected release branch.
- String equality between a planned input and a PR title is not semantic
  confirmation.  Actual code/diff review is required.
- Partial evidence (some PRs found, some contributors without PRs) is a
  valid intermediate state.  Report it accurately — do not claim
  completion or fabricate evidence.
- Unknown or contradictory results (e.g., PR merged but reverted) must
  be reported as findings, not silently resolved.

### Step 3 — Build Plan

Provide the validation result, normalized evidence, target, and optional
profile to `evidence.py build-plan`.  The script produces:

- Per-input delivery status (delivered/in\_progress/missing)
- PR Remote Links to add
- Metadata proposals
- Findings (missing evidence, new surfaces, unresolved refs, target
  ambiguity)
- Source-change proposal (disabled; advisory)
- Consumer readiness dimensions (when profile provided)

### Step 4 — Check Enrichment

Provide the plan and current issue state (with existing Remote Links) to
`evidence.py check-enrichment`.  The script identifies:

- Eligible links (new, not already present)
- Existing links (already on the issue)
- Skipped links (invalid URLs)
- Forbidden fields (blocked by policy)
- Baseline fingerprint (for drift detection)

### Step 5 — Present Preview

Show the user the complete bounded preview:

- Target issue key and current baseline
- Delivery summary (counts per status)
- Per-input status with PR references and target notes
- Findings requiring attention
- Eligible PR Remote Links (the set that would be added)
- Existing links (already present, no action needed)
- Metadata proposals with evidence
- Source-change proposal (disabled, with intended changes and owning
  workflow action)
- Consumer readiness state (dimensions recorded, results pending)
- Operation eligibility summary

## Phase 2: Apply (Explicit Approval Required)

The user reviews the preview and explicitly approves or rejects the
enrichment plan as a single bounded operation.

### On Approval

1. **Re-read** the issue's current Remote Links from Jira (fresh, not
   cached from preview).
2. **Detect drift**: if the baseline fingerprint changed since the
   preview, the plan is stale.  Report the conflict and regenerate.
3. **Apply** eligible PR Remote Links via the runtime's available Jira
   write capability.
4. **Re-read** the issue after writes.
5. **Produce receipt**: per-link confirmed/uncertain status.
6. **Report**: complete results including any uncertain outcomes.

### On Rejection

No writes.  The preview artifacts remain available for review.

## Source-Change Proposals

The skill produces structured proposals for updating the Documentation
Inputs section in the owning design workflow's source artifacts.  These
proposals include:

- Specific intended changes (add, update) with evidence references
- The owning workflow (`design`) and action (`/revise`)
- Factual observations from PR review

**Source/narrative apply is disabled.**  The docs-handoff skill does NOT
directly modify design source artifacts or Jira issue descriptions.  The
proposal is advisory — the human or owning workflow applies changes
through the established `/revise` phase.

This is an explicit design choice, not a limitation to work around:

- The design workflow owns the Documentation Inputs source
- Direct edits could conflict with the sync manifest and content hashes
- Writer-managed content in the description must not be overwritten
- The `/revise` phase has the correct reconciliation and consistency
  checks

If a supported explicit owning-source handoff can be established in a
future version, it must be tested for producer/renderer/sync preservation
and writer/concurrency handling BEFORE enabling apply.

## Late Contributor Changes

If evidence gathering reveals that a contributing story's actual scope
differs from the planned Documentation Inputs (e.g., a new API field was
added that is not in the plan), this is reported as a finding with type
`new_surface`.  It is a PROPOSAL for the user to evaluate, not a silent
scope expansion.  The user decides whether to:

1. Accept the new surface and request a `/revise` to update the source
2. Defer it to a future documentation cycle
3. Determine it is out of scope for this DOCS story
