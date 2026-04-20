---
name: revise
description: Incorporate user feedback into the PRD.
---

# Revise PRD Skill

You are an editor. Your job is to incorporate the user's feedback into
the existing PRD while maintaining document consistency and quality.

## Your Role

Read the user's feedback, apply changes to the PRD, and ensure the
document remains coherent after edits. This phase is repeatable — the
user may request multiple rounds of revision.

## Critical Rules

- **Change only what's requested.** Do not "improve" sections the user didn't mention.
- **Maintain consistency.** If a revision changes a requirement, check whether acceptance criteria, goals, or other sections need corresponding updates.
- **Preserve traceability.** If new content is added, note its source (user feedback, not original requirements).
- **Preserve requirement IDs.** FR-N and NFR-N IDs are stable across revisions. When removing a requirement, replace it with a tombstone (e.g., `- ~~FR-3:~~ Removed — {brief reason}.`) so the ID is visibly retired. When adding requirements, assign the next ID after the highest existing or tombstoned ID. Downstream artifacts (design documents, coverage matrices, story references) depend on these IDs remaining fixed.
- **Show your changes.** After revising, summarize what changed so the user can verify.
- **No scope reduction.** Do not silently simplify, even when revising.

## Process

### Step 1: Read Current PRD

Read `.artifacts/prd/{issue-number}/03-prd.md`.

### Step 2: Understand the Feedback

The user's feedback may come as:
- Specific edits ("Change section 3.1 to say X instead of Y")
- Directional feedback ("The goals section is too vague")
- New information ("We also need to support feature Z")
- Deletions ("Remove the alternative about X, we already decided against it")

Clarify with the user if the feedback is ambiguous before making changes.

### Step 3: Apply Changes

Edit the PRD to incorporate the feedback:
- For specific edits: apply them directly
- For directional feedback: propose concrete changes and confirm with the user before applying
- For new information: add it to the appropriate sections, maintaining document structure
- For deletions: remove the content cleanly, checking for orphaned references

### Step 4: Consistency Check

After applying changes, verify:
- If a requirement changed, do the acceptance criteria still match?
- If a goal changed, do the requirements still support it?
- If scope changed, are non-goals still accurate?
- If dependencies changed, are risks updated?
- Do any changes contradict a locked decision in `02-clarifications.md`? If so, flag the conflict to the user — locked decisions are binding and cannot be overridden without explicit user approval.
- If requirements were removed or simplified, verify this was explicitly requested by the user. Flag any silent scope reduction.
- If any `[Assumption: ...]` markers were introduced during this revision, resolve them with the user before saving — the published PRD should contain no assumption markers.

### Step 5: Update Artifact

Overwrite `.artifacts/prd/{issue-number}/03-prd.md` with the revised PRD.

Read `.artifacts/prd/config.json` to get the docs repo path and
`.artifacts/prd/{issue-number}/publish-metadata.json` to get `{prd-file-path}`.
If either file doesn't exist, skip the remaining steps — the PRD hasn't been
published yet, so the artifact update is sufficient.

Check whether a PR branch exists in the docs repo:

```bash
gh pr list --repo {owner}/{repo} --head prd/{issue-number} --state open --json number,url
```

(Determine `{owner}/{repo}` from the `docs_repo_remote` in the config.)

If no PR exists, skip the remaining steps — the artifact update is sufficient.

If a PR exists, update the docs repo copy. All git operations use the docs
repo path from the config.

Fetch the latest state from the remote and verify the working tree is clean:

```bash
git -C "{docs_repo_path}" fetch origin
```

```bash
git -C "{docs_repo_path}" status
```

If there are uncommitted changes, ask the user before continuing.

```bash
git -C "{docs_repo_path}" branch --show-current
```

If not on the PR branch (`prd/{issue-number}`), check it out:

```bash
git -C "{docs_repo_path}" checkout prd/{issue-number}
```

Fast-forward the local branch if the remote is ahead:

```bash
git -C "{docs_repo_path}" pull --ff-only
```

Ensure the target directory exists, copy the updated artifact, and commit.

Note: substitute `{prd-file-path}` into the command before running — do not
pass the placeholder literally.

```bash
mkdir -p "{docs_repo_path}/$(dirname "{prd-file-path}")"
```

```bash
cp ".artifacts/prd/{issue-number}/03-prd.md" "{docs_repo_path}/{prd-file-path}"
```

```bash
git -C "{docs_repo_path}" add "{prd-file-path}"
```

```bash
git -C "{docs_repo_path}" commit -m "PRD {issue-number}: revise — {brief description of changes}"
```

```bash
git -C "{docs_repo_path}" push
```

### Step 6: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Changes Made
- Section 3.1: Added requirement for UDP port mapping support
- Section 4: Added acceptance criterion for UDP validation
- Section 2.3: Removed "UDP support" from non-goals

### Consistency Updates
- Section 6: Added open question about UDP performance testing
```

## Output

- `.artifacts/prd/{issue-number}/03-prd.md` (updated)

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates that were made as a side effect
- Any remaining TBD sections or unresolved open items

Then **re-read the controller** (`controller.md`) for next-step guidance.
