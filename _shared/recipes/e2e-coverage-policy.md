---
name: e2e-coverage-policy
version: 0.1.0
description: >-
  Discover and resolve E2E test coverage policy from repository guidance.
  Used by ui-implement phases to determine per-framework, per-path
  restrictions on new test coverage.
---
# Recipe: E2E Coverage Policy

Discover, refresh, and resolve E2E test coverage policy from the project's
AI convention files and referenced testing guidance. This recipe owns the
shared policy semantics; consuming phases read and follow it before every
policy-dependent decision.

## Parameters

| Parameter | Description |
|-----------|-------------|
| CONTEXT_PATH | Path to `01-context.md` for this story |
| DISCOVERED_FRAMEWORKS | List of E2E frameworks discovered during `/ingest` (from the E2E Framework section of `01-context.md`) |
| PHASE | The calling phase (`ingest`, `plan`, `revise`, `code`, or `validate`) |

## When to invoke

Every phase that makes or evaluates a policy-dependent decision **must**
invoke this recipe unconditionally — even when the E2E Coverage Policy
section already exists in `01-context.md`, even on a validation cache hit,
and even when `AGENTS.md`/`CLAUDE.md` are already in session. Policy
guidance can change between workflow commands; a stale snapshot is never
sufficient.

## Process

### Step 1: Snapshot prior evidence and read current sources

If CONTEXT_PATH already has an E2E Coverage Policy section, snapshot the
prior entries (including any Resolution fields and Source provenance)
before proceeding. This snapshot is used in Step 3 for
preservation/invalidation comparison.

Then read the project's **current** `AGENTS.md`, `CLAUDE.md`, and any
testing-related documents they reference for explicit directives about
new E2E test coverage. Also freshly check any source files or sections
previously recorded in the snapshot — a previously known source that is
now missing or unreadable must be detected, not silently discarded.

This read is always fresh — never rely on cached or previously loaded
content for policy decisions.

### Step 2: Classify each framework/scope

For each framework in DISCOVERED_FRAMEWORKS, evaluate the current source
guidance **and** any previously recorded sources from the Step 1 snapshot.
Build candidate entries — one per framework/scope combination. When
policies differ by path for the same framework, record separate entries
(e.g. `Cypress/legacy/` = prohibited, `Cypress/integration/` = none).
These are candidate entries; the caller persists them (see Step 5).

**Restriction values:**

- `none` — no explicit restriction found for this framework in the
  applicable scope. This includes projects where optional convention
  files (`AGENTS.md`/`CLAUDE.md`) are absent — a never-present optional
  file is complete discovery, not an unresolved source. Default
  discovery-based behavior applies.
- `prohibited` — an explicit directive forbids adding new test specs,
  cases, coverage, or stubs for this framework within the stated scope.
  Record the source file, section heading, and applicable path scope.
- `ambiguous` — wording is unclear or conflicts with other guidance.
  Record all relevant sources so the user can clarify.
- `unresolved` — a known, referenced, or previously recorded applicable
  policy source is missing or unreadable. Record the file path and
  error. Prevents new coverage or stubs for the affected framework/scope
  only; does not suppress other frameworks or scopes. A previously
  recorded source that is now missing stays `unresolved`, not `none`.
  Never-present optional files are `none`, not `unresolved`.

### Step 3: Preserve or invalidate prior user clarifications

Using the prior-evidence snapshot from Step 1, for each candidate entry
that had a Resolution field from a prior `/revise`:

- Compare the Source file's current content against the excerpt/identity
  recorded with the Resolution (not just the file path).
- **Source unchanged:** preserve the existing Resolution. Set the entry's
  Restriction to the resolved value (`none` if the user permitted,
  `prohibited` if the user forbade). The Resolution applies only to its
  own entry's framework/scope — it cannot override a separate applicable
  entry.
- **Source changed:** invalidate the Resolution field, set Restriction
  to the re-evaluated value from the new source, and (if PHASE is
  `revise`) notify the user that the prior decision may no longer apply.
- **Source unreadable/missing:** set Restriction to `unresolved`. A prior
  Resolution may remain as audit information but is NOT effective
  permission while the source cannot be checked. After recovery, reuse
  the Resolution only if a fresh read confirms the guidance is unchanged;
  otherwise invalidate it.

User clarification can resolve **readable** `ambiguous` restrictions only.
User clarification CANNOT resolve `unresolved` to `none` or `prohibited`.

### Step 4: Compute final effective restriction

After Steps 2–3 produce candidate entries (with preserved or invalidated
Resolutions), compute the final effective restriction for each
framework/path by considering ALL applicable entries:

- `none` (no explicit restriction found) is not permission to bypass a
  separate broader prohibition from an authoritative source.
- A valid prior Resolution on one entry cannot erase a NEW separate
  applicable broad prohibition or conflict on another entry.
- Conflicts between authoritative entries stay `ambiguous` unless the
  repository's own precedence resolves them.
- A restriction scoped to one framework does not apply to others.
- A restriction scoped to one path does not apply outside that path.
- A `none` entry for one path does not release a restriction at a
  different path.

### Step 5: Return refreshed policy evidence

Return the refreshed candidate entries and effective restrictions to the
calling phase. The **caller** is responsible for persisting these entries
into CONTEXT_PATH via its own artifact write/confirmation path:

- `/ingest`: merges into the context draft and writes in Step 8/8a
  (respecting the write-each-output-once rule and user confirmation).
- `/plan`, `/code`, `/validate`: update the E2E Coverage Policy section
  of the existing `01-context.md` before their own policy decisions.
- `/revise`: updates the E2E Coverage Policy section of `01-context.md`;
  the plan revision (`02-plan.md`) is updated separately by `/revise`
  Step 5.

If no E2E framework was discovered, omit the section entirely.

## Output

The E2E Coverage Policy section of CONTEXT_PATH, with one entry per
framework/scope combination containing: Framework, Restriction, Scope,
Source, Details, and (when applicable) Resolution.

## Invariants

- No E2E framework discovered → omit the section; do not introduce a
  framework.
- Framework present, no contrary policy → `none`; planned-stub default
  applies.
- Explicit applicable policy from authoritative source overrides inferred
  presence-based convention.
- Unreadable known source → `unresolved`; no new coverage or stubs for
  affected scope. Prior Resolution is audit-only until source recovered
  and confirmed unchanged.
- No replacement framework, blanket new approval, deletion or weakening
  of existing test checks.
- Each consuming phase re-invokes this recipe before its own policy
  decisions; no phase trusts a prior phase's snapshot alone.
