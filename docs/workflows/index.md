<!-- Edited by Claude Code -->
# Workflows Overview

This project provides 12 production-ready workflows that together cover the full software development lifecycle. The diagram below shows how they connect.

## SDLC Coverage

```mermaid
graph TD
    subgraph Requirements
        PRD[PRD]
    end
    subgraph Planning
        Design[Design]
        Triage[Triage]
    end
    subgraph Implementation
        Implement[Implement]
        Bugfix[Bugfix]
        CVEFix[CVE Fix]
    end
    subgraph Quality
        E2E[E2E Testing]
        CodeReview[Code Review]
    end
    subgraph Documentation
        DocsWriter[Docs Writer]
        KCS[KCS]
    end
    subgraph Tooling
        AIReady[AI-Ready]
        SkillReviewer[Skill Reviewer]
    end

    PRD --> Design
    Design --> Implement
    Design --> E2E
    Triage --> Bugfix
    Implement --> CodeReview
    Bugfix --> CodeReview
    CVEFix --> CodeReview
    Implement --> DocsWriter
    Bugfix --> KCS
```

## Workflow Catalog

| Workflow | Phases | Purpose |
|----------|--------|---------|
| [Bugfix](bugfix.md) | assess, reproduce, diagnose, fix, test, review, document, pr, feedback | Systematic bug resolution |
| [Code Review](code-review.md) | start, continue, clean | AI-driven code review with human decisions |
| [CVE Fix](cve-fix.md) | start, scan, patch, validate, pr, backport, close | Automated CVE remediation |
| [Design](design.md) | ingest, research, draft, decompose, revise, publish, respond, sync | Technical design and Jira decomposition |
| [Docs Writer](docs-writer.md) | gather, plan, draft, validate, apply, mr | Documentation creation and validation |
| [E2E Testing](e2e.md) | ingest, plan, revise, code, validate, publish, respond | Story-to-tests for QE stories |
| [Implement](implement.md) | ingest, plan, revise, code, validate, publish, respond | Story-to-code via TDD |
| [KCS](kcs.md) | gather, draft, validate, handoff | KCS Solution article workflow |
| [PRD](prd.md) | ingest, clarify, draft, revise, publish, respond | Requirements to PRD |
| [Triage](triage.md) | start, scan, analyze, report, assess | Bulk Jira bug triage |
| [AI-Ready](ai-ready.md) | update | AGENTS.md generation |
| [Skill Reviewer](skill-reviewer.md) | review | AI skill quality auditing |

## Architecture

Every workflow follows the same directory structure:

```text
workflow-name/
  SKILL.md              # Entry point with YAML frontmatter
  guidelines.md         # Behavioral rules and guardrails
  README.md             # Human-readable documentation
  skills/
    controller.md       # Optional phase dispatcher
    phase-name.md       # Implementation for each phase
  commands/
    phase-name.md       # Thin wrappers for slash commands
```

Design principles:

- **Auto-discovery** — the installer finds any directory that contains a `SKILL.md`
- **Progressive disclosure** — `SKILL.md` stays under 30 lines; details live in `guidelines.md` and `skills/`
- **Relative paths** — all file references are relative, so symlinks resolve correctly regardless of install location
- **Phase-based execution** — each workflow is split into discrete phases with explicit transitions
- **No auto-advance** — the workflow always pauses and waits for user input between phases
