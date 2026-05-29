# Sizing Workflow

A pre-cycle Feature sizing workflow that assesses Jira Features using T-shirt sizes (XS–XXL), produces per-team effort breakdowns (DEV, QE, UX, UI, DOCS), classifies each Feature on an impact-vs-effort quadrant for prioritization, and writes results back to Jira. Supports single-Feature and batch (Fix Version) modes.

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Jira access (MCP or CLI) | Yes | Fetch Features, write Size field, add comments |
| Git | Yes | Codebase exploration |

## Phases

| Phase | Command | Purpose | Artifact(s) |
|-------|---------|---------|-------------|
| Ingest | `/ingest` | Fetch Feature(s) from Jira, explore codebase | `01-context.md` |
| Assess | `/assess` | Apply sizing rubric, produce recommendations | `02-assessment.md` |
| Apply | `/apply` | Write sizes to Jira, add team breakdown comment | — |

## Input Modes

### Single Feature

```text
/ingest EDM-2324
```

Sizes a single Feature.

### Batch by Release

```text
/ingest release:EDM:1.3.0
```

Fetches all Features in the specified project and Fix Version, sizing them together for relative calibration. Format: `release:{project}:{version}`.

## Typical Flow

```text
/ingest EDM-2324
  → fetches Feature from Jira (description, acceptance criteria, comments)
  → explores affected codebase areas
  → writes .artifacts/sizing/EDM-2324/01-context.md

/assess
  → reads sizing rubric (../_shared/sizing-rubric.md)
  → evaluates Feature against heuristics
  → produces overall size + per-team breakdown (DEV, QE, UX, UI, DOCS)
  → rates impact and classifies effort-impact quadrant
  → writes .artifacts/sizing/EDM-2324/02-assessment.md

/apply
  → previews what will be written to Jira (dry run)
  → sets Size field (customfield_10795) on the Feature
  → adds comment with team effort breakdown and rationale
```

### Batch Flow

```text
/ingest release:EDM:1.3.0
  → fetches all Features in project EDM with fixVersion = "1.3.0"
  → explores codebase for each Feature
  → writes .artifacts/sizing/1-3-0/01-context.md

/assess
  → sizes each Feature individually
  → rates impact and classifies effort-impact quadrant per Feature
  → relative calibration: compares Features against each other
  → writes .artifacts/sizing/1-3-0/02-assessment.md (summary table + per-Feature detail)

/apply
  → previews all sizes
  → user can exclude specific Features
  → writes approved sizes to Jira
```

## Artifacts

All artifacts are stored in `.artifacts/sizing/{context}/` where context is
the Feature key (single mode) or a kebab-case Fix Version slug (batch mode).

```text
.artifacts/sizing/EDM-2324/          (single mode)
  01-context.md                      (Feature data + codebase impact)
  02-assessment.md                   (sizing recommendation + team breakdown)

.artifacts/sizing/1-5/               (batch mode, Fix Version "1.5")
  01-context.md                      (all Features + codebase impact)
  02-assessment.md                   (summary table + per-Feature assessments)
```

## Size Scale

| Size | Duration | Meaning |
|------|----------|---------|
| XS | Up to 2 days | Minimal scope, well-understood change |
| S | Up to 1 week | Narrow scope, low risk |
| M | ~1–2 weeks | Moderate scope, multiple can coexist |
| L | Up to ~3 weeks | Roughly half the dev phase |
| XL | ~4–6 weeks | Most of a cycle |
| XXL | — | Must split before committing |

See `../_shared/sizing-rubric.md` for the full rubric including heuristics and
team effort guidance.

## Directory Structure

```text
sizing/
├── SKILL.md                    # Workflow entry point
├── guidelines.md               # Behavioral rules and guardrails
├── README.md                   # This file
├── skills/
│   ├── controller.md           # Phase dispatcher and transitions
│   ├── ingest.md               # Fetch Features, explore codebase
│   ├── assess.md               # Apply rubric, produce recommendations
│   └── apply.md                # Write sizes to Jira
└── commands/
    ├── ingest.md               # /ingest command
    ├── assess.md               # /assess command
    └── apply.md                # /apply command
```

## Getting Started

```bash
# Install the workflow
./install.sh claude --workflows sizing

# Or install all workflows
./install.sh all
```

Then run the sizing workflow's `ingest` command with a Feature key or Fix Version.
