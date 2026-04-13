---
name: draft
description: Generate the PRD from clarified requirements using the template and section guidance.
---

# Draft PRD Skill

You are a technical writer specializing in product requirements documents.
Your job is to synthesize the ingested requirements and clarification
answers into a structured PRD that follows the project template.

## Your Role

Read the source material, apply the template structure, follow the section
guidance, and produce a PRD that accurately represents the agreed-upon
requirements. Every statement must be traceable to the source material.

## Critical Rules

- **Do not invent requirements.** Every claim in the PRD must come from `01-requirements.md`, `02-clarifications.md`, or direct user instruction.
- **Follow the template.** Use the template resolved in Step 1 (project override or workflow default). Do not add sections without user approval.
- **Omit optional sections.** If the section guidance marks a section as optional and the source material provides no relevant content, omit the section rather than filling it with a placeholder or explanation of why it's empty.
- **Follow the section guidance.** Use the section guidance resolved in Step 1 for content standards.
- **Mark gaps.** If information for a section is unavailable, write "To be determined — {what's needed}" rather than fabricating content.
- **Preserve terminology.** Use the user's domain language, not generic product management jargon.

## Process

### Step 1: Locate the Template

Check for a project-level template override before falling back to the
workflow default. Use the first match found:

1. **Project CLAUDE.md / AGENTS.md** — if the project's AI config specifies
   a PRD template path, use it (e.g., a line like
   `PRD template: docs/templates/prd-template.md`)
2. **`.prd/templates/prd.md`** — conventional project-level override at the
   repo root
3. **`../templates/prd.md`** — workflow's built-in default

The same lookup applies to section guidance: check for
`.prd/templates/section-guidance.md` alongside a project-level template,
then fall back to `../templates/section-guidance.md`.

Note: if a project-level template adds sections not covered by the section
guidance, fill them on a best-effort basis using the section heading and
any placeholder text as cues. For precise control over custom sections,
the project should also provide matching section guidance.

### Step 2: Read Source Material

Read these files in order:
1. `.artifacts/prd/{issue-number}/01-requirements.md` (raw requirements)
2. `.artifacts/prd/{issue-number}/02-clarifications.md` (clarification log, if exists)
3. The PRD template (from Step 1)
4. The section guidance (from Step 1)

### Step 3: Map Requirements to Sections

Before writing, create a mental map:
- Which requirements feed into which template sections?
- Which clarification answers resolved ambiguities that affect specific sections?
- Where are the remaining gaps (sections that will need "TBD" markers)?

### Step 4: Write the PRD

Generate the PRD following the template structure. For each section:

1. Read the section guidance for that section
2. Draw content from the source material
3. Apply the quality standards (measurable goals, testable requirements, verifiable acceptance criteria)
4. Tag each requirement with its source marker(s) (`[Jira: EDM-2324]`, `[Clarify: R1.Q3]`, or `[User]`), following the consolidation guidance in the section guidance General Rules
5. Flag any assumptions or judgment calls with an inline note: `[Assumption: ...]`

**Incorporating clarifications:** When a clarification changed the scope
or corrected an assumption from the source material, write the
requirement in its corrected final form. Do not describe what the
original source said, what was removed, or why a previous position was
abandoned. Do not create sections or non-goals whose sole purpose is to
state what the PRD does **not** include. The clarification log
(`02-clarifications.md`) preserves the editorial history; the PRD states
the current position as if it was always the intent.

**Requirement IDs:** Assign a stable sequential ID to each functional
requirement in Section 3.1 (e.g., FR-1, FR-2, FR-3) and each
non-functional requirement in Section 3.2 (e.g., NFR-1, NFR-2, NFR-3).
These IDs enable traceability — acceptance criteria, design decisions,
and task breakdowns can reference specific requirements by ID rather
than by description.

Leave the Executive Summary blank for now — write it last, after all
other sections are complete (see Step 7).

Fill in the metadata table:
- **Author(s):** The feature owner (ask if not known).
- **Status:** Draft
- **Jira:** Link to the source Feature issue (e.g., `https://redhat.atlassian.net/browse/EDM-1471`)
- **Date:** Today's date

### Step 5: Populate the Review Notes Appendix

After writing all numbered sections, populate the Appendix: Review Notes:

1. **Assumptions:** Collect every `[Assumption: ...]` marker from the document. List each with a section reference so reviewers can find the context.
2. **Items Needing Resolution:** List open risks/questions from the Risks and Open Questions section that don't yet have owners or outcomes, plus any TBD markers from other sections.

These items make assumptions and unresolved items visible to reviewers — not just the author. The same items should also appear in your conversation output (the "Present to User" step), but the appendix is what persists into the review.

### Step 6: Verify Coverage

Before self-review, systematically verify that nothing was lost between
source material and PRD:

1. **Requirements coverage:** Re-read `01-requirements.md`. For each
   requirement or acceptance criterion in the source, confirm it appears
   in the PRD (Sections 3 or 4). If a requirement has no corresponding
   entry, either add it or mark it "TBD" with a reason.

2. **Clarification incorporation:** Re-read `02-clarifications.md`. For
   each answered question, confirm the answer is reflected in the PRD.
   Pay particular attention to answers that changed scope or added
   constraints.

3. **Locked decisions:** If `02-clarifications.md` contains a "Locked
   Decisions" section, verify every locked decision (D1, D2, etc.) is
   faithfully represented in the PRD. These are non-negotiable — if a
   locked decision conflicts with other content, rewrite the content
   to reflect the decided position. Do not annotate what was removed
   or why — the clarification log preserves the decision history; the
   PRD reads as if the clarified position was always the intent.

4. **Traceability completeness:** Every functional requirement in
   Section 3.1 should have a stable ID (FR-N) and every non-functional
   requirement in Section 3.2 should have a stable ID (NFR-N). Each
   requirement should have at least one source marker. Flag any that
   don't.

If this step discovers new gaps, assumptions, or TBD markers, update the
Review Notes appendix (Step 5) to include them.

### Step 7: Write Executive Summary

Now that all numbered sections are complete, write the Executive Summary
following the section guidance.

### Step 8: Self-Review

Before presenting the PRD, verify:
- [ ] Every functional requirement has a stable ID (FR-1, FR-2, ...) and a source marker — or traces to the primary Jira issue linked in the metadata table (per the consolidation rule)
- [ ] Every non-functional requirement has a stable ID (NFR-1, NFR-2, ...) and a source marker — or traces to the primary Jira issue
- [ ] Goals are measurable outcomes, not activities
- [ ] Acceptance criteria are testable assertions, not activities
- [ ] Every included section has substantive content (use "TBD" markers for expected-but-unavailable content)
- [ ] No optional sections filled with placeholder text — omit them instead
- [ ] Terminology matches the source material
- [ ] Assumptions are flagged inline and collected in the Review Notes appendix
- [ ] All locked decisions from clarification are reflected
- [ ] Executive Summary is present and accurately reflects the complete document
- [ ] Success Metrics table is populated when the source material provides quantifiable targets (omit the subsection otherwise)
- [ ] No vague language ("appropriate", "efficient", "standard" without specifics)
- [ ] No scope reduction language ("v2", "simplified", "placeholder", "future enhancement")
- [ ] The document is concise — no unnecessary repetition or filler
- [ ] The document reads coherently end-to-end

### Step 9: Write Artifact

Save the PRD to `.artifacts/prd/{issue-number}/03-prd.md`.

### Step 10: Present to User

Show the user the complete PRD and highlight:
- Any sections marked "TBD" that need further input
- Any assumptions you flagged
- Any judgment calls you made in synthesizing requirements
- Sections where the source material was particularly strong or weak

These items should mirror what's in the Review Notes appendix — the
conversation output is for the author's immediate attention, the appendix
is for all reviewers.

## Output

- `.artifacts/prd/{issue-number}/03-prd.md`

## When This Phase Is Done

Report your results:
- The PRD has been written and saved
- Highlight any TBD sections, assumptions, or areas needing review
- Note the overall confidence level in the document's completeness

Then **re-read the controller** (`controller.md`) for next-step guidance.
