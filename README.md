# AI Workflows

Reusable AI coding workflows a team member can install globally or per-project, in any environment: Cursor, Claude Code, and others.

## What's Included

- **Bugfix** -- Systematic bug resolution: assess, reproduce, diagnose, fix, test, review, document, pr.
  Used in the **Flight Control** projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui)).
  See [bugfix/README.md](bugfix/README.md).

- **Docs Writer** -- Systematic documentation creation: gather context, plan structure, draft content, validate, apply changes, create merge request.
  Used in the [edge-manager](https://gitlab.cee.redhat.com/red-hat-enterprise-openshift-documentation/edge-manager) downstream docs project.
  See [docs-writer/README.md](docs-writer/README.md).

- **Triage** -- Bulk Jira bug triage with AI-driven categorization and interactive HTML reports.
  See [triage/README.md](triage/README.md).

- **Skill Reviewer** -- Meta-workflow that audits AI skill directories against eight quality dimensions.
  See [skill-reviewer/README.md](skill-reviewer/README.md).

## How It Works

Each workflow is a directory with a `SKILL.md` (the mandatory entry point), optional phase skills under `skills/`, and optional command wrappers under `commands/` -- all plain markdown, no IDE-specific syntax. Some workflows also include a `skills/controller.md` for phase dispatch, but this is an optional pattern. The installer auto-discovers every directory that contains a `SKILL.md`.

```
~/.ai-workflows/  (symlink to your clone)
  bugfix/
    SKILL.md, skills/, commands/
  docs-writer/
    SKILL.md, skills/, commands/
```

`git pull` updates everything instantly through the symlink.

## Installation

Clone the repo and run the install script:

```bash
git clone https://github.com/flightctl/ai-workflows.git
cd ai-workflows
```

### Cursor

**User-level** -- available in all your projects:

```bash
./install.sh cursor
```

**Project-level** -- shared with anyone who clones the repo:

```bash
./install.sh cursor --project /path/to/project
```

### Claude Code

**User-level:**

```bash
./install.sh claude
```

**Project-level:**

```bash
./install.sh claude --project /path/to/project
```

### All Environments at Once

```bash
./install.sh all                          # user-level
./install.sh all --project /path/to/proj  # project-level
```

### Selective Installation

Each workflow is intended for a specific project or use case:

- **bugfix** -- the **Flight Control** projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui))
- **docs-writer** -- the [edge-manager](https://gitlab.cee.redhat.com/red-hat-enterprise-openshift-documentation/edge-manager) downstream docs project
- **triage** -- teams that want bulk Jira triage, categorization, and HTML reports from this repo or a clone
- **skill-reviewer** -- reviewing or standardizing Cursor/agent skills and skill packs (structure, clarity, completeness)

Use `--workflows` to install only the workflows relevant to a given project:

```bash
./install.sh cursor --project ~/flightctl --workflows bugfix
./install.sh cursor --project ~/edge-manager --workflows docs-writer
./install.sh --list                       # show available workflows
```

## Scopes

| Scope | Cursor | Claude Code |
|-------|--------|-------------|
| **User** (default) | `~/.cursor/skills/<workflow>` | `~/.claude/CLAUDE.md` |
| **Project** (`--project`) | `.cursor/skills/<workflow>` | `.claude/CLAUDE.md` |

## Usage

### Cursor

Invoke a workflow command:

- `@bugfix/commands/assess`, `@bugfix/commands/diagnose`, `@bugfix/commands/fix`, ...
- `@docs-writer/commands/gather`, `@docs-writer/commands/plan`, `@docs-writer/commands/draft`, ...

### Claude Code

Ask the agent to run a command:

> "Run the diagnose phase on this bug"
> "Gather context for JIRA-1234"

## Updating

```bash
cd ~/.ai-workflows && git pull
```

## Uninstalling

```bash
./uninstall.sh                                          # user-level everything
./uninstall.sh cursor                                   # user-level Cursor only
./uninstall.sh cursor --workflows bugfix                # remove specific workflow
./uninstall.sh cursor --project /path/to/proj           # project-level Cursor
./uninstall.sh all --project /path/to/proj              # project-level everything
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add or modify workflows.

## License

See [LICENSE](LICENSE).
