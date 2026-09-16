---
name: ingest
description: Fetch the [UI] story, load UX handoff, PRD, and design document from shared locations, and explore the UI codebase and backend API.
---

# Ingest Context Skill

You are a frontend architect and technical researcher. Your job is to read the
`[UI]` story, load all upstream planning artifacts from their published
locations, explore the UI codebase and backend API, and produce a structured
context document that will inform the UI design phase.

## Your Role

Understand the requirements (from the story, UX handoff, PRD, and design
document), the current frontend architecture (from the codebase), and the
backend API surface well enough that the plan phase can make informed
component and state management decisions. Capture what exists, what needs
to change, and what constraints apply.

## Critical Rules

- **Read-only.** Jira access is read-only. Never create, update, or modify Jira issues.
- **Capture, don't design.** Record what you find — architectural decisions happen in `/plan`.
- **Published sources only.** Read upstream artifacts from the docs repo and Jira, never from another workflow's `.artifacts/` directory.
- **UX handoff is optional.** The `[UI]` story may not have a UX handoff artifact. If none exists, note it and proceed — the workflow must function for purely technical work.
- **Explore relevant areas only.** Don't map the entire codebase. Focus on UI components, hooks, routes, and API endpoints the story will affect.
- **Note unknowns.** If you can't determine something from the codebase, say so explicitly.
- **Re-invocation diffs before overwriting.** If `01-context.md` already exists, preserve it before exploring. After compiling new context, diff the key sections against the previous version and present changes to the user before overwriting (see Steps 2a and 8a).

## Shared Script

This skill delegates deterministic Jira issue fetching to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/fetch-issue.py
```

The script provides subcommands: `get` and `search`. See the script
header for full usage. It requires `JIRA_URL`, `JIRA_TOKEN`, and
`JIRA_EMAIL` environment variables for Jira Cloud API token auth
(Basic auth with `email:token`).

If the script returns a successful result but the issue key is missing
or empty, treat it as a retrieval failure — stop and report the error
before compiling context. Do not write `01-context.md` with empty fields.

## Process

### Step 1: Identify the Context

The user will provide one of:
- A Jira issue key or URL (a `[UI]` story)
- A path to an existing context document
- A description of the UI work to be done

**Jira input:** Extract the full Jira issue key, including the project
prefix (e.g., `PROJ-1234`, not just `1234`). Use this as `{issue-key}`
throughout the workflow.

**Non-Jira input:** When the user provides a path or description instead
of a Jira key, derive a stable context identifier from the input — for
example, a slug from the document filename or a short user-provided label.
Confirm the identifier with the user before creating the artifact directory.
Skip Jira retrieval in Step 3 and proceed directly to Step 4.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/ui-design/{issue-key}
```

### Step 2a: Check for Prior Ingest

If `.artifacts/ui-design/{issue-key}/01-context.md` already exists, this
is a re-invocation. Copy the existing file to
`.artifacts/ui-design/{issue-key}/01-context.md.prev` so it is preserved
for the diff in Step 8a.

### Step 3: Read the [UI] Story

Fetch the Jira issue using the shared script:

```bash
python3 "../../_shared/scripts/fetch-issue.py" get {issue-key}
```

From the story, extract:
- **Summary and description** — what the UI work entails
- **Acceptance criteria** — testable outcomes for the UI
- **Parent epic/feature** — for hierarchy context
- **Design Reference** — links to the design document, PRD, or UX handoff
- **Linked issues** — sibling stories (`[DEV]`, `[UX]`, `[QE]`) that
  provide implementation context
- **Labels and components** — for scoping codebase exploration

### Step 4: Resolve the Docs Repo

Read `.artifacts/config.json` for `docs_repo_path` and `docs_repo_remote`.

**If the config exists**, validate it:
1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the remote URL matches the configured `docs_repo_remote`

If any validation fails, inform the user and re-ask for the correct values.
Resolve `~` to an absolute path before saving. Update
`.artifacts/config.json` with the corrected values.

**If the config does not exist**, ask the user for the docs repo local path
and remote, validate them. Resolve `~` to the user's home directory so
the stored path is absolute. Write `.artifacts/config.json`.

### Step 5: Load Upstream Planning Artifacts

Search the docs repo for a directory whose name contains `{issue-key}` or
the parent feature key:

```bash
find "{docs_repo_path}" -type d \( -name "*{issue-key}*" -o -name "*{feature-key}*" \)
```

#### 5a: Load the PRD

Filter matches to directories containing `prd.md`. If exactly one match,
read it. If multiple, present them to the user and ask which is current.
If none, ask the user for the path.

Record the resolved PRD path.

#### 5b: Load the Design Document

Filter matches to directories containing `design.md`. Read it for:
- API Changes (§4.3) — endpoints, request/response shapes
- Data Model / Schema Changes (§4.2) — models the UI will consume
- Interface Changes (§5) — IC-N entries relevant to the UI
- Architecture (§4.1) — system topology the frontend interacts with
- RBAC / Tenancy (§4.7) — permission model for persona-aware UI

Record the resolved design document path.

#### 5c: Load the UX Handoff (Optional)

Filter matches to directories containing `05-handoff.md` (the UX handoff
artifact) or a file with `handoff` in its name.

If found, read it. Extract and record:
- **Component Mapping** — UI elements → design system components
- **State Matrix** — component states (empty, loading, error, populated, etc.)
- **Interaction Specs** — user flows, keyboard navigation, focus management
- **Data Annotations** — per-element data source types (API, User input,
  Configuration, Computed, Static, Unknown)
- **Persona-Specific Views** — user group differences, permission-gated actions
- **Accessibility Requirements** — WCAG, ARIA, keyboard, screen reader
- **Acceptance Criteria** — Given/When/Then with AC-N numbering

If not found, record: *"No UX handoff artifact found. Proceeding with PRD,
design document, and codebase context only."*

#### 5d: Load Clarifications

If `clarifications.md` exists alongside the PRD, read it. Note any locked
decisions — these are binding constraints.

### Step 6: Read Project Configuration

Check for and read these files if they exist:
- `AGENTS.md` — project conventions, coding standards, build commands
- `CLAUDE.md` — project-specific AI instructions
- `UI-ARCHITECTURE.md` — frontend-specific patterns discovered by the
  `ai-ready` workflow: restricted imports, generated files, test framework,
  component patterns, state management conventions

These inform how the UI design document should be structured and what
conventions to follow.

### Step 7: Explore the Codebase

Based on the story, UX handoff, and design document, identify and explore
the areas of the codebase that the UI work will affect. Focus on two domains:

#### 7a: Frontend Codebase

1. **Component structure:** How are components organized? What is the
   directory convention? (e.g., `src/components/`, feature-based folders,
   barrel exports)

2. **Affected components:** Which existing components will be modified or
   extended? Read their key files to understand current patterns — props,
   composition, and internal state.

3. **Hook patterns:** What custom hooks exist? How does the project handle
   data fetching (React Query, SWR, custom hooks, Redux thunks)? Where do
   hooks live?

4. **State management:** What state management approach does the project use?
   (Redux, Zustand, Context, Jotai, local state only) Where is global state
   defined? What patterns exist for derived/computed state?

5. **Routing:** What router is used? (React Router, Next.js, TanStack Router)
   How are routes organized? Where are lazy loading boundaries? What route
   guards or auth checks exist?

6. **Design system:** What component library is used? (PatternFly, MUI,
   custom) Are there project-specific wrappers?

7. **Testing patterns:** What test framework is used? (Jest, Vitest,
   Playwright, Cypress) Where do tests live? What patterns do existing
   component tests follow?

8. **TypeScript patterns:** How are types organized? Are there shared type
   definitions for API responses? What naming conventions are used?

#### 7b: Backend API Surface

1. **API types:** Find TypeScript type definitions, Go structs, or OpenAPI
   specs that define the API response shapes the frontend consumes.

2. **API client layer:** How does the frontend call the API? (fetch wrapper,
   axios instance, generated client) Where are API base URLs configured?

3. **Relevant endpoints:** Which API endpoints does the story's UI need?
   What do they return? What query parameters do they support (pagination,
   filtering, sorting)?

4. **Authentication/authorization:** How are API calls authenticated? What
   RBAC patterns exist on the API side?

Use file search (glob), content search (grep), and targeted file reading.
Focus on 15–25 key files that establish the patterns and boundaries of change.
If the last 3–5 files explored introduced no new patterns or constraints,
exploration is likely complete. Note what remains uncertain in the Open
Questions section.

### Step 8: Compile Context

Compile the story, upstream artifacts, and codebase findings into the
structure below. If this is a re-invocation (Step 2a found an existing file),
**do not write the file yet** — hold the compiled content and proceed to
Step 8a first.

If this is a first invocation, write
`.artifacts/ui-design/{issue-key}/01-context.md` with this structure:

```markdown
# UI Design Context — {issue-key}

## Story Summary

- **Story:** {issue-key} — {title}
- **Type:** [UI]
- **Parent:** {parent epic/feature key}
- **Jira:** {issue URL}

### Acceptance Criteria

{Bulleted list of the story's acceptance criteria, preserving AC-N IDs
 if present.}

### Linked Stories

| Key | Type | Summary | Relevance |
|-----|------|---------|-----------|
| {key} | [DEV] | {summary} | {how it relates to this UI work} |
| {key} | [UX] | {summary} | {how it relates} |

## Upstream Artifacts

### PRD Summary

- **PRD:** {resolved path in docs repo}
- **Clarifications:** {resolved path, or "None published"}

{Brief summary of the requirements relevant to this UI story.
 Preserve FR-N / NFR-N IDs for traceability.}

### Design Document Summary

- **Design:** {resolved path in docs repo}

{Summary of design sections relevant to the UI — API changes, data model,
 interface changes, architecture, RBAC/tenancy. Reference specific section
 numbers (§4.3, §5, etc.) so /plan can cite them.}

### UX Handoff Summary

- **Handoff:** {resolved path in docs repo, or "Not available"}

{If available: summary of component mapping, key interaction specs, data
 annotation source types, persona-specific views, accessibility
 requirements, and acceptance criteria count.

 If not available: "No UX handoff artifact. This [UI] story operates from
 PRD and design document context only."}

### Locked Decisions

{From PRD clarification log and design document. These are binding.
 If none: "No locked decisions from upstream artifacts."}

## Frontend Codebase Context

### Project Overview

- **Framework:** {e.g., React 18, Next.js 14}
- **Language:** {e.g., TypeScript 5.x}
- **Component Library:** {e.g., PatternFly 5, MUI 5, custom}
- **State Management:** {e.g., Redux Toolkit, Zustand, React Context}
- **Router:** {e.g., React Router v6, Next.js App Router}
- **Data Fetching:** {e.g., React Query, SWR, Redux thunks}
- **Test Framework:** {e.g., Vitest + Testing Library, Jest, Playwright}
- **Build Tool:** {e.g., Vite, Webpack, Next.js}

### Component Patterns

{How components are organized in this project. Directory structure,
 naming conventions, composition patterns.}

### Affected Components

{For each component the story will touch:}

#### {Component Name}
- **Location:** {path}
- **Purpose:** {what it does}
- **Current patterns:** {props, state, hooks used}
- **What changes:** {brief note on what the story requires}

### Hook Patterns

{Existing custom hooks relevant to this work. Data-fetching patterns,
 cache strategies, error handling conventions.}

### State Management Patterns

{How state is organized — slices/stores, selectors, actions. What
 belongs in global state vs. local state in this project.}

### Route Structure

{Current routing setup relevant to the story — file-based or config-based,
 lazy loading patterns, route guard patterns.}

### Testing Conventions

{Test framework, directory structure, naming conventions, what existing
 component tests look like, coverage expectations.}

## Backend API Context

### API Client

- **Client library:** {e.g., axios instance at src/api/client.ts}
- **Base URL config:** {how it's configured}
- **Auth pattern:** {how API calls are authenticated}

### Relevant Endpoints

{For each API endpoint the UI will consume:}

#### {Method} {path}
- **Purpose:** {what it does}
- **Request:** {params, query, body — key fields only}
- **Response:** {key fields and types}
- **Pagination:** {if applicable — cursor, offset, page-based}
- **Notes:** {filtering, sorting, known limitations}

### API Type Definitions

{Key TypeScript interfaces or type definitions for API responses that
 the frontend uses. Show structure, not full code.}

## Constraints and Considerations

{Technical constraints discovered during exploration — restricted imports,
 generated files, design system requirements, performance constraints,
 browser support, existing patterns the design should follow.}

## Open Questions

{Things you couldn't determine from the codebase or upstream artifacts
 that the plan phase will need to resolve.}
```

### Step 8a: Diff Against Prior Ingest (Re-invocation Only)

If Step 2a created a `.prev` file, compare `01-context.md.prev` against
the newly compiled content. Focus the diff on:

- Changes to the story's acceptance criteria
- Changes in upstream artifacts (PRD requirements, design sections, UX handoff)
- New or removed API endpoints
- Changes to affected components

Then check whether downstream artifacts exist (`02-ui-design.md`,
`03-api-findings.md`, `04-pr-description.md`, `05-review-responses.md`,
`sync-manifest.json`). If they do, tell the user:

- Which artifacts exist and may be affected
- Which specific changes are likely to affect them
- If `sync-manifest.json` exists, warn that stories have already been
  synced to Jira and re-ingesting may require manual Jira updates

Wait for the user to confirm before proceeding. If the user confirms,
write the compiled content to `01-context.md` and clean up the temp file.
If the user declines, delete the temp file and stop without overwriting.

### Step 9: Report to User

Present a brief summary:
- What story was read and its scope
- Which upstream artifacts were loaded (PRD, design doc, UX handoff)
- Which codebase areas were explored (frontend + backend)
- Key affected components identified
- API endpoints relevant to the UI work
- Any constraints or open questions discovered
- Whether the context is sufficient to proceed to `/plan`

If the user declined a re-invocation overwrite in Step 8a, report instead:
- What changes were found (summary of the diff)
- That the existing `01-context.md` was preserved unchanged

## Output

- `.artifacts/ui-design/{issue-key}/01-context.md`

## When This Phase Is Done

Report your findings:
- Story scope and acceptance criteria
- Upstream artifacts loaded (and any that were missing)
- Frontend architecture patterns discovered
- Backend API endpoints relevant to the UI
- Constraints and open questions
- Assessment of readiness for `/plan`

Then return to the invoking workflow router for completion guidance.
