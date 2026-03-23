---
name: ai-ready
description: Scans a codebase structure, audits AI convention files, and creates or updates AGENTS.md with project-specific build commands, test patterns, and coding standards. Use when onboarding a project for AI agents, setting up AI instructions, after significant codebase changes, or to audit AI convention files like AGENTS.md or .cursorrules.
---
# AI-Ready Workflow

Ensure a project is AI-ready by maintaining accurate AGENTS.md files.

## Quick Start

Run `/update` to execute the full workflow. Executable without opening other files:

1. Check if `AGENTS.md` exists at the project root; read it as baseline if present. Scan for all AI convention files: `**/{.github/copilot-instructions.md,AGENT.md,AGENTS.md,CLAUDE.md,.cursorrules,.windsurfrules,.clinerules,.cursor/rules/**,.windsurf/rules/**,.clinerules/**}`
2. Analyze the codebase — inspect package manifests (`cat package.json | jq '.scripts'`), CI configs, test dirs, linter configs, recent git history (`git log --oneline -20`)
3. Create or surgically update `AGENTS.md`:

```markdown
# my-project

REST API for user management.

## Build

`npm run build` — compiles TypeScript to dist/.

## Test

`npm test` — runs Jest. Tests live in `src/__tests__/`, named `*.test.ts`.

## Code Style

ESLint + Prettier. Run `npm run lint` before committing.
```

4. Audit each AI convention file: **keep** (tool-specific, e.g. `.cursor/rules/`), **merge** (generic instructions → AGENTS.md, then delete), **update** (stale content), or **create** (missing nested AGENTS.md in monorepo)
5. Validate: verify every file path and command in AGENTS.md resolves — `test -f <path>` for files, check `package.json` scripts for commands; fix before reporting
6. Report changes and audit results

## Example Session

```text
User: "Make this project AI-ready"

/update → scans codebase, finds package.json, pytest.ini, .github/workflows/ci.yml
        → creates AGENTS.md (Build, Test, Code Style, Architecture)
        → .cursorrules → kept (glob-scoped rules)
        → .github/copilot-instructions.md → merged into AGENTS.md
        → validates all paths and commands
        → "Created AGENTS.md (4 sections), merged 1 file, kept 1 file"
```

## Phase Transitions

`/update` is a single-phase workflow with built-in validation:

- Scan completes → write or update AGENTS.md
- Audit each AI convention file → keep, merge, update, or create
- Validate all referenced paths and commands exist → if validation fails, fix before reporting
- Report → present changes and audit results to the user

## File Layout

```text
ai-ready/
  SKILL.md              # This file — workflow overview and routing
  guidelines.md         # Principles, limits, safety, quality standards
  README.md             # User-facing documentation
  commands/
    update.md           # /update command — loads guidelines + skill
  skills/
    update.md           # The scan and update skill (detailed steps)
```
