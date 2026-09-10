---
name: resolve-docs-publish-remotes
version: 0.2.0
---
# Recipe: Resolve Documentation Publish Remotes

Resolve the canonical repository where the pull request belongs and the
remote where the contributor branch must be pushed. Remote names are local
labels and must not be used to infer either role.

## Inputs

- `DOCS_REPO_PATH`: absolute path to the documentation repository.
- `CONFIGURED_DOCS_REPO_REMOTE`: the URL stored in `.artifacts/config.json`,
  if present.
- `BRANCH_NAME`: the feature branch being published.

## Outputs

Set these values for the remainder of the publish phase:

- `UPSTREAM_REMOTE`: local remote whose repository is the canonical PR target.
- `PUSH_REMOTE`: local remote where `BRANCH_NAME` is pushed.
- `UPSTREAM_REPO`: canonical GitHub repository in `owner/repo` form.
- `PUSH_REPO`: GitHub repository reached by the push URL of `PUSH_REMOTE`.
- `PUSH_URL`: the selected push URL for `PUSH_REMOTE`, with URL userinfo
  removed before it is displayed or passed between workflow steps.
- `FORK_OWNER`: GitHub owner of `PUSH_REMOTE` when it is a fork; empty for a
  direct canonical publish.
- `CROSS_REPOSITORY`: `true` when `PUSH_REPO` and `UPSTREAM_REPO` differ;
  otherwise `false`.

## Resolution Procedure

1. From `DOCS_REPO_PATH`, enumerate `git remote` names. For every remote,
   inspect its fetch URL and every push URL with `git remote get-url` and
   `git remote get-url --push --all`, and normalize each URL to `owner/repo`.
   Keep fetch and push identities separate: a triangular remote may fetch from
   the canonical repository and push to a fork. Do not assume that `origin`,
   `upstream`, or `fork` has any particular role. Do not persist or display
   credentials embedded in a remote URL.
2. If `CONFIGURED_DOCS_REPO_REMOTE` is set, validate that its normalized URL
   matches at least one configured remote URL. A match on `origin` is not
   required. If it matches no remote, stop and report the mismatch.
3. For each distinct fetch or push repository identity, query GitHub metadata
   with `gh repo view owner/repo --json nameWithOwner,isFork,parent`. Treat the
   configured repository as the initial candidate when it is available.
4. Select the canonical repository:
   - If the configured repository is a fork, use its `parent.nameWithOwner` as
     `UPSTREAM_REPO`.
   - Otherwise use the configured repository as `UPSTREAM_REPO`.
   - When there is no configured repository, prefer non-fork repositories that
     are parents of observed fork candidates. If none are related, select the
     sole non-fork repository. If there is no unique selection, stop and ask
     the user to identify the canonical repository.
5. Select `UPSTREAM_REMOTE` as the local remote whose repository is
   `UPSTREAM_REPO`. If the canonical repository is not configured as a local
   remote, stop and ask the user to add it or confirm an explicit fetch plan.
6. Select `PUSH_REMOTE` and `PUSH_REPO` from push URL identities:
   - If a remote's push URLs all reach the same fork whose
     `parent.nameWithOwner` equals `UPSTREAM_REPO`, use that remote and set
     `PUSH_URL`, `PUSH_REPO`, and `FORK_OWNER` from it. This includes a
     triangular remote whose fetch and push URLs are different repositories.
   - If a candidate remote has multiple push destinations, or any destination
     cannot be normalized, stop and ask the user to configure one confirmed
     push destination. This prevents `git push <remote>` from broadcasting to
     an unconfirmed repository.
   - If no matching fork push destination exists, use `UPSTREAM_REMOTE` only
     when all of its push URLs resolve to the canonical repository, setting
     `PUSH_URL` and leaving `FORK_OWNER` empty. Otherwise stop and ask the user
     to configure a fork push destination or grant direct access.
7. Set `CROSS_REPOSITORY` to `true` when `PUSH_REPO` and `UPSTREAM_REPO`
   differ. Before modifying the docs repository, report `UPSTREAM_REPO`,
   `UPSTREAM_REMOTE`, `PUSH_REMOTE`, `PUSH_URL`, `PUSH_REPO`, and the selected
   branch to the user for confirmation as required by the calling workflow.

## Publish Commands

Use `UPSTREAM_REMOTE` for fetching the canonical base and checking the base
branch. `PUSH_URL` is a credential-free display value; derive the raw push URL
only in a local shell variable for checking whether the feature branch already
exists on the push destination. This is required for a triangular remote,
where the remote's fetch URL and push URL point to different repositories. Use
`PUSH_REMOTE` for pushing the feature branch:

```bash
git -C "$DOCS_REPO_PATH" fetch "$UPSTREAM_REMOTE"
PUSH_URL_RAW="$(git -C "$DOCS_REPO_PATH" remote get-url --push "$PUSH_REMOTE")"
git -C "$DOCS_REPO_PATH" ls-remote --heads "$PUSH_URL_RAW" "refs/heads/$BRANCH_NAME"
git -C "$DOCS_REPO_PATH" push -u "$PUSH_REMOTE" "$BRANCH_NAME"
```

Create the draft PR as follows:

- When `CROSS_REPOSITORY=true`, use
  `gh pr create --draft --repo "$UPSTREAM_REPO" --head
  "$FORK_OWNER:$BRANCH_NAME"`. The base branch is supplied by the calling
  workflow.
- When `CROSS_REPOSITORY=false`, use the direct-repository form with
  `--repo "$UPSTREAM_REPO" --head "$BRANCH_NAME"`.

Never derive `--repo` from the push remote, and never use an unqualified
`--head` for a cross-repository PR.

## Verification Matrix

Before committing workflow changes, verify the observable result for each
topology:

| Topology | `UPSTREAM_REPO` | `PUSH_REMOTE` / `PUSH_REPO` | PR head |
|----------|-----------------|---------------|---------|
| Direct canonical clone | canonical repository | canonical remote | `branch` |
| Canonical `origin`, fork `fork` | canonical repository | `fork` | `fork-owner:branch` |
| Fork `origin`, canonical `upstream` | canonical repository | `origin` | `fork-owner:branch` |
| Canonical fetch plus fork `pushurl` | canonical repository | same remote / fork repository | `fork-owner:branch` |

If any row cannot be resolved without guessing, stop and request clarification.
