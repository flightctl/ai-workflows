<!-- Edited by Claude Code -->
# Quick Start

Once you have [installed](installation.md) the workflows, you can invoke any command from your AI coding environment.

## Running a Workflow

Every command follows the pattern `/<workflow>:<phase>`:

```
/bugfix:assess JIRA-123
/code-review:start
/implement:ingest PROJ-456
```

## Example: Bug Fix

```
/bugfix:assess JIRA-123        # Read and understand the bug report
/bugfix:reproduce               # Confirm the bug is reproducible
/bugfix:diagnose                 # Identify the root cause
/bugfix:fix                      # Implement the fix with tests
/bugfix:test                     # Verify and create regression tests
/bugfix:review                   # Self-review the changes
/bugfix:pr                       # Submit a pull request
```

## Example: Code Review

```
/code-review:start               # Review uncommitted changes
/code-review:continue             # Implement accepted findings
/code-review:clean                # Remove review artifacts
```

## Example: Implement a Story

```
/implement:ingest PROJ-456       # Fetch story context from Jira
/implement:plan                   # Design the implementation approach
/implement:code                   # Write tests and code via TDD
/implement:validate               # Run the full validation suite
/implement:publish                # Push branch and create a draft PR
```

## Selective Installation

Each workflow is designed for a specific project type or use case:

| Workflow | Best for |
|----------|----------|
| **bugfix** | Flight Control projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui)) |
| **code-review** | Any project — reviews uncommitted changes |
| **docs-writer** | Downstream docs projects (e.g., edge-manager) |
| **prd** | Teams drafting Product Requirements Documents from Jira |
| **design** | Teams creating technical designs and Jira-ready epic/story breakdowns |
| **implement** | Teams implementing Jira stories produced by the design workflow |
| **e2e** | Teams writing e2e tests for QE stories |
| **cve-fix** | Teams patching CVEs from Jira vulnerability tickets |
| **ai-ready** | Onboarding any project for AI agents by generating AGENTS.md |
| **kcs** | Teams writing KCS Solution articles for known issues |
| **triage** | Teams wanting bulk Jira triage and HTML reports |
| **skill-reviewer** | Reviewing or standardizing AI skills and skill packs |
