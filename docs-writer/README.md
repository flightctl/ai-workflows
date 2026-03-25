# Docs Writer Workflow

A structured workflow for creating and updating technical documentation in AsciiDoc. Guides writers through the complete documentation lifecycle from feature research to repository integration.

## Overview

This workflow provides a systematic approach to writing documentation for Red Hat Edge Manager:

- **Research-Driven**: Gathers context from Jira tickets, GitHub issues, or text descriptions before writing
- **Structure-First**: Plans where content belongs in the repository before drafting
- **Style-Compliant**: Enforces Red Hat style guidelines and AsciiDoc conventions automatically
- **Validated Output**: Runs Vale linting (and optionally AsciiDoctor builds) before applying changes
- **IDE-Native**: All work happens in the IDE workspace with file artifacts passed between phases

## Prerequisites

The workflow depends on external tools and integrations. Not all are needed for every phase — install what you need based on which phases you plan to use.

| Tool | Used By | Required? | Install|
|------|---------|-----------|--------|
| **Jira MCP** | `/gather` | Required for Jira ticket input | Configure as an MCP server in your IDE or agent environment|
| **GitHub MCP** or **`gh` CLI** | `/gather` | Required for GitHub issues and upstream PR diffs | [gh CLI](https://cli.github.com/) or configure GitHub MCP in your IDE. GitHub CLI is preferred|
| **Vale** | `/draft`, `/validate` | Required | [vale.sh/docs/install](https://vale.sh/docs/install)|
| **Asciidoctor** | `/draft`, `/validate` | Required (Vale uses it to parse `.adoc` files) | `dnf install asciidoctor` or `gem install asciidoctor`|
| **`glab` CLI** | `/mr` | Required for merge request creation | [docs.gitlab.com/editor_extensions/gitlab_cli](https://docs.gitlab.com/editor_extensions/gitlab_cli)|
| **`git`** | `/mr` | Required | Pre-installed on most systems|
| **`podman`** or **`docker`** | `/validate` (builds) | Optional (fallback for AsciiDoctor builds) | `dnf install podman`|

## Directory Structure

```text
docs-writer/
├── commands/             # Slash commands (thin wrappers → skills)
│   ├── gather.md
│   ├── plan.md
│   ├── draft.md
│   ├── validate.md
│   ├── apply.md
│   └── mr.md
└── skills/               # Detailed process definitions
    ├── controller.md
    ├── gather-context.md
    ├── plan-structure.md
    ├── draft-content.md
    ├── validate.md
    ├── apply-changes.md
    └── create-mr.md
├── guidelines.md         # Behavioral guidelines
└── README.md             # This file
```

### How Commands and Skills Work Together

Each **command** is a thin wrapper that invokes the **controller**, which then dispatches the corresponding **skill**. When you run `/gather`, the command file tells the agent to read the controller and dispatch the gather phase — passing along any arguments you provided.

The **controller** (`skills/controller.md`) owns all shared context (project references, AsciiDoc conventions, Vale config, artifact format) so individual skills stay focused on their specific task without repeating common instructions.

## Workflow Phases

The Docs Writer Workflow follows this approach:

```text
gather → plan → [approve] → draft → validate → apply → mr
```

### Phase 1: Gather Context (`/gather`)

**Purpose**: Understand the feature end-to-end by collecting requirements and code changes.

- Classify the input (Jira ticket, GitHub issue, or text description)
- Fetch requirements from the appropriate source
- Navigate the Jira hierarchy (Feature → Epic → Story) to build full context
- Identify linked pull requests in upstream repositories
- Fetch code diffs to understand technical changes
- Synthesize a comprehensive context document

**Output**: `.artifacts/${ticket_id}/01-context.md`

**When to use**: Start here when you have a Jira ticket, GitHub issue URL, or feature description.

### Phase 2: Plan Structure (`/plan`)

**Purpose**: Determine exactly where new documentation should live in the repository.

- Review the gathered context
- Understand the repository's guide structure (`master.adoc` + `includes/` pattern)
- Search for existing related content
- Create a structural plan specifying which `.adoc` files to create or modify

**Output**: `.artifacts/${ticket_id}/02-plan.md`

**When to use**: After gathering context, or skip here if you already understand the feature.

### Approval Gate

After `/plan` completes, the workflow pauses for user approval. Review the plan, modify it if needed, then approve to continue. The plan must be approved before drafting begins.

### Phase 3: Draft Content (`/draft`)

**Purpose**: Write style-compliant AsciiDoc documentation based on context and the approved plan.

- Review the context and plan artifacts
- Study existing `.adoc` files as exemplars for conventions
- Write AsciiDoc content following project conventions
- Use product name attributes (`{rhem}`, `{ocp}`, `{rhel}`) — never hardcode names
- Apply Red Hat Supplementary Style Guide rules (voice, terminology, UI formatting)
- Apply Red Hat Modular Documentation Guide patterns
- Enforce AsciiDoc conventions (headings, section IDs, source blocks, product attributes)
- Run Vale and fix all violations
- Format the output for downstream phases

**Output**: `.artifacts/${ticket_id}/03-final-docs.adoc`

**When to use**: After the plan is approved, or jump here if you already have a plan.

### Phase 4: Validate (`/validate`)

**Purpose**: Verify that the styled content passes all quality checks before applying.

- Parse the draft artifact to identify target files
- Run Vale on each file segment and resolve all violations
- Optionally run AsciiDoctor to verify the content compiles
- Loop back to `/draft` if validation fails

**Output**: Validation pass/fail (modifies `03-final-docs.adoc` if corrections are needed)

**When to use**: After drafting, to ensure quality before applying to the repository.

### Phase 5: Apply Changes (`/apply`)

**Purpose**: Write the validated content to the actual repository files.

- Parse the artifact format to extract target file paths and content
- Write content to existing or new `.adoc` files in the repository
- Update `master.adoc` includes if new topic files were created
- Notify the user that files are ready for review in the IDE

**Output**: Modified `.adoc` files in the repository workspace.

**When to use**: After validation passes, and you're ready to apply changes.

### Phase 6: Create Merge Request (`/mr`)

**Purpose**: Create a GitLab merge request for the documentation changes.

- Run pre-flight checks (GitLab CLI auth, git config, remotes)
- Determine push strategy (direct push vs. fork workflow)
- Create a branch, stage and commit changes
- Push the branch and create a draft merge request via `glab mr create`
- Fall back to a manual MR URL if automated creation fails

**Output**: A draft merge request on GitLab (or a pre-filled URL for manual creation).

**When to use**: After applying changes to the repository, to submit them for review.

## Getting Started

### Quick Start

1. **Provide context**: Jira ticket URL/key, GitHub issue URL, or a text description
2. **Start with `/gather`** to research the feature
3. **Follow the phases** sequentially, or jump to any phase based on your context

### Example Usage

#### Scenario 1: You have a Jira ticket

```text
User: "Document RHEM-456 — new device enrollment API"

Workflow: Starts with /gather to fetch Jira details and code diffs
→ /plan to decide where the content belongs
→ [approve the plan]
→ /draft to write style-compliant AsciiDoc content
→ /validate to run Vale
→ /apply to write files to the repository
→ /mr to create a merge request
```

#### Scenario 2: You know what to write

```text
User: "Add a procedure for configuring TLS certificates under managing_devices"

Workflow: Jumps to /plan to determine the target files
→ [approve the plan]
→ /draft to write the content
→ /validate → /apply
```

#### Scenario 3: You already have a draft

```text
User: "I've written a draft at .artifacts/RHEM-789/03-final-docs.adoc, validate it"

Workflow: Jumps to /validate to verify
→ /apply to write to the repository
```

## Artifacts Generated

All workflow artifacts are organized in the `.artifacts/${ticket_id}/` directory:

```text
.artifacts/${ticket_id}/
├── 01-context.md          # Feature research and context
├── 02-plan.md             # Structural plan (which files to create/modify)
├── 03-final-docs.adoc     # Style-compliant, validated AsciiDoc (multi-file format)
└── 04-mr-description.md   # MR description (prepared by /apply, used by /mr)
```

The final artifact (`03-final-docs.adoc`) uses a multi-file format with `// File: <path>` markers and `----` separators so the apply phase knows which repository files to target.
