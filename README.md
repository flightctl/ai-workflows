# AI Workflows

Reusable AI coding workflows your team can install globally or per-project, in any environment: Cursor, Claude Code, and others.

## What's Included

- **Bugfix** -- Systematic bug resolution: assess, reproduce, diagnose, fix, test, review, document, pr.
  See [bugfix/README.md](bugfix/README.md).

- **Docs Writer** -- Systematic documentation creation: gather context, plan structure, draft content, validate, apply changes, create merge request.
  See [docs-writer/README.md](docs-writer/README.md).

## How It Works

Each workflow is a directory with a `SKILL.md`, a `skills/controller.md`, command wrappers, and phase skills -- all plain markdown, no IDE-specific syntax. The installer auto-discovers every directory that contains a `SKILL.md`.

```
~/.ai-workflows/  (symlink to your clone)
  bugfix/
    SKILL.md, skills/, commands/
  docs-writer/
    SKILL.md, skills/, commands/
```

`git pull` updates everything instantly through the symlink.

## Installation

### Cursor

**Plugin marketplace:**

```text
/plugin-add ai-workflows
```

**Manual (user-level)** -- available in all your projects:

```bash
git clone <repo-url> ~/.ai-workflows
./install.sh cursor
```

**Manual (project-level)** -- shared with anyone who clones the repo:

```bash
./install.sh cursor --project /path/to/project
```

See [.cursor-plugin/INSTALL.md](.cursor-plugin/INSTALL.md) for details.

### Claude Code

**Plugin marketplace:**

```bash
/plugin marketplace add flightctl/ai-workflows
/plugin install ai-workflows
```

**Manual (user-level):**

```bash
git clone <repo-url> ~/.ai-workflows
./install.sh claude
```

**Manual (project-level):**

```bash
./install.sh claude --project /path/to/project
```

See [.claude-plugin/INSTALL.md](.claude-plugin/INSTALL.md) for details.

### All Environments at Once

```bash
./install.sh all                          # user-level
./install.sh all --project /path/to/proj  # project-level
```

### Other Environments

Clone and point your tool's global instructions at the controller for the workflow you need:

- `~/.ai-workflows/bugfix/skills/controller.md`
- `~/.ai-workflows/docs-writer/skills/controller.md`

## Scopes

| Scope | Cursor | Claude Code |
|-------|--------|-------------|
| **User** (default) | `~/.cursor/skills/<workflow>` | `~/.claude/CLAUDE.md` |
| **Project** (`--project`) | `.cursor/skills/<workflow>` | `.claude/CLAUDE.md` |

## Usage

### Cursor

Reference a workflow skill or a specific command:

- `@bugfix` / `@bugfix/commands/fix`
- `@docs-writer` / `@docs-writer/commands/draft`

### Claude Code

Ask the agent to run a phase:

> "Run the diagnose phase on this bug"
> "Gather context for JIRA-1234"

### Any Environment

Tell the agent to read and follow the controller for the workflow you want.

## Adding New Workflows

Drop a new directory at the repo root with a `SKILL.md`, a `skills/controller.md`, and `commands/`. The installer auto-discovers it -- no script changes needed.

## Updating

```bash
cd ~/.ai-workflows && git pull
```

## Uninstalling

```bash
./uninstall.sh                                # user-level everything
./uninstall.sh cursor                         # user-level Cursor only
./uninstall.sh cursor --project /path/to/proj # project-level Cursor
./uninstall.sh all --project /path/to/proj    # project-level everything
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add or modify workflows.

## License

See [LICENSE](LICENSE).
