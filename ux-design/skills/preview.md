---
name: preview
description: Build a static review preview bundle and publish it for human browser inspection.
---

# Preview — Static Review Bundle

Build a self-contained static preview of the current prototype for human
review in a browser. The preview is published to the project's configured
Pages site so reviewers can inspect the design alongside the handoff spec.

The preview is for human review only. It is never consumed by downstream
workflows or agents. The structured text handoff (`05-handoff.md`) remains
the authoritative downstream contract.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/03-prototype/prototype-notes.md` for
the prototype mode (standalone or workspace), iteration number, and design
decisions. If it does not exist, stop and recommend `/prototype` first.

Read `00-context.md` for the current prototype iteration and discovery
revision. The preview must be built from a prototype that has been
reviewed against the current context.

## Artifact Path Safety

Run `git rev-parse --show-toplevel` and store the result as
`source_repo_root`. If it fails, stop and ask the researcher to open the
source-repository workspace.

Before using `{issue-key}` in a path, require it to match
`[A-Za-z0-9][A-Za-z0-9._-]*` and reject `.` or `..`. Treat it as one
path component.

## Process

### Step 1: Validate the Prototype for Static Preview

Determine the prototype mode from `prototype-notes.md` (`standalone` or
`workspace`).

Resolve `{AI_WORKFLOWS_ROOT}` as the root of the ai-workflows install,
following the same convention as other skills in this workflow (e.g.,
`respond.md`). This is typically `~/.ai-workflows` when installed via
symlinks, or the root of the ai-workflows repository when running from
source. Do **not** use `$0`, `$BASH_SOURCE`, or run
`git rev-parse --show-toplevel` against the **source repository** — that
resolves to the wrong root (the project repo, not the ai-workflows
install).

```text
UX_SCRIPTS="{AI_WORKFLOWS_ROOT}/ux-design/scripts"
```

Run validation:

```bash
python3 "${UX_SCRIPTS}/preview-bundle.py" validate \
  --prototype-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/03-prototype" \
  --mode {standalone|workspace}
```

Parse the JSON output. Check the `valid` field:

**If `valid` is `false` with reason `no_static_content`:**
The prototype requires a build step or live development server and
cannot be packaged as a static preview.

Before falling back, attempt the project's own static build:

1. Check for build scripts in the prototype's `code/` directory
   (`package.json` scripts, `Makefile`, etc.)
2. If a build command exists, run it and re-validate the output

If no build is available or the build fails:
**Screenshot fallback** — Capture screenshots of the key flows and
states, then attach them to the handoff PR for reviewer reference.
The screenshots must be actually accessible to reviewers — attached
through the platform's attachment mechanism or uploaded to an
approved location.

If the researcher chooses screenshots, record this decision in
`preview-metadata.json` with `deploy_status: screenshot-fallback`. Do not
proceed to Step 2. The screenshots must be actually accessible to
reviewers — either attached to the PR through the platform's attachment
mechanism or uploaded to an approved location. Do not create local
markdown image references to files reviewers cannot access.

**If `valid` is `false` with reason `backend_dependencies`:**
Present the findings and let the researcher decide:

> The prototype has {N} backend dependency indicator(s) that may prevent
> static preview. Findings:
> {list each finding with file and line}
>
> Options:
> 1. **Proceed anyway** — if these are false positives or the mocked data
>    is sufficient for review purposes
> 2. **Screenshot fallback** — capture screenshots instead
> 3. **Return to /prototype** — add controlled mocks to replace the
>    backend calls

**If `valid` is `true`:** Proceed to Step 2.

**Important:** Validation is an advisory lint check, not proof of
correct rendering. The absence of backend-dependency patterns does
not guarantee the prototype renders correctly in a browser. Visual
verification occurs in Step 4 after deployment.

### Step 2: Build the Preview Bundle

```bash
python3 "${UX_SCRIPTS}/preview-bundle.py" package \
  --prototype-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/03-prototype" \
  --output-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/preview-bundle" \
  --issue-key "{issue-key}" \
  --revision "iteration-{N}" \
  --mode {standalone|workspace}
```

Parse the JSON output for `bundle_dir`, `entry_point`, and `file_count`.

Record the build details:

- Entry point path
- Number of files in the bundle
- Which components are mocked (from the manifest)
- What is unchanged source vs prototype content

### Step 3: Resolve the Deployment Interface

Read `{source_repo_root}/.artifacts/config.json` for the shared
configuration. The **default deployment target** is the docs repository
already configured via `docs_repo_remote` and `docs_repo_path` — the
same repository used by `/publish` for handoff PRs.

The preview publisher is a single command interface at:

```text
PREVIEW_PUBLISH_SCRIPT="{AI_WORKFLOWS_ROOT}/ux-design/scripts/preview-publish.py"
```

Required inputs for the publisher:
- `--bundle-dir` — the packaged bundle from Step 2
- `--site-dir` — the assembled site directory (typically inside the
  docs repo or a staging location)
- `--pr-url` — the handoff PR URL (from `publish-metadata.json`);
  deployment requires a real PR identity, not just a local build
- `--target-repo` — the `{owner}/{repo}` from `docs_repo_remote`

**When `docs_repo_remote` is configured (default):**

Use it as the deployment target. The `{owner}/{repo}` is derived from
`docs_repo_remote` the same way as in `/publish`. Do not guess a Pages
URL from the repository name.

The project owner may optionally override the deployment target by
setting `preview_site_url` in `.artifacts/config.json`. This override
must be explicitly approved — do not construct URLs from repository
naming conventions.

If `publish-metadata.json` does not exist (no handoff PR yet), record
`deploy_status: awaiting-setup` — deployment requires a real PR
identity. Present the researcher with the bundle location and
recommend `/publish` first.

**When `docs_repo_remote` is not configured:**

Record `deploy_status: awaiting-setup` in preview-metadata.json. Present
the researcher with:

> No docs repository is configured for this project.
>
> The preview bundle is packaged and ready at:
> `{bundle_dir}`
>
> To enable preview deployment, run `/publish` first to configure the
> docs repository, or set `docs_repo_remote` in `.artifacts/config.json`.

Do not proceed to Step 4. Skip to Step 5.

### Step 4: Deploy and Verify the Preview

When the deployment interface is available and a handoff PR exists:

1. **Confirm with the researcher** before deploying:
   > Deploy preview bundle to {target-repo} at previews/{issue-key}/{revision}/?
   > PR: {pr-url}
   > Target repo: {owner}/{repo}

2. **Invoke the publisher:**

   ```bash
   python3 "$PREVIEW_PUBLISH_SCRIPT" publish \
     --bundle-dir "{bundle_dir}/previews/{issue-key}/{revision}" \
     --site-dir "{site_staging_dir}" \
     --pr-url "{pr-url}" \
     --target-repo "{owner}/{repo}"
   ```

   Parse the JSON receipt. Check `digest_match` — if `false`, the
   content was corrupted during publish. Record `deploy-failed`.

3. **Verify the published content** using the publisher's verify
   command with per-file hash checking:

   ```bash
   python3 "$PREVIEW_PUBLISH_SCRIPT" verify \
     --site-dir "{site_staging_dir}" \
     --issue-key "{issue-key}" \
     --revision "{revision}" \
     --expected-digest "{content_sha256_from_manifest}"
   ```

   Parse the JSON result. Check `verified` — if `false`, report
   per-file mismatches. Do not claim the preview is published until
   verification passes. A receipt alone is not verification — all
   expected files must match their per-file hashes.

4. **Check site preservation:**
   The publisher verifies existing content is preserved. If the
   receipt reports a preservation violation, record `deploy-failed`.

If any step fails, record `deploy_status: deploy-failed` with the
specific error and offer the screenshot fallback.

### Step 5: Record Preview Metadata

Write `.artifacts/ux-design/{issue-key}/preview-metadata.json`:

```json
{
  "issue_key": "{issue-key}",
  "revision": "iteration-{N}",
  "prototype_mode": "{standalone|workspace}",
  "bundle_path": ".artifacts/ux-design/{issue-key}/preview-bundle/previews/{issue-key}/iteration-{N}",
  "entry_point": "{entry-point}",
  "deploy_status": "{published|awaiting-setup|awaiting-upload|deploy-failed|screenshot-fallback|stale}",
  "content_sha256": "{digest-from-manifest-or-null}",
  "site_url": "{verified-url-or-null}",
  "target_repo": "{owner/repo-from-docs_repo_remote-or-null}",
  "pr_url": "{handoff-pr-url-or-null}",
  "mocked_components": [],
  "timestamp": "{ISO-8601}"
}
```

### Step 6: Update the Handoff PR

If `publish-metadata.json` exists (the handoff PR is open), add the
preview link to the PR:

For a published preview:
> **Review Preview:** [{verified-url}]({verified-url})
> Built from prototype iteration {N} ({mode} mode).
> Entry point: `{entry-point}`

For screenshot fallback:
> **Review Screenshots:** Screenshots of key flows are attached to this PR.
> Built from prototype iteration {N} ({mode} mode).

For awaiting-setup:
> **Preview Bundle Ready:** The static preview bundle is packaged but
> deployment is not yet configured. See preview-metadata.json for details.

For awaiting-upload:
> **Preview Bundle Ready:** The static preview bundle is packaged and
> deployment is configured, but the bundle has not been uploaded to the
> deploy target. See preview-metadata.json for details.

For stale:
> **Preview Status: Stale** — The handoff spec has been updated since
> the preview was last published. Current revision: iteration-{N},
> deployed revision: {deployed-revision}. Run `/preview` to rebuild.

## Output

- `.artifacts/ux-design/{issue-key}/preview-bundle/` — packaged static
  bundle with `preview-manifest.json`
- `.artifacts/ux-design/{issue-key}/preview-metadata.json` — deployment
  status and verified URLs

## When This Phase Is Done

Present the preview status to the researcher:

- Bundle location and entry point
- Deployment status (published URL, awaiting setup, awaiting upload, or screenshot fallback)
- Mocked components inventory
- Whether the handoff PR was updated with the preview link

Then **re-read the controller** (`controller.md`) for next-step guidance.
