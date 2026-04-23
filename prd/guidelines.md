# PRD Workflow Guidelines

## Principles

- The PRD represents the **user's** understanding of requirements, not the AI's interpretation. Always confirm before committing content.
- Trace every statement in the PRD back to source material (Jira issue, clarification answers, or user direction). Do not invent requirements.
- Precision over verbosity. A short, precise PRD is better than a long, vague one.
- Ask targeted questions. Generic questions ("Can you tell me more?") waste the user's time. Specific questions ("The Jira ticket mentions port mappings but doesn't specify whether UDP is supported — is this TCP-only?") drive progress.
- Preserve the user's terminology and domain language. Do not rewrite their terms into generic product management jargon.
- Diagrams must be **explained**. Never drop a Mermaid diagram into the document without accompanying narrative that tells the reader what to take away from it.

## Hard Limits

- No fabricated requirements. Every functional requirement, acceptance criterion, and constraint must be sourced from the ingested material or user responses.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, posting comments) without explicit user approval.
- No modifying Jira issues. This workflow is read-only with respect to Jira.
- No committing to `main` directly. Use feature branches for `/publish`.
- **No scope reduction.** Never silently simplify, defer to "v2", use "placeholder", or say "future enhancement" to reduce scope. If scope won't fit, flag it explicitly and propose a split — don't reduce.
- Locked decisions from `/clarify` are binding. No phase may contradict a locked decision without explicit user override.

## Safety

- Show your work before finalizing. After `/draft`, present the PRD for review — do not assume it's ready.
- Indicate confidence when synthesizing requirements: flag sections where the source material was ambiguous or where you made judgment calls.
- Flag assumptions explicitly. If the Jira issue doesn't specify something and you filled it in, mark it as an assumption.
- Before `/publish`, confirm the target repository, branch, and PR details with the user.

## Quality

- Follow the PRD template structure (`templates/prd.md`). Do not invent new sections without user approval. Sections the section guidance marks as optional may be omitted when the source material provides no relevant content.
- Follow the section guidance (`templates/section-guidance.md`) for content standards in each section.
- Goals must be measurable outcomes, not activities.
- Acceptance criteria must be written as **testable assertions**, not activities.
- Requirements must be testable.
- Open questions must have owners and impact statements.

## Escalation

Stop and request human guidance when:

- Requirements contradict each other and the correct resolution is unclear
- The scope appears too broad for a single PRD (suggest splitting)
- The Jira issue lacks sufficient detail to produce meaningful requirements after clarification
- A technical or architectural decision is required that goes beyond requirements
- The user's feedback on a revision is ambiguous or contradictory

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Adopt the project's conventions for document formatting if they exist
- Use the configured docs repository for `/publish` operations
