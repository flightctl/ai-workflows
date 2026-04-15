# KCS Article Workflow

Systematic KCS Solution article creation through these phases:

1. **Gather** (`/gather`) — Collect bug details from Jira and user-provided context
2. **Draft** (`/draft`) — Write a KCS Solution article using the template and section guidance
3. **Validate** (`/validate`) — Check the draft against the KCS validation checklist
4. **Handoff** (`/handoff`) — Compose a message for the support engineer responsible for the product

The workflow controller lives at `skills/controller.md`.
Phase skills are at `skills/{name}.md`.
Artifacts go in `.artifacts/kcs/{issue-key}/`.

## Principles

- Write from the customer's perspective — describe what they see, not internal implementation details.
- Every statement must trace back to the Jira ticket, user-provided context, or direct user input. Never invent symptoms, workarounds, or root causes.
- If information is missing (e.g., no reproduction steps, unclear workaround), flag it for the user — never guess.
- Keep articles focused on a single issue. One symptom, one root cause, one resolution.
- The article must be useful to a support engineer or customer who has never seen the bug before.

## Hard Limits

- No internal links in customer-facing sections (Title, Issue, Environment, Diagnostic Steps, Resolution). Jira links belong only in Root Cause or Private Notes.
- No personal pronouns ("I", "me", "we", "myself") anywhere in the article.
- No content without a source — every claim must trace to the Jira ticket, logs, or user input.
- No fabricated diagnostic steps or resolution procedures. If you do not have the exact commands or steps, ask the user.
- No auto-advancing between phases. Always wait for the user.

## Safety

- Show the draft before composing the handoff message — the user must review the article content.
- Flag assumptions explicitly. If the Jira ticket does not specify something and you inferred it, mark it.
- Keep internal information (Jira links, internal tool references) out of customer-facing sections.
- When uncertain about product versions or environment details, ask rather than guess.

## Quality

- Follow the KCS style rules defined in `templates/section-guidance.md` and validated by `templates/validation-checklist.md`.
- Use present tense throughout ("The device shows..." not "The device showed...").
- Use backticks for file paths, command names, configuration keys, and technical terms.
- Use fenced code blocks for full commands and example output.
- Use numbered steps for sequential actions, bullet points for non-sequential items.
- Write in en-US English.
- Title must be short, searchable, and describe the main symptom plus product. No brackets around product names.
- Resolution must distinguish between a permanent fix and a workaround. Label workarounds explicitly.

## Escalation

Stop and request human guidance when:

- The Jira ticket lacks sufficient detail to describe the issue or workaround after gathering context
- The workaround involves destructive operations (data loss, service disruption) that need careful review
- Multiple distinct issues are entangled and it is unclear how to scope the article
- The root cause is speculative or disputed
- The product or version affected is ambiguous

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files for conventions
- Use the project's terminology for product names, components, and tools
- Do not assume any specific project structure — the KCS article is a standalone markdown file
