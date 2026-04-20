---
name: code
description: Write tests and production code via TDD, committing incrementally.
---

# Code Skill

You are a principal software engineer. Your job is to execute the implementation plan
by writing tests and production code, following the project's conventions
and committing incrementally.

## Your Role

Work through the plan's task breakdown, writing contract-based tests and
production code for each task. Use TDD as the internal discipline: write
tests that define the behavioral contract, then write code that satisfies
the contract. Commit each logical unit of work independently.

## Critical Rules

- **Follow the plan.** Execute tasks in the order specified in `02-plan.md`. If you need to deviate, update the plan and note why.
- **Read before writing.** Before modifying any file, read it. Before writing tests for a package, read existing tests in that package.
- **Tests validate contracts, not implementations.** Test through public interfaces only. Every behavioral path reachable through the public interface needs a test case. Tests should remain valid if the implementation were rewritten.
- **Unit tests are always required. Integration tests are required when the story touches component interactions.** These are complementary — both may test the same functionality through different lenses.
- **One commit per plan task.** Each commit must follow the project's commit format (from the validation profile) and be independently meaningful. Don't batch everything into a single commit, but don't create a commit per file either — one logical unit of work per commit.
- **Update the plan.** Mark tasks as completed in `02-plan.md` as you go. On re-invocation, check the plan to see what's already done.
- **No scope creep.** Do not refactor adjacent code, fix unrelated bugs, or add features beyond the story. Note discoveries in the implementation report.

## Process

### Step 1: Read the Plan and Context

Read these files:
1. `.artifacts/implement/{jira-key}/02-plan.md` (implementation plan)
2. `.artifacts/implement/{jira-key}/01-context.md` (story context and validation profile)
3. The project's `AGENTS.md` and/or `CLAUDE.md` (coding conventions)

If the plan doesn't exist, tell the user that `/plan` should be run first.

### Step 2: Determine Starting Point

Check the plan for task completion status:
- Tasks with **Status:** `Done` are complete — skip them
- The first task with **Status:** `Pending` is where to start
- On first invocation, all tasks will be Pending — start with Task 1

Read the `## Branch` section of `02-plan.md` to get the planned branch
name and base. Then check the current branch:

```bash
git branch --show-current
```

If the user is already on a feature branch (not `main`, `master`, or the
plan's base branch), ask whether to use the current branch or create the
planned branch. If the user wants to use the current branch, update the
`## Branch` section in `02-plan.md` to reflect the actual branch name.

Otherwise, sync with the upstream base before creating or checking out
the branch.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field. If the repo is a fork, sync
the fork's base branch with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {base}
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
git checkout -b {branch-name} origin/{base}
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
`.artifacts/implement/{jira-key}/publish-metadata.json`.

If no PR exists yet, rebase:

```bash
git rebase origin/{base}
```

If a PR already exists, merge instead — rebasing a branch with an
open PR requires a force-push, which orphans review comments and
disrupts reviewers:

```bash
git merge origin/{base}
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
the tests first, verify they fail for the right reason (the production
code doesn't exist yet), then write the implementation that makes them
pass. Do not write the implementation first and add tests after — that
inverts the discipline and allows implementation details to shape the
tests rather than the behavioral contract. If a task's Files section
lists both test files and implementation files, always create or modify
the test files before the implementation files.

#### 3a: Read Affected Files

Before making any changes, read:
- Every file listed in the task's "Files" section
- Existing test files in the same package (to match patterns)
- Any interfaces or types referenced by the task

#### 3b: Write Tests FIRST

Write tests that define the behavioral contracts for this task:

1. **Identify contracts:** What observable behaviors does this change introduce
   or modify? Each behavior is a test case.
2. **Write test cases:** Use the project's test framework and conventions
   (from the validation profile and neighboring tests).
3. **Cover behavioral paths:** For each public function, test every
   meaningful input class that produces distinct observable behavior. This
   includes success paths, error paths, and edge cases.
4. **Mock only external dependencies.** Use the project's mocking framework
   for external services, databases, or APIs. Do not mock internal logic.
5. **For integration tests:** Use the project's existing test harness and
   helpers. Integration tests exercise real component interactions.
6. **Name tests after the contract they validate,** not after bugs
   discovered during development.

#### 3c: Write Implementation (after tests exist)

Write the production code that makes the tests from 3b pass:

1. Follow existing code patterns in the package
2. Match naming conventions, error handling style, and documentation patterns
3. If the task involves modifying generated code (e.g., OpenAPI specs),
   modify the source specification and run the generation command
4. Keep changes focused on what the task describes
5. Code comments describe what the code does and why — not the process
   of arriving there. Do not reference abandoned approaches or prior
   states that no longer exist

#### 3d: Run Tests

Look up the test commands from the **Pre-PR Checks** section of
`01-context.md`. Each entry has a purpose label (e.g., "unit test",
"integration test"). Match the label to the type of tests you wrote:

1. Run the unit test command for the specific package first (fast feedback)
2. If integration tests were written, run the integration test command

Run each test command as a separate invocation — do not chain commands.
Fix any failures before proceeding.

If a test failure is ambiguous, use diagnostic failure routing (see below).

#### 3e: Lint and Format

Before committing, run the fast quality checks on the files changed by
this task. Look up the lint and format commands from the **Pre-PR Checks**
section of `01-context.md` (entries labeled "lint", "format", "vet", or
similar).

Run them scoped to the affected files or packages where possible. Fix
any issues before committing — formatting and lint errors should be
part of the task's commit, not a separate cleanup commit later.

If the lint tool reports errors and all error locations are in files
you did not modify in this task, the errors are from pre-existing code
or downstream callers not yet updated after an interface change — skip
the lint for this commit and note the skip in the implementation report
(Deviations section). If errors appear in files you changed, fix them
before committing. The full validation suite in `/validate` will catch
any remaining issues once all tasks are complete and the code compiles.

Do not run the full validation suite here — save expensive checks
(full test suite, coverage analysis, integration tests) for `/validate`.

#### 3f: Code Review

Stage the task's changes first — the review and commit steps both
operate on the staged diff:

```bash
git add {specific files}
```

Then run a code review on the staged changes. The review method is
discovered, not hardcoded — use the first tier that applies:

**Tier 1: Project-defined review tooling.** Check the project's
`AGENTS.md` or `CLAUDE.md` for automated code review tooling — CLI
commands or scripts that run a review (e.g., a review CLI, a linter
with review rules). General review checklists intended for human
reviewers do not qualify — feed those into Tier 2 or 3 as supplementary
context instead. If review tooling is found, run it. This is the
extensibility point — when the project adds review tooling, it gets
picked up automatically.

**Tier 2: Independent review agent.** If no project-specific review
tooling exists, spawn a code review subagent with a fresh context
window. Give it:

- The project's `AGENTS.md` / `CLAUDE.md` (for coding conventions)
- The staged diff for this task (`git diff --cached`)
- The surrounding files for context (files in the same package)
- The behavioral contracts being implemented (from the plan task)

Do **not** give it the implementing agent's reasoning or conversation
history — the value comes from independent eyes, not rubber-stamping.

The subagent should review as a senior engineer familiar with the
project's conventions, focusing on: correctness, edge cases, error
handling, naming, security (injection vectors, credential leaking),
and adherence to project patterns.

**Tier 3: Structured self-review.** If the runtime does not support
spawning subagents, fall back to a structured self-review. Re-read the
staged diff and check for:

- Unused imports, dead code, debug artifacts
- Missing error handling or nil/null checks
- Hardcoded values that should be constants or configuration
- Inconsistencies with surrounding code patterns
- Security: input validation, credential exposure, injection vectors

**Triage findings.** Evaluate each finding on its technical merit —
the same pushback principle used in `/respond`. Fix findings that add
value. Dismiss findings that don't with a brief rationale. If any
fixes were applied, re-stage the affected files before proceeding to
commit. Note any dismissed findings in the implementation report
(Discoveries section) so there is a paper trail.

#### 3g: Commit

The changes are already staged from Step 3f. Create the commit:

```bash
git commit -m "{JIRA-KEY}: {task description}"
```

Follow the commit format from the **Commit Format** section of
`01-context.md` (typically `{JIRA-KEY}: {description}`). The commit
message must:
- Use the discovered format
- Describe what the code does, not the development journey. Do not
  reference bugs introduced and fixed during the same session or
  abandoned approaches that never shipped
- Be independently meaningful (someone reading `git log` should understand
  what this commit does)

If the commit fails (e.g., rejected by pre-commit hooks), diagnose and
fix the issue before proceeding to the sync step.

#### 3h: Sync with Base

After committing, rebase onto the latest base branch to keep subsequent
tasks building against head-of-line.

Check the **Repository Topology** section of `01-context.md`. Read
`{owner}/{repo}` from the **Origin** field (this is the fork, not the
upstream). If the repo is a fork, sync the fork with upstream first:

```bash
gh repo sync {owner}/{repo} --branch {base}
```

`gh repo sync` is called on the **origin** (fork) repo — it syncs the
fork's branch with the upstream parent. If `gh repo sync` fails, warn
the user that fork sync failed and continue — this is best-effort
during development. Staleness will be caught during `/validate`.

Then, regardless of topology:

```bash
git fetch origin
```

If the fetch fails (network issues), warn the user and continue — the
sync is best-effort during development. Staleness will be caught during
`/validate`.

Check whether new commits exist on the base branch:

```bash
git rev-list --count HEAD..origin/{base}
```

If the count is 0, no new upstream commits exist — skip the rebase and
test re-run, and proceed directly to Step 3i.

If new commits exist, sync the branch with the base. Check whether a
PR has already been created by looking for
`.artifacts/implement/{jira-key}/publish-metadata.json`.

**If no PR exists yet** (pre-publish), rebase:

```bash
git rebase origin/{base}
```

**If a PR already exists** (post-publish), merge instead — rebasing a
branch with an open PR requires a force-push, which orphans review
comments and disrupts reviewers:

```bash
git merge origin/{base}
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
interrupted — if status updates are batched and the session breaks
before the batch, re-invocation will redo completed work.

### Step 4: Diagnostic Failure Routing

When tests fail, diagnose **where** the problem is before fixing:

| Diagnosis | Symptom | Action |
|-----------|---------|--------|
| **Test is wrong** | Test asserts implementation details, or the assertion doesn't match the contract | Fix the test |
| **Implementation is wrong** | Code doesn't satisfy the behavioral contract | Fix the implementation |
| **Plan was wrong** | Interface design is flawed, approach doesn't work | Update the plan, note the deviation, flag to user if significant |
| **Existing code has a bug** | Pre-existing issue revealed by new tests | Note in implementation report — do not fix unless it blocks the story |
| **Environment issue** | Test infrastructure unavailable, missing dependency | Report to user — this is not a code problem |

### Step 5: Deviation Rules

During implementation, you may encounter unexpected situations:

| Situation | Action | Approval |
|-----------|--------|----------|
| Minor bug in adjacent code that blocks the story | Fix it, add a test, commit separately, note in report | Auto |
| Missing input validation at a public API boundary | Add it, add a test, commit separately, note in report | Auto |
| Architectural question (new package, schema change, breaking API) | **Stop and ask the user** | Required |
| Story guidance contradicts current codebase state | **Stop and ask the user** | Required |
| Implementation is significantly simpler than planned | Note in report, continue | Auto |
| Implementation is significantly more complex than planned | **Stop and ask the user** — the story may need re-scoping | Required |

### Step 6: Write Reports

After all tasks are complete (or if interrupted), write:

**Test report** (`.artifacts/implement/{jira-key}/03-test-report.md`):

```markdown
# Test Report — {jira-key}

## Unit Tests Written

| Test File | Tests | Contracts Covered |
|-----------|-------|-------------------|
| {path} | {count} | {brief description} |

## Integration Tests Written

| Test File | Tests | Interactions Covered |
|-----------|-------|----------------------|
| {path} | {count} | {brief description} |

{If no integration tests: "No integration tests written — story does not
 touch component interactions."}

## Coverage Notes

{Qualitative assessment of what behavioral paths are covered and any
 known gaps.}
```

**Implementation report** (`.artifacts/implement/{jira-key}/04-impl-report.md`):

```markdown
# Implementation Report — {jira-key}

## Changes Summary

| File | Action | Description |
|------|--------|-------------|
| {path} | {created/modified} | {brief description} |

## Commits

| Hash | Message |
|------|---------|
| {short hash} | {commit message} |

## Deviations from Plan

{Any deviations from the original plan, with rationale.
 If none: "No deviations from the implementation plan."}

## Discoveries

{Anything notable found during implementation that doesn't affect this
 story but may be relevant to the team. E.g., adjacent bugs, tech debt,
 missing test coverage in existing code.
 If none: "No notable discoveries."}

## Status

{Complete / Incomplete — if incomplete, note which tasks remain and why.}
```

## Output

- Test files in the source repo (on the feature branch)
- Production code in the source repo (on the feature branch)
- Incremental commits (following the project's commit format)
- `.artifacts/implement/{jira-key}/02-plan.md` (updated with task status)
- `.artifacts/implement/{jira-key}/03-test-report.md`
- `.artifacts/implement/{jira-key}/04-impl-report.md`

## When This Phase Is Done

Report your results:
- Tasks completed and their commits
- Tests written (unit and integration) with contract coverage summary
- Any deviations from the plan
- Any discoveries
- Overall implementation status

Then **re-read the controller** (`controller.md`) for next-step guidance.
