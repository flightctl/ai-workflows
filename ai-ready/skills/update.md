---
name: update
description: Scan the codebase, audit AI convention files and create or update AGENTS.md.
---

# Update AI-Readiness

You are making this project AI-ready by ensuring it has accurate, up-to-date AGENTS.md files and a clean set of AI convention files.

## Process

### Step 1: Discover Current State

Check whether an AGENTS.md exists at the project root.

- **If it exists:** Read it in full. This is your baseline — every section is assumed correct unless the codebase proves otherwise.
- **If it does not exist:** You will create one from scratch in Step 3.

Then scan for all AI convention files in the project (one glob search):

```text
**/{.github/copilot-instructions.md,AGENT.md,AGENTS.md,CLAUDE.md,.cursorrules,.windsurfrules,.cursor/rules/**,.windsurf/rules/**,.clinerules,.clinerules/**}
```

Note every file found and its path.

### Step 2: Analyze the Codebase

Gather the information needed to write or update AGENTS.md. Inspect these concrete signals — skip any that don't exist in the project:

- **Directory tree** (top 2–3 levels) — project layout and architecture
- **Package manifests** (package.json, pyproject.toml, Cargo.toml, go.mod, pom.xml, build.gradle, etc.) — dependencies, scripts, build commands
- **CI/CD configs** (.github/workflows/, .gitlab-ci.yml, Jenkinsfile) — build, test, and lint steps as actually run in CI
- **Linting/formatting configs** (.eslintrc, .prettierrc, ruff.toml, .editorconfig, .pre-commit-config.yaml) — code style rules
- **Test directories** (test/, tests/, \_\_tests\_\_/, spec/) — framework, naming conventions, how to run tests
- **Build/task runners** (Makefile, justfile, Taskfile.yml, scripts/) — available commands
- **Container configs** (Dockerfile, docker-compose.yml) — environment setup
- **Entry points** (main.\*, index.\*, src/app.\*) — where execution starts
- **Developer docs** (README.md, CONTRIBUTING.md, DEVELOPMENT.md, HACKING.md) — existing conventions and instructions

Also check recent git history (`git log --oneline -20`) to spot recently changed areas that may need documentation.

Only collect information that is **concrete and verifiable**. Do not infer or assume anything you cannot confirm from the codebase.

If analysis yields fewer than 2 concrete sections worth of content, report that the project has insufficient signals for a useful AGENTS.md and ask the user for guidance before proceeding.

### Step 3: Create or Update AGENTS.md

#### If creating from scratch

Use the section template below. Only include sections where you found concrete, project-specific content. Omit sections that would be empty or generic.

```markdown
# Project Name

One-line description of what this project is.

## Dev Environment

Prerequisites, install steps, environment variables.

## Build

Build commands and what they produce.

## Test

How to run tests: framework, commands, patterns for test file naming/placement.

## Code Style

Linter, formatter, naming conventions, file organization patterns.

## Architecture

Key directories, components, data flow, important abstractions.

## PR and Commit Conventions

Branch naming, commit message format, review process.

## Security

Areas where AI agents should exercise caution (e.g., "auth logic lives in `src/auth/` — changes here require manual review"). Do NOT document internal mechanisms, credentials, token formats, or implementation details of security controls.
```

#### If updating an existing AGENTS.md

Compare what you found in Step 2 against the current content. Focus on what has **changed** or is **missing**. Apply minimal, surgical updates:

- Do NOT rewrite or rephrase sections that are still accurate — leave them exactly as they are
- Preserve existing structure, section ordering, and formatting
- Place new content in the most logical existing section rather than creating new sections
- Remove or update references to files, directories, commands, or dependencies that no longer exist
- Verify every file path mentioned in the existing AGENTS.md still resolves

#### Writing rules

These apply to both creation and updates:

- Write in imperative, second-person voice: "Run X", "Use Y", "See `path/to/file`"
- Include specific file paths and commands from THIS project — no placeholders
- Avoid generic advice ("write tests", "handle errors") — document this project's actual approaches
- Document only discoverable patterns, not aspirational practices
- Reference key files and directories that exemplify important patterns
- Keep it concise: prefer a command over a paragraph
- Include specific examples from the codebase when describing patterns
- Aim for under 500 lines per AGENTS.md file. For monorepos, split project-wide concerns into the root file and package-specific details into nested files rather than writing one large file

#### AGENTS.md format reference

AGENTS.md is standard Markdown with no required fields or structure:

- Any headings work — agents parse the full text
- In monorepos, the closest AGENTS.md to the edited file takes precedence
- Explicit user prompts override AGENTS.md instructions

### Step 4: Audit AI Convention Files

For each AI convention file found in Step 1, choose one action. For directory-based conventions (`.cursor/rules/`, `.windsurf/rules/`, `.clinerules/`), evaluate each file within the directory individually — different files may warrant different actions:

**Keep** — The file serves a tool-specific purpose that AGENTS.md cannot replace. This includes files that are auto-loaded by their respective tools (e.g., `CLAUDE.md` by Claude Code, `.github/copilot-instructions.md` by GitHub Copilot) or files with capabilities AGENTS.md can't express (e.g., `.cursor/rules/` with glob-scoped rules). Merging these into AGENTS.md would lose the tool integration. Leave them untouched.

**Merge** — The file contains generic agent instructions that belong in AGENTS.md. Consolidate its unique content into AGENTS.md, then delete the original file.

**Update** — The file is tool-specific but contains stale or inaccurate content. Update it in place.

**Create** — A useful file is missing. Create it (e.g., nested AGENTS.md for a monorepo subproject).

When merging:

- Show the user what content will be consolidated and which file will be deleted before proceeding
- Before deleting any file, ensure all its unique content is captured in AGENTS.md
- When sources conflict, prefer the most recently modified file
- Deduplicate — do not repeat the same instruction in AGENTS.md and another file

**Monorepo awareness:** If the project uses workspaces (package.json workspaces, pnpm-workspace.yaml, Cargo `[workspace]`, multiple go.mod files), check whether subprojects have their own AGENTS.md. Root AGENTS.md covers project-wide concerns; nested files cover package-specific details. For existing nested AGENTS.md files, apply the same create-or-update logic from Step 3 scoped to the subproject. Recommend creating nested files where they're missing.

### Step 5: Validate

Before finishing, verify **accuracy** and **completeness**.

Accuracy:

- Every file path referenced in AGENTS.md exists in the project
- Every command referenced is runnable (appears in package.json scripts, Makefile, CI config, etc.)
- No contradictions between sections
- No contradictions between AGENTS.md and kept convention files (e.g., `CLAUDE.md`, `.github/copilot-instructions.md`). If a kept file conflicts with AGENTS.md, update the kept file to align — AGENTS.md is the source of truth
- No content duplicated across sections
- Running this skill again would produce no further changes (idempotency check)

Completeness — cross-reference Step 2 findings against the final AGENTS.md:

- If the project has a build system, AGENTS.md documents how to build
- If the project has tests, AGENTS.md documents how to run them
- If the project uses a linter or formatter, AGENTS.md documents the commands
- If the project has CI, AGENTS.md reflects what CI checks
- If the project has environment setup steps, AGENTS.md covers prerequisites

A missing section is acceptable only when the codebase provides no concrete information for it. If the information exists in the codebase but is absent from AGENTS.md, add it.

Fix any issues you find before proceeding to Step 6.

### Step 6: Report

Present a summary to the user with two parts:

**1. AGENTS.md changes** — What was added, modified, or removed. If created from scratch, summarize the sections written and key content in each.

**2. AI convention file audit** — For every AI convention file found (and any created), list the file, what action was taken, and why.

Example format:

```text
AI convention file audit:
- AGENTS.md          → Created (new file with 6 sections)
- .windsurfrules     → Merged (generic instructions moved to AGENTS.md)
- .cursor/rules/     → Kept (contains glob-scoped rules AGENTS.md can't express)
- packages/api/      → Recommended: add nested AGENTS.md for API-specific conventions
```

Only include tool-auto-loaded files (e.g., `CLAUDE.md`, `.github/copilot-instructions.md`) in the report if they have issues — stale content, contradictions with AGENTS.md, or other findings worth flagging.

## Output

- AGENTS.md created or updated at the project root
- AI convention files merged, updated, or flagged as recommendations
- Summary of all changes presented to the user
- All changes are applied and ready to commit

## When Done

Present your report to the user. All changes should already be applied and ready to commit.
