---
name: respond
description: Fetch and address reviewer comments on the published handoff spec PR.
---

# Respond — Address Review Comments

Fetch reviewer comments from the GitHub PR, help the user understand and
respond to them, and apply any resulting handoff spec changes.

## Critical Rules

- **Never post comments without user approval.** Propose responses, then wait.
- **Separate content changes from clarifications.** Some comments need handoff spec edits; others just need a reply.
- **Preserve the review trail.** Don't delete or modify existing comments.
- **Allowed `gh` operations:**
  - **Read:** `gh pr view` (for PR discovery only — comment fetching is
    delegated to the shared script)
  - **Write:** delegated to `pr-comments.py reply` (do not call `gh api`
    or `gh pr comment` directly for review replies)
  - **Forbidden:** `gh pr close`, `gh pr merge`, `gh pr edit`, `gh pr ready`

## Shared Script

This skill delegates deterministic PR comment operations to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/pr-comments.py
```

The script provides subcommands: `fetch`, `reply`, and `log`. See the
script header for full usage.

## Process

### Step 1: Fetch PR Comments

Read `.artifacts/config.json` to get the docs repo path and
`.artifacts/ux-design/{issue-key}/publish-metadata.json` to get the PR
number and `{branch-name}`. If either file doesn't exist, tell the user
that `/publish` should be run first.

Determine `{source_repo_root}` with `git rev-parse --show-toplevel`. Normalize
`docs_repo_path` before using it: expand `~`, resolve a relative value against
`{source_repo_root}`, then use `Path.resolve()` to get an absolute path. This
also supports existing configs that stored the path relative to the source
repository. Use only the normalized absolute path in subsequent Git commands,
filesystem paths, and provenance targets.

Read `00-context.md` and compare the published handoff's discovery revision
with the current revision. If enrichment made the handoff stale, stop before
applying review feedback and recommend `/handoff` to regenerate it. Resume
`/respond` after the updated handoff is approved so reviewer feedback is applied
to the current design context.

Determine `{owner}/{repo}` from the config's `docs_repo_remote`.

Resolve `{AI_WORKFLOWS_ROOT}` as the git root of the ai-workflows install
(typically `git rev-parse --show-toplevel` from the workflow directory, or
`~/.ai-workflows` when symlinked). Keep the source repository as the process
CWD so artifact paths remain relative to its root. Then resolve the shared
script to an absolute path:

```bash
PR_COMMENTS_SCRIPT="{AI_WORKFLOWS_ROOT}/_shared/scripts/pr-comments.py"
```

Use `$PR_COMMENTS_SCRIPT` in all subsequent commands.

Fetch all comments using the shared script. The script fetches line-level
review comments, top-level comments, and reviews in a single call and outputs
a unified JSON array to stdout:

```bash
python3 "$PR_COMMENTS_SCRIPT" fetch --owner {owner} --repo {repo} --pr {pr-number} --responses-log .artifacts/ux-design/{issue-key}/responses.jsonl --include-review-threads
```

The `--responses-log` flag excludes comment IDs already addressed in prior
respond rounds. The `--include-review-threads` flag annotates line comments
with thread resolution status via GraphQL.

If no comments are found, tell the user and suggest checking back later.

### Step 2: Categorize Comments

| Category | Action |
|----------|--------|
| **Clarification request** | Draft a reply explaining the rationale |
| **Design alternative** | Evaluate the suggestion, propose a response |
| **Factual correction** | Update the handoff spec and acknowledge |
| **Scope question** | Draft a reply; may need `/revise` |
| **New requirement** | Flag for user decision — update or defer |
| **Approval / positive** | Acknowledge |

### Step 3: Propose Responses

Present each comment with a proposed response:

```markdown
## Review Comment Summary

### Comment 1 — {reviewer}
> {quoted comment text}

**Category:** {category}
**Proposed response:** {your suggested reply}
**Handoff change needed:** {Yes/No — description if yes}
```

Wait for the user to approve, modify, or reject each response.

### Step 4: Apply Approved Changes

**If "Handoff change needed: Yes":**

Update `.artifacts/ux-design/{issue-key}/05-handoff.md` with approved changes.

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

Update the docs repo copy:

Before switching branches, confirm the docs repo worktree and index are clean:

```bash
git -C "{docs_repo_path}" status --porcelain
```

If the output is not empty, stop before checkout and ask the researcher to
resolve the changes. Leave the worktree and index untouched.

```bash
git -C "{docs_repo_path}" checkout {branch-name}
```

```bash
git -C "{docs_repo_path}" pull --ff-only
```

```bash
cp ".artifacts/ux-design/{issue-key}/05-handoff.md" "{docs_repo_path}/{handoff_file_path}"
```

**Update screenshot assets if changed.** Read
`.artifacts/ux-design/{issue-key}/screenshot-manifest.json` and
`.artifacts/ux-design/{issue-key}/publish-metadata.json`. Derive the
handoff directory from the published handoff path:

```bash
handoff_dir=$(dirname "{handoff_file_path}")
```

**Skip screenshot handling on initial text-only publishes** — when the
authoring manifest does not exist or contains no screenshots, **and**
`screenshot_storage` is `none`, **and** `publish-metadata.json` has no
prior `screenshot_assets`. Do not touch asset paths.

**Reconcile previous assets on updates.** When `publish-metadata.json`
records prior `screenshot_assets`, always check for removals even if the
current authoring manifest is empty or absent (transition to text-only).
Use previous metadata for cleanup; do not overwrite metadata with empty
values before using it for reconciliation.

Otherwise, apply the same validation and storage gates as `/publish`:

1. **Validate containment** of every planned destination path before
   copying, using the same filename-pattern and symlink checks as
   `/publish` Step 6.

2. **Verify current local bytes** before change detection. For each
   entry in the authoring manifest, compute the SHA-256 of the actual
   local file at `.artifacts/.../screenshots/{filename}` and confirm it
   matches the manifest's `sha256`. If they differ, the manifest is
   stale — stop and ask the researcher to re-curate or update the
   manifest before proceeding.

   **Detect changes, additions, and removals:**
   - For each verified manifest entry, compare its `sha256` against the
     corresponding `screenshot_assets` entry in `publish-metadata.json`.
     Changed checksum → updated image.
   - Manifest entries absent from `publish-metadata.json` → newly added.
   - `publish-metadata.json` entries absent from the current manifest →
     removed.

3. **Handle removals** (`lfs` or `git` mode): `git rm` only files
   still tracked (skip if already removed by a prior committed run):

   ```bash
   git -C "{docs_repo_path}" rm -- "{handoff_dir}/screenshots/{removed_filename}"
   ```

   Remove the entry from the published `screenshot-manifest.json`. If
   all screenshots are removed and the consumer manifest is still
   tracked, remove it:

   ```bash
   git -C "{docs_repo_path}" rm -- "{handoff_dir}/screenshot-manifest.json"
   ```

   Track each removed filename in a `removed_filenames` array.

4. **Handle additions and updates** (`lfs` or `git` mode): copy each
   changed or new file individually and verify its SHA-256 matches the
   authoring manifest:

   ```bash
   cp ".artifacts/ux-design/{issue-key}/screenshots/{filename}" \
      "{docs_repo_path}/{handoff_dir}/screenshots/{filename}"
   ```

   Track each copied filename in a `copied_filenames` array.

5. **External mode — rewrite ALL current image references.** After
   copying the freshly authored handoff over the published copy, the
   published document contains local authoring refs (`screenshots/...`)
   that must all be rewritten to external URLs:

   - **Unchanged images** (current manifest `sha256` matches
     `publish-metadata.json` `screenshot_assets` for that ID): reuse the
     existing `published_path` URL from `publish-metadata.json`. Verify
     the URL is still well-formed and immutable.
   - **Changed or new images**: require the researcher to provide new
     immutable, revision-bound URLs. Retrieve image bytes from each URL,
     compute SHA-256, and verify against the authoring manifest. Stop on
     mismatch.
   - **Removed images**: delete the embed and Screenshot Index entry.
     External hosted bytes are not deleted by this workflow.

   Rewrite **every** current `![alt](ref)` embed **and** Screenshot
   Index `Ref` column in the published handoff with the correct external
   URL. This ensures a text-only edit with unchanged images preserves
   all external references. Preserve authoring references in
   `05-handoff.md` separately.

   **Final-image removal in external mode.** If all images are removed,
   `git rm` the consumer manifest (`{handoff_dir}/screenshot-manifest.json`)
   and pass `MANIFEST_REMOVED="true"` to the staging recipe. This applies
   to all storage modes, not only `lfs`/`git`.

6. **Regenerate the published consumer-facing manifest** at
   `{handoff_dir}/screenshot-manifest.json` with the current set of
   published screenshots (no private paths). If all screenshots were
   removed (any storage mode), skip — the manifest was removed above.

7. **Update `publish-metadata.json`** `screenshot_assets` with the new
   checksums, paths, and entry set. Do not write metadata until the
   commit and push succeed (Step below).

**Capture provenance and render footer** after all screenshot updates are
applied to the handoff, so the footer reflects the final content:

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`, `PHASE=respond`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`,
`TARGET_FILE="{docs_repo_path}/{handoff_file_path}"`.

**Build owned-path allowlist, stage, and commit.** Read and follow
`../../_shared/recipes/screenshot-publish-stage.md` with:
- `DOCS_REPO_PATH="{docs_repo_path}"`
- `HANDOFF_FILE_PATH="{handoff_file_path}"`
- `HANDOFF_DIR="{handoff_dir}"`
- `COPIED_FILENAMES` = the `copied_filenames` array built above
- `REMOVED_FILENAMES` = the `removed_filenames` array built above
- `MANIFEST_WRITTEN="true"` if the consumer manifest was regenerated
- `MANIFEST_REMOVED="true"` if the consumer manifest was removed (all screenshots deleted)
- `COMMIT_MESSAGE="UX design {issue-key}: address review feedback"`

Follow the pending attempt protocol in
`../../_shared/recipes/screenshot-publish-stage.md` §4.
Push only when unpushed commits exist. Before pushing, verify the
local branch HEAD matches the commit SHA from the staging recipe;
refuse if unexpected ahead commits appear. If a prior invocation
committed but the push failed, this retries without re-running the
removal/copy steps.

```bash
git -C "{docs_repo_path}" push
```

Only update `publish-metadata.json` `screenshot_assets` after the push
succeeds. If push failed, preserve previous metadata unchanged. Set
`screenshot_storage` to `none` only after successful push when all
screenshots have been removed.
If push succeeded but metadata write fails, recover by re-reading
the branch HEAD and screenshot state without creating a new commit.

**If "Handoff change needed: No":**

Skip the git operations above — the handoff spec is unchanged. The response
is comment-only (clarification, acknowledgment, or pushback).

**In both cases:**

Write each approved reply to
`.artifacts/ux-design/{issue-key}/tmp-reply.md` using the host's file-writing
capability. Do not use a shell heredoc because reply content can contain the
delimiter string.

Route each comment based on its `type` field from the fetch output.

For a `line_comment`, reply in-thread using the comment's `id`:

```bash
python3 "$PR_COMMENTS_SCRIPT" reply --owner {owner} --repo {repo} --pr {pr-number} --body-file .artifacts/ux-design/{issue-key}/tmp-reply.md --comment-id {id}
```

For a `review` or `top_level` comment, post a top-level reply:

```bash
python3 "$PR_COMMENTS_SCRIPT" reply --owner {owner} --repo {repo} --pr {pr-number} --body-file .artifacts/ux-design/{issue-key}/tmp-reply.md
```

If the reply command fails, report the error and continue to the next comment
without logging the failed reply.

After each successful reply, record its `id` so later respond rounds skip it:

```bash
python3 "$PR_COMMENTS_SCRIPT" log --responses-log .artifacts/ux-design/{issue-key}/responses.jsonl --comment-id {id}
```

If logging fails, stop before posting another reply to avoid duplicate replies
on the next respond round.

Delete the temporary reply file after a successful post and log:

```bash
rm .artifacts/ux-design/{issue-key}/tmp-reply.md
```

### Step 5: Report to User

Summarize:
- How many comments were addressed
- How many handoff spec changes were made
- Whether any comments remain unresolved

## Output

- PR comments posted (with user approval)
- `.artifacts/ux-design/{issue-key}/05-handoff.md` (updated if needed)

## When This Phase Is Done

Report your results:
- Comments addressed and responses posted
- Handoff spec changes made
- Outstanding items

Then **re-read the controller** (`controller.md`) for next-step guidance.
