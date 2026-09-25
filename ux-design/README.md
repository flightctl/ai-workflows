# UX Design Workflow

A UX design workflow that takes a `[UX]` story through discovery, user
research, prototyping, and heuristic evaluation to produce a validated
design handoff artifact for the `ui-design` workflow. `/ingest` follows the
story's references to load the PRD, design document, and sibling stories from
shared locations, so the design is grounded in the feature's real personas,
non-functional requirements, and technical constraints.

## Phase Flow

```mermaid
graph TD
    ingest([ingest]) --> research
    ingest --> prototype
    research --> prototype
    prototype --> evaluate
    evaluate -->|iterate| prototype
    evaluate -->|ready| handoff
    handoff --> revise
    handoff --> publish
    revise --> publish
    publish --> respond
```

Research is conditional — skip directly to `/prototype` if the researcher
already has validated data or well-understood user needs.

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Jira access (MCP or CLI) | For `/ingest` | Fetch the `[UX]` story, its Design Reference, and sibling stories |
| Docs repo (published PRD + design doc) | For `/ingest` | Load the PRD and design document the design must honor |
| UXD Research, Prototype, and Design plugins | Required | Discovery, prototyping, evaluation, and handoff skills |
| Jira access (Atlassian MCP) | For Full `/evaluate` | `uxd-prototype-evaluate` fetches story acceptance criteria |
| `python3`, Node/npm, and Playwright Chromium | For Full `/evaluate` | Prototype evaluation helper scripts and browser walkthroughs |

`/ingest` loads all upstream inputs from **shared** locations (the published
docs repo and Jira) — never from another workflow's private `.artifacts/`.
Missing inputs are recorded as gaps, not fabricated; `/handoff`'s feasibility
check marks its findings "unverified" when the design document was unavailable.

## Phases

| Phase | Command | Purpose | Artifact(s) |
|-------|---------|---------|-------------|
| Ingest | `/ingest` | Load PRD + design doc + sibling stories, frame the problem, identify user groups, survey landscape | `01-discovery.md` |
| Research | `/research` | Conduct user research, synthesize findings | `02-research.md` |
| Prototype | `/prototype` | Generate design prototypes from research | `03-prototype/` |
| Evaluate | `/evaluate` | Heuristic evaluation and usability assessment | `04-evaluation.md` |
| Design handoff | `/handoff` | Produce implementation-ready design spec | `05-handoff.md` |
| Revise | `/revise` | Incorporate stakeholder feedback | `05-handoff.md` (updated) |
| Publish | `/publish` | Push handoff spec to docs repo for review | `06-pr-description.md`, `publish-metadata.json`, PR in docs repo |
| Respond | `/respond` | Address PR reviewer comments | Updated `05-handoff.md` |

## Typical Flow

```text
/ingest EDM-1234
  → follows the [UX] story's Design Reference to load the PRD, design
    document, and sibling stories from the docs repo and Jira
  → frames the problem, identifies user groups
  → surveys competitive landscape
  → writes .artifacts/ux-design/EDM-1234/01-discovery.md

/research                          (conditional — skip if you have data)
  → conducts user research
  → synthesizes findings into themed insights
  → documents persona-specific needs
  → writes 02-research.md

/prototype
  → generates design prototypes informed by research
  → writes 03-prototype/ (files + prototype-notes.md)

/evaluate
  → runs heuristic evaluation against prototype
  → writes 04-evaluation.md
  → loops back to /prototype if critical issues found

/handoff
  → synthesizes all artifacts into implementation spec
  → maps UI elements to design system components
  → annotates data requirements per UI element
  → documents persona-specific views
  → reality-checks the design against the technical design (final vision
    vs. MVP/phase-1 split when constraints require it)
  → writes 05-handoff.md

/publish
  → pushes 05-handoff.md to docs repo
  → opens PR for team review

/respond
  → addresses PR review comments
  → updates 05-handoff.md as needed
```

## Artifacts

All artifacts are stored in `.artifacts/ux-design/{issue-key}/`.

```text
.artifacts/ux-design/EDM-1234/
  01-discovery.md              (problem framing, user groups, landscape)
  02-research.md               (research findings, insights, recommendations)
  03-prototype/                (mirrored skill output + design rationale)
    prototype-notes.md         (design decisions, user stories covered)
    prototype/                 (generated prototype files, from the skill)
  04-evaluation.md             (heuristic eval report, readiness assessment)
  04-eval-raw/                 (raw skill reports, mirrored from the eval skills)
  05-handoff.md                (implementation spec, component mapping, AC)
  06-pr-description.md         (generated PR body for /publish)
  publish-metadata.json        (PR tracking: number, URL, branch, head SHA)
  provenance.json              (authoring provenance log)
```

## Contract for the handoff

`05-handoff.md` is the primary artifact consumed by the `ui-design` workflow.
It contains:

- **Component mapping** — UI elements mapped to design system components
- **Interaction specs** — every user interaction documented
- **State enumeration** — empty, loading, error, populated, responsive
- **Data annotations** — what data each UI element needs (with gaps flagged)
- **Persona-specific views** — where user groups interact differently
- **Acceptance criteria** — testable, traced to research findings
- **Feasibility and phasing** — design reality-checked against the technical
  design, with a final-vision/MVP split when constraints require it
- **Research context** — why decisions were made

## UXD Marketplace Skills

This workflow uses skills from the
[UXD AI Skills repository](https://github.com/rh-uxd/ai-helpers). The installer
clones its current `main` branch and refreshes an existing clean checkout on
each run of `./install.sh`; it does not pin a commit. The upstream team will
notify us before breaking changes.

The installer links skill folders by bare name for Claude Code, Cursor, Gemini,
and Codex. Invoke the skill name directly rather than using a plugin-marketplace
namespace.

| Skill | Upstream plugin | Used by |
|-------|-----------------|---------|
| `uxd-discovery` | `uxd-research` | `/ingest` |
| `uxd-prototype-create` | `uxd-prototype` | `/prototype` |
| `uxd-prototype-export` | `uxd-prototype` | Optional export from prototype creation |
| `uxd-prototype-evaluate` | `uxd-prototype` | `/evaluate` (Full) |
| `uxd-prototype-publish` | `uxd-prototype` | Optional standalone publishing |
| `uxd-research-heuristic-eval` | `uxd-research` | `/evaluate` |
| `uxd-evaluate-design-heuristics` | `uxd-research` | `/evaluate` |
| `uxd-design-handoff` | `uxd-design` | `/handoff` |
| `uxd-figma-read` | `uxd-design` | Optional standalone use; prototype creation reads Figma links directly |

**Runtime paths:** Some upstream skills use `CLAUDE_SKILL_DIR` and
`CLAUDE_PLUGIN_ROOT` to locate scripts or plugin resources. Claude Code supplies
these variables. In other runtimes, resolve a skill under
`${HOME}/.uxd-ai-skills/plugins/<plugin>/skills/<skill>` and its plugin root at
`${HOME}/.uxd-ai-skills/plugins/<plugin>`. Supply the expected path to helpers
when needed. Full evaluation also requires Atlassian MCP access, Node/npm, and
Playwright Chromium; if those prerequisites are unavailable, do not silently
skip or downgrade the requested Full evaluation.

## Directory Structure

```text
ux-design/
├── SKILL.md                    # Workflow entry point
├── guidelines.md               # Behavioral rules and guardrails
├── README.md                   # This file
├── skills/
│   ├── controller.md           # Phase dispatcher and transitions
│   ├── ingest.md               # Frame problem, identify user groups
│   ├── research.md             # Conduct user research
│   ├── prototype.md            # Generate design prototypes
│   ├── evaluate.md             # Heuristic evaluation
│   ├── handoff.md              # Design-to-implementation spec
│   ├── revise.md               # Incorporate stakeholder feedback
│   ├── publish.md              # Push to docs repo PR
│   └── respond.md              # Address PR review comments
└── commands/
    ├── ingest.md               # /ingest command
    ├── research.md             # /research command
    ├── prototype.md            # /prototype command
    ├── evaluate.md             # /evaluate command
    ├── handoff.md              # /handoff command
    ├── revise.md               # /revise command
    ├── publish.md              # /publish command
    └── respond.md              # /respond command
```

## Getting Started

```bash
# Install the workflow
./install.sh claude --workflows ux-design

# Or install all workflows
./install.sh all
```

Then in your project, run `/ingest` with a Jira issue key or feature
description to begin.
