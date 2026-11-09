---
name: publish
description: Post the design document as a GitHub PR for external review.
---

# Publish Design Document Skill

You are a submission specialist. Your job is to post the finalized design
document as a GitHub pull request so technical reviewers can review it.

## Your Role

Take the design document artifact, commit it to a feature branch, push it,
and create a draft PR with a clear description. Confirm all details with
the user before taking action.

## Critical Rules

- **Confirm before pushing.** Verify the target repository, branch name, and PR details with the user.
- **Draft PR.** Always create as a draft — the user decides when to mark it ready for review.
- **No force-push.** No destructive git operations.
- **No direct commits to main.** Always use a feature branch.

## Shared Script

This skill delegates deterministic git and CLI operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/publish.py
```

The script provides subcommands: `preflight`, `resolve-remotes`, `push`,
`check-existing`, `create-pr`, and `save-metadata`. See the script header for
full usage.

## Process

### Prerequisites: Resolve Script Paths

Before any `cd` or subshell that changes the working directory, resolve
shared scripts to absolute paths so they remain valid:

```bash
PUBLISH_SCRIPT="${HOME}/.ai-workflows/_shared/scripts/publish.py"
```

Set `SKILL_DIR` to the canonical directory of this loaded skill file
(resolved from the path provided by the phase dispatcher or file-read
context, following symlinks). If the loaded file path is unavailable,
stop and report — do not fall back to `$HOME`, `BASH_SOURCE`, or the
current working directory:

```bash
# SKILL_DIR: set by the agent to this skill file's canonical directory
VALIDATION_INDEX_SCRIPT="$(realpath "${SKILL_DIR}/../scripts/validation_index.py")" || { echo "Cannot resolve ../scripts/validation_index.py" >&2; exit 1; }
```

If the resolution fails (script not found at the expected relative
location), stop and report the error — do not fall back to a different
install or guess the path.

Use `$PUBLISH_SCRIPT` and `$VALIDATION_INDEX_SCRIPT` instead of the
relative paths in all subsequent commands.

### Step 1: Read the Design Document

Read `.artifacts/design/{issue-key}/03-design.md`.

If the file doesn't exist, tell the user that `/draft` should be run first.

### Step 2: Resolve Docs Repo

Check for an existing docs repo configuration at `.artifacts/config.json`.

**If the config exists**, read it and validate:

1. Verify the path exists on the local filesystem
2. Verify the directory is a git repository
3. Verify the configured `docs_repo_remote` matches at least one fetch or push
   URL in the docs repository; do not require it to be named `origin`

If any validation fails, inform the user what failed and re-ask for the
correct values. Resolve `~` to an absolute path before saving. Update
`.artifacts/config.json` with the corrected values.

**If the config does not exist**, ask the user:

- **Docs repo local path:** Where is the planning docs repo checked out?
  (e.g., `~/src/planning-docs`)
- **Docs repo remote:** Run `git -C "{docs_repo_path}" remote -v`, choose the
  docs repository URL without embedded credentials to save, and confirm it
  with the user before proceeding. Never save a token or password in
  `.artifacts/config.json`.
  The remote name is not part of the configuration contract.

Validate the path and remote. Resolve `~` to the user's home directory
so the stored path is absolute. Write `.artifacts/config.json` with the
validated `docs_repo_path` and `docs_repo_remote`.

### Step 3: Pre-Flight Checks

Run the shared pre-flight checks from the docs repo directory:

```bash
(cd "{docs_repo_path}" && python3 "$PUBLISH_SCRIPT" preflight --platform github)
```

Parse the output to confirm `auth_ok=true`. Also verify the docs repo state:

```bash
git -C "{docs_repo_path}" remote -v
```

```bash
git -C "{docs_repo_path}" status
```

Resolve the canonical PR target and the branch push destination:

Read and follow `../../_shared/recipes/resolve-docs-publish-remotes.md` with
`DOCS_REPO_PATH`, `CONFIGURED_DOCS_REPO_REMOTE`, and `BRANCH_NAME`. The shared
script invocation below performs that resolution and emits the recipe's
outputs as JSON.

```bash
(cd "{docs_repo_path}" && python3 "$PUBLISH_SCRIPT" resolve-remotes --configured-remote "{docs_repo_remote}")
```

Parse the JSON output and confirm these values with the user before modifying
or pushing the docs repository:

- `upstream_repo` — repository where the PR will be created
- `upstream_remote` — remote used to fetch the canonical base branch
- `push_remote` and `push_url` — destination for the feature branch
- `fork_owner` and `cross_repository` — values used to qualify the PR head

`push_url` is a credential-free display value. When a Git command needs the
actual push transport, derive it locally with `git remote get-url --push
"{push_remote}"`; do not copy credentials into workflow artifacts or prompts.

Provenance at publish time:
- If `.artifacts/design/{issue-key}/provenance.json` exists from `/draft`, `/revise`,
  or `/respond`, the footer reflects the full authoring session (`provenance_kind:
  session`).
- If the log is missing, the render recipe **auto-captures a commit-time snapshot**
  (`phase=commit`, `provenance_kind: commit_only`) so stale footers are replaced
  instead of copied forward.
- Only if the user explicitly declines provenance, pass `ALLOW_MISSING=yes` to strip
  the footer and record `provenance_kind: declined` (no human-readable block).

Search the docs repo for a published PRD directory containing
`{issue-key}`:

```bash
find "{docs_repo_path}" -type d -name "*{issue-key}*"
```

Filter matches to directories that contain a `prd.md` file.

If exactly one matching directory contains `prd.md` (e.g.,
`v2.1/delta-updates-EDM-4867`), parse the path to extract `release` (first
path component under the docs repo root) and `feature` (second component)
and propose them as defaults below. If multiple matches contain `prd.md`,
present them to the user and ask which one to use.

Confirm with the user:
- **Base branch:** Which branch should the PR target? (usually `main`)
- **Release:** Which release is this for? (e.g., `v2.1`, `2026-Q2`).
  If a PRD directory was found, propose the extracted `release` value as
  the default. Otherwise, if the Jira issue has a fix version, suggest that.
- **Feature:** A short, lowercase, hyphenated slug for the feature
  directory, with the Jira issue key appended (e.g., `port-mappings-EDM-1471`).
  If a PRD directory was found, propose the extracted `feature` value as
  the default. Otherwise, suggest a slug derived from the Jira issue summary
  with the issue key appended. Ask for **just the slug**, not a full path.
- **Branch name:** Propose `design/{issue-key}` and let the user override.
  Use the confirmed value as `{branch-name}` in all subsequent steps.

These values determine the design document file path in the docs repo:
`{release}/{feature}/design.md`. The filename is always `design.md` —
placed alongside the PRD (`prd.md`) if one was published previously.

### Step 4: Create Branch and Commit

All git operations run against the **docs repo**. Use
`git -C "{docs_repo_path}"` for all commands.

Verify the docs repo is clean before modifying it:

```bash
git -C "{docs_repo_path}" status
```

If there are uncommitted changes, ask the user before continuing.

Check if the branch already exists:

```bash
git -C "{docs_repo_path}" branch --list {branch-name}
```

```bash
git -C "{docs_repo_path}" fetch {upstream-remote}
```

```bash
PUSH_URL_RAW="$(git -C "{docs_repo_path}" remote get-url --push "{push-remote}")"
git -C "{docs_repo_path}" ls-remote --heads "$PUSH_URL_RAW" "refs/heads/{branch-name}"
```

Depending on results:

```bash
# If branch exists locally:
git -C "{docs_repo_path}" checkout {branch-name}

# If branch does not exist locally but exists on the push URL:
git -C "{docs_repo_path}" fetch "$PUSH_URL_RAW" "refs/heads/{branch-name}:refs/remotes/publish-push/{branch-name}"
git -C "{docs_repo_path}" checkout -b {branch-name} publish-push/{branch-name}

# If branch doesn't exist at all:
git -C "{docs_repo_path}" checkout -b {branch-name}
```

**Validation artifact resolution and preflight (before any docs-repo
mutation):**

All resolution, snapshot, and preflight operations below run
against local `.artifacts/` and read from the docs repo without
modifying it. No file in `{docs_repo_path}` is copied, staged, or
committed until all preflights pass and any required confirmations
are obtained.

**Resolve current artifacts.** Resolve the local validation
artifact set:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" resolve --local ".artifacts/design/{issue-key}"
```

If the command exits 0, parse the JSON array output as the current
set (may be empty `[]`). If the command exits non-zero, a
validation error occurred (malformed index, missing listed files) —
**stop and report the error to the user.** Do not fall back to
legacy behavior when a malformed index is present.

If `validation-index.json` does not exist in
`.artifacts/design/{issue-key}` and `04-testplan.md` exists (legacy
layout), build a normalized index first:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" build-legacy ".artifacts/design/{issue-key}" ".artifacts/design/{issue-key}/validation-index.json"
```

This writes `validation-index.json` with the single primary entry.
Re-run `resolve --local` to get the normalized set.

Remove any snapshot left by a previous run before capturing:

```bash
rm -f -- ".artifacts/design/{issue-key}/prev-published-index.json"
```

If the removal command fails (non-zero exit for a reason other than
file-not-found), stop and report the error.

**Snapshot previous published state.** Before writing any
files to the docs repo, snapshot the previously published index so
stale files can be identified after the new set is written.

If `{docs_repo_path}/{release}/{feature}/validation-index.json`
exists, reject it if it is a symlink (including dangling) before
copying — the `cp` command follows symlinks by default and would
accept ownership from the linked target:

```bash
if [ -L "{docs_repo_path}/{release}/{feature}/validation-index.json" ]; then
  echo "Published index is a symlink — refusing to copy" >&2; exit 1
fi
```

**Validate the published index at its source before capturing.**
Validate the original published index in place — before `cp` —
to ensure it conforms to the published schema and is trustworthy
for later removal decisions:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" validate --published "{docs_repo_path}/{release}/{feature}/validation-index.json" || { echo "Published index validation failed — aborting" >&2; exit 1; }
```

If validation fails, **stop and report** — do not copy or proceed
with a malformed published index. Only after validation passes,
capture the snapshot:

```bash
cp "{docs_repo_path}/{release}/{feature}/validation-index.json" ".artifacts/design/{issue-key}/prev-published-index.json" || { echo "Snapshot copy failed" >&2; exit 1; }
```

If it does not exist but `{docs_repo_path}/{release}/{feature}/testplan.md`
exists (legacy single-testplan), write a minimal published snapshot:

```json
{
  "schema_version": "1.0",
  "primary_testplan": "testplan.md",
  "artifacts": [{"file": "testplan.md", "type": "testplan"}]
}
```

Save to `.artifacts/design/{issue-key}/prev-published-index.json`.

If neither exists, there is no previous set — skip the snapshot
and proceed with an empty previous set.

**Distinguish absent from failed.** When copying an existing
published index or building a legacy snapshot, check that the copy
or write succeeded. If a published `validation-index.json` or
legacy `testplan.md` exists at the source but the snapshot file
could not be created (I/O error, permission denied), **stop and
report** — do not proceed with an empty previous set when a prior
publication exists. An empty previous set is correct only when
no prior published state exists (first publish).

**Removal preflight (non-empty current set with previous snapshot):**
Before copying any artifacts or overwriting the published index,
identify proposed removals so the user can approve them first.
Transform the current local index to a candidate published index
under `.artifacts`:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{issue-key}/validation-index.json" ".artifacts/design/{issue-key}/candidate-published-index.json" --trusted-output-base "." || { echo "Transform failed — aborting" >&2; exit 1; }
```

Diff the previous snapshot against the candidate:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{issue-key}/prev-published-index.json" ".artifacts/design/{issue-key}/candidate-published-index.json" || { echo "Diff failed — aborting" >&2; exit 1; }
```

If the `removed` list is non-empty, present each removal with its full
published path `{release}/{feature}/{filename}` and require named
confirmation of each removal before proceeding.
An earlier explicit named-artifact approval (from a prior `/revise` or
`/publish` step that named these specific `{release}/{feature}/{filename}` paths) counts as confirmation
only if the artifact's published state has not changed since approval —
approval is consumed by the operation it authorized, and is not reusable
after an intervening synchronization, restoration, or content
replacement. When state continuity cannot be established, require fresh
confirmation. Generic update approval does not authorize removal. If the user declines, stop — preserve
published artifacts and metadata unchanged. Clean up the candidate file
after the preflight completes (it is not published directly).

If no previous snapshot was captured (first publish), skip this
preflight — first-publish has no removals.

**If the current set is empty** and a previous snapshot exists, this
is an empty-set retirement. Present the exact filenames from the
previous snapshot to the user and require named confirmation before
any docs-repo mutation occurs:

- For each artifact in the previous snapshot, show:
  `{release}/{feature}/{filename}`
- Show: `{release}/{feature}/validation-index.json` (if the previous
  publication included one)

Ask the user: **"The following published validation artifacts will
be removed. Confirm retirement, or restore the local artifact set
before proceeding."** The user must explicitly confirm removal of
these specific filenames. Generic publish approval is not sufficient.
If the user declines, stop — no docs-repo files are copied, staged,
or committed. Record the confirmation for Step 7 to execute.

### Step 5: Copy Design Document and Current Artifacts

All preflights have passed and any required confirmations have been
obtained. Before modifying the docs repo, verify ALL destination paths
first so a rejected publication leaves the checkout unchanged.

**Check all destinations before any copy:**

Verify the design document destination before creating directories:
- If any **existing** ancestor in the destination path between
  `{docs_repo_path}` and `design.md` is a symlink, stop and report —
  the destination could escape the docs checkout. Symlinks at or above
  `{docs_repo_path}` itself are permitted (the checkout root may
  be an alias).
- If `{docs_repo_path}/{release}/{feature}/design.md` itself is a
  symlink, stop and report.

Only after the ancestor check passes, create the feature directory:

```bash
mkdir -p "{docs_repo_path}/{release}/{feature}"
```

If the current set is non-empty (has validation artifacts), verify
each artifact destination before any copy:

For each entry in the current set, verify the local file exists.
A listed artifact whose local file is missing is an error — stop and
report it to the user. Do not proceed with partial publication.

Verify that no source file is a symlink. For each destination path,
check:
- If any ancestor in the destination path between `{docs_repo_path}`
  and the target file is a symlink, stop and report — the
  destination could escape the docs checkout. Symlinks at or above
  `{docs_repo_path}` itself are permitted (the checkout root may
  be an alias).
- If the destination itself is a symlink, stop and report.
- If the destination already exists and the filename is NOT in the
  previous validation set (from Step 4), stop and report — this
  would overwrite an unowned file (e.g., `clarifications.md` from
  PRD publication). Files that ARE in the previous set are owned
  updates and may be overwritten.

All destination checks passed. Now begin writing to the docs repo.

**Copy the design document:**

```bash
cp ".artifacts/design/{issue-key}/03-design.md" "{docs_repo_path}/{release}/{feature}/design.md"
```

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{release}/{feature}/design.md"`.

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/design.md"
```

**Copy validation artifacts:**

If the current set is empty (no validation artifacts), skip to Step 7.

Copy each artifact to the docs repo:

```bash
cp ".artifacts/design/{issue-key}/{local}" "{docs_repo_path}/{release}/{feature}/{published_as}"
```

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/{published_as}"
```

### Step 6: Publish the Validation Index

Transform and write the
published index for downstream discovery:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" transform ".artifacts/design/{issue-key}/validation-index.json" "{docs_repo_path}/{release}/{feature}/validation-index.json" --trusted-output-base "{docs_repo_path}" || { echo "Transform failed — aborting" >&2; exit 1; }
```

If the transform exits non-zero, **stop and report** — do not proceed
to stage the index. A failed transform may leave a stale index at the
destination; staging it would publish incorrect downstream metadata.

```bash
git -C "{docs_repo_path}" add "{release}/{feature}/validation-index.json"
```

### Step 7: Remove Stale Artifacts

Compute the change set by comparing the previous snapshot (Step 4)
against the current set. The comparison must use the new published
index when one was written in Step 6, or an empty artifact list
when the current set is empty.

**If the current set is non-empty** and a previous snapshot exists,
execute the removals that were already confirmed during the removal
preflight (Step 4). Re-diff using the final published index to
verify the removal set is unchanged:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" diff ".artifacts/design/{issue-key}/prev-published-index.json" "{docs_repo_path}/{release}/{feature}/validation-index.json" || { echo "Diff failed — aborting" >&2; exit 1; }
```

The `removed` list must match the preflight result. If the sets
differ (unexpected — would indicate a transform inconsistency),
stop and report before deleting anything. Do not re-prompt for
confirmation — the user already approved these specific filenames
in the preflight.

For each confirmed filename in `removed`:

```bash
git -C "{docs_repo_path}" rm -- "{release}/{feature}/{stale-filename}"
```

Do not remove files outside the feature directory or files not
listed in the previous set.

**If the current set is empty** and the previous set had artifacts,
execute the retirement using the confirmation obtained in Step 4's
empty-set preflight. If no such confirmation was recorded (the
preflight was bypassed or state changed since confirmation), stop
and restart the preflight before any docs-repo mutation — do not
prompt for confirmation after the design document has already been
copied. The `/revise` fallback to `/publish` must not bypass this
gate.

If the user confirms, validate the previous snapshot before removal:

```bash
python3 "$VALIDATION_INDEX_SCRIPT" validate --published ".artifacts/design/{issue-key}/prev-published-index.json"
```

If validation fails, **stop and report** — do not delete files based
on a malformed snapshot. If validation passes, remove each artifact
listed in the snapshot:

```bash
git -C "{docs_repo_path}" rm -- "{release}/{feature}/{previous-artifact-file}"
```

If the previous snapshot was built from a published
`validation-index.json` (not a legacy-only `testplan.md` snapshot),
also remove the index:

```bash
git -C "{docs_repo_path}" rm -- "{release}/{feature}/validation-index.json"
```

Do not attempt to remove `validation-index.json` for a legacy-only
snapshot — no index file exists to remove.

If no previous snapshot exists (first publish with no artifacts),
no removal is needed.

### Step 8: Commit

Commit with a message reflecting what was published:

```bash
# If validation artifacts were published:
git -C "{docs_repo_path}" commit -m "Add design document and validation artifacts for {issue-key}: {title}"

# If no validation artifacts (design-only):
git -C "{docs_repo_path}" commit -m "Add design document for {issue-key}: {title}"
```

### Step 9: Push and Create PR

Push the branch using the shared script (run from the docs repo).
Use the current HEAD of the docs repo (the Step 8 commit) to pin
the push to the exact committed state:

```bash
DOCS_HEAD=$(git -C "{docs_repo_path}" rev-parse HEAD)
(cd "{docs_repo_path}" && python3 "$PUBLISH_SCRIPT" push --remote {push-remote} --branch {branch-name} --expected-sha "$DOCS_HEAD")
```

The `--expected-sha` flag verifies that HEAD still matches the
Step 8 commit and pins the push refspec to that exact SHA, so
branch movement after the commit cannot publish uncommitted content.

Read the design document and identify specific areas that warrant reviewer
attention (AI-dependent):
- Open questions from Section 9 (list each by title)
- Sections with remaining TBD markers
- Key architectural decisions that have significant trade-offs

Prepare the PR description and save it to
`.artifacts/design/{issue-key}/08-pr-description.md`:

```markdown
## Design: {title}

**Jira:** {issue-link}
**PRD:** {link to PRD PR or file, if available}

### Summary
{2-3 sentence summary of the design approach}

### Requesting Review On
{Populate from the design document. If there are open questions, TBD
markers, or significant trade-offs, list each as a bullet. If none
exist, write "General review — no specific items flagged."}

### Documents
- `design.md` — technical design document
{For each published validation artifact, add a bullet using the
 file names from the published validation-index.json (Step 6):
- `{primary_testplan}` — acceptance test cases mapped to PRD requirements
- `{companion-file}` — {companion purpose}
If no validation artifacts were published, omit these bullets entirely.}

### How to Review
- Comment inline on specific sections
- Approve when the design accurately reflects a viable implementation approach
```

Use `upstream_repo` from `resolve-remotes` as `{owner}/{repo}`. Set
`{pr-title}` based on whether `{issue-key}` is a Jira
key: if yes, use `{issue-key}: Design - {title}`; otherwise use
`Design: {title}`.

Set `{head-ref}` to `{fork-owner}:{branch-name}` when `cross_repository=true`;
otherwise set it to `{branch-name}`.

First, check whether a PR already exists for this branch:

```bash
python3 "$PUBLISH_SCRIPT" check-existing --repo {owner}/{repo} --head {head-ref}
```

If exit code is 5, a PR already exists — skip to Step 10 and report its
URL. Parse the PR number from the returned JSON. If the command fails
(non-zero exit other than 5), stop and report the error. If exit code
is 0, create a new PR:

```bash
python3 "$PUBLISH_SCRIPT" create-pr \
  --repo {owner}/{repo} \
  --base {base-branch} \
  --head {head-ref} \
  --title "{pr-title}" \
  --body-file .artifacts/design/{issue-key}/08-pr-description.md \
  --draft
```

The script prints the PR URL on stdout. Parse the PR number from the URL path.

### Step 10: Save Metadata and Report

Save the core metadata using the shared script. If the primary
testplan was published, include `testplan_file_path` for backwards
compatibility with consumers that do not read `validation_artifacts`.
Derive the primary testplan filename from the published
`validation-index.json` written in Step 6 — read its
`primary_testplan` value (e.g., `testplan.md` for the default, or a
custom name if the index specifies one). For the legacy case where
no index was written, fall back to the literal `testplan.md`:

```bash
python3 "$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/design/{issue-key}/publish-metadata.json \
  release={release} \
  feature={feature} \
  design_file_path={release}/{feature}/design.md \
  testplan_file_path={release}/{feature}/{primary_testplan} \
  pr_number={pr-number} \
  branch={branch-name}
```

If no testplan was published, omit `testplan_file_path`:

```bash
python3 "$PUBLISH_SCRIPT" save-metadata \
  --file .artifacts/design/{issue-key}/publish-metadata.json \
  release={release} \
  feature={feature} \
  design_file_path={release}/{feature}/design.md \
  pr_number={pr-number} \
  branch={branch-name}
```

**Add the validation artifact list.** After `save-metadata` writes
the file, read it, add the `validation_artifacts` array, and write it
back. This list is the authoritative record of all published
validation artifacts:

Read `.artifacts/design/{issue-key}/publish-metadata.json`, parse as
JSON. Add a `validation_artifacts` key with the same array as the
published `validation-index.json` (using `file`, `type`, and for
companions, `purpose` and `audience`). Write the updated JSON back to
the same file.

Example resulting metadata:

```json
{
  "branch": "design/EDM-1471",
  "design_file_path": "v2.1/feature-slug/design.md",
  "feature": "feature-slug",
  "pr_number": "42",
  "release": "v2.1",
  "testplan_file_path": "v2.1/feature-slug/testplan.md",
  "validation_artifacts": [
    {"file": "testplan.md", "type": "testplan"},
    {"file": "hw-validation.md", "type": "companion", "purpose": "Hardware qualification", "audience": "Hardware QE"}
  ]
}
```

When no validation artifacts were published, omit the
`validation_artifacts` key entirely (legacy-only metadata).

**Report to the user:**

Present:
- PR URL
- Docs repo and branch name
- File location in the docs repo
- Next steps (share with reviewers, wait for comments, then use `/respond`)

## Output

- `.artifacts/config.json` (workspace-level config, created if it didn't exist)
- `.artifacts/design/{issue-key}/publish-metadata.json` (includes `validation_artifacts` when artifacts were published)
- Design document and validation artifacts committed and pushed to feature branch in the docs repo
- `validation-index.json` published to docs repo feature directory for downstream discovery
- Draft PR created against the docs repo
- `.artifacts/design/{issue-key}/08-pr-description.md`

## When This Phase Is Done

Report your results:
- PR URL and branch name
- Docs repo and file location
- Suggested next steps

Then **re-read the controller** (`controller.md`) for next-step guidance.
