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
${HOME}/.ai-workflows/_shared/scripts/fetch-issue.py
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
prefix (e.g., `PROJ-1234`, not just `1234`). Use this as `{workspace-id}`
throughout the workflow. Validate the extracted key against the pattern
`^[A-Z][A-Z0-9]+-[0-9]+$` (uppercase project prefix, hyphen, numeric
ID — e.g., `EDM-1234`, `OCPBUGS-42`). This ensures the value is a
well-formed Jira issue key before tagging the workspace as
`Origin: Jira`. If validation fails, stop and report the error before
creating the artifact directory.

**Non-Jira input:** When the user provides a path or description instead
of a Jira key, derive `{workspace-id}` from the input — for example, a
slug from the document filename or a short user-provided label. Validate
the identifier before proceeding: it must match the pattern
`^[A-Za-z0-9][A-Za-z0-9_-]{2,49}$` (3–50 characters, alphanumeric
start, only alphanumeric characters, hyphens, and underscores). Reject
identifiers containing path separators, dots, spaces, or other special
characters. Confirm the validated identifier with the user before
creating the artifact directory. Skip Jira retrieval in Step 3 and
proceed directly to Step 4.

### Step 2: Create Artifact Directory

**Collision check (non-Jira flow only).** When `{workspace-id}` was
derived from non-Jira input (a user-provided slug, not a Jira issue
key), check whether `.artifacts/ui-design/{workspace-id}/` already
exists. If it does, ask the user to confirm before proceeding:

*"The workspace directory `.artifacts/ui-design/{workspace-id}/`
already exists and contains prior artifacts. If you reuse this
workspace, `01-context.md` will be regenerated (overwritten) by this
ingest run, but all other phase artifacts (e.g., `02-ui-design.md`,
`03-api-findings.md`, `sync-manifest.json`) will be preserved. Do you
want to proceed, or provide a different workspace-id?"*

Wait for the user's choice. If they do not confirm, ask for a different
identifier, re-validate it (same rules as Step 1), and use it going
forward. If they confirm, proceed — preserving all existing artifacts
except `01-context.md`, which the ingest phase regenerates. Do not
delete or overwrite other phase artifacts during ingest.

```bash
mkdir -p ".artifacts/ui-design/{workspace-id}"
```

### Step 2a: Check for Prior Ingest

If `.artifacts/ui-design/{workspace-id}/01-context.md` already exists, this
is a re-invocation. Copy the existing file to
`.artifacts/ui-design/{workspace-id}/01-context.md.prev` so it is preserved
for the diff in Step 8a.

### Step 3: Read the [UI] Story

**Jira input.** Fetch the Jira issue using the shared script:

```bash
python3 "${HOME}/.ai-workflows/_shared/scripts/fetch-issue.py" get "{workspace-id}" --parent --parent-fields summary,status,key,parent --links
```

From the story, extract:
- **Summary and description** — what the UI work entails
- **Acceptance criteria** — testable outcomes for the UI
- **Parent epic/feature** — for hierarchy context (requires `--parent`)
- **Design Reference** — links to the design document, PRD, or UX handoff
- **Linked issues** — sibling stories (`[DEV]`, `[UX]`, `[QE]`) that
  provide implementation context (requires `--links`)
- **Labels and components** — for scoping codebase exploration

**Grandparent Feature chase.** The `--parent-fields` flag above includes
`parent`, which returns the parent's own parent key when one exists.
After the initial fetch, check whether the story's parent is already a
Feature. If the parent is not a Feature (e.g., it is an Epic), resolve
the grandparent:

- **If the parent's `parent` field is present as a nested object** (with
  sub-fields like `key`, `summary`) — the parent is an Epic whose parent
  is a Feature. Extract the grandparent key from the nested object and
  make a second fetch to retrieve the grandparent Feature:

  ```bash
  python3 "${HOME}/.ai-workflows/_shared/scripts/fetch-issue.py" get "{grandparent-key}" --fields summary,status,key,issuetype
  ```

  Use the grandparent (Feature) key as `{feature-key}` for docs-repo
  directory resolution in Steps 5 and beyond.

- **If the parent's `parent` field is present as a bare key string**
  (just an issue key like `"PROJ-100"`, with no nested fields) — the
  parent returns its own parent as a key reference only. Make a second
  fetch to retrieve that parent issue and check its type:

  ```bash
  python3 "${HOME}/.ai-workflows/_shared/scripts/fetch-issue.py" get "{bare-parent-key}" --fields summary,status,key,issuetype,parent
  ```

  If the fetched issue is a Feature, use its key as `{feature-key}`.
  If it is an Epic with its own parent, use that parent's key as
  `{feature-key}` (one additional level). Do not chase beyond two
  levels above the original story.

- **If the parent's `parent` field is absent** — the parent is either a
  Feature or an Epic with no grandparent (flat project structure). Check
  the parent's `issuetype`:
  - If the parent is a Feature, use the parent key as `{feature-key}`.
  - If the parent is an Epic with no grandparent, set `{feature-key}`
    to `"N/A"` — downstream phases (`/publish`, `/sync`) will use the
    epic as the parent for directory resolution and story creation.
    Record this in `01-context.md` so downstream phases can detect the
    flat hierarchy without repeating the chase.

Record the resolved `{feature-key}` in `01-context.md`'s Story Summary
so downstream phases (`/publish`, `/sync`) can use it for directory and
parent resolution without repeating the chase.

**Non-Jira input.** When the user provided a path or description instead
of a Jira issue key (as identified in Step 1), do not call
`fetch-issue.py`. Instead, compile the context from the supplied input:

1. Set `{title}` to the user-provided description or document filename
2. Set `{parent epic/feature key}` to `"N/A (local workspace)"`
3. Set `{issue URL}` to `"N/A — workspace derived from: {source description}"`,
   where `{source description}` is the path or label the user provided
4. Set all Jira-only values (linked issues, labels, components) to not
   applicable
5. Skip the Linked Stories table
6. Continue to Step 4 — do not attempt Jira retrieval

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

After resolving `docs_repo_path` from configuration (whether loaded from
an existing config or provided by the user), normalize it to an absolute
path before any downstream use:

```bash
DOCS_REPO_PATH="$(cd "${docs_repo_path}" && pwd)"
```

This resolves relative paths, `~` expansions, and symlinks to a
canonical absolute path. Use `DOCS_REPO_PATH` in all subsequent steps.

### Step 5: Load Upstream Planning Artifacts

Before using `docs_repo_path` in shell commands, validate that it is a
clean filesystem path: it must be an absolute path, must not contain
shell metacharacters (`$`, `` ` ``, `|`, `;`, `&`, newlines), and must
resolve to an existing directory. If validation fails, stop and ask
the user to correct the path in `.artifacts/config.json`.

Search the docs repo for a directory whose name contains `{workspace-id}` or
the parent feature key. Pass `docs_repo_path` as a quoted argument.

**When `{feature-key}` is available** (the Jira story has a parent
epic or feature), include both predicates:

```bash
find "${docs_repo_path}" -type d \( -name "*${workspace_id}*" -o -name "*${feature_key}*" \)
```

**When `{feature-key}` is empty or unavailable** (no parent epic, or
non-Jira input), search by `{workspace-id}` only — do not include an
empty feature-key predicate, as `-name "**"` matches every directory:

```bash
find "${docs_repo_path}" -type d -name "*${workspace_id}*"
```

#### 5.1: Load the PRD

Filter matches to directories containing `prd.md`. If exactly one match,
read it. If multiple, present them to the user and ask which is current.
If none, ask the user for the path.

Record the resolved PRD path.

#### 5.2: Load the Design Document

Filter matches to directories containing `design.md`. If exactly one
match, read it. If multiple, present them to the user and ask which is
current. If none, ask the user for the path.

Read the resolved design document for:
- API Changes (§4.3) — endpoints, request/response shapes
- Data Model / Schema Changes (§4.2) — models the UI will consume
- Interface Changes (§5) — IC-N entries relevant to the UI
- Architecture (§4.1) — system topology the frontend interacts with
- RBAC / Tenancy (§4.7) — permission model for persona-aware UI

Record the resolved design document path.

#### 5.3: Load the UX Handoff (Optional)

Filter matches to directories containing `handoff.md` (the published
canonical name from the `ux-design` workflow). If no match is found,
fall back to `05-handoff.md` (the private artifact name). If multiple
match, present them to the user and ask which is current. If none,
proceed without a handoff (it is optional).

If found, read it.

**Screenshot inspection.** Check the handoff's **Screenshot Index**
for image references (`SS-N` IDs). Images are embedded inline at User
Flows, State Matrix, and Persona-Specific Views sections.

- **If referenced:** Read and follow
  `../../_shared/recipes/screenshot-inspection.md` with
  `HANDOFF_DIR` = the handoff's directory and
  `MANIFEST_PATH` = `{HANDOFF_DIR}/screenshot-manifest.json`.
  Warn if the manifest's `context_revision`/`prototype_iteration` differ
  from the handoff header.
  After inspection, set the Screenshot Observations status to
  `inspected` (all images inspected), `partial` (some inspected),
  or `unavailable` (none inspected). Preserve each image's per-entry
  status and any user acceptance decision.

- **If none** (Screenshot Index says "None" or absent): Set
  `HAS_SCREENSHOTS = false`. Record the reason if stated.

- **If deferred** (user authorizes skipping inspection): Set
  `HAS_SCREENSHOTS = deferred`. Note reduced visual fidelity downstream.

**Provenance freshness check.** Look for `<!-- ai-workflow-provenance:`
in the handoff. If absent, warn the user it may not be finalized and ask
whether to proceed or wait. If they wait, skip the handoff.

Extract: Component Mapping, State Matrix, Interaction Specs, Data
Annotations (source types), Persona-Specific Views, Accessibility
Requirements, Acceptance Criteria (Given/When/Then, AC-N), and
Feasibility & Phasing (MVP vs Final Vision, implementation order).

If not found: *"No UX handoff artifact. Proceeding with PRD, design
document, and codebase context only."*

#### 5.4: Load Clarifications

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

#### 7.1: Frontend Codebase

1. **Component structure:** How are components organized? What is the
   directory convention? (e.g., `src/components/`, feature-based folders,
   barrel exports)

2. **Affected components:** Which existing components will be modified or
   extended? Read their key files to understand current patterns — props,
   composition, and internal state.

3. **Hook patterns:** Custom hooks, data fetching approach (React Query,
   SWR, Redux thunks), hook locations
4. **State management:** Approach (Redux, Zustand, Context, Jotai,
   local), global state location, derived/computed state patterns
5. **Routing:** Router (React Router, Next.js, TanStack), route
   organization, lazy loading, guards
6. **Design system:** Component library (PatternFly, MUI, custom),
   project-specific wrappers
7. **Testing patterns:** Framework (Jest, Vitest, Playwright, Cypress),
   test location, existing component test patterns
8. **TypeScript patterns:** Type organization, shared API type
   definitions, naming conventions

#### 7.2: Backend API Surface

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
If tools are unavailable, stop and report before producing codebase
context. Focus on 15-25 key files. Stop exploring when 3-5 consecutive
files introduce no new patterns. Note remaining unknowns in Open Questions.

#### No-Evidence Stop Gate

If codebase exploration found **none** of: `UI-ARCHITECTURE.md`,
component directories (`src/components/` etc.), or backend API type
definitions — stop before writing `01-context.md`. Report which searches
were attempted and their results. Wait for the user to provide a
corrected path or explicitly confirm proceeding with limited evidence.
If the user provides a corrected path, re-run Step 7 using that path.

### Step 8: Compile Context

Compile the story, upstream artifacts, and codebase findings into the
structure below. If this is a re-invocation (Step 2a found an existing file),
**do not write the file yet** — hold the compiled content and proceed to
Step 8a first.

**Non-Jira placeholder values.** When `{workspace-id}` was derived from
non-Jira input (Step 1), fill the Story Summary with substitute values:
`{title}` = the user-provided description or document filename;
`{parent epic/feature key}` = `"N/A (local workspace)"`;
`{issue URL}` = `"N/A — workspace derived from: {source description}"`,
where `{source description}` is the path or label the user provided.
Skip the Linked Stories table if no Jira data is available.

If this is a first invocation, write
`.artifacts/ui-design/{workspace-id}/01-context.md` with this structure:

```markdown
# UI Design Context — {workspace-id}

## Story Summary

- **Origin:** {`Jira` if workspace-id came from a Jira issue key; `Non-Jira` if derived from non-Jira input}
- **Story:** {workspace-id} — {title}
- **Type:** [UI]
- **Parent:** {parent epic/feature key, or "N/A (local workspace)" for non-Jira input}
- **Feature:** {resolved feature-key from grandparent chase, or parent key if parent is a Feature, or "N/A" if unavailable}
- **Jira:** {issue URL, or "N/A — workspace derived from: {source description}" for non-Jira input}

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

### Screenshot Observations

- **Screenshots:** {`inspected` / `partial` / `none` / `deferred` / `unavailable`}
- **Manifest revision:** {context_revision from manifest, or "N/A"}
- **Manifest iteration:** {prototype_iteration from manifest, or "N/A"}

{If `inspected`/`partial`: one row per image per the inspection recipe schema.}

| ID | Status | Identity | Ref | Expected SHA | Observed SHA | Observation | Spec Match | Notes |
|----|--------|----------|-----|-------------|-------------|-------------|------------|-------|
| SS-1 | inspected | verified | `screenshots/SS-1-desc.png` | `a1b2…` | `a1b2…` | {layout, state} | Yes/No | — |

{`none`/`deferred`/`unavailable`: one-line reason and per-image status.}

### Feasibility & Phasing

{From UX handoff: MVP vs Final Vision, Supported vs Needs backend,
 phasing recommendations. Informs /plan and /sync.
 If unavailable: "No feasibility or phasing information available."}

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

If Step 2a created a `.prev` file, diff `01-context.md.prev` against the
compiled content. Focus on: acceptance criteria, upstream artifact changes,
API endpoints, and affected components.

Check for downstream artifacts (`02-ui-design.md`, `03-api-findings.md`,
`04-pr-description.md`, `05-review-responses.md`, `sync-manifest.json`).
If any exist, report which may be affected and warn about Jira sync
implications. Present the diff summary and wait for the user to confirm.
If they confirm, write the compiled content to `01-context.md` and delete
`01-context.md.prev` and any temporary file. If they decline, discard the
compiled content, delete `01-context.md.prev`, report that `01-context.md`
was preserved, and stop.

### Step 9: Report to User

Summarize: story scope, upstream artifacts loaded, codebase areas
explored, affected components, relevant API endpoints, constraints,
open questions, and readiness for `/plan`. If re-invocation was
declined, report the diff summary and that `01-context.md` was preserved.

## Output

- `.artifacts/ui-design/{workspace-id}/01-context.md`

## When This Phase Is Done

Report findings then return to the invoking workflow router.
