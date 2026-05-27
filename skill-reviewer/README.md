# Skill Reviewer Workflow

A structured workflow for reviewing AI skill directories. Evaluates structure, clarity, completeness, and consistency — then produces a findings report with actionable suggestions.

## Overview

This workflow provides a skeptical, structured review of any AI skill directory:

- **8 Review Dimensions**: Orchestration, sequencing, schemas, cognitive load, clarity, documentation, naming, error handling
- **Severity Classification**: CRITICAL, HIGH, MEDIUM, LOW — with clear blocker vs suggestion distinction
- **Actionable Output**: Every finding includes a concrete suggestion for improvement
- **Artifact Persistence**: Review reports saved to `.artifacts/skill-reviewer/{skill-name}/review.md`

## Phase Flow

```mermaid
graph TD
    review([review]) --> read[Read all files]
    read --> checks[Run pre-review checks]
    checks --> evaluate[Evaluate 8 dimensions]
    evaluate --> report[Produce findings report]
```

## Directory Structure

```text
skill-reviewer/
├── commands/
│   └── review.md
├── prompts/
│   └── analyze-skill.md
├── scripts/
│   └── pre-review-checks.py
├── skills/
│   └── review.md
├── guidelines.md
├── SKILL.md
└── README.md
```

### How Commands and Skills Work Together

The **command** (`commands/review.md`) is a thin wrapper that routes directly to the **review skill** (`skills/review.md`), which contains the full review process. The **prompts** directory contains `analyze-skill.md`, a prompt template given to an Explore sub-agent when reviewing large skills (15+ files) to produce a structured skill map before evaluation. The **scripts** directory contains `pre-review-checks.py`, which runs automated structural checks before the LLM evaluation. No controller is needed — this is a single-phase workflow.

## Workflow Phase

### Review (`/review`)

**Purpose**: Perform a deep, skeptical review of an AI skill directory.

1. Read all files in the target skill directory (`SKILL.md`, `skills/*.md`, `commands/*.md`, `guidelines.md`, `README.md`)
2. Run automated pre-review checks (`scripts/pre-review-checks.py`) — structural validation, frontmatter, orphaned/dangling references, step sequencing
3. Evaluate against 8 review dimensions (using automated check results as pre-validated evidence):
   - **Orchestration & Routing** — correct routing, no orphaned or dangling references
   - **Step Sequencing & Numbering** — sequential numbering, correct cross-references
   - **Schema Consistency** — matching field names/types across files
   - **Cognitive Load & Context Risk** — step count, batching, synthesis placement
   - **Instruction Clarity** — unambiguous, first-try-correct instructions
   - **Documentation & Project Alignment** — README matches implementation, consistent with sibling skills and project conventions
   - **Command Naming** — consistent, self-explanatory names
   - **Error Handling & Edge Cases** — failure modes documented, escalation clear
4. Classify findings by severity and produce a structured report

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

The review itself is read-only. After the review, the user can ask to fix findings — this is normal editing, not a workflow phase.

```text
User: "Fix the findings"

Agent works through findings from highest severity to lowest.
```

## Artifacts Generated

```text
.artifacts/skill-reviewer/{skill-name}/
├── file-hashes.json    # SHA-256 hashes for change detection between reviews
├── skill-map.md        # Structured skill map (comprehension artifact before evaluation)
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

- **Read-only**: The review phase never modifies the target skill's files; fixing findings afterward is a separate user-initiated action
- **Complete reads**: Every file must be read in full before forming opinions
- **Skeptical stance**: The goal is to find problems, not validate
- **Actionable findings**: Every finding must include a concrete suggestion

See `guidelines.md` for full details.
