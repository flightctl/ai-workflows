---
name: revise
description: Incorporate stakeholder feedback into the handoff spec.
---

# Revise — Update Handoff Spec

Incorporate the user's feedback into the existing handoff spec while
maintaining consistency across all prior artifacts. This phase is
repeatable — the user may request multiple rounds of revision.

## Critical Rules

- **Change only what's requested.** Do not "improve" sections the user didn't mention.
- **Maintain consistency across artifacts.** If a handoff change contradicts research findings or evaluation results, flag it.
- **Show your changes.** After revising, summarize what changed so the user can verify.

## Process

### Step 1: Read Current Artifacts

Read the handoff spec and prior artifacts. If `05-handoff.md` does not exist,
stop and tell the researcher to run `/handoff` first.

Read `00-context.md`. If the context revision changed after the handoff or the
handoff is not approved against the current enriched revision, stop and
recommend `/handoff` to regenerate it before applying stakeholder revisions.

- `.artifacts/ux-design/{issue-key}/05-handoff.md` (the deliverable)
- `.artifacts/ux-design/{issue-key}/04-evaluation.md` (evaluation context)
- `.artifacts/ux-design/{issue-key}/02-research.md` (research findings, if it
  exists — needed to check acceptance-criteria traceability in Step 4)
- `.artifacts/ux-design/{issue-key}/01-discovery.md` (problem context)

### Step 2: Understand the Feedback

The user's feedback may target:
- Component mapping changes
- Interaction spec corrections
- State coverage gaps
- Acceptance criteria adjustments
- Research context clarifications
- Screenshot additions, replacements, or removals

Clarify with the user if the feedback is ambiguous before making changes.

### Step 3: Apply Changes

Edit the handoff spec:
- For specific edits: apply them directly
- For directional feedback: propose concrete changes and confirm before applying
- For new information: add it to the appropriate sections

### Step 3a: Handle Screenshot Changes

If the revision adds, replaces, or removes screenshots:

1. **Adding:** Assign a new `SS-N` ID (next unused integer). Copy the
   image into `.artifacts/ux-design/{issue-key}/screenshots/` using stable
   naming. Compute its SHA-256 and add the entry to
   `screenshot-manifest.json`. Add both an inline `![alt](ref)` embed at
   the relevant flow/state section and a row in the Screenshot Index of
   `05-handoff.md`.

2. **Replacing:** Replace the file in `screenshots/`, update the
   manifest's `sha256` field, and update the embed's alt text and caption
   if the visual content changed. Note the visual change in the revision
   summary. The manifest checksum ensures `/publish` detects the update
   even when the filename and handoff text are unchanged.

3. **Removing:** Delete the file from `screenshots/`, remove its manifest
   entry, remove the inline `![alt](ref)` embed **and** the Screenshot
   Index row from `05-handoff.md`. If a PR has been published, `/publish`
   will remove the file from the published Git/LFS tree on the next
   update.

4. **Image-only change** (same ID, same filename, visually different
   content): Replace the file, update the manifest's `sha256`, and note
   the change. The checksum difference signals `/publish` and `ui-design`
   that the visual content changed.

**Adding screenshots to a previously text-only handoff.** If the handoff
has `Screenshot Index: None` and the researcher provides images, the recorded
`screenshot_storage` policy of `none` is no longer valid. Tell the
researcher that an explicit storage policy (`lfs`, `external`, or `git`)
is required before the next `/publish`, then follow the curation
procedure from `/handoff` Step 5.

**Provenance capture.** After all textual and screenshot changes are
written to `05-handoff.md` and the manifest, capture provenance:

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ux-design`, `ISSUE_KEY={issue-key}`, `PHASE=revise`,
`AUTHORING_MODE=skill`.

### Step 4: Consistency Check

After applying changes, verify:
- Do acceptance criteria still trace to research findings?
- Does the component mapping still align with the prototype?
- Are interaction specs consistent with evaluation findings?
- Are there contradictions with locked research decisions?
- Do screenshot references in the handoff match the manifest?

### Step 5: Present Changes

Summarize what changed:

```markdown
## Revision Summary

### Handoff Changes
- {Section}: {what changed and why}

### Consistency Updates
- {any cascading updates to maintain coherence}
```

## Output

- `.artifacts/ux-design/{issue-key}/05-handoff.md` (updated)
- `.artifacts/ux-design/{issue-key}/provenance.json` (updated)

## If a PR Already Exists

`/revise` can run before or after `/publish`. If a PR already exists for this
handoff spec (check for `.artifacts/ux-design/{issue-key}/publish-metadata.json`),
the revised `05-handoff.md` is now out of sync with the published copy in the
docs repo. Do **not** push it manually. Tell the researcher to run `/publish`
to update the existing open PR branch through the workflow's publish path;
`/publish` uses the saved metadata and does not create a second PR. Use
`/respond` separately to address reviewer comments.

## When This Phase Is Done

Report your results:
- What was changed and why
- Any consistency updates made as a side effect
- Whether a PR already exists and the spec now needs re-publishing
- Any remaining open questions

Then **re-read the controller** (`controller.md`) for next-step guidance.
