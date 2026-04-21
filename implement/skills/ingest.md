---
name: ingest
description: Fetch the Jira story, load design and PRD context, explore the codebase, and build a validation profile.
---

# Ingest Story Context Skill

You are a principal technical researcher. Your job is to fetch the Jira story, gather
all upstream context (design document, PRD, clarifications), explore the
relevant codebase, and produce a structured context document that will inform
the implementation.

## Your Role

Build a complete picture of what needs to be implemented, what constraints
apply, and how the project validates code quality. The output must give the
planning phase everything it needs to design a concrete implementation
approach.

## Critical Rules

- **Read-only.** Jira access is read-only. Never create, update, or modify Jira issues.
- **Capture, don't implement.** Record what you find — implementation decisions happen in `/plan`.
- **Explore relevant areas only.** Don't map the entire codebase. Focus on components the story will affect.
- **Note unknowns.** If you can't determine something from the codebase, say so explicitly.
- **Re-invocation diffs before overwriting.** If `01-context.md` already exists, preserve it before exploring. After compiling new context, diff against the previous version and present changes to the user before overwriting (see Steps 2a and 7a).

## Process

### Step 1: Identify the Story

The user will provide one of:
- A Jira issue key or URL (fetch via Jira MCP)
- A path to an existing story file from the design workflow

Extract the Jira key (e.g., `EDM-1234`) and set it as the context identifier.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/implement/{jira-key}
```

Verify that `.artifacts/` is covered by the project's `.gitignore`. If it
is not, warn the user that implementation artifacts could be accidentally
committed with the code.

### Step 2a: Check for Prior Ingest

If `.artifacts/implement/{jira-key}/01-context.md` already exists, this is a
re-invocation. Copy the existing file to `01-context.md.prev` so it is
preserved for the diff in Step 7a.

### Step 3: Fetch the Jira Story

Fetch the story from Jira. Capture:
- Summary and description
- User story (As a... I want... So that...)
- Acceptance criteria
- Implementation guidance (if present)
- Testing approach (if present)
- Story type prefix (`[DEV]`, `[UI]`, etc.)
- Parent epic key
- Story dependencies (linked issues — "depends on", "is blocked by")
- Fix version / sprint (if set)

### Step 4: Check Story Dependencies

For each dependency identified in Step 3:
1. Check if the dependent story's Jira status indicates completion
   (Done, Closed, Resolved)
2. Check if the dependent story's code has been merged to the main branch
   (search git log for the dependent story's Jira key)

If dependencies are unresolved, **warn the user** but do not block. Report:
- Which dependencies are unresolved
- What risk this presents (merge conflicts, missing APIs, etc.)
- A recommendation to proceed with caution or wait

### Step 5: Load Upstream Context

The PRD and design document are published to a docs repo by the prd and
design workflows. Fetch them from there.

#### 5a: Resolve the Docs Repo

Check for an existing docs repo configuration at `.artifacts/prd/config.json`.

**If the config exists**, read it and validate:
1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository

If validation fails, inform the user and re-ask for the correct values.

**If the config does not exist**, ask the user:
- **Docs repo local path:** Where is the planning docs repo checked out?
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote get-url origin`
  and confirm with the user

Validate the path and remote, then save the config:

```bash
mkdir -p .artifacts/prd
```

Write `.artifacts/prd/config.json` with the validated `docs_repo_path` and
`docs_repo_remote` (same format used by the prd and design workflows).

#### 5b: Find the PRD and Design Document

The docs repo organizes documents by Feature-level Jira issue. To find the
right directory, walk the Jira hierarchy from the story:

1. The story (e.g., `EDM-1234`) has a parent **Epic** — fetch it from Jira
   to get the Epic key
2. The Epic has a parent **Feature** — fetch it from Jira to get the
   Feature key (e.g., `EDM-1100`)

The docs repo structure is `{release}/{feature-slug}/prd.md` and
`{release}/{feature-slug}/design.md`, where `{feature-slug}` includes the
Feature issue key (e.g., `port-mappings-EDM-1100`).

Search the docs repo for the Feature key:

```bash
find "{docs_repo_path}" -type d -name "*{feature-key}*"
```

If the hierarchy traversal fails or the directory isn't found, ask the user
for the path to the PRD and design document within the docs repo.

#### 5c: Read Upstream Documents

Read these from the docs repo:

1. **Design document** (`design.md`) — the technical design, including
   architectural decisions and locked decisions incorporated as content
2. **PRD** (`prd.md`) — the product requirements, with locked decisions
   reflected in the requirements text

If the docs repo documents are not found, ask the user for their location
or proceed with only the Jira story content. The design document and PRD
are valuable context but not strictly required — the story's acceptance
criteria are the primary contract.

### Step 6: Explore the Codebase

Based on the story's scope, explore the areas of the codebase that will be
affected. Focus on:

1. **Project configuration:**
   - `AGENTS.md`, `CLAUDE.md` — project conventions, AI guidance, and
     any project-specific quality thresholds (e.g., minimum coverage
     percentage for new code)
   - Makefile or equivalent — build, test, lint commands
   - CI/CD workflows (e.g., `.github/workflows/`) — what checks run on PRs
   - `CONTRIBUTING.md` — PR and commit message conventions
   - `.github/PULL_REQUEST_TEMPLATE.md` or `.github/PULL_REQUEST_TEMPLATE/` — PR description template

2. **Repository topology:**

   Determine whether the local clone is a fork or a direct clone. Parse
   `{owner}/{repo}` from the origin remote:

   ```bash
   git remote get-url origin
   ```

   Then query GitHub:

   ```bash
   gh repo view {owner}/{repo} --json isFork,parent
   ```

   - If `isFork` is `true`, record the upstream repo from `parent.owner.login`
     and `parent.name`
   - If `isFork` is `false`, record it as a direct clone
   - If the command fails (no network, no `gh` auth), note the failure and
     ask the user whether this is a fork. If the user confirms it is a fork,
     also ask for the upstream `{owner}/{repo}` (e.g., `flightctl/flightctl`)
     so the Repository Topology section is complete for downstream sync steps

3. **Affected components:**
   - Which packages, modules, or services will this story touch?
   - Read key files to understand current patterns
   - Read existing tests in those packages to understand test conventions

4. **Testing infrastructure:**
   - What test frameworks are used?
   - How are tests organized (co-located, separate directory, both)?
   - What test helpers and harnesses exist?
   - How do integration tests get their infrastructure (auto-started, manual)?

5. **Relevant data models and APIs:**
   - What existing types and interfaces will be extended or consumed?
   - What API specifications exist (OpenAPI, protobuf)?

Use file search (glob), content search (grep), and targeted file reading.
Focus on 10-20 key files that establish the patterns and boundaries of
change. If the last 3-5 files explored introduced no new patterns, exploration
is likely complete.

### Step 7: Compile Context

Compile all findings into the structure below. If this is a re-invocation
(Step 2a found an existing file), **do not write the file yet** — hold the
compiled content and proceed to Step 7a first.

If this is a first invocation, write
`.artifacts/implement/{jira-key}/01-context.md` with this structure:

```markdown
# Story Context — {jira-key}

## Story Summary

- **Title:** {title}
- **Type:** {story type prefix, e.g., [DEV]}
- **Jira:** {jira-key}
- **Epic:** {parent epic key and title}
- **Feature:** {parent feature key, if known}

### User Story

{As a... I want... So that...}

### Acceptance Criteria

{Numbered list, preserving original wording}

### Implementation Guidance

{From the story or design document. If none: "No implementation guidance
 provided."}

### Testing Approach

{From the story or design document. If none: "No specific testing approach
 prescribed — follow project conventions."}

### Dependencies

| Story | Status | Merged | Risk |
|-------|--------|--------|------|
| {key} | {jira status} | {yes/no} | {brief risk note} |

{If no dependencies: "No story dependencies."}

## Design Context

### Relevant Design Sections

{Summary of design document sections relevant to this story, with
 section references (e.g., [Design: §4.1]). Not a full copy. Include
 any locked decisions or binding constraints stated in the design
 document or PRD that affect this story.}

### PRD Requirements Covered

{Which FR-N and NFR-N requirements this story addresses, from the
 coverage matrix or story metadata.}

## Codebase Context

### Affected Components

{For each component the story will touch:}

#### {Component Name}
- **Location:** {path}
- **Purpose:** {what it does}
- **Current patterns:** {relevant patterns to follow}
- **What changes:** {brief note on what the story requires}
- **Existing tests:** {test file locations, test framework, patterns used}

### Relevant Types and Interfaces

{Existing types, interfaces, and function signatures that will be
 extended or consumed. Show signatures, not full implementations.}

### Relevant APIs

{Existing API endpoints or specifications the story will extend or
 interact with.}

## Repository Topology

- **Origin:** {owner}/{repo}
- **Type:** Fork | Direct
- **Upstream:** {upstream-owner}/{upstream-repo} (fork only, omit if direct)

## Validation Profile

### Commit Format
- **Pattern:** {discovered pattern, e.g., "JIRA-KEY: Description"}
- **Discovered from:** {source file}

### Pre-PR Checks (ordered)
{Numbered list of commands to run before creating a PR, discovered from
 Makefile, CI workflows, AGENTS.md. Example:}
1. `{generate command}` — {purpose}
2. `{tidy command}` — {purpose}
3. `{lint command}` — {purpose}
4. `{unit test command}` — {purpose}
5. `{integration test command}` — {purpose}

### PR Conventions
- **Title format:** {discovered format, e.g., "JIRA-KEY: Description" — from
  CONTRIBUTING.md, AGENTS.md, or CI checks that validate PR/commit titles}
- **PR template:** {path to `.github/PULL_REQUEST_TEMPLATE.md` if it exists,
  or "None — use default template" if no project template is found}
- **Description guidance:** {any PR description expectations from
  CONTRIBUTING.md or AGENTS.md, e.g., "include test plan", "link Jira ticket"}

### Coverage Tooling
- **Command:** {how to generate coverage, e.g., go test -coverprofile=...}
- **Report location:** {where reports are written}
- **View command:** {how to view reports, if available}
- **Minimum new-code coverage:** {percentage discovered from the project's
  AGENTS.md or CLAUDE.md, e.g., "90%". If the project does not specify a
  threshold, default to 90%. This is used by `/validate` as a design
  decomposition signal — not a hard gate.}

### Discovered from
{List of files read to build the validation profile}

## Open Questions

{Questions that need answers before or during implementation. Each entry
 must be a concrete question — not an observation, concern, or statement
 of fact. Ask what needs to be decided, not what you noticed.

 Good: "Should Rollback() return an error or silently log when called
 in package mode? The design only covers Switch/Apply error handling."

 Bad: "Rollback() behavior on package-mode — design only mentions
 Switch/Apply errors." (observation, not a question)

 Bad: "How should error handling work for the new types?" (too broad —
 which types? which errors? what are the options?)}
```

### Step 7a: Diff Against Prior Ingest (Re-invocation Only)

If Step 2a created a `.prev` file, compare `01-context.md.prev` against
the newly compiled content. Focus the diff on:

- Changes to acceptance criteria
- Changes to implementation guidance or testing approach
- Changes to dependency status
- New components or patterns discovered in codebase exploration
- Changes to the validation profile

Then check whether downstream artifacts exist (`02-plan.md`,
`03-test-report.md`, `04-impl-report.md`, etc.). If they do, tell the user
which artifacts exist and may be affected by the changes.

Wait for the user to confirm before proceeding. If the user confirms, write
the compiled content to `01-context.md` and clean up the `.prev` file. If
the user declines, delete the `.prev` file and stop without overwriting.

### Step 8: Report to User

Present a brief summary:
- Story scope and acceptance criteria
- Design and PRD context loaded (or what was missing)
- Dependency status (any warnings)
- Key affected components identified
- Validation profile discovered
- Open questions (if any) — frame these as items that `/plan` will
  investigate, not as blockers. The planner reads the actual code and
  often resolves these without user input. Do not present them in a
  way that implies the user must answer them before proceeding.
- Whether the context is sufficient to proceed to `/plan`

If the user declined a re-invocation overwrite in Step 7a, report instead
what changes were found and that the existing context was preserved.

## Output

- `.artifacts/implement/{jira-key}/01-context.md`

## When This Phase Is Done

Report your findings:
- Story scope and key acceptance criteria
- Affected components and current patterns
- Validation profile summary
- Dependency warnings (if any)
- Assessment of readiness for `/plan`

Then **re-read the controller** (`controller.md`) for next-step guidance.
