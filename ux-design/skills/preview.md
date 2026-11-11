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

Resolve the preview-bundle script relative to the workflow's installed
location. From any skill file in `ux-design/skills/`:

```text
UX_SCRIPTS="$(cd "$(dirname "$(readlink -f "$0")")/../../ux-design/scripts" 2>/dev/null && pwd)"
```

If running in a context where `$0` is not resolvable (e.g., from a
markdown skill file), locate the ai-workflows install root and resolve:

```text
AI_WORKFLOWS_ROOT="$(git -C "$(dirname "$(readlink -f "$0")")" rev-parse --show-toplevel 2>/dev/null)"
UX_SCRIPTS="${AI_WORKFLOWS_ROOT}/ux-design/scripts"
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

Read `{source_repo_root}/.artifacts/config.json` for preview site
configuration:

```json
{
  "preview_site_url": "https://example.com/site",
  "preview_artifact_method": "workflow_artifact|s3|manual",
  "preview_deploy_repo": "org/deploy-repo",
  "preview_deploy_workflow": "deploy-preview.yml",
  "preview_deploy_inputs": {
    "artifact_name": "preview-bundle",
    "namespace": "previews/{issue-key}/{revision}"
  }
}
```

**When preview configuration is not present:**

Record `deploy_status: awaiting-setup` in preview-metadata.json. Present
the researcher with:

> No preview deployment is configured for this project.
>
> The preview bundle is packaged and ready at:
> `{bundle_dir}`
>
> To enable preview deployment, the project owner must configure:
>
> 1. `preview_site_url` — the actual configured site URL (do not guess
>    from repository name or assume `*.github.io`)
> 2. `preview_artifact_method` — how the bundle reaches the deploy job
> 3. `preview_deploy_repo` and `preview_deploy_workflow` — the
>    deployment target
>
> See the project's deployment documentation for the supported interface.

Do not proceed to Step 4. Skip to Step 5.

**When configuration exists but `preview_site_url` is missing:**

Stop. The site URL must come from project configuration or explicit
researcher input, not from repository naming conventions.

### Step 4: Deploy and Verify the Preview

When the deployment interface is fully configured:

1. **Confirm with the researcher** before deploying:
   > Deploy preview bundle to {preview_site_url}/previews/{issue-key}/{revision}/?
   > Repository: {preview_deploy_repo}
   > Workflow: {preview_deploy_workflow}

2. **Transport the bundle** to the location the deploy job can access.
   The transport method depends on `preview_artifact_method`:
   - `workflow_artifact` — upload via `gh run` artifact mechanism
   - `s3` — upload to the configured S3 path
   - `manual` — instruct the researcher to transfer the bundle

   A local file path cannot be passed as a remote workflow input.
   The deployment job must receive the actual bundle content, not a
   path on the author's machine.

3. **Invoke the deployment** using the project's documented interface.
   Pass the exact inputs specified in `preview_deploy_inputs`. Do not
   invent workflow input names or guess namespace formats.

4. **Wait for deployment receipt:**
   - Check the workflow/deployment run status until completion
   - Record the run ID and completion status

5. **Verify the published preview:**
   - Request the entry point URL from the configured `preview_site_url`
     plus the namespace path
   - Verify HTTP 200 with content matching the bundle's entry point
   - Verify at least one CSS/JS asset loads (not a 404)
   - Compare the served content against the bundle's `content_sha256`
     digest from the manifest

   Do not claim the preview is published until ALL verifications pass.
   A constructed URL alone is not proof. An HTTP 200 that matches old
   content is not proof — compare the content digest.

6. **Check site preservation:**
   If other previews or documentation exist on the site, verify they
   are still accessible after deployment. The deployment must preserve
   existing content, not replace the entire site.

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
  "target_repo": "{owner/repo-or-null}",
  "deploy_workflow": "{workflow-or-null}",
  "deploy_run_id": "{run-id-or-null}",
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
