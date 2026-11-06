---
name: publish
description: Push the handoff spec as a GitHub PR for external review.
---

# Publish — Post Handoff Spec

Post the finalized handoff spec as a GitHub pull request so technical
reviewers and stakeholders can review it.

## Critical Rules

- **Confirm before pushing** — verify the target repository, branch name, and PR details with the researcher.
- **Draft PR** — create new PRs as drafts; when updating an existing PR, preserve its current status.
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

If `{source_repo_root}/.artifacts/ux-design/{issue-key}/publish-metadata.json`
exists, read it and treat this invocation as an update to the existing PR. Keep
its PR number, branch, and handoff path; do not create a second PR for the same
handoff. Older metadata may also contain `release` and `feature` fields; treat
those as informational and do not use them to reconstruct the handoff path. If
the metadata is unreadable or lacks its PR number, branch, or handoff path,
stop and ask the researcher to repair it before publishing.

Read `{source_repo_root}/.artifacts/ux-design/{issue-key}/00-context.md` and
verify that the context is `enriched` and the handoff
is approved against the current discovery revision. If the manifest marks the
handoff stale or its revision differs, stop and recommend `/handoff` before
publishing. Never publish a handoff produced from exploratory context.

Also read `{source_repo_root}/.artifacts/ux-design/{issue-key}/01-discovery.md`;
its **Upstream References** record the resolved published PRD and design paths.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at
`{source_repo_root}/.artifacts/config.json`.

The shared config stores `docs_repo_path` as a normalized absolute path. For
backward compatibility, expand `~` and resolve a relative configured or
researcher-supplied path against `{source_repo_root}`. Use the normalized
absolute result as runtime `{docs_repo_path}` for all validation, `git -C`
commands, filesystem paths, and provenance targets below. Never pass a raw
relative config value to Git or file operations.

**If the config exists**, read its `docs_repo_path` and `docs_repo_remote`.
**If it does not exist**, ask the researcher where the planning docs repo is
checked out, accepting an absolute path or one relative to
`{source_repo_root}`.

Resolve the candidate path against `{source_repo_root}` if it is relative, then
verify that the normalized absolute path exists and is a git repository. If
either check fails, stop, report the failed check, and ask the researcher to
correct the path before continuing. Run
`git -C "{docs_repo_path}" remote get-url origin` to read the
actual remote. When a config already exists, verify this URL matches its
`docs_repo_remote`. When no config exists, confirm the URL with the researcher
and use it as `docs_repo_remote`.

If reading or validating the remote fails, stop before publishing, report the
error or mismatch, and ask the researcher to correct the path or remote. Re-run
all validations after the correction. Do not write or update the shared config
while validation is failing. Once the path and remote pass validation, save
the normalized absolute `docs_repo_path` and `docs_repo_remote` to the shared
config. Keep using the resolved absolute `{docs_repo_path}` for the rest of this
phase.

Derive `{owner}/{repo}` from the remote URL (e.g.,
`git@github.com:org/repo.git` → `org/repo`).
Validate `{owner}` and `{repo}` separately as single components using
`[A-Za-z0-9][A-Za-z0-9._-]*`; stop if either component is invalid.

### Step 3: Resolve the Canonical Handoff Location and Pre-Flight Checks

Read the Feature key from `00-context.md`. It must be a valid Jira issue key
matching `[A-Z][A-Z0-9]*-[0-9]+`; otherwise stop and ask the researcher to
enrich the context with its Feature key.

Read the resolved PRD and design document paths from `01-discovery.md`'s
**Upstream References**. If either is missing, stop and ask the researcher to
publish or locate both planning documents in the docs repo before publishing
the handoff.

Set `docs_repo_root = Path(docs_repo_path).resolve()`. Resolve relative source
paths against `docs_repo_root`, then resolve both paths with `strict=True`.
Require the files to exist, have the basenames `prd.md` and `design.md`, and
remain inside `docs_repo_root`. Require both files to have the same parent
directory. This is the canonical feature directory: `/ui-design:ingest` looks
for the UX handoff alongside the PRD and design document, so `/publish` must
put it there rather than accepting a second, independently chosen directory.

Set `destination_dir` to the resolved parent directory,
`handoff_file_path` to
`(destination_dir / "handoff.md").relative_to(docs_repo_root).as_posix()`, and
`handoff_target` to `(destination_dir / "handoff.md").resolve()`. Require
`destination_dir.name` to contain the Feature key. `/ui-design:ingest`
discovers published artifacts by matching the feature directory name to the
Feature or story key, so a directory that cannot be found by that search is
not a valid handoff destination. Require both the directory and target to
remain inside the docs repo, including through existing symlinks.
Require each component of the repo-relative directory path to match
`[A-Za-z0-9][A-Za-z0-9._-]*` before using the path in shell commands.

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

**If updating an existing PR**, validate the stored `branch` using the branch
checks below. Require the stored `handoff_file_path` to equal the canonical path
derived above, and require `pr_number` to contain only decimal digits. Read the
existing PR:

```bash
gh pr view {pr-number} --repo {owner}/{repo} --json state,url,headRefName,baseRefName
```

Require the PR to be open and its head branch to match the stored branch. If
either check fails, stop and report the mismatch; do not create a replacement
PR automatically. Show the researcher the PR URL, base branch, feature branch,
and canonical handoff path, then ask for approval to update that PR. Use its
`baseRefName` as `{base-branch}` and the stored branch for this run.

**If no publish metadata exists**, confirm with the researcher:
- **Base branch:** Which branch should the PR target? (usually `main`)
- **Handoff path:** Show the canonical `{handoff_file_path}` derived from the
  published PRD and design directory; do not offer a different destination
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

Use only the resolved `destination_dir`, `handoff_target`, and
`handoff_file_path` for filesystem operations and the provenance target below.

### Step 4: Validate Screenshot References

Before publishing, verify that every screenshot referenced in the handoff
is available and has a valid identity record.

Read `{source_repo_root}/.artifacts/ux-design/{issue-key}/screenshot-manifest.json`.
Check the handoff's Screenshot Index section. If the handoff references
screenshots but the manifest is missing or has no screenshot entries,
stop and recommend re-running `/handoff` to generate the manifest.

For each entry in the manifest:

1. **File exists:** Verify the screenshot file at
   `{source_repo_root}/.artifacts/ux-design/{issue-key}/screenshots/{filename}`
   exists and is a regular file (not a symlink to a path outside the
   artifact directory).

2. **Checksum matches:** Compute the SHA-256 of the file and compare it to
   the manifest's `sha256` field. If they differ, warn the researcher that
   the image has changed since the manifest was written and ask whether to
   update the manifest or re-curate.

3. **Reference in handoff:** Verify the screenshot ID (e.g., `SS-1`) appears
   in the handoff's Screenshot Index section. Warn about manifest entries not
   referenced in the handoff (orphaned assets) and about handoff references
   not in the manifest (broken references).

If any screenshot is missing or has a broken reference, stop before
creating the branch and report the specific failures.

### Step 5: Resolve Screenshot Storage Policy

**Skip this step entirely** when the handoff's Screenshot Index section says
"None" and the authoring manifest does not exist or is empty. Resolve
`screenshot_storage` to `none` **in memory only** — do not write it to
`publish-metadata.json` yet. Previous metadata and assets must remain
intact for the reconciliation check in Step 6; persist `none` only after
a successful commit+push. Proceed to Step 6 without prompting for a
storage policy or touching asset paths.

**Inverse mismatch guard.** If the Screenshot Index says "None" or
text-only but the authoring manifest is **nonempty**, stop and ask the
researcher to reconcile (reference the images or clear the authoring
manifest) before publishing. Do not automatically delete evidence;
prior published consumer data remains available for Step 6 cleanup.

When the handoff contains screenshot references, determine how assets
will be stored. The explicit repository or researcher policy is
authoritative — do not infer storage mode from filesystem configuration
alone.

**Policy resolution order:**

1. **Recorded policy.** If the `publish-metadata.json` for this handoff
   already contains a `screenshot_storage` field **and its value is not
   `none`**, use it. A previously recorded `none` is not valid
   authorization when the handoff now contains images — fall through to
   check repository policy or ask the researcher.

2. **Repository-level policy.** Check for a `screenshot_storage` key in
   `{docs_repo_path}/.workflows/ux-design/config.json` first. If it has
   no valid value, check `{docs_repo_path}/.workflows/config.json`.
   Valid values are `lfs`, `external`, or `git`. Use the first valid
   value as the explicit repository policy.

3. **No valid policy.** Stop before copying assets. Present options:
   **lfs** (Git LFS; requires LFS init in docs repo), **external**
   (immutable revision-bound URLs per screenshot), **git** (ordinary
   Git objects; increases repo size). Wait for the researcher's
   explicit choice. Do not default to any mode.

**Constraints:** `.gitattributes` LFS patterns alone are not a policy
choice; do not auto-commit images or auto-enable LFS tracking. Do not
invent external upload providers. Store the policy in
`publish-metadata.json` for subsequent updates.

### Step 6: Create or Update Branch and Commit

All git operations run against the **docs repo**. Use
`git -C "{docs_repo_path}"` for all commands.

Immediately before switching or creating the branch, repeat the clean-worktree check:

```bash
git -C "{docs_repo_path}" status --porcelain
```

If the output is not empty, stop before checkout and ask the researcher to
resolve the changes. Leave the worktree and index untouched.

**For a new PR**, create the feature branch from the confirmed base branch:

```bash
git -C "{docs_repo_path}" checkout -b "{branch-name}" "{base-branch}"
```

**For an existing PR**, fetch and check out its branch without resetting local
work. If the local branch exists, fast-forward it to the remote; otherwise,
create a tracking branch:

```bash
git -C "{docs_repo_path}" fetch origin "{branch-name}"
```

```bash
if git -C "{docs_repo_path}" show-ref --verify --quiet "refs/heads/{branch-name}"; then
  git -C "{docs_repo_path}" checkout "{branch-name}"
  git -C "{docs_repo_path}" merge --ff-only "origin/{branch-name}"
else
  git -C "{docs_repo_path}" checkout --track -b "{branch-name}" "origin/{branch-name}"
fi
```

```bash
mkdir -p "{destination_dir}"
```

```bash
cp "{source_repo_root}/.artifacts/ux-design/{issue-key}/05-handoff.md" "{handoff_target}"
```

**Skip screenshot handling on initial text-only publishes** — when the
handoff's Screenshot Index says "None" **and** no publish-metadata
`screenshot_assets` exist from a prior publish. Do not prompt for a
storage policy, touch asset paths, or stage screenshot directories.

**Reconcile previous assets on updates.** When updating an existing
publish (`publish-metadata.json` exists with `screenshot_assets`), always
check for removals even if the current handoff has no screenshots. If
the current authoring manifest is empty or absent but `screenshot_assets`
records prior images: remove them (lfs/git: `git rm` only paths still
tracked; external: remove embeds/index entries), `git rm` the consumer
manifest only if still tracked, and set `screenshot_storage` to `none`
**after** the commit and push succeed. Use previous metadata for
cleanup; do not overwrite it before reconciliation.

**Copy screenshot assets** (only when the authoring manifest is non-empty
and the Screenshot Index section contains image references):

**Pre-copy validation.** For each manifest entry, require `{filename}`
to match `^SS-[0-9]+-[a-z0-9-]+\.png$`. Resolve each candidate
destination `{destination_dir}/screenshots/{filename}` and verify it is
inside `{docs_repo_root}`. If `screenshots/` exists, confirm it is not
a symlink escaping the repo. Stop before copying if any check fails.

**`lfs` or `git` mode:** Create `{destination_dir}/screenshots/`, copy
each file individually, verify each copy's SHA-256 matches the manifest.
For `lfs`, also confirm LFS is initialized and tracking covers the path.

**`external` mode:** No file copies. Require immutable HTTPS URLs per
screenshot. Retrieve each URL's bytes, verify SHA-256 against the
manifest, and stop on mismatch. Rewrite embeds and index in the published
handoff; preserve authoring references in `05-handoff.md`.

**Reconcile removals** (update publishes only). Compare previous
`screenshot_assets` against the current manifest. For removed IDs:
`lfs`/`git` — `git rm` only if still tracked; `external` — remove
embed/index entries. If all removed, also `git rm` the consumer
manifest if tracked, and set `screenshot_storage` to `none` after
commit.

**Publish consumer manifest.** When any screenshots remain after
removals, write `{destination_dir}/screenshot-manifest.json` with `id`,
`sha256`, `caption`, `alt_text`, `flow`, `state`, `published_ref`, plus
`issue_key`, `context_revision`, `prototype_iteration`. Omit the
authoring `source` field.

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

**Build owned-path allowlist, stage, and commit.** Read and follow
`../../_shared/recipes/screenshot-publish-stage.md` with:
- `DOCS_REPO_PATH="{docs_repo_path}"`
- `HANDOFF_FILE_PATH="{handoff_file_path}"`
- `HANDOFF_DIR` = the repo-relative parent directory of `{handoff_file_path}` (i.e., `dirname "{handoff_file_path}"`)
- `COPIED_FILENAMES` = the array of screenshot filenames copied this run
- `REMOVED_FILENAMES` = the array of screenshot filenames removed via `git rm`
- `MANIFEST_WRITTEN="true"` if the consumer manifest was written/updated
- `MANIFEST_REMOVED="true"` if the consumer manifest was removed (all screenshots deleted)
- `COMMIT_MESSAGE="{Add|Update} UX design handoff for {issue-key}"`

### Step 7: Prepare PR Description for a New PR

When updating an existing PR, keep its existing description and skip the rest
of this step. Do not rewrite the PR body as part of a handoff-only update.

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

### Step 8: Push and Create PR

**For an existing PR**, push to its branch when unpushed commits
exist (the branch is ahead of its remote tracking ref). Keep its PR
number, URL, and draft/ready status; do not run `gh pr create`. If a
prior invocation committed but the push failed, this recovers without
re-running Steps 4–7.

```bash
git -C "{docs_repo_path}" push origin "{branch-name}"
```

**For a new PR**, push the branch and create a draft PR:

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

### Step 9: Save Publish Metadata

For a new PR, write
`{source_repo_root}/.artifacts/ux-design/{issue-key}/publish-metadata.json`:
Store `handoff_file_path`, `upstream_prd_path`, and `upstream_design_path`
relative to the docs repo root, with `/` separators. The upstream paths are the
resolved paths used to derive the canonical handoff directory.

```json
{
  "handoff_file_path": "{handoff_file_path}",
  "upstream_prd_path": "{repo-relative-prd-path}",
  "upstream_design_path": "{repo-relative-design-path}",
  "pr_number": "{pr-number}",
  "branch": "{branch-name}",
  "screenshot_storage": "{lfs | external | git | none}",
  "screenshot_assets": [
    {
      "id": "SS-1",
      "filename": "{filename}",
      "sha256": "{hex digest at publish time}",
      "published_path": "{repo-relative path or external URL}"
    }
  ]
}
```

- `screenshot_storage`: the storage mode used for this publish. `none` when
  the handoff has no screenshots.
- `screenshot_assets`: one entry per published screenshot, enabling
  `/respond` and subsequent publishes to detect visual-only changes by
  comparing the current file's SHA-256 against the recorded value. For
  `external` mode, `published_path` is the external URL; for `lfs` or
  `git`, it is the repo-relative path.

For an existing PR, retain the PR number, branch, and other identity
metadata. After a successful push, update `screenshot_storage` and
replace `screenshot_assets` with the current entries. If no screenshots
remain, set `screenshot_storage` to `none` and `screenshot_assets` to
`[]`. If push failed, preserve previous metadata unchanged.

### Step 10: Report to Researcher

Present the existing PR URL when updating, or the new PR URL when publishing
for the first time. Also report:
- Docs repo and branch name
- File location in the docs repo
- Whether the existing PR was updated, was already current, or a new draft PR
  was created
- Next steps (share with reviewers, then use `/respond` when comments arrive)

## Output

- `{source_repo_root}/.artifacts/ux-design/{issue-key}/06-pr-description.md`
- `{source_repo_root}/.artifacts/ux-design/{issue-key}/publish-metadata.json`
- Handoff spec committed and pushed to feature branch in the docs repo
- Existing PR updated or draft PR created against the docs repo

## When This Phase Is Done

Report your results:
- PR URL and branch name, and whether it was updated, already current, or newly
  created
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
