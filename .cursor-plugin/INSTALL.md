# Installing AI Workflows for Cursor

## Option A: Plugin Marketplace

```text
/plugin-add ai-workflows
```

## Option B: Manual

### 1. Clone the repository

```bash
git clone https://github.com/flightctl/ai-workflows.git ~/.ai-workflows
```

### 2. Install the skills

**User-level** (available in all your projects):

```bash
./install.sh cursor
```

**Project-level** (available in a specific project, shared via the repo):

```bash
./install.sh cursor --project /path/to/project
```

All workflows (bugfix, docs-writer, etc.) are installed automatically.

### 3. Restart Cursor

Restart Cursor to discover the new skills.

## Verify

Start a new session and reference `@bugfix` or `@docs-writer` -- the agent should load the workflow skill.

## Scopes

| Scope | Symlink location | Visible to |
|-------|------------------|------------|
| User | `~/.cursor/skills/<workflow>` | All your projects |
| Project | `<project>/.cursor/skills/<workflow>` | Anyone who clones the project |

## Updating

```bash
cd ~/.ai-workflows && git pull
```

Changes are reflected immediately through the symlinks.

## Uninstalling

**User-level:**

```bash
./uninstall.sh cursor
```

**Project-level:**

```bash
./uninstall.sh cursor --project /path/to/project
```
