# Story Context — {issue-key}

## Story Summary

- **Title:** {title}
- **Type:** {story type prefix, e.g., [UI]}
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

### UI Design Sections

{2–5 locked bullets per cited section for this story (component tree, hook interface, state shape, route, data flow, accessibility requirement). Refs like [UI Design: §4.1]. Not a paraphrase of the chapter.}

### Relevant Design Sections

{2–5 locked bullets per cited section for this story (API contract, data model, flow). Refs like [Design: §4.1]. If no general design sections apply: "No general design sections cited."}

### Handoff Context

{If handoff.md found: interaction specs, state matrix entries, component mapping items relevant to this story. Refs like [Handoff: §x.y].
 If not found: "No handoff document available."}

### API Findings

{If API findings document found: resolved endpoints, mock strategies for this story. Refs like [API: §x.y].
 If not found: "No API findings document available."}

### PRD Requirements Covered

{One clause per FR/NFR ID, not an ID-only list. From the story or slices already read.}

### Story Test Plan

{If written: "Story-scoped test plan written to `.artifacts/ui-implement/{issue-key}/testplan.md` with {N} test cases. TC IDs: {list}."

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
| {path} | {one line: pattern-only / shared hook / leftover grep hit} |

{If none: "None."}

### Relevant Types and Interfaces

{TypeScript signatures only, not implementations.}

### Relevant APIs

{Endpoints, hooks, or specs this story extends or calls.}

## Repository Topology

- **Origin:** {owner}/{repo from `git remote get-url origin`}
- **Type:** Fork | Direct {from `isFork` on that origin repo, not a substituted upstream}
- **Upstream:** {upstream-owner}/{upstream-repo} (fork only, omit if direct)

## UI Toolchain

### Test Infrastructure

- **Unit test framework:** {discovered framework (e.g., "vitest", "jest") or "None — see recommendation below"}
- **Testing library:** {discovered testing library (e.g., "@testing-library/react") or "None"}
- **Test run command:** {discovered command or "N/A"}
- **Test file pattern:** {discovered pattern (e.g., "*.test.tsx", "*.spec.tsx") or "N/A"}
- **Test utilities:** {project-specific test helpers, render wrappers, mocks}

{If no unit test framework found:}
#### Recommendation: Introduce Unit Testing
- **Recommended framework:** {framework based on build tooling}
- **Rationale:** {why this framework fits the project}
- **Required packages:** {list of npm packages}
- **Configuration:** {brief config description}

### Design System

- **Package:** {discovered package (e.g., "@patternfly/react-core") or "None — raw HTML/CSS"}
- **Import pattern:** {how components are imported}
- **Token usage:** {CSS variables, theme tokens, or "N/A"}

### Internationalization

- **Library:** {discovered library or "None — no i18n in project"}
- **Wrapping convention:** {e.g., "t('key')", "<Trans>", or "N/A"}
- **Key structure:** {key naming convention or "N/A"}
- **Translation files:** {path to translation files or "N/A"}

### State Management

- **Approach:** {discovered approach (e.g., "React Query for server state, React context for client state")}
- **Data fetching:** {pattern description}

### Routing

- **Library:** {discovered library or "N/A"}
- **Pattern:** {route organization pattern}

### Permission/RBAC

- **Mechanism:** {discovered pattern or "None — no permission checks in UI"}
- **Usage pattern:** {how permission checks are applied}

### E2E Framework

- **Framework:** {discovered framework or "None — no e2e tests in project"}
- **Test location:** {path or "N/A"}
- **Run command:** {command or "N/A"}

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

- **Component props contract:** {expected props shape / render behavior, or N/A}
- **Story boundary:** {vs dependency or successor, or N/A}
- **Spec vs AC:** {conflict: record both; or N/A}
- **Missing design system component:** {needed but not available, or N/A}
- **Placement:** {existing module vs new, or N/A}
- **Permission gate:** {RBAC check not in current code, or N/A}
- **Loading/error/empty states:** {not specified in design, or N/A}
- **i18n keys:** {naming convention unclear, or N/A}
