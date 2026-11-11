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
the prototype mode (standalone or workspace), iteration number, design
decisions, and static review notes (build command, entry point, mocked
components). If it does not exist, stop and recommend `/prototype` first.

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

Read the **Static Review Notes** section of `prototype-notes.md` for:
- **Build command** — recorded build command for static export
- **Content root** — explicit content directory (relative to 03-prototype)
- **Entry point** — explicit HTML entry point filename

Run validation (pass `--content-root` and `--entry-point` when the notes
record them):

```bash
python3 "${UX_SCRIPTS}/preview-bundle.py" validate \
  --prototype-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/03-prototype" \
  --mode {standalone|workspace} \
  [--content-root "{content_root}"] \
  [--entry-point "{entry_point}"]
```

The validator exits with code 2 when validation produces a `valid: false`
result.  This is a normal validation outcome, not a tool error.  Parse the
JSON output from stdout regardless of exit code (exit 0 = valid,
exit 2 = invalid with JSON report, exit 1 = argument error).

Check the `valid` field and `reason`:

**If `valid` is `false` with reason `no_static_content`:**
The prototype requires a build step or live development server and
cannot be packaged as a static preview.

Before falling back, attempt the project's recorded or discovered build:

1. If `prototype-notes.md` records a **Build command**, run it first
2. Otherwise check for build scripts in the prototype's `code/` directory
   (`package.json` scripts, `Makefile`, etc.)
3. If a build command exists, run it and re-validate the output

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

**If `valid` is `false` with reason `no_entry_point`:**
The content directory exists but has no HTML entry point. Ask the
researcher for the entry point filename and re-run with `--entry-point`,
or offer the screenshot fallback.

**If `valid` is `true`:** Proceed to Step 2.

**Important:** Validation is an advisory lint check, not proof of
correct rendering. The absence of backend-dependency patterns does
not guarantee the prototype renders correctly in a browser. Visual
verification occurs in Step 4 after deployment.

### Step 2: Build the Preview Bundle

When repeating `/preview` for the same iteration (e.g. after a build
fix), choose a fresh revision identifier (`iteration-{N}-r{K}`) — the
bundler rejects an existing revision to prevent destructive overwrites.
Record the actual returned revision and bundle path.

```bash
python3 "${UX_SCRIPTS}/preview-bundle.py" package \
  --prototype-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/03-prototype" \
  --output-dir "{source_repo_root}/.artifacts/ux-design/{issue-key}/preview-bundle" \
  --issue-key "{issue-key}" \
  --revision "iteration-{N}" \
  --mode {standalone|workspace} \
  [--content-root "{content_root}"] \
  [--entry-point "{entry_point}"]
```

Parse the JSON output for `bundle_dir`, `entry_point`, `file_count`, and
`content_sha256`.  The `content_sha256` is required for Step 4.

Record the build details:

- Entry point path
- Number of files in the bundle
- Which components are mocked (from the manifest)
- What is unchanged source vs prototype content

### Step 3: Resolve the Deployment Interface

Read `{source_repo_root}/.artifacts/config.json` for the shared
configuration.

The preview publisher wrapper is at:

```text
PREVIEW_PUBLISH="{AI_WORKFLOWS_ROOT}/ux-design/scripts/preview-publish.py"
```

Read `publish-metadata.json` for the handoff PR identity:
- `pr_number` — the PR number (required for publication namespace)
- `branch` — the PR branch

If `publish-metadata.json` does not exist, record
`deploy_status: awaiting-setup` — publication requires a real PR
identity. Present the bundle location and recommend `/publish` first.
Do not proceed to Step 4.

**Resolve the target repository:**

The **default target** is `docs_repo_remote` from `.artifacts/config.json`
(the same docs repository used by `/publish`). The project owner may
override this with `preview_target_repo` in `.artifacts/config.json` —
this is a separate repo override, distinct from any site URL.

Derive `{pr_repo}` from `docs_repo_remote` (the PR's repository) and
`{target_repo}` from `preview_target_repo` if set, otherwise from
`docs_repo_remote`.

If neither is configured, record `deploy_status: awaiting-setup`. Do
not proceed to Step 4.

**Resolve the deploy command and site URL:**

Check `.artifacts/config.json` for `preview_deploy_command` — a path
to a project-owned executable that owns byte transport, whole-site
assembly (preserving docs and other PRs), and deployment. The command
receives four positional arguments:
`<bundle-dir> <namespace> <content-sha256> <site-base-url>` and must
print a JSON receipt to stdout with at minimum
`{"status": "published", "url": "...", "content_sha256": "..."}`.

The command must not return until the namespace and all assets are
served at the site URL.  The wrapper verifies content immediately.

Check `.artifacts/config.json` for `preview_site_url` — the approved
HTTPS base URL where previews are served. If `preview_deploy_command`
is configured but `preview_site_url` is not, record
`deploy_status: awaiting-setup` and do not proceed to Step 4 — the
wrapper requires a site URL to verify served content. Do not construct
or guess a site URL.

The project owner must approve the deploy command and confirm:
- Reviewer visibility and access to the deployed preview
- Site-preserving integration (existing content not replaced)
- Namespace ownership (no collision with other PRs)

If no `preview_deploy_command` is configured, the wrapper returns
`awaiting-setup`. Do not claim the preview is published.

### Step 4: Deploy and Verify the Preview

When the handoff PR exists and deployment is configured:

1. **Confirm with the researcher** before deploying:
   > Deploy preview to {target_repo} for PR #{pr_number}?
   > Content digest: {content_sha256[:12]}…

2. **Invoke the publisher wrapper:**

   The `{bundle_dir}` from Step 2's JSON output already points to the
   full namespaced bundle path — do not append another level.

   ```bash
   python3 "$PREVIEW_PUBLISH" publish \
     --bundle-dir "{bundle_dir}" \
     --pr-repo "{pr_repo}" \
     --pr-number "{pr_number}" \
     --content-sha256 "{content_sha256}" \
     --target-repo "{target_repo}" \
     --deploy-command "{preview_deploy_command}" \
     --site-url "{preview_site_url}"
   ```

   The wrapper recomputes the bundle's actual byte digest before
   deploying and rejects modified bundles. It verifies served content
   at the approved `preview_site_url` (not the deploy receipt's URL).
   Parse the JSON receipt:

   - `status: awaiting-setup` — deploy command is not configured.
   - `status: published` — served content verified against the
     approved site URL using per-file hashes and aggregate digest.
   - `status: deployed-unverified` — deploy ran but served
     verification failed. Record `deploy-failed`.

   Identity fields (PR repo, number, content SHA, namespace) are
   guarded — the deploy command cannot overwrite them. A receipt
   alone is not verification.

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
  "deploy_status": "{published|awaiting-setup|deploy-failed|screenshot-fallback|stale}",
  "content_sha256": "{digest-from-package-output-or-null}",
  "pr_repo": "{owner/repo-from-docs_repo_remote}",
  "pr_number": "{pr-number-from-publish-metadata}",
  "target_repo": "{owner/repo-or-null}",
  "published_namespace": "{previews/owner/repo/pr-N/sha12-or-null}",
  "site_url": "{verified_url from publisher output when status is published; preserved as last-verified when stale; null otherwise}",
  "mocked_components": [],
  "timestamp": "{ISO-8601}"
}
```

### Step 6: Update the Handoff PR (with researcher approval)

If `publish-metadata.json` does not exist (no handoff PR), skip this
step.  The researcher can see the preview status in the phase completion
report.  Do not post `awaiting-setup` comments unless the researcher
explicitly requests it.

If `publish-metadata.json` exists and `deploy_status` is `published` or
`screenshot-fallback`, compose the comment text below and **present it
to the researcher for approval before posting**.  Use the existing
PR-comments script (`pr-comments.py reply`) that `/respond` uses to
post the approved comment.

For a published preview:
> **Review Preview:** [{site_url}]({site_url})
> Built from prototype iteration {N} ({mode} mode).
> Entry point: `{entry-point}`

For screenshot fallback:
> **Review Screenshots:** Screenshots of key flows are attached to this PR.
> Built from prototype iteration {N} ({mode} mode).

For deploy-failed:
> **Preview Status: Deploy Failed** — The static preview bundle was
> packaged but deployment verification failed. See
> preview-metadata.json for details. The bundle can be retried with
> `/preview` or the screenshot fallback can be used.

For stale:
> **Preview Status: Stale** — The handoff spec has been updated since
> the preview was last published. Last verified URL:
> [{site_url}]({site_url}) (outdated — not current).
> Run `/preview` to rebuild.

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
