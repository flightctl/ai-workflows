---
name: preflight
description: Shared gate every rebase-stack phase runs before doing anything else.
---

# Preflight (shared step)

Every phase starts here. Do not skip it and do not reuse an earlier phase's
result — the stack, the remotes, and the working tree all change mid-workflow.

## Step 1: Resolve the Scripts Directory

The helper scripts ship inside this workflow package, as a sibling of the
`skills/` directory this file lives in. Resolve that path once and reuse it as
`{scripts}` for the whole phase. Do not hardcode an install location: global,
project-local (`.workflows/`), and symlinked installs all differ.

- You are reading `<package>/skills/preflight.md`.
- Therefore `{scripts}` is `<package>/scripts`.

Confirm it before first use:

```bash
ls "{scripts}"
# expect: preflight.sh  snapshot.sh  stack-status.sh  validate-branches.sh
```

If that listing fails, stop and report an incomplete package. Run every command
below from the repository root of the project being rebased.

## Run It

```bash
mkdir -p .artifacts/rebase-stack
bash "{scripts}/preflight.sh" > .artifacts/rebase-stack/context.json
echo "preflight exit: $?"
```

For `/continue`, which runs with a rebase deliberately in progress, add the
flag:

```bash
bash "{scripts}/preflight.sh" --allow-rebase-in-progress \
  > .artifacts/rebase-stack/context.json
echo "preflight exit: $?"
```

## Act on the Exit Code

**Exit 0** — continue with the phase. Read the context:

```bash
jq -r '"base=\(.trunk)  base-remote=\(.baseRemote)  push-remote=\(.pushRemote)  validate=\(.validationBranch)"' \
  .artifacts/rebase-stack/context.json
jq -r '.branches[] | "\(.name)  needsRebase=\(.needsRebase)  pr=\(.pr // "none")"' \
  .artifacts/rebase-stack/context.json
```

Bind these names for the rest of the phase:

| Name | jq path |
|------|---------|
| `{base}` | `.trunk` |
| `{base-remote}` | `.baseRemote` |
| `{push-remote}` | `.pushRemote` |
| `{push-list}` | `.branches[].name`, bottom to top |
| `{bottom-branch}` | `.bottomBranch` |
| `{validation-branch}` | `.validationBranch` — the trunk-adjacent branch |
| `{existing-pr}` | `.branches[].pr` |
| `{is-fork}` / `{parent-repo}` / `{fork-owner}` | `.isFork` / `.parentRepo` / `.forkOwner` |

**Any non-zero exit** — the script already printed the reason and the exact
remedy on stderr. Relay that message verbatim and **stop**. Do not work around
it, do not install anything, do not fall back to `git rebase`.

| Exit | Meaning | What to tell the user |
|------|---------|-----------------------|
| 2 | Not in a tracked stack | This workflow only rebases gh-stack stacks. Use `git rebase` for a single branch, or `gh stack init` to adopt a chain first. |
| 3 | Rebase already in progress | Run `/continue`, or `gh stack rebase --abort`. |
| 4 | GitHub API failure | Show `gh auth status`; ask before retrying. |
| 6 | Branch is in several stacks | Run `gh stack checkout <branch>` to disambiguate. |
| 7 | Dirty working tree | Commit or stash, then retry. |
| 8 | Missing `gh`, `jq`, or the `gh stack` extension | Install the named tool. This workflow will not do it. Note gh exits 0 with an advisory when the extension is absent, so never infer availability from an exit code. |
| 9 | Remote could not be resolved | Ask which remote hosts the base branch and which receives the push. |
