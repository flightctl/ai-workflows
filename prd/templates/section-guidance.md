# PRD Section Guidance

Instructions for the AI on how to fill each section of the PRD template.
This file is read during the `/draft` phase. It is not included in the final output.

## General Rules

- Write in third person, present tense.
- Be specific. Vague requirements produce vague implementations.
- Every claim should be traceable to the source requirements or clarification answers. Use standardized source markers for traceability:
  - `[Jira: EDM-2324]` — from the Jira issue description or acceptance criteria
  - `[Jira: EDM-2324, comment by @user]` — from a specific Jira comment
  - `[Clarify: R1.Q3]` — from clarification round 1, question 3 (matches `R1.Q3` headings in `02-clarifications.md`)
  - `[User]` — from direct user instruction during the workflow
  - Place markers at the end of the requirement or statement they support.
- Do not invent features, constraints, or details not supported by the ingested requirements or clarification responses.
- If information for a section is genuinely unavailable after clarification, write "To be determined — [what's needed]" rather than fabricating content.

## 1. Problem Statement

- Lead with the user's pain, not the solution.
- Quantify impact if the source material supports it (e.g., "affects N users," "adds M minutes per deployment").
- Explain the cost of inaction — what happens if this work is not done.
- Keep to 3-5 sentences. If it takes more, the problem isn't well enough understood.

## 2. Goals and Non-Goals

- Goals must be **measurable outcomes**, not activities. "Reduce deployment time" is an activity. "Users can deploy a single-container app without writing Compose or Quadlet YAML" is a measurable outcome.
- Limit to 3-5 goals. If there are more, the scope is too broad.
- Non-goals are just as important as goals. They prevent scope creep and set expectations. Include anything a reasonable reader might assume is in scope but isn't.

## 3. User Stories

- Identify the primary persona(s) from the requirements. Use role names from the source material, not generic labels.
- Each story should be independently valuable — not "As a user, I want the backend refactored."
- Include both happy-path and edge-case stories where the requirements support them.
- 3-7 stories is typical. More suggests the PRD should be split.

## 4. Requirements

### 4.1 Functional Requirements

- Each requirement should be **testable**. If you can't describe how to verify it, it isn't specific enough.
- Use "must" for mandatory requirements, "should" for important but negotiable, "may" for optional.
- Group related requirements under subheadings if the list exceeds 8 items.
- Trace each requirement back to the source (e.g., "From Jira acceptance criteria," "Per clarification Q3").

### 4.2 Non-Functional Requirements

- Include only constraints that are stated or clearly implied by the source material.
- Common categories: performance, scalability, security, compatibility, availability, observability.
- Be concrete: "API response time under 200ms at p95" not "the system should be fast."

## 5. Acceptance Criteria

- These define **done**. They drive the testing strategy.
- Write as checkboxes — each should be independently verifiable.
- Acceptance criteria are the bridge between requirements and implementation. If a requirement says "must support port mappings," the acceptance criterion says "A user can specify port mappings in the format host:container and the system correctly exposes the mapped ports."
- Cover the primary user stories. Edge cases belong in a test plan, not here.

## 6. Design Overview

- This section is **optional** in early PRDs. If the requirements are still being validated, it's fine to leave this as "Design to follow in a separate document."
- When included, stay at the architecture level: components, data flow, integration points.
- Do not include API schemas, database schemas, or implementation details — those belong in a design document.
- **Diagrams:** Use Mermaid diagrams when a visual clarifies architecture, data flow, or component relationships. Do not generate ASCII art or PlantUML. When including a diagram:
  - Introduce it with a sentence explaining what it shows and why it's relevant.
  - Use only `flowchart` or `sequenceDiagram` types — these render reliably on GitHub.
  - Keep diagrams simple: labeled nodes, clear edge labels, no styling directives (`style`, `classDef`, color codes).
  - The diagram must be understandable on its own (a reader should grasp the structure without reading the surrounding prose), but never drop a diagram into the document without context.
  - Only include a diagram when it adds clarity that prose alone cannot. A three-component system doesn't need a diagram; a multi-service flow with conditional paths probably does.

## 7. Alternatives Considered

- Include at least one alternative for any non-trivial design decision surfaced during requirements.
- Each alternative gets its own numbered subsection with Pros, Cons, and Rejection Reasons as sub-lists.
- Each sub-list (Pros, Cons, Rejection Reasons) can have one or more entries.
- "Do nothing" is a valid alternative — explain why it's insufficient.
- Keep descriptions concise but specific. "Simpler to implement" is not a useful pro; "Reuses existing Quadlet installation logic, no new agent code needed" is.

## 8. Dependencies

- List teams, services, APIs, or external systems that this work depends on or that depend on this work.
- Include ordering constraints: "API changes must land before agent changes."
- If there are no external dependencies, say so explicitly rather than omitting the section.

## 9. Risks and Open Questions

- Each risk or open question gets its own numbered subsection with **Owner**, **Status** (Open, Resolved, Deferred), and **Outcome** fields.
- When a question is resolved during clarification, record the outcome in the Outcome field rather than deleting the entry — this preserves the decision trail.
- Risks should describe what could go wrong and the mitigation strategy, if known.
- This section is a living part of the document — it gets updated during review.

## Appendix: Review Notes

- This appendix collects items that reviewers should pay attention to. It makes assumptions and unresolved items visible to all reviewers, not just the author.
- **Assumptions:** List every assumption flagged during drafting with `[Assumption: ...]` markers. Include the section reference so reviewers can find the context. These are judgment calls the AI made where the source material was ambiguous — reviewers should confirm or correct them.
- **Items Needing Resolution:** List open risks/questions from Section 9 that don't yet have owners or outcomes, plus any other items that need reviewer input. Cross-reference the section and item so reviewers can navigate directly.
- Populate this appendix during `/draft`. The items listed here should match those presented in the conversation output (Step 8 of draft.md) — the conversation output is ephemeral, the appendix persists into review.
