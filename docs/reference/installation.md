<!-- Edited by Claude Code -->
# Installation Reference

## Install Script

```bash
./install.sh <target> [options]
```

### Targets

| Target | Description |
|--------|-------------|
| `cursor` | Install for Cursor IDE |
| `claude` | Install for Claude Code |
| `all` | Install for all supported environments |

### Options

| Option | Description |
|--------|-------------|
| `--project <path>` | Install at project level instead of user level |
| `--workflows <list>` | Comma-separated list of workflows to install |
| `--list` | Show available workflows |

### Installation Scopes

| Scope | Cursor | Claude Code |
|-------|--------|-------------|
| **User** (default) | `~/.cursor/skills/<workflow>` | `~/.claude/CLAUDE.md` |
| **Project** | `.cursor/skills/<workflow>` | `.claude/CLAUDE.md` |

### Examples

```bash
# User-level, all environments
./install.sh all

# Project-level, specific workflows
./install.sh cursor --project ~/flightctl --workflows bugfix
./install.sh claude --project ~/edge-manager --workflows docs-writer

# List available workflows
./install.sh --list
```

## Uninstall Script

```bash
./uninstall.sh [target] [options]
```

### Examples

```bash
# Remove everything (user-level)
./uninstall.sh

# Remove specific target
./uninstall.sh cursor

# Remove specific workflow
./uninstall.sh cursor --workflows bugfix

# Remove project-level installation
./uninstall.sh cursor --project /path/to/proj
```

## How It Works

The installer auto-discovers workflows by scanning for any directory at the repo root that contains a `SKILL.md`. No script changes are needed when a new workflow is added.

### Claude Code Integration

1. Appends workflow references to `CLAUDE.md` (or `.claude/CLAUDE.md` for project-level) beneath the `# ai-workflows` marker
2. Symlinks workflows into the user-level Claude skills directory (or `.claude/skills/` for project-level) for slash command discovery
3. Removes stale references to avoid duplicates

### Updating

```bash
cd ~/.ai-workflows && git pull
```

Because the install uses symlinks, running `git pull` updates every installed workflow instantly.
