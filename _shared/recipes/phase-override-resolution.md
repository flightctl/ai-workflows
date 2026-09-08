---
name: phase-override-resolution
version: 0.2.0
---
# Recipe: Phase Override Resolution

Resolves the skill file for a phase, checking for a project-level override
before falling back to the workflow's built-in default.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| WORKFLOW | Yes | Workflow name (e.g., `bugfix`, `design`, `docs-writer`) |
| PHASE_FILE | Yes | The filename to resolve — typically `{phase}.md`, but some workflows use different filenames (e.g., docs-writer maps `/gather` to `gather-context.md`). The caller supplies the mapped filename. |

## Procedure

1. Locate `.workflows/{WORKFLOW}/skills/{PHASE_FILE}` at the consuming repo
   root. The built-in fallback is the same `PHASE_FILE` in the installed
   workflow's `skills/` directory, independent of the caller's location.
2. If no override exists, select the built-in phase. Otherwise, read the
   override for validation only, using the contract below.
3. If validation rejects the override, warn with the specific reason and select
   the built-in phase. Rejection is recoverable; it is not a resolution failure.
4. If using a project override, announce it: *"Using project override:
   {WORKFLOW}/{PHASE_FILE}."* Identify the file using these supplied values;
   do not infer a command name from the filename.
5. Return the selected file's location to the invoking router with its
   instructions unchanged, whether it is an override or the built-in fallback.

The invoking router executes the selected phase and handles its complete
handoff. It preserves required waits and user selections, applies its documented
normalization, and executes each authorized continuation once. This recipe does
not execute phase steps, completion guides, waits, or continuations.

Resolution fails only when the selected built-in fallback cannot be located,
read, or contains no executable phase instructions. Report that failure and
stop. Once the invoking router starts phase execution, it must not switch
implementations; it reports operational errors through the workflow's error
handling.

## Override Validation

A routing refactor must continue to accept previously valid overrides without
requiring edits. Preserve their input and output artifacts, reporting, and
completion behavior. Falling back to a built-in phase does not preserve a
valid override's customization.

Reject an unreadable override or one with no executable instructions. Also
reject unclosed YAML frontmatter or fenced code blocks, or unresolved merge
conflict markers outside quoted or fenced examples. Do not reject an override
for different headings, formatting, or additional phase steps alone.

Validate the completion instructions by their behavior, not by an exact phrase
or the position of a sentence. Read the override's executable instructions and
the invoking router's completion contract without executing either. Examples of
supported completion behavior include:

- Reporting results and re-reading the workflow's controller for next steps.
- Returning to the invoking workflow router for completion guidance.
- Reading the workflow's completion guide.

These are examples, not an exhaustive grammar. Equivalent wording and existing
phase-specific handoffs remain valid. A dispatcher that normalizes controller
returns must accept legacy overrides that request those returns, even when the
current built-in phase uses a different exit. During validation, interpret the
whole handoff under the router's documented normalization solely to assess
compatibility, including user selections and continuations. Leave the handoff
unchanged for the router to execute. Do not reject a legacy handoff solely
because it differs from the current built-in phase's completion instructions.

Reject completion behavior only when it is absent or incompatible with the
workflow's contract: for example, a controller mentioned only in an example,
conflicting destinations, or advancing without user selection where the
contract requires it. An explicit terminal sentence is unnecessary when the
workflow's router already defines how a phase returns after its steps finish.
A documented stop for missing input, an operational error, or a user decision
is a valid pause or failure outcome, not a missing completion instruction.

Legacy controller-return exits remain supported for existing overrides. A
dispatcher may normalize them to its completion guide to preserve the original
next-step behavior; this compatibility has no planned removal. Controller-based
workflows may continue to use controller returns directly.
