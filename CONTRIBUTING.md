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

## IDE-Specific Files

IDE integration files live at the repo root, not inside individual workflows:

- `.cursor-plugin/plugin.json` -- Cursor marketplace manifest
- `.claude-plugin/plugin.json` -- Claude Code marketplace manifest
- `.cursor-plugin/INSTALL.md` -- Manual Cursor install instructions
- `.claude-plugin/INSTALL.md` -- Manual Claude Code install instructions

Update these when adding a workflow only if the install instructions need to change (they usually don't -- auto-discovery handles it).

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
