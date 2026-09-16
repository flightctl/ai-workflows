# UI Design Workflow Guidelines

## Principles

- The UI design document represents the **team's** agreed frontend approach, not the AI's interpretation. Always confirm before committing content.
- Trace every component, hook, and state management decision back to a UX handoff requirement, design document constraint, or user direction. Do not invent requirements.
- **Precision over verbosity.** A concise UI design document with specific component names, prop interfaces, and hook signatures gets better reviews than a long narrative. Cover everything that matters; don't pad it.
- **Follow existing patterns.** The codebase context from `/ingest` shows how the project structures components, manages state, and handles data fetching. Match those patterns unless there is an explicit reason to deviate.
- Preserve the project's terminology and naming conventions. If the codebase uses `useFleetData`, don't rename it to `useFleetInfo` in the design.
- Components are organized around **user-facing concerns**, not technical layers. "DeviceDetailPanel" is a good component; "DataFetcherWrapper" is not.
- **Persona-aware decomposition is required.** When the UX handoff identifies multiple user groups with distinct views or permissions, the component architecture must address conditional rendering, permission gates, and shared vs. persona-specific components explicitly.
- **Data annotations drive API review.** Every `Unknown` or `API` source type in the UX handoff's Data Annotations table must be resolved to a specific API endpoint and field — or flagged as a gap.
- **Accessibility is architectural.** ARIA roles, keyboard navigation, and focus management are designed alongside components, not bolted on later.
- **Tests validate behavior, not implementation.** The testing strategy describes what user-facing behaviors to verify, using the project's existing test framework and patterns.

## Shared Content Rules

Read and follow `../_shared/content-rules.md` for generated-content rules. Those standards apply to all
artifacts and published output from this workflow.

## Hard Limits

- No fabricated requirements. Every component, hook, and route must trace to a UX handoff element, design document constraint, PRD requirement, or user direction.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, posting comments) without explicit user approval.
- No Jira modifications without explicit user approval and a dry-run preview first.
- **No scope reduction.** Never silently simplify, defer to "v2", use "placeholder", or say "future enhancement" to reduce scope. If scope won't fit, propose a split — don't reduce.
- No committing to `main` directly. Use feature branches for `/publish`.
- **No inventing API endpoints.** When the backend API does not provide data the UI needs, flag it as a gap — do not design a fictional endpoint. The `/sync` phase creates `[DEV]` stories for gaps; the frontend design works with what exists or documents what it needs.

## Safety

- Show your work before finalizing. After `/plan` (UI design document) and `/review-api` (API findings), present artifacts for review — do not assume they are ready.
- Indicate confidence when making architectural recommendations. Flag sections where you made judgment calls vs. sections driven directly by the UX handoff or design document.
- Flag assumptions explicitly. If the UX handoff or design document doesn't specify something and you filled it in, mark it as an assumption.
- Before `/publish`, confirm the target repository, branch, and PR details with the user.
- Before `/sync`, always run a dry-run showing exactly what Jira issues would be created. Wait for explicit approval before creating anything.

## Quality

- Every component in the architecture must have a clear reason to exist — it maps to a UX handoff element, encapsulates reusable logic, or manages a distinct piece of state. No "just in case" abstractions.
- Hook designs must specify their return types, parameters, and side effects. A hook that says "fetches data" without naming the endpoint and return shape is too vague.
- State management decisions must justify their scope. Not everything needs global state — local component state is the default; escalate to shared state only with a stated reason.
- Route definitions must include lazy loading boundaries, route guards, and parameter types.
- Data flow mappings must resolve every UX handoff data annotation to a specific API field or flag it as a gap. No unresolved `Unknown` source types may remain after `/review-api`.
- Acceptance criteria must be **behavioral outcomes** (what the user sees and can interact with), not implementation details.

## Escalation

Stop and request human guidance when:

- The UX handoff and design document contradict each other on a UI behavior
- The API surface has significant gaps that would block implementation of core user flows
- The component architecture requires a pattern not established in the codebase (e.g., new state management library, new routing approach)
- Multiple valid architectural approaches exist and the trade-offs are not clearly resolvable from the inputs
- The scope appears too broad for a single UI design document (suggest splitting)
- Confidence in a component decomposition or state management recommendation is low

## Artifact Persistence and Isolation

- All workflow artifacts MUST be stored under `.artifacts/ui-design/{issue-key}/`
- NEVER read from another workflow's `.artifacts/` directory (`.artifacts/prd/`,
  `.artifacts/design/`, `.artifacts/ux-design/`, etc.) — those are private working
  directories, not interfaces
- Shared inputs MUST come from published locations:
  - Jira issues (read-only until `/sync`)
  - Published docs repository (PRD, design doc, UX handoff)
  - `.artifacts/config.json` (shared repo configuration)
  - Project files (AGENTS.md, CLAUDE.md, UI-ARCHITECTURE.md)
  - The actual codebase (source code, API types, route definitions)

## Shell Command Safety

When instructing the AI to interpolate values into shell commands (e.g., Jira
titles, branch names, user input):

- Always quote interpolated values with double quotes
- Never pass unvalidated free-form text (e.g., Jira issue summaries) as
  command-line flags unquoted
- Validate values match expected patterns before interpolation when possible

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Read `UI-ARCHITECTURE.md` if it exists — it contains frontend-specific patterns, restricted imports, generated files, and test conventions discovered by the `ai-ready` workflow
- Adopt the project's conventions for component structure, naming, and file organization
- Use the configured docs repository for `/publish` operations
- Use the project's Jira configuration for `/sync` operations
