# Code Review Workflow Guidelines

## Principles

- **Review what the developer wrote, not what you would have written.** The reviewer evaluates correctness, clarity, safety, and adherence to project conventions. It does not impose stylistic preferences that are not codified in the project's linting or contribution guidelines.
- **Findings must be actionable.** Every finding must include a concrete suggestion the developer can evaluate and apply. Vague observations ("consider improving this") are not findings.
- **Severity must be honest.** CRITICAL and HIGH are blockers that would cause bugs, security issues, or maintenance problems. MEDIUM and LOW are suggestions that improve quality but are not blocking. Inflating severity erodes trust; deflating it hides real problems.
- **Every finding deserves honest assessment.** The implementor must carefully consider every finding — including nits and LOW-severity items — and make a value judgment. If a minor suggestion genuinely improves the code (clearer naming, better readability, a small correctness improvement), recommend accepting it. If it doesn't add real value (stylistic preference, churn without improvement, subjective taste), recommend rejecting it with a concrete explanation of why. Severity does not determine whether a finding is worth implementing — value does.
- **The human decides.** The reviewer proposes; the implementor assesses; the user approves. No change is applied without the user's explicit decision.
- **Productive disagreement is valuable.** When the implementor disagrees with a finding, that disagreement must be grounded in evidence (code behavior, test coverage, design constraints). The user resolves ties.
- **Discover, don't assume.** The project's tech stack, conventions, and quality standards are discovered from the codebase, not hardcoded. Every project gets a review tailored to its own standards.
- **Scope is about relevance, not mechanics.** The review covers all uncommitted changes, but not every file in the workspace is necessarily part of the change. Determine relevance by examining each file's content and its relationship to the logical change — not by a mechanical staged/unstaged filter.
- **The review is private.** All artifacts stay in `.artifacts/` (gitignored). Review iterations are working documents, not public records.

## Hard Limits

- No auto-advancing between phases. Always wait for the user.
- No code changes without user approval. The implementor proposes changes based on accepted findings; the user confirms before implementation begins.
- No modifying files outside the scope of the reviewed changes.
- No fabricated findings. Every issue cited must reference a specific file and location in the actual diff.
- No scope creep. The reviewer reviews what changed, not what didn't.
- No mutating git operations (commit, push, branch, checkout) during `/start`. Read-only git commands (`git diff`, `git log`, `git ls-files`) are expected. Code changes happen only in `/continue`.

## Safety

- Read the project's `AGENTS.md`, `CLAUDE.md`, and contribution guidelines before reviewing. Project conventions override general preferences.
- Verify that each finding references real code. If a finding cites a file or line that doesn't exist in the diff, discard it.
- When the implementor disagrees with a finding, present both perspectives to the user with evidence. Do not silently drop findings or silently accept them.
- Before applying code changes in `/continue`, read the affected file to confirm the change is still valid (the file may have been modified between rounds).

## Quality

- Findings should cover: correctness, error handling, security, performance, naming and clarity, test coverage, and adherence to project conventions.
- The reviewer should prioritize findings by impact. A correctness bug matters more than a naming suggestion.
- The implementor's assessment should be independent, not reflexively agreeing or disagreeing with the reviewer.
- Each review round should show measurable progress: findings addressed, new issues surfaced (if any), and a clear approval or continuation signal.

## Escalation

Stop and request human guidance when:

- The changes are too large to review meaningfully in one pass (recommend splitting)
- The reviewer and implementor disagree on a CRITICAL finding
- The changes affect security-sensitive code and the reviewer is uncertain
- The project has no discoverable conventions and the reviewer cannot calibrate

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's coding conventions and quality standards as review criteria
- Use the project's linting and testing commands when verifying changes
- Do not impose conventions from other projects
