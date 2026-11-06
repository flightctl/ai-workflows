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

If the authoring manifest does not exist or contains no screenshots, and
`screenshot_storage` is `none`, skip screenshot handling entirely — do not
touch asset paths.

Otherwise, apply the same validation and storage gates as `/publish`:

1. **Validate containment** of every planned destination path before
   copying, using the same filename-pattern and symlink checks as
   `/publish` Step 4.

2. **Detect changes, additions, and removals:**
   - For each entry in the current authoring manifest, compare its
     `sha256` against the corresponding `screenshot_assets` entry in
     `publish-metadata.json`. Changed checksum → updated image.
   - Manifest entries absent from `publish-metadata.json` → newly added.
   - `publish-metadata.json` entries absent from the current manifest →
     removed.

3. **Handle removals** (`lfs` or `git` mode): remove the deleted file
   from the docs repo and stage the removal:

   ```bash
   git -C "{docs_repo_path}" rm -- "{handoff_dir}/screenshots/{removed_filename}"
   ```

   Remove the entry from the published `screenshot-manifest.json`.

4. **Handle additions and updates** (`lfs` or `git` mode): copy each
   changed or new file individually and verify its SHA-256 matches the
   authoring manifest:

   ```bash
   cp ".artifacts/ux-design/{issue-key}/screenshots/{filename}" \
      "{docs_repo_path}/{handoff_dir}/screenshots/{filename}"
   ```

5. **External mode:** For changed or added screenshots, require the
   researcher to provide new immutable, revision-bound URLs. Rewrite
   **both** the inline `![alt](ref)` embeds **and** the Screenshot Index
   entries in the published handoff with the new URLs. For removals,
   delete the embed and index entry. Preserve authoring references in
   `05-handoff.md` separately.

6. **Regenerate the published consumer-facing manifest** at
   `{handoff_dir}/screenshot-manifest.json` with the current set of
   published screenshots (no private paths).

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

**Stage only owned files by explicit allowlist:**

```bash
git -C "{docs_repo_path}" add -- "{handoff_file_path}"
git -C "{docs_repo_path}" add -- "{handoff_dir}/screenshot-manifest.json"
# For each changed/added {filename}:
git -C "{docs_repo_path}" add -- "{handoff_dir}/screenshots/{filename}"
```

If no owned files changed (exit 0 from `git diff --cached --quiet` on
the allowlist), skip the commit. If changes exist:

```bash
git -C "{docs_repo_path}" commit --only \
  -m "UX design {issue-key}: address review feedback" \
  -- "{handoff_file_path}" "{handoff_dir}/screenshot-manifest.json" \
     "{handoff_dir}/screenshots/{file1}" ...
```

Only update `publish-metadata.json` `screenshot_assets` after the commit
and push succeed.

```bash
git -C "{docs_repo_path}" push
```

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
