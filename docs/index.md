<!-- Edited by Claude Code -->
# AI Workflows

Reusable AI coding workflows a team member can install globally or per-project, in any environment: Cursor, Claude Code, and others.

## What You Get

A library of **12 production-ready workflows** that cover the full software development lifecycle — from requirements gathering to code delivery:

| Workflow | What it does |
|----------|-------------|
| [Bugfix](workflows/bugfix.md) | Systematic bug resolution: assess, reproduce, diagnose, fix, test, review, document, PR |
| [Code Review](workflows/code-review.md) | AI-driven code review with human-in-the-loop decisions |
| [CVE Fix](workflows/cve-fix.md) | Automated CVE remediation from Jira tickets |
| [Design](workflows/design.md) | Technical design documents with Jira epic/story decomposition |
| [Docs Writer](workflows/docs-writer.md) | Systematic documentation creation and validation |
| [E2E Testing](workflows/e2e.md) | Story-to-tests workflow for QE stories |
| [Implement](workflows/implement.md) | Story-to-code workflow via TDD |
| [KCS](workflows/kcs.md) | KCS Solution article drafting and validation |
| [PRD](workflows/prd.md) | Requirements-to-PRD workflow |
| [Triage](workflows/triage.md) | Bulk Jira bug triage with AI categorization |
| [AI-Ready](workflows/ai-ready.md) | AGENTS.md generation for any codebase |
| [Skill Reviewer](workflows/skill-reviewer.md) | Meta-workflow auditing AI skill quality |

## How It Works

Each workflow is a directory with a `SKILL.md` entry point, optional phase skills under `skills/`, and command wrappers under `commands/` — all plain markdown, no IDE-specific syntax.

```
~/.ai-workflows/  (symlink to your clone)
  bugfix/
    SKILL.md, skills/, commands/
  design/
    SKILL.md, skills/, commands/
```

`git pull` updates everything instantly through the symlink.

## Quick Links

- [Installation](getting-started/installation.md) — get started in under a minute
- [Quick Start](getting-started/quick-start.md) — run your first workflow
- [Workflows Overview](workflows/index.md) — see all workflows and how they connect
- [Contributing](development/contributing.md) — add or modify workflows
