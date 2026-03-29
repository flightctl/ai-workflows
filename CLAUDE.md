# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reusable AI coding workflows (plain markdown, no IDE-specific syntax) installable into Cursor, Claude Code, and Gemini CLI. Each workflow is a self-contained directory with phases that guide an AI agent through a structured process (e.g., bugfix: assess -> reproduce -> diagnose -> fix -> test -> review -> document -> pr).

## Architecture

Every workflow directory follows this structure:
- `SKILL.md` — required entry point (YAML frontmatter with `name` + `description`). Keep under 30 lines.
- `guidelines.md` — behavioral rules, principles, hard limits, escalation criteria
- `skills/` — one markdown file per phase with detailed steps
- `skills/controller.md` — optional phase dispatcher managing transitions between phases
- `commands/` — thin wrappers that invoke the controller (or SKILL.md) for a specific phase

The installer (`install.sh`) auto-discovers any root-level directory containing a `SKILL.md`. No script changes needed when adding a workflow.

All internal file references use **relative paths from the file's own location** (e.g., `commands/*.md` reference `../skills/controller.md`). This is critical because workflows are consumed via symlinks.

## Workflows

- **bugfix** — systematic bug resolution (assess, reproduce, diagnose, fix, test, review, document, pr). Used in FlightControl projects.
- **docs-writer** — documentation creation (gather, plan, draft, validate, apply, mr). Used in edge-manager downstream docs.
- **triage** — bulk Jira bug triage with AI categorization and HTML reports.
- **skill-reviewer** — meta-workflow auditing AI skill directories against quality dimensions.

## Install / Uninstall

```bash
./install.sh <cursor|claude|gemini|all> [--workflows wf1,wf2] [--project [path]]
./uninstall.sh <all|cursor|claude|gemini> [--workflows wf1,wf2] [--project [path]]
./install.sh --list    # show available workflows
```

- User-level (default): symlinks into `~/.cursor/skills/`, `~/.claude/CLAUDE.md`, or `~/.gemini/skills/`
- Project-level (`--project`): symlinks into the project's `.cursor/`, `.claude/`, or `.gemini/` directory
- The repo itself is symlinked to `~/.ai-workflows/`

## Testing Changes

1. `./install.sh cursor` (or `all`) — verify auto-discovery picks up your workflow
2. Reference `@your-workflow` in Cursor or invoke in Claude Code
3. Run through at least one phase to confirm dispatch works
4. `./uninstall.sh && ./install.sh cursor` — verify clean teardown/reinstall

## Key Conventions

- Workflow content is plain markdown — no IDE-specific syntax
- Don't duplicate content between `SKILL.md`, `guidelines.md`, and `controller.md`
- Controllers never auto-advance between phases — always wait for user confirmation
- Phase skills end by reporting findings and re-reading the controller for next-step guidance
- IDE integration files (`.cursor-plugin/`, `.claude-plugin/`) live at the repo root, not inside workflows
