---
name: publish
description: Push the handoff spec as a GitHub PR for external review.
---

# Publish — Post Handoff Spec

Post the finalized handoff spec as a GitHub pull request so technical
reviewers and stakeholders can review it.

## Critical Rules

- **Confirm before pushing** — verify the target repository, branch name, and PR details with the researcher.
- **Draft PR** — always create as a draft; the researcher decides when to mark it ready for review.
- **No force-push.** No destructive git operations.
- **No direct commits to main.** Always use a feature branch.

## Process

Run `git rev-parse --show-toplevel` from anywhere inside the source repo and
store its output in the `source_repo_root` shell variable. If this command
fails, stop and ask the researcher to open the source-repo workspace. Resolve
all source-repo artifact paths below against this root.

Before reading the handoff or constructing any path containing `{issue-key}`,
require the entire value to match `[A-Za-z0-9][A-Za-z0-9._-]*`. If it does not,
stop and ask the researcher for a valid artifact key. This keeps the key to a
single path component.

### Step 1: Read the Handoff Spec

Read `{source_repo_root}/.artifacts/ux-design/{issue-key}/05-handoff.md`.

If the file doesn't exist, tell the researcher that `/handoff` should be run first.

Read `{source_repo_root}/.artifacts/ux-design/{issue-key}/00-context.md` and
verify that the context is `enriched` and the handoff
is approved against the current discovery revision. If the manifest marks the
handoff stale or its revision differs, stop and recommend `/handoff` before
publishing. Never publish a handoff produced from exploratory context.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at
`{source_repo_root}/.artifacts/config.json`.

The shared config stores `docs_repo_path` relative to `{source_repo_root}`.
Resolve a relative configured or researcher-supplied path against
`{source_repo_root}`; keep an absolute path absolute. Use the normalized
absolute result as runtime `{docs_repo_path}` for all validation, `git -C`
commands, filesystem paths, and provenance targets below. Never pass the raw
relative config value to Git or file operations.

**If the config exists**, read its `docs_repo_path` and `docs_repo_remote`.
**If it does not exist**, ask the researcher where the planning docs repo is
checked out, accepting an absolute path or one relative to
`{source_repo_root}`.

Resolve the candidate path against `{source_repo_root}` if it is relative. Verify
that the resolved path exists and is a git repository. If either check fails,
stop, report the failed check, and ask the researcher to correct the path before
continuing. Run `git -C "{docs_repo_path}" remote get-url origin` to read the
actual remote. When a config already exists, verify this URL matches its
`docs_repo_remote`. When no config exists, confirm the URL with the researcher
and use it as `docs_repo_remote`.

If reading or validating the remote fails, stop before publishing, report the
error or mismatch, and ask the researcher to correct the path or remote. Re-run
all validations after the correction. Do not write or update the shared config
while validation is failing. Once the path and remote pass validation, save
`docs_repo_path` relative to `{source_repo_root}` and `docs_repo_remote` to the
shared config. Keep using the resolved absolute `{docs_repo_path}` for the rest
of this phase.

Derive `{owner}/{repo}` from the remote URL (e.g.,
`git@github.com:org/repo.git` → `org/repo`).
Validate `{owner}` and `{repo}` separately as single components using
`[A-Za-z0-9][A-Za-z0-9._-]*`; stop if either component is invalid.

### Step 3: Pre-Flight Checks

Verify the environment:

```bash
gh auth status
```

```bash
git -C "{docs_repo_path}" remote -v
```

```bash
git -C "{docs_repo_path}" status --porcelain
```

If the output is not empty, stop and tell the researcher the docs repo has
uncommitted changes that must be resolved before publishing. Do not proceed
with a dirty working tree.

Confirm with the researcher:
- **Base branch:** Which branch should the PR target? (usually `main`)
- **Release:** Which release is this for?
- **Feature:** A short, lowercase, hyphenated slug with the issue key appended
- **Branch name:** Propose `ux-design/{issue-key}` and let the researcher override

Before using `{base-branch}` or `{branch-name}` in shell commands, require each
to match `[A-Za-z0-9][A-Za-z0-9._/-]*`. Then validate both as Git branch names:

```bash
git -C "{docs_repo_path}" check-ref-format --branch "{base-branch}"
git -C "{docs_repo_path}" check-ref-format --branch "{branch-name}"
```

If either command fails, ask the researcher for a valid branch name. Also reject
`main` and the selected `{base-branch}` as the feature branch name; ask for a
different value before continuing.

Before building commands from `{release}` or `{feature}`, require each value to
match `[A-Za-z0-9][A-Za-z0-9._-]*` so each is a single safe path component.
Set `docs_repo_root = Path(docs_repo_path).resolve()`,
`destination_dir = (docs_repo_root / release / feature).resolve()`, and
`handoff_target = (destination_dir / "handoff.md").resolve()`. Require
`destination_dir.relative_to(docs_repo_root)` to succeed and return a non-`.`
relative path. Apply the same containment check to `handoff_target`.
If either check fails, stop and report that the destination is outside the docs
repo. This check also catches existing symlinks that point outside the
repository.
Use the resolved destination paths for filesystem operations and the provenance
target below.

The handoff spec file path in the docs repo: `{release}/{feature}/handoff.md`.

### Step 4: Create Branch and Commit

All git operations run against the **docs repo**. Use
`git -C "{docs_repo_path}"` for all commands.

```bash
git -C "{docs_repo_path}" checkout -b "{branch-name}" "{base-branch}"
```

```bash
mkdir -p "{destination_dir}"
```

```bash
cp "{source_repo_root}/.artifacts/ux-design/{issue-key}/05-handoff.md" "{handoff_target}"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{handoff_target}"`.

Provenance at publish time:
- If the provenance event log at
  `{source_repo_root}/.artifacts/ux-design/{issue-key}/provenance.json` contains
  any non-`commit` event, the footer reflects the full authoring session
  (`provenance_kind: session`). The ux-design authoring phases are `/handoff`,
  `/revise`, `/respond`, and `manual-edit`.
- If the log is missing, the render recipe **auto-captures a commit-time
  snapshot** (`phase=commit`, `provenance_kind: commit_only`) so stale footers
  are replaced instead of copied forward.
- If the existing log contains only `commit` events, the render recipe refreshes
  the commit-time snapshot and keeps `provenance_kind: commit_only`.
- Only if the researcher explicitly declines provenance, pass `ALLOW_MISSING=yes` to
  strip the footer and record `provenance_kind: declined`.

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/handoff.md"
```

```bash
git -C "{docs_repo_path}" commit -m "Add UX design handoff for {issue-key}"
```

### Step 5: Prepare PR Description

Prepare the PR description and save it to
`{source_repo_root}/.artifacts/ux-design/{issue-key}/06-pr-description.md`
(in the source repo's artifact directory):

```markdown
## UX Design Handoff: {title}

**Jira:** {issue-link}

### Summary
{2-3 sentence summary of what this handoff spec covers}

### Requesting Review On
- Component mapping accuracy
- State enumeration completeness
- Acceptance criteria clarity
- Interaction specs correctness

### How to Review
- Comment inline on specific sections
- Flag any missing states or interaction edge cases
- Approve when the handoff spec is implementation-ready
```

### Step 6: Push and Create PR

```bash
git -C "{docs_repo_path}" push -u origin "{branch-name}"
```

Create a draft PR:

Treat the title in the PR description as data; do not interpolate it into shell
source. Keep the following validated values in shell variables:

```bash
pr_repo="{owner}/{repo}"
base_branch="{base-branch}"
branch_name="{branch-name}"
issue_key="{issue-key}"
pr_body_file="${source_repo_root}/.artifacts/ux-design/${issue_key}/06-pr-description.md"
```

Read the title from the PR description and invoke `gh` through a Python argument
list so the title is passed literally:

```bash
python3 - "$pr_repo" "$base_branch" "$branch_name" "$issue_key" "$pr_body_file" <<'PY'
from pathlib import Path
import re
import subprocess
import sys

repo, base, head, issue_key, body_file = sys.argv[1:]
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repo):
    raise SystemExit("Invalid GitHub owner/repo")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", base):
    raise SystemExit("Invalid base branch")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", head):
    raise SystemExit("Invalid head branch")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", issue_key):
    raise SystemExit("Invalid issue key")

body = Path(body_file).read_text(encoding="utf-8")
match = re.search(r"(?m)^## UX Design Handoff: (.+)$", body)
if not match:
    raise SystemExit("PR description is missing its UX Design Handoff title")
title = f"{issue_key}: UX Design Handoff - {match.group(1).strip()}"
subprocess.run(
    [
        "gh", "pr", "create", "--draft", "--repo", repo,
        "--base", base, "--head", head, "--title", title,
        "--body-file", body_file,
    ],
    check=True,
    shell=False,
)
PY
```

### Step 7: Save Publish Metadata

Write `{source_repo_root}/.artifacts/ux-design/{issue-key}/publish-metadata.json`:

```json
{
  "release": "{release}",
  "feature": "{feature}",
  "handoff_file_path": "{release}/{feature}/handoff.md",
  "pr_number": "{pr-number}",
  "branch": "{branch-name}"
}
```

### Step 8: Report to Researcher

Present:
- PR URL
- Docs repo and branch name
- File location in the docs repo
- Next steps (share with reviewers, then use `/respond` when comments arrive)

## Output

- `{source_repo_root}/.artifacts/ux-design/{issue-key}/06-pr-description.md`
- `{source_repo_root}/.artifacts/ux-design/{issue-key}/publish-metadata.json`
- Handoff spec committed and pushed to feature branch in the docs repo
- Draft PR created against the docs repo

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
