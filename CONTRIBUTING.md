# Contributing

## Workflow Structure

Every workflow is a directory at the repo root containing:

```
workflow-name/
  SKILL.md              # Required -- YAML frontmatter (name, version, description) + entry point
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
version: 0.1.0
description: Brief description. Include trigger terms so the agent knows when to use it.
---
```

- `name`: lowercase, hyphens only, max 64 chars.
- `version`: semantic version (X.Y.Z). New workflows start at `0.1.0`. See [Versioning](#versioning).
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
2. Symlinks workflows into the Claude skills directory (or `.claude/skills/` for project-level) for slash command discovery
3. Symlinks each workflow's `commands/` directory into `.claude/commands/` so phases are discoverable as `/{workflow}:{command}` slash commands (e.g., `/bugfix:assess`, `/cve-fix:patch`)
4. Removes stale references (old controller.md paths) to avoid duplicates

**Cursor integration**: Cursor uses two discovery mechanisms — skills (`SKILL.md` in `.cursor/skills/*/`) and commands (`.md` files in `.cursor/commands/`). The installer uses both:

1. Symlinks each workflow directory into `.cursor/skills/{workflow}/` for top-level skill discovery
2. For each `commands/{phase}.md` in a workflow, generates a command file `.cursor/commands/{workflow}-{phase}.md` — a thin dispatch prompt that reads the workflow's controller and dispatches the phase

Cursor scans both project-level (`.cursor/commands/`) and user-level (`~/.cursor/commands/`) directories, so commands work at either scope. No manifest file is needed — uninstall identifies generated commands by matching `{workflow}-*.md` filenames against existing `commands/*.md` source files.

**Note on symlinks**: The skill symlinks (`.cursor/skills/{workflow}/` -> `~/.ai-workflows/{workflow}`) depend on Cursor following symlinks for top-level skill discovery. There are [reported issues](https://forum.cursor.com/t/cursor-doesnt-follow-symlinks-to-discover-skills/149693) with this in some Cursor versions. The generated command files avoid this problem by using absolute paths to `$INSTALL_DIR`, so the slash commands work independently of symlink resolution.

**Uninstall** (`uninstall.sh`) mirrors the install logic with removal. For Cursor, it removes generated command files by matching `{workflow}-{phase}.md` against the source workflow's `commands/` directory to avoid removing unrelated files. Selective uninstall (`--workflows`) only removes commands belonging to the specified workflows.

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

## Versioning

Every workflow has a semantic version in its `SKILL.md` frontmatter.
Shared files in `_shared/` also carry versions in their frontmatter.
See `versioning.md` for the full rationale and scheme.

### When to bump

| Change type | Bump | Examples |
|---|---|---|
| Non-behavioral | None | README.md edits |
| Typo fix, wording clarification | PATCH | Fix spelling in step instructions |
| Behavioral change | MINOR | Add/change/reorder steps, modify rules, change templates |
| Breaking change | MAJOR | Remove/rename phases or commands |

Behavioral files: `SKILL.md` body, `guidelines.md`, `skills/*.md`,
`commands/*.md`, `templates/*`, `prompts/*`, `scripts/*`,
`_shared/**/*.md`, and root-level `.md` files read during execution
(e.g., `design/decomposition-review.md`).

### Shared file cascade

When a file in `_shared/` changes, PATCH-bump every workflow that
references it. Search by basename (e.g., `self-review-gate` for
`_shared/recipes/self-review-gate.md`):

```bash
grep -rl "<basename-without-extension>" */skills/*.md */commands/*.md \
  */guidelines.md | sed 's|/.*||' | sort -u
```

### Commit convention

Include the version bump in the same commit as the behavioral change.
Do not make a separate commit for the version bump.

### Git tags

Tags are created automatically when version bumps merge to main via
the `tag-versions.yaml` workflow. Tag formats:

- Workflows: `{workflow}/v{version}` (e.g., `design/v1.3.0`)
- Shared files: `_shared/{name}/v{version}` (e.g., `_shared/self-review-gate/v0.1.1`)

Manual fallback:

```bash
git tag design/v1.3.0
git push origin design/v1.3.0
```

## Scripts

Some workflows include a `scripts/` directory for scripts that offload deterministic work from the LLM — validation, data transformation, file discovery, or any operation better handled by code than by prompt. The `scripts/` directory is optional and follows these conventions:

- Scripts are invoked by the workflow's skill files, not by users directly
- Scripts must work when the workflow is installed via symlink (`scripts/` under the workflow root)
- Exit codes follow two conventions depending on the script's purpose:
  - **Report scripts** (e.g., pre-review checks): `exit 0` = informational (findings reported but workflow continues), `exit 1` = halt (workflow should stop and surface the failure). Scripts that only report findings should always exit 0.
  - **Search/query scripts** (e.g., checking for existing PRs): May define their own exit code semantics in their docstrings (e.g., 0 = match found, 1 = no match, 2 = error). The docstring is the source of truth for these scripts.
- Use Python 3 or bash — whichever fits the task

Currently, `skill-reviewer/scripts/` and `cve-fix/scripts/` use this pattern.

## Prompts

Some workflows include a `prompts/` directory for prompt templates given to sub-agents that perform delegated work — structured reading, analysis, or exploration that benefits from a fresh context window. The `prompts/` directory is optional and follows these conventions:

- Prompt templates are self-contained — the sub-agent receives only the prompt, not the caller's context
- Templates use `{placeholder}` syntax for values the caller fills in before spawning the sub-agent
- Prompts must work when the workflow is installed via symlink (`prompts/` under the workflow root)
- Prompts instruct the sub-agent to write output to `.artifacts/`, not to return it in conversation

Currently, only `skill-reviewer/prompts/` uses this pattern.
