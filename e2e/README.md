# E2E Test Workflow

A story-to-tests workflow that takes a Jira [QE] Story, discovers the project's e2e testing infrastructure, plans test scenarios mapped to acceptance criteria, writes e2e test code following the project's patterns, validates against anti-patterns and scenario coverage, and manages review via GitHub PRs.

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Jira access (MCP or CLI) | For `/ingest` | Fetch [QE] Story issue details |
| GitHub CLI (`gh`) | For `/publish`, `/respond` | Create PRs, post review comments |
| Git | Yes | Branch management, commits |
| Project e2e test tooling | Yes | Discovered during `/ingest` from project's AGENTS.md, Makefile, CI workflows |
| Docs repo (local clone) | For `/ingest` | Read PRD and design document for upstream context |

## Phases

| Phase | Command | Purpose | Artifact(s) |
|-------|---------|---------|-------------|
| Ingest | `/ingest` | Fetch [QE] story, verify [DEV] dependencies, explore e2e infrastructure | `01-context.md` |
| Plan | `/plan` | Map ACs to test scenarios, select reference suite | `02-plan.md` |
| Revise | `/revise` | Incorporate feedback into the test plan | Updated `02-plan.md` |
| Code | `/code` | Write e2e test code following discovered patterns | `03-test-report.md`, `04-impl-report.md` |
| Validate | `/validate` | Run tests, check anti-patterns, verify scenario coverage | `05-validation-report.md` |
| Publish | `/publish` | Push branch, create draft PR | `06-pr-description.md` |
| Respond | `/respond` | Address reviewer comments | `07-review-responses.md` |

## Typical Flow

```text
/ingest EDM-5678
  -> fetches [QE] story from Jira
  -> verifies [DEV] dependencies are merged
  -> loads design document and PRD context
  -> explores e2e test infrastructure (framework, harness, patterns)
  -> selects reference suite as pattern source
  -> discovers validation profile (test execution, lint commands)
  -> writes .artifacts/e2e/EDM-5678/01-context.md

/plan
  -> maps each acceptance criterion to test scenarios
  -> selects reference suite and documents patterns to follow
  -> designs test file structure (suite file + test files)
  -> plans harness method usage and auxiliary services
  -> breaks work into ordered tasks (suite file first, then scenarios)
  -> writes 02-plan.md

/revise (optional, repeatable)
  -> user reviews plan, requests changes
  -> plan updated, consistency maintained

/code
  -> creates feature branch
  -> for each task: read reference -> write test code -> run tests -> review -> commit
  -> updates 02-plan.md with task completion status
  -> writes 03-test-report.md, 04-impl-report.md

/validate
  -> runs e2e tests (scoped to new suite)
  -> checks for anti-patterns (hardcoded sleeps, missing cleanup, etc.)
  -> verifies every AC has a passing test scenario
  -> checks for regressions in adjacent suites
  -> writes 05-validation-report.md

/publish
  -> pushes feature branch
  -> creates draft GitHub PR with Jira link
  -> writes 06-pr-description.md

/respond (repeatable)
  -> fetches PR review comments
  -> proposes responses (user approves before posting)
  -> applies code changes if needed
  -> writes 07-review-responses.md
```

## Artifacts

All artifacts are stored in `.artifacts/e2e/{jira-key}/`.

```text
.artifacts/e2e/EDM-5678/
  01-context.md              (story context, e2e infrastructure, validation profile)
  02-plan.md                 (scenario breakdown, AC coverage -- updated as tasks complete)
  03-test-report.md          (tests written, harness methods used)
  04-impl-report.md          (changes, commits, deviations, discoveries)
  05-validation-report.md    (check results, anti-patterns, regressions)
  06-pr-description.md       (PR body)
  07-review-responses.md     (review comment log)
  publish-metadata.json      (PR number, branch, URL)
```

## Key Design Decisions

### Discovery-Based Infrastructure

The workflow does not hardcode language-specific commands or framework assumptions. During `/ingest`, it discovers the project's e2e testing framework, harness, auxiliary services, execution commands, and conventions. This makes the workflow portable across projects using different testing stacks (Ginkgo, Playwright, pytest, Cypress, etc.).

### Reference Suite Pattern

Before writing any test code, the workflow identifies the most similar existing e2e test suite in the project and extracts its patterns: imports, setup/teardown, harness usage, assertion style, labels, and cleanup. New tests follow these patterns exactly, ensuring consistency with the project's existing test base.

### Scenario-Driven Planning

Unlike implementation planning (task-driven), e2e test planning is scenario-driven. Each acceptance criterion maps to one or more concrete test scenarios with specific Describe/Context/It nesting, steps, assertions, and labels. This ensures every AC is verifiably covered.

### Anti-Pattern Detection

Validation checks for 10 common e2e test anti-patterns: hardcoded sleeps, brittle selectors, order-dependent tests, shared mutable state, missing cleanup, harness bypass, missing labels, hardcoded values, missing async polling, and missing failure diagnostics. Each detected anti-pattern is fixed during validation.

### Feature Defects Are Not Test Bugs

If e2e tests reveal that the feature behaves differently than the acceptance criteria describe, that is a defect in the [DEV] implementation, not a test failure. The test is adjusted (xfail/skip) and the defect is noted in the implementation report. The e2e workflow does not fix feature code.

### Incremental Commits

Each logical unit of work gets its own commit, following the project's commit format (discovered during `/ingest`). Each commit should be independently meaningful.

### Plan as Living Document

`02-plan.md` is updated during `/code` as tasks are completed. On re-invocation (e.g., after context limits or interruptions), the plan shows which tasks are done and which remain.

## Directory Structure

```text
e2e/
├── SKILL.md                    # Workflow entry point
├── guidelines.md               # Behavioral rules and guardrails
├── README.md                   # This file
├── skills/
│   ├── controller.md           # Phase dispatcher and transitions
│   ├── ingest.md               # Fetch story, explore e2e infrastructure
│   ├── plan.md                 # Map ACs to test scenarios
│   ├── revise.md               # Incorporate plan feedback
│   ├── code.md                 # Write e2e test code
│   ├── validate.md             # Run tests, check anti-patterns
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
./install.sh claude --workflows e2e

# Or install all workflows
./install.sh all
```

Then in your project, run the `e2e` workflow's `ingest` command for your [QE] Jira story (e.g., EDM-5678).
