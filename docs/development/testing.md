<!-- Edited by Claude Code -->
# Testing

## Testing a Workflow

Because workflows are markdown-based skill files, testing is manual. Follow these steps to validate a workflow:

1. **Install locally**: `./install.sh cursor` (or `all`)
2. **Verify discovery**: Open a project and confirm the workflow appears in your AI environment
3. **Smoke test**: Run through at least one phase to confirm the controller dispatches correctly
4. **Clean teardown**: Uninstall and reinstall to verify removal works: `./uninstall.sh && ./install.sh cursor`

## CI Checks

The following checks run automatically on every pull request:

### Structure Validation

`.github/scripts/validate-structure.sh` verifies:

- Every workflow directory contains a `SKILL.md`
- Required files are present and properly formatted
- YAML frontmatter in `SKILL.md` files is valid

### Markdown Lint

Uses [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2) with the project's `.markdownlint-cli2.yaml` configuration. All markdown files must pass linting.

### Link Check

Uses [lychee](https://github.com/lycheeverse/lychee-action) to check for broken links in all markdown files. Configuration in `.lychee.toml`.

## What to Check Before Submitting

- [ ] `./install.sh cursor` picks up the new workflow
- [ ] At least one phase runs end-to-end
- [ ] Path references are all relative (for symlink compatibility)
- [ ] `SKILL.md` is under 30 lines
- [ ] YAML frontmatter has valid `name` and `description`
- [ ] `guidelines.md` covers principles, hard limits, safety, and quality
- [ ] `README.md` documents phases, artifacts, and getting started
