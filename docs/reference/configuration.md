<!-- Edited by Claude Code -->
# Configuration

## Workflow Configuration

Workflows are configured through their own files, not through external configuration. Each workflow's behavior is defined by:

- **SKILL.md** — Entry point with YAML frontmatter (`name`, `description`)
- **guidelines.md** — Behavioral rules, principles, hard limits
- **skills/controller.md** — Phase dispatch and transition rules (optional)

## Project-Level Overrides

Some workflows allow you to override the default templates at the project level:

### PRD Templates

The `/prd:draft` phase checks for custom templates in this order:

1. Path specified in the project's `CLAUDE.md` or `AGENTS.md`
2. `.prd/templates/prd.md` at the project root
3. Workflow's built-in template (fallback)

### Design Templates

The `/design:draft` phase checks for custom templates in this order:

1. Path specified in the project's `CLAUDE.md` or `AGENTS.md`
2. `.design/templates/design.md` at the project root
3. Workflow's built-in template (fallback)

## Artifact Storage

All workflows store their artifacts in `.artifacts/<workflow-name>/<context>/`:

```text
.artifacts/
├── bugfix/{issue}/          # Bug fix workflow artifacts
├── code-review/{branch}/    # Code review artifacts
├── cve-fix/{context}/       # CVE fix artifacts
├── design/{issue-number}/   # Design workflow artifacts
├── e2e/{jira-key}/          # E2E test artifacts
├── implement/{jira-key}/    # Implementation artifacts
├── kcs/{issue-key}/         # KCS article artifacts
├── prd/{issue-number}/      # PRD artifacts
├── skill-reviewer/{name}/   # Skill review artifacts
└── triage/{project}/        # Triage artifacts
```

Add `.artifacts/` to your project's `.gitignore` to keep these working files out of version control.

## AI Convention Files

The AI-Ready workflow generates and maintains these convention files, which are auto-loaded by their respective tools:

| File | Tool | Auto-loaded? |
|------|------|-------------|
| `AGENTS.md` | Universal | Yes (Cursor, Claude Code, Copilot, Codex, Jules, Windsurf, Junie) |
| `CLAUDE.md` | Claude Code | Yes |
| `.cursorrules` | Cursor | Yes |
| `.github/copilot-instructions.md` | GitHub Copilot | Yes |

## Environment Requirements

Every workflow requires:

- **Git** — for branch management and commit operations
- **An AI coding environment** — Cursor, Claude Code, or any compatible tool

Individual workflows may have additional requirements (e.g., Jira access, specific language toolchains). See each workflow's README for details.
