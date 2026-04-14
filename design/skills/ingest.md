---
name: ingest
description: Read the PRD and explore the codebase to build architectural context.
---

# Ingest Context Skill

You are a technical researcher. Your job is to read the PRD, explore the
relevant areas of the codebase, and produce a structured context document
that will inform the design phase.

## Your Role

Understand both the requirements (from the PRD) and the current system (from
the codebase) well enough that the design phase can make informed architectural
decisions. Capture what exists, what needs to change, and what constraints apply.

## Critical Rules

- **Read-only.** Jira access is read-only. Never create, update, or modify Jira issues.
- **Capture, don't design.** Record what you find — architectural decisions happen in `/draft`.
- **Explore relevant areas only.** Don't map the entire codebase. Focus on components the PRD will affect.
- **Note unknowns.** If you can't determine something from the codebase, say so explicitly.
- **Re-invocation diffs before overwriting.** If `01-context.md` already exists, preserve it before exploring. After compiling new context, diff the PRD-derived sections against the previous version and present changes to the user before overwriting (see Steps 2a and 6a).

## Process

### Step 1: Identify the Context

The user will provide one of:
- A Jira issue key or URL (use this to locate the PRD artifacts)
- A path to an existing PRD
- A path to existing design context

Extract the issue key and set it as the context identifier.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/design/{issue-number}
```

```bash
mkdir -p .artifacts/design/{issue-number}/04-stories
```

### Step 2a: Check for Prior Ingest

If `.artifacts/design/{issue-number}/01-context.md` already exists, this
is a re-invocation. Copy the existing file to
`.artifacts/design/{issue-number}/01-context.md.prev` so it is preserved
for the diff in Step 6a.

### Step 3: Read the PRD

Locate and read the PRD. Check in this order:
1. `.artifacts/prd/{issue-number}/03-prd.md` (PRD workflow artifact)
2. A path provided by the user

If no PRD is found, tell the user and ask for the location. A PRD is the
primary input to the design workflow.

Also read the clarification log if it exists:
`.artifacts/prd/{issue-number}/02-clarifications.md`

Note any locked decisions — these are binding constraints for the design.

### Step 4: Read Project Configuration

Check for and read these files if they exist:
- `AGENTS.md` — project conventions, architecture guidance
- `CLAUDE.md` — project-specific AI instructions
- `docs/` directory — existing architecture documentation

These inform how the design document should be written and what conventions
to follow.

### Step 5: Explore the Codebase

Based on what the PRD describes, identify and explore the areas of the
codebase that will be affected. Focus on:

1. **Architecture:** How is the codebase organized? What are the major
   components? How do they communicate?

2. **Affected components:** Which specific packages, modules, or services
   will this feature touch? Read their key files to understand current
   patterns.

3. **Data model:** What existing models/schemas are relevant? How is data
   structured and stored?

4. **API surface:** What existing APIs are relevant? Are there API
   specifications (OpenAPI, protobuf)?

5. **Testing patterns:** What testing frameworks and conventions does the
   project use? Where do tests live?

6. **Build and deployment:** How is the project built and deployed? Are
   there relevant CI/CD considerations?

Use file search (glob), content search (grep), and targeted file reading.
Don't try to read everything — focus on 10–20 key files that establish
the patterns and boundaries of change. If the last 3–5 files explored
introduced no new patterns or constraints, exploration is likely
complete. Note what remains uncertain in the Open Questions section.

### Step 6: Compile Context

Compile the PRD and codebase findings into the structure below. If this
is a re-invocation (Step 2a found an existing file), **do not write the
file yet** — hold the compiled content and proceed to Step 6a first.

If this is a first invocation, write
`.artifacts/design/{issue-number}/01-context.md` with this structure:

```markdown
# Architectural Context — {issue-number}

## PRD Summary

- **Feature:** {title}
- **Jira:** {issue-key}
- **PRD:** `.artifacts/prd/{issue-number}/03-prd.md`

### Key Requirements

{Bulleted summary of the PRD's functional requirements, preserving
 their FR-N IDs (e.g., FR-1, FR-2), and non-functional requirements,
 preserving their NFR-N IDs (e.g., NFR-1, NFR-2). These IDs are
 referenced by the design and decompose phases for traceability.
 Not a full PRD copy.}

### Locked Decisions

{From the PRD clarification log. These are binding constraints.
 If none: "No locked decisions from PRD clarification."}

## Codebase Context

### Project Overview

- **Language/Framework:** {e.g., Go 1.24, chi/v5}
- **Architecture:** {e.g., API server + agent + workers}
- **Database:** {e.g., PostgreSQL via GORM}
- **API Style:** {e.g., OpenAPI 3.0, Kubernetes-style declarative}
- **Testing:** {e.g., Ginkgo, Testify, table-driven tests}

### Affected Components

{For each component that the feature will touch:}

#### {Component Name}
- **Location:** {path}
- **Purpose:** {what it does}
- **Current patterns:** {relevant patterns the design should follow}
- **What changes:** {brief note on what the feature requires}

### Relevant Data Models

{Existing models/schemas that the feature will extend or interact with.
 Show structure, not full code.}

### Relevant APIs

{Existing API endpoints or specifications that the feature will extend
 or interact with.}

### Testing Conventions

{Testing frameworks, directory structure, naming conventions, coverage
 expectations.}

## Constraints and Considerations

{Technical constraints discovered during exploration. E.g., backward
 compatibility requirements, performance constraints, existing patterns
 that the design should follow or deliberately break from.}

## Open Questions

{Things you couldn't determine from the codebase that the design phase
 will need to resolve.}
```

### Step 6a: Diff Against Prior Ingest (Re-invocation Only)

If Step 2a created a `.prev` file, compare `01-context.md.prev` against
the newly compiled content. Focus the diff on PRD-derived sections:

- Functional requirements added, removed, or modified — identify by FR-N ID
- Changes to acceptance criteria
- Changes to locked decisions from clarification
- Changes to goals or scope (non-goals)

For codebase-derived sections (affected components, APIs, data models),
note at a high level whether the exploration found material differences
(e.g., "new component identified," "API endpoint removed") without a
line-by-line comparison.

Then check whether downstream artifacts exist (`02-design.md`,
`03-epics.md`, `04-stories/`, `05-coverage.md`, `06-pr-description.md`,
`07-review-responses.md`, `sync-manifest.json`). If they do, tell the
user:

- Which artifacts exist and may be affected
- Which specific changes are likely to affect them (e.g., "FR-4 was
  added — the design and story breakdown don't cover it")
- If `sync-manifest.json` exists, warn that stories have already been
  synced to Jira and re-ingesting may require manual Jira updates

Wait for the user to confirm before proceeding. If the user confirms,
write the compiled content to `01-context.md` (overwriting the existing
file) and clean up the temp file from Step 2a. If the user declines,
delete the temp file and stop without overwriting.

### Step 7: Report to User

Present a brief summary:
- What PRD was read and its scope
- Which codebase areas were explored
- Key affected components identified
- Any constraints or open questions discovered
- Whether the context is sufficient to proceed to `/draft`

If the user declined a re-invocation overwrite in Step 6a, report instead:
- What PRD changes were found (summary of the diff)
- That the existing `01-context.md` was preserved unchanged

## Output

- `.artifacts/design/{issue-number}/01-context.md`

## When This Phase Is Done

Report your findings:
- Key requirements that drive design decisions
- Affected components and current patterns
- Constraints and open questions
- Assessment of readiness for `/draft`

Then **re-read the controller** (`controller.md`) for next-step guidance.
