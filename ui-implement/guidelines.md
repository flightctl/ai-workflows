# UI Implement Workflow Guidelines

## Principles

- The implementation must satisfy the **story's acceptance criteria** as written. Do not reinterpret, expand, or reduce scope.
- **Tests validate contracts, not implementations.** Test through public component/hook interfaces. Every behavioral path reachable through a public interface is a distinct contract that needs its own test case. Tests should remain valid if the implementation were rewritten.
- **Unit tests are always required.** Test components via their rendered output and user interactions, and hooks via their return values and effects. Integration/e2e test stubs are written after all tasks complete, following the project's existing patterns (if any).
- Follow the **project's existing patterns.** Read neighboring components and tests before writing new code. Match naming conventions, file organization, test style, and error handling patterns.
- **Follow the project's commit format** as discovered during `/ingest` and recorded in the validation profile. Commit one logical unit of work per commit — typically one commit per plan task. Don't batch everything into a single commit, but don't create a commit per file either.
- Each completed story must leave the system in a **stable state**. All tests pass, linter is clean, no regressions.
- The implementation plan is a **living document**. Update `02-plan.md` as tasks are completed so it reflects current progress.
- **Discover, don't assume.** The project's build commands, test framework, design system, i18n library, and commit format are discovered during `/ingest` and recorded in the validation profile. Never hardcode assumptions about specific tools (Vitest, Cypress, PatternFly, react-i18next, or any other library).
- **Comments must earn their place — and describe the final state, not the journey.** Default to no comments unless the project's conventions require doc comments on exported symbols. Add a comment only when the *why* is non-obvious. Do not:
  - Restate what the function signature or component props already say
  - Reference abandoned approaches or prior states
  - Cite design-document sections or ticket IDs
  - Embed verification notes ("confirmed by inspection", "matches the design's table")
  - Document callers or consumers ("used by X", "consumed by Y")
  - Cross-reference private functions from public doc comments
  - Repeat the same explanation at every usage site of a shared mechanism

  Code comments, commit messages, PR descriptions, and test names describe what the code does now. A reader who has never seen the design document or the prior codebase must find every comment useful. Internal artifacts (implementation report, review responses, plan) may document the journey.

## UI-Specific Principles

- **Design system compliance.** Use the project's discovered design system components and tokens. Do not introduce raw HTML elements or inline styles when a design system equivalent exists. If a pattern is not covered by the design system, note it in the implementation report.
- **Internationalization.** Wrap all user-visible strings with the project's discovered i18n mechanism. If the project has no i18n, note the gap but do not introduce one without user approval.
- **Accessibility.** Every interactive element must be keyboard-navigable and have appropriate ARIA attributes. Follow the project's existing accessibility patterns. Test accessibility contracts (role, aria-label, keyboard interaction) alongside functional contracts.
- **Permission-aware rendering.** When the design specifies permission-gated UI, use the project's discovered permission/RBAC patterns. Do not hardcode permission checks.
- **State completeness.** Every data-dependent component must handle loading, error, and empty states unless the design explicitly excludes them.
- **Component composition.** Prefer composition over prop drilling. Follow the project's existing patterns for state management, context usage, and data fetching.

## Shared Content Rules

Read and follow `../_shared/content-rules.md` for generated-content rules. Those standards apply to all
artifacts and published output from this workflow.

## Hard Limits

- No fabricated implementations. Every code change must trace to a story requirement, acceptance criterion, or explicit user direction.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, pushing branches) without explicit user approval.
- No Jira modifications. This workflow is read-only with respect to Jira.
- **No scope creep.** Do not refactor adjacent components, add features beyond the story, or "improve" code you didn't need to change. If you discover something that should be fixed, note it in the implementation report — don't fix it silently.
- **No test shortcuts.** Do not write tests that test implementation details, mock internal component logic, or exist solely to increase coverage numbers. Every test must validate a behavioral contract through a public interface (rendered output, user events, hook return values).
- No committing to `main` directly. Use a feature branch.
- No force-push or destructive git operations.
- **No hardcoded tool assumptions.** Never assume a specific test runner (Vitest, Jest, Mocha), design system (PatternFly, MUI, Chakra), i18n library (react-i18next, FormatJS), or e2e framework (Cypress, Playwright). All tooling is discovered during `/ingest`.

## Safety

- Show your work before finalizing. After `/plan`, present the task breakdown for review — do not assume it's ready.
- Before `/code`, confirm the feature branch name and starting point with the user.
- Before `/publish`, confirm the PR target branch and description with the user.
- **Read before writing.** Before modifying any file, read it first. Before writing tests for a component, read existing tests in that package to match patterns.
- **Deviation transparency.** If during `/code` you encounter something unexpected (a bug in adjacent code, a missing dependency, a design assumption that doesn't hold), report it. Apply deviation rules (see `skills/code.md`) but never silently change approach.
- Flag assumptions explicitly. If the story or design doesn't specify something and you made a judgment call, note it in the implementation report.

## Quality

- Follow the project's `AGENTS.md` and `CLAUDE.md` for coding conventions, testing standards, and contribution guidelines.
- **Contract-based test coverage.** Identify all behavioral contracts of each public component/hook — every meaningful input (props, user interaction, state change) that produces distinct observable behavior. Write test cases that exercise each one. Don't test internal state or implementation details, but do ensure every behavior the public interface promises is verified through its observable effects (rendered output, fired events, returned values).
- Use code coverage tooling as a **signal, not a target.** If coverage shows an uncovered branch inside a component, ask: "Is there a behavioral contract I missed?" Write a test for the *behavior*, not the uncovered line.
- **Low coverage through public APIs is a design signal.** If new code cannot reach the project's minimum coverage threshold (discovered during `/ingest`, defaults to 90%) through tests that invoke public interfaces, the component is likely too coarse-grained — too much behavior is hidden behind a narrow API. The response is to decompose into smaller components with more testable interfaces, not to write tests that reach into internals.
- Run the project's full validation suite (lint, unit tests, type checking) before considering implementation complete.
- Self-review code before presenting. Check for: unused imports, dead code, missing error handling, inconsistent naming, violations of project conventions, missing i18n wrapping, accessibility gaps.

## Escalation

Stop and request human guidance when:

- Story acceptance criteria are ambiguous or contradictory
- The implementation approach requires architectural decisions not covered by the design document
- A story dependency is unmerged and blocks meaningful progress
- The design document's guidance contradicts the current state of the codebase
- Test infrastructure is unavailable or broken (not a code problem — an environment problem)
- A code change would affect components outside the story's scope
- Confidence in the implementation approach is low
- The ui-design document specifies components or patterns that conflict with the project's discovered design system
- The handoff document's interaction specs are incomplete or contradictory
- No unit test framework exists and the user has not approved introducing one

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's coding conventions, component patterns, and commit message format
- Use the project's build, test, and lint commands as discovered during `/ingest`
- Respect the project's CI/CD pipeline expectations
- Use the project's design system components and tokens — do not introduce alternatives
- Follow the project's i18n, routing, and state management patterns
