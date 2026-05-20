<!-- Edited by Claude Code -->
# Installation

Start by cloning the repository:

```bash
git clone https://github.com/flightctl/ai-workflows.git
cd ai-workflows
```

## Cursor

**User-level** — makes workflows available in every project you open:

```bash
./install.sh cursor
```

**Project-level** — scoped to a single project and shared with anyone who clones it:

```bash
./install.sh cursor --project /path/to/project
```

## Claude Code

**User-level:**

```bash
./install.sh claude
```

**Project-level:**

```bash
./install.sh claude --project /path/to/project
```

## All Environments at Once

```bash
./install.sh all                          # user-level
./install.sh all --project /path/to/proj  # project-level
```

## Selective Installation

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
