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

Resolve the preview-bundle script to an absolute path relative to this
workflow's installed location:

```bash
UX_SCRIPTS="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]:-$0}")")/../scripts" 2>/dev/null && pwd)"
```

If running from a symlinked install, resolve the script location from the
workflow root. The script is at `ux-design/scripts/preview-bundle.py`
relative to the ai-workflows install root.

Run validation:

```bash
python3 "${UX_SCRIPTS}/preview-bundle.py" validate \
  --prototype-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/03-prototype" \
  --mode {standalone|workspace}
```

Parse the JSON output. Check the `valid` field:

**If `valid` is `false` with reason `no_static_content`:**
The prototype has no pre-built static HTML. For workspace prototypes this
means the app requires a build step or a live dev server. Stop and present
the screenshot fallback:

> The prototype requires a live development server or build step and
> cannot be packaged as a static preview. Options:
>
> 1. **Screenshots** — Capture screenshots of the key flows and states,
>    then attach them to the handoff PR for reviewer reference.
> 2. **Running instance** — Provide a running instance URL if one is
>    available for the reviewer.
>
> Which approach should we use?

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
configuration. The config uses the existing shared config pattern:

```json
{
  "docs_repo_path": "/path/to/docs",
  "docs_repo_remote": "git@github.com:org/docs.git",
  "preview_pages_repo": "org/preview-site",
  "preview_deploy_workflow": "deploy-preview.yml",
  "preview_deploy_input": "bundle_path",
  "preview_site_url": "https://org.github.io/preview-site",
  "preview_path_prefix": "previews"
}
```

**Default behavior:** When `preview_pages_repo` is not configured, derive
the Pages site from the configured `docs_repo_remote`. Parse `{owner}`
and `{repo}` from the remote URL and propose
`https://{owner}.github.io/{repo}/previews/{issue-key}/{revision}/` as
the preview URL namespace.

**Explicit override:** When `preview_pages_repo` is configured, use that
repository as the deployment target instead.

**Resolve the deployment workflow:** Check whether the target repository
has a deployment workflow matching `preview_deploy_workflow` (or a
conventional name like `deploy-preview.yml`, `pages.yml`, or
`deploy.yml`). The workflow must accept the bundle path and preview
namespace as inputs.

If no deployment interface is found, present the researcher with options:

> No preview deployment workflow is configured for {target_repo}.
> Options:
>
> 1. **Configure deployment** — Provide the workflow filename and input
>    parameters for the target repository's deployment mechanism.
>    The preview bundle is ready at:
>    `{bundle_dir}`
> 2. **Screenshot fallback** — Capture screenshots of the key flows
>    instead of deploying a live preview.
>
> The bundle is packaged and ready for deployment once a workflow is
> configured. Preview URL namespace:
> `{site_url}/previews/{issue-key}/{revision}/`

If the researcher provides deployment configuration, save it to
`config.json` following the shared config pattern.

### Step 4: Deploy the Preview

When the deployment interface is resolved and confirmed:

1. **Confirm with the researcher** before deploying:
   > Deploy preview bundle to {target_url}?
   > Repository: {target_repo}
   > Workflow: {deploy_workflow}
   > Namespace: previews/{issue-key}/{revision}/

2. **Invoke the deployment workflow** using the resolved interface.
   The exact invocation depends on the project's deployment mechanism.
   For a GitHub Actions workflow dispatch:

   ```bash
   gh workflow run "{deploy_workflow}" \
     --repo "{preview_pages_repo}" \
     -f "{deploy_input}={bundle_path}" \
     -f "namespace=previews/{issue-key}/{revision}" \
     -f "issue_key={issue-key}"
   ```

   For other mechanisms, follow the project's documented procedure.

3. **Wait for deployment** and verify the result:
   - Check workflow run status
   - Verify the entry point URL returns HTTP 200
   - Verify at least one asset loads correctly
   - Record the verified URL

   Do not claim the preview is published until the URL is verified.
   If deployment fails, report the error and offer the screenshot
   fallback.

4. If deployment verification succeeds, record the verified URL. If it
   fails, record the failure and offer alternatives.

### Step 5: Record Preview Metadata

Write `.artifacts/ux-design/{issue-key}/preview-metadata.json`:

```json
{
  "issue_key": "{issue-key}",
  "revision": "iteration-{N}",
  "prototype_mode": "{standalone|workspace}",
  "bundle_path": ".artifacts/ux-design/{issue-key}/preview-bundle/previews/{issue-key}/iteration-{N}",
  "entry_point": "{entry-point}",
  "deploy_status": "{published|awaiting-setup|screenshot-fallback}",
  "site_url": "{verified-url-or-null}",
  "target_repo": "{owner/repo-or-null}",
  "deploy_workflow": "{workflow-or-null}",
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

## Output

- `.artifacts/ux-design/{issue-key}/preview-bundle/` — packaged static
  bundle with `preview-manifest.json`
- `.artifacts/ux-design/{issue-key}/preview-metadata.json` — deployment
  status and verified URLs

## When This Phase Is Done

Present the preview status to the researcher:
- Bundle location and entry point
- Deployment status (published URL, awaiting setup, or screenshot fallback)
- Mocked components inventory
- Whether the handoff PR was updated with the preview link

Then **re-read the controller** (`controller.md`) for next-step guidance.
