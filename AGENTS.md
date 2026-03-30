# AGENTS.md

This file provides guidance to AI coding assistants when working with this repository.

## Project Overview

This repository contains reusable AI coding workflows that can be installed globally or per-project in any environment (Cursor, Claude Code, Gemini). Each workflow is a self-contained directory with structured markdown files that AI agents can read and execute.

**Current workflows:**
- **bugfix** — Systematic bug resolution (assess, reproduce, diagnose, fix, test, review, document, pr)
- **docs-writer** — Documentation creation workflow
- **triage** — Bulk Jira bug triage with AI-driven categorization and HTML reports
- **skill-reviewer** — Meta-workflow that audits AI skill directories

## Architecture

### Workflow Structure

Every workflow follows this canonical structure:

```
workflow-name/
  SKILL.md              # Entry point with YAML frontmatter (name, description)
  guidelines.md         # Behavioral rules: principles, hard limits, safety, quality
  README.md             # Human-readable documentation
  skills/
    controller.md       # Optional phase dispatcher
    phase-name.md       # Implementation for each phase
  commands/
    phase-name.md       # Thin wrappers that invoke controller or SKILL.md
```

**Key architectural principles:**
1. **Auto-discovery**: Any directory with `SKILL.md` is automatically discovered by the installer
2. **Progressive disclosure**: SKILL.md is thin (under 30 lines), details live in guidelines.md and skills/
3. **Relative paths**: All file references must be relative to the file's location (for symlink compatibility)
4. **Phase-based execution**: Most workflows operate through discrete phases with explicit transitions

### File Reference Conventions

Critical for symlink resolution:
- `commands/*.md` reference controller as `../skills/controller.md` or `../SKILL.md`
- `skills/controller.md` references sibling skills as `phase-name.md` (not `skills/phase-name.md`)
- `SKILL.md` references `guidelines.md` and `skills/controller.md` (same directory)

### Artifact Management

Workflows write outputs to `.artifacts/{workflow-name}/{context}/`:
- **bugfix**: `.artifacts/bugfix/{issue-number}/` (root-cause.md, reproduction.md, etc.)
- **triage**: `.artifacts/triage/{project}/` (issues.json, analyzed.json, report.html)
- **skill-reviewer**: `.artifacts/skill-reviewer/{skill-name}/` (review.md)

## Prerequisites

### Required for All Workflows
- Git (for version control operations)

### Workflow-Specific Dependencies
- **bugfix**: GitHub CLI (`gh`) — for PR queries and creation
- **triage**: Jira MCP server — configured and authenticated for Jira API access
- **docs-writer**: GitLab CLI or API access (for merge request creation)

## Installation System

### install.sh

The installer uses auto-discovery to find all workflows and creates symlinks:

```bash
# User-level (all workflows)
./install.sh cursor                    # ~/.cursor/skills/
./install.sh claude                    # ~/.claude/CLAUDE.md + ~/.claude/skills/
./install.sh gemini                    # ~/.gemini/skills/
./install.sh all                       # All environments

# Selective workflows
./install.sh cursor --workflows bugfix,triage

# Project-level
./install.sh cursor --project /path/to/proj    # .cursor/skills/
./install.sh claude --project /path/to/proj    # .claude/CLAUDE.md
```

**Auto-discovery mechanism**: The script scans for `*/SKILL.md` files at repo root. No script changes needed when adding workflows.

### uninstall.sh

Mirrors install.sh structure with removal logic.

### Claude Code Integration

For Claude Code, the installer:
1. Adds workflow references to `CLAUDE.md` (or `.claude/CLAUDE.md` for project-level)
2. Symlinks workflows into `~/.claude/skills/` for slash command discovery
3. Removes stale references (old controller.md paths) to avoid duplicates

## Quality Assurance

### Cursor Rules (.cursor/rules/)

**skill-review.mdc**: Deep review of AI skill directories
- Evaluates 8 dimensions: orchestration, sequencing, schemas, cognitive load, clarity, documentation, naming, error handling
- Severity levels: CRITICAL, HIGH, MEDIUM, LOW
- Invoked on-demand (not automatic)
- Use the **skill-reviewer** workflow (`/review`) for automated analysis

## Development Workflows

### Adding a New Workflow

1. Create directory at repo root: `new-workflow/`
2. Add required files:
   ```bash
   new-workflow/SKILL.md          # With YAML frontmatter
   new-workflow/guidelines.md
   new-workflow/README.md
   new-workflow/skills/           # Phase implementations
   new-workflow/commands/         # Command wrappers
   ```
3. Test: `./install.sh cursor && ./uninstall.sh`
4. Submit PR

**SKILL.md frontmatter template:**
```yaml
---
name: workflow-name
description: >-
  Brief description. Include trigger terms so the agent knows when to use it.
  Activated by commands: /command1, /command2.
---
```

### Modifying Workflows

When editing workflow files:
1. Read the entire skill first (SKILL.md, guidelines.md, all skills/, commands/)
2. Maintain relative path conventions
3. Don't duplicate content between SKILL.md and skills/ — use progressive disclosure
4. Use the **skill-reviewer** workflow to validate changes after edits

### Testing Changes

```bash
# Install locally
./install.sh cursor

# Test in Cursor
@workflow-name/commands/phase-name

# Clean reinstall to verify teardown
./uninstall.sh && ./install.sh cursor
```

**Quality Review**: After modifying workflow files, use the **skill-reviewer** workflow to validate structure, sequencing, schema consistency, cognitive load, instruction clarity, documentation alignment, naming conventions, and error handling.

## Workflow-Specific Notes

### bugfix

- Unattended mode available: `skills/unattended.md` (chains diagnose → fix → test → review)
- Uses git commands extensively (blame, log, status, diff)
- Creates regression tests during `/test` phase
- Integrates with GitHub CLI for PR creation

### triage

- Requires Jira MCP server configured and authenticated
- Generates self-contained HTML reports with Material Design styling
- Read-only: never modifies Jira issues
- `/assess` is for single-issue triage (not part of bulk pipeline)
- Recently resolved bugs fetched for regression matching

### skill-reviewer

- Single-phase workflow (no controller)
- Read-only review (fixing findings is separate from review phase)
- Must read all files in target skill before forming opinions

### docs-writer

- Converts Jira tickets or GitHub issues into AsciiDoc documentation
- Runs Vale for style compliance before applying changes
- Creates GitLab merge requests (or GitHub PRs with appropriate CLI)
- Must get user approval after `/plan` phase before proceeding to `/draft`

## Common Commands

**Note**: This repository contains AI workflow definitions (markdown files), not traditional code requiring build/test commands. "Testing" refers to verifying workflow execution and symlink installation.

### Installation
```bash
./install.sh all                           # Install all workflows, all environments
./install.sh cursor --workflows bugfix     # Install specific workflow
./install.sh --list                        # List available workflows
./uninstall.sh cursor                      # Remove Cursor installation

# Verify installation
ls -la ~/.cursor/skills/                   # Check Cursor symlinks
ls -la ~/.claude/skills/                   # Check Claude Code symlinks
cat ~/.claude/CLAUDE.md                    # Verify Claude Code references
```

### Git Workflow
```bash
git status                                 # Check staged changes
git diff                                   # Review changes
git log --oneline -10                      # Recent commits
git blame <file>                           # Trace file history
```

### GitHub CLI (for bugfix)
```bash
gh pr list --state open
gh pr create --title "..." --body "..."
gh pr view 123
gh issue view <num> --repo <owner/repo>    # For docs-writer
gh pr diff <num> --repo <owner/repo>       # For docs-writer
```

### Jira MCP (for triage, docs-writer)
```bash
# Invoked via MCP tools, not CLI directly
# Example JQL: "project = EDM AND issuetype = Bug AND resolution = Unresolved"
```

### Vale (for docs-writer)
```bash
vale path/to/file.adoc    # Style/terminology validation
```

## Key Constraints

1. **No IDE-specific syntax**: All workflow content is plain markdown
2. **Relative paths only**: For symlink compatibility across install scopes
3. **Progressive disclosure**: SKILL.md stays under 30 lines
4. **Never auto-advance**: Workflows wait for user input between phases
5. **Artifact persistence**: All significant outputs saved to .artifacts/
6. **Read-only reviews**: skill-reviewer never modifies target skill files during review

## File Organization

```
ai-workflows/
├── bugfix/                    # Workflows (auto-discovered via SKILL.md)
├── docs-writer/
├── triage/
├── skill-reviewer/
├── install.sh                 # Installer with auto-discovery
├── uninstall.sh              # Removal script
├── .cursor-plugin/           # Cursor marketplace files
├── .claude-plugin/           # Claude Code marketplace files
├── AGENTS.md                 # AI assistant guidance (this file)
├── CLAUDE.md                 # Claude Code reference (points to AGENTS.md)
├── CONTRIBUTING.md           # Workflow development guide
└── README.md                 # User-facing documentation
```

## Path to Production

When a workflow invokes commands that could affect shared systems:
- **Git operations**: Always verify with `git status` before destructive operations
- **PR/MR creation**: Confirm branch and base before pushing (bugfix uses GitHub, docs-writer uses GitLab)
- **Jira queries**: Triage is read-only, but always confirm project key before bulk operations
- **Documentation changes**: Run Vale validation before applying changes to repository files (docs-writer)
