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
2. If no override exists, use the built-in phase. Otherwise, read the override
   and validate it using the contract below before executing any of its steps.
3. If validation rejects the override, warn with the specific reason and use
   the built-in phase. Rejection is recoverable; it is not a resolution failure.
4. If using a project override, announce it: *"Using project override for
   /{phase}."* Read and execute the selected file only after resolution.

Resolution fails only when the selected built-in fallback cannot be located,
read, or contains no executable phase instructions. Report that failure and
stop. Do not switch implementations after phase execution has started; report
operational errors through the invoking workflow's error handling.

## Override Validation

Reject an unreadable override or one with no executable instructions. Also
reject unclosed YAML frontmatter or fenced code blocks, unresolved merge
conflict markers, or a missing or unsupported terminal instruction. These are
the malformed-file conditions; do not reject an override for different heading
names, formatting, or additional phase steps alone.

The terminal instruction is the last executable instruction in the phase's
completion section, or at the end of the file if there is no completion section.
Ignore blank lines, headings, comments, and quoted or fenced examples. Join
wrapped lines and ignore Markdown emphasis, inline-code delimiters, an optional
leading "Then", capitalization, and trailing punctuation when identifying the
following imperative forms:

| Exit | Accepted instruction forms |
|------|----------------------------|
| Router return | `Return to the invoking router`, `Return to the invoking workflow router`, or `Return control to the invoking router` |
| Completion guide | `Read` or `Re-read` followed by a named completion guide (a filename or Markdown link), or `Read the completion guide` when the router names that guide |
| Controller return | `Re-read the controller`, `Re-read this controller`, or `Re-read` followed by the workflow's controller filename or Markdown link |

A form may include a target in parentheses and a suffix such as "for next-step
guidance" or "and follow it". It must direct that exit after reporting; a
mention, negated instruction, or conditional exit with a path that never
returns is insufficient. Reject conflicting exit destinations or additional
phase work after the terminal instruction.

Read the built-in phase's completion instructions for comparison, without
executing them. Compare the override's destination with the built-in's after
applying only the invoking router's documented normalization. Accept equivalent
destinations even when the wording or exit form differs. Without documented
normalization, the exit and destination must match. If the built-in has no
explicit terminal instruction, use the router's documented completion contract;
if neither defines a comparable destination, warn and use the built-in phase.

Legacy controller-return exits remain supported for existing overrides. A
dispatcher may normalize them to its completion guide to preserve the original
next-step behavior; this compatibility has no planned removal. Controller-based
workflows may continue to use controller returns directly.
