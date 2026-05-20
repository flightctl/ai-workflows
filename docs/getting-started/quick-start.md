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
| [**bugfix**](../workflows/bugfix.md) | Flight Control projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui)) |
| [**code-review**](../workflows/code-review.md) | Any project — reviews uncommitted changes |
| [**docs-writer**](../workflows/docs-writer.md) | Downstream docs projects (e.g., edge-manager) |
| [**prd**](../workflows/prd.md) | Teams drafting Product Requirements Documents from Jira |
| [**design**](../workflows/design.md) | Teams creating technical designs and Jira-ready epic/story breakdowns |
| [**implement**](../workflows/implement.md) | Teams implementing Jira stories produced by the design workflow |
| [**e2e**](../workflows/e2e.md) | Teams writing e2e tests for QE stories |
| [**cve-fix**](../workflows/cve-fix.md) | Teams patching CVEs from Jira vulnerability tickets |
| [**ai-ready**](../workflows/ai-ready.md) | Onboarding any project for AI agents by generating AGENTS.md |
| [**kcs**](../workflows/kcs.md) | Teams writing KCS Solution articles for known issues |
| [**triage**](../workflows/triage.md) | Teams wanting bulk Jira triage and HTML reports |
| [**skill-reviewer**](../workflows/skill-reviewer.md) | Reviewing or standardizing AI skills and skill packs |
