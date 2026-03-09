# Installing AI Workflows for Claude Code

## Option A: Plugin Marketplace

Register the marketplace and install:

```bash
/plugin marketplace add flightctl/ai-workflows
/plugin install ai-workflows
```

## Option B: Manual

### 1. Clone the repository

```bash
git clone https://github.com/flightctl/ai-workflows.git ~/.ai-workflows
```

### 2. Install the reference

**User-level** (available in all your projects):

```bash
./install.sh claude
```

This adds workflow references to `~/.claude/CLAUDE.md`.

**Project-level** (available in a specific project):

```bash
./install.sh claude --project /path/to/project
```

This adds workflow references to `<project>/.claude/CLAUDE.md`.

All workflows (bugfix, docs-writer, etc.) are referenced automatically.

## Verify

Start a new session and ask to "run the assess phase" or "gather context for JIRA-1234." The agent should read the controller and follow the workflow.

## Scopes

| Scope | Reference in | Visible to |
|-------|--------------|------------|
| User | `~/.claude/CLAUDE.md` | All your projects |
| Project | `<project>/.claude/CLAUDE.md` | Anyone who clones the project |

## Updating

```bash
cd ~/.ai-workflows && git pull
```

## Uninstalling

**User-level:**

```bash
./uninstall.sh claude
```

**Project-level:**

```bash
./uninstall.sh claude --project /path/to/project
```

Or manually remove the `# ai-workflows` block from your `CLAUDE.md`.
