---
name: revise
description: Answer questions about the draft review, apply requested edits, add user-authored findings, and re-present until the user approves posting.
---

# Revise PR Review Skill

You are addressing the local user's feedback on a draft PR/MR review before
it gets posted. Your job is to answer their questions, apply the edits they
asked for, incorporate any findings they want added, and re-present an
updated draft -- repeatable until they approve posting.

## Your Role

Treat the current draft as a living document that isn't posted yet. Nothing
here is sent to the host; this phase only produces a new, better draft.

## Critical Rules

- **Read-only against the reviewed repository.** Like `/start`, this phase
  may re-inspect `{worktree}` for more context when answering a question or
  validating a user-authored finding, but never edits anything in it.
- **No posting.** Only `/publish` posts, and only on a separate,
  fully-approved run.
- **Every edit still honors the resolved comment style.** Reworded comments
  and user-authored findings must still follow `../templates/comment-style.md`
  (or the project's override) -- suggestive tone, no severity labels, no
  "Finding N" headers in posted text.
- **User-authored findings are validated like automated ones.** A finding
  the user asks to add must still cite a real file and a real line inside
  the PR/MR diff before it becomes a draft comment -- see
  `../../_shared/review-protocol.md`'s validation rules.
- **Nothing is dropped silently.** Every item from the previous round --
  kept, dropped, or edited -- must be accounted for in the new draft or
  explicitly noted as removed.

## Process

### Step 1: Read Context

Read `.artifacts/pr-review/{context}/review-metadata.json` for the current
iteration and worktree location, the latest draft
(`02-draft-review-{NNN}.md`), and the matching decisions file
(`decisions-{NNN}.json`).

If `review-metadata.json` is missing, there's no review in progress for
this context -- tell the user and suggest `/start` instead. If the draft or
decisions file for the current iteration is missing or unreadable, or the
worktree directory referenced in metadata no longer exists, stop and report
exactly what's missing rather than guessing its contents or fabricating a
draft to edit.

If the user's requested changes for this round aren't already clear from
the conversation, ask them to state their decisions on the current draft
first (which comments to keep/drop/edit, any questions, any new findings to
add).

### Step 2: Answer Questions

For each question in `decisions-{NNN}.json` (or raised directly in
conversation) about a specific proposed comment:

1. Re-inspect `{worktree}` as needed (read more surrounding context, check
   git history in the worktree, etc.) to give a grounded answer.
2. Answer the question directly and concretely.
3. If the answer reveals the original finding was wrong or overstated,
   adjust the comment's wording or drop it -- don't leave a comment
   standing that your own answer just undermined.

### Step 3: Apply Requested Edits

For each comment the user asked to reword, soften, sharpen, or otherwise
change (including changing or removing its suggestion block): rewrite it,
re-checking it still follows the resolved comment style. For each comment
the user asked to drop: remove it from the draft.

### Step 4: Add User-Authored Findings

For each new finding the user describes (a file/line and a concern they
want raised, with or without a suggested fix):

1. Read the cited location in `{worktree}` to confirm it exists and falls
   inside the PR/MR diff (`git -C {worktree} diff {merge-base-sha} HEAD`).
   If it doesn't -- wrong file, line outside the diff, line doesn't exist
   -- tell the user and ask for a corrected location rather than fabricating
   one.
2. Build the permalink and quote the snippet exactly as `/start` Step 7
   does.
3. Draft the comment in the resolved comment style, including a suggestion
   block only if the user's request implies a concrete mechanical fix.
4. Add it to the draft with its own internal note (category and rationale
   the user gave, or your own assessment if they didn't specify one).

### Step 5: Re-Render the Draft

Increment the round number. Write
`.artifacts/pr-review/{context}/02-draft-review-{NNN}.md` (matching the
format from `start.md` Step 8) reflecting every kept, edited, and
newly-added comment. Cross-check against the previous round's draft: every
prior comment must appear here as kept (possibly edited) or be accounted
for as dropped -- nothing should silently vanish.

### Step 6: Update Metadata

Update `.artifacts/pr-review/{context}/review-metadata.json`: bump
`iteration` to the new round number, update `last_updated`, and set `state`
to `awaiting_decision`.

### Step 7: Present the Updated Draft

Present the same way as `start.md` Step 9 (PR context recap, decision
table including any items still "Disagree"/dropped for transparency, full
comment blocks for every kept comment) plus:

```markdown
## What Changed This Round
{brief list: comments dropped, comments reworded, comments added, and
questions answered}
```

Prompt the user the same way as `start.md` Step 9. Persist their new
decisions to `.artifacts/pr-review/{context}/decisions-{NNN}.json` (matching
the incremented round number).

If the user approves posting as-is, tell them to run `/publish`. If they
have further changes, they can run `/revise` again -- there is no round
limit; this loop continues until the local user is satisfied.

## Output

- `.artifacts/pr-review/{context}/02-draft-review-{NNN}.md`
- `.artifacts/pr-review/{context}/decisions-{NNN}.json`
- Updated `review-metadata.json`

## When This Phase Is Done

Present the updated draft and decision table to the user.

Then **re-read the controller** (`controller.md`) for next-step guidance.
