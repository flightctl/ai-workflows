<!-- Edited by Claude Code -->
# Contributing

## Adding a New Workflow

1. Create a directory at the repo root (lowercase, hyphens, e.g. `code-review/`).
2. Add the required files following the [workflow structure](workflow-structure.md).
3. Run `./install.sh cursor` (or `all`) to verify it gets picked up.
4. Submit a PR.

## Style

- Workflow content is plain markdown — no IDE-specific syntax.
- Keep `SKILL.md` under 30 lines. Use progressive disclosure (`guidelines.md`, `README.md`) for details.
- Use consistent terminology within a workflow.
- Don't duplicate content between `SKILL.md`, `guidelines.md`, and `controller.md`.

## Scripts

Some workflows include a `scripts/` directory for scripts that offload deterministic work from the LLM — validation, data transformation, file discovery.

Conventions:

- Scripts are invoked by the workflow's skill files, not by users directly
- Scripts must work when the workflow is installed via symlink
- Use Python 3 or bash — whichever fits the task
- Exit codes:
    - **Report scripts**: `exit 0` = informational, `exit 1` = halt
    - **Search/query scripts**: define semantics in docstrings

Currently, `skill-reviewer/scripts/` and `cve-fix/scripts/` use this pattern.

## Prompts

Some workflows include a `prompts/` directory for prompt templates given to sub-agents:

- Templates are self-contained — the sub-agent receives only the prompt
- Templates use `{placeholder}` syntax for values the caller fills in
- Prompts instruct the sub-agent to write output to `.artifacts/`

Currently, only `skill-reviewer/prompts/` uses this pattern.

## Testing Your Changes

1. Install locally: `./install.sh cursor` (or `all`).
2. Open a Cursor project and reference `@your-workflow` to verify discovery.
3. Run through at least one phase to confirm the controller dispatches correctly.
4. Uninstall and reinstall to verify clean teardown: `./uninstall.sh && ./install.sh cursor`.
