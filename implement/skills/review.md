---
name: review
description: Apply user-supplied feedback to the current local implementation.
---

# Review Skill

You are a principal software engineer. Your job is to apply one piece of
direct user feedback to the current local implementation, run scoped checks,
and commit.

## Your Role

Handle a single feedback request. Read the user's feedback from the command
context, assess it against the story scope and documented requirements, apply
the change, run the affected checks, and commit. Each invocation is
self-contained — there is no open-review session or session artifact.

## Critical Rules

- **One request per invocation.** Apply only the feedback in this command's
  context. The user may invoke `/implement:review` again for more feedback.
- **No full validation.** Run affected tests and scoped lint/format checks.
  Do not run the full test suite, coverage analysis, full regression checks,
  or the self-review gate. The user runs `/validate` after feedback is
  complete.
- **No push, no PR interaction.** Work on the local branch only. Do not
  fetch or post PR comments, push changes, or change `/respond`.
- **No session artifacts.** Do not create a review-session file, open-review
  flag, or any artifact beyond the commit itself.
- **Preserve unrelated work.** Do not modify, stage, or commit changes that
  belong to the user or to other phases. If pre-existing uncommitted changes
  exist, track them and keep them untouched.
- **Jira is read-only.** Do not modify Jira. If feedback supersedes a
  documented requirement, the user must update the canonical source.

## Process

### Step 1: Read Context and Check Entry Conditions

Determine the issue key. An explicit key in the command context takes
priority. Otherwise, use the key from the current active implement
workflow context if exactly one is established and consistent. If no
key is available, multiple `.artifacts/implement/` directories exist
without a clear active context, or sources conflict, stop and ask the
user to specify the issue key. Do not pick an arbitrary artifact
directory, even if only one exists — it may be from a prior session.

Read:
1. `.artifacts/implement/{issue-key}/02-plan.md` — required. If it does not
   exist, stop and recommend `/plan` then `/code`.
2. `.artifacts/implement/{issue-key}/01-context.md` — story context and
   validation profile.

Check blocking conditions:

1. If `02-plan.md` contains a `## Pending Scope Decision` section or records
   an unmerged prerequisite dependency, stop and recommend `/revise`. Do not
   apply feedback while a scope decision is pending.

2. Verify the current branch is a feature branch, not `main` or `master`:

   ```bash
   git branch --show-current
   ```

   If on `main` or `master`, stop and recommend creating or checking out
   a feature branch first.

3. If the user did not provide feedback in the command context, stop
   and explain that this phase requires direct feedback to apply. Do
   not search for or fetch external feedback.

4. Record pre-existing worktree state using NUL-delimited output for
   stable path parsing, including all untracked files and submodules:

   ```bash
   git status --porcelain -z --untracked-files=all --ignore-submodules=none
   ```

   Parse the NUL-delimited entries. For each entry, record the two-character
   status code and path. For renames (`R`) and copies (`C`), record both
   the source and destination paths. These are pre-existing changes that
   this phase must not touch. If the command fails, stop and report.

### Step 2: Assess Feedback

Assess the user's feedback against:
- Acceptance criteria in `01-context.md`
- Approved plan in `02-plan.md`
- Scope Baseline (when present in the plan)
- Existing code contracts and project conventions

**Documented-requirement conflict rule.** Read and follow the
documented-requirement conflict policy in `../guidelines.md`. If the
feedback conflicts with a documented requirement, stop before changing
code: identify the source and requirement, explain the conflict, and
ask the user. If the requirement is superseded, direct the user to
update the canonical source, then `/ingest` to refresh `01-context.md`
(ingest preserves old context and shows a diff), then `/revise` to
align the plan before coding resumes. If the requirement is kept,
explain the rationale. Tests follow the resolved requirement.

If the feedback is ambiguous, materially expands scope, or requires a
pending scope decision, follow the existing clarification and `/revise`
paths instead of silently applying it. Explain the technical reasoning
if declining or adjusting the requested approach.

### Step 3: Apply the Change

For an in-scope change with no unresolved conflicts:

1. Identify the files that will need modification or creation.
   Establish the repository root (`git rev-parse --show-toplevel`)
   and the intended base directory for relative paths (from command
   context; ask the user if ambiguous). Normalize each target path:
   physically resolve the parent directory (following symlinks in
   parent components, including `..`) via `os.path.realpath` on the
   parent, then append the final path component unchanged — this
   preserves the final entry for `os.path.lexists` and symlink
   detection while correctly resolving `..` across symlinks. Compute
   the repo-root-relative path and verify it stays within the repo
   using path-component containment (the relative path must not start
   with a `..` component — check `os.path.relpath(resolved, root)`
   does not begin with `../`; note `..notes` is a valid filename, not
   an escape). Do not damage leading-dot filenames (`.env`). If a
   target resolves outside the repo, stop and report. If the final
   component is a symlink and the intended edit target is ambiguous
   (the link entry vs its referent), ask the user; the actual content
   target must independently pass scope/dirty/ignored checks. Run all
   git commands from the repository root with normalized paths.
2. **Pre-edit isolation check.** Before making any edits:

   a. Compare every target path against the pre-existing paths from
      Step 1 in both directions: exact path match, a pre-existing path
      is a path-component prefix of the target (dirty `mysub` blocks
      `mysub/file.go`), OR the target is a path-component prefix of a
      pre-existing path (target `assets` replacing a directory would
      clobber dirty `assets/draft.txt`). Use path-component boundaries
      (`/`), not string prefix (`foo` does not match `foobar`). Include
      both sides of renames. Do not target a directory for replacement —
      it may contain ignored descendants invisible to status and
      check-ignore at the directory level. Expand directory operations
      to explicit file paths; if the user's feedback implies replacing
      a directory, list the affected files and ask for confirmation.

   b. Check for existing ignored files at target paths:

      ```bash
      git check-ignore -- {target paths}
      ```

      If any target path is reported as ignored AND exists on disk
      (check with lexical existence — a file, directory, or dangling
      symlink), stop — it may be user-owned data excluded from version
      control. Do not follow or overwrite an existing ignored symlink.
      A clean tracked file that matches a `.gitignore` pattern is NOT
      an ignored file (default `git check-ignore` without `--no-index`
      correctly excludes tracked files) and is safe to edit. A
      nonexistent path matching an ignore pattern is not pre-existing
      user data, though a later `git add` failure must be reported
      honestly without `--force`. If `git check-ignore` exits with an
      error (exit code other than 0 or 1, e.g., 128 for paths inside
      a submodule), stop and report the error — do not treat the error
      as "not ignored." For targets inside a submodule, the
      superproject cannot verify ignored status; ask the user.

   If any check finds a conflict, **stop and report** before editing.
   Explain which paths conflict and how to resolve (handle the
   pre-existing work via `/code` or user-approved `/revise`, then
   re-invoke `/implement:review`).
3. Read every file that will be modified.
4. Edit only what the feedback requires. Keep changes minimal and focused.
5. If the change affects behavior, add or update tests for the changed
   behavior through public interfaces. Follow the same contract-based
   testing standards as `/code`.
6. Preserve all pre-existing uncommitted changes (recorded in Step 1).

### Step 4: Run Affected Tests

Look up the test commands from the **Pre-PR Checks** section of
`01-context.md`. Run the unit test command scoped to the affected
package(s). If integration tests were written or modified, run the
integration test command for the affected packages.

Run each test command as a separate invocation. Fix any failures before
proceeding.

### Step 5: Run Scoped Lint and Format Checks

Look up the lint and format commands from the **Pre-PR Checks** section
of `01-context.md`. Run them scoped to the files changed by this feedback
request. Fix any issues before proceeding.

Do not run the full validation suite — save expensive checks for `/validate`.

### Step 6: Stage and Commit

Stage ONLY the specific files changed by this feedback request,
including any newly created test or code files:

```bash
git add -- {explicit paths changed in Steps 3-5}
```

Verify the staged diff contains only this phase's changes:

```bash
git diff --cached -- {same explicit paths}
```

Then commit using `--only` on the same paths, which creates a commit
from exactly those paths without disturbing other pre-existing staged
content:

```bash
git commit --only -m "{issue-key}: {brief description}" -- {same explicit paths}
```

Use the commit format from the **Commit Format** section of
`01-context.md`. Never use `git add .`, `git add -A`, or `git add -u`
— those would capture pre-existing changes. Never use `git reset` on
user-staged content.

After committing, verify that pre-existing state is preserved using
the same snapshot format as Step 1:

```bash
git status --porcelain -z --untracked-files=all --ignore-submodules=none
```

Compare parsed paths against the Step 1 baseline. All pre-existing
paths must still appear with their original status codes. If any
pre-existing path is missing or its status changed, stop and report.

Do not push.

### Step 7: Report

If no code change was warranted, explain why and do not create an empty
commit. For a request that only changes the implementation plan or
acceptance criteria, direct the user to `/revise`.

Otherwise, report:
- What was changed and why
- Which tests ran and their results
- Which lint/format checks ran and their results
- The commit hash
- Recommend another `/implement:review` call for more feedback, or
  `/validate` when feedback is complete

Note: Any commit made by this phase makes a previous validation report
stale. The user must run `/validate` before `/publish`.

## Output

- Code changes on the local feature branch
- Test additions or updates (if behavior changed)
- One local commit (following the project's commit format)

## When This Phase Is Done

Report your results:
- Change applied and commit hash
- Tests and lint checks run with results
- Recommendation for next step

Then return to the invoking workflow router for completion guidance.
