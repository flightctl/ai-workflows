# Design Document — Section Guidance

Instructions for the AI on how to fill each section of the design document template.
This file is read during the `/draft` phase. It is not included in the final output.

## General Rules

These apply across all sections:

- **Favor conciseness.** Long design documents don't get read. Every sentence should earn its place.
- Write in third person, present tense.
- **Be specific.** No vague language: "efficient data structure" → name the structure. "Appropriate caching" → specify the cache strategy and invalidation approach. "Standard error handling" → define the error taxonomy.
- Every design decision must be traceable to source material. Use source markers at the end of statements: `[PRD: §4.1]`, `[PRD: FR-3]`, `[PRD: NFR-2]`, `[Locked: D{N}]`, `[User]`, `[Assumption]`, `[Codebase: path/to/file]`.
- **Consolidate markers.** When most design decisions trace to the same PRD, tagging every statement with `[PRD: §X.Y]` adds noise without aiding traceability. Instead:
  - Tag each decision with its specific source(s) only when the source is non-obvious or differs from the primary PRD.
  - Rely on the metadata table's Jira and PRD links for the overall reference.
  - Reserve inline markers for clarification-derived changes (`[Locked: D{N}]`), direct user instructions (`[User]`), codebase-derived decisions (`[Codebase: ...]`), and assumptions (`[Assumption]`).
- **Incorporate, don't narrate.** When a clarification or PRD revision changed the scope or corrected an assumption, write the design decision in its final form. Do not describe what the original PRD said, what was removed, or why a previous position was abandoned. The clarification log preserves the editorial history; the design document states the current position as if it was always the intent.
- Do NOT invent requirements. If the PRD doesn't specify something, either mark it as an assumption or flag it as an open question.
- If information is unavailable, write "To be determined — {what's needed}".
- **No scope reduction.** Never use "simplified version", "v2", "placeholder", or "future enhancement" to silently reduce scope. If something won't fit, say so explicitly and propose a split.
- **Formatting restraint.** Use bold sparingly for genuine emphasis — terms the reader must not miss or that distinguish this design element from a similar one. When every noun phrase is bold, nothing stands out and the document becomes harder to scan.
- **Diagrams:** Use Mermaid diagrams when they add clarity. Any Mermaid diagram type is allowed — choose the one that best communicates the concept (e.g., `sequenceDiagram` for interactions, `flowchart` for control flow, `classDiagram` for data models, `erDiagram` for schema relationships, `stateDiagram-v2` for state machines). Every diagram **must** be accompanied by narrative explaining what it shows and what the reader should take away. A diagram without explanation is worse than no diagram — it forces the reader to reverse-engineer your intent.
  - Keep diagrams simple: labeled nodes, clear edge labels, no styling directives (`style`, `classDef`, color codes).
  - Do not use ASCII art or PlantUML.

## Per-Section Guidance

### Metadata Header

- **Author(s):** The feature owner.
- **Status:** One of Draft, In Review, Final.
- **Jira:** Link to the Feature issue.
- **Date:** Date of last significant update.

### 1. Overview

1–2 paragraphs. What this design achieves and the technical approach. Link to the PRD. A reader should understand the scope of this document after reading only this section.

### 2. Goals and Non-Goals

- **Goals** are design-scoped — they constrain the implementation approach, not the product outcome. "Reuse the existing Quadlet management logic" is a design goal. "Users can deploy containers" is a product goal (belongs in the PRD).
- **Non-Goals** prevent scope creep at the implementation level. "Support for multi-container applications via this specification" is a design non-goal.
- 3–5 goals, 2–4 non-goals. Each one sentence.

### 3. Motivation / Background

Restate the problem in implementation terms for technical reviewers. Explain the current system's limitations and why this approach is proposed. Keep to 2–4 paragraphs. Do not duplicate the PRD — bridge from it.

### 4. Design

This is the core section. All subsections (4.1–4.8) are required. If a subsection has no impact, state so explicitly with brief justification — do not omit it.

#### 4.1 Architecture

- Lead with a high-level description of the approach.
- Identify affected components and their responsibilities.
- Describe data flow from user action to system response.
- Use a Mermaid diagram when the flow involves 3+ components or has non-obvious ordering. Explain the diagram.
- Keep component descriptions focused on what changes, not a full system overview.

#### 4.2 Data Model / Schema Changes

- Show new or modified models/schemas with enough detail for a reviewer to assess correctness (field names, types, constraints, relationships).
- For projects using ORMs: show the model-level representation, not raw SQL.
- For projects using OpenAPI: show the schema definition.
- Note migration requirements (additive vs. breaking, data backfill needs).
- If no changes: "No schema changes required."

#### 4.3 API Changes

- Show new or modified endpoints with request/response shapes.
- Specify validation rules for new fields.
- Include a concrete example (request payload → response) when it aids understanding, especially for non-obvious mappings.
- Note whether changes are additive (non-breaking) or breaking.
- If no changes: "No API changes required."

#### 4.4 Scalability and Performance

- Estimate impact on CPU, memory, database load, and storage.
- State assumptions about expected scale.
- If impact is minimal, say so with brief justification (e.g., "Processing occurs only during application install/update and is lightweight for single containers").
- Do not over-engineer this section for features with obviously bounded impact.

#### 4.5 Security Considerations

- Cover input validation, authentication/authorization changes, and data exposure risks.
- If the feature inherits the existing security model without changes, state that and explain why it's sufficient.
- Do not invent security concerns that don't apply — reviewers will waste time evaluating irrelevant risks.

#### 4.6 Failure Handling and Recovery

- Enumerate concrete failure modes (not generic categories).
- For each: what happens, how the system recovers, what the user sees.
- Cover both API-side and agent-side failures where applicable.
- Note retry behavior and idempotency guarantees.

#### 4.7 RBAC / Tenancy

- Describe any new roles, permissions, or tenancy boundaries.
- Note visibility constraints and edge cases.
- If no changes: "No RBAC or tenancy changes required." with brief justification.

#### 4.8 Extensibility / Future-Proofing

- Explain how the design accommodates likely future enhancements.
- Do not over-design for hypothetical requirements. Focus on decisions that would be expensive to change later.
- If the feature is straightforward: one paragraph stating that and why.

### 5. Alternatives Considered

- At least one alternative for each non-trivial design decision.
- Include "Do nothing" if applicable.
- For each: brief description, specific pros, specific cons, rejection reason.
- Be honest about trade-offs — don't make the chosen approach look artificially superior.

### 6. Observability and Monitoring

- List new metrics, events, alerts, tracing spans, or structured log events.
- If none: "No new observability changes. Existing monitoring mechanisms apply."

### 7. Impact and Compatibility

- State whether changes are backward-compatible.
- Note migration requirements (schema, data, configuration).
- Note version compatibility constraints between components.
- If purely additive: state that clearly.

### 8. Open Questions

- Number each question.
- Track outcomes alongside original questions — do not delete resolved questions.
- Format: question text, then "Outcome:" with resolution or "Open".
- **Design scope only.** This section contains technical design questions and risks. Process-level actions (e.g., "update Jira ticket text," "schedule a meeting to discuss") belong in the PR description or review discussion, not in the design document.
- Open questions with significant design impact should be resolved before the document moves to "Final" status.

## Appendix: Review Notes

- This appendix collects items that reviewers should pay attention to. It makes assumptions and unresolved items visible to all reviewers, not just the author.
- **Assumptions:** List every assumption flagged during drafting with `[Assumption: ...]` markers. Include the section reference so reviewers can find the context. These are judgment calls the AI made where the source material (PRD, codebase) was ambiguous — reviewers should confirm or correct them.
- **Items Needing Resolution:** List open questions from Section 8 that don't yet have outcomes, plus any areas where confidence is lower (e.g., scalability estimates, security analysis). Cross-reference the section so reviewers can navigate directly.
- Populate this appendix during `/draft`. The items listed here should match those presented in the conversation output (the "Present to User" step of draft.md) — the conversation output is ephemeral, the appendix persists into review.
