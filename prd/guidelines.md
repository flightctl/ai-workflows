# PRD Workflow Guidelines

## Principles

- The PRD represents the **user's** understanding of requirements, not the AI's interpretation. Always confirm before committing content.
- Trace every statement in the PRD back to source material (Jira issue, clarification answers, or user direction). Do not invent requirements.
- Clarity over completeness. A short, precise PRD is better than a long, vague one.
- Ask targeted questions. Generic questions ("Can you tell me more?") waste the user's time. Specific questions ("The Jira ticket mentions port mappings but doesn't specify whether UDP is supported — is this TCP-only?") drive progress.
- Preserve the user's terminology and domain language. Do not rewrite their terms into generic product management jargon.

## Hard Limits

- No fabricated requirements. Every functional requirement, acceptance criterion, and constraint must be sourced from the ingested material or user responses.
- No auto-advancing between phases. Always wait for the user.
- No publishing (creating PRs, posting comments) without explicit user approval.
- No modifying Jira issues. This workflow is read-only with respect to Jira.
- No committing to `main` directly. Use feature branches for `/publish`.

## Safety

- Show your work before finalizing. After `/draft`, present the PRD for review — do not assume it's ready.
- Indicate confidence when synthesizing requirements: flag sections where the source material was ambiguous or where you made judgment calls.
- Flag assumptions explicitly. If the Jira issue doesn't specify something and you filled it in, mark it as an assumption.
- Before `/publish`, confirm the target repository, branch, and PR details with the user.

## Quality

- **AI co-authorship:** Any output document that includes an Author field must list the AI as a co-author alongside the user. Use the AI product name (e.g., "Claude", "Gemini"), not the model version ID. The user is always the primary author.
- Follow the PRD template structure (`templates/prd.md`). Do not invent new sections or omit existing ones without user approval.
- Follow the section guidance (`templates/section-guidance.md`) for content standards in each section.
- Goals must be measurable outcomes, not activities.
- Acceptance criteria must be independently verifiable.
- Requirements must be testable.
- Open questions must have owners and statuses.

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
- Use the project's GitHub repository for `/publish` operations
