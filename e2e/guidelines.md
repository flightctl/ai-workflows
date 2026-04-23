# E2E Test Workflow Guidelines

## Principles

- The e2e tests must validate the **user-facing behaviors** described in the story's acceptance criteria. Each AC maps to one or more concrete test scenarios.
- **E2e tests exercise the system from the outside.** They validate observable outcomes through the project's test infrastructure, not internal component contracts. Write tests that a QE engineer would write — scenario-driven, using the project's actual tools and infrastructure.
- **Scope is e2e only.** Do not consider, plan, or write unit or integration tests. Every test this workflow produces must exercise the system end-to-end.
- **Follow the project's existing e2e test patterns.** Read the most similar existing test suite before writing new tests. Match the test infrastructure usage, lifecycle hooks, naming conventions, labels, and assertion style.
- Follow the **project's commit format** as discovered during `/ingest` and recorded in the validation profile. Commit one logical unit of work per commit — typically one commit per plan task. Don't batch everything into a single commit, but don't create a commit per file either.
- Each completed story must leave the test suite in a **stable state**. All new tests pass, no regressions in existing tests.
- The test plan is a **living document**. Update `02-plan.md` as tasks are completed so it reflects current progress.
- **Discover, don't assume.** The project's e2e test framework, test infrastructure abstractions, auxiliary services (if any), execution commands, and conventions are discovered during `/ingest` and recorded in the context document. Never hardcode language-specific or project-specific assumptions. Different projects use different test infrastructure — harness objects, fixtures, page objects, helper modules, or nothing at all. Use whatever vocabulary the project uses.
- **Shipped artifacts describe the final state, not the journey.** Code comments, commit messages, PR descriptions, and test names describe what the tests verify now — not the process of getting there. Do not reference abandoned approaches, intermediate failures introduced and fixed during the same session, or prior states that no longer exist. Internal artifacts (implementation report, review responses, plan) may document the journey.

## Hard Limits

- No fabricated tests. Every test must trace to a story acceptance criterion or explicit user direction.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, pushing branches) without explicit user approval.
- No Jira modifications. This workflow is read-only with respect to Jira.
- **No scope creep.** Do not write tests beyond the story's acceptance criteria, refactor existing test code, or "improve" test infrastructure you didn't need to change. If you discover something that should be fixed, note it in the implementation report — don't fix it silently.
- **No shallow tests.** Do not write tests that assert only that the system doesn't crash or return a non-error status. Every test must verify a specific behavioral outcome described in the acceptance criteria.
- **No duplicate coverage.** E2e tests validate user-facing workflows. Do not re-test unit-level or integration-level behavior that is already covered by the `[DEV]` story's tests. E2e tests exercise the full system from end to end — they are complementary to, not replacements for, lower-level tests.
- No committing to `main` directly. Use a feature branch.
- No force-push or destructive git operations.

## Safety

- Show your work before finalizing. After `/plan`, present the test scenario breakdown for review — do not assume it's ready.
- Before `/code`, confirm the feature branch name and starting point with the user.
- Before `/publish`, confirm the PR target branch and description with the user.
- **Read before writing.** Before writing tests for a suite, read existing tests in similar suites to match patterns. Read the test infrastructure code you plan to use (harness methods, fixtures, page objects, or helpers — whatever the project provides).
- **Deviation transparency.** If during `/code` you encounter something unexpected (a feature defect, a test infrastructure limitation, an assumption that doesn't hold), report it. Apply deviation rules (see `skills/code.md`) but never silently change approach.
- Flag assumptions explicitly. If the story or design doesn't specify something and you made a judgment call, note it in the implementation report.

## Quality

- Follow the project's `AGENTS.md` and `CLAUDE.md` for testing conventions and contribution guidelines. Also follow any test-specific documentation (e.g., `test/AGENTS.md`, `test/GUIDELINES.md`).
- **Scenario coverage.** E2e test quality is measured by scenario coverage — do the tests exercise every acceptance criterion? — and by resilience — will the tests break only when real behavior changes, not when unrelated implementation details change?
- **Anti-pattern avoidance.** Do not introduce:
  - Hardcoded sleeps or fixed delays (use polling/retry mechanisms)
  - Brittle selectors (use semantic locators, test infrastructure methods)
  - Order-dependent tests (each test must be independently runnable)
  - Shared mutable state between tests (use per-test isolation)
  - Missing cleanup (follow the project's teardown patterns)
  - Test infrastructure bypass (use the project's test abstractions, not ad-hoc API calls or direct infrastructure access)
- Run the project's e2e test suite (scoped to the new tests) before considering the work complete.
- Self-review test code before presenting. Check for: unused imports, dead code, debug artifacts, hardcoded values that should be constants, inconsistencies with the reference suite's patterns.

## Escalation

Stop and request human guidance when:

- Story acceptance criteria are ambiguous or contradictory
- The `[DEV]` story dependencies are unmerged — the feature under test may not exist yet
- The e2e test infrastructure is broken or unavailable
- The test requires an environment capability that doesn't exist (e.g., TPM, specific VM type, identity provider)
- A test scenario requires test infrastructure methods that don't exist and adding them is outside the story's scope
- The feature behaves differently than the acceptance criteria describe (potential defect in the `[DEV]` implementation)
- Confidence in the test approach is low

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Read and follow any test-specific documentation (test directory README, AGENTS.md, GUIDELINES.md)
- Adopt the project's e2e testing conventions, test infrastructure patterns, and commit message format
- Use the project's e2e test execution commands as discovered during `/ingest`
- Respect the project's CI/CD pipeline expectations
