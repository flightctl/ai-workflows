---
name: validation-gate
version: 0.1.0
---
# Recipe: Validation Gate

A pre-commit quality gate that discovers and runs the project's
CI-equivalent build, test, lint/format, and codegen checks. Used by
workflows that commit or push code (for example bugfix `/pr` and
`/feedback`) so agents do not invent partial or file-scoped substitutes.

## Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| PROJECT_DIR | No | Directory of the target project (where `AGENTS.md` / `Makefile` / `package.json` live). Run all discovered commands from this directory. | Current working directory |
| SCOPE | No | What to run: `full` (build, tests, lint/format, and codegen when inputs changed) or `lint` (lint/format discovery only). | `full` |

## Procedure

### Step 1: Discover Commands

Work from `{PROJECT_DIR}`. Discover validation commands using this
**priority order** — use the first source that documents a usable command
for each category you need (build, test, lint/format, codegen):

1. **`AGENTS.md`** (or `CLAUDE.md` if it points at the same guidance) —
   prefer the exact CI-equivalent commands the project documents.
2. **`Makefile`** — look for `lint`, `fmt`, `test`, `build`, `check`, or
   similarly named targets.
3. **`package.json` scripts** — look for `lint`, `test`, `build`, `check`,
   or similarly named scripts.

If **no** source documents commands for a required category under the
chosen `SCOPE`, ask the user before proceeding. Do not invent commands
and do not fall back to guessed language-specific defaults (for example
`eslint`, `golint`, or `ruff` inferred only from file extensions).

### Step 2: Run the Full Documented Sequence

**Gate: do not commit or push until all checks pass.**

Run the discovered CI-equivalent sequence for `{SCOPE}`:

- Prefer the **exact** project command (for example `pnpm lint`,
  `make lint`, `make test`) over composing lower-level tools yourself.
- Do **not** substitute partial or file-scoped invocations (for example
  `eslint path/to/file.ts` instead of the project's `lint` script).
- When `SCOPE` is `full`, include build, tests, lint/format, and codegen
  when the project's docs say those apply to the change.

### Step 3: On Failure

If any check fails:

1. Stop.
2. Fix the failure.
3. Re-run this recipe from Step 2.
4. Do not proceed to commit, push, or any later calling-workflow step
   until every required check passes.

### Step 4: Return

Report to the calling workflow:

- Commands discovered and which discovery source provided each
- Commands run and pass/fail
- Any categories skipped (and why)
