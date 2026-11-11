---
name: ingest
description: Fetch the [QE] story, verify dependencies, explore e2e test infrastructure, and build a test-execution profile.
---

# Ingest Story Context Skill

You are a principal QE engineer. Your job is to fetch the [QE] story, verify
that the features under test have been implemented and merged, explore the
project's e2e testing infrastructure in depth, and produce a structured
context document that will inform the test planning phase.

This workflow is exclusively for e2e tests. Unit and integration tests are
handled by the implement workflow — do not consider them here.

## Your Role

Build a complete picture of what needs to be tested, what e2e test
infrastructure exists, and how the project runs its e2e tests. The output
must give the planning phase everything it needs to design concrete test
scenarios and file structure.

## Critical Rules

- **Read-only.** Jira access is read-only. Never create, update, or modify Jira issues.
- **Capture, don't implement.** Record what you find — test scenario decisions happen in `/plan`.
- **Deep infrastructure discovery.** Unlike implementation ingestion, e2e ingestion must thoroughly explore the project's test infrastructure — whatever abstractions it uses (harness, fixtures, page objects, helpers), lifecycle hooks, auxiliary services (if any), and test conventions. Shallow discovery leads to tests that don't follow project patterns.
- **Note unknowns.** If you can't determine something from the codebase, say so explicitly.
- **Re-invocation diffs before overwriting.** If `01-context.md` already exists, preserve it before exploring. After compiling new context, diff against the previous version and present changes to the user before overwriting (see Steps 2a and 8a).

## Shared Script

This skill delegates deterministic Jira issue fetching to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/fetch-issue.py
```

The script provides subcommands: `get` and `search`. See the script
header for full usage. It requires `JIRA_URL` and `JIRA_TOKEN`
environment variables.

## Process

### Step 1: Identify the Story

The user will provide one of:
- A Jira issue key or URL (fetch via the shared script)
- A path to an existing story file from the design workflow

Extract the full Jira issue key, including the project prefix (e.g.,
`PROJ-1234`, not just `1234`). Use this as `{issue-key}` throughout
the workflow — it is the context identifier for the artifact directory
and all downstream phases.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/e2e/{issue-key}
```

Verify that `.artifacts/` is covered by the project's `.gitignore`. If it
is not, warn the user that e2e artifacts could be accidentally committed
with the code.

### Step 2a: Check for Prior Ingest

If `.artifacts/e2e/{issue-key}/01-context.md` already exists, this is a
re-invocation. Copy the existing file to `01-context.md.prev` so it is
preserved for the diff in Step 8a.

### Step 3: Fetch the Jira Story

Resolve the shared script to an absolute path so it remains valid
regardless of working directory:

```bash
FETCH_ISSUE_SCRIPT="${HOME}/.ai-workflows/_shared/scripts/fetch-issue.py"
```

Use `$FETCH_ISSUE_SCRIPT` instead of the relative path in all subsequent
commands.

Fetch the story using the shared script:

```bash
python3 "$FETCH_ISSUE_SCRIPT" get "{issue-key}" --fields summary,description,issuetype,status,priority,labels --comments --parent --parent-fields summary,status,issuetype,parent --links --link-fields summary,status
```

Capture:
- Summary and description
- User story (As a... I want... So that...)
- Acceptance criteria
- Testing approach (if present — this is the primary implementation guidance for [QE] stories)
- Implementation guidance (if present — may be sparse for [QE] stories)
- Validated by (if present — TC IDs used for testplan filtering in Step 6)
- Design Reference (if present — PRD requirement IDs used for testplan filtering fallback in Step 6)
- Story type prefix — verify it is `[QE]`. If it is `[DEV]`, `[UI]`, or another prefix, warn the user that this workflow is designed for `[QE]` stories and ask whether to proceed.
- Parent epic key
- Story dependencies (linked issues — "depends on", "is blocked by")
- Fix version / sprint (if set)

### Step 4: Check Story Dependencies

For a `[QE]` story, dependencies are typically `[DEV]` stories that
implement the feature being tested. These are not just warnings — if the
feature doesn't exist yet, the tests cannot pass.

For each dependency identified in Step 3:
1. Check if the dependent story's Jira status indicates completion
   (Done, Closed, Resolved) — use `python3 "$FETCH_ISSUE_SCRIPT" get "{DEP-KEY}" --fields summary,status`
2. Check if the dependent story's code has been merged to the main branch
   (search git log for the dependent story's Jira key)

If dependencies are unresolved, **warn the user explicitly**:
- Which dependencies are unmerged
- That the feature under test may not exist yet
- Recommendation: wait for the `[DEV]` story to land, or proceed at risk
  (tests can be written but may not pass during `/validate` until the
  feature is merged)

### Step 5: Load Upstream Context

The PRD and design document are published to a docs repo by the prd and
design workflows. Fetch them from there.

#### 5a: Resolve the Docs Repo

Check for an existing docs repo configuration at `.artifacts/config.json`.
This config is workspace-level and shared across all workflows — a prior
workflow run may have already created it.

**If the config exists**, read it and validate:
1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the remote URL matches the configured `docs_repo_remote`

If any validation fails, inform the user and re-ask for the correct values.
Resolve `~` to an absolute path before saving. Update
`.artifacts/config.json` with the corrected values.

**If the config does not exist**, ask the user:
- **Docs repo local path:** Where is the planning docs repo checked out?
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote get-url origin`
  and confirm with the user

Validate the path and remote. Resolve `~` to the user's home directory
so the stored path is absolute. Write `.artifacts/config.json` with the
validated `docs_repo_path` and `docs_repo_remote` (workspace-level config
shared across all workflows).

#### 5b: Find the PRD and Design Document

The docs repo organizes documents by Feature-level Jira issue. To find the
right directory, walk the Jira hierarchy from the story:

1. The story (e.g., `EDM-5678`) has a parent **Epic** — fetch the Epic using
   `python3 "$FETCH_ISSUE_SCRIPT" get "{EPIC-KEY}" --fields summary,status,issuetype --parent --parent-fields summary,status,issuetype`
   to get the parent **Feature** key from the Epic's `parent` output
2. The Epic's parent is the **Feature** — extract the Feature key
   (e.g., `EDM-1100`) from the `parent.key` field returned above

The docs repo structure is `{release}/{feature-slug}/prd.md` and
`{release}/{feature-slug}/design.md`, where `{feature-slug}` includes the
Feature issue key (e.g., `port-mappings-EDM-1100`).

Search the docs repo for the Feature key:

```bash
find "{docs_repo_path}" -type d -name "*{feature-key}*"
```

If the hierarchy traversal fails or the directory isn't found, ask the user
for the path to the PRD and design document within the docs repo.

#### 5c: Read Upstream Documents

Read these from the docs repo:

1. **Design document** (`design.md`) — the technical design, including
   architectural decisions and locked decisions incorporated as content
2. **PRD** (`prd.md`) — the product requirements, with locked decisions
   reflected in the requirements text
3. **Testplan** — behavioral test cases mapped to PRD requirements.
   The primary filename is discovered in Step 6 via the validation
   index; do not assume `testplan.md` before discovery. **Do not
   read the testplan in Step 5** — defer all testplan reading to
   Step 6 after the resolver has identified the correct file.

If the design document or PRD are not found, ask the user for their
location or proceed with only the Jira story content. The design
document and PRD are valuable context but not strictly required — the
story's acceptance criteria are the primary contract.

### Step 6: Discover Validation Artifacts and Filter to Story Scope

**Resolve and validate published artifacts before reading.** Before
reading or filtering any validation artifacts (indexed or legacy),
resolve the validation index script and run the published resolver
unconditionally. This ensures that malicious or invalid index entries
cannot direct the agent to read files outside the feature directory,
and that legacy fallback paths receive the same symlink/ownership
validation as indexed paths.

Set `SKILL_DIR` to the canonical directory of this loaded skill file
(resolved from the path provided by the phase dispatcher or file-read
context, following symlinks). If the loaded file path is unavailable,
stop and report — do not fall back to `$HOME`, `BASH_SOURCE`, or the
current working directory:

```bash
# SKILL_DIR: set by the agent to this skill file's canonical directory
VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../../design/scripts/validation_index.py")" || { echo "Cannot resolve ../../design/scripts/validation_index.py" >&2; exit 1; }
```

If a `validation-index.json` exists in the source feature directory,
run `python3 "$VALIDATION_INDEX_SCRIPT" resolve --published
"{source-feature-directory}"` and use its returned validated artifact
list for all subsequent reading and filtering. If no
`validation-index.json` exists (legacy design), run the resolver on
the feature directory to validate the legacy `testplan.md` path
before reading it. Do not read or filter any artifact file that the
resolver has not validated.

**Artifact discovery (using validated resolver output):** Use the
resolver's returned artifact list to identify the published
validation artifact filenames and the primary testplan. For legacy
designs (no `validation-index.json`), the resolver validates and
returns the testplan path in its artifact list (e.g.,
`[{file: "testplan.md", type: "testplan"}]`). An empty resolver
result (`[]`) means no valid artifacts were found — route through
the existing no-source outcome rather than reading unvalidated paths.

**Filter across all validation artifacts:** For each validation
artifact file discovered above, apply the TC matching rules below.
Collect matching TCs from ALL artifacts (primary testplan and any
companions).

The Jira story's description contains a `Validated by` line in its
Design Reference section (captured in Step 3) listing TC IDs, and a
`PRD Requirements` line listing requirement IDs.

For `[QE]` stories, `Validated by` may not carry the full set of
relevant TCs — `/decompose` assigns TCs via IC overlap, but `[QE]`
stories typically don't implement ICs (they test the surface that
`[DEV]` stories implement). To ensure complete coverage, always
**union** the `Validated by` TC IDs with requirement-heading matches
across all validation artifacts: extract PRD requirement IDs from the
story's `PRD Requirements` line and collect all test cases whose
requirement heading matches, then merge with the `Validated by` set
(deduplicate).

For non-`[QE]` stories, use `Validated by` TC IDs directly. If the
`Validated by` line is missing, empty, or contains no TC IDs (e.g.,
`Validated by: None — ...`), fall back to requirement-heading
matching as above.

**Extract relevant gates (before TC outcome).** If any feature-level
validation artifact (primary or companion) has a
`## Review and Qualification Gates` section, check each gate's
requirement and IC mappings against the story's `PRD Requirements`
and `Interface Changes`. Gates whose requirements or ICs overlap are
relevant to this story. Collect all relevant gates with their source
path, gate heading/name, mapped requirements and ICs, type,
Required Evidence (copy verbatim from the source gate's Required
Evidence column; if missing, set to "criteria not specified in
source — clarification needed"), and reviewer/owner. If a gate
lacks a requirement mapping, IC mapping, or type, retain the gate
with the missing field set to "not specified in source —
clarification needed" and record the source origin. Do not silently
drop gates with incomplete mappings or fabricate mappings. For
TC-based gates, also copy the TC's Expected Results as evidence
criteria. This extraction runs BEFORE the outcome table below — a
story with zero TCs but relevant gates still produces a retained
validation artifact.

**Outcome gate:**

| Outcome | Condition | Action |
|---------|-----------|--------|
| **Normal** | Matching test cases found (in any artifact) | Write `.artifacts/e2e/{issue-key}/testplan.md` |
| **Gate-only** | Zero TC matches but relevant gates found | Write `testplan.md` with only the `## Qualification Gates` section (no TC sections). This is not an error — the story's validation is gate-based. |
| **Expected zero** | No TC matches, no relevant gates, AND story type is `[DOCS]`, `[UX]`, or `[CI]` | Note in context. |
| **Anomalous zero** | No TC matches, no relevant gates, AND story type is `[QE]`, `[DEV]`, or `[UI]` | Warn the user. This is non-blocking. |

If the story type prefix is not listed above, treat it as anomalous
zero (warn the user, continue without `testplan.md`).

**Validate the published index before selecting an outcome.** The
resolver was already invoked at the start of this step. If the
resolver returned a validated artifact list, use that list as
authoritative. Do not re-read the raw index or fall back to
unvalidated paths.

**Resolution failure handling.** If the index is present but
malformed, contains an empty artifacts list, the source location or
any discovered validation artifact cannot be resolved or read, or
the resolve command exits non-zero, the source is unresolvable:
- If a prior story-scoped testplan exists, retain it and mark it
  `Freshness: unverified`. Additionally, record
  `Source-Discovery: unresolved` to distinguish plan freshness from
  source discovery status. Do not overwrite prior evidence.
  Source discovery is separate from plan freshness: a user may confirm
  retained TCs (clearing unverified concerns) but unresolved discovery
  means the source inspection itself failed — new TCs, gates, or
  requirements may exist that were not discovered. Unresolved discovery
  blocks `Overall: PASS` in validation even if retained TCs are
  user-confirmed, because undiscovered required gates cannot be
  accounted for.
- If no prior story-scoped testplan exists, write a minimal marker
  to `.artifacts/e2e/{issue-key}/testplan.md`:
  ```
  # Story Test Plan — {issue-key}
  Freshness: unresolved-source
  Source-Discovery: unresolved
  Source: could not be read or resolved
  ```
  This marker is distinct from confirmed absence (expected zero) or
  a verified empty set. Downstream validation must report this state
  as unresolved discovery, not as confirmed absence or full coverage.
  A successful subsequent ingest that checks the source clears both
  the Freshness and Source-Discovery markers by writing the normal
  testplan or deleting it for expected
  zero outcomes.
- Report that the source could not be checked. Skip the outcome
  gate and story testplan write below. AC-based work may continue,
  but unresolved required validation cannot be claimed as complete.

A present but invalid index is distinct from an absent index: do
not fall back to legacy `testplan.md` discovery when a
`validation-index.json` exists but fails validation. Failed script
resolution or index validation is not confirmed absence.

For valid-source filtered-zero outcomes (expected zero or anomalous
zero where the source was successfully read and no TCs or gates
matched the story's scope): first, verify that every gate's
relevance was established. A gate's relevance requires checking
both its requirement mappings and IC mappings against the story's
scope:
- If either dimension (requirement or IC) shows known overlap with
  the story's scope, the gate is relevant regardless of the other
  dimension's status.
- If both dimensions are fully known and neither overlaps the
  story's scope, the gate is irrelevant.
- If any dimension needed to determine overlap is missing or marked
  "clarification needed", and known dimensions do not already
  establish overlap, the gate has unknown relevance — its
  applicability cannot be confirmed or denied.

Preserve origins and known mappings: do not invent mappings for
unknown dimensions or treat all unknown-relevance gates as
mandatory for every AC. Explicit known non-overlap (fully known on
both dimensions) establishes irrelevance without clarification.

If any gate has unknown relevance, the outcome is not a confirmed
zero. In that case:
- If a prior story testplan exists, retain it with
  `Freshness: unverified` and request clarification on the unmapped
  gate's applicability in the ingest handoff rather than deleting
  evidence whose relevance could not be assessed.
- If no prior story testplan exists (first ingest), record
  `Gate-Applicability: unresolved` with the affected gate names in
  the Story Test Plan section of `01-context.md`. Do not write a
  testplan for gates whose relevance is unknown. Request
  clarification in the ingest handoff.

In both cases, update the `gate-applicability.pending` file in the
artifact directory
(`.artifacts/e2e/{issue-key}/gate-applicability.pending`). If the
file already exists, read it first and preserve its existing
entries — a gate absent from the latest artifact set is not
verified irrelevant, and newly unresolved gates must not overwrite
previously recorded ones. Merge newly unresolved gates by origin and name — when that pair
unambiguously identifies the same source gate, merge the entries.
Preserve each entry's origin, name, and status. If distinct gates
share both origin and name, retain separate entries and request
clarification in the existing handoff; keep the blocker until
every such gate is resolved. Remove an entry only through the
allowed checked clearing
procedure (re-ingestion with gate recording and plan
reconciliation, or verified irrelevance). Write the merged result
immediately during gate analysis, before Step 8 compilation — it
is not subject to Step 8a approval and persists even if a
re-invocation overwrite is declined. Also include the
`Gate-Applicability: unresolved` marker in the compiled
`01-context.md` content (Step 8) for human readability, but the
pending file is the authoritative blocker checked by `/validate`
and `/publish`.

This marker is distinct from `Source-Discovery: unresolved` (which
records that the source itself could not be read).

**Clearing `gate-applicability.pending`** requires one of:
- **Re-ingestion with resolved gates:** A completed `/ingest` run
  where all previously unresolved gates have known relevance. Gates
  confirmed relevant must be recorded with their original
  mappings, origin, and evidence in the story testplan
  (`testplan.md`). If a downstream plan (`02-plan.md`) exists, its
  approval/update contract must be reconciled before clearing — the
  plan must acknowledge the newly recorded gates. If no downstream
  plan exists yet, the pending file is still removed after testplan
  recording so that a subsequent `/plan` consumes the recorded
  gates from the testplan.
- **Verified irrelevance:** Explicit clarification establishing
  that a specific gate is irrelevant (fully known non-overlap on
  both requirement and IC dimensions). Verified irrelevance clears
  only that gate's contribution to the pending state — if other
  gates remain unresolved, the pending file persists with the
  remaining gate names. Irrelevance does not fabricate a gate or
  TC obligation.

**Does NOT clear the pending file:** TC confirmation alone, partial
clarification that leaves any gate unresolved, a missing prior
testplan or downstream plan, failed or unreadable source discovery,
or declined context/plan changes (Step 8a declined).

**Legacy context marker synchronization.** The
`Gate-Applicability: unresolved` marker in `01-context.md` serves
as a validator fallback after the pending file is removed.
Clearing the pending file therefore also requires updating or
removing the legacy marker in `01-context.md` — but only when the
context overwrite has been approved (Step 8a accepted on
re-invocation, or first-invocation write). If the context
overwrite was declined or unanswered, the legacy marker in
`01-context.md` persists and the pending file must NOT be cleared,
because the validator fallback would no longer detect the blocker.
A re-invocation that resolves all gates must compile a new
`01-context.md` without the unresolved marker and obtain Step 8a
approval before removing the pending file.

**Deferred finalization.** Step 6 determines clearing eligibility
during gate analysis but does not perform the actual pending-file
removal or legacy-marker update. These operations are deferred to
the context write: Step 8 (first invocation) or Step 8a
(re-invocation, accepted branch). This ensures the context has
been written (or approved for overwrite) before the pending file
is removed, maintaining the validator fallback invariant. The
compiled `01-context.md` content should reflect the resolved gate
state (omitting the `Gate-Applicability: unresolved` marker when
all gates are resolved), but the pending file is not removed until
the context write succeeds.

Only after confirming that all gates have known relevance (or no
gates exist): if `.artifacts/e2e/{issue-key}/testplan.md` exists
from a prior ingest run, delete it. A stale story-scoped testplan
whose source was verified to contain no matching content would cause
downstream gates to enforce obsolete coverage requirements.

Source absence, resolution failure, or unreadable/invalid source
**never** authorizes deletion of a prior plan.

**Checked absence (resolver succeeds with no artifacts).** If the
source location was checked successfully (resolver exited zero) and
no validation artifacts were found (neither `validation-index.json`
nor `testplan.md` in the docs repo), this is checked absence — source
discovery succeeded but found nothing. If a story-level testplan
already exists from a prior ingest, retain it and mark it
`Freshness: unverified` but do NOT set `Source-Discovery: unresolved`
— the source was successfully checked, not unresolvable. If the
retained testplan already contains a `Source-Discovery: unresolved`
marker from an earlier failed ingest, remove it — the current
successful check supersedes the prior failure. The retained plan
keeps `Freshness: unverified` (the TCs are still unverified) but
source discovery is no longer unresolved. Emit a
warning: "Source testplan not found — retained story testplan marked
as unverified. `/plan` and `/validate` should treat its TC coverage
requirements as provisional until the upstream source is available."
If no prior testplan exists, note "No feature-level testplan
available" and continue. This is not an error — the testplan is a
newer feature and older designs may not have one.

**Resolution failure (distinct from checked absence).** If the
source location could not be checked (resolver exited non-zero,
source location was malformed, listed artifacts were missing or
unreadable, or the index was present but invalid), retain any
existing prior story testplan as unverified. Mark it
`Freshness: unverified` AND `Source-Discovery: unresolved` and emit
a warning including the failure reason. The `Source-Discovery:
unresolved` marker is appropriate here because the inspection itself
failed — new TCs, gates, or requirements may exist that were not
discovered.

When writing the story testplan from matches across multiple artifacts,
include all matched TCs in a single `testplan.md` with a Source line
listing each contributing artifact. Include a `## Qualification Gates`
section for any relevant gates found above.

**Per-TC verification classification:** Classify each matched TC
by its verification method, regardless of source artifact:

- **`Automation: automated`** — candidate for e2e test automation.
  These are the default and require automated test scenarios.
- **`Automation: manual`** — requires human verification (visual
  checks, exploratory testing, UX evaluation). Listed in the story
  testplan with a `[Manual verification]` marker. The `/plan` and
  `/code` phases must not generate automated e2e test code for
  these; `/validate` tracks them as manual verification evidence.
- **`Qualification gate`** — requires a specialized execution
  environment (hardware device lab, security audit tooling,
  cross-service staging not available in CI). Listed with a
  `[Qualification gate]` marker. The `/plan` and `/code` phases
  must not generate automated e2e test code for these; `/validate`
  tracks them as external validation evidence.

When a matched TC comes from a companion artifact (type
`"companion"` in the published index), additionally note its
source artifact and purpose in the story testplan metadata.

**Write story-scoped testplan (Normal outcome only):**

Write `.artifacts/e2e/{issue-key}/testplan.md`:

```markdown
# Story Test Plan — {issue-key}

- **Source:** {comma-separated list of contributing source files}
- **Story:** {issue-key} — {story-title}
- **Test cases:** {count of automatable + manual TCs}
- **Manual verification:** {count or 0}
- **Qualification gates:** {count or 0}

## TC-FR1-01: {scenario title}

| Requirement | Interface Change | Priority | Automation | Source |
|-------------|-----------------|----------|------------|--------|
| FR-1 | IC-1 | high | automated | testplan.md |

### Preconditions

- {precondition}

### Steps

1. {step}
2. {step}

### Expected Results

- {expected outcome}

## TC-FR1-02: {scenario title}

{... same structure for each automatable test case ...}

## TC-NFR3-01: {scenario title} [Qualification gate]

| Requirement | Interface Change | Priority | Verification |
|-------------|-----------------|----------|--------------|
| NFR-3 | IC-5 | high | hardware device lab |

- **Source artifact:** {hw-validation.md or testplan.md}
- **Designated environment:** {e.g., hardware device lab}
- **Required evidence:** {e.g., device test report}
- **Evidence status:** not-started

{Qualification-gate TCs use the [Qualification gate] heading suffix
 and a Verification column instead of Automation. Evidence status
 values: not-started, pending, verified, failed. Include one section
 per qualification-gate TC.}

## Qualification Gates

{Non-TC qualification gates from the source testplan. Include this
 section when the source contains gates that are not individual test
 cases — cross-cutting validation requirements such as hardware
 certification or security audit. For gate-only plans (zero TC
 sections), this is the only content section. For mixed plans, this
 section follows the TC sections. Omit entirely when no non-TC
 qualification gates apply.}

| Gate | Requirement | Interface Changes | Source | Type | Required Evidence | Reviewer | Status |
|------|-------------|-------------------|--------|------|-------------------|----------|--------|
| {gate-heading} | {req-id} | {IC IDs from source or "not specified in source — clarification needed"} | {source-file} | {gate-type} | {evidence} | {reviewer or "unassigned"} | not-started |
```

Each test case becomes an H2 heading with the same structure as the
feature-level testplan (metadata table, Preconditions, Steps, Expected
Results as sub-headings). Heading levels are shifted up by two because
the requirement-grouping layer and the Test Cases section are removed.
The Requirement ID and Interface Change are included in the metadata
table for traceability back to the feature-level testplan.

### Step 7: Explore E2E Test Infrastructure

This is the core discovery step. Unlike implementation ingestion, which
explores production code, this step focuses on the project's e2e testing
infrastructure. Thorough discovery here is critical — shallow exploration
leads to tests that don't follow project patterns.

#### 7a: Project Configuration

Read project-level configuration:
- `AGENTS.md`, `CLAUDE.md` — project conventions and AI guidance
- Makefile or equivalent — build, test, lint commands
- CI/CD workflows (e.g., `.github/workflows/`) — what checks run on PRs
- `CONTRIBUTING.md` — PR and commit message conventions
- `.github/PULL_REQUEST_TEMPLATE.md` — PR description template

#### 7b: Repository Topology

Determine whether the local clone is a fork or a direct clone. Parse
`{owner}/{repo}` from the origin remote:

```bash
git remote get-url origin
```

Then query GitHub:

```bash
gh repo view {owner}/{repo} --json isFork,parent
```

- If `isFork` is `true`, record the upstream repo from `parent.owner.login`
  and `parent.name`
- If `isFork` is `false`, record it as a direct clone
- If the command fails (no network, no `gh` auth), note the failure and
  ask the user whether this is a fork. If the user confirms it is a fork,
  also ask for the upstream `{owner}/{repo}` so the Repository Topology
  section is complete for downstream sync steps

#### 7c: E2E Test Framework and Runner

Discover the testing framework and how tests are executed:

1. **Framework:** Search test files for import statements to identify the
   framework (e.g., Ginkgo, pytest, Playwright, Cypress, Jest)
2. **Runner:** Check the Makefile or scripts for e2e test execution targets
3. **Scoping:** How can tests be run for a specific suite or directory?
   (e.g., `GO_E2E_DIRS=`, `--spec`, `--testPathPattern`)
4. **Filtering:** What label/tag/focus mechanisms exist for CI selection?
5. **Parallel execution:** Does the project support parallel test execution?

#### 7d: Test Organization

Map the e2e test directory structure:

1. **Root directory:** Where do e2e tests live? (e.g., `test/e2e/`)
2. **Suite organization:** How are suites structured? (one directory per
   feature area, flat files, nested by component)
3. **Suite file conventions:** What files does each suite contain?
   (e.g., `*_suite_test.go` + `*_test.go` in Go/Ginkgo)
4. **Naming conventions:** How are test files and directories named?

#### 7e: Test Infrastructure Abstractions

Discover what abstractions the project uses for test code to interact
with the system under test. Projects vary widely — look for whichever
of these the project uses (it may use one, several, or none):

- **Harness object:** A central test API object (e.g., `test/harness/`)
- **Fixtures:** Framework-provided setup mechanisms (e.g., pytest
  fixtures, Playwright fixtures)
- **Page objects:** UI interaction abstractions (e.g., Playwright/Cypress
  page object models)
- **Helper modules:** Standalone utility functions or classes for test
  setup and interaction

For whatever the project uses:

1. **Location:** Where do the test infrastructure source files live?
2. **Initialization:** How do tests obtain access? (global variable,
   dependency injection, fixture parameter, constructor, import)
3. **Key methods:** Catalog the public methods relevant to the story's
   scope — include their full signatures (parameters and return types),
   not just names. Focus on methods the test scenarios will need — don't
   catalog the entire API.
4. **Domain-specific files:** Some projects split test infrastructure by
   domain. Identify which files are relevant to the story.

If the project has no dedicated test infrastructure abstractions (tests
interact with the system directly), note that — this is a valid pattern.

#### 7f: Test Lifecycle

Read 2-3 existing suite/test files to understand lifecycle patterns.
Use whatever terminology the project's framework uses — common patterns
include:

1. **Suite-level setup** (e.g., BeforeSuite, setup_module, beforeAll):
   What happens once per suite? (services, providers, initialization)
2. **Per-test setup** (e.g., BeforeEach, setup_method, beforeEach):
   What happens before each test? (login, reset, context creation)
3. **Per-test teardown** (e.g., AfterEach, teardown_method, afterEach):
   What happens after each test? (log collection, resource cleanup)
4. **Suite-level teardown** (e.g., AfterSuite, teardown_module, afterAll):
   What happens after all tests? (service cleanup)

Record the actual hook names the project uses — downstream phases will
use these names, not generic placeholders.

Also discover the **parallelism model** — if tests can run in parallel:

1. **Mechanism:** How is parallelism achieved? (framework-native workers,
   test sharding, process-level parallelism)
2. **Isolation strategy:** How do parallel workers avoid interfering?
   (per-worker resources, shared resource pool allocation, unique naming
   with worker IDs, separate databases, snapshot revert)
3. **Lifecycle interaction:** How do lifecycle hooks relate to
   parallelism? In particular: does suite-level setup run once
   globally or once per worker? This affects how the suite file
   must be structured.

If tests run sequentially or parallelism is not documented, note that.

#### 7g: Auxiliary Services

If the project manages external services for e2e tests, discover them.
Not all projects do this — some test against pre-deployed environments
or let the framework handle service lifecycle internally.

If the project does manage test services:

1. **Services used:** Registry, git server, database, identity provider,
   metrics collector, tracing, etc.
2. **How started:** Testcontainers, make targets, docker-compose, manual
3. **How accessed:** Helper functions, environment variables, test
   infrastructure methods
4. **Singleton vs. per-suite:** Are services shared across suites?

If no auxiliary service management is found, note "Tests run against a
pre-existing environment" or whatever the actual pattern is.

#### 7h: Test Utilities

Find test helper packages:

1. **Utility packages:** Common helpers (e.g., `test/util/`)
2. **Constants:** Timeouts, polling intervals, resource type strings
3. **Tracing/logging:** How tests set up observability
4. **Test data:** Where test fixtures and example files live

#### 7i: Test Conventions and Documentation

Read test-specific documentation:

1. **Test READMEs:** `test/README.md`, `test/e2e/README.md`
2. **Test AGENTS.md:** `test/AGENTS.md`, `test/e2e/AGENTS.md`
3. **Test guidelines:** `test/e2e/GUIDELINES.md` or similar
4. **Lint rules:** Any test-specific lint rules (e.g., import restrictions)
5. **Label conventions:** How labels/tags are used for CI filtering

If these files don't exist, note their absence — the project may document
test conventions elsewhere (in the main AGENTS.md) or not at all.

#### 7j: Reference Suite Selection

Based on the story's scope, identify the 1-2 existing test suites most
similar to what needs to be written:

1. Match by feature area (e.g., if the story tests rollout behavior, find
   the existing rollout suite)
2. If no exact match, find a suite that uses similar test infrastructure
   methods or tests similar interaction patterns
3. Read the selected suite thoroughly: suite file + 1-2 test files
4. Extract concrete patterns: imports, setup, assertions, labels, helpers
5. **Extract a lifecycle skeleton:** Create a sanitized copy of the
   reference suite's lifecycle structure. This skeleton goes into the
   context document and gives `/code` a copy-paste starting point for
   the new suite file.

   **Keep:** hook declarations, framework registration calls,
   infrastructure initialization calls (e.g., harness setup, fixture
   creation), cleanup/teardown calls, worker or parallelism setup,
   and the structural nesting of test blocks.

   **Strip:** specific assertions, business-logic conditionals,
   hardcoded resource names and test data, and inline comments that
   reference story-specific details.

   Replace stripped content with brief comments describing what
   happens at that point (e.g., `// create test resources`,
   `// verify expected state`).

These suites become the "pattern source" for the `/code` phase.

Use file search (glob), content search (grep), and targeted file reading.
Focus exploration on the test infrastructure files. Apply the convergence
heuristic per discovery area (Steps 7c–7j), not across the entire
exploration: within each area, if the last 5-7 files explored introduced
no new patterns, that area is likely complete. E2e infrastructure spans
a broad surface (test infrastructure files, auxiliary configs, suite files, utilities,
CI workflows, test documentation), so premature convergence can miss
critical patterns.

### Step 8: Compile Context

> **Checkpoint:** Step 7 is the heaviest phase of ingestion (10 sub-steps
> across test infrastructure, services, utilities, conventions, and reference suites).
> Before compiling, verify that all Step 7 sub-steps have been completed
> and that key findings are captured. If working in a constrained context,
> consider spawning a subagent for the compilation.

Compile all findings into the structure below. If this is a re-invocation
(Step 2a found an existing file), **do not write the file yet** — hold the
compiled content and proceed to Step 8a first.

If this is a first invocation, write
`.artifacts/e2e/{issue-key}/01-context.md` with this structure:

```markdown
# Story Context — {issue-key}

## Story Summary

- **Title:** {title}
- **Type:** [QE]
- **Jira:** {issue-key}
- **Epic:** {parent epic key and title}
- **Feature:** {parent feature key, if known}

### User Story

{As a... I want... So that...}

### Acceptance Criteria

{Numbered list, preserving original wording}

### Testing Approach

{From the story or design document. This is the primary guidance for [QE]
 stories — it describes what e2e scenarios should be covered.
 If none: "No testing approach provided — derive scenarios from acceptance
 criteria."}

### Implementation Guidance

{From the story or design document. May be sparse for [QE] stories.
 If none: "No implementation guidance provided."}

### Dependencies

| Story | Type | Status | Merged | Risk |
|-------|------|--------|--------|------|
| {key} | {[DEV]/[UI]/etc.} | {jira status} | {yes/no} | {brief risk note} |

{If no dependencies: "No story dependencies."
 If [DEV] dependencies are unmerged: highlight that the feature under test
 may not exist yet.}

## Design Context

### Relevant Design Sections

{Summary of design document sections relevant to the feature being tested,
 with section references (e.g., [Design: §4.1]). Focus on the behavior
 being tested, not implementation details.}

### PRD Requirements Covered

{Which FR-N and NFR-N requirements this story's tests will validate.}

### Story Test Plan

{If story-scoped testplan was written: "Story-scoped test plan written
 to `.artifacts/e2e/{issue-key}/testplan.md` with {N} test cases
 covering requirements {FR-1, FR-3, NFR-2}.
 TC IDs: {comma-separated list}."

 If feature-level testplan exists but no matches (expected):
 "Feature-level testplan found in docs repo but no test cases match
 this {story-type} story's requirements (expected). No story-scoped
 testplan written."

 If feature-level testplan exists but no matches (anomalous):
 "Feature-level testplan found in docs repo but no test cases match
 this {story-type} story's requirements (anomalous — flagged during
 ingest). No story-scoped testplan written."

 If no feature-level testplan in docs repo: "No feature-level testplan
 available in docs repo. No story-scoped testplan written."

 If any gate has unknown applicability (append to whichever case
 above applies): "Gate-Applicability: unresolved — gates
 {gate-names} have unknown relevance to this story. Clarification
 needed before validation can confirm coverage completeness."}

## E2E Test Infrastructure

### Framework
- **Framework:** {e.g., Ginkgo v2 + Gomega, Playwright, pytest, Cypress, Jest}
- **Runner:** {e.g., ginkgo CLI, playwright test, pytest, npx cypress}
- **Test location:** {e.g., test/e2e/}
- **Suite organization:** {e.g., one directory per feature area, flat files}

### Test Execution
- **Run all e2e tests:** `{command}`
- **Run specific suite:** `{command with scoping}`
- **Filter by label/tag:** `{mechanism}`
- **Filter by name/description:** `{mechanism}`
- **Parallel execution:** `{command flag or mechanism, if supported}`
- **Environment assumptions:** {what must be running before tests execute}

### Test Infrastructure

{Describe what abstractions the project uses. Include whichever of the
 following the project actually has — omit sections that don't apply:}

- **Type:** {harness object / fixtures / page objects / helper modules / none}
- **Location:** {path(s) to test infrastructure files}
- **Initialization:** {how tests obtain access}
- **Key methods for this story:**

| Method | Parameters / Return | Purpose | Source File |
|--------|---------------------|---------|-------------|
| `{method}` | `{params and return types}` | {what it does} | {file} |

{If no dedicated test infrastructure: "Tests interact with the system
 directly — no harness, fixtures, or page objects."}

### Test Lifecycle

{Use the actual hook names from the project's framework:}

- **Suite-level setup** ({discovered hook name}): {what happens}
- **Per-test setup** ({discovered hook name}): {what happens}
- **Per-test teardown** ({discovered hook name}): {what happens}
- **Suite-level teardown** ({discovered hook name}): {what happens}

### Parallelism Model

{If the project supports parallel test execution:}

- **Supported:** {yes/no}
- **Mechanism:** {e.g., framework-native workers, test sharding, process-level}
- **Isolation strategy:** {how parallel workers avoid interfering — e.g.,
  per-worker resources, shared resource pool allocation, unique naming,
  separate databases}
- **Lifecycle interaction:** {how lifecycle hooks relate to parallelism —
  e.g., "suite setup runs once per worker, not once globally"}

{If parallelism is not supported or tests run sequentially: "Tests run
 sequentially. No parallel execution model."}

### Auxiliary Services

{If the project manages external services for tests:}

| Service | How Started | How Accessed | Required By |
|---------|-------------|-------------|-------------|
| {name} | {mechanism} | {how tests access it} | {which tests} |

{If tests run against a pre-existing environment or no auxiliary service
 management exists: "Tests run against {describe environment}. No
 test-managed auxiliary services."}

### Test Utilities
- **Constants:** {path, key constants}
- **Helpers:** {path(s), key functions}
- **Tracing:** {how tests set up tracing}
- **Test data:** {where fixtures live}

### Conventions
- **Labels/tags:** {convention for CI-filtering labels or tags}
- **File naming:** {convention for test files}
- **Test naming:** {convention for test grouping and naming}
- **Lint rules:** {test-specific lint rules, if any}
- **Documentation:** {test docs locations}

### Reference Suite

#### {Suite Name} — `{path}`

**Why selected:** {what makes this suite similar to the planned tests}

**Patterns to follow:**
- **Imports:** {import pattern from the suite file}
- **Setup:** {lifecycle hook pattern, using the project's actual hook names}
- **Assertions:** {assertion style, including any async/polling patterns}
- **Labels:** {how labels/tags are applied}
- **Cleanup:** {teardown pattern}
- **Key code pattern:** {any distinctive pattern worth replicating}

**Lifecycle skeleton:**

{Sanitized skeleton of the reference suite's lifecycle — hook ordering,
 infrastructure initialization, parallelism integration, cleanup. Include
 the suite entry point, all lifecycle hooks, and a representative test
 block. Apply the keep/strip rules from Step 7j.}

```{language — use the project's language, e.g., go, python, typescript}
{skeleton code here — actual hook names, actual method calls,
 with domain-specific logic replaced per the keep/strip rules
 in Step 7j}
```

## Repository Topology

- **Origin:** {owner}/{repo}
- **Type:** Fork | Direct
- **Upstream:** {upstream-owner}/{upstream-repo} (fork only, omit if direct)

## Validation Profile

### Commit Format
- **Pattern:** {discovered pattern}
- **Discovered from:** {source file}

### Pre-PR Checks (ordered)
{Numbered list of commands to run before creating a PR, discovered from
 Makefile, CI workflows, AGENTS.md. Focus on checks relevant to test code:}
1. `{lint command}` — {purpose}
2. `{e2e test command scoped to new suite}` — {purpose}

### PR Conventions
- **Title format:** {discovered format}
- **PR template:** {path or "None — use default template"}
- **Description guidance:** {any expectations from CONTRIBUTING.md or AGENTS.md}

### E2E Test Execution
- **Run new suite:** `{command scoped to the new test directory}`
- **Scoping mechanism:** `{how to restrict execution, e.g., GO_E2E_DIRS=}`
- **Environment assumptions:** {what must be running}

### Discovered from
{List of files read to build the validation profile and infrastructure context}

## Open Questions

{Questions that need answers before or during test planning. Each entry
 must be a concrete question — not an observation, concern, or statement
 of fact. Ask what needs to be decided, not what you noticed.

 Good: "Should the fleet rollback e2e tests enroll a real VM, or use
 the device simulator? The existing rollout suite uses real VMs but the
 agent suite uses both patterns."

 Bad: "Need to figure out the VM approach." (too vague)

 Bad: "The test infrastructure supports both VMs and simulators."
 (observation, not a question)}
```

**Pending finalization (first invocation).** After writing
`01-context.md`, if Step 6 determined that all previously
unresolved gates now have a known disposition and the clearing
conditions are met for each gate, remove
`gate-applicability.pending`:
- **Relevant gates** must be recorded in the story testplan with
  original mappings, origin, and evidence; and either no downstream
  plan (`02-plan.md`) exists or the plan acknowledges the newly
  recorded gates.
- **Verified-irrelevant gates** (explicit gate-specific proof of
  fully known non-overlap on both requirement and IC dimensions)
  are cleared without testplan recording or gate obligation.
  All-irrelevant outcomes (every gate verified irrelevant, including
  zero-match / no story testplan) satisfy the clearing condition.

Before removing the pending file, the written `01-context.md` must
not contain the `Gate-Applicability: unresolved` marker. If
clearing conditions are not met (source discovery failed, some
gates remain unresolved, downstream plan reconciliation is
incomplete, or any gate lacks a verified disposition), retain the
pending file and the marker in the written context.

### Step 8a: Diff Against Prior Ingest (Re-invocation Only)

If Step 2a created a `.prev` file, compare `01-context.md.prev` against
the newly compiled content. Focus the diff on:

- Changes to acceptance criteria or testing approach
- Changes to dependency status (have [DEV] stories been merged since last ingest?)
- New test infrastructure methods or patterns discovered
- Changes to the validation profile or test execution commands
- Changes to the reference suite selection

Then check whether downstream artifacts exist (`02-plan.md`,
`03-test-report.md`, `04-impl-report.md`, etc.). If they do, tell the user
which artifacts exist and may be affected by the changes.

Wait for the user to confirm before proceeding. If the user
confirms, write the compiled content to `01-context.md` and clean
up the `.prev` file. Apply the same pending finalization as
Step 8: if Step 6 determined clearing eligibility and all
conditions are met for each gate (relevant gates recorded with
original mappings/origin/evidence and downstream plan reconciled;
verified-irrelevant gates cleared without testplan recording or
gate obligation — including all-irrelevant outcomes), remove
`gate-applicability.pending`. Before removing the pending file, the
written `01-context.md` must not contain the
`Gate-Applicability: unresolved` marker. If the user declined or
did not answer the overwrite, do not clear the pending file — the
legacy marker in the existing `01-context.md` must persist so the
validator fallback continues to detect the blocker.

### Step 9: Report to User

Present a brief summary:
- Story scope and acceptance criteria
- Design and PRD context loaded (or what was missing)
- Dependency status — especially whether `[DEV]` stories are merged
- E2E test infrastructure discovered (framework, test abstractions, reference suite)
- Validation profile discovered (how to run tests)
- Open questions (if any) — frame these as items that `/plan` will
  investigate, not as blockers. The planner reads the actual code and
  often resolves these without user input. Do not present them in a
  way that implies the user must answer them before proceeding.
- Whether the context is sufficient to proceed to `/plan`

If the user declined a re-invocation overwrite in Step 8a, report instead
what changes were found and that the existing context was preserved.

## Output

- `.artifacts/e2e/{issue-key}/01-context.md`
- `.artifacts/e2e/{issue-key}/testplan.md` (if testplan exists with matching test cases)
- `.artifacts/e2e/{issue-key}/gate-applicability.pending` (if any gate has unresolved applicability)

## When This Phase Is Done

Report your findings:
- Story scope and key acceptance criteria
- Dependency status ([DEV] stories merged or not)
- E2E infrastructure discovered (framework, test abstractions, reference suite)
- Validation profile summary
- Story test plan status (test cases found / expected zero / anomalous zero / no testplan)
- Assessment of readiness for `/plan`

Then return to the invoking workflow router for completion guidance.
