# Comment Style (Default)

Default tone and structure rules for every comment this workflow drafts and
posts. `skills/start.md`, `skills/revise.md`, and `skills/publish.md` all
resolve and apply this file (or a project override — see "Resolution"
below) when rendering the text that will actually be posted to the PR/MR.

## Resolution

Check for a project-level override before falling back to this built-in
default. Use the first match found:

1. **`{worktree}/.pr-review/templates/comment-style.md`** — the reviewed
   repository's own preference, checked into its own repo (analogous to how
   the `prd` workflow's own template can be overridden by a project). Since
   this workflow comments on a project it doesn't own, the project's own
   conventions take priority over this default.
2. **This file** — the workflow's built-in default.

If a candidate override is missing, unreadable, or empty, warn the user and
fall back to this built-in default. If using a project override, announce
it: *"Using project override for comment style."*

## Tone

- **Suggestive, not directive.** Frame every comment as a question or an
  option, never as an instruction.
  - Use: "Should we add a nil check here?", "What if this used a map
    instead?", "Would it make sense to extract this into a helper?"
  - Avoid: "Add a nil check here.", "You must use a map instead.", "Please
    extract this into a helper."
- **State the concern, then the option.** Lead with what could go wrong or
  what could improve, phrased plainly, then offer the suggested direction as
  a question — don't bury the concern inside a compound question.
- **No hedging filler.** Suggestive does not mean vague. State the specific
  issue; only the framing of the fix is a question, not the existence of the
  issue.

## Structure

- **No severity or category labels in posted content.** `CRITICAL`,
  `HIGH`, `Correctness`, `Security`, etc. are internal-only labels used
  while presenting the draft for local approval (see `skills/start.md` Step
  10) — they never appear in the text that gets posted to the PR/MR.
- **No "Finding N" headers in posted content.** Each posted comment is
  anchored to its own line by the host's own UI; it doesn't need a numbered
  heading to stand apart from other comments.
- **Self-contained.** Each posted comment includes the concern and (when
  applicable) the suggested-change block — a reader should not need to
  cross-reference another comment to understand this one.
- **Review summary is always fixed.** The top-level body of the posted
  review (GitHub) or the separate summary note (GitLab) is always the
  literal string `See comments below` — regardless of how many comments
  there are, their severity, or their category. Never restate counts,
  severities, or an overall verdict there.

## Suggested-change blocks

- Include a suggestion block only when the fix is a concrete, mechanical
  replacement of the flagged lines (e.g., a rename, a null check, a
  corrected condition).
- Omit the block entirely for conceptual or design-level findings (e.g., "is
  this abstraction worth its complexity?") — do not fabricate a diff just to
  fill the field. The suggestive-tone explanation stands alone in that case.
- **The fence syntax differs by provider — this is not cosmetic, using the
  wrong one means the host will not recognize the block as an applicable
  suggestion:**
  - **GitHub:** a bare ` ```suggestion ` fence works for both single-line
    and multi-line replacements.
  - **GitLab:** the fence must carry a line-offset annotation,
    ` ```suggestion:-{lines_above}+{lines_below} `, where the offsets are
    relative to the anchored comment line. Use `-0+0` when the suggestion
    replaces only the anchored line itself; use `-0+2`, for example, when it
    replaces the anchored line plus the two lines below it. A bare
    ` ```suggestion ` with no offset is GitHub-only syntax and will not
    apply correctly on GitLab.

## Example (built-in default)

GitHub:

`````markdown
This loop re-reads `config.json` on every iteration, which could get slow
for large inputs. Should we hoist the read outside the loop?

```suggestion
config = load_config("config.json")
for item in items:
    process(item, config)
```
`````

The same finding on GitLab, replacing the anchored line plus the one below
it (`-0+1`):

`````markdown
This loop re-reads `config.json` on every iteration, which could get slow
for large inputs. Should we hoist the read outside the loop?

```suggestion:-0+1
config = load_config("config.json")
for item in items:
    process(item, config)
```
`````
