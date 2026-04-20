# Implement Workflow Guidelines

## Principles

- The implementation must satisfy the **story's acceptance criteria** as written. Do not reinterpret, expand, or reduce scope.
- **Tests validate contracts, not implementations.** Test through public interfaces. Every behavioral path reachable through a public interface is a distinct contract that needs its own test case. Tests should remain valid if the implementation were rewritten.
- **Unit tests are always required. Integration tests are required when the story touches component interactions** (API-to-service, service-to-store, agent-to-server). Unit and integration tests are complementary, not alternatives.
- Follow the **project's existing patterns.** Read neighboring code and tests before writing new code. Match naming conventions, package organization, test style, and error handling patterns.
- **Follow the project's commit format** as discovered during `/ingest` and recorded in the validation profile. Commit one logical unit of work per commit — typically one commit per plan task. Don't batch everything into a single commit, but don't create a commit per file either.
- Each completed story must leave the system in a **stable state**. All tests pass, linter is clean, no regressions.
- The implementation plan is a **living document**. Update `02-plan.md` as tasks are completed so it reflects current progress.
- **Discover, don't assume.** The project's build commands, test commands, lint commands, coverage tooling, and commit format are discovered during `/ingest` and recorded in the validation profile. Never hardcode language-specific or project-specific assumptions.
- **Shipped artifacts describe the final state, not the journey.** Code comments, commit messages, PR descriptions, and test names describe what the code does now — not the process of getting there. Do not reference abandoned approaches, intermediate bugs introduced and fixed during the same session, or prior states that no longer exist. Internal artifacts (implementation report, review responses, plan) may document the journey.

## Hard Limits

- No fabricated implementations. Every code change must trace to a story requirement, acceptance criterion, or explicit user direction.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, pushing branches) without explicit user approval.
- No Jira modifications. This workflow is read-only with respect to Jira.
- **No scope creep.** Do not refactor adjacent code, add features beyond the story, or "improve" code you didn't need to change. If you discover something that should be fixed, note it in the implementation report — don't fix it silently.
- **No test shortcuts.** Do not write tests that test implementation details, mock internal logic, or exist solely to increase coverage numbers. Every test must validate a behavioral contract through a public interface.
- No committing to `main` directly. Use a feature branch.
- No force-push or destructive git operations.

## Safety

- Show your work before finalizing. After `/plan`, present the task breakdown for review — do not assume it's ready.
- Before `/code`, confirm the feature branch name and starting point with the user.
- Before `/publish`, confirm the PR target branch and description with the user.
- **Read before writing.** Before modifying any file, read it first. Before writing tests for a package, read existing tests in that package to match patterns.
- **Deviation transparency.** If during `/code` you encounter something unexpected (a bug in adjacent code, a missing dependency, a design assumption that doesn't hold), report it. Apply deviation rules (see `skills/code.md`) but never silently change approach.
- Flag assumptions explicitly. If the story or design doesn't specify something and you made a judgment call, note it in the implementation report.

## Quality

- Follow the project's `AGENTS.md` and `CLAUDE.md` for coding conventions, testing standards, and contribution guidelines.
- **Contract-based test coverage.** Identify all behavioral contracts of each public function — every meaningful input class that produces distinct observable behavior. Write test cases that exercise each one. Don't test internal mechanics, but do ensure every behavior the public interface promises is verified through its observable effects.
- Use code coverage tooling as a **signal, not a target.** If coverage shows an uncovered branch inside a public function, ask: "Is there a behavioral contract I missed?" Write a test for the *behavior*, not the uncovered line.
- **Low coverage through public APIs is a design signal.** If new code cannot reach the project's minimum coverage threshold (discovered during `/ingest`, defaults to 90%) through tests that invoke public interfaces, the component is likely too coarse-grained — too much behavior is hidden behind a narrow API. The response is to decompose into smaller components with more testable interfaces, not to write tests that reach into internals.
- Run the project's full validation suite (lint, unit tests, integration tests) before considering implementation complete.
- Self-review code before presenting. Check for: unused imports, dead code, missing error handling, inconsistent naming, violations of project conventions.

## Escalation

Stop and request human guidance when:

- Story acceptance criteria are ambiguous or contradictory
- The implementation approach requires architectural decisions not covered by the design document
- A story dependency is unmerged and blocks meaningful progress
- The design document's guidance contradicts the current state of the codebase
- Test infrastructure is unavailable or broken (not a code problem — an environment problem)
- A code change would affect components outside the story's scope
- Confidence in the implementation approach is low

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's coding conventions, test patterns, and commit message format
- Use the project's build, test, and lint commands as discovered during `/ingest`
- Respect the project's CI/CD pipeline expectations
