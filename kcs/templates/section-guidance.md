# KCS Section Guidance

Instructions for the AI on how to fill each section of the KCS Solution template.
This file is read during the `/draft` phase. It is not included in the final output.

## General Rules

- Write in present tense throughout ("The device shows..." not "The device showed...").
- No personal pronouns ("I", "me", "we", "myself") anywhere in the article.
- Use backticks for file paths, command names, configuration keys, and technical terms.
- Use fenced code blocks for full commands and example output.
- Use numbered steps for sequential actions, bullet points for non-sequential items.
- Write in en-US English.
- Every claim must trace to the gathered context (Jira ticket, user-provided details, or logs). Use standardized source markers for traceability:
  - `[Jira: PROJ-123]` — from the Jira issue description or comments
  - `[User]` — from direct user input during the workflow
- Do not invent symptoms, commands, or workaround steps not supported by the gathered context.
- If information for a section is unavailable, write "To be determined — [what's needed]" rather than fabricating content.

## Metadata Block

- **ISSUE_KEY:** Replace with the Jira issue key (e.g., `EDM-3340`).
- **Article Type:** Always `Solution`.
- **Article Confidence:** Start at `Not-Validated (WIP)`. The support engineer sets the final confidence level after publishing.
- **Product:** Product name and version from the Jira ticket or user input. Use the official product name, not internal shorthand.

## Title

- Short and searchable — a support engineer or customer should find this by searching for the symptom.
- Format: main symptom + product name (e.g., "Device stuck in OutOfDate with spec rollback loop after fleet OS upgrade").
- No brackets around product names.
- No article type prefix (do not start with "Solution:" or "KCS:").
- Aim for under 120 characters.

## Issue

- Describe the problem from the customer's perspective. What do they observe? What fails? What error messages appear?
- Include specific error messages or status values in fenced code blocks or backtick-quoted inline.
- If there are conditions that affect the behavior (e.g., fleet-owned vs standalone device), describe each scenario.
- Do not describe the workaround here — that belongs in Resolution.
- Keep to 1-3 short paragraphs.

## Environment

- List each affected product and version on its own line, prefixed with a bullet.
- Use official product names (e.g., "Red Hat Edge Manager 1.0", not "RHEM" or "flightctl").
- If the issue affects multiple versions, list each one.
- If the version is unknown, write the product name and note the version as "To be determined".

## Diagnostic Steps

- Numbered steps that a support engineer can follow to confirm this exact issue.
- Each step should have one action and its expected output or observation.
- Include the full command in a fenced code block, followed by a description of what to look for in the output.
- Use `<PLACEHOLDER>` style for user-specific values (e.g., `<DEVICE_NAME>`, `<FLEET_NAME>`). Use uppercase with underscores.
- If the diagnostic requires device access (SSH, console), state that prerequisite explicitly.
- Order steps from least invasive to most invasive.

## Resolution

- If this is a workaround (not a permanent fix), start with **Workaround** in bold, followed by a short description of the approach.
- Use numbered steps for the procedure.
- Each step: one action in a fenced code block, followed by a brief explanation of what it does and what to verify.
- Use `<PLACEHOLDER>` style for user-specific values, consistent with Diagnostic Steps.
- If the resolution has prerequisites (e.g., CLI access, specific permissions), state them before the first step.
- End with a verification step that confirms the issue is resolved.
- If a permanent fix exists or is tracked, mention it at the end and direct readers to the Root Cause section.

## Root Cause

- Technical explanation of why the issue occurs. This is for engineers, not end users.
- Explain the mechanism: what triggers the issue, what goes wrong internally, and why the resolution works.
- Link to the Jira ticket tracking the permanent fix (e.g., `[PROJ-123](https://issues.redhat.com/browse/PROJ-123)`).
- This section may be placed in Private Notes on the customer portal, so internal references are acceptable here.
- Keep to 1-2 paragraphs.
