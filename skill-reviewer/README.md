# Skill Reviewer Workflow

A structured workflow for reviewing AI skill directories. Evaluates structure, clarity, completeness, and consistency — then produces a findings report with actionable suggestions.

## Overview

This workflow provides a skeptical, structured review of any AI skill directory:

- **8 Review Dimensions**: Orchestration, sequencing, schemas, cognitive load, clarity, documentation, naming, error handling
- **Severity Classification**: CRITICAL, HIGH, MEDIUM, LOW — with clear blocker vs suggestion distinction
- **Actionable Output**: Every finding includes a concrete suggestion for improvement
- **Artifact Persistence**: Review reports saved to `.artifacts/skill-reviewer/{skill-name}/review.md`

## Directory Structure

```text
skill-reviewer/
├── commands/
│   └── review.md
├── skills/
│   └── review.md
├── guidelines.md
├── SKILL.md
└── README.md
```

### How Commands and Skills Work Together

The **command** (`commands/review.md`) is a thin wrapper that routes directly to the **review skill** (`skills/review.md`), which contains the full review process. No controller is needed — this is a single-phase workflow.

## Workflow Phase

### Review (`/review`)

**Purpose**: Perform a deep, skeptical review of an AI skill directory.

1. Read all files in the target skill directory (`SKILL.md`, `skills/*.md`, `commands/*.md`, `guidelines.md`, `README.md`)
2. Evaluate against 8 review dimensions:
   - **Orchestration & Routing** — correct routing, no orphaned or dangling references
   - **Step Sequencing & Numbering** — sequential numbering, correct cross-references
   - **Schema Consistency** — matching field names/types across files
   - **Cognitive Load & Context Risk** — step count, batching, synthesis placement
   - **Instruction Clarity** — unambiguous, first-try-correct instructions
   - **Documentation Alignment** — README matches implementation
   - **Command Naming** — consistent, self-explanatory names
   - **Error Handling & Edge Cases** — failure modes documented, escalation clear
3. Classify findings by severity and produce a structured report

**Output**: `.artifacts/skill-reviewer/{skill-name}/review.md` + findings presented inline.

## Getting Started

### Quick Start

Specify the skill directory to review:

```text
/review bugfix
```

### Example Usage

#### Review a skill directory

```text
User: "Review the docs-writer skill"

/review  → reads all files in docs-writer/
         → evaluates 8 review dimensions
         → produces findings table
         → writes .artifacts/skill-reviewer/docs-writer/review.md
```

#### Review with specific concerns

```text
User: "/review triage — check if the scan skill handles empty results"

/review  → reads all files in triage/
         → evaluates all dimensions with extra focus on error handling
         → reports findings
```

#### Fix findings after review

```text
User: "Fix the findings"

Workflow: Works through findings from highest severity to lowest
```

## Artifacts Generated

```text
.artifacts/skill-reviewer/{skill-name}/
└── review.md           # Full review report with findings table
```

## Severity Levels

| Severity | Meaning | Classification |
|----------|---------|----------------|
| CRITICAL | Skill would produce wrong output or fail | Blocker |
| HIGH | Skill would produce degraded output | Blocker |
| MEDIUM | Quality issue, documentation drift | Suggestion |
| LOW | Polish, readability, minor wording | Suggestion |

## Behavioral Guidelines

The `guidelines.md` file defines principles and quality standards for reviews. Key points:

- **Read-only**: Reviews never modify the target skill's files
- **Complete reads**: Every file must be read in full before forming opinions
- **Skeptical stance**: The goal is to find problems, not validate
- **Actionable findings**: Every finding must include a concrete suggestion

See `guidelines.md` for full details.
