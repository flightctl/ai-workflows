<!-- Edited by Claude Code -->
# AI Workflows

A library of reusable AI coding workflows that any team member can install — globally or per-project — in Cursor, Claude Code, or any compatible environment.

## What You Get

**12 production-ready workflows** covering the full software development lifecycle, from requirements gathering through code delivery:

| Workflow | What it does |
|----------|-------------|
| [Bugfix](workflows/bugfix.md) | Resolve bugs systematically: assess, reproduce, diagnose, fix, test, review, document, and submit a PR |
| [Code Review](workflows/code-review.md) | Review uncommitted changes with AI, then let a human decide which findings to act on |
| [CVE Fix](workflows/cve-fix.md) | Patch CVEs end-to-end: scan, fix dependencies, validate, open PRs, backport, and close Jira tickets |
| [Design](workflows/design.md) | Draft a technical design from a PRD and decompose it into Jira-ready epics and stories |
| [Docs Writer](workflows/docs-writer.md) | Create and validate documentation: gather context, plan, draft, review, and publish |
| [E2E Testing](workflows/e2e.md) | Turn a QE story into end-to-end tests mapped to acceptance criteria |
| [Implement](workflows/implement.md) | Implement a Jira story using test-driven development, from ingestion through PR |
| [KCS](workflows/kcs.md) | Draft and validate a KCS Solution article from a Jira bug with a known workaround |
| [PRD](workflows/prd.md) | Generate a Product Requirements Document from Jira requirements via iterative Q&A |
| [Triage](workflows/triage.md) | Triage Jira bugs in bulk with AI-driven categorization and interactive HTML reports |
| [AI-Ready](workflows/ai-ready.md) | Scan a codebase and generate an AGENTS.md with build commands, test patterns, and coding standards |
| [Skill Reviewer](workflows/skill-reviewer.md) | Audit AI skill directories for structure, clarity, and completeness across eight quality dimensions |

## How It Works

Each workflow is a directory containing a `SKILL.md` entry point, phase-specific skills in `skills/`, and slash-command wrappers in `commands/`. Everything is plain markdown — no IDE plugins or proprietary syntax required.

```
~/.ai-workflows/  (symlink to your clone)
  bugfix/
    SKILL.md, skills/, commands/
  design/
    SKILL.md, skills/, commands/
```

Because your install is a symlink, running `git pull` updates every workflow instantly.

## Quick Links

- [Installation](getting-started/installation.md) — install in under a minute
- [Quick Start](getting-started/quick-start.md) — run your first workflow
- [Workflows Overview](workflows/index.md) — browse all workflows and see how they connect
- [Contributing](development/contributing.md) — learn how to add or modify workflows
