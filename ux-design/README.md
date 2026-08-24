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
| UXD skills (`uxd-workshop`) | Required | Prototype generation, heuristic evaluation, discovery, handoff |
| `python3` on PATH | For `/evaluate` (Standard/Full) | `uxd-prototype-evaluate` helper scripts |

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
| Handoff | `/handoff` | Produce implementation-ready design spec | `05-handoff.md` |
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

## Handoff Contract

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

This workflow requires skills from the
[UXD AI Skills marketplace](https://github.com/rh-uxd/ai-helpers).
These skills are a hard dependency — phases that use them will stop and prompt
you to run `./install.sh` if they are missing.

`install.sh` installs them **AI-agnostically**: it clones the `rh-uxd/ai-helpers`
repo (pinned to a specific commit) and symlinks each skill into the skills
directory for your AI tool (Claude Code, Cursor, or Gemini). The skills are
installed and invoked by **bare name** (`uxd-discovery`, `uxd-prototype-create`,
…), *not* through Claude Code's `/uxd-workshop:<skill>` plugin-marketplace
namespace — the bare-name form is the one that resolves across all three tools.

| Skill | Plugin | Used by |
|-------|--------|---------|
| `uxd-discovery` | `uxd-workshop` | `/ingest` |
| `uxd-prototype-create` | `uxd-workshop` | `/prototype` |
| `uxd-research-heuristic-eval` | `uxd-workshop` | `/evaluate` |
| `uxd-evaluate-design-heuristics` | `uxd-workshop` | `/evaluate` |
| `uxd-prototype-evaluate` | `uxd-workshop` | `/evaluate` (Standard/Full depth) |
| `uxd-design-handoff` | `uxd-workshop` | `/handoff` |

`uxd-prototype-create` reads Figma links directly, so the workflow does not
invoke `uxd-figma-read` separately (`install.sh` still symlinks it if you want to
use it standalone).

**Runtime note:** the script-backed skills (`uxd-prototype-create` and
`uxd-prototype-evaluate`) run Python helpers via the `${CLAUDE_SKILL_DIR}`
environment variable, which only Claude Code sets. Under Cursor or Gemini it is
unset, so `/prototype` and `/evaluate` resolve the scripts from the deterministic
install path (`${HOME}/.uxd-ai-skills/plugins/uxd-workshop/skills/<skill>`) and
substitute it inline. If **neither** the variable nor that path resolves to a
real `scripts/` directory (or a helper is missing), the phase stops and reports
the error rather than silently downgrading a Standard/Full evaluation to Quick.
This `${CLAUDE_SKILL_DIR}` workaround is the one runtime-specific wrinkle, and it
would be removed by an upstream change to how the skills resolve their scripts.
The remaining skills use no runtime-specific mechanisms.

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
