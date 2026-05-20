<!-- Edited by Claude Code -->
# Documentation Site

The AI Workflows documentation site is built with [Zensical](https://zensical.org) — the next-gen successor to Material for MkDocs by the same team. Source lives in `docs/`, configuration in `zensical.toml`.

## Setup

```bash
uv sync --extra docs --no-install-project
```

## Local Preview

```bash
uv run zensical serve
```

Opens at `http://localhost:8000` with live reload on save.

## Build Static Site

```bash
uv run zensical build
```

Output goes to the `site/` directory (gitignored).

## Deploy to GitHub Pages

Build first, then push to the `gh-pages` branch:

```bash
uv run zensical build
uv run ghp-import -n -p -f site
```

Flags: `-n` adds a `.nojekyll` file (required for GitHub Pages), `-p` pushes to the remote, `-f` force-pushes.

GitHub Pages serves the `gh-pages` branch automatically. Enable it once under **Repository Settings → Pages → Source → Deploy from branch → `gh-pages`**.

The site will be live at `https://flightctl.github.io/ai-workflows/`.

### Automatic deployment

CI deploys on every push to `main` that touches `docs/`, `zensical.toml`, `CONTRIBUTING.md`, or `README.md` — no manual deploy needed after the initial setup.

## Structure

```text
docs/
├── index.md                     # Home page
├── getting-started/
│   ├── installation.md          # Installation guide
│   └── quick-start.md           # Quick start guide
├── workflows/
│   ├── index.md                 # Workflows overview with master diagram
│   ├── bugfix.md
│   ├── code-review.md
│   ├── cve-fix.md
│   ├── design.md
│   ├── docs-writer.md
│   ├── e2e.md
│   ├── implement.md
│   ├── kcs.md
│   ├── prd.md
│   ├── triage.md
│   ├── ai-ready.md
│   └── skill-reviewer.md
├── development/
│   ├── contributing.md
│   ├── workflow-structure.md
│   └── testing.md
├── reference/
│   ├── installation.md
│   └── configuration.md
└── images/
    └── logo.svg
```

## Adding a Page

1. Create `docs/section/page.md`
2. Add it to the `nav` array in `zensical.toml`
3. Run `uv run zensical serve` to preview

## Notes

- `site/` is gitignored — never commit it
- GLightbox is enabled natively via `zensical.extensions.glightbox`
- Mermaid diagrams render automatically in fenced code blocks tagged `mermaid`
- Dark/light mode uses Lucide icons (`lucide/sun`, `lucide/moon`)
