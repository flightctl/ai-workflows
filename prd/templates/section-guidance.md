# PRD Section Guidance

Instructions for the AI on how to fill each section of the PRD template.
This file is read during the `/draft` phase. It is not included in the final output.

## General Rules

- **Favor conciseness.** These documents are read by humans. Write enough to communicate clearly and no more. If a section can be said in three sentences, do not use ten. Long PRDs don't get read.
- Write in third person, present tense.
- Be specific. Vague requirements produce vague implementations.
- Every claim should be traceable to the source requirements or clarification answers. Use standardized source markers for traceability:
  - `[Jira: EDM-2324]` — from the Jira issue description or acceptance criteria
  - `[Jira: EDM-2324, comment by @user]` — from a specific Jira comment
  - `[Clarify: R1.Q3]` — from clarification round 1, question 3 (matches `R1.Q3` headings in `02-clarifications.md`)
  - `[User]` — from direct user instruction during the workflow
  - Place markers at the end of the requirement or statement they support.
- **Consolidate markers.** When most requirements trace to the same Jira issue, tagging every statement with `[Jira: EDM-NNNN]` adds noise without aiding traceability. Instead:
  - Tag each FR/NFR with its specific source(s) only when the source is non-obvious or differs from the primary issue.
  - Rely on the metadata table's Jira link for the overall issue reference.
  - Reserve inline markers for clarification-derived changes (`[Clarify: ...]`) and direct user instructions (`[User]`).
- **Incorporate, don't narrate.** When a clarification changed the scope or corrected an assumption from the source material, write the requirement in its corrected form. Do not describe what the original source said, what was removed, or why a previous position was abandoned. The PRD states current intent; the clarification log preserves the editorial history.
- Do not invent features, constraints, or details not supported by the ingested requirements or clarification responses.
- If information for a section is genuinely unavailable after clarification, write "To be determined — [what's needed]" rather than fabricating content.
- **Formatting restraint.** Use bold sparingly for genuine emphasis — terms the reader must not miss or that distinguish this requirement from a similar one. When every noun phrase is bold, nothing stands out and the document becomes harder to scan.
- **Diagrams.** When a visual clarifies architecture, data flow, or component relationships in any section, use Mermaid diagrams. Only include a diagram when it adds clarity that prose alone cannot.
  - Use only `flowchart` or `sequenceDiagram` types (these render reliably on GitHub).
  - Keep diagrams simple: labeled nodes, clear edge labels, no styling directives (`style`, `classDef`, color codes).
  - Always introduce a diagram with a sentence explaining what it shows and why it's relevant.
  - Do not use ASCII art or PlantUML.

## 1. Problem Statement

- Lead with the user's pain, not the solution.
- Quantify impact if the source material supports it (e.g., "affects N users," "adds M minutes per deployment").
- Explain the cost of inaction — what happens if this work is not done.
- Keep to 3-5 sentences. If it takes more, the problem isn't well enough understood.

## 2. Goals and Non-Goals

### 2.1 Goals

- Goals must be **measurable outcomes**, not activities. "Reduce deployment time" is an activity. "Users can deploy a single-container app without writing Compose or Quadlet YAML" is a measurable outcome.
- Limit to 3-5 goals. If there are more, the scope is too broad.

### 2.2 Success Metrics

- This subsection is **optional**. If the source material provides no quantifiable targets and none can be reasonably derived, omit this subsection rather than filling it with "To be determined" rows.
- When included, each metric needs a target value and a baseline (the current state). If the baseline is unknown because this is a new capability, write "N/A (new feature)."
- Only include metrics supported by the source material. Do not invent numbers.
- 3-5 metrics is typical. More suggests you're measuring implementation details, not outcomes.

### 2.3 Non-Goals

- Non-goals are just as important as goals. They prevent scope creep and set expectations. Include anything a reasonable reader might assume is in scope but isn't.

## 3. Requirements

### 3.1 Functional Requirements

- **Assign a stable ID** to each requirement (FR-1, FR-2, ...). These IDs are referenced by acceptance criteria, design documents, and task breakdowns.
- Each requirement should be **testable**. If you can't describe how to verify it, it isn't specific enough.
- Use "must" for mandatory requirements, "should" for important but negotiable, "may" for optional.
- Group related requirements under subheadings if the list exceeds 8 items.
- Trace each requirement back to the source (e.g., "From Jira acceptance criteria," "Per clarification Q3").

### 3.2 Non-Functional Requirements

- **Assign a stable ID** to each requirement (NFR-1, NFR-2, ...). These IDs are referenced by design documents and task breakdowns.
- Include only constraints that are stated or clearly implied by the source material.
- Common categories: performance, scalability, security, compatibility, availability, observability.
- Be concrete: "API response time under 200ms at p95" not "the system should be fast."

## 4. Acceptance Criteria

- These define **done**. They drive the testing strategy.
- Write as checkboxes — each should be independently verifiable.
- Acceptance criteria are the bridge between requirements and implementation. If a requirement says "must support port mappings," the acceptance criterion says "A user can specify port mappings in the format host:container and the system correctly exposes the mapped ports."
- Cover the primary use cases. Edge cases belong in a test plan, not here.

## 5. Dependencies

- This section is **optional**. If the source material identifies no external dependencies, omit this section rather than writing "None."
- List teams, services, APIs, or external systems that this work depends on or that depend on this work.
- Include ordering constraints: "API changes must land before agent changes."

## 6. Risks

- Each risk gets its own numbered subsection (6.1, 6.2, ...) with **Owner** and **Mitigation** fields.
- Risks describe what could go wrong and the mitigation strategy, if known. If no mitigation is known yet, write "To be determined."
- Risks are permanent — they stay in the document even after the PRD is approved, unless the risk no longer applies.
- **Product scope only.** Process-level risks (e.g., "schedule might slip") belong in project management tools, not the PRD.
- This section is **optional**. If no product risks were identified during drafting or clarification, omit it.

## 7. Open Questions

- Each open question gets its own numbered subsection (7.1, 7.2, ...) with **Owner** (person or team who should answer) and **Impact** (which section or decision the answer affects).
- **Frame as clear, answerable questions.** Write "Should tenants be able to configure scan sources, or is this fixed at install time?" not "To be determined — how much tenants configure versus fixed at install." The reader should know exactly what they're being asked.
- Open questions are things that could not be resolved during the clarify phase and need broader stakeholder input via PR review.
- Questions resolved during clarification should **not** appear here — they are already incorporated into the PRD body via locked decisions.
- **Transient by design.** When an open question is resolved during PR review (`/prd respond`), the answer is incorporated into the appropriate section of the PRD (e.g., a scope decision becomes a non-goal, a constraint goes into NFRs) and the entry is removed from Section 7. By the time the PRD is approved, this section should be empty and removed.
- **Product scope only.** Process-level questions (e.g., "when should we update the Jira text?") belong in PR discussion, not in the PRD.
- This section is **optional**. If no open questions remain after clarification, omit it entirely.
