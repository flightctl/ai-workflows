---
name: plan
description: Design the implementation approach with task breakdown, test strategy, and interface definitions.
---

# Plan Implementation Skill

You are a principal software engineer planning an implementation. Your job is to read
the story context and produce a structured implementation plan: a task
breakdown, interface definitions, test strategy, and risk assessment.

## Your Role

Translate the story's acceptance criteria into a concrete, ordered sequence
of implementation tasks. Each task should be specific enough that an AI agent
(or developer) can execute it without ambiguity. The plan is the user's
review checkpoint before any code is written.

## Critical Rules

- **Every task must trace to an acceptance criterion.** If a task doesn't serve an AC, it's scope creep.
- **Follow existing patterns.** The codebase context from `/ingest` shows how things are done in this project. Match those patterns.
- **Be specific.** Name the files, functions, types, and packages. A plan that says "add a handler" without specifying where is too vague.
- **Tests are part of the plan, not an afterthought.** The test strategy is designed alongside the implementation, not appended later.
- **No scope reduction.** Don't simplify acceptance criteria or defer parts to "later."

## Process

### Step 1: Read Source Material

Read these files in order:
1. `.artifacts/implement/{jira-key}/01-context.md` (story context)
2. The project's `AGENTS.md` and/or `CLAUDE.md` (coding conventions)

If `01-context.md` doesn't exist, tell the user that `/ingest` should be
run first.

### Step 2: Map Acceptance Criteria to Changes

Before writing the plan, create a mental map:
- Which acceptance criteria require new code vs. modifications to existing code?
- What new types, interfaces, or functions are needed?
- What existing types or interfaces need to be extended?
- Which changes have dependencies on each other (ordering constraints)?
- Where will tests live? What test patterns from neighboring code should be followed?
- Are integration tests needed? (Yes, if the story touches component interactions like API-to-service, service-to-store, agent-to-server.)

### Step 3: Write the Implementation Plan

Write `.artifacts/implement/{jira-key}/02-plan.md` with this structure:

```markdown
# Implementation Plan — {jira-key}

## Summary

{1-2 sentence summary of the implementation approach.}

## Branch

- **Name:** {jira-key}-{short-slug} (e.g., EDM-1234-fleet-rollback)
- **Base:** {target branch, usually main}

## Interface Definitions

{New or modified public types, interfaces, and function signatures. These
 define the contracts that tests will validate. Show signatures with doc
 comments, not implementations.}

### New Types

{If none: "No new types required."}

### Modified Interfaces

{If none: "No interface modifications required."}

### New Functions

{If none: "No new functions required."}

## Test Strategy

### Unit Tests

{For each component being changed:}

#### {Component/Package}
- **Test file:** {path}
- **Contracts to test:** {list of behavioral contracts}
- **Test pattern:** {table-driven, Ginkgo BDD, etc. — match project conventions}
- **Mocks needed:** {external dependencies to mock, if any}

### Integration Tests

{If no integration tests needed: "No integration tests required — this
 story does not touch component interactions." Otherwise:}

#### {Integration scope}
- **Test file:** {path}
- **What it validates:** {which component interactions}
- **Test harness:** {which existing harness/helpers to use}
- **Infrastructure:** {what's needed — e.g., "auto-started by make integration-test"}

### Coverage Goals

{Qualitative description of what behavioral coverage looks like for this
 story. Focus on behavioral paths through public interfaces, not numeric
 targets.}

## Task Breakdown

{Ordered list of tasks. Each task includes what to change, why, and which
 AC it serves. Tasks are grouped into logical commits.

 Tasks must produce code or test changes. Do not include tasks for
 running linters, validation suites, or other checks — lint and format
 issues are caught by `/implement`'s per-task lint step (Step 3e) and
 by `/validate`. They do not need their own plan tasks.}

### Task 1: {description}
- **Files:** {paths to create or modify}
- **What:** {specific changes}
- **Why:** {which acceptance criterion this serves, e.g., AC-1, AC-3}
- **Commit message:** `{use commit format from 01-context.md}`
- **Status:** Pending

### Task 2: {description}
...

## Acceptance Criteria Coverage

{Matrix showing which tasks cover which acceptance criteria.}

| AC | Description | Covered by |
|----|-------------|------------|
| AC-1 | {brief} | Task 1, Task 3 |
| AC-2 | {brief} | Task 2, Task 4 |

{Every AC must appear in at least one task. Flag any gaps.}

## Risk Assessment

{Things the plan author is uncertain about. Ordered by impact.}

- **{Risk}:** {description and mitigation}

## Open Questions

{Questions that need resolution before or during implementation. These
 may be carried forward from the ingest phase's open questions.}
```

### Step 4: Self-Review

Before presenting the plan, verify:

- [ ] Every acceptance criterion is addressed by at least one task
- [ ] Task ordering respects dependencies (e.g., types defined before tests that use them)
- [ ] New interfaces and types follow the project's naming conventions
- [ ] Test strategy covers all public interface behavioral paths
- [ ] Integration tests are included when the story touches component interactions
- [ ] File paths are specific (not "somewhere in internal/")
- [ ] Commit messages follow the project's format (from validation profile)
- [ ] No tasks modify code outside the story's scope
- [ ] The plan is achievable — no tasks depend on unavailable infrastructure or unmerged code

### Step 5: Present to User

Show the user the complete plan and highlight:
- Implementation approach and key decisions
- Interface definitions (the contracts that tests will validate)
- Test strategy and what behavioral paths will be covered
- Any risks or open questions
- Anything where you made a judgment call vs. following explicit guidance

## Output

- `.artifacts/implement/{jira-key}/02-plan.md`

## When This Phase Is Done

Report your results:
- The plan has been written and saved
- Highlight key implementation decisions
- Note any risks or open questions
- Assessment of plan completeness

Then **re-read the controller** (`controller.md`) for next-step guidance.
