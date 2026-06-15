# Sizing Workflow Guidelines

## Principles

- **Appetite over estimates.** We enforce fixed time and variable scope. Features are sized to fit available time — we don't extend the timeline.
- **Consistency via the rubric.** Every sizing assessment references `../_shared/sizing-rubric.md`. The rubric's heuristics ensure different sessions produce comparable results.
- **Sizing is advisory.** The AI produces a recommendation with rationale. Humans make the final call during cycle planning.
- **Relative calibration.** In batch mode, compare Features against each other. A Feature's size is more meaningful when evaluated alongside its peers in the same release.
- **Team breakdown is required.** Every Feature assessment includes per-team effort (DEV, QE, UX, UI, DOCS) so capacity planning accounts for team-level constraints, not just aggregate effort.

## Hard Limits

- No fabricated sizes. Every size must be justified by the rubric's heuristics applied to the Feature's actual content and codebase impact.
- No auto-advancing between phases. Always wait for the user.
- No Jira writes without explicit user approval and a dry-run preview first.
- **XXL is never committed.** If a Feature is assessed as XXL, it must be split. Do not write XXL to Jira — recommend the user split first.
- No scope reduction. If a Feature doesn't fit, flag it as XXL and recommend splitting — don't silently reduce its scope to make it fit a smaller size.
- **No personal names in generated content.** Replace references to individuals from Jira tickets or comments with role-based descriptions (e.g., "the feature owner noted…", "the team lead identified…") or drop the attribution and state the finding directly.

## Safety

- Present the full assessment before applying to Jira. The user must see and approve every size before it is written.
- Flag low-confidence assessments. If the Feature description is vague or the codebase impact is uncertain, say so explicitly and explain what additional information would improve confidence.
- Compare with existing Jira Size. If the Feature already has a Size in Jira, note whether the assessment agrees or differs, and why.

## Quality

- Reference the rubric for every assessment. Do not size from intuition alone — cite which heuristics drove the size.
- Team breakdown rationale must be specific. "DEV: M because 3 components affected and new API surface" is good. "DEV: M" alone is not.
- Use "—" (not applicable) for teams with no involvement, not XS.

## Escalation

Stop and request human guidance when:

- The Feature description is too vague to produce a meaningful size
- Conflicting signals produce ambiguous sizing (e.g., narrow scope but high risk)
- The user disagrees with the assessment and the rationale doesn't resolve the disagreement
- A batch contains Features with unclear or missing Fix Version assignments
- Codebase exploration reveals the Feature's scope is fundamentally different from what the Jira description suggests

## Working With the Project

This workflow gets deployed into different projects. Respect the target project:

- Read and follow the project's own `AGENTS.md` or `CLAUDE.md` files
- Use the project's codebase context to inform component surface and novelty assessments
- Adopt the project's terminology for components, services, and architectural concepts
