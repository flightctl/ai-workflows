# AI Workflows

Reusable AI coding workflows a team member can install globally or per-project, in any environment: Cursor, Claude Code, and others.

## What's Included

- **Bugfix** -- Systematic bug resolution: assess the report, reproduce, diagnose root cause, fix, test, review, document, and submit a PR. Supports iterative PR feedback and an unattended mode.
  Used in the **Flight Control** projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui)).
  See [bugfix/README.md](bugfix/README.md).

- **Docs Writer** -- Systematic documentation creation: gather context, plan structure, draft content, validate, apply changes, create merge request.
  Used in the [edge-manager](https://gitlab.cee.redhat.com/red-hat-enterprise-openshift-documentation/edge-manager) downstream docs project.
  See [docs-writer/README.md](docs-writer/README.md).

- **Triage** -- Bulk Jira bug triage with AI-driven categorization and interactive HTML reports.
  See [triage/README.md](triage/README.md).

- **PRD** -- Requirements-to-PRD workflow: ingest requirements from Jira, clarify ambiguities through iterative Q&A, draft a Product Requirements Document, revise based on feedback, publish as a GitHub PR, and respond to reviewer comments.
  See [prd/README.md](prd/README.md).

- **Design** -- Design-and-decompose workflow: ingest a PRD, draft a technical design document, decompose into Jira-ready epics and stories, revise based on feedback, publish as a GitHub PR, respond to reviewer comments, and sync epics/stories to Jira.
  See [design/README.md](design/README.md).

- **CVE Fix** -- Automated CVE remediation: read vulnerability details from Jira, apply multi-strategy dependency fixes, validate, create pull requests, backport to release branches, and close Jira tickets. Language-agnostic.
  See [cve-fix/README.md](cve-fix/README.md).

- **AI-Ready** -- Scans a codebase and creates or updates AGENTS.md with project-specific build commands, test patterns, and coding standards.
  See [ai-ready/README.md](ai-ready/README.md).

- **KCS** -- KCS Solution article workflow: gather bug context from Jira, draft a KCS article in markdown, validate against the KCS Content Standard, and produce a handoff message for the support engineer.
  See [kcs/README.md](kcs/README.md).

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
- **prd** -- teams drafting Product Requirements Documents from Jira features
- **design** -- teams creating technical design documents and Jira-ready epic/story breakdowns from PRDs
- **cve-fix** -- teams patching CVEs and updating vulnerable dependencies from Jira vulnerability tickets
- **ai-ready** -- onboarding any project for AI agents by generating AGENTS.md
- **kcs** -- teams writing KCS Solution articles for known issues with workarounds
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

Invoke a workflow command (works in both Cursor and Claude Code):

- `/bugfix:assess`, `/bugfix:diagnose`, `/bugfix:fix`, ...
- `/docs-writer:gather`, `/docs-writer:plan`, `/docs-writer:draft`, ...

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
