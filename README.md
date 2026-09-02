# AI Workflows

Reusable AI coding workflows and focused skills a team member can install globally or per-project, in any environment: Cursor, Claude Code, and others.

## What's Included

### Skills

- **Report Bug** -- Drafts an evidence-based Jira Bug, supports consumer-owned
  project templates and field vocabulary with an EDM-style fallback,
  distinguishes Severity from triage-owned Priority, checks
  duplicate/regression context, supports explicitly reviewed optional
  attachments, works through Jira MCP, CLI, or REST capabilities, and creates
  the issue only after confirmation.
  See [skills/report-bug/SKILL.md](skills/report-bug/SKILL.md).

### Workflows

- **Bugfix** -- Systematic bug resolution: assess the report, reproduce, diagnose root cause, fix, test, review, document, and submit a PR. Supports iterative PR feedback and an unattended mode.
  Used in the **Flight Control** projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui)).
  See [bugfix/README.md](bugfix/README.md).

- **Docs Writer** -- Systematic documentation creation: gather context, plan structure, draft content, validate, apply changes, create merge request.
  Used in the [edge-manager](https://gitlab.cee.redhat.com/red-hat-enterprise-openshift-documentation/edge-manager) downstream docs project.
  See [docs-writer/README.md](docs-writer/README.md).

- **Triage** -- Bulk Jira bug triage with AI-driven categorization and interactive HTML reports.
  See [triage/README.md](triage/README.md).

- **PRD** -- Requirements-to-PRD workflow: ingest requirements from Jira, clarify ambiguities through iterative Q&A, draft a Product Requirements Document, revise based on feedback, publish as a GitHub PR, and respond to reviewer comments.
  See [prd/README.md](prd/README.md) and the [PRD Guide](prd/GUIDE.md).

- **Design** -- Design-and-decompose workflow: ingest a PRD, draft a technical design document, decompose into Jira-ready epics and stories, revise based on feedback, publish as a GitHub PR, respond to reviewer comments, and sync epics/stories to Jira.
  See [design/README.md](design/README.md).

- **Implement** -- Story-to-code workflow: take a Jira Story, plan the implementation, write contract-based tests and production code via TDD, validate against the project's CI expectations, and manage review via GitHub PRs.
  See [implement/README.md](implement/README.md).

- **E2E** -- Story-to-tests workflow for [QE] stories: discover the project's e2e testing infrastructure, map acceptance criteria to test scenarios, write e2e test code following the project's patterns and reference suite, validate against anti-patterns and scenario coverage, and manage review via GitHub PRs.
  See [e2e/README.md](e2e/README.md).

- **Code Review** -- AI-driven code review for uncommitted changes: discover project conventions, review with an independent reviewer perspective, present findings with honest implementor assessments for human decision, iterate until approved. Supports unattended mode for fully automated review-fix-iterate cycles.
  See [code-review/README.md](code-review/README.md).

- **CVE Fix** -- Automated CVE remediation: read vulnerability details from Jira, apply multi-strategy dependency fixes, validate, create pull requests, backport to release branches, and close Jira tickets. Language-agnostic.
  See [cve-fix/README.md](cve-fix/README.md).

- **AI-Ready** -- Scans a codebase and creates or updates AGENTS.md with project-specific build commands, test patterns, and coding standards.
  See [ai-ready/README.md](ai-ready/README.md).

- **KCS** -- KCS Solution article workflow: gather bug context from Jira, draft a KCS article in markdown, validate against the KCS Content Standard, and produce a handoff message for the support engineer.
  See [kcs/README.md](kcs/README.md).

- **Rebase Stack** -- Rebase a stacked-branch chain onto an updated base using `gh stack`, guide through conflict resolution, validate each branch, and push all updated branches.
  See [rebase-stack/README.md](rebase-stack/README.md).

- **Sizing** -- Pre-cycle Feature sizing: ingest Features from Jira (single or batch by Fix Version), assess against a T-shirt size rubric (XS–XXL) with per-team effort breakdowns (DEV, QE, UX, UI, DOCS), and write results back to Jira.
  See [sizing/README.md](sizing/README.md).

- **Skill Reviewer** -- Meta-workflow that audits AI skill directories against eight quality dimensions.
  See [skill-reviewer/README.md](skill-reviewer/README.md).

## How It Works

Each workflow is a top-level directory with a `SKILL.md`, while focused skills
live under `skills/<name>/`. Both use plain markdown with no IDE-specific
syntax. Workflows may add phase skills and commands; simple skills use only the
supporting references or scripts they need. The installer discovers both forms.

```
~/.ai-workflows/  (symlink to your clone)
  bugfix/
    SKILL.md, skills/, commands/
  docs-writer/
    SKILL.md, skills/, commands/
  skills/
    report-bug/
      SKILL.md, references/
```

`git pull` updates everything instantly through the symlink.

### Configuring Report Bug

`report-bug` derives its Jira target from the request, applicable project
`AGENTS.md`, issue context, or the consuming repository. Teams can commit
`.workflows/report-bug/config.yaml` and an optional Markdown template:

```yaml
jira_url: https://example.atlassian.net
project: TEAM
issue_type: Bug
template: template.md
severity_field: Severity
severity_mapping:
  critical: Critical
  high: High
  medium: Medium
  low: Low
  informational: Informational
environment_field: Environment
parent_field: Parent
affects_version_field: Affects versions
provenance:
  enabled: true
  agent: null
  model: null
```

Without consumer configuration, the skill prompts for unresolved target
details and offers the EDM project and EDM-style template as an opinionated
fallback; it never selects that target silently.
Priority is always left unset for triage. Parent relationships are validated,
Affects Version requires confirmation, and assignee is set only when requested;
Fix Version and Target Version remain planning decisions.
The skill is attended by design: creating a bug, adding evidence to a matching
issue, and uploading attachments each require an explicit preview and approval.
Generated descriptions identify the skill and version. Agent/model identity is
included only when the runtime exposes it authoritatively or configuration names
it explicitly.

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

### Codex

**User-level:**

```bash
./install.sh codex
```

**Project-level:**

```bash
./install.sh codex --project /path/to/project
```

### All Environments at Once

```bash
./install.sh all                          # user-level
./install.sh all --project /path/to/proj  # project-level
```

### Selective Installation

Each workflow or skill is intended for a specific project or use case:

- **bugfix** -- the **Flight Control** projects ([flightctl](https://github.com/flightctl/flightctl), [flightctl-ui](https://github.com/flightctl/flightctl-ui))
- **code-review** -- any project; reviews uncommitted changes against discovered project conventions
- **docs-writer** -- the [edge-manager](https://gitlab.cee.redhat.com/red-hat-enterprise-openshift-documentation/edge-manager) downstream docs project
- **prd** -- teams drafting Product Requirements Documents from Jira features
- **design** -- teams creating technical design documents and Jira-ready epic/story breakdowns from PRDs
- **implement** -- teams implementing Jira stories produced by the design workflow
- **e2e** -- teams writing e2e tests for [QE] stories produced by the design workflow
- **cve-fix** -- teams patching CVEs and updating vulnerable dependencies from Jira vulnerability tickets
- **ai-ready** -- onboarding any project for AI agents by generating AGENTS.md
- **kcs** -- teams writing KCS Solution articles for known issues with workarounds
- **triage** -- teams that want bulk Jira triage, categorization, and HTML reports from this repo or a clone
- **sizing** -- teams sizing Features for cycle planning using T-shirt sizes with per-team effort breakdowns
- **skill-reviewer** -- reviewing or standardizing Cursor/agent skills and skill packs (structure, clarity, completeness)
- **report-bug** -- filing complete Jira bugs with consumer-configurable targets and templates while leaving Priority for triage

Use `--packages` to install only the named workflows or skills:

```bash
./install.sh cursor --project ~/flightctl --packages bugfix
./install.sh cursor --project ~/edge-manager --packages docs-writer
./install.sh cursor --packages report-bug
./install.sh --list                       # show available workflows and skills
```

The former `--workflows` selector remains available as a deprecated alias.

For project-level Cursor installs, add the generated commands directory to `.gitignore`:

```gitignore
.cursor/commands/
```

The skill symlinks under `.cursor/skills/` and `.agents/skills/` may also need
ignoring depending on your project's conventions.

## Scopes

| Scope | Cursor | Claude Code | Gemini | Codex |
|-------|--------|-------------|--------|-------|
| **User** (default) | `~/.cursor/skills/<package>` + `~/.cursor/commands/` | `~/.claude/CLAUDE.md` | `~/.gemini/skills/<package>` | `~/.agents/skills/<package>` |
| **Project** (`--project`) | `.cursor/skills/<package>` + `.cursor/commands/` | `.claude/CLAUDE.md` | `.gemini/skills/<package>` | `.agents/skills/<package>` |

## Usage

### Claude Code

Invoke a workflow command using the colon-namespaced format:

- `/bugfix:assess`, `/bugfix:diagnose`, `/bugfix:fix`, ...
- `/code-review:start`, `/code-review:continue`, `/code-review:clean`
- `/docs-writer:gather`, `/docs-writer:plan`, `/docs-writer:draft`, ...

### Cursor

The installer generates flat command files in `.cursor/commands/` so each phase appears in the Cursor slash menu:

- `/bugfix-assess`, `/bugfix-diagnose`, `/bugfix-fix`, ...
- `/code-review-start`, `/code-review-continue`, `/code-review-clean`
- `/docs-writer-gather`, `/docs-writer-plan`, `/docs-writer-draft`, ...

Cursor scans both project-level (`.cursor/commands/`) and user-level (`~/.cursor/commands/`) directories. Commands are plain `.md` files — no manifest or wrapper directories needed. They are created by `install.sh` and cleaned up by `uninstall.sh`.

### Codex

Invoke a package as a skill and pass the workflow phase as context:

- `$bugfix assess EDM-123`
- `$design ingest PRD-123`
- `$report-bug`

Codex discovers user-level and repository-level skill symlinks automatically;
see [Where Codex loads local skills](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).

## Updating

```bash
cd ~/.ai-workflows && git pull
# or, if you enabled the update notifier:
aiw-update
```

### Optional: daily update notifier (Linux)

On Linux desktops with systemd user sessions and `notify-send`, `install.sh` can prompt to enable a daily check. If `~/.ai-workflows` is behind `origin/main`, you get a desktop notification suggesting `aiw-update`.

```bash
./install.sh cursor                  # prompts [y/N] when supported
./install.sh cursor --with-update-timer
./install.sh cursor --no-update-timer
./hack/install-update-timer.sh       # enable later
./hack/install-update-timer.sh --remove
```

## Uninstalling

```bash
./uninstall.sh                                          # user-level everything
./uninstall.sh cursor                                   # user-level Cursor only
./uninstall.sh codex                                    # user-level Codex only
./uninstall.sh cursor --packages bugfix                 # remove specific package
./uninstall.sh cursor --project /path/to/proj           # project-level Cursor
./uninstall.sh all --project /path/to/proj              # project-level everything
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add or modify workflows.

## License

See [LICENSE](LICENSE).
