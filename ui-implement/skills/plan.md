---
name: plan
description: Design the UI implementation approach with task breakdown, component/hook interfaces, test strategy, and risk assessment.
---

# Plan UI Implementation Skill

You are a principal front-end engineer planning an implementation. Your job is
to read the story context and produce a structured implementation plan: a task
breakdown, component/hook interface definitions, test strategy, and risk
assessment.

## Your Role

Translate the story's acceptance criteria into a concrete, ordered sequence
of implementation tasks. Each task should be specific enough that an AI agent
(or developer) can execute it without ambiguity. The plan is the user's
review checkpoint before any code is written.

## Critical Rules

- **Every task must trace to an acceptance criterion.** If a task doesn't serve an AC, it's scope creep.
- **Follow existing patterns.** The codebase context from `/ingest` shows how things are done in this project. Match those patterns.
- **Be specific.** Name the files, components, hooks, types, and modules. A plan that says "add a component" without specifying where is too vague.
- **Tests are part of the plan, not an afterthought.** The unit test strategy is designed alongside the implementation. Integration/e2e test stubs are planned as a final post-task step.
- **No scope reduction.** Don't simplify acceptance criteria or defer parts to "later."
- **Design system first.** Plan to use discovered design system components. Flag gaps where no design system component exists.
- **Accessibility is not optional.** Every interactive component must have keyboard navigation and ARIA attributes planned.

## Process

### Step 1: Read Source Material

Read these files in order:
1. `.artifacts/ui-implement/{issue-key}/01-context.md` (story context)
1. `.artifacts/ui-implement/{issue-key}/testplan.md` (story-scoped testplan, if exists)
1. The project's `AGENTS.md` and/or `CLAUDE.md` (coding conventions)

If `01-context.md` doesn't exist, tell the user that `/ingest` should be
run first.

Then open **citations only** from `01-context.md` (ingest is an index; this is where the files are read):

1. Each `[UI Design: §…]`, `[Design: §…]`, `[Handoff: §…]`, `[API: §…]` (or equivalent) → that path + heading range. Do not Read the rest of the document.
1. Cited source/test paths (Affected Components + Cited, not opened) as needed to name types. Signature `offset`/`limit` slices, not whole files.
1. Cap **≤12** cited source Reads total (bootstrap reads of `01-context.md`, `testplan.md`, and `AGENTS.md`/`CLAUDE.md` do not count). Skip a citation if it is not needed to lock a task or interface.
1. Do not glob, repo-wide grep, Jira, or unrelated sibling artifacts. Read the required `testplan.md` when it exists. Do not re-run ingest exploration.
1. Classify each ingest open question (ingest is an index, not a spec). Do **not** treat ingest text as a complete contract:
   - **Already specified:** citations (or an unambiguous AC) define the component, hook, or behavior → **Locked decision**.
   - **Implementer default:** unspecified but `/code` needs a choice (component name, prop name, default state value, error message text). Lock a default that matches cited neighboring code; note it is a default `/revise` may change. Do not leave it open.
   - **Product fork:** spec vs AC, or two product-legal behaviors. Keep under **Open Questions**. Follow AC in the tasks until the user picks. Do not silently lock the design side.
1. Do not paste opened file bodies into `02-plan.md` (signatures and decisions only).

### Step 1a: Evaluate Test Infrastructure

Check the **Test Infrastructure** section of `01-context.md`:

- **If a unit test framework exists:** proceed normally. Plan tests using
  the discovered framework and patterns.
- **If no unit test framework exists:** the context will include a
  recommendation. Include a **Task 0: Introduce unit testing framework**
  in the plan that:
  1. Installs the recommended test framework and testing library
  1. Adds test scripts to `package.json`
  1. Creates a minimal test configuration file
  1. Writes one smoke test for an existing simple component to verify the setup
  1. Runs the test to confirm the framework works

  Plan all story tasks normally alongside Task 0 — use the recommended
  framework for the test strategy. Present the framework recommendation
  as part of the plan review; the user approves it when they approve
  the plan. `/code` runs Task 0 first so the framework is in place
  when subsequent tasks execute.

### Step 2: Determine Local Base and PR Target

Before writing the plan, determine two distinct branches:

**Local Base** — the branch this story's commits are stacked on locally.
Used by `/code` and `/validate` for all `git rebase` and sync operations.

Run:

```bash
git branch --show-current
```

Evaluate the result:

- **If the current branch is a trunk branch** (`main`, `master`, `develop`, or similar) — use it as the Local Base.
- **If the current branch is a feature branch** (e.g., a prior story branch) — the user is likely stacking stories. Present both options and ask which to use:
  - Use the current branch (e.g., `EDM-1233-prior-story`) as the Local Base — correct for stacked stories
  - Use `main` (or the project default) as the Local Base — correct if the user has already switched to the wrong branch by mistake

**PR Target** — the branch the pull request will target (`--base` in `gh pr create`).
This is almost always the repository's default trunk branch (`main`, `master`, etc.),
regardless of how the story is stacked locally.

Read the **Repository Topology** section of `01-context.md`:

- **If the repo is a fork**: PR Target = the upstream default branch. Confirm by running:
  ```bash
  gh repo view {upstream-owner}/{upstream-repo} --json defaultBranchRef --jq '.defaultBranchRef.name'
  ```
- **If the repo is a direct clone**: PR Target = `main` (or the project default) unless the user explicitly wants PR-based stacking against a prior story's branch.

Do not conflate Local Base with PR Target. A stacked story rebases locally onto a prior story's branch, but its PR still targets the selected PR Target.

### Step 3: Map Acceptance Criteria to Changes

Before writing the plan, create a mental map:
- Which acceptance criteria require new components vs. modifications to existing components?
- What new components, hooks, types, or utilities are needed?
- What existing components or hooks need to be extended?
- Which changes have dependencies on each other (ordering constraints)?
- Where will tests live? What test patterns from neighboring code should be followed?
- What design system components will be used?
- Which components need i18n string wrapping?
- What accessibility requirements apply (ARIA roles, keyboard navigation, screen reader text)?
- Are there loading, error, and empty states to implement?
- Are there permission gates to implement?

### Step 4: Write the Implementation Plan

Write `.artifacts/ui-implement/{issue-key}/02-plan.md` with this structure:

```markdown
# Implementation Plan — {issue-key}

## Summary

{1-2 sentence summary of the implementation approach.}

## Branch

- **Name:** {issue-key}-{short-slug} (e.g., EDM-1234-fleet-dashboard)
- **Local Base:** {branch confirmed in Step 2 — used for rebasing during /code and /validate}
- **PR Target:** {branch confirmed in Step 2 — used as --base in gh pr create; typically `main`}

## Locked Decisions

{Ingest gaps resolved as "already specified" or "implementer default." Each bullet: decision + one-line why (citation or "default, match {existing pattern}"). Product forks do not belong here.}

## Interface Definitions

{New or modified public component props, hook signatures, and TypeScript
 types. These define the contracts that tests will validate. Show
 signatures with doc comments, not implementations.}

### New Components

{If none: "No new components required."}

{For each new component:}

#### `{ComponentName}`
- **File:** {path}
- **Props:** `{TypeScript interface}`
- **Design system components used:** {list}
- **i18n keys:** {translation keys needed, if i18n exists}
- **Accessibility:** {ARIA roles, keyboard interactions}
- **States:** {loading, error, empty — if applicable}

### New Hooks

{If none: "No new hooks required."}

{For each new hook:}

#### `{useHookName}`
- **File:** {path}
- **Signature:** `{TypeScript signature}`
- **Returns:** {return type description}
- **Side effects:** {API calls, state mutations, etc.}

### Modified Components/Hooks

{If none: "No modifications required."}

### New Types

{If none: "No new types required."}

## Test Strategy

### Unit Tests

{For each component/hook being created or changed:}

#### {Component/Hook}
- **Test file:** {path}
- **Contracts to test:** {list of behavioral contracts — rendered output, user interactions, hook return values}
- **Test pattern:** {match project conventions discovered during /ingest}
- **Mocks needed:** {API calls, router, i18n provider, etc.}

### Integration/E2E Test Stubs

{Written after all tasks complete. Describe what stubs will cover:}

- **Framework:** {discovered e2e framework, or "None — project has no e2e framework"}
- **Stubs planned:** {list of test scenarios, or "No stubs — no e2e framework in project"}

### Coverage Goals

{Qualitative description of what behavioral coverage looks like for this
 story. Focus on behavioral paths through public interfaces, not numeric
 targets.}

## Task Breakdown

{Ordered list of tasks. Each task includes what to change, why, and which
 AC it serves. Tasks are grouped into logical commits.

 Tasks must produce code or test changes. Do not include tasks for
 running linters, validation suites, or other checks — lint and format
 issues are caught by `/code`'s per-task lint step and by `/validate`.
 They do not need their own plan tasks.

 If Task 0 (test framework introduction) is needed, it appears first.}

### Task 0: Introduce unit testing framework (conditional)

{Include only if /ingest found no unit test framework. Otherwise omit.}

- **Files:** {package.json, test config, smoke test file}
- **What:** {install framework, configure, write smoke test}
- **Why:** No unit test framework exists — must run first during /code
- **Commit message:** `{use commit format from 01-context.md}`
- **Status:** Pending

### Task 1: {description}
- **Files:** {paths to create or modify}
- **What:** {specific changes}
- **Why:** {which acceptance criterion this serves, e.g., AC-1, AC-3}
- **UI concerns:** {design system components, i18n keys, a11y attributes, states}
- **Commit message:** `{use commit format from 01-context.md}`
- **Status:** Pending

### Task 2: {description}
...

### Task N+1: Write integration/e2e test stubs (conditional)

{Include only if the project has an e2e framework discovered during /ingest.
 Otherwise omit.}

- **Files:** {paths for test stubs}
- **What:** {stub test files with describe blocks and pending/skip test cases}
- **Why:** Provide scaffolding for QE to implement full e2e tests
- **Commit message:** `{use commit format from 01-context.md}`
- **Status:** Pending

## Acceptance Criteria Coverage

{Matrix showing which tasks cover which acceptance criteria.}

| AC | Description | Covered by |
|----|-------------|------------|
| AC-1 | {brief} | Task 1, Task 3 |
| AC-2 | {brief} | Task 2, Task 4 |

{Every AC must appear in at least one task. Flag any gaps.}

## Test Plan Coverage

{Include this section only if `.artifacts/ui-implement/{issue-key}/testplan.md`
 exists. If no story-scoped testplan: omit this section entirely.}

| TC ID | Title | Covered by Task | Notes |
|-------|-------|-----------------|-------|
| TC-FR1-01 | {title} | Task 2 | |
| TC-FR1-02 | {title} | Task 3 | |
| TC-NFR1-01 | {title} | N/A | {rationale} |

{Every TC ID from testplan.md must appear. Each must be assigned to a
 task or marked N/A with a rationale. This is a set-diff gate:
 compute the difference between the set of TC IDs in testplan.md and
 the set assigned to tasks or marked N/A. If the difference is
 non-empty, the plan is incomplete — resolve before proceeding.}

## UI Cross-Cutting Concerns

{Summarize how each cross-cutting concern applies to this story's tasks.}

| Concern | Approach | Tasks Affected |
|---------|----------|----------------|
| Design system | {components to use} | {task list} |
| i18n | {keys/patterns} | {task list} |
| Accessibility | {ARIA/keyboard plan} | {task list} |
| Permissions | {gate pattern or N/A} | {task list} |
| Loading/error/empty | {state handling} | {task list} |

## Risk Assessment

{Things the plan author is uncertain about. Ordered by impact.}

- **{Risk}:** {description and mitigation}

## Open Questions

{Product forks only — spec vs AC or two product-legal behaviors. Not
 implementer defaults. If none: "None — `/code` can proceed."}
```

### Step 5: Self-Review

Before presenting the plan, verify:

- [ ] Every acceptance criterion is addressed by at least one task
- [ ] Task ordering respects dependencies (e.g., types defined before components that use them, hooks before components that call them)
- [ ] New components and hooks follow the project's naming conventions
- [ ] Test strategy covers all public interface behavioral paths
- [ ] Each proposed component exposes enough public surface area that its significant behavioral paths can be tested without reaching into internals
- [ ] File paths are specific (not "somewhere in components/")
- [ ] Commit messages follow the project's format (from validation profile)
- [ ] No tasks modify code outside the story's scope
- [ ] Task count is reasonable — if you have more than 10 tasks, consider whether the story needs re-scoping
- [ ] The plan is achievable — no tasks depend on unavailable infrastructure or unmerged code
- [ ] If story-scoped testplan exists: every TC ID is assigned to a task or marked N/A with rationale (Test Plan Coverage set-diff is clean)
- [ ] Every ingest open question is a locked decision (specified or implementer default) or a product fork still listed
- [ ] Open Questions contains only product forks, not defaults `/code` could pick
- [ ] Cited Reads stayed within the cap; `02-plan.md` has no pasted file bodies
- [ ] Design system components are specified for each new UI element
- [ ] i18n wrapping is planned for all user-visible strings (if i18n exists)
- [ ] Accessibility attributes are specified for all interactive elements
- [ ] Loading, error, and empty states are planned where applicable
- [ ] Integration/e2e test stubs are planned as the final task (if e2e framework exists)

### Step 6: Present to User

Show the user the complete plan and highlight:
- Implementation approach and key decisions
- Component/hook interface definitions (the contracts that tests will validate)
- Test strategy and what behavioral paths will be covered
- UI cross-cutting concerns and how they're addressed
- Any risks or open questions
- Anything where you made a judgment call vs. following explicit guidance
- If Task 0 is included: the test framework recommendation and why

## Output

- `.artifacts/ui-implement/{issue-key}/02-plan.md`

## When This Phase Is Done

Report your results:
- The plan has been written and saved
- Highlight key implementation decisions
- Note any risks or open questions
- Assessment of plan completeness

Then return to the invoking workflow router for completion guidance.
