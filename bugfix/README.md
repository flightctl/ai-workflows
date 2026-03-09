# Bug Fix Workflow

A systematic workflow for analyzing, fixing, and verifying software bugs. Guides developers through the complete bug resolution lifecycle from reproduction to release.

## Overview

This workflow provides a structured approach to fixing software bugs:

- **Systematic Process**: Structured methodology from reproduction to PR submission
- **Root Cause Focus**: Emphasizes understanding *why* bugs occur, not just *what* happens
- **Comprehensive Testing**: Ensures fixes work and prevents regression
- **Complete Documentation**: Creates all artifacts needed for release and future reference

## Directory Structure

```text
bugfix/
├── commands/             # Slash commands (thin wrappers → skills)
│   ├── assess.md
│   ├── diagnose.md
│   ├── document.md
│   ├── fix.md
│   ├── pr.md
│   ├── reproduce.md
│   ├── review.md
│   └── test.md
└── skills/               # Detailed process definitions
    ├── assess.md
    ├── controller.md
    ├── diagnose.md
    ├── document.md
    ├── fix.md
    ├── pr.md
    ├── reproduce.md
    ├── review.md
    └── test.md
├── CLAUDE.md             # Behavioral guidelines
└── README.md             # This file
```

### How Commands and Skills Work Together

Each **command** is a thin wrapper that invokes a corresponding **skill**. When you run `/diagnose`, the command file tells the agent to read the Diagnose skill from `.claude/skills/diagnose/SKILL.md` and apply it — passing along any arguments you provided plus existing session context.

This separation keeps commands simple and consistent while the skills contain the full process details.

## Workflow Phases

The Bug Fix Workflow follows this approach:

### Phase 1: Reproduce (`/reproduce`)

**Purpose**: Systematically reproduce the bug and document observable behavior.

- Parse bug reports and extract key information
- Set up environment matching bug conditions
- Attempt reproduction with variations to understand boundaries
- Document minimal reproduction steps
- Create reproduction report with severity assessment

**Output**: `.artifacts/{number}/bugfix/reports/reproduction.md`

**When to use**: Start here if you have a bug report, an issue URL, or a symptom description.

### Phase 2: Diagnose (`/diagnose`)

**Purpose**: Perform root cause analysis and assess impact.

- Review reproduction report and understand failure conditions
- Analyze code paths and trace execution flow
- Examine git history and recent changes
- Form and test hypotheses about root cause
- Assess impact across the codebase
- Recommend fix approach

**Output**: `.artifacts/{number}/bugfix/analysis/root-cause.md`

**When to use**: After successful reproduction, or skip here if you know the symptoms.

### Phase 3: Fix (`/fix`)

**Purpose**: Implement the bug fix following best practices.

- Review fix strategy from diagnosis phase
- Create feature branch (`bugfix/{number}-{description}`)
- Implement minimal code changes to fix the bug
- Address similar patterns identified in analysis
- Run linters and formatters
- Document implementation choices

**Output**: Modified code files + `.artifacts/{number}/bugfix/fixes/implementation-notes.md`

**When to use**: After diagnosis phase, or jump here if you already know the root cause.

### Phase 4: Test (`/test`)

**Purpose**: Verify the fix and create regression tests.

- Create regression test that fails without fix, passes with fix
- Write comprehensive unit tests for modified code
- Run integration tests in realistic scenarios
- Execute full test suite to catch side effects
- Perform manual verification of original reproduction steps
- Check for performance or security impacts

**Output**: New test files + `.artifacts/{number}/bugfix/tests/verification.md`

**When to use**: After implementing the fix.

### Phase 5: Review (`/review`) — Optional

**Purpose**: Critically evaluate the fix and its tests before proceeding.

- Re-read all evidence (reproduction report, root cause analysis, code changes, test results)
- Critique the fix: Does it address the root cause or just suppress the symptom?
- Critique the tests: Do they prove the bug is fixed, or do mocks hide real problems?
- Classify into a verdict and recommend next steps

**Verdicts**:

- **Fix is inadequate** → Recommend going back to `/fix` with specific guidance
- **Fix is adequate, tests are incomplete** → Provide instructions for what additional testing is needed (including manual steps for the user)
- **Fix and tests are solid** → Recommend proceeding to `/document` and `/pr`

**Output**: Review findings reported inline to the user (not a file).

**When to use**: After `/test`, especially for complex or high-risk fixes.

### Phase 6: Document (`/document`)

**Purpose**: Create complete documentation for the fix.

- Update issue/ticket with root cause and fix summary
- Create release notes entry
- Write CHANGELOG addition
- Update code comments with issue references
- Draft PR description

**Output**: `.artifacts/{number}/bugfix/docs/` containing issue updates, release notes, changelog entries, and PR description.

**When to use**: After testing is complete.

### Phase 7: PR (`/pr`)

**Purpose**: Create a pull request to submit the bug fix.

- Run pre-flight checks (authentication, remotes, git config)
- Ensure a fork exists and is configured as a remote
- Create a branch, stage changes, and commit with conventional format
- Push to fork and create a draft PR targeting upstream
- Handle common failures (no push access, no fork permission) with clear fallbacks

**Output**: A draft pull request URL (or manual creation instructions if automation fails).

**When to use**: After all prior phases are complete, or whenever you're ready to submit.

## Getting Started

### Quick Start

1. **Provide context**: Bug report URL, issue number, or symptom description
2. **Start with `/reproduce`** to systematically document the bug
3. **Follow the phases** sequentially or jump to any phase based on your context

### Example Usage

#### Scenario 1: You have a bug report

```text
User: "Fix bug https://github.com/org/repo/issues/425 - session status updates failing"

Workflow: Starts with /reproduce to confirm the bug
→ /diagnose to find root cause
→ /fix to implement solution
→ /test to verify fix
→ /document to create release notes
→ /pr to submit the fix
```

#### Scenario 2: You know the symptoms

```text
User: "Sessions are failing to update status in the operator"

Workflow: Jumps to /diagnose for root cause analysis
→ /fix to implement
→ /test to verify
→ /document
→ /pr
```

#### Scenario 3: You already know the fix

```text
User: "Missing retry logic in UpdateStatus call at operator/handlers/sessions.go:334"

Workflow: Jumps to /fix to implement
→ /test to verify
→ /document
→ /pr
```

### Prerequisites

- Access to the codebase where the bug exists
- Ability to run and test code locally or in an appropriate environment
- Git access for creating branches and reviewing history

## Artifacts Generated

All workflow artifacts are organized in the `.artifacts/{number}/bugfix/` directory:

```text
.artifacts/{number}/bugfix/
├── reports/                  # Bug reproduction reports
│   └── reproduction.md
├── analysis/                 # Root cause analysis
│   └── root-cause.md
├── fixes/                    # Implementation notes
│   └── implementation-notes.md
├── tests/                    # Test results and verification
│   └── verification.md
├── review/                   # Review results and notes
│   └── review.md
└── docs/                     # Documentation and release notes
    ├── issue-update.md
    ├── release-notes.md
    ├── changelog-entry.md
    ├── team-announcement.md
    └── pr-description.md
```

## Best Practices

### Reproduction

- Take time to reproduce reliably — flaky reproduction leads to incomplete diagnosis
- Document even failed attempts — inability to reproduce is valuable information
- Create minimal reproduction steps that others can follow

### Diagnosis

- Understand the *why*, not just the *what*
- Document your reasoning process for future developers
- Use `file:line` notation when referencing code (e.g., `handlers.go:245`)
- Consider similar patterns elsewhere in the codebase

### Implementation

- Keep fixes minimal — only change what's necessary
- Don't combine refactoring with bug fixes
- Avoid referencing issue numbers in code comments
- Consider backward compatibility

### Testing

- Regression tests are mandatory — every fix must include a test
- Test the test — verify it fails without the fix
- Run the full test suite, not just new tests
- Manual verification matters

### Documentation

- Be clear and specific for future developers
- Link issues, PRs, and commits for easy navigation
- Consider your audience (technical vs. user-facing)
- Don't skip this step — documentation is as important as code

## Behavioral Guidelines

The `guidelines.md` file defines engineering discipline, safety, and quality standards for bug fix sessions. Key points:

- **Confidence levels**: Every action is tagged High/Medium/Low confidence
- **Safety guardrails**: No direct commits to main, no force-push, no secret logging
- **Escalation criteria**: When to stop and request human guidance
- **Project respect**: The workflow adapts to the target project's conventions

See `guidelines.md` for full details.

### Environment-Specific Adjustments

- **Microservices**: Add service dependency analysis to Diagnose
- **Frontend**: Include browser testing in Test
- **Backend**: Add database migration checks to Fix
- **Infrastructure**: Include deployment validation in Test

## Troubleshooting

### "I can't reproduce the bug"

- Document what you tried and what was different
- Check environment differences (versions, config, data)
- Ask the reporter for more details
- Consider it may be fixed or non-reproducible

### "Multiple potential root causes"

- Document all hypotheses in `/diagnose`
- Test each systematically
- May need multiple fixes if multiple issues

### "Tests are failing after fix"

- Check if tests were wrong or your fix broke something
- Review test assumptions
- Consider if behavior change was intentional

### "Fix is too complex"

- Consider breaking into smaller fixes
- May indicate an underlying architectural issue
