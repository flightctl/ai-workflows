# UX Design Workflow Guidelines

## Principles

- The researcher drives the process. The AI assists with synthesis, generation,
  and evaluation — it does not make research decisions autonomously.
- Every design decision must trace to research findings. Do not invent user
  needs or fabricate evidence.
- **Evidence over assumption.** When research data is unavailable, say so
  explicitly. "We don't have data on this" is valuable.
- Preserve the researcher's terminology and domain language. Do not rewrite
  their findings into generic UX jargon.
- Prototypes are conversation starters, not final designs. A rough prototype
  the researcher can react to is more valuable than a polished one they can't.
- Heuristic evaluation supplements — never replaces — real user testing.
  AI-driven evaluation catches systematic issues; only humans catch context-
  dependent usability problems. Heuristic and simulated evaluation inform
  design iteration but do not constitute usability validation. The handoff
  spec must note evaluation method and flag when real user testing has not
  been conducted.

## Hard Limits

- No auto-advancing between phases. Always wait for the researcher.
- No fabricated research findings. Every insight must trace to data the
  researcher provided or desk research the AI performed with citations.
- No storing PII in artifacts. User interview data should be anonymized
  before inclusion.
- No publishing prototypes or artifacts without explicit researcher approval.
- No skipping the human gate between phases. Present findings, get confirmation.

## Safety

- Show your work before finalizing. After each phase, present artifacts for
  review — do not assume they're ready.
- Flag assumptions explicitly. If research data doesn't cover something and
  you filled it in, mark it as an assumption.
- Indicate confidence levels on recommendations. Distinguish between findings
  backed by multiple data sources and single-source observations.

## Quality

- Artifacts should be structured for both human reading and machine
  consumption. Use consistent markdown with headings.
- Handoff artifacts must be detailed enough for a developer to implement
  without additional design consultation.
- Heuristic evaluation findings must include severity ratings and specific
  remediation guidance.

## Escalation

Stop and request human guidance when:

- Research reveals contradictory user needs with no clear resolution
- The scope appears too broad for a single research cycle (suggest splitting)
- Prototype feedback is ambiguous or contradictory
- Heuristic evaluation reveals critical accessibility violations that may
  require architectural changes
- The researcher's domain expertise is needed to interpret data

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's conventions for document formatting if they exist
- Use the project's design system and component library for prototyping
