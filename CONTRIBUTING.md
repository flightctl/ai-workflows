# Contributing

## SKILL.md Conventions

Every workflow and simple skill has a thin `SKILL.md` entry point with YAML
frontmatter:

```yaml
---
name: package-name
version: 0.1.0
description: Briefly state what the package does and when to use it.
---
```

- `name`: lowercase letters, digits, and hyphens; maximum 64 characters; must
  match the package directory basename and be unique across workflows and
  simple skills.
- `version`: semantic version (`X.Y.Z`). New packages start at `0.1.0`; see
  [Versioning](#versioning).
- `description`: concise third-person discovery text describing both the
  capability and when it applies.
- Keep the entire `SKILL.md`, including frontmatter, under 30 lines and use
  relative links for progressive disclosure.

Include only purpose, routing, essential constraints, and links needed whenever
the package runs. Put conditional or detailed procedures in the package's
supporting files.

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

Project-level phase overrides (in the consuming repo):

.workflows/
  workflow-name/
    skills/
      phase-name.md     # Overrides the built-in phase skill (see "Phase Overrides" below)
```

The installer auto-discovers top-level `*/SKILL.md` workflows and
`skills/*/SKILL.md` simple skills. No script changes are needed when adding a
workflow.

## Adding a New Workflow

1. Create a directory at the repo root (lowercase, hyphens, e.g. `code-review/`).
2. Add the required files following the structure above.
3. Run `./install.sh cursor` (or `all`) to verify it gets picked up.
4. Submit a PR.

### Workflow SKILL.md

Follow the shared [SKILL.md conventions](#skillmd-conventions). The workflow
entry point gives a short phase overview and routes to `guidelines.md` and,
when present, `skills/controller.md`. Phase implementation details belong in
the phase files, not the entry point.

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

**Exception:** Phase override paths (`.workflows/{workflow}/skills/{phase}.md`) are relative to the consuming project's repo root, not to the controller file's location. This is intentional — overrides live outside the workflow directory tree.

## Phase Overrides

Projects can override individual phase skills without forking the workflow. When a controller dispatches a phase, it checks for a project-level override before falling back to the built-in default:

1. **`.workflows/{workflow}/skills/{phase}.md`** — project-level override at the repo root
2. **`{phase}.md`** — workflow's built-in default (sibling file in `skills/`)

For example, a team that needs a custom `/sync` phase for the design workflow drops a file at `.workflows/design/skills/sync.md` in their repo. The controller picks it up automatically and announces the override to the user.

**Filename mapping.** Most workflows map `/phase` to `{phase}.md`, but some use different filenames. For example, docs-writer maps `/gather` to `gather-context.md` and `/plan` to `plan-structure.md`. Check the Phases list in the workflow's controller to find the correct filename for the override.

### Rules for Override Files

- **Start from a copy.** Copy the built-in phase file and modify it rather than writing from scratch. This avoids accidentally omitting contract scaffolding such as artifact paths, exit behavior, or the controller re-read instruction.
- **Full replacement.** An override replaces the entire phase — it is not merged with the built-in. The override file must be self-contained.
- **Same contract.** The override must read the same input artifacts and write the same output artifacts as the built-in phase. Downstream phases and the controller depend on this contract (see the Artifacts table in each controller).
- **Same exit behavior.** End the override file with the same "report findings and re-read the controller" instruction so the controller can recommend next steps.
- **No cross-references to built-in internals.** The override should not reference sibling files in the workflow's `skills/` directory — it lives in the project repo and should be self-contained.

### Version Control

Commit `.workflows/` to the consuming repo. Overrides are team-level decisions — not personal preferences — and should be reviewed and shared like any other project configuration.

### Discoverability

When a project uses overrides, document them in the project's `CLAUDE.md` or `AGENTS.md` so newcomers know which phases behave differently from the built-in defaults. The controller announces overrides at runtime, but a static list prevents surprises when reading workflow documentation.

### Example Project Layout

```
my-project/
├── .workflows/
│   ├── design/
│   │   └── skills/
│   │       └── sync.md      ← custom sync, all other phases use the built-in
│   └── bugfix/
│       └── skills/
│           └── fix.md       ← custom fix phase
├── src/
└── ...
```

## Simple Skills

### Structure

Focused, non-phased skills live under `skills/`:

```
skills/
  skill-name/
    SKILL.md
    references/          # Optional conditional detail
    templates/           # Optional generated-content templates
    scripts/             # Optional deterministic helpers
```

Keep the entry point thin and add only resources the skill actually uses. The
installer discovers `skills/*/SKILL.md` and installs each skill by its basename.
That basename must be unique across both top-level workflows and `skills/`; the
installer and CI reject collisions rather than choosing one package silently.
Consumer-specific skill configuration belongs under
`.workflows/{skill-name}/` in the consuming repository; do not place credentials
there.

### Adding a New Simple Skill

1. Create `skills/{skill-name}/` using a globally unique lowercase name.
2. Add `SKILL.md` following the shared entry-point conventions.
3. Add only the references, templates, scripts, and tests required by the skill.
4. Add the skill to `README.md` and `AGENTS.md`.
5. Run relevant script tests and linters, then verify selective install and
   uninstall with `--packages {skill-name}`.
6. Submit a PR.

### Simple Skill SKILL.md

Follow the shared [SKILL.md conventions](#skillmd-conventions). State the
focused outcome, trigger conditions, essential safety or permission boundaries,
and routing to supporting resources. Do not add workflow phases, controllers,
or transition language to a task that has no genuine phase model.

### References and Templates

Use `references/` for detailed schemas, policies, or conditional procedures.
The entry point must link every reference that an agent may need and state when
to read it. Keep each rule in one authoritative location.

Use `templates/` for generated-output structure. Document the template contract,
supported customization, and failure behavior. Treat template changes as
behavioral changes requiring a version bump after the initial version is
committed.

### Scripts and Tests

Add a script when deterministic execution materially improves correctness or
avoids repeatedly reconstructing fragile logic. Scripts are maintained code:
document their interface, fail clearly, avoid unnecessary dependencies, and
follow repository language conventions. Add unit tests for meaningful behavior
and wire new suites into CI; tests that run only locally are insufficient.

### Consumer Configuration

Consumer-owned configuration belongs at `.workflows/{skill-name}/` in the
consuming repository. Document its schema, precedence, validation, and security
boundaries. Never store credentials there. Applicable `AGENTS.md` instructions
remain authoritative according to their normal directory scope.

## Installation Internals

The installer (`install.sh`) auto-discovers workflows from `*/SKILL.md` and
simple skills from `skills/*/SKILL.md`. No script changes are needed when adding
either form.

**Claude Code integration**: The installer:
1. Appends package references to `CLAUDE.md` (or `.claude/CLAUDE.md` for project-level) beneath the `# ai-workflows` marker
2. Symlinks workflows and simple skills into the Claude skills directory (or `.claude/skills/` for project-level) for discovery
3. Symlinks each workflow's `commands/` directory into `.claude/commands/` so phases are discoverable as `/{workflow}:{command}` slash commands (e.g., `/bugfix:assess`, `/cve-fix:patch`)
4. Removes stale references (old controller.md paths) to avoid duplicates

**Cursor integration**: Cursor uses two discovery mechanisms — skills (`SKILL.md` in `.cursor/skills/*/`) and commands (`.md` files in `.cursor/commands/`). The installer uses both:

1. Symlinks each selected workflow or simple skill into `.cursor/skills/{name}/` for discovery
2. For each `commands/{phase}.md` in a workflow, generates a command file `.cursor/commands/{workflow}-{phase}.md` — a thin dispatch prompt that reads the workflow's controller and dispatches the phase

Cursor scans both project-level (`.cursor/commands/`) and user-level (`~/.cursor/commands/`) directories, so commands work at either scope. No manifest file is needed — uninstall identifies generated commands by matching `{workflow}-*.md` filenames against existing `commands/*.md` source files.

**Codex integration**: The installer symlinks each selected workflow or simple
skill into `~/.agents/skills/{name}/` for user scope or
`.agents/skills/{name}/` for project scope. Codex follows skill-directory
symlinks and invokes workflow phases through the selected workflow's controller,
for example `$bugfix assess`.

**Note on symlinks**: The skill symlinks (`.cursor/skills/{workflow}/` -> `~/.ai-workflows/{workflow}`) depend on Cursor following symlinks for top-level skill discovery. There are [reported issues](https://forum.cursor.com/t/cursor-doesnt-follow-symlinks-to-discover-skills/149693) with this in some Cursor versions. The generated command files avoid this problem by using absolute paths to `$INSTALL_DIR`, so the slash commands work independently of symlink resolution.

**Uninstall** (`uninstall.sh`) mirrors the install logic with removal. For Cursor, it removes generated command files by matching `{workflow}-{phase}.md` against the source workflow's `commands/` directory to avoid removing unrelated files. Selective uninstall (`--packages`) only removes commands belonging to the specified packages. The legacy `--workflows` option remains as a deprecated alias.

## Testing Your Changes

1. Install locally: `./install.sh cursor` (or `all`).
2. Open a Cursor project and reference the package to verify discovery.
3. For a workflow, run at least one phase and verify controller dispatch. For a
   simple skill, exercise its primary behavior and permission gates.
4. Run every changed script's tests and the same checks configured in CI.
5. Uninstall and reinstall to verify clean teardown: `./uninstall.sh && ./install.sh cursor`.

## Style

- Package content is plain markdown -- no IDE-specific syntax.
- Keep `SKILL.md` under 30 lines and use progressive disclosure for details.
- Use consistent terminology within a package. Pick one term and stick with it.
- Do not duplicate rules across entry points, guidelines, controllers, and
  references. Each file has a distinct role.

## Versioning

Every workflow and simple skill has a semantic version in its `SKILL.md` frontmatter.
Shared files in `_shared/` also carry versions in their frontmatter.
Versions enable the observability system to segment telemetry at
version boundaries and measure whether instruction rewrites improve
confusion rates. New packages start at `0.1.0` and graduate to
`1.0.0` once their public behavior and interfaces stabilize.

### When to bump

| Change type | Bump | Examples |
|---|---|---|
| Non-behavioral | None | README.md edits |
| Typo fix, wording clarification | PATCH | Fix spelling in step instructions |
| Behavioral change | MINOR | Add/change/reorder steps, modify rules, change templates |
| Breaking change | MAJOR | Remove/rename phases, commands, configuration keys, or other public interfaces |

Behavioral files: `SKILL.md` body, `guidelines.md`, `skills/*.md`,
`commands/*.md`, `templates/*`, `prompts/*`, `scripts/*`,
`_shared/**/*.md`, and root-level `.md` files read during execution
(e.g., `design/decomposition-review.md`). For simple skills, this includes
`skills/{skill-name}/SKILL.md`, `references/*`, `templates/*`, `prompts/*`,
`scripts/*`, and other files read or executed by the skill.

### Shared file cascade

When a file in `_shared/` changes, PATCH-bump every workflow or simple skill that
references it — including references in templates, prompts, scripts,
and other behavioral markdown listed above. Search by basename (e.g.,
`self-review-gate` for `_shared/recipes/self-review-gate.md`, or
`content-rules` for `_shared/content-rules.md`):

```bash
grep -rl "<basename-without-extension>" \
  */SKILL.md \
  */guidelines.md \
  */skills/*.md \
  */commands/*.md \
  */templates/*.md \
  */prompts/*.md \
  */scripts/* \
  2>/dev/null | sed 's|/.*||' | sort -u

grep -rl "<basename-without-extension>" \
  skills/*/SKILL.md \
  skills/*/references/*.md \
  skills/*/templates/* \
  skills/*/prompts/*.md \
  skills/*/scripts/* \
  2>/dev/null | sed -E 's|^(skills/[^/]+)/.*|\1|' | sort -u
```

Also check simple-skill resources and root-level workflow `.md` files read
during execution (e.g., `design/decomposition-review.md`). See
`.github/scripts/validate-versions.sh` for the full cascade check used in CI.

### Commit convention

Include the version bump in the same commit as the behavioral change.
Do not make a separate commit for the version bump.

### Git tags

Tags are created automatically when version bumps merge to main via
the `tag-versions.yaml` workflow. Tag formats:

- Workflows: `{workflow}/v{version}` (e.g., `design/v1.3.0`)
- Simple skills: `{skill}/v{version}` (e.g., `report-bug/v0.1.0`)
- Shared files: `_shared/{name}/v{version}` (e.g., `_shared/self-review-gate/v0.1.1`)

Manual fallback:

```bash
git tag design/v1.3.0
git push origin design/v1.3.0
```

## Scripts

Some packages include a `scripts/` directory for deterministic validation,
transformation, discovery, or other operations better handled by code than by
prompt. The directory is optional and follows these conventions:

- Scripts are invoked by package instructions, not by users directly unless the
  package explicitly documents a supported CLI
- Scripts must work when the package is installed via symlink
- Exit codes follow two conventions depending on the script's purpose:
  - **Report scripts** (e.g., pre-review checks): `exit 0` = informational (findings reported but workflow continues), `exit 1` = halt (workflow should stop and surface the failure). Scripts that only report findings should always exit 0.
  - **Search/query scripts** (e.g., checking for existing PRs): May define their own exit code semantics in their docstrings (e.g., 0 = match found, 1 = no match, 2 = error). The docstring is the source of truth for these scripts.
- Use Python 3 or bash — whichever fits the task

Currently, workflow scripts and `skills/report-bug/scripts/` use this pattern.

## Prompts

Packages may include a `prompts/` directory for templates given to sub-agents
that perform delegated work. The directory is optional and follows these
conventions:

- Prompt templates are self-contained — the sub-agent receives only the prompt, not the caller's context
- Templates use `{placeholder}` syntax for values the caller fills in before spawning the sub-agent
- Prompts must work when the workflow is installed via symlink (`prompts/` under the workflow root)
- Prompts instruct the sub-agent to write output to `.artifacts/`, not to return it in conversation

Currently, only `skill-reviewer/prompts/` uses this pattern.
