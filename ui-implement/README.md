# UI Implement Workflow

A story-to-code workflow for UI/front-end stories. Takes a Jira [UI] Story, plans the implementation using discovered design-system and testing conventions, writes contract-based unit tests and production code via TDD, validates against the project's CI expectations, and manages review via GitHub PRs.

## Phase Flow

```mermaid
graph TD
    ingest([ingest]) --> plan
    plan --> revise
    revise --> revise
    plan --> code
    revise --> code
    code --> validate
    validate -->|pass| publish
    validate -->|fail| validate
    publish -->|comments| respond
    respond --> respond
```

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Jira access (MCP or CLI) | For `/ingest` | Fetch Story issue details |
| GitHub CLI (`gh`) | For `/publish`, `/respond` | Create PRs, post review comments |
| Git | Yes | Branch management, commits |
| Project build/test tooling | Yes | Discovered during `/ingest` from project's AGENTS.md, package.json, CI workflows |
| Docs repo (local clone) | For `/ingest` | Read ui-design, PRD, handoff, and API findings documents |

## Phases

| Phase | Command | Purpose | Artifact(s) |
|-------|---------|---------|-------------|
| Ingest | `/ingest` | Fetch story, load ui-design/PRD/handoff context, discover UI toolchain | `01-context.md`, `testplan.md` (when test cases match) |
| Plan | `/plan` | Design implementation approach, component/hook interfaces, test strategy | `02-plan.md` |
| Revise | `/revise` | Incorporate feedback into the plan | Updated `02-plan.md` |
| Code | `/code` | Write unit tests and code via TDD, then integration/e2e stubs | `03-test-report.md`, `04-impl-report.md` |
| Validate | `/validate` | Run tests, lint, type checking, coverage analysis | `05-validation-report.md` |
| Publish | `/publish` | Push branch, create draft PR | `06-pr-description.md` |
| Respond | `/respond` | Address reviewer comments | `07-review-responses.md` |

Each phase command invokes `skills/dispatch.md` with the requested phase. The
dispatcher resolves any project override, loads only that phase, and passes
along the command context. After the phase reports its result,
`skills/completion.md` supplies the shared next-step guidance without loading
the full controller. The controller remains the entry point for workflow
discovery and ambiguous requests.

## Typical Flow

```text
/ingest EDM-1234
  → fetches story from Jira
  → loads ui-design document, design document, PRD, handoff, API findings
  → explores affected components and UI codebase areas
  → discovers UI toolchain (test framework, design system, i18n, state management)
  → discovers validation profile (build, test, lint, type-check commands)
  → writes .artifacts/ui-implement/EDM-1234/01-context.md
  → writes testplan.md when story test cases match

/plan
  → designs implementation approach
  → defines component props and hook signatures (the contracts)
  → plans unit test strategy per component/hook
  → plans integration/e2e test stubs (if framework exists and policy permits)
  → plans UI cross-cutting concerns (design system, i18n, a11y, permissions, states)
  → breaks work into ordered tasks
  → optionally includes Task 0 for test framework introduction
  → writes 02-plan.md

/revise (optional, repeatable)
  → user reviews plan, requests changes
  → plan updated, consistency maintained

/code
  → creates feature branch
  → for each task: write unit tests → write code → review → commit
  → after all tasks: write integration/e2e test stubs (if planned and policy permits)
  → updates 02-plan.md with task completion status
  → writes 03-test-report.md, 04-impl-report.md

/validate
  → runs full validation suite (discovered during /ingest)
  → analyzes coverage for untested behavioral paths
  → verifies UI cross-cutting concerns (design system, i18n, a11y, states)
  → adds tests for gaps, fixes lint/type issues
  → writes 05-validation-report.md

/publish
  → pushes feature branch
  → creates draft GitHub PR with Jira link
  → writes 06-pr-description.md

/respond (repeatable)
  → fetches PR review comments
  → proposes responses (user approves before posting)
  → applies code changes if needed
  → writes 07-review-responses.md
```

## Artifacts

All artifacts are stored in `.artifacts/ui-implement/{issue-key}/`.

```text
.artifacts/ui-implement/EDM-1234/
  01-context.md              (story context, UI toolchain, validation profile)
  testplan.md                (story-scoped test cases, when ingest finds matches)
  02-plan.md                 (task breakdown, test strategy — updated as tasks complete)
  03-test-report.md          (tests written, contracts covered)
  04-impl-report.md          (changes, commits, UI concerns applied, deviations)
  05-validation-report.md    (check results, coverage, UI cross-cutting verification)
  06-pr-description.md       (PR body)
  07-review-responses.md     (review comment log)
  publish-metadata.json      (PR number, branch, URL)

.artifacts/ui-implement/
  _validation-profile.md     (discovered build/test/lint commands, cached across stories)
  .meta.json                 (file hashes/mtimes for validation cache invalidation)
```

## Key Design Decisions

### Contract-Based Testing (TDD for Unit Tests)

Unit tests validate behavioral contracts through public interfaces:
- **Components:** Test rendered output, user interactions, accessibility attributes
- **Hooks:** Test return values, state transitions, side effects
- Tests should remain valid if the implementation were rewritten
- Unit tests use TDD: write tests first, then implementation, task by task

### Integration/E2E Test Stubs (Post-Implementation)

Integration and e2e test stubs are written **after** all implementation tasks complete:
- Stubs follow the project's existing e2e patterns (if any)
- They provide scaffolding (describe blocks, pending tests) — not full implementations
- Full e2e test suites are the responsibility of `[QE]` stories
- **Policy-gated:** `/ingest` discovers explicit test coverage policies from
  `AGENTS.md`, `CLAUDE.md`, and referenced testing guidance. When a project
  prohibits new coverage for a specific framework, no stubs are planned or
  generated for that framework. Restrictions are per-framework — a Cypress
  prohibition does not suppress Playwright stubs. Ambiguous or conflicting
  guidance is surfaced for user clarification during `/revise`.

### Discovery-Based Everything

The workflow does not hardcode any tool assumptions. During `/ingest`, it discovers:
- Test framework (Vitest, Jest, Mocha, etc.)
- Design system (PatternFly, MUI, Chakra, custom, etc.)
- i18n library (react-i18next, react-intl, FormatJS, etc.)
- State management approach
- Routing library
- E2e framework (Cypress, Playwright, etc.)
- E2e coverage policy — per-framework/path restrictions via `_shared/recipes/e2e-coverage-policy.md`
- Permission/RBAC patterns
- Build, test, lint, and type-check commands

If the project adds new tools or changes conventions, the next `/ingest` picks them up.

### Test Framework Introduction

When `/ingest` discovers no unit testing framework exists:
- It identifies suitable frameworks based on the project's build tooling
- Records a recommendation in `01-context.md`
- `/plan` includes this as "Task 0: Introduce unit testing framework"
- The user approves the framework choice before any story code is written

### Upstream Design Documents

This workflow reads published docs from the docs repo, never from another
workflow's `.artifacts/` directory:
- `ui-design-{workspace-id}.md` — **required** — component architecture, hook designs, state management, accessibility plan
- `handoff.md` — **optional** — interaction specs, state matrix, acceptance criteria enrichment
- `api-findings-{workspace-id}.md` — **optional** — resolved endpoints, API gaps
- `prd.md` — requirements coverage
- `design.md` — API contracts, data models

### UI Cross-Cutting Concerns

Every `/code` task and `/validate` review checks:
- **Design system compliance** — use design system components, not raw HTML
- **i18n** — wrap all user-visible strings
- **Accessibility** — ARIA attributes, keyboard navigation, screen reader text
- **Permission-aware rendering** — use discovered RBAC patterns
- **State completeness** — loading, error, and empty states

### What This Workflow Does NOT Do

- Full e2e test suites (those are for `[QE]` stories via the `e2e` workflow)
- Visual regression tests
- Backend implementation (that's the `implement` workflow for `[DEV]` stories)

## Directory Structure

```text
ui-implement/
├── SKILL.md                    # Workflow entry point
├── guidelines.md               # Behavioral rules and guardrails
├── README.md                   # This file
├── templates/
│   ├── 01-context.md           # Ingest context skeleton
│   └── story-testplan.md       # Story-scoped testplan skeleton
├── skills/
│   ├── controller.md           # Discovery and ambiguous-input router
│   ├── dispatch.md             # Explicit-phase dispatcher
│   ├── completion.md           # Shared next-step guidance
│   ├── ingest.md               # Fetch story, discover UI toolchain, explore codebase
│   ├── plan.md                 # Design implementation approach
│   ├── revise.md               # Incorporate plan feedback
│   ├── code.md                 # Write tests and code via TDD, then stubs
│   ├── validate.md             # Run validation suite
│   ├── publish.md              # Create GitHub PR
│   └── respond.md              # Address review comments
└── commands/
    ├── ingest.md               # /ingest command
    ├── plan.md                 # /plan command
    ├── revise.md               # /revise command
    ├── code.md                 # /code command
    ├── validate.md             # /validate command
    ├── publish.md              # /publish command
    └── respond.md              # /respond command
```

## Getting Started

```bash
# Install the workflow
./install.sh claude --packages ui-implement

# Or install all workflows
./install.sh all
```

Then in your project, run the `ui-implement` workflow's `ingest` command for your Jira story (e.g., EDM-1234).

## E2E Coverage Policy — Behavioral Scenarios

The following matrix describes how E2E test stub planning and generation
behaves under different project configurations. These are instruction-level
contracts — the workflow instructions specify this behavior; actual execution
depends on the LLM following the instructions at runtime.

All five phases invoke `_shared/recipes/e2e-coverage-policy.md` unconditionally before policy decisions:
- **Ingest**: PHASE=ingest — discovers frameworks, records initial evidence; caller persists in Step 8/8a
- **Plan**: PHASE=plan — freshly refreshes before stub strategy per artifact path
- **Revise**: PHASE=revise — freshly refreshes; handles user clarification for readable ambiguity; persists Resolution
- **Code**: PHASE=code — recomputes from current sources before writing stubs; never trusts stale plan
- **Validate**: PHASE=validate — freshly refreshes before diff enforcement within applicable scope

| Scenario | Ingest | Plan | Code (Step 4) | Validate |
|----------|--------|------|---------------------|----------|
| No E2E framework discovered | Policy section omitted | "No stubs — no e2e framework" | Step skipped entirely | No stub gap flagged |
| Framework present, no restriction (`none`) | Records `none` per framework | Plans stubs normally | Writes stubs normally | Reports stubs per plan |
| Framework present, `prohibited` | Records `prohibited` with source | No stubs planned for that framework | Skips stubs for that framework | Verifies diff has no new prohibited coverage; reports "respected" |
| Framework A prohibited, Framework B unrestricted | A=`prohibited`, B=`none` | Plans stubs for B only | Writes stubs for B only; skips A | Verifies A clean; reports B per plan |
| `ambiguous` restriction (scoped) | Records `ambiguous` with both sources per scope | No stubs in ambiguous paths; other paths for same framework eligible if own policy permits | Skips stubs in ambiguous scope only | Reports "ambiguous" per affected scope; recommends `/revise` |
| Same framework: pathA `ambiguous`, pathB `none` | Both entries recorded | Skips stubs for pathA; plans stubs for pathB normally | Writes stubs for pathB only | Reports ambiguous for A, stubs per plan for B |
| `/revise` resolves readable ambiguous → `prohibited` | — | Updated in next revision | Honors resolved restriction | Verifies prohibition respected |
| `/revise` resolves readable ambiguous → `none` | — | Plans stubs in next revision | Writes stubs normally | Reports stubs per plan |
| Older `01-context.md` without policy section | — | Re-reads current sources; performs full discovery | Re-reads current sources; backfills result | Re-reads current sources before assuming default |
| `AGENTS.md` adds new policy after initial ingest | — | Re-read finds new policy; applies it | Re-read finds new policy; applies it | Re-read finds new policy; applies it |
| Existing `none` entry becomes `prohibited` after `AGENTS.md` changes | — | Re-read detects changed source; updates entry to `prohibited`; suppresses stubs | Re-read detects changed source; updates entry; skips stubs | Re-read detects changed source; verifies no new prohibited coverage |
| Cached validation profile reused across stories | Policy discovery runs unconditionally even on cache hit | Same freshness re-read as new ingest | Same freshness re-read | Same freshness re-read |
| Known/referenced source missing or unreadable (`unresolved`) | Records `unresolved` with file path and error for affected framework/scope only | Does not plan stubs or coverage for that framework/scope; others unaffected | Does not write stubs or coverage for that framework/scope | Verifies no new coverage/stubs in affected scope; reports "unresolved"; recommends `/revise` |
| Previously recorded source now missing | Records `unresolved` — does not silently become `none` | Does not plan stubs; reports unresolved source | Does not write stubs | Reports "unresolved — previously recorded source missing" |
| Optional `AGENTS.md`/`CLAUDE.md` never present, never recorded | Records `none` — never-present optional file is complete discovery, not unresolved | Plans stubs normally (no restriction found) | Writes stubs normally | No policy violation; reports per plan |
| `/revise` resolves readable ambiguous to permitted (`none`) | — | — | — | — |
| ↳ Source content unchanged since resolution | — | Restriction=`none`; honors Resolution; plans stubs normally | Writes stubs normally | Reports stubs per plan |
| ↳ Source content changed since resolution | — | Invalidates Resolution; re-reads source; re-evaluates restriction | Re-reads; applies new restriction | Re-reads; validates against new restriction |
| `/revise` Resolution provenance | — | Source retains repo file/section; Resolution stores decision + excerpt identity + "user decision during /revise" | Traces both Source and Resolution | Traces both; detects content changes via recorded excerpt |
| `unresolved` cannot be user-resolved to `none` | — | `unresolved` stays until source recovered and readable | Stubs deferred; prior Resolution is audit only, not permission | Verifies no new coverage/stubs; reports "unresolved" |
| Previously permitted resolution → source becomes unreadable | — | Resolution suspended; restriction reverts to `unresolved`; no stubs | No new stubs or coverage in affected scope | Reports "unresolved"; prior permission not effective |
| Source recovered after `unresolved` | — | Fresh read; if guidance unchanged, prior Resolution reused; if changed, invalidated | Honors reused or re-evaluated restriction | Validates against effective restriction |
| `unresolved` prevents coverage AND stubs | — | No new coverage or stubs for affected framework/scope | No new specs, cases, coverage, or stubs | Verifies diff has no new specs/cases/coverage/stubs in affected scope; existing tests preserved |
| Separate broad prohibition still applies across paths | — | Even if one path's ambiguity is resolved, a separate applicable prohibition still blocks | Honors effective policy after considering all applicable entries; a broad prohibition is not bypassed by a narrower resolution | Validates against all applicable entries |
| Restriction scoped to specific path (e.g. `cypress/`) | Records scope per entry | Applies restriction only within scoped path; plans stubs outside scope normally | Writes stubs only outside scoped path | Verifies no new coverage within scoped path; allows stubs outside |
| Broad prohibition + narrow `none`: generation recomputes | — | — | Recomputes from current sources; inferred narrow `none` does not bypass broader explicit prohibition; writes stubs only where effective restriction is `none` | Validates against freshly computed effective policy |
| Prohibited scope: validation checks only within scope | — | — | — | Checks new specs/cases/coverage/stubs within prohibited path scope only; stubs outside the scope evaluated by their own effective policy |
