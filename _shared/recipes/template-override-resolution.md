---
name: template-override-resolution
version: 0.1.0
---
# Recipe: Template Override Resolution

Resolves the document template and its section guidance for a workflow,
checking for a project-level override before falling back to the workflow's
built-in default. Every phase that reads, writes, or restructures the
document — not just the phase that first drafts it — must run this
resolution, since a project's override can be introduced or changed at any
time and is never cached across phases or sessions.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | Workflow name (`prd` or `design`) |
| TEMPLATE_FILE | Yes | Built-in template filename (e.g. `prd.md`, `design.md`) |
| SECTION_GUIDANCE_FILE | No | Section guidance filename. Defaults to `section-guidance.md`. |

## Procedure

Check for a project-level override before falling back to the workflow
default. Use the first match found for the template:

1. **Project `CLAUDE.md` / `AGENTS.md`** — if the project's AI config
   specifies a `{WORKFLOW}` template path (e.g. a line like "PRD template:
   `docs/templates/prd-template.md`"), use it.
2. **`.{WORKFLOW}/templates/{TEMPLATE_FILE}`** — conventional project-level
   override at the repo root.
3. **`../templates/{TEMPLATE_FILE}`** — workflow's built-in default (sibling
   file in `templates/`, relative to the calling skill file).

For section guidance, use the first match found from steps 2–3 only — no
project currently declares a section-guidance path in `CLAUDE.md`/`AGENTS.md`,
so step 1 does not apply:

1. **`.{WORKFLOW}/templates/{SECTION_GUIDANCE_FILE}`** — conventional
   project-level override at the repo root, alongside the template override.
2. **`../templates/{SECTION_GUIDANCE_FILE}`** — workflow's built-in default.

If a project-level override exists but is empty or appears malformed, warn
the user and fall back to the built-in default for that file.

If using a project override for either file, announce it: *"Using project
override for {template|section guidance}."*

## Using the Resolved Files

The resolved section guidance is the authoritative source for section names,
required vs. optional sections, and any project-specific requirement/tracking
scheme (e.g., whether requirements use numbered IDs like `FR-N`/`NFR-N`, and
whether the template has a distinct open-questions section or tracks open
items elsewhere). Do not assume the built-in template's structure or
vocabulary applies — a project override may omit sections the built-in
template has, rename them, or track information differently. When a skill's
own instructions or examples reference specific section names, treat those as
illustrations of the built-in template only; substitute the resolved
template's actual names and structure.

If a project-level template adds sections not covered by the section
guidance, apply best-effort judgment using the section heading and any
placeholder text as cues. For precise control over custom sections, the
project should also provide matching section guidance.
