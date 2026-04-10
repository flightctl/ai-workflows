# Design Workflow

A design-and-decompose workflow that takes a PRD, drafts a technical design document, breaks work into Jira-ready epics and stories, and manages review via GitHub PRs.

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Jira access (MCP or CLI) | For `/ingest`, `/sync` | Fetch Feature issue, create epics/stories |
| GitHub CLI (`gh`) | For `/publish`, `/respond` | Create PRs, post review comments |
| Git | Yes | Branch management, commits |

## Phases

| Phase | Command | Purpose | Artifact(s) |
|-------|---------|---------|-------------|
| Ingest | `/ingest` | Read PRD, explore codebase | `01-context.md` |
| Design | `/draft` | Draft design document | `02-design.md` |
| Decompose | `/decompose` | Break into epics and stories | `03-epics.md`, `04-stories/`, `05-coverage.md` |
| Revise | `/revise` | Incorporate feedback | Updated design and/or stories |
| Publish | `/publish` | Post design doc as GitHub PR | `06-pr-description.md` |
| Respond | `/respond` | Address reviewer comments | `07-review-responses.md` |
| Sync | `/sync` | Create Jira epics and stories | `sync-manifest.json` |

## Typical Flow

```text
/ingest EDM-2324
  → reads PRD from .artifacts/prd/EDM-2324/03-prd.md
  → explores affected codebase areas
  → writes .artifacts/design/EDM-2324/01-context.md

/draft
  → generates design document using templates/design.md structure
  → follows templates/section-guidance.md for content standards
  → writes 02-design.md

/decompose
  → breaks design into epics and stories
  → validates coverage against PRD requirements
  → writes 03-epics.md, 04-stories/ (epics + stories), 05-coverage.md

/revise
  → user reviews, requests changes to design and/or decomposition
  → artifacts updated, consistency maintained
  → repeatable

/publish
  → commits design document to feature branch in docs repo
  → creates draft GitHub PR
  → writes 06-pr-description.md

/respond
  → fetches PR review comments
  → proposes responses (user approves before posting)
  → updates design document if needed
  → repeatable

/sync
  → previews Jira issues to be created (dry run)
  → creates epics under the Feature, stories under epics
  → records created issues in sync-manifest.json
```

## Artifacts

All artifacts are stored in `.artifacts/design/{issue-number}/`.

Epic and story files live under `04-stories/`. Each file maps 1:1 to a
Jira issue:

```text
.artifacts/design/EDM-2324/
  01-context.md
  02-design.md
  03-epics.md                          (metadata: ordering, dependencies)
  04-stories/
    epic-1-image-building.md           (→ Jira Epic)
    epic-1/
      story-01-scaffold-pipeline.md    (→ Jira Story)
      story-02-add-validation.md       (→ Jira Story)
    epic-2-deployment.md               (→ Jira Epic)
    epic-2/
      story-01-deploy-config.md        (→ Jira Story)
  05-coverage.md
  06-pr-description.md
  07-review-responses.md
  publish-metadata.json
  sync-manifest.json
```

## Design Document Template

The design document template (`templates/design.md`) follows the team's established structure:

1. Overview
2. Goals and Non-Goals
3. Motivation / Background
4. Design
   - 4.1 Architecture
   - 4.2 Data Model / Schema Changes
   - 4.3 API Changes
   - 4.4 Scalability
   - 4.5 Security Considerations
   - 4.6 Failure Handling and Recovery
   - 4.7 RBAC / Tenancy
   - 4.8 Extensibility / Future-Proofing
5. Alternatives Considered
6. Observability and Monitoring
7. Impact and Compatibility
8. Open Questions

Section-level guidance for the AI is in `templates/section-guidance.md`.

## Task Decomposition

The decomposition follows the team's Jira hierarchy:

- **Feature** (exists in Jira — input to this workflow)
  - **Epic** — user-value oriented, standalone, T-shirt sized
    - **Story** — right-sized, includes functionality + testing, prefixed with `[DEV]`/`[UI]`/`[UX]`/`[QE]`/`[DOCS]`/`[CI]`

Key constraints:
- Each epic delivers complete functionality independently
- Each story leaves the system in a stable state (CI/CD to main)
- Every story includes both functionality and testing (no deferred test stories)
- Tests validate the software's contract, not its implementation — use test types appropriate to the change (unit, integration, e2e)
- A coverage matrix ensures all PRD requirements are addressed

## Jira Sync

The `/sync` phase creates Jira issues from the approved decomposition:

- **Dry-run first** — always previews what would be created
- **Batch creation** — epics first (confirm), then stories per epic (confirm)
- **Idempotent** — tracks created issues in `sync-manifest.json`; re-running creates only new items
- **Create-only behavior** — never modifies or deletes existing Jira issues

## Directory Structure

```text
design/
├── SKILL.md                    # Workflow entry point
├── guidelines.md               # Behavioral rules and guardrails
├── README.md                   # This file
├── templates/
│   ├── design.md               # Design document template
│   └── section-guidance.md     # AI instructions per section
├── skills/
│   ├── controller.md           # Phase dispatcher and transitions
│   ├── ingest.md               # Read PRD, explore codebase
│   ├── draft.md                # Draft design document
│   ├── decompose.md            # Break into epics and stories
│   ├── revise.md               # Incorporate feedback
│   ├── publish.md              # Create GitHub PR
│   ├── respond.md              # Address review comments
│   └── sync.md                 # Create Jira issues
└── commands/
    ├── ingest.md               # /ingest command
    ├── draft.md                # /draft command
    ├── decompose.md            # /decompose command
    ├── revise.md               # /revise command
    ├── publish.md              # /publish command
    ├── respond.md              # /respond command
    └── sync.md                 # /sync command
```

## Project-Level Template Override

Projects can customize the design document template by providing their own at a well-known location. The `/draft` phase checks for overrides in this order:

1. Path specified in the project's `CLAUDE.md` or `AGENTS.md`
2. `.design/templates/design.md` at the project root
3. Workflow's built-in template (fallback)

The same applies to `section-guidance.md`.

## Getting Started

```bash
# Install the workflow
./install.sh claude --workflows design

# Or install all workflows
./install.sh all
```

Then in your project, run the `design` workflow's `ingest` command for your Jira issue (e.g., EDM-2324).
