# Implement Workflow

A story-to-code workflow that takes a Jira Story, plans the implementation, writes contract-based tests and production code via TDD, validates against the project's CI expectations, and manages review via GitHub PRs.

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Jira access (MCP or CLI) | For `/ingest` | Fetch Story issue details |
| GitHub CLI (`gh`) | For `/publish`, `/respond` | Create PRs, post review comments |
| Git | Yes | Branch management, commits |
| Project build/test tooling | Yes | Discovered during `/ingest` from project's AGENTS.md, Makefile, CI workflows |
| Docs repo (local clone) | For `/ingest` | Read PRD and design document for upstream context |

## Phases

| Phase | Command | Purpose | Artifact(s) |
|-------|---------|---------|-------------|
| Ingest | `/ingest` | Fetch story, load context, explore codebase | `01-context.md` |
| Plan | `/plan` | Design implementation approach and test strategy | `02-plan.md` |
| Revise | `/revise` | Incorporate feedback into the plan | Updated `02-plan.md` |
| Code | `/code` | Write tests and code via TDD | `03-test-report.md`, `04-impl-report.md` |
| Validate | `/validate` | Run tests, lint, coverage analysis | `05-validation-report.md` |
| Publish | `/publish` | Push branch, create draft PR | `06-pr-description.md` |
| Respond | `/respond` | Address reviewer comments | `07-review-responses.md` |

## Typical Flow

```text
/ingest EDM-1234
  → fetches story from Jira
  → loads design document and PRD context
  → explores affected codebase areas
  → discovers validation profile (build, test, lint commands)
  → writes .artifacts/implement/EDM-1234/01-context.md

/plan
  → designs implementation approach
  → defines interfaces and types (the contracts)
  → plans test strategy (unit + integration)
  → breaks work into ordered tasks
  → writes 02-plan.md

/revise (optional, repeatable)
  → user reviews plan, requests changes
  → plan updated, consistency maintained

/code
  → creates feature branch
  → for each task: write tests → write code → review → commit
  → updates 02-plan.md with task completion status
  → writes 03-test-report.md, 04-impl-report.md

/validate
  → runs full validation suite (discovered during /ingest)
  → analyzes coverage for untested behavioral paths
  → adds tests for gaps, fixes lint issues
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

All artifacts are stored in `.artifacts/implement/{jira-key}/`.

```text
.artifacts/implement/EDM-1234/
  01-context.md              (story context, validation profile)
  02-plan.md                 (task breakdown, test strategy — updated as tasks complete)
  03-test-report.md          (tests written, contracts covered)
  04-impl-report.md          (changes, commits, deviations)
  05-validation-report.md    (check results, coverage, regressions)
  06-pr-description.md       (PR body)
  07-review-responses.md     (review comment log)
  publish-metadata.json      (PR number, branch, URL)
```

## Key Design Decisions

### Contract-Based Testing

Tests validate behavioral contracts through public interfaces:
- Every behavioral path reachable through a public function gets its own test case
- Tests should remain valid if the implementation were rewritten
- Unit tests are always required; integration tests are required when the story touches component interactions
- Coverage tooling is a signal ("is there a behavioral contract I missed?"), not a numeric target. However, new code that cannot reach the project's coverage threshold (discovered during `/ingest`, default 90%) through public API tests signals a design problem — the component likely needs decomposition into smaller units, not tests that reach into internals

### Discovery-Based Validation

The workflow does not hardcode language-specific commands. During `/ingest`, it discovers the project's validation expectations from AGENTS.md, Makefile, and CI workflows, and records them in a validation profile. `/validate` executes whatever was discovered. If the project adds new CI checks, the next `/ingest` picks them up automatically.

### Incremental Commits

Each logical unit of work gets its own commit, following the project's commit format (discovered during `/ingest`). Each commit should be independently meaningful.

### Plan as Living Document

`02-plan.md` is updated during `/code` as tasks are completed. On re-invocation (e.g., after context limits or interruptions), the plan shows which tasks are done and which remain.

## Directory Structure

```text
implement/
├── SKILL.md                    # Workflow entry point
├── guidelines.md               # Behavioral rules and guardrails
├── README.md                   # This file
├── skills/
│   ├── controller.md           # Phase dispatcher and transitions
│   ├── ingest.md               # Fetch story, explore codebase
│   ├── plan.md                 # Design implementation approach
│   ├── revise.md               # Incorporate plan feedback
│   ├── code.md                 # Write tests and code via TDD
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
./install.sh claude --workflows implement

# Or install all workflows
./install.sh all
```

Then in your project, run the `implement` workflow's `ingest` command for your Jira story (e.g., EDM-1234).
