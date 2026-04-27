# Design Workflow Guidelines

## Principles

- The design document represents the **team's** agreed technical approach, not the AI's interpretation. Always confirm before committing content.
- Trace every design decision back to a PRD requirement or user direction. Do not invent requirements.
- **Precision over verbosity.** A short, precise design document gets better reviews and better feedback. Cover everything that matters, but don't pad it.
- Diagrams must be **explained**. Never drop a Mermaid diagram into the document without accompanying narrative that tells the reader what to take away from it.
- Preserve the user's terminology and domain language. Do not rewrite their terms into generic architecture jargon.
- Epics are organized around **user value**, not technical layers. "User Authentication" is a good epic; "Database Setup" is not.
- Each epic must be **standalone** — it delivers complete functionality and enables future epics without requiring them.
- Every story leaves the system in a **stable state**. Code merges to main via CI/CD.
- Every `[DEV]` story includes **functionality AND testing**. Tests should validate the software's contract, not its implementation. `[DEV]` stories must include comprehensive unit tests; integration tests should be included when natural, but may be split into a separate `[DEV]` story when the integration test surface warrants it. Use the test types appropriate to what the story changes — unit tests for isolated logic, integration tests for component interactions, and e2e tests for user-facing workflows. Match the project's existing test infrastructure.
- `[QE]` stories are appropriate for **standalone e2e test automation** owned by the QE team. These are not "just tests" stories — they represent dedicated QE work (e2e automation, manual test execution, negative test coverage) that tracks separately from unit/integration tests embedded in `[DEV]` stories.
- Stories should be **right-sized** — neither too small (excessive process overhead) nor too large (hard to review accurately).
- **Research is evidence-based.** When `/research` is used, every claim must be verified via web search and cite its source. Training data is hypothesis, not fact — verify before asserting. Use the source confidence hierarchy (HIGH/MEDIUM/LOW) defined in the research skill.
- **Research is conditional.** Not every design needs a research phase. `/research` is recommended when the PRD involves external integrations, standards, unfamiliar domains, or third-party solution evaluation. Purely internal features skip directly to `/draft`.

## Hard Limits

- No fabricated requirements. Every design decision, schema change, and API addition must trace to a PRD requirement or user direction.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, posting comments) without explicit user approval.
- No Jira modifications without explicit user approval and a dry-run preview first.
- **No scope reduction.** Never silently simplify, defer to "v2", use "placeholder", or say "future enhancement" to reduce scope. If scope won't fit, propose a split — don't reduce.
- Locked decisions from PRD clarification are binding. No phase may contradict a locked decision without explicit user override.
- No committing to `main` directly. Use feature branches for `/publish`.

## Safety

- Show your work before finalizing. After `/draft` and `/decompose`, present artifacts for review — do not assume they're ready.
- Indicate confidence when making architectural recommendations. Flag sections where you made judgment calls vs. sections driven directly by requirements.
- Flag assumptions explicitly. If the PRD doesn't specify something and you filled it in, mark it as an assumption.
- Before `/publish`, confirm the target repository, branch, and PR details with the user.
- Before `/sync`, always run a dry-run showing exactly what Jira issues would be created. Wait for explicit approval before creating anything.

## Quality

- Follow the design document template (`templates/design.md`). Do not invent new sections or omit existing ones without user approval. Sections with no impact should say so explicitly (e.g., "No schema changes required") rather than being omitted.
- Follow the section guidance (`templates/section-guidance.md`) for content standards.
- Design-scoped goals are **implementation constraints**, not product outcomes. They complement — not duplicate — the PRD's goals.
- Acceptance criteria must be **behavioral outcomes** (what the system does, testable from outside), not activities or implementation specifications. Implementation details belong in Implementation Guidance.
- Open questions must track outcomes as decisions are made.

## Escalation

Stop and request human guidance when:

- Requirements contradict each other and the correct resolution is unclear
- The scope appears too broad for a single design document (suggest splitting)
- A technical or architectural decision is required that goes beyond the PRD's scope
- The user's feedback on a revision is ambiguous or contradictory
- Design changes would contradict a PRD locked decision
- Confidence in an architectural recommendation is low

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's conventions for document formatting if they exist
- Use the configured docs repository for `/publish` operations
- Use the project's Jira configuration for `/sync` operations
