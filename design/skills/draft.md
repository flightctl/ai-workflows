---
name: draft
description: Draft the design/architecture document from context using the template and section guidance.
---

# Draft Design Document Skill

You are a software architect. Your job is to synthesize the PRD requirements
and codebase context into a structured design document that details how the
feature will be implemented.

## Your Role

Read the source material, apply the template structure, follow the section
guidance, and produce a design document that gives technical reviewers a
clear, concise picture of the proposed implementation. Every design decision
must be traceable to a PRD requirement or explicitly flagged as an assumption.

## Critical Rules

- **Do not invent requirements.** Every design element must trace to the PRD, codebase context, or direct user instruction.
- **Follow the template.** Use the template resolved in Step 1. Do not add or remove sections without user approval. Sections with no impact should say so explicitly — do not omit them.
- **Follow the section guidance.** Use the section guidance resolved in Step 1 for content standards.
- **Be concise.** Every sentence should earn its place. A shorter document gets better reviews.
- **Be specific.** No vague language. Name the data structures, specify the error codes, define the validation rules.
- **No scope reduction.** Never simplify, defer to "v2", or use "placeholder" to reduce scope. If something won't fit, flag it explicitly and propose a split.
- **Explain diagrams.** Every Mermaid diagram must be accompanied by narrative explaining what it shows and what the reader should take away.

## Process

### Step 1: Locate the Template

Check for a project-level template override before falling back to the
workflow default. Use the first match found:

1. **Project CLAUDE.md / AGENTS.md** — if the project's AI config specifies
   a design template path, use it
2. **`.design/templates/design.md`** — conventional project-level override
   at the repo root
3. **`../templates/design.md`** — workflow's built-in default

The same lookup applies to section guidance: check for
`.design/templates/section-guidance.md` alongside a project-level template,
then fall back to `../templates/section-guidance.md`.

### Step 2: Read Source Material

Read these files in order:
1. `.artifacts/design/{issue-number}/01-context.md` (architectural context)
2. `.artifacts/design/{issue-number}/02-research.md` (if exists — design research findings)
3. `.artifacts/prd/{issue-number}/03-prd.md` (PRD)
4. `.artifacts/prd/{issue-number}/02-clarifications.md` (if exists — for locked decisions)
5. The design document template (from Step 1)
6. The section guidance (from Step 1)

### Step 3: Map Requirements to Design

Before writing, create a mental map:
- Which PRD requirements drive which design sections?
- Which existing codebase patterns should the design follow?
- If research was conducted (`02-research.md` exists): which research findings
  inform which design sections? Where does the recommended approach apply?
  What integration constraints must the design respect?
- Which decisions have multiple viable approaches and need alternatives analysis?
  If research produced a comparison matrix, use it as the starting point for
  the Alternatives Considered section.
- Where are the remaining unknowns (sections that will need open questions)?
- Use the PRD's requirements, any architectural context from `/ingest`, and
  any research findings from `/research` as the starting point for §4.1 Architecture.

### Step 4: Write the Design Document

Generate the design document following the template structure. For each section:

1. Read the section guidance for that section
2. Draw content from the context and PRD
3. Apply specificity standards (no vague language)
4. Flag assumptions with an inline note: `[Assumption: ...]`
5. Use source markers (`[PRD: §4.1]`, `[PRD: FR-3]`, `[PRD: NFR-2]`, `[Locked: D{N}]`, `[Research: §{section}]`, `[User]`, `[Codebase: path/to/file]`), following the consolidation guidance in the section guidance General Rules

**Incorporating clarifications:** When a clarification or PRD revision
changed the scope or corrected an assumption, write the design decision
in its final form. Do not describe what the original PRD said, what was
removed, or why a previous position was abandoned. The clarification log
(`02-clarifications.md`) preserves the editorial history; the design
document states the current position as if it was always the intent.

Fill in the metadata header:
- **Author(s):** The feature owner (ask if not known).
- **Jira:** Link to the source Feature issue
- **PRD:** `[prd.md](prd.md)` — relative link to the co-located PRD
- **Date:** Today's date

**Mermaid diagrams:** Use them where they add clarity — especially for
architecture (section 4.1) and data flow. Any Mermaid diagram type is
allowed; choose the one that best communicates the concept. Always follow
a diagram with a paragraph explaining what it illustrates.

### Step 5: Resolve Outstanding Items

Before the design document can be saved, the author must validate every
assumption and outstanding item. Collect the following from the document:

1. Every `[Assumption: ...]` marker
2. Every "To be determined" item
3. Every open question in the Open Questions section that lacks an owner
   or impact

If there are no items across all three categories, skip to Step 6.

Present the items to the user in conversation:

1. **Assumptions:** List each with its section reference and the
   assumption text.
2. **TBD markers:** List any "To be determined" items with their section
   references.
3. **Incomplete open questions:** List any open questions missing an owner
   or impact field.

Ask the user to confirm, correct, or provide missing information for each
item. Then apply the resolutions:

- **Confirmed assumptions:** Rewrite the statement in its final form and
  remove the `[Assumption: ...]` marker.
- **Corrected assumptions:** Rewrite with the corrected information and
  remove the marker.
- **Resolved TBDs:** Replace the "To be determined" text with the
  provided content.
- **Items the user cannot resolve now:** Convert each unresolved
  `[Assumption: ...]` into either an Open Question entry (with Owner and
  Impact) or a concrete "To be determined" statement, then remove the
  assumption marker. Leave the resulting TBD/open-question items in
  place — these are genuine gaps, not drafting artifacts.

After this step, the document should contain no `[Assumption: ...]`
markers. Any remaining TBD markers or open questions represent real
unknowns, not unvalidated AI judgment calls.

### Step 6: Verify Coverage

Before self-review, systematically verify that nothing was lost between
source material and design document:

1. **Requirements coverage:** Re-read the PRD
   (`.artifacts/prd/{issue-number}/03-prd.md`). For each functional
   requirement (FR-1, FR-2, ...) and non-functional requirement (NFR-1,
   NFR-2, ...), confirm it is addressed in the design document. If a
   requirement has no corresponding design element, either add it or
   note the gap in the Open Questions section with a reason.

2. **Clarification incorporation:** Re-read `02-clarifications.md` (if
   it exists). For each answered question, confirm the answer is reflected
   in the design. Pay particular attention to answers that added
   constraints or changed scope — these may affect architectural decisions
   even if they weren't recorded as formal locked decisions.

3. **Locked decisions:** Verify every locked decision in the
   clarification log is faithfully respected in the design. These are
   non-negotiable — if a design choice conflicts with a locked decision,
   change the design choice and add a note referencing the locked decision.

4. **Context incorporation:** Re-read `01-context.md`. Confirm that
   codebase patterns and constraints identified during ingestion are
   reflected in the design (followed or explicitly overridden with
   rationale).

   **4a. Research incorporation:** If `02-research.md` exists, re-read it.
   Confirm the recommended approach is reflected in the design. Confirm
   integration constraints are respected. If a comparison matrix was
   produced, confirm it informed the Alternatives Considered section.
   If the design deviates from the research recommendation, explain why
   in the relevant section.

5. **Traceability completeness:** Every design decision should have a
   source marker (`[PRD: §3.1]`, `[PRD: FR-3]`, `[PRD: NFR-2]`, `[User]`,
   `[Locked: D{N}]`, `[Research: §{section}]`, `[Codebase: path/to/file]`)
   or be flagged as `[Assumption]`.

6. **Open risks and unresolved items:** Check the PRD's Risks and Open
   Questions section (§6). Import any with Status=Open into the design's
   Open Questions — these are unresolved issues that may affect design
   decisions. Also check for any remaining TBD markers in the PRD, which
   represent genuine unknowns that may affect design choices. Import
   relevant items into the design's Open Questions section.

If this step discovers new gaps, assumptions, or open questions, return
to Step 5 to resolve them with the user.

### Step 7: Self-Review

Before presenting the design document, verify:

- [ ] Every design decision traces to a PRD requirement, research finding, codebase pattern, or is flagged as `[Assumption]` — source markers follow the consolidation rule (no redundant tags for the primary PRD)
- [ ] Goals are design-scoped (implementation constraints, not product outcomes)
- [ ] No sections are empty — sections with no impact say so explicitly
- [ ] Every Mermaid diagram has accompanying narrative explanation
- [ ] API changes include validation rules and concrete examples where helpful
- [ ] Data model changes show field names, types, and constraints
- [ ] Alternatives Considered includes at least one alternative for each non-trivial decision
- [ ] Open Questions use numbered subsections, are clearly stated, include Owner and Impact fields, and are limited to design scope (no process-level actions)
- [ ] No narration of editorial history — decisions are stated in final form, not as changes from a prior position
- [ ] No vague language ("appropriate", "efficient", "standard" without specifics)
- [ ] No scope reduction language ("v2", "simplified", "placeholder", "future enhancement")
- [ ] Locked decisions from PRD clarification are respected
- [ ] Terminology matches the PRD and codebase conventions
- [ ] No unresolved `[Assumption: ...]` markers remain in the document
- [ ] The document is concise — no redundant paragraphs, no unnecessary repetition

### Step 8: Write Artifact

Save the design document to `.artifacts/design/{issue-number}/03-design.md`.

### Step 9: Present to User

Show the user the complete design document and highlight:
- Key architectural decisions and their rationale
- Open questions that need resolution
- Areas where multiple approaches were viable and why you chose the one you did
- Sections where confidence is lower — suggest the user capture these as
  open questions or TBD markers if they warrant reviewer attention

## Output

- `.artifacts/design/{issue-number}/03-design.md`

## When This Phase Is Done

Report your results:
- The design document has been written and saved
- Highlight key decisions, assumptions, and open questions
- Note overall confidence in the document's completeness

Then **re-read the controller** (`controller.md`) for next-step guidance.
