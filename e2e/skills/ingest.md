---
name: ingest
description: Fetch the [QE] story, verify dependencies, explore e2e test infrastructure, and build a test-execution profile.
---

# Ingest Story Context Skill

You are a principal QE engineer. Your job is to fetch the [QE] story, verify
that the features under test have been implemented and merged, explore the
project's e2e testing infrastructure in depth, and produce a structured
context document that will inform the test planning phase.

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
- **Re-invocation diffs before overwriting.** If `01-context.md` already exists, preserve it before exploring. After compiling new context, diff against the previous version and present changes to the user before overwriting (see Steps 2a and 7a).

## Process

### Step 1: Identify the Story

The user will provide one of:
- A Jira issue key or URL (fetch via Jira MCP)
- A path to an existing story file from the design workflow

Extract the Jira key (e.g., `EDM-5678`) and set it as the context identifier.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/e2e/{jira-key}
```

Verify that `.artifacts/` is covered by the project's `.gitignore`. If it
is not, warn the user that e2e artifacts could be accidentally committed
with the code.

### Step 2a: Check for Prior Ingest

If `.artifacts/e2e/{jira-key}/01-context.md` already exists, this is a
re-invocation. Copy the existing file to `01-context.md.prev` so it is
preserved for the diff in Step 7a.

### Step 3: Fetch the Jira Story

Fetch the story from Jira. Capture:
- Summary and description
- User story (As a... I want... So that...)
- Acceptance criteria
- Testing approach (if present — this is the primary implementation guidance for [QE] stories)
- Implementation guidance (if present — may be sparse for [QE] stories)
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
   (Done, Closed, Resolved)
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

Check for an existing docs repo configuration at `.artifacts/prd/config.json`.
This config is project-level and shared across workflows (prd, design,
implement, e2e) — a prior workflow run may have already created it.

**If the config exists**, read it and validate:
1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository

If validation fails, inform the user and re-ask for the correct values.

**If the config does not exist**, ask the user:
- **Docs repo local path:** Where is the planning docs repo checked out?
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote get-url origin`
  and confirm with the user

Validate the path and remote, then save the config:

```bash
mkdir -p .artifacts/prd
```

Write `.artifacts/prd/config.json` with the validated `docs_repo_path` and
`docs_repo_remote` (same format used by the prd and design workflows).

#### 5b: Find the PRD and Design Document

The docs repo organizes documents by Feature-level Jira issue. To find the
right directory, walk the Jira hierarchy from the story:

1. The story (e.g., `EDM-5678`) has a parent **Epic** — fetch it from Jira
   to get the Epic key
2. The Epic has a parent **Feature** — fetch it from Jira to get the
   Feature key (e.g., `EDM-1100`)

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

If the docs repo documents are not found, ask the user for their location
or proceed with only the Jira story content. The design document and PRD
are valuable context but not strictly required — the story's acceptance
criteria are the primary contract.

### Step 6: Explore E2E Test Infrastructure

This is the core discovery step. Unlike implementation ingestion, which
explores production code, this step focuses on the project's e2e testing
infrastructure. Thorough discovery here is critical — shallow exploration
leads to tests that don't follow project patterns.

#### 6a: Project Configuration

Read project-level configuration:
- `AGENTS.md`, `CLAUDE.md` — project conventions and AI guidance
- Makefile or equivalent — build, test, lint commands
- CI/CD workflows (e.g., `.github/workflows/`) — what checks run on PRs
- `CONTRIBUTING.md` — PR and commit message conventions
- `.github/PULL_REQUEST_TEMPLATE.md` — PR description template

#### 6b: Repository Topology

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

#### 6c: E2E Test Framework and Runner

Discover the testing framework and how tests are executed:

1. **Framework:** Search test files for import statements to identify the
   framework (e.g., Ginkgo, pytest, Playwright, Cypress, Jest)
2. **Runner:** Check the Makefile or scripts for e2e test execution targets
3. **Scoping:** How can tests be run for a specific suite or directory?
   (e.g., `GO_E2E_DIRS=`, `--spec`, `--testPathPattern`)
4. **Filtering:** What label/tag/focus mechanisms exist for CI selection?
5. **Parallel execution:** Does the project support parallel test execution?

#### 6d: Test Organization

Map the e2e test directory structure:

1. **Root directory:** Where do e2e tests live? (e.g., `test/e2e/`)
2. **Suite organization:** How are suites structured? (one directory per
   feature area, flat files, nested by component)
3. **Suite file conventions:** What files does each suite contain?
   (e.g., `*_suite_test.go` + `*_test.go` in Go/Ginkgo)
4. **Naming conventions:** How are test files and directories named?

#### 6e: Test Infrastructure Abstractions

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
   scope. Focus on methods the test scenarios will need — don't catalog
   the entire API.
4. **Domain-specific files:** Some projects split test infrastructure by
   domain. Identify which files are relevant to the story.

If the project has no dedicated test infrastructure abstractions (tests
interact with the system directly), note that — this is a valid pattern.

#### 6f: Test Lifecycle

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

#### 6g: Auxiliary Services

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

#### 6h: Test Utilities

Find test helper packages:

1. **Utility packages:** Common helpers (e.g., `test/util/`)
2. **Constants:** Timeouts, polling intervals, resource type strings
3. **Tracing/logging:** How tests set up observability
4. **Test data:** Where test fixtures and example files live

#### 6i: Test Conventions and Documentation

Read test-specific documentation:

1. **Test READMEs:** `test/README.md`, `test/e2e/README.md`
2. **Test AGENTS.md:** `test/AGENTS.md`, `test/e2e/AGENTS.md`
3. **Test guidelines:** `test/e2e/GUIDELINES.md` or similar
4. **Lint rules:** Any test-specific lint rules (e.g., import restrictions)
5. **Label conventions:** How labels/tags are used for CI filtering

If these files don't exist, note their absence — the project may document
test conventions elsewhere (in the main AGENTS.md) or not at all.

#### 6j: Reference Suite Selection

Based on the story's scope, identify the 1-2 existing test suites most
similar to what needs to be written:

1. Match by feature area (e.g., if the story tests rollout behavior, find
   the existing rollout suite)
2. If no exact match, find a suite that uses similar test infrastructure
   methods or tests similar interaction patterns
3. Read the selected suite thoroughly: suite file + 1-2 test files
4. Extract concrete patterns: imports, setup, assertions, labels, helpers

These suites become the "pattern source" for the `/code` phase.

Use file search (glob), content search (grep), and targeted file reading.
Focus exploration on the test infrastructure files. Apply the convergence
heuristic per discovery area (Steps 6c–6j), not across the entire
exploration: within each area, if the last 5-7 files explored introduced
no new patterns, that area is likely complete. E2e infrastructure spans
a broad surface (test infrastructure files, auxiliary configs, suite files, utilities,
CI workflows, test documentation), so premature convergence can miss
critical patterns.

### Step 7: Compile Context

> **Checkpoint:** Step 6 is the heaviest phase of ingestion (10 sub-steps
> across test infrastructure, services, utilities, conventions, and reference suites).
> Before compiling, verify that all Step 6 sub-steps have been completed
> and that key findings are captured. If working in a constrained context,
> consider spawning a subagent for the compilation.

Compile all findings into the structure below. If this is a re-invocation
(Step 2a found an existing file), **do not write the file yet** — hold the
compiled content and proceed to Step 7a first.

If this is a first invocation, write
`.artifacts/e2e/{jira-key}/01-context.md` with this structure:

```markdown
# Story Context — {jira-key}

## Story Summary

- **Title:** {title}
- **Type:** [QE]
- **Jira:** {jira-key}
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
- **Parallel execution:** `{mechanism, if supported}`
- **Environment assumptions:** {what must be running before tests execute}

### Test Infrastructure

{Describe what abstractions the project uses. Include whichever of the
 following the project actually has — omit sections that don't apply:}

- **Type:** {harness object / fixtures / page objects / helper modules / none}
- **Location:** {path(s) to test infrastructure files}
- **Initialization:** {how tests obtain access}
- **Key methods for this story:**

| Method | Purpose | Source File |
|--------|---------|-------------|
| `{method}` | {what it does} | {file} |

{If no dedicated test infrastructure: "Tests interact with the system
 directly — no harness, fixtures, or page objects."}

### Test Lifecycle

{Use the actual hook names from the project's framework:}

- **Suite-level setup** ({discovered hook name}): {what happens}
- **Per-test setup** ({discovered hook name}): {what happens}
- **Per-test teardown** ({discovered hook name}): {what happens}
- **Suite-level teardown** ({discovered hook name}): {what happens}

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

### Step 7a: Diff Against Prior Ingest (Re-invocation Only)

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

Wait for the user to confirm before proceeding. If the user confirms, write
the compiled content to `01-context.md` and clean up the `.prev` file. If
the user declines, delete the `.prev` file and stop without overwriting.

### Step 8: Report to User

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

If the user declined a re-invocation overwrite in Step 7a, report instead
what changes were found and that the existing context was preserved.

## Output

- `.artifacts/e2e/{jira-key}/01-context.md`

## When This Phase Is Done

Report your findings:
- Story scope and key acceptance criteria
- Dependency status ([DEV] stories merged or not)
- E2E infrastructure discovered (framework, test abstractions, reference suite)
- Validation profile summary
- Assessment of readiness for `/plan`

Then **re-read the controller** (`controller.md`) for next-step guidance.
