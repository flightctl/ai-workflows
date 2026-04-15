# KCS Article Workflow

A structured workflow for creating KCS (Knowledge-Centered Service) Solution articles. Guides writers through gathering bug context, drafting the article, validating against the KCS Content Standard, and preparing a handoff message for the support engineer who publishes it.

## Overview

- **Context-Driven**: Gathers bug details from Jira and user-provided workaround steps before writing
- **Template-Based**: Uses a KCS Solution skeleton and per-section writing guidance to produce consistent articles
- **Validated Output**: Checks the draft against a comprehensive KCS checklist before handoff
- **Portable**: No hardcoded product names, contacts, or project references — works for any team
- **IDE-Native**: All work happens in the IDE workspace with file artifacts passed between phases

## Prerequisites

| Tool | Used By | Required? | Install |
|------|---------|-----------|---------|
| **Jira MCP** | `/gather` | Required for Jira ticket input | Configure as an MCP server in your IDE or agent environment |
| **Git** | General | Recommended | Pre-installed on most systems |

No external linters, build tools, or CLI utilities are required. The workflow produces standalone Markdown files.

## Directory Structure

```text
kcs/
├── SKILL.md                    # Entry point (thin)
├── guidelines.md               # Behavioral guidelines
├── README.md                   # This file
├── templates/
│   ├── kcs-solution.md         # Article skeleton
│   ├── section-guidance.md     # Per-section AI writing instructions
│   └── validation-checklist.md # Checklist for /validate phase
├── skills/
│   ├── controller.md           # Phase dispatch and transitions
│   ├── gather.md               # Phase: collect bug context
│   ├── draft.md                # Phase: write the article
│   ├── validate.md             # Phase: check against KCS standard
│   └── handoff.md              # Phase: compose support engineer message
└── commands/
    ├── gather.md               # Thin wrapper → controller
    ├── draft.md                # Thin wrapper → controller
    ├── validate.md             # Thin wrapper → controller
    └── handoff.md              # Thin wrapper → controller
```

### How Commands and Skills Work Together

Each **command** is a thin wrapper that invokes the **controller**, which then dispatches the corresponding **skill**. When you run `/gather`, the command file tells the agent to read the controller and dispatch the gather phase — passing along any arguments you provided.

The **controller** (`skills/controller.md`) owns all shared context (artifact paths, template references, phase transitions) so individual skills stay focused on their specific task.

## Workflow Phases

```text
gather → draft → validate → handoff
```

### Phase 1: Gather Context (`/gather`)

**Purpose**: Collect bug details from Jira and user-provided context.

- Fetch bug details from a Jira ticket (description, status, affected versions, comments)
- Merge in user-provided context (workaround steps, logs, diagnostic commands)
- Identify information gaps and ask targeted questions
- Save a structured context document

**Output**: `.artifacts/kcs/{issue-key}/01-context.md`

**When to use**: Start here when you have a Jira ticket for a bug with a known workaround.

### Phase 2: Draft Article (`/draft`)

**Purpose**: Write a KCS Solution article using the template and section guidance.

- Load the article template and per-section writing guidance
- Fill in each section: Title, Issue, Environment, Diagnostic Steps, Resolution, Root Cause
- Apply KCS style rules (present tense, no pronouns, proper formatting)
- Flag any assumptions made during drafting

**Output**: `.artifacts/kcs/{issue-key}/02-kcs-draft.md`

**When to use**: After gathering context, or directly if you already have full context.

### Phase 3: Validate (`/validate`)

**Purpose**: Check the draft against the KCS validation checklist.

- Run every item in the checklist (structure, content, style)
- Auto-fix minor issues (formatting, tense, backticks)
- Report issues requiring user input
- Surface and confirm any flagged assumptions

**Output**: Updated `.artifacts/kcs/{issue-key}/02-kcs-draft.md`

**When to use**: After drafting, to verify quality before handoff. Loops back to `/draft` on significant failures.

### Phase 4: Handoff (`/handoff`)

**Purpose**: Compose a message for the support engineer who publishes the article.

- Ask the user for the support engineer's name and contact method
- Compose a concise message: bug summary, Jira reference, KCS compliance note
- Present the message for user review before sending

**Output**: `.artifacts/kcs/{issue-key}/03-handoff-message.md`

**When to use**: After validation passes and the draft is ready to publish.

## Getting Started

### Quick Start

1. **Provide a Jira ticket**: Issue key (e.g., `EDM-3340`) or URL, plus any workaround details
2. **Run `/gather`** to collect and structure the context
3. **Follow the phases** sequentially: `/draft` → `/validate` → `/handoff`

### Example Usage

#### Scenario 1: Jira ticket with workaround details

```text
User: "Write a KCS article for EDM-3340. The workaround is to detach the
device from the fleet, apply a recovery spec, then re-assign."

/gather   → .artifacts/kcs/EDM-3340/01-context.md
/draft    → .artifacts/kcs/EDM-3340/02-kcs-draft.md
/validate → checks pass, minor fixes applied
/handoff  → .artifacts/kcs/EDM-3340/03-handoff-message.md
```

#### Scenario 2: Context already in hand

```text
User: "I have full context for this bug, skip to drafting."

/draft    → .artifacts/kcs/PROJ-456/02-kcs-draft.md
/validate → .artifacts/kcs/PROJ-456/02-kcs-draft.md (updated)
/handoff  → .artifacts/kcs/PROJ-456/03-handoff-message.md
```

#### Scenario 3: Validate an existing draft

```text
User: "I already wrote a draft at .artifacts/kcs/PROJ-789/02-kcs-draft.md"

/validate → runs checklist, fixes formatting issues
/handoff  → composes message for support engineer
```

## Artifacts Generated

```text
.artifacts/kcs/{issue-key}/
├── 01-context.md          # Bug details and user-provided context
├── 02-kcs-draft.md        # The KCS Solution article (markdown)
└── 03-handoff-message.md  # Ready-to-send message for the support engineer
```

## References

These links are for human reference only (Red Hat SSO required). The skill itself does not access these at runtime — all rules are embedded in the `templates/` files.

- [KCS Solutions Content Standard v3.0](https://source.redhat.com/departments/products_and_global_engineering/cee_kcs_program/cee_kcs_program_wiki/kcs_solutions_content_standard_v20) (Red Hat internal)
- [Red Hat Customer Portal - Solutions](https://access.redhat.com/solutions)
