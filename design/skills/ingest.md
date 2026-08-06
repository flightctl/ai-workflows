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

Extract the full Jira issue key, including the project prefix (e.g.,
`PROJ-1234`, not just `1234`). Use this as `{issue-key}` throughout
the workflow — it is the context identifier for the artifact directory
and all downstream phases.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/design/{issue-key}
```

```bash
mkdir -p .artifacts/design/{issue-key}/05-stories
```

### Step 2a: Check for Prior Ingest

If `.artifacts/design/{issue-key}/01-context.md` already exists, this
is a re-invocation. Copy the existing file to
`.artifacts/design/{issue-key}/01-context.md.prev` so it is preserved
for the diff in Step 6a.

### Step 3: Read the PRD

The published PRD in the docs repo is the authoritative source. Locate it
there — do not read from `.artifacts/prd/`.

#### Resolve the Docs Repo

Read `.artifacts/config.json` for `docs_repo_path` and `docs_repo_remote`.

**If the config exists**, validate it:
1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the remote URL matches the configured `docs_repo_remote`

If any validation fails, inform the user and re-ask for the correct values.
Update `.artifacts/config.json` with the corrected values.

**If the config does not exist**, ask the user for the docs repo local path
and remote, validate them, and write `.artifacts/config.json`.

#### Find the PRD in the Docs Repo

Search the docs repo for a directory whose name contains `{issue-key}`:

```bash
find "{docs_repo_path}" -type d -name "*{issue-key}*"
```

Filter matches to directories that contain a `prd.md` file.

If exactly one matching directory contains `prd.md` (e.g.,
`v2.1/delta-updates-EDM-4867/prd.md`), read it.

If multiple matching directories contain `prd.md`, present them to the
user and ask which one contains the current PRD.

If no match is found (or no matches contain `prd.md`), ask the user for
the path to the PRD.

#### Read Clarifications

If `clarifications.md` exists in the same docs repo directory as the PRD,
read it. Note any locked decisions — these are binding constraints for the
design.

If no clarifications file exists, the PRD itself should reflect all locked
decisions in its final form.

#### Record the Resolved Paths

Record the resolved PRD path (and clarifications path, if found) in
`.artifacts/design/{issue-key}/01-context.md` (in the PRD Summary section)
so that downstream phases (`/draft`, `/research`, `/decompose`) can read
them directly without repeating the lookup.

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
`.artifacts/design/{issue-key}/01-context.md` with this structure:

```markdown
# Architectural Context — {issue-key}

## PRD Summary

- **Feature:** {title}
- **Jira:** {issue-key}
- **PRD:** {resolved PRD path}
- **Clarifications:** {resolved clarifications path, or "None published"}

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

Then check whether downstream artifacts exist (`02-research.md`,
`03-design.md`, `04-epics.md`, `05-stories/`, `06-coverage.md`,
`07-testplan.md`, `08-pr-description.md`, `09-review-responses.md`,
`sync-manifest.json`).
If they do, tell the
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

- `.artifacts/design/{issue-key}/01-context.md`

## When This Phase Is Done

Report your findings:
- Key requirements that drive design decisions
- Affected components and current patterns
- Constraints and open questions
- Assessment of readiness for `/draft`

Then **re-read the controller** (`controller.md`) for next-step guidance.
