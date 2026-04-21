# AGENTS.md

This file provides guidance to AI coding assistants when working with this repository.

## Project Overview

This repository contains reusable AI coding workflows that can be installed globally or per-project in any environment (Cursor, Claude Code, Gemini). Each workflow is a self-contained directory with structured markdown files that AI agents can read and execute.

**Current workflows:**
- **ai-ready** — Codebase scanning and AGENTS.md generation (update)
- **bugfix** — Systematic bug resolution (assess, reproduce, diagnose, fix, test, review, document, pr)
- **docs-writer** — Documentation creation workflow
- **triage** — Bulk Jira bug triage with AI-driven categorization and HTML reports
- **skill-reviewer** — Meta-workflow that audits AI skill directories
- **cve-fix** — Automated CVE remediation from Jira tickets (start, patch, validate, pr, backport, close)
- **prd** — Requirements-to-PRD workflow (ingest, clarify, draft, revise, publish, respond)
- **design** — Design-and-decompose workflow (ingest, draft, decompose, revise, publish, respond, sync)
- **kcs** — KCS Solution article workflow (gather, draft, validate, handoff)

## Architecture

### Workflow Structure

Every workflow follows this canonical structure:

```text
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
- `commands/*.md` reference `../skills/controller.md` (if workflow has a controller) or `../SKILL.md` (for workflows without a controller) or `../skills/phase-name.md` (direct phase reference)
- `skills/controller.md` (when present) references sibling skills as `phase-name.md` (not `skills/phase-name.md`)
- `SKILL.md` references `guidelines.md` and optionally `skills/controller.md` (same directory)

### Artifact Management

Workflows write outputs to `.artifacts/{workflow-name}/{context}/`:
- **ai-ready**: No persistent artifacts (writes directly to the target project's AGENTS.md)
- **bugfix**: `.artifacts/bugfix/{issue-number}/` (root-cause.md, reproduction.md, etc.)
- **triage**: `.artifacts/triage/{project}/` (issues.json, analyzed.json, report.html)
- **skill-reviewer**: `.artifacts/skill-reviewer/{skill-name}/` (review.md)
- **cve-fix**: `.artifacts/cve-fix/{context}/` (context.md, patch-log.md, validation-results.md, pr-description.md, backport-log.md, close-report.md)
- **prd**: `.artifacts/prd/{issue-number}/` (01-requirements.md, 02-clarifications.md, 03-prd.md, 04-pr-description.md, 05-review-responses.md)
- **design**: `.artifacts/design/{issue-number}/` (01-context.md, 02-design.md, 03-epics.md, 04-stories/epic-{N}-{slug}.md, 04-stories/epic-{N}/story-{NN}-{slug}.md, 05-coverage.md, 06-pr-description.md, 07-review-responses.md, publish-metadata.json, sync-manifest.json)
- **kcs**: `.artifacts/kcs/{issue-key}/` (01-context.md, 02-kcs-draft.md, 03-handoff-message.md)

## Prerequisites

### Required for All Workflows
- Git (for version control operations)

### Workflow-Specific Dependencies
- **ai-ready**: None (reads codebase, writes AGENTS.md)
- **bugfix**: GitHub CLI (`gh`) — for PR queries and creation
- **triage**: Jira MCP server — configured and authenticated for Jira API access
- **docs-writer**: GitLab CLI — for merge request creation (or GitHub CLI for GitHub-hosted projects)
- **cve-fix**: Jira MCP server or Jira CLI (`jira`), GitHub CLI (`gh`), optionally `skopeo` for container image verification
- **prd**: Jira MCP server — for requirements ingestion; GitHub CLI (`gh`) — for PR creation and review comment management
- **design**: Jira MCP server or CLI — for `/ingest` (read-only) and `/sync` (creates epics/stories); GitHub CLI (`gh`) — for `/publish` and `/respond`
- **kcs**: Jira MCP server — for `/gather` (read-only)

## Installation System

### install.sh

The installer uses auto-discovery to find all workflows and creates symlinks:

```bash
# User-level (all workflows)
./install.sh cursor                    # ~/.cursor/skills/
./install.sh claude                    # ~/.claude/CLAUDE.md and ~/.claude/skills/
./install.sh gemini                    # ~/.gemini/skills/
./install.sh all                       # All environments

# Selective workflows
./install.sh cursor --workflows bugfix,triage

# Project-level
./install.sh cursor --project /path/to/proj    # .cursor/skills/
./install.sh claude --project /path/to/proj    # .claude/CLAUDE.md and .claude/skills/
```

**Auto-discovery mechanism**: The script scans for `*/SKILL.md` files at repo root. No script changes needed when adding workflows.

### uninstall.sh

Mirrors install.sh structure with removal logic.

### Claude Code Integration

For Claude Code, the installer:
1. Appends workflow references to `CLAUDE.md` (or `.claude/CLAUDE.md` for project-level) beneath the `# ai-workflows` marker
2. Symlinks workflows into `~/.claude/skills/` (or `.claude/skills/` for project-level) for slash command discovery
3. Removes stale references (old controller.md paths) to avoid duplicates

## Development Workflows

For detailed workflow development guidelines (structure, file conventions, testing), see CONTRIBUTING.md.

**Quick reference:**
- New workflow: Create directory with SKILL.md, run `./install.sh --list` to verify auto-discovery
- Modify workflow: Maintain relative paths, use progressive disclosure, run skill-reviewer for validation
- Test: `./install.sh cursor && ./uninstall.sh` for clean reinstall verification

## Workflow-Specific Notes

### ai-ready

- Single-phase workflow: `/update` scans the codebase and writes AGENTS.md
- No external dependencies or artifacts
- Safe for any project — reads only, writes one file

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
- Creates GitLab merge requests (designed for GitLab-hosted docs repos, adaptable to GitHub with gh CLI)
- Must get user approval after `/plan` phase before proceeding to `/draft`

### cve-fix

- Requires Jira MCP server or CLI for ticket research
- Only `/close` writes to Jira (all other phases are read-only)
- `/backport` is optional and repeatable for multiple release branches
- Container image verification via `skopeo` is optional
- Multi-strategy patching tries fixes in ascending risk order (direct → transitive → override → major)

### prd

- Requires Jira MCP server for requirements ingestion (read-only — never modifies Jira)
- Uses GitHub CLI (`gh`) for PR creation and review comment management
- `/clarify` has explicit exit criteria and is re-entrant (can loop back from `/draft`)
- `/respond` requires user approval before posting any PR comments
- PRD template and section guidance live in `templates/` (not embedded in skills)
- Must get user review after `/draft` before proceeding to `/publish`

### design

- Requires a completed PRD (`.artifacts/prd/{issue-number}/03-prd.md`) as input
- Jira is read-only until `/sync`; only `/sync` creates issues, and only with dry-run + explicit approval
- Design and decomposition co-evolve — changes to the design flag the decomposition for regeneration, and decomposition gaps recommend revising the design
- Shares docs repo config with PRD workflow (`.artifacts/prd/config.json`)
- Design doc template and section guidance live in `templates/` with project-level override support
- Each story must include functionality AND testing (no deferred test stories)

### kcs

- Requires Jira MCP server for `/gather` (read-only — never modifies Jira)
- Produces KCS Solution articles in markdown following the KCS Content Standard
- Article template, section guidance, and validation checklist live in `templates/`
- `/validate` checks the draft against a structured checklist and fixes violations inline
- `/handoff` composes a channel-agnostic message for the support engineer
- Must get user confirmation between phases; all `/validate` blockers must be resolved before `/handoff`

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

### Jira MCP (for triage, docs-writer, prd, design, kcs)
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

```text
ai-workflows/
├── ai-ready/                  # Workflows (auto-discovered via SKILL.md)
├── bugfix/
├── cve-fix/
├── design/
├── docs-writer/
├── kcs/
├── prd/
├── skill-reviewer/
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
- **PR/MR creation**: Confirm branch and base before pushing (bugfix uses GitHub, docs-writer uses GitLab)
- **Jira queries**: Triage is read-only, but always confirm project key before bulk operations
- **Documentation changes**: Run Vale validation before applying changes to repository files (docs-writer)
