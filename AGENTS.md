# AGENTS.md

This file provides guidance to AI coding assistants when working with this repository.

## Project Overview

This repository contains reusable AI coding workflows that can be installed globally or per-project in any environment (Cursor, Claude Code, Gemini). Each workflow is a self-contained directory with structured markdown files that AI agents can read and execute.

**Current workflows:**
- **ai-ready** — Codebase scanning and AGENTS.md generation (update)
- **bugfix** — Systematic bug resolution (assess, reproduce, diagnose, fix, test, review, document, pr)
- **code-review** — AI-driven code review with human-in-the-loop decisions (start, continue, clean)
- **cve-fix** — Automated CVE remediation from Jira tickets (start, patch, validate, pr, backport, close)
- **design** — Design-and-decompose workflow (ingest, research, draft, decompose, revise, publish, respond, sync)
- **docs-writer** — Documentation creation workflow (gather, plan, draft, validate, apply, mr)
- **e2e** — Story-to-tests workflow for [QE] stories (ingest, plan, revise, code, validate, publish, respond)
- **implement** — Story-to-code workflow (ingest, plan, revise, code, validate, publish, respond)
- **kcs** — KCS Solution article workflow (gather, draft, validate, handoff)
- **prd** — Requirements-to-PRD workflow (ingest, clarify, draft, revise, publish, respond)
- **skill-reviewer** — Meta-workflow that audits AI skill directories
- **triage** — Bulk Jira bug triage with AI-driven categorization and HTML reports

## Architecture

### Workflow Structure

Every workflow follows this canonical structure:

```text
workflow-name/
  SKILL.md              # Entry point with YAML frontmatter (name, description)
  guidelines.md         # Behavioral rules: principles, hard limits, safety, quality
  README.md             # Human-readable documentation (prerequisites, artifacts, usage)
  skills/
    controller.md       # Optional phase dispatcher
    phase-name.md       # Implementation for each phase
  commands/
    phase-name.md       # Thin wrappers that invoke controller or SKILL.md
  scripts/              # Optional — deterministic operations invoked by skills
  prompts/              # Optional — prompt templates for sub-agent delegation
```

**Key architectural principles:**
1. **Auto-discovery**: Any directory with `SKILL.md` is automatically discovered by the installer
2. **Progressive disclosure**: SKILL.md is thin (under 30 lines), details live in guidelines.md and skills/
3. **Relative paths**: All file references must be relative to the file's location (for symlink compatibility)
4. **Phase-based execution**: Most workflows operate through discrete phases with explicit transitions
5. **Shared resources**: Cross-cutting concerns live in `_shared/` and are referenced by relative path

### Shared Resources (`_shared/`)

```text
_shared/
  review-protocol.md              # Shared code review criteria, finding format, severity definitions
  recipes/
    self-review-gate.md           # Pre-PR self-review quality gate (used by bugfix, implement, e2e, cve-fix)
```

Recipes are self-contained, parameterized procedures that workflows reference via relative path (e.g., `../../_shared/recipes/self-review-gate.md` from `skills/`).

### File Reference Conventions

Critical for symlink resolution:
- `commands/*.md` reference `../skills/controller.md` (if workflow has a controller) or `../SKILL.md` (for workflows without a controller) or `../skills/phase-name.md` (direct phase reference)
- `skills/controller.md` (when present) references sibling skills as `phase-name.md` (not `skills/phase-name.md`)
- `SKILL.md` references `guidelines.md` and optionally `skills/controller.md` (same directory)

## Key Constraints

1. **No IDE-specific syntax**: All workflow content is plain markdown
2. **Relative paths only**: For symlink compatibility across install scopes
3. **Progressive disclosure**: SKILL.md stays under 30 lines
4. **No auto-advance in attended mode**: Workflows wait for user input between phases unless an explicit unattended mode is documented for that workflow
5. **Artifact persistence**: All significant outputs saved to `.artifacts/{workflow-name}/{context}/`
6. **Read-only reviews**: skill-reviewer never modifies target skill files during review

## Installation

Install with `./install.sh <target>` (targets: `cursor`, `claude`, `gemini`, `all`). See README.md for scopes, options, and uninstall instructions.

## Development

See CONTRIBUTING.md for workflow structure conventions, path rules, testing, and installation internals.

## File Organization

```text
ai-workflows/
├── _shared/                   # Cross-cutting shared resources
│   ├── review-protocol.md     # Shared code review criteria and finding format
│   └── recipes/
│       └── self-review-gate.md  # Pre-PR self-review quality gate
├── ai-ready/                  # Workflows (auto-discovered via SKILL.md)
├── bugfix/
├── code-review/
├── cve-fix/
├── design/
├── docs-writer/
├── e2e/
├── implement/
├── kcs/
├── prd/
├── skill-reviewer/
│   ├── prompts/
│   └── scripts/
├── triage/
├── install.sh                 # Installer with auto-discovery
├── uninstall.sh              # Removal script
├── AGENTS.md                 # AI assistant guidance (this file)
├── CLAUDE.md                 # Claude Code reference (points to AGENTS.md + install.sh appends here)
├── CONTRIBUTING.md           # Workflow development guide
├── README.md                 # User-facing documentation
└── .gitignore                # Excludes .cursor/, .claude/, .artifacts/, etc.
```

## Path to Production

When a workflow invokes commands that could affect shared systems:
- **Git operations**: Always verify with `git status` before destructive operations
- **PR/MR creation**: Confirm branch and base before pushing
- **Jira writes**: Only cve-fix `/close` and design `/sync` write to Jira; both require explicit approval
- **Documentation changes**: Run Vale validation before applying changes to repository files
