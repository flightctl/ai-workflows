---
name: e2e-coverage-policy
version: 0.1.0
description: >-
  Discover and resolve E2E test coverage policy from repository guidance.
  Returns refreshed candidate entries and effective restrictions for the
  caller to persist.
---
# Recipe: E2E Coverage Policy

Discover, refresh, and resolve E2E test coverage policy from the project's
AI convention files and referenced testing guidance. This recipe owns the
shared policy algorithm; it returns refreshed evidence and effective
restrictions — the **caller** is responsible for persisting results and
acting on them (writing artifacts, notifying users, gating decisions).

## Parameters

| Parameter | Description |
|-----------|-------------|
| PRIOR_ENTRIES | Prior E2E Coverage Policy entries from the caller's context (if any), including Resolution fields and Source provenance. Empty on first invocation. |
| DISCOVERED_FRAMEWORKS | List of discovered E2E frameworks and their test locations |

## When to invoke

Every phase that makes or evaluates a policy-dependent decision **must**
invoke this recipe unconditionally — even when policy entries already
exist, even on a validation cache hit, and even when `AGENTS.md`/`CLAUDE.md`
are already in session. Policy guidance can change between workflow
commands; a stale snapshot is never sufficient.

## Process

### Step 1: Snapshot prior evidence and read current sources

Snapshot PRIOR_ENTRIES (including any Resolution fields and Source
provenance) for use in Step 3. Then read the project's **current**
`AGENTS.md`, `CLAUDE.md`, and any testing-related documents they
reference for explicit directives about new E2E test coverage. Also
freshly check any source files or sections previously recorded in the
snapshot — a previously known source that is now missing or unreadable
must be detected, not silently discarded.

This read is always fresh — never rely on cached or previously loaded
content for policy decisions.

### Step 2: Classify each framework/scope

For each framework in DISCOVERED_FRAMEWORKS, evaluate the current source
guidance **and** any previously recorded sources from the Step 1 snapshot.
Build candidate entries — one per framework/scope combination. When
policies differ by path for the same framework, record separate entries
(e.g. `Cypress/legacy/` = prohibited, `Cypress/integration/` = none).

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
that had a Resolution field:

- Compare the Source file's current content against the excerpt/identity
  recorded with the Resolution (not just the file path).
- **Source unchanged:** preserve the existing Resolution. Apply the
  Resolution's decision to derive per-path effective values:
  - **Full-scope Resolution** (Resolution.scope equals entry Scope):
    set the entry's Restriction to the resolved value (`none` if
    permitted, `prohibited` if forbidden).
  - **Partial-scope Resolution** (Resolution.scope is narrower than
    entry Scope, e.g. `cypress/smoke/` within `cypress/**`): the
    entry's raw Restriction stays `ambiguous`. The Resolution
    provides an effective override only within Resolution.scope —
    Step 4 uses this scoped value when evaluating paths inside
    Resolution.scope, and the raw `ambiguous` for paths outside it.
    The whole parent entry does NOT become `none` from a partial
    permission. If the unclarified remainder cannot be precisely
    determined, keep `ambiguous` rather than widen permission.
- **Source changed:** invalidate the Resolution field, set Restriction
  to the re-evaluated value from the new source, and include a
  diagnostic indicating the prior decision may no longer apply.
- **Source unreadable/missing:** set Restriction to `unresolved`. A prior
  Resolution may remain as audit information but is NOT effective
  permission while the source cannot be checked. After recovery, reuse
  the Resolution only if a fresh read confirms the guidance is unchanged;
  otherwise invalidate it.

User clarification can resolve **readable** `ambiguous` restrictions only.
User clarification CANNOT resolve `unresolved` to `none` or `prohibited`.

### Step 4: Compute final effective restriction

For each target framework/path, derive the effective restriction by
considering ALL applicable entries from Steps 2–3:

1. For each entry whose Scope covers the target path, determine the
   per-path value: use the Resolution's scoped effective value if the
   target path is within Resolution.scope; otherwise use the entry's
   raw Restriction.
2. Combine all applicable per-path values for the target:
   - `none` is not permission to bypass a separate broader `prohibited`
     from an authoritative source.
   - A valid prior Resolution on one entry cannot erase a NEW separate
     applicable broad prohibition or conflict on another entry.
   - Conflicts between authoritative entries stay `ambiguous` unless
     the repository's own precedence resolves them.
   - A restriction scoped to one framework does not apply to others.
   - A `none` entry for one path does not release a restriction at a
     different path.

**Worked cases** (static contract, not executed agent proof):

| Input | Resolution | Target path | Effective |
|-------|-----------|-------------|-----------|
| Cypress `ambiguous` scope=`cypress/**` | full-scope permit | `cypress/smoke/` | `none` |
| Cypress `ambiguous` scope=`cypress/**` | partial permit scope=`cypress/smoke/` | `cypress/smoke/foo.cy.ts` | `none` (within Resolution.scope) |
| Same partial as above | same | `cypress/e2e/bar.cy.ts` | `ambiguous` (outside Resolution.scope) |
| Same partial + independent broad `prohibited` scope=`all paths` | same | `cypress/smoke/foo.cy.ts` | `prohibited` (broad ban overrides) |
| Cypress `ambiguous` scope=`cypress/**` | source changed → invalidated | any | re-evaluated from new source |
| Cypress `ambiguous` scope=`cypress/**` | source unreadable → `unresolved` | any | `unresolved` (Resolution audit-only) |

### Step 5: Return refreshed policy evidence

Return the refreshed candidate entries, effective restrictions, and any
diagnostics (e.g. invalidated Resolutions, source errors) to the calling
phase. The **caller** is responsible for:

- Merging returned entries into its context artifacts
- Persisting via its own artifact write/confirmation path
- Acting on diagnostics (e.g. notifying users of invalidated Resolutions)
- Gating its own decisions on the effective restrictions

If no E2E framework was discovered, return an empty result so the caller
can omit the policy section.

## Output

Refreshed candidate entries (one per framework/scope combination) with:
Framework, Restriction, Scope, Source, Details, Resolution (if any),
and diagnostics (invalidations, source errors).

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
