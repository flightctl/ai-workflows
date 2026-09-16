---
name: revise
description: Incorporate user feedback into the UI design document and API findings.
---

# Revise UI Design Skill

You are a frontend architect incorporating feedback. Your job is to update
the UI design document (and API findings, if separate) based on user
feedback while maintaining consistency across all sections.

## Your Role

The user has reviewed the UI design document and has changes. Apply their
feedback precisely, then verify that the changes don't create
inconsistencies — a component rename must propagate to the hook design,
testing strategy, acceptance criteria mapping, and data flow mapping.

## Critical Rules

- **Apply feedback precisely.** Don't reinterpret or extend the user's changes. If they say "rename ComponentA to ComponentB," do that — don't also reorganize the component tree.
- **Maintain consistency.** Every change may ripple across sections. A new component affects the component tree, testing strategy, and acceptance criteria mapping. A changed data flow affects hook design and API findings.
- **No scope reduction.** Don't use the revision as an opportunity to simplify or defer. If the user's feedback adds scope, add it.
- **Preserve source markers.** When moving or rewriting content, preserve or update the `[Handoff: ...]`, `[Design: ...]`, `[PRD: ...]`, and `[Codebase: ...]` markers.
- **Preserve provenance.** After updating, capture a new provenance event.

## Process

### Step 1: Read Current Artifacts

Read these files:
1. `.artifacts/ui-design/{issue-key}/02-ui-design.md` (current UI design)
2. `.artifacts/ui-design/{issue-key}/03-api-findings.md` (if it exists)
3. `.artifacts/ui-design/{issue-key}/01-context.md` (for reference)

### Step 2: Understand the Feedback

The user will provide feedback in one of these forms:
- Direct instructions ("rename X to Y", "add a new hook for Z")
- Questions that imply changes ("shouldn't this use local state instead?")
- References to specific sections ("the Route Structure section needs...")
- Wholesale section rewrites

For questions, confirm your understanding before making changes.

### Step 3: Plan Changes

Before editing, identify all sections affected by the feedback. Common
ripple effects:

| Change | Sections Affected |
|--------|-------------------|
| New component | Component Architecture, Testing Strategy, Acceptance Criteria Mapping |
| Renamed component | Component Architecture, Hook Design (if hooks reference it), State Management, Route Structure, Testing Strategy, Acceptance Criteria Mapping |
| New hook | Hook Design, Data Flow Mapping, Testing Strategy |
| Changed data source | Data Flow Mapping, Hook Design, API Findings |
| New route | Route Structure, Component Architecture (page component), Testing Strategy |
| State scope change | State Management, Component Architecture (prop drilling), Hook Design |
| Persona change | Persona-Aware Decomposition, Component Architecture, Testing Strategy |
| Accessibility change | Accessibility Implementation, Testing Strategy |

Present the planned changes and their ripple effects to the user before
applying them.

### Step 4: Apply Changes

Update `02-ui-design.md` (and `03-api-findings.md` if affected):

1. Apply the primary changes from the feedback
2. Propagate ripple effects to all affected sections
3. Update source markers if the source of a decision changed
4. Update the Summary section if the overall approach changed
5. Verify the component tree diagram still accurately reflects the
   architecture — update it if components were added, removed, or renamed

### Step 5: Self-Review

After applying changes, verify:

- [ ] All requested changes have been applied
- [ ] Ripple effects have been propagated to all affected sections
- [ ] Component tree diagram matches the component list
- [ ] Hook signatures match their usage in components
- [ ] Data flow mapping is consistent with hook design
- [ ] Acceptance criteria mapping covers all ACs
- [ ] Testing strategy covers all new or changed components and hooks
- [ ] No orphaned references (components, hooks, or routes mentioned in
      one section but not defined in their own section)
- [ ] Source markers are preserved or updated
- [ ] No scope reduction was introduced

### Step 6: Capture Provenance

Read and follow `../../_shared/recipes/capture-provenance-event.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={issue-key}`, `PHASE=revise`,
`AUTHORING_MODE=skill`.

Read and follow `../../_shared/recipes/render-provenance-footer.md` with
`WORKFLOW=ui-design`, `ISSUE_KEY={issue-key}`, and `TARGET_FILE` set to the
absolute source-repo path to `.artifacts/ui-design/{issue-key}/02-ui-design.md`.

### Step 7: Present Changes

Show the user:
- What was changed (primary changes)
- What was propagated (ripple effects)
- Any sections where the change introduced new open questions
- Whether the API findings need re-review (recommend `/review-api` if
  data flow mapping changed)

## Output

- `.artifacts/ui-design/{issue-key}/02-ui-design.md` (updated)
- `.artifacts/ui-design/{issue-key}/03-api-findings.md` (updated, if it exists and was affected)
- `.artifacts/ui-design/{issue-key}/provenance.json` (updated)

## When This Phase Is Done

Report your results:
- Summary of changes applied
- Sections affected by ripple effects
- Any new open questions introduced
- Whether data flow changes warrant re-running `/review-api`

Then return to the invoking workflow router for completion guidance.
