# Contributing

## Workflow Structure

Every workflow is a directory at the repo root containing:

```
workflow-name/
  SKILL.md              # Required -- YAML frontmatter (name, description) + entry point
  guidelines.md         # Behavioral rules: principles, hard limits, safety, quality, escalation
  README.md             # Human-readable documentation
  skills/
    controller.md       # Optional -- phase dispatch, transitions, next-step recommendations
    phase-name.md       # One file per phase
  commands/
    phase-name.md       # Thin wrappers that invoke the controller or SKILL.md for a specific phase
```

The installer auto-discovers any directory with a `SKILL.md`. No script changes are needed when adding a workflow.

## Adding a New Workflow

1. Create a directory at the repo root (lowercase, hyphens, e.g. `code-review/`).
2. Add the required files following the structure above.
3. Run `./install.sh cursor` (or `all`) to verify it gets picked up.
4. Submit a PR.

### SKILL.md

The `SKILL.md` is the entry point. Keep it thin -- phase overview and a reference to `guidelines.md`. Cursor uses the YAML frontmatter for skill discovery.

```yaml
---
name: workflow-name
description: Brief description. Include trigger terms so the agent knows when to use it.
---
```

- `name`: lowercase, hyphens only, max 64 chars.
- `description`: what the workflow does and when to use it. Write in third person.

### guidelines.md

Contains principles, hard limits, safety, quality standards, escalation criteria, and project-respect rules. This file is not auto-discovered by Cursor (unlike `AGENTS.md`), so it only loads when the workflow explicitly references it.

### skills/controller.md (optional)

Some workflows use a controller to manage phase execution and transitions. This is an optional pattern -- simpler workflows can route directly from `SKILL.md` without a controller. When present, it should:

- List all phases with references to sibling skill files (e.g. `assess.md`, not `skills/assess.md`).
- Define how to execute a phase (announce, read, execute, report, wait).
- Provide next-step recommendations after each phase.
- Never auto-advance -- always wait for the user.

### skills/phase-name.md

Each phase skill contains the detailed steps for that phase. At the end, it should instruct the agent to report findings and re-read the controller for next-step guidance.

### commands/phase-name.md

Each command is a thin wrapper:

```markdown
# /phase-name

Read `../skills/controller.md` and follow it.

Dispatch the **phase-name** phase. Context:

$ARGUMENTS
```

The path `../skills/controller.md` is relative to the command file's location inside `commands/`. If the workflow has no controller, commands can reference `../SKILL.md` or the phase skill directly.

## Path Conventions

All internal file references must be **relative to the file's own location**:

- `commands/*.md` reference the controller as `../skills/controller.md` (or `../SKILL.md` if no controller)
- `skills/controller.md` (when present) references sibling skills as `assess.md`, `fix.md`, etc.
- `SKILL.md` references `guidelines.md` and optionally `skills/controller.md` (both in the same directory)

This ensures symlinks resolve paths correctly regardless of where the workflow is installed.

## Installation Internals

The installer (`install.sh`) auto-discovers workflows by scanning for `*/SKILL.md` at the repo root. No script changes are needed when adding a workflow.

**Claude Code integration**: The installer:
1. Appends workflow references to `CLAUDE.md` (or `.claude/CLAUDE.md` for project-level) beneath the `# ai-workflows` marker
2. Symlinks workflows into `~/.claude/skills/` (or `.claude/skills/` for project-level) for slash command discovery
3. Removes stale references (old controller.md paths) to avoid duplicates

**Uninstall** (`uninstall.sh`) mirrors the install logic with removal.

## Testing Your Changes

1. Install locally: `./install.sh cursor` (or `all`).
2. Open a Cursor project and reference `@your-workflow` to verify Cursor discovers it.
3. Run through at least one phase to confirm the controller dispatches correctly.
4. Uninstall and reinstall to verify clean teardown: `./uninstall.sh && ./install.sh cursor`.

## Style

- Workflow content is plain markdown -- no IDE-specific syntax.
- Keep `SKILL.md` under 30 lines. Use progressive disclosure (`guidelines.md`, `README.md`) for details.
- Use consistent terminology within a workflow. Pick one term and stick with it.
- Don't duplicate content between `SKILL.md`, `guidelines.md`, and `controller.md` (when present). Each file has a distinct role.

## Scripts

Some workflows include a `scripts/` directory for scripts that offload deterministic work from the LLM — validation, data transformation, file discovery, or any operation better handled by code than by prompt. The `scripts/` directory is optional and follows these conventions:

- Scripts are invoked by the workflow's skill files, not by users directly
- Scripts must work when the workflow is installed via symlink (`scripts/` under the workflow root)
- Exit codes: `exit 0` = informational (findings reported but workflow continues), `exit 1` = halt (workflow should stop and surface the failure). Scripts that only report findings (like pre-review checks) should always exit 0.
- Use Python 3 or bash — whichever fits the task

Currently, only `skill-reviewer/scripts/` uses this pattern.

## Prompts

Some workflows include a `prompts/` directory for prompt templates given to sub-agents that perform delegated work — structured reading, analysis, or exploration that benefits from a fresh context window. The `prompts/` directory is optional and follows these conventions:

- Prompt templates are self-contained — the sub-agent receives only the prompt, not the caller's context
- Templates use `{placeholder}` syntax for values the caller fills in before spawning the sub-agent
- Prompts must work when the workflow is installed via symlink (`prompts/` under the workflow root)
- Prompts instruct the sub-agent to write output to `.artifacts/`, not to return it in conversation

Currently, only `skill-reviewer/prompts/` uses this pattern.
