---
name: resolve-artifacts
version: 0.1.0
---
# Canonical Workflow State

## Every Entry Point

Before any phase, standalone command, unattended run, resume/discovery, precheck,
cleanup, or artifact read/write, resolve state with the shared script. This also
applies when invoking a phase directly or using a project phase override. Resolve
from the **source repository**, not a documentation/deliverable checkout. Carry
the absolute result across subsequent CWD changes and pass it to helper scripts
and delegated prompts. Re-resolve on each new phase/session, not from cached CWD.

Locate the script relative to the installed skill's real directory:
`../_shared/scripts/artifacts.py` from a workflow root, or
`../../_shared/scripts/artifacts.py` from a source simple-skill root.
The installer also links `_shared` beside installed skills. Resolve the skill
symlink to locate the source installation; do not infer it from the target repo.

```bash
ARTIFACTS_ROOT="$(python3 "{AI_WORKFLOWS_ROOT}/_shared/scripts/artifacts.py" \
  --repo "{SOURCE_REPO}")" || exit 1
```

`{ARTIFACTS_ROOT}` in workflow instructions is this absolute value, never a
literal directory name. Quote the expanded path in shell commands. Repository
configuration is `{ARTIFACTS_ROOT}/config.json`. Workflow state normally lives at
`{ARTIFACTS_ROOT}/{workflow}/{context}`. Preserve each workflow's existing
issue-less names (project, target skill, date, or operation); do not invent Jira
issues. This does not relocate published documents, source files, docs clones,
or their consumer-defined output paths. The docs-writer ticket directory remains
`{ARTIFACTS_ROOT}/{ticket_id}` for compatibility.

The script also accepts `WORKFLOW [CONTEXT]` or `--path .artifacts/...` and prints
the checked absolute path. Python consumers import `artifact_root`,
`artifact_directory`, or `canonical_path` from `_shared/scripts/artifacts.py`.
Errors stop the operation; do not fall back to a local `.artifacts` directory.

## Ownership And Lifetime

Git's first worktree record identifies the main worktree, regardless of its
branch name. All linked/detached worktrees of that repository share the main
worktree's `.artifacts`. Single-checkout repositories use their own `.artifacts`.
No state is created by resolution. Bare/nonrepository invocation is an error.
Artifact paths must not traverse symlinks or escape the canonical state root.

State is anchored to the main worktree's filesystem lifetime: removing it removes
access to that state. Back up state before moving/removing the main checkout;
restore it explicitly if needed. This is not an independent durable store.
There is **no locking**. Serialize same-ticket/operation writes across sessions;
coordinate repository-wide `config.json` updates as well. Do not run concurrent
writers expecting automatic merging, atomic multi-file updates, or conflict
resolution. Existing worktree creation/removal policies are unchanged.

## Explicit Legacy Reconciliation (No Automatic Migration)

Before returning state, the resolver examines `.artifacts` in every registered
linked worktree. Any files or symlinks there stop resolution, including disjoint
legacy files; overlapping canonical names are reported as conflicts/overlaps.
Nothing is copied, overwritten, deleted, or automatically migrated. Unregistered
or removed checkouts cannot be discovered: include any known copies in review.

1. Stop all writers and inventory the reported legacy paths, the main checkout's
   state, and any known unregistered copies. Back them up outside these trees.
2. Compare same-relative-path files, including plans, manifests, publish metadata,
   provenance, and `config.json`. Decide explicitly which version to retain or
   how to merge it. Even identical duplicates need explicit acknowledgement.
3. For absent destinations only, manually create parent directories and copy
   with a no-clobber operation (for example `cp -n -- SOURCE DEST` on GNU systems).
   Check the destination content afterward: a skipped copy is not proof of
   success. Never follow artifact symlinks; investigate them separately.
4. Resolve every overlap explicitly using reviewed copies, retaining backups.
   Only after verifying canonical contents, explicitly archive/remove the old
   copies with the owner's approval. The resolver performs none of these steps.
5. Re-run the resolver from both checkouts; both must report the same root before
   resuming. Do not bypass refusal by redirecting state or adding symlinks.
