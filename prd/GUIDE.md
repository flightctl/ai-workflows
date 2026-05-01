# PRD Workflow Guide

The PRD workflow turns Jira requirements into a structured, reviewable Product Requirements Document. It handles the mechanical work — gathering context, enforcing structure, maintaining traceability — so you can focus on the decisions that matter: what to build, what's out of scope, and what needs more thought.

This guide explains how to drive the workflow. For the command reference and artifact layout, see [README.md](README.md).

## Design Principles

These principles shaped every phase of the workflow. Understanding them will help you predict how the workflow behaves and why.

**Fidelity to source material.** Every requirement in the PRD traces back to a Jira issue, a clarification you gave, or a direct instruction. The workflow does not invent requirements or fill gaps with assumptions.

**User agency.** The PRD represents *your* understanding of the problem, not the AI's interpretation. The workflow never auto-advances between phases — you decide when to move on, go back, or skip ahead.

**Scope protection.** The workflow will never silently simplify, defer work to "v2," or label things as "future enhancements" to reduce scope. If scope needs to change, it flags the issue and asks you to decide.

**Locked decisions are binding.** When you answer a clarification question definitively ("TCP only, not UDP"), that answer becomes a locked decision. No later phase — draft, revise, or review response — can contradict it without your explicit override.

**Jira is read-only.** The workflow reads from Jira to gather context. It never creates, modifies, or comments on Jira issues.

## The Six Phases

The workflow has six phases. The typical path is linear, but you can loop back or skip phases depending on your situation.

```
/prd:ingest → /prd:clarify → /prd:draft → /prd:revise → /prd:publish → /prd:respond
```

### Ingest

**Command:** `/prd:ingest JIRA-KEY`

You provide a Jira issue key. The workflow fetches the issue's description, acceptance criteria, comments, and attachments. It also fetches laterally linked issues (one level deep — related issues, not children or epics).

Everything is captured as-is, with no interpretation. The output is a raw requirements document that becomes the foundation for everything that follows.

If you re-run ingest later (because the Jira issue was updated), the workflow diffs the old and new content before overwriting and warns you if downstream artifacts already exist.

### Clarify

**Command:** `/prd:clarify`

The workflow analyzes the raw requirements and identifies gaps: unclear scope boundaries, missing edge cases, contradictions, unstated assumptions. It asks you 3-5 specific questions per round — questions with enough context that you can answer them without re-reading the entire issue.

Your answers are recorded in a clarification log. When you give a definitive answer, it becomes a **locked decision** that binds all subsequent phases.

The workflow tracks exit criteria and tells you when it thinks clarification is sufficient: requirements are enumerable, scope boundaries are clear, no unresolved contradictions, and key assumptions are confirmed.

**When to skip:** If your Jira issue already has tight, unambiguous requirements, you can go straight to `/prd:draft`. The workflow will still work — it just won't have clarification context to draw on.

### Draft

**Command:** `/prd:draft`

The workflow generates a PRD following a structured template with eight sections:

1. **Problem Statement** — why this work is needed and who's affected
2. **Goals and Non-Goals** — measurable outcomes, what's explicitly out of scope, optional success metrics
3. **Requirements** — functional requirements (FR-1, FR-2, ...) and non-functional requirements (NFR-1, NFR-2, ...) under a single section
4. **Acceptance Criteria** — testable assertions defining "done"
5. **Assumptions** — statements believed true but not yet verified (optional, omitted if none)
6. **Dependencies** — teams or systems this depends on (optional, omitted if none)
7. **Risks** — product risks with owners and mitigations (optional, omitted if none)
8. **Open Questions** — unresolved questions for reviewers to decide during PR review (optional, see below)

Every requirement gets a stable ID (FR-1, NFR-1) and a source marker indicating where it came from: `[Jira: EDM-2324]`, `[Clarify: R1.Q3]`, or `[User]`.

Before presenting the draft, the workflow runs a coverage check (did anything from the source material get dropped?) and resolves outstanding assumptions with you.

**Template overrides:** Projects can provide their own PRD template. The workflow checks these locations in order: a path specified in the project's `CLAUDE.md` or `AGENTS.md`, then `.prd/templates/prd.md` at the project root, then the built-in default.

### Revise

**Command:** `/prd:revise`

You review the draft and request changes — specific edits, directional feedback, new information, or deletions. The workflow applies your changes and runs a consistency check: if you changed a goal, do the requirements still support it? If you narrowed scope, are non-goals updated?

Requirement IDs are stable across revisions. If a requirement is removed, it gets a tombstone (`~~FR-3~~ Removed — reason`) so that IDs are never reused, which matters for traceability into downstream design and implementation work.

You can run `/prd:revise` as many times as needed. Each round updates the same artifact.

### Publish

**Command:** `/prd:publish`

The workflow copies the PRD to a docs repository and creates a **draft** GitHub PR. It asks you to confirm the details first: base branch, release name, feature slug, and branch name.

On first use, it asks for your docs repo location and saves the configuration to `.artifacts/prd/config.json`. Subsequent PRDs reuse this configuration without asking again.

The PR is always created as a draft. It includes a description with a link to the Jira issue, a summary of what the PRD covers, and guidance for reviewers on what to focus on.

**When to skip:** For internal-only PRDs that don't need external review, you can stop after `/prd:revise`.

### Respond

**Command:** `/prd:respond`

This phase handles the PR review cycle. See the dedicated section below.

## The Artifact Trail

Each PRD produces a set of numbered artifacts in `.artifacts/prd/{issue-number}/`:

| File | Created by | Purpose |
|------|-----------|---------|
| `01-requirements.md` | `/prd:ingest` | Raw Jira data, uninterpreted |
| `02-clarifications.md` | `/prd:clarify` | Q&A log with locked decisions |
| `03-prd.md` | `/prd:draft` | The PRD itself (updated by `/prd:revise`) |
| `04-pr-description.md` | `/prd:publish` | PR description text |
| `05-review-responses.md` | `/prd:respond` | Review comment log, round by round |

These are plain markdown files. You can inspect any of them, hand them to a colleague, or use them as input to downstream workflows (like the design workflow). The numbering reflects the order they're created, making it easy to follow how the PRD evolved.

## How Phases Connect

The typical path is linear, but the workflow supports both skipping ahead and going back:

**Skipping forward:**
- **Skip clarify** — if your Jira issue already has tight, unambiguous requirements, go straight from `/prd:ingest` to `/prd:draft`.
- **Skip publish and respond** — for internal-only PRDs that don't need external review, stop after `/prd:revise`.

**Going back:**
- **Draft reveals gaps** — if `/prd:draft` uncovers ambiguities that weren't caught during clarify, go back to `/prd:clarify` before continuing.
- **Review feedback is substantial** — if PR reviewers surface significant changes, use `/prd:revise` to update the PRD, then push the update.
- **Respond surfaces new requirements** — if a reviewer's comment amounts to a new requirement, the workflow flags it for your decision. You can accept it (revise the PRD) or explain why it's out of scope.

The workflow never auto-advances. After each phase, it recommends a next step, but you choose.

## The PR Review Cycle

Once you've published, the review cycle works like this:

1. **Reviewers leave comments** on the PR — inline on specific lines or top-level.

2. **You run `/prd:respond`** to fetch and process all comments. The workflow categorizes each one:
   - **Clarification request** — needs a reply, no PRD change
   - **Factual correction** — update the PRD, acknowledge in reply
   - **Scope question** — reply explaining scope; may trigger a revision
   - **New requirement** — flagged for your decision
   - **Open question resolution** — a reviewer answered one of your open questions
   - **Approval / positive** — acknowledge
   - **Out of scope** — explain why

3. **You approve each response.** The workflow proposes a reply for every comment and indicates whether a PRD change is needed. You approve, edit, or reject each one before anything is posted. Nothing goes out without your sign-off.

4. **PRD updates are pushed automatically.** If approved responses require PRD changes, the workflow updates both the local artifact and the docs repo copy, commits, and pushes to the PR branch.

5. **Repeat as needed.** Run `/prd:respond` again when new comments arrive. Each round is logged in `05-review-responses.md` with a round number, date, and summary of what changed.

## Open Questions as a Decision Tool

The Open Questions section of the PRD is not a dumping ground for "things we haven't figured out." It's a structured way to get specific decisions from specific people during PR review.

Each open question has three parts:
- **The question itself** — clear and answerable
- **An owner** — who should answer it (a specific person, role, or team)
- **An impact statement** — which part of the PRD changes depending on the answer

**Example:**
> **8.1** Should port mapping support UDP in addition to TCP?
> *Owner: networking team. Impact: FR-4 scope, NFR-2 performance targets.*

When a reviewer answers an open question during PR review, `/prd:respond` handles the resolution:

1. It identifies which open question the discussion addresses.
2. It synthesizes the review thread into a proposed answer.
3. It determines the target section based on the question's impact field.
4. It presents the resolution to you for approval.
5. On approval, it incorporates the answer into the target section in final form — not as a narrative of the discussion, but as a proper requirement or constraint.
6. It removes the resolved question from the Open Questions section.
7. If all open questions are resolved, the entire section is removed.

This turns PR review into a structured decision-making process. Instead of "LGTM" or vague "needs changes" comments, reviewers know exactly what you need from them.

Open questions must be product-scope: "Should we support UDP?" is appropriate. "When will the backend team be available?" is not — that's a project management question.

## Guardrails Worth Knowing

These are the behaviors most likely to surprise you on first use:

**No scope reduction.** The workflow will not say "future enhancement," "out of scope for v1," or "deferred" unless you explicitly direct it to. If the source material says something is needed, it stays in the PRD. If scope genuinely needs to shrink, you make that call and the workflow records it with a source marker.

**Locked decisions are binding.** If you said "Postgres, not SQLite" during clarification, the draft phase will not mention SQLite. If a PR reviewer later suggests SQLite, `/prd:respond` will flag the conflict with your locked decision. You can override it, but the workflow won't silently let it through.

**Nothing is posted without your approval.** During `/prd:respond`, every proposed reply is shown to you first. You approve, edit, or reject each one individually.

**Requirement IDs are stable.** FR-1 stays FR-1 across revisions. Removed requirements get tombstones, not reassigned IDs. This matters because downstream work (design documents, implementation stories) references these IDs.

**Template is overridable.** If the default PRD structure doesn't fit your project, you can provide a custom template. The workflow checks for project-specific templates before falling back to the default.

**Optional sections are omitted, not filled with placeholders.** If the source material doesn't mention dependencies, the Dependencies section is left out entirely rather than included with "None identified" or "TBD."
