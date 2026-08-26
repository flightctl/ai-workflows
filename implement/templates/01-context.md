# Story Context — {issue-key}

## Story Summary

- **Title:** {title}
- **Type:** {story type prefix, e.g., [DEV]}
- **Jira:** {issue-key}
- **Epic:** {parent epic key and title}
- **Feature:** {parent feature key, if known}

### User Story

{As a... I want... So that...}

### Acceptance Criteria

{Numbered list, preserving original wording}

### Implementation Guidance

{From the story or design document. If none: "No implementation guidance provided."}

### Testing Approach

{From the story or design document. If none: "No specific testing approach prescribed — follow project conventions."}

### Dependencies

| Story | Status | Merged | Risk |
|-------|--------|--------|------|
| {key} | {jira status} | {yes/no} | {brief risk note} |

{If no dependencies: "No story dependencies."}

## Design Context

### Relevant Design Sections

{2–5 locked bullets per cited section for this story (identity/key, where a check runs, write vs read target, failure/CAS, timeout/limit, out of scope). Refs like [Design: §4.1]. Not a paraphrase of the chapter.}

### PRD Requirements Covered

{One clause per FR/NFR ID, not an ID-only list. From the story or slices already read.}

### Story Test Plan

{If written: "Story-scoped test plan written to `.artifacts/implement/{issue-key}/testplan.md` with {N} test cases. TC IDs: {list}."

 If feature testplan exists but no matches (expected): "Feature-level testplan found but no cases match this {story-type} story (expected). No story-scoped testplan written."

 If feature testplan exists but no matches (anomalous): "Feature-level testplan found but no cases reference this {story-type} story (anomalous). No story-scoped testplan written."

 If no feature testplan: "No feature-level testplan available. No story-scoped testplan written."}

## Codebase Context

### Affected Components

#### {Component Name}
- **Location:** {path}
- **Purpose:** {what it does}
- **Current patterns:** {relevant patterns to follow}
- **What changes:** {brief note on what the story requires}
- **Existing tests:** {test file locations, framework, patterns}

### Cited, not opened

| Path | Why |
|------|-----|
| {path} | {one line: pattern-only / deploy surface / leftover grep hit} |

{If none: "None."}

### Relevant Types and Interfaces

{Signatures only, not implementations.}

### Relevant APIs

{Endpoints or specs this story extends or calls.}

## Repository Topology

- **Origin:** {owner}/{repo from `git remote get-url origin`}
- **Type:** Fork | Direct {from `isFork` on that origin repo, not a substituted upstream}
- **Upstream:** {upstream-owner}/{upstream-repo} (fork only, omit if direct)

## Validation Profile

### Commit Format
- **Pattern:** {e.g., "JIRA-KEY: Description"}
- **Discovered from:** {source file}

### Pre-PR Checks (ordered)
1. `{command}` — {purpose}

### PR Conventions
- **Title format:** {discovered format}
- **PR template:** {path or "None — use default template"}
- **Description guidance:** {from CONTRIBUTING.md or AGENTS.md}

### Coverage Tooling
- **Command:** {how to generate coverage}
- **Report location:** {where reports are written}
- **View command:** {if available}
- **Minimum new-code coverage:** {from AGENTS.md/CLAUDE.md, default 90%}

### Discovered from
{Files read to build this profile}

## Open Questions

Fill each slot with a concrete question or `N/A (reason)`:

- **Inbound contract:** {queue payload / HTTP body / CLI args / event shape, or N/A}
- **Story boundary:** {vs dependency or successor, or N/A}
- **Spec vs AC:** {conflict: record both; or N/A}
- **Missing knob:** {config/flag/timeout/default named but absent in code, or N/A}
- **Placement:** {existing package vs new, or N/A}
- **Runtime dependency:** {binary/image/service not on current deploy path, or N/A}
- **Shared-state predicate:** {CAS/lock/idempotency if mutating shared records, or N/A}
