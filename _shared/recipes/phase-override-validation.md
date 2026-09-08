---
name: phase-override-validation
version: 0.1.0
---
# Recipe: Phase Override Validation

Read only when the resolver finds a project override. Use its `WORKFLOW` and
`PHASE_FILE` parameters and the invoking router's completion contract. Read the
override for validation only; return acceptance or a specific rejection reason
to the resolver. Do not execute the phase or its handoff.

## Compatibility Contract

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
