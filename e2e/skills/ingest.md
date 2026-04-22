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
- **Deep infrastructure discovery.** Unlike implementation ingestion, e2e ingestion must thoroughly explore the test harness, auxiliary services, setup/teardown patterns, and test conventions. Shallow discovery leads to tests that don't follow project patterns.
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

#### 6e: Test Harness

Explore the test harness in depth — this is the API that test code uses:

1. **Location:** Find harness source files (e.g., `test/harness/e2e/`)
2. **Initialization:** How do tests obtain the harness? (global var,
   per-worker function, constructor)
3. **Key methods:** Read the harness files and catalog the public methods
   relevant to the story's scope. Focus on methods the test scenarios
   will need — don't catalog the entire harness.
4. **Domain-specific harness files:** Many projects split the harness by
   domain (e.g., `harness_device.go`, `harness_fleet.go`). Identify which
   domain files are relevant to the story.

#### 6f: Setup and Teardown Patterns

Read 2-3 existing suite files to understand lifecycle patterns:

1. **BeforeSuite / setup_module:** What happens once per suite?
   (auxiliary services, providers, harness initialization)
2. **BeforeEach / setup_method:** What happens before each test?
   (login, environment reset, test context creation)
3. **AfterEach / teardown_method:** What happens after each test?
   (log collection on failure, resource cleanup)
4. **AfterSuite / teardown_module:** What happens after all tests?
   (auxiliary service cleanup)

#### 6g: Auxiliary Services

Discover what external services tests depend on:

1. **Services used:** Registry, git server, database, identity provider,
   metrics collector, tracing, etc.
2. **How started:** Testcontainers (self-starting), make targets, manual
3. **How accessed:** Helper functions, environment variables, harness methods
4. **Singleton vs. per-suite:** Are services shared across suites?

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
2. If no exact match, find a suite that uses similar harness methods or
   tests similar interaction patterns
3. Read the selected suite thoroughly: suite file + 1-2 test files
4. Extract concrete patterns: imports, setup, assertions, labels, helpers

These suites become the "pattern source" for the `/code` phase.

Use file search (glob), content search (grep), and targeted file reading.
Focus exploration on the test infrastructure files. Apply the convergence
heuristic per discovery area (Steps 6c–6j), not across the entire
exploration: within each area, if the last 5-7 files explored introduced
no new patterns, that area is likely complete. E2e infrastructure spans
a broad surface (harness files, auxiliary configs, suite files, utilities,
CI workflows, test documentation), so premature convergence can miss
critical patterns.

### Step 7: Compile Context

> **Checkpoint:** Step 6 is the heaviest phase of ingestion (10 sub-steps
> across harness, services, utilities, conventions, and reference suites).
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
- **Framework:** {e.g., Ginkgo v2 + Gomega, Playwright, pytest}
- **Runner:** {e.g., ginkgo CLI, playwright test, pytest}
- **Test location:** {e.g., test/e2e/}
- **Suite organization:** {e.g., one directory per feature area}

### Test Execution
- **Run all e2e tests:** `{command}`
- **Run specific suite:** `{command with scoping}`
- **Filter by label:** `{mechanism, e.g., GINKGO_LABEL_FILTER="label"}`
- **Filter by description:** `{mechanism, e.g., GINKGO_FOCUS="pattern"}`
- **Parallel execution:** `{mechanism, e.g., GINKGO_PROCS=N}`
- **Environment assumptions:** {what must be running before tests execute}

### Harness
- **Location:** {path(s) to harness files}
- **Initialization:** {how tests obtain the harness}
- **Key methods for this story:**

| Method | Purpose | Source File |
|--------|---------|-------------|
| `{method}` | {what it does} | {file} |

### Setup/Teardown Patterns
- **BeforeSuite:** {what happens}
- **BeforeEach:** {what happens}
- **AfterEach:** {what happens}
- **AfterSuite:** {what happens}

### Auxiliary Services

| Service | How Started | How Accessed | Required By |
|---------|-------------|-------------|-------------|
| {name} | {testcontainer/make target/manual} | {helper/env var/harness method} | {which tests} |

{If no auxiliary services: "No auxiliary services required for e2e tests."}

### Test Utilities
- **Constants:** {path, key constants}
- **Helpers:** {path(s), key functions}
- **Tracing:** {how tests set up tracing}
- **Test data:** {where fixtures live}

### Conventions
- **Labels:** {convention, e.g., Label("ticket-id", "component-tag")}
- **File naming:** {convention for test files}
- **Test naming:** {convention for Describe/It blocks}
- **Lint rules:** {test-specific lint rules, if any}
- **Documentation:** {test docs locations}

### Reference Suite

#### {Suite Name} — `{path}`

**Why selected:** {what makes this suite similar to the planned tests}

**Patterns to follow:**
- **Imports:** {import pattern from the suite file}
- **Setup:** {BeforeSuite/BeforeEach pattern}
- **Assertions:** {assertion style, e.g., Eventually/Expect}
- **Labels:** {how labels are applied}
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

 Good: "Should the fleet rollback e2e tests enroll a real VM via the
 harness, or use the device simulator? The existing rollout suite uses
 real VMs but the agent suite uses both patterns."

 Bad: "Need to figure out the VM approach." (too vague)

 Bad: "The harness supports both VMs and simulators." (observation, not
 a question)}
```

### Step 7a: Diff Against Prior Ingest (Re-invocation Only)

If Step 2a created a `.prev` file, compare `01-context.md.prev` against
the newly compiled content. Focus the diff on:

- Changes to acceptance criteria or testing approach
- Changes to dependency status (have [DEV] stories been merged since last ingest?)
- New harness methods or infrastructure discovered
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
- E2E test infrastructure discovered (framework, harness, reference suite)
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
- E2E infrastructure discovered (framework, harness, reference suite)
- Validation profile summary
- Assessment of readiness for `/plan`

Then **re-read the controller** (`controller.md`) for next-step guidance.
