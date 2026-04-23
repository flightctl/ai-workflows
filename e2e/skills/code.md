---
name: code
description: Write e2e test code following discovered patterns, committing incrementally.
---

# Code E2E Tests Skill

You are a principal QE engineer. Your job is to execute the test plan by
writing e2e test code following the project's conventions and the reference
suite's patterns, committing incrementally.

## Your Role

Work through the plan's task breakdown, writing e2e test code for each
task. Follow the reference suite's patterns exactly — imports, test
infrastructure usage, assertion style, labels, lifecycle hooks. Commit
each logical unit of work independently.

## Critical Rules

- **Follow the plan.** Execute tasks in the order specified in `02-plan.md`. If you need to deviate, update the plan and note why.
- **Read before writing.** Before writing any test code, read the reference suite files and existing tests in similar suites. Match their patterns.
- **Use the project's test infrastructure.** Do not make ad-hoc API calls, CLI invocations, or direct infrastructure access. Use the test abstractions (harness, fixtures, page objects, helpers) and utilities the project provides.
- **One commit per plan task.** Each commit must follow the project's commit format (from the validation profile) and be independently meaningful.
- **Update the plan.** Mark tasks as completed in `02-plan.md` as you go. On re-invocation, check the plan to see what's already done.
- **No scope creep.** Do not write tests beyond the story's acceptance criteria, refactor existing test code, or improve test infrastructure. Note discoveries in the implementation report.

## Process

### Step 1: Read the Plan and Context

Read these files:
1. `.artifacts/e2e/{jira-key}/02-plan.md` (test plan)
2. `.artifacts/e2e/{jira-key}/01-context.md` (story context and e2e infrastructure)
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
`.artifacts/e2e/{jira-key}/publish-metadata.json`.

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
handling as Step 3g (stop, show conflicts, offer to resolve, proceed
only with user approval).

Verify the starting point:

```bash
git log --oneline -5
```

### Step 3: Execute Tasks

For each task in the plan, follow this cycle.

#### 3a: Read Reference and Affected Files

Before making any changes, read:
- The reference suite file(s) noted in the plan (re-read to reinforce patterns)
- Any test infrastructure methods the task will use (verify signatures and behavior)
- Existing test files in neighboring suites (to match patterns)
- Any test utilities or constants the task will use

#### 3b: Write Test Code

Write the test code for this task, following the reference suite's patterns
exactly:

1. **Match the import block:** Use the same imports as the reference suite.
   Include framework imports, test infrastructure imports, and utility
   imports.
2. **Match the test grouping structure:** Use the project's test
   organization blocks (e.g., Describe/Context/It in Ginkgo,
   test classes/methods in pytest, describe/it in Playwright). Match
   indentation, naming conventions, and label placement.
3. **Use step annotations** (if the project uses them — e.g., By() in
   Ginkgo, test step markers in BDD frameworks) for human-readable test
   flow documentation.
4. **Use the project's test infrastructure.** Call the project's test
   abstractions for all system interactions. Do not create ad-hoc HTTP
   clients, CLI wrappers, or API calls.
5. **Use test utilities.** Use the project's constants (timeouts, polling
   intervals, resource type strings). Do not hardcode values.
6. **Use async polling.** Use the project's async waiting mechanism
   (e.g., Eventually/Consistently in Ginkgo, polling helpers in pytest,
   expect with toPass/polling in Playwright) for any operation that may
   not complete immediately. Never use fixed delays (e.g., time.Sleep,
   asyncio.sleep, page.waitForTimeout).
7. **Follow test isolation patterns.** Generate unique test IDs using the
   project's mechanism. Use those IDs for resource names. Ensure cleanup
   happens via the project's teardown hooks or deferred functions.
8. **Apply labels/tags.** Follow the label convention from the context
   document.

For the suite file (typically Task 1):
- Follow the reference suite's lifecycle hook structure exactly (use the
  actual hook names discovered during `/ingest`)
- Start only the auxiliary services the plan identified as needed (if any)
- Use the same test infrastructure initialization pattern
- Use the same login/auth pattern

#### 3c: Run Tests

Run the e2e tests scoped to the new suite. Use the scoped execution
command from the **E2E Test Execution** section of `01-context.md`.

If tests fail, diagnose **where** the problem is before fixing:

| Diagnosis | Symptom | Action |
|-----------|---------|--------|
| **Test code is wrong** | Wrong method call, bad assertion, incorrect setup, wrong import | Fix the test code |
| **Test expectation is wrong** | Feature behaves differently than the AC implies | Verify against the AC — if the AC is ambiguous, note in report and escalate to user |
| **Feature has a defect** | Feature doesn't match its AC — a genuine bug | Note as a discovery in the implementation report — do NOT fix the feature (out of scope). The test may need to be adjusted to skip or xfail if the defect blocks it. |
| **Test infrastructure limitation** | The project's test abstractions don't expose a method needed for the scenario | If a simple helper within the test file suffices, write it. If a test infrastructure change is needed, escalate — that's out of scope. |
| **Environment issue** | Services not running, VM unavailable, network error | Report to user — this is not a test code problem |

#### 3d: Lint and Format

Before committing, run the fast quality checks on the files changed by
this task. Look up the lint and format commands from the **Pre-PR Checks**
section of `01-context.md` (entries labeled "lint", "format", "vet", or
similar).

Run them scoped to the affected files or packages where possible. Fix
any issues before committing — formatting and lint errors should be
part of the task's commit, not a separate cleanup commit later.

If the lint tool reports errors and all error locations are in files
you did not modify in this task, the errors are from pre-existing code
— skip the lint for this commit and note the skip in the implementation
report (Deviations section). If errors appear in files you changed, fix
them before committing. The full validation suite in `/validate` will
catch any remaining issues once all tasks are complete.

Do not run the full validation suite here — save expensive checks
for `/validate`.

#### 3e: Code Review

Stage the task's changes first — the review and commit steps both
operate on the staged diff:

```bash
git add {specific files}
```

Then run a code review on the staged changes. The review method is
discovered, not hardcoded — use the first tier that applies:

**Tier 1: Project-defined review tooling.** Check the project's
`AGENTS.md` or `CLAUDE.md` for automated code review tooling — CLI
commands or scripts that run a review. If review tooling is found, run it.

**Tier 2: Independent review agent.** If no project-specific review
tooling exists, spawn a code review subagent with a fresh context
window. Give it:

- The project's `AGENTS.md` / `CLAUDE.md` and test documentation
- The staged diff for this task (`git diff --cached`)
- The reference suite files for pattern comparison
- The test scenarios being implemented (from the plan task)

Do **not** give it the implementing agent's reasoning or conversation
history — the value comes from independent eyes.

The subagent should review as a senior QE engineer familiar with the
project's testing conventions, focusing on: correct test infrastructure
usage, assertion completeness, anti-patterns (hardcoded sleeps, brittle
selectors, missing cleanup), label conventions, and test isolation.

**Tier 3: Structured self-review.** If the runtime does not support
spawning subagents, fall back to a structured self-review. Re-read the
staged diff and check for:

- Anti-patterns: hardcoded sleeps, shared mutable state, missing cleanup
- Test infrastructure bypass: direct API calls instead of project-provided abstractions
- Missing async polling: synchronous assertions on async operations
- Hardcoded values: inline strings/numbers instead of constants
- Pattern drift: deviations from the reference suite's conventions
- Missing labels: tests without CI-filtering labels

**Triage findings.** Evaluate each finding on its technical merit.
Fix findings that add value. Dismiss findings that don't with a brief
rationale. If any fixes were applied, re-stage the affected files before
proceeding to commit. Note any dismissed findings in the implementation
report (Discoveries section).

#### 3f: Commit

The changes are already staged from Step 3e. Create the commit:

```bash
git commit -m "{JIRA-KEY}: {task description}"
```

Follow the commit format from the **Commit Format** section of
`01-context.md`. The commit message must:
- Use the discovered format
- Describe what the tests verify, not the development journey
- Be independently meaningful

If the commit fails (e.g., rejected by pre-commit hooks), diagnose and
fix the issue before proceeding to the sync step.

#### 3g: Sync with Base

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

Check whether new commits exist on the base branch:

```bash
git rev-list --count HEAD..origin/{base}
```

If the count is 0, skip the rebase/merge and proceed to Step 3h.

If new commits exist, check whether a PR has already been created by
looking for `.artifacts/e2e/{jira-key}/publish-metadata.json`.

**If no PR exists yet**, rebase:

```bash
git rebase origin/{base}
```

**If a PR already exists**, merge instead:

```bash
git merge origin/{base}
```

If the operation applies cleanly, re-run the task's tests to confirm
they still pass against the updated base. If tests fail, diagnose using
the failure routing in Step 3c.

**If there are conflicts:**

1. Stop and report the conflicting files to the user
2. Show the conflict markers so the user can see what's colliding
3. Offer to resolve the conflicts — describe what you would do
4. Proceed only after the user approves the resolution (or resolves it
   themselves)
5. After resolution, run `git rebase --continue` or commit the merge
   resolution as appropriate, then re-run the task's tests

#### 3h: Update Plan

Mark the task as completed in `02-plan.md`:
- Change `Pending` to `Done`

Update the status immediately after each task, not in bulk at the end.
This is the checkpoint that allows the session to resume correctly if
interrupted.

### Step 4: Deviation Rules

During test implementation, you may encounter unexpected situations:

| Situation | Action | Approval |
|-----------|--------|----------|
| Feature defect found — test reveals a bug in the [DEV] implementation | Note in report as a discovery. Adjust test to document expected behavior (may xfail or skip with reason). Do NOT fix the feature. | Auto |
| Test infrastructure doesn't expose needed method | Write a local helper within the test file if simple. If a test infrastructure change is needed, escalate. | Auto (local helper) / Required (infrastructure change) |
| Test scenario is significantly simpler than planned | Note in report, continue | Auto |
| Test scenario is significantly more complex than planned | **Stop and ask the user** — the story may need re-scoping | Required |
| Reference suite pattern doesn't apply to this scenario | Adapt minimally, note deviation in report | Auto |
| Story guidance contradicts current system behavior | **Stop and ask the user** | Required |

### Step 5: Write Reports

After all tasks are complete (or if interrupted), write:

**Test report** (`.artifacts/e2e/{jira-key}/03-test-report.md`):

```markdown
# E2E Test Report — {jira-key}

## Tests Written

| Test File | Scenarios | Acceptance Criteria |
|-----------|-----------|---------------------|
| {path} | {count} | {which ACs} |

## Scenario Summary

| Scenario | Description | Labels |
|----------|-------------|--------|
| {name} | {what it validates} | {labels} |

## Test Infrastructure Used

| Method / Abstraction | Purpose |
|---------------------|---------|
| `{method}` | {what it does} |

## Auxiliary Services

{Which services must be running for these tests, if any. If the services
 are self-starting, note that. If tests run against a pre-existing
 environment: "Tests run against {environment}."}

## Notes

{Any qualitative observations about test coverage, gaps, or patterns.}
```

**Implementation report** (`.artifacts/e2e/{jira-key}/04-impl-report.md`):

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

{Any deviations from the test plan, with rationale.
 If none: "No deviations from the test plan."}

## Discoveries

{Notable findings during test implementation:
 - Feature defects found (bugs in the [DEV] implementation)
 - Test infrastructure gaps (missing methods or capabilities)
 - Missing test infrastructure
 - Pre-existing test issues in adjacent suites
 If none: "No notable discoveries."}

## Status

{Complete / Incomplete — if incomplete, note which tasks remain and why.}
```

## Output

- Test files in the source repo (on the feature branch)
- Incremental commits (following the project's commit format)
- `.artifacts/e2e/{jira-key}/02-plan.md` (updated with task status)
- `.artifacts/e2e/{jira-key}/03-test-report.md`
- `.artifacts/e2e/{jira-key}/04-impl-report.md`

## When This Phase Is Done

Report your results:
- Tasks completed and their commits
- Test scenarios written with AC coverage summary
- Any deviations from the plan
- Any discoveries (especially feature defects)
- Overall implementation status

Then **re-read the controller** (`controller.md`) for next-step guidance.
