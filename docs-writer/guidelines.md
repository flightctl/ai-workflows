# Docs Writer Workflow

Systematic documentation creation through these phases:

1. **Gather Context** (`/gather`) — Research the feature from Jira, GitHub, or a description
2. **Plan Structure** (`/plan`) — Determine where content belongs in the repository
3. **Draft Content** (`/draft`) — Write style-compliant AsciiDoc content
4. **Validate** (`/validate`) — Run Vale and optionally AsciiDoctor
5. **Apply Changes** (`/apply`) — Write validated content to repository files
6. **Create Merge Request** (`/mr`) — Create a GitLab merge request for the changes

The workflow controller lives at `skills/controller.md`.
It defines how to execute phases, recommend next steps, and handle transitions.
Phase skills are at `skills/{name}.md`.
Artifacts go in `.artifacts/${ticket_id}/`.

## Principles

- Write accurate documentation — never invent features, flags or endpoints.
- Rely on gathered context and code diffs as the source of truth.
- If requirements are unclear, flag for human decision — never guess.
- When something doesn't fit the plan, say so and recommend adjustments.
- Don't assume tools are missing. Check for Vale, AsciiDoctor, and container runtimes before concluding they aren't available.

## Hard Limits

- No hardcoded product names — always use AsciiDoc attributes (`{rhem}`, `{ocp}`, `{rhel}`)
- No content without a source — every statement must trace back to Jira, code diffs, or user input
- No modifying files outside the plan — only change files listed in the artifact
- No skipping the approval gate — the plan must be approved before drafting

## Safety

- Show the plan before writing content
- Indicate confidence in structural decisions
- Flag assumptions about where content belongs
- Preserve existing `include::` directives and `master.adoc` structure

## Quality

- Follow Red Hat Supplementary Style Guide and Modular Documentation Guide
- Zero tolerance for Vale violations — fix them, don't skip them
- Use existing `.adoc` files as exemplars for structure and conventions
- Verify content compiles when possible (AsciiDoctor build)

## Escalation

Stop and request human guidance when:

- The feature scope is unclear after reviewing Jira and code diffs
- Multiple valid placements exist for the content (which guide, which section)
- The plan requires restructuring existing content significantly
- A new guide directory may be needed
- Existing content conflicts with the new information

## Working With the Project

This workflow operates on a documentation repository. Respect the target project:

- Read and follow the project's own `AGENTS.md` for repository structure and conventions
- Consult `BOOKMARKS.md` for style guides and tooling references
- Use `topics/document-attributes.adoc` for product name attributes
- Adopt the project's existing AsciiDoc patterns, not your own preferences
- When in doubt about conventions, check existing `.adoc` files in the target guide
