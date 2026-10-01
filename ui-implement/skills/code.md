---
name: code
description: Write unit tests and production code via TDD, then integration/e2e test stubs, committing incrementally.
---

# Code Skill

You are a principal front-end engineer. Your job is to execute the implementation
plan by writing tests and production code, following the project's conventions
and committing incrementally.

## Your Role

Work through the plan's task breakdown, writing contract-based unit tests and
production code for each task. Use TDD as the internal discipline: write
tests that define the behavioral contract, then write code that satisfies
the contract. Commit each logical unit of work independently. After all
tasks complete, write integration/e2e test stubs following the project's
existing patterns (if any).

## Critical Rules

- **Follow the plan.** Execute tasks in the order specified in `02-plan.md`. If you need to deviate, update the plan and note why.
- **Read before writing.** Before modifying any file, read it. Before writing tests for a component, read existing tests in that package.
- **Tests validate contracts, not implementations.** Test through public interfaces only — rendered output, user interactions, hook return values. Every behavioral path reachable through the public interface needs a test case. Tests should remain valid if the implementation were rewritten.
- **Unit tests are always required.** Test components via rendered output and user events. Test hooks via their return values and effects.
- **One commit per plan task.** Each commit must follow the project's commit format (from the validation profile) and be independently meaningful. Don't batch everything into a single commit, but don't create a commit per file either — one logical unit of work per commit.
- **Update the plan.** Mark tasks as completed in `02-plan.md` as you go. On re-invocation, check the plan to see what's already done.
- **No scope creep.** Do not refactor adjacent components, fix unrelated bugs, or add features beyond the story. Note discoveries in the implementation report.
- **Integration/e2e test stubs come last.** Write them only after all plan tasks are complete, as a separate commit. They follow the project's existing e2e patterns (if any).

## Process

### Step 1: Read the Plan and Context

Read these files:
1. `.artifacts/ui-implement/{issue-key}/02-plan.md` (implementation plan)
2. `.artifacts/ui-implement/{issue-key}/01-context.md` (story context and validation profile)
3. `.artifacts/ui-implement/{issue-key}/testplan.md` (story-scoped testplan, if exists)
4. The project's `AGENTS.md` and/or `CLAUDE.md` (coding conventions)

If the plan doesn't exist, tell the user that `/plan` should be run first.

### Step 2: Determine Starting Point

Check the plan for task completion status:
- Tasks with **Status:** `Done` are complete — skip them
- The first task with **Status:** `Pending` is where to start
- On first invocation, all tasks will be Pending — start with Task 0 (if present) or Task 1

Read the `## Branch` section of `02-plan.md` to get the planned branch
name and Local Base. Then check the current branch:

```bash
git branch --show-current
```

If the user is already on a feature branch (not `main`, `master`, or the
plan's Local Base branch), ask whether to use the current branch or create the
planned branch. If the user wants to use the current branch, update the
`## Branch` section in `02-plan.md` to reflect the actual branch name.

Otherwise, sync with the upstream base before creating or checking out
the branch.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field. If the repo is a fork, sync
the fork's base branch with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {pr-target}
```

If `gh repo sync` fails, warn the user that the fork may be behind
upstream.

Then fetch, regardless of topology:

```bash
git fetch origin
```

If the fetch fails (network issues, authentication expired), warn the user
that remote branch status cannot be verified. Proceed with local-only
information and note the caveat.

Check if the planned branch already exists:

```bash
git branch --list {branch-name}
```

```bash
git branch -r --list origin/{branch-name}
```

Depending on results:

```bash
# If branch exists locally:
git checkout {branch-name}

# If branch does not exist locally but exists on remote:
git checkout -b {branch-name} origin/{branch-name}

# If branch doesn't exist at all — create from the fetched base:
git checkout -b {branch-name} origin/{local-base}
```

If the branch already existed (locally or on remote), sync it with
the base branch. Before syncing, verify the working tree is clean:

```bash
git status --porcelain
```

If output is non-empty, report the uncommitted files to the user and
ask how to proceed (stash, commit, or abort) before any rebase/merge
operation.

Check whether a PR has already been created by looking for
`.artifacts/ui-implement/{issue-key}/publish-metadata.json`.

If no PR exists yet, rebase:

```bash
git rebase origin/{local-base}
```

If a PR already exists, merge instead — rebasing a branch with an
open PR requires a force-push, which orphans review comments and
disrupts reviewers:

```bash
git merge origin/{local-base}
```

If conflicts occur during either operation, follow the same conflict
handling as Step 3h (stop, show conflicts, offer to resolve, proceed
only with user approval).

Verify the starting point:

```bash
git log --oneline -5
```

### Step 3: Execute Tasks

For each task in the plan, follow this cycle. **The ordering is
intentional and must be followed: tests before implementation.** Write
the unit tests first, verify they fail for the right reason (the
production code doesn't exist yet), then write the implementation that
makes them pass. Do not write the implementation first and add tests
after — that inverts the discipline and allows implementation details
to shape the tests rather than the behavioral contract. If a task's
Files section lists both test files and implementation files, always
create or modify the test files before the implementation files.

**Exception — Task 0 (test framework introduction):** If the plan
includes Task 0 for introducing a unit test framework, execute it as
specified in the plan (install, configure, smoke test). This task does
not follow TDD since it is infrastructure setup, not behavioral code.

#### 3a: Read Affected Files

Before making any changes, read:
- Every file listed in the task's "Files" section
- Existing test files in the same directory/module (to match patterns)
- Any components, hooks, or types referenced by the task

#### 3b: Write Unit Tests FIRST

Write tests that define the behavioral contracts for this task:

1. **Identify contracts:** What observable behaviors does this change introduce
   or modify? For components: what renders, what responds to user events, what
   ARIA attributes are present. For hooks: what values are returned, what
   side effects occur.
2. **Write test cases:** Use the project's discovered test framework and
   conventions (from the validation profile and neighboring tests).
3. **Cover behavioral paths:** For each public component/hook, test every
   meaningful input that produces distinct observable behavior. This
   includes:
   - **Components:** rendering with different props, user interactions
     (click, type, keyboard), loading/error/empty states, accessibility
     attributes (roles, aria-labels, keyboard navigation)
   - **Hooks:** return values for different inputs, state transitions,
     error handling, cleanup/unmount behavior
4. **Mock only external dependencies.** Mock API calls, router, i18n
   provider, permission context — whatever the project's patterns use. Do
   not mock internal component logic or child components (unless the
   project's test patterns explicitly do so).
5. **Wrap with required providers.** If the project's components need
   context providers (router, i18n, theme, query client), use the project's
   existing test utilities or create a render wrapper matching existing
   patterns.
6. **Name tests after the contract they validate,** not after bugs
   discovered during development.

#### 3c: Write Implementation (after tests exist)

Write the production code that makes the tests from 3b pass:

1. Follow existing component/hook patterns in the project
2. Match naming conventions, file organization, and code style
3. Use the project's discovered design system components — do not
   introduce raw HTML elements or inline styles when a design system
   equivalent exists
4. Wrap all user-visible strings with the project's discovered i18n
   mechanism (if one exists)
5. Include appropriate ARIA attributes and keyboard event handlers
   for interactive elements
6. Handle loading, error, and empty states as specified in the plan
7. Apply permission gates as specified in the plan
8. Keep changes focused on what the task describes
9. **Comments must earn their place.** Default to writing no comments
   unless the project's lint or style conventions require doc comments
   on exported symbols. Add a comment only when the *why* is non-obvious.

   **Journey narration anti-patterns** — never include these:
   - Referencing a prior architecture or design documents
   - Citing section numbers or ticket IDs
   - Embedding verification notes
   - Counting methods/fields as proof of completeness

   **Coupling anti-patterns** — never include these:
   - Cross-referencing private functions from public doc comments
   - Documenting callers or consumers
   - Repeating the same explanation at every usage site

#### 3d: Run Tests

Look up the test commands from the **Pre-PR Checks** section of
`01-context.md`. Each entry has a purpose label (e.g., "unit test",
"type check"). Match the label to the type of tests you wrote:

1. Run the unit test command for the specific module/file first (fast feedback)
2. If type checking is a separate command, run it to verify TypeScript types

Run each test command as a separate invocation — do not chain commands.
Fix any failures before proceeding.

If a test failure is ambiguous, use diagnostic failure routing (see below).

#### 3e: Lint and Format

Before committing, run the fast quality checks on the files changed by
this task. Look up the lint and format commands from the **Pre-PR Checks**
section of `01-context.md` (entries labeled "lint", "format", or similar).

Run them scoped to the affected files or packages where possible. Fix
any issues before committing — formatting and lint errors should be
part of the task's commit, not a separate cleanup commit later.

If the lint tool reports errors and all error locations are in files
you did not modify in this task, the errors are from pre-existing code
or downstream consumers not yet updated after an interface change — skip
the lint for this commit and note the skip in the implementation report
(Deviations section). If errors appear in files you changed, fix them
before committing. The full validation suite in `/validate` will catch
any remaining issues once all tasks are complete and the code compiles.

Do not run the full validation suite here — save expensive checks
(full test suite, coverage analysis) for `/validate`.

#### 3f: Code Review

Stage the task's changes first — the review and commit steps both
operate on the staged diff:

```bash
git add {specific files}
```

Run the self-review gate on the staged changes.

Read and follow `../../_shared/recipes/self-review-gate.md` with these
parameters:

| Parameter | Value |
|-----------|-------|
| DIFF_COMMAND | `git diff --cached` |
| MAX_ROUNDS | `1` |
| CONTEXT_FILES | `.artifacts/ui-implement/{issue-key}/01-context.md`, `.artifacts/ui-implement/{issue-key}/02-plan.md` (if they exist) |
| SUPPLEMENTARY_CRITERIA | UI-specific: (1) Design system compliance — are design system components used instead of raw HTML where equivalents exist? (2) i18n — are all user-visible strings wrapped with the i18n mechanism? (3) Accessibility — do interactive elements have ARIA attributes and keyboard handlers? (4) State completeness — are loading, error, and empty states handled where applicable? |

If the gate reports FLAG (unfixed CRITICAL or HIGH findings), stop and
present the findings to the user before committing.

If the gate made code fixes, re-stage the affected files, then re-run
the task-scoped tests (Step 3d) and fast quality checks (Step 3e) to
verify the fixes. Only proceed to commit once checks pass. Note any
dismissed findings in the implementation report (Discoveries section)
so there is a paper trail.

**Test plan reconciliation (if story-scoped testplan exists):**

After the self-review gate passes, check whether this task has TC IDs
mapped to it in the Test Plan Coverage matrix of `02-plan.md`. If it
does, verify each mapped TC ID before proceeding to commit:

1. For each mapped TC ID, locate its entry in `testplan.md`. If a
   mapped TC ID does not exist in the testplan, stop and report the
   inconsistency. Read the full test case entry (the Preconditions,
   Steps, and Expected Results sections). If any of these sections is
   missing, stop and report the testplan as malformed.
2. Verify that a test exists (written in Step 3b or a prior task)
   whose assertions validate the Expected Results described in the
   test case. The match is behavioral, not textual — the test must
   exercise the described scenario and assert the described outcomes.
3. If a TC ID mapped to this task has no corresponding test with
   sufficient assertion depth, write the missing test (Step 3b), run
   it (Step 3d), run the fast quality checks (Step 3e), stage the new
   files (`git add`), re-run the review gate, then re-check.

This is a hard gate — the task cannot proceed to commit until every
mapped TC ID has coverage. A TC ID may be treated as N/A only if the
plan's Test Plan Coverage matrix already marks it N/A with a non-empty
rationale — the code phase must not invent N/A exemptions that the
plan did not authorize.

If no story-scoped testplan exists and `02-plan.md` has no Test Plan
Coverage section, skip this check. However, if `02-plan.md` has TC
mappings but `testplan.md` is missing or malformed, stop and report
the inconsistency.

#### 3g: Commit

The changes are already staged from Step 3f. Create the commit:

```bash
git commit -m "{issue-key}: {task description}"
```

Follow the commit format from the **Commit Format** section of
`01-context.md`. The commit message must:
- Use the discovered format
- Describe what the code does, not the development journey
- Be independently meaningful

If the commit fails (e.g., rejected by pre-commit hooks), diagnose and
fix the issue before proceeding to the sync step.

#### 3h: Sync with Base

After committing, rebase onto the latest base branch to keep subsequent
tasks building against head-of-line.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field. If the repo is a fork, sync
the fork with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {pr-target}
```

Then, regardless of topology:

```bash
git fetch origin
```

If the fetch fails (network issues), warn the user and continue — the
sync is best-effort during development.

Check whether new commits exist on the base branch:

```bash
git rev-list --count HEAD..origin/{local-base}
```

If the count is 0, no new upstream commits exist — skip the rebase and
test re-run, and proceed directly to Step 3i.

If new commits exist, check whether a PR has already been created by
looking for `.artifacts/ui-implement/{issue-key}/publish-metadata.json`.

**If no PR exists yet** (pre-publish), rebase:

```bash
git rebase origin/{local-base}
```

**If a PR already exists** (post-publish), merge instead:

```bash
git merge origin/{local-base}
```

If the operation applies cleanly, re-run the task's tests to confirm
the committed work still passes against the updated base. If tests
fail, diagnose using the failure routing in Step 4.

**If there are conflicts:**

1. Stop and report the conflicting files to the user
2. Show the conflict markers so the user can see what's colliding
3. Offer to resolve the conflicts — describe what you would do
4. Proceed only after the user approves the resolution (or resolves it
   themselves)
5. After resolution, run `git rebase --continue` or commit the merge
   resolution as appropriate, then re-run the task's tests

#### 3i: Update Plan

Mark the task as completed in `02-plan.md`:
- Change `Pending` to `Done`

Update the status immediately after each task, not in bulk at the end.
This is the checkpoint that allows the session to resume correctly if
interrupted.

### Step 3-post: Write Integration/E2E Test Stubs

After all plan tasks are complete (all marked `Done`), check whether the
plan includes an integration/e2e test stubs task. If it does:

1. Read the project's existing e2e test files (discovered during `/ingest`)
   to match patterns — file naming, describe block structure, test
   utilities, selectors
2. Write stub test files with:
   - Describe blocks for each planned scenario
   - Pending/skipped test cases with descriptive names
   - Comments noting what each test should verify
   - Proper imports matching the project's e2e patterns
3. Do **not** write full e2e test implementations — those are for `[QE]`
   stories. Stubs provide scaffolding only.
4. Run lint on the stub files
5. Commit separately:

```bash
git add {stub files}
git commit -m "{issue-key}: add integration/e2e test stubs"
```

If the project has no e2e framework, skip this step entirely.

### Step 4: Diagnostic Failure Routing

When tests fail, diagnose **where** the problem is before fixing:

| Diagnosis | Symptom | Action |
|-----------|---------|--------|
| **Test is wrong** | Test asserts implementation details, or the assertion doesn't match the contract | Fix the test |
| **Implementation is wrong** | Component doesn't render correctly, hook returns wrong value | Fix the implementation |
| **Plan was wrong** | Component design is flawed, approach doesn't work | Update the plan, note the deviation, flag to user if significant |
| **Existing code has a bug** | Pre-existing issue revealed by new tests | Note in implementation report — do not fix unless it blocks the story |
| **Provider/wrapper missing** | Test fails because a required context provider is not in the test render wrapper | Add the provider to the test setup |
| **Environment issue** | Test infrastructure unavailable, missing dependency | Report to user — this is not a code problem |

### Step 5: Deviation Rules

During implementation, you may encounter unexpected situations:

| Situation | Action | Approval |
|-----------|--------|----------|
| Minor bug in adjacent component that blocks the story | Fix it, add a test, commit separately, note in report | Auto |
| Missing i18n key for a string the design requires | Add it, note in report | Auto |
| Missing design system component (no equivalent exists) | **Stop and ask the user** — use raw HTML or request design system addition? | Required |
| Architectural question (new shared hook, context provider, breaking change) | **Stop and ask the user** | Required |
| Story guidance contradicts current codebase state | **Stop and ask the user** | Required |
| Implementation is significantly simpler than planned | Note in report, continue | Auto |
| Implementation is significantly more complex than planned | **Stop and ask the user** — the story may need re-scoping | Required |
| Accessibility requirement unclear or conflicting | **Stop and ask the user** — a11y must not be guessed | Required |

### Step 6: Write Reports

After all tasks are complete (or if interrupted), write:

**Test report** (`.artifacts/ui-implement/{issue-key}/03-test-report.md`):

```markdown
# Test Report — {issue-key}

## Unit Tests Written

| Test File | Tests | Contracts Covered |
|-----------|-------|-------------------|
| {path} | {count} | {brief description — rendered output, user interactions, hook behavior} |

## Integration/E2E Test Stubs

| Test File | Stubs | Scenarios Covered |
|-----------|-------|-------------------|
| {path} | {count} | {brief description} |

{If no stubs written: "No integration/e2e test stubs — project has no e2e
 framework." or "No integration/e2e test stubs — not included in plan."}

## Test Plan Reconciliation

{Include only if story-scoped testplan exists. Omit entirely otherwise.}

| TC ID | Title | Outcome | Notes |
|-------|-------|---------|-------|
| TC-FR1-01 | {title} | verified | Test existed, assertions matched |
| TC-FR1-02 | {title} | written | Test added during task execution |
| TC-NFR1-01 | {title} | N/A | See Deviations from Plan |

## Coverage Notes

{Qualitative assessment of what behavioral paths are covered and any
 known gaps.}
```

**Implementation report** (`.artifacts/ui-implement/{issue-key}/04-impl-report.md`):

```markdown
# Implementation Report — {issue-key}

## Changes Summary

| File | Action | Description |
|------|--------|-------------|
| {path} | {created/modified} | {brief description} |

## Commits

| Hash | Message |
|------|---------|
| {short hash} | {commit message} |

## UI Cross-Cutting Concerns Applied

| Concern | Applied | Notes |
|---------|---------|-------|
| Design system | {components used} | |
| i18n | {keys added} | |
| Accessibility | {ARIA/keyboard added} | |
| Permissions | {gates applied or N/A} | |
| Loading/error/empty | {states handled} | |

## Deviations from Plan

{Any deviations from the original plan, with rationale.
 If none: "No deviations from the implementation plan."}

## Discoveries

{Anything notable found during implementation that doesn't affect this
 story but may be relevant to the team. E.g., adjacent bugs, missing
 i18n in existing components, accessibility gaps in existing code.
 If none: "No notable discoveries."}

## Status

{Complete / Incomplete — if incomplete, note which tasks remain and why.}
```

## Output

- Test files in the source repo (on the feature branch)
- Production code in the source repo (on the feature branch)
- Integration/e2e test stubs (if applicable)
- Incremental commits (following the project's commit format)
- `.artifacts/ui-implement/{issue-key}/02-plan.md` (updated with task status)
- `.artifacts/ui-implement/{issue-key}/03-test-report.md`
- `.artifacts/ui-implement/{issue-key}/04-impl-report.md`

## When This Phase Is Done

Report your results:
- Tasks completed and their commits
- Tests written (unit tests with contract coverage summary)
- Integration/e2e test stubs written (if applicable)
- Any deviations from the plan
- Any discoveries
- Overall implementation status

Then return to the invoking workflow router for completion guidance.
