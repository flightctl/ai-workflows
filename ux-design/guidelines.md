# UX Design Workflow Guidelines

## Principles

- The handoff spec represents the **team's** agreed UX approach, not the AI's
  interpretation. Always confirm before finalizing content.
- Trace every design decision back to a research finding or user direction.
  Do not invent user needs or fabricate evidence.
- **Evidence over assumption.** When research data is unavailable, say so
  explicitly. "We don't have data on this" is valuable — silence is not.
- **Precision over verbosity.** A concise, well-structured handoff gets better
  reviews. Cover everything that matters; don't pad it.
- Preserve the researcher's terminology and domain language. Do not rewrite
  their findings into generic UX jargon.
- Prototypes are conversation starters, not final designs. A rough prototype
  the researcher can react to is more valuable than a polished one they can't.
- Heuristic evaluation supplements — never replaces — real user testing.
  AI-driven evaluation catches systematic issues; only humans catch context-
  dependent usability problems. The handoff spec must note the evaluation
  method and flag when real user testing has not been conducted.
- **Research is conditional.** Not every feature needs a dedicated research
  phase. `/research` is recommended when user needs are unclear or unvalidated.
  Skip to `/prototype` if the researcher already has validated data.

## Hard Limits

- No auto-advancing between phases. Always wait for the researcher.
- No fabricated research findings. Every insight must trace to data the
  researcher provided or desk research the AI performed with citations.
- No storing PII in artifacts. User interview data must be anonymized before
  inclusion. Use role-based labels ("User P1", "Admin P2"), not names.
- No publishing artifacts without explicit researcher approval.
- No skipping the human gate between phases. Present findings, get confirmation.
- No committing to `main` directly. Use feature branches for `/publish`.
- **No personal names in generated content.** Replace references to individuals
  from Jira tickets, interview notes, or other source material with role-based
  descriptions ("the fleet admin reported…", "a participant noted…"). Author
  metadata fields are exempt — they identify the document author, not
  referenced individuals.
- **No scope reduction.** Never silently defer design decisions to "v2" or
  mark states as "future enhancement" to reduce scope. If scope won't fit
  a single research cycle, propose a split — don't quietly drop it.

## Safety

- Show your work before finalizing. After each phase, present artifacts for
  review — do not assume they are ready.
- Flag assumptions explicitly. If research data doesn't cover something and
  you filled it in, mark it clearly as an assumption.
- Indicate confidence levels on recommendations. Distinguish between findings
  backed by multiple data sources (HIGH) and single-source observations (LOW).
- Before `/publish`, confirm the target repository, branch, and PR details
  with the researcher.

## Quality

- Artifacts must be structured for both human reading and machine consumption.
  Use consistent markdown headings and table formats — downstream workflows
  (ui-design, ui-implement) parse these artifacts programmatically.
- The handoff spec must be detailed enough for a developer to implement without
  additional design consultation. If a developer would need to ask a question,
  the answer belongs in the spec.
- Heuristic evaluation findings must include severity ratings and specific
  remediation guidance — not just observations.
- Acceptance criteria must be **behavioral outcomes** (what the system does,
  testable from outside), not activities or implementation details.
- The Data Annotations and Persona-Specific Views sections of the handoff spec
  are required, not optional. If all user groups interact identically, say so
  explicitly. If no UI element has data uncertainty, say so explicitly. Do not
  omit these sections.

## Escalation

Stop and request human guidance when:

- Research reveals contradictory user needs with no clear resolution
- The scope appears too broad for a single research cycle (suggest splitting)
- Prototype feedback is ambiguous or contradictory
- Heuristic evaluation reveals critical accessibility violations that may
  require architectural changes
- The researcher's domain expertise is needed to interpret data
- Confidence in a design recommendation is low

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's conventions for document formatting if they exist
- Use the project's design system and component library for prototyping
- Use the configured docs repository for `/publish` operations
