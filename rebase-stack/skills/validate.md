---
name: validate
description: Build and test the stack — the trunk-adjacent branch by default, every branch with --all — then show the push overview.
---

# Validate Rebase Stack

Two modes. The whole stack is rebased either way; only the amount of linting
and testing changes.

| Invocation | Branches linted and tested | Use when |
|------------|---------------------------|----------|
| `/validate` (default) | `{validation-branch}` only — the trunk-adjacent branch, the layer that merges first | Normal case. One suite run instead of N. |
| `/validate --all` | every branch in `{push-list}`, bottom to top | The layers above the bottom matter: the stack's final state must be exercised, an upper layer must stand on its own, or a failure you need to attribute to a specific layer. |

See `../guidelines.md` → "Validation Policy" for the rationale and the limits
of the default.

## Step 1: Parse the Mode

Read `$ARGUMENTS`. Set `{mode}`:

- contains `--all` → `{mode} = all`
- otherwise → `{mode} = tip`

Unrecognized arguments: do not guess. Say which arguments you did not
understand, state that `--all` is the only supported flag, and ask.

Echo the resolved mode before running anything:

> Mode: `{mode}`. Validating `{list of branches}`.

## Step 2: Preflight

Follow `preflight.md`. If a rebase is still in progress, preflight exits 3 —
tell the user to run `/continue` first.

## Step 3: Refresh Remotes and Re-read Health

The fetch here is what makes `--force-with-lease` meaningful in `/push`. Do
not skip it, and do not let `/push` run without it.

```bash
bash "{scripts}/stack-status.sh" \
  < .artifacts/rebase-stack/context.json
echo "status exit: $?"
```

Only exit codes 0 and 1 are report verdicts. **On any other exit — 2 (bad
input) or 3 (a remote could not be fetched) — stop before running any tests
and before writing a validation record.** Relay the script's stderr verbatim.
Exit 3 in particular means the fetch did not happen, so a record written after
it would certify a state that was never compared against the remote, and the
`--force-with-lease` in `/push` would be meaningless.

On exit 0 or 1, stop and report if either is true:

- Any layer still shows `STALE  YES` — the rebase did not finish. Send the user
  back to `/start`.
- Any layer shows `-N` in `VS-PUBLISHED` — the remote has commits you do not.
  Pushing would discard them.

## Step 4: Discover the Validation Commands

Look for the project's lint and unit-test commands, in this order, and stop at
the first source that documents them.

Every line must carry the file it came from. A bare `make test` is not
traceable: when the suite fails you have to say *where the command was defined*
so the user can fix it at the source, and two files can disagree about it.
`grep -H` forces the filename even for a single-file search, and the
`package.json` entries are labelled explicitly:

```bash
for f in AGENTS.md CLAUDE.md CONTRIBUTING.md; do
  [ -f "$f" ] && grep -nHEi '^[[:space:]]*(make|npm|yarn|pnpm|go|cargo|pytest|tox|\./gradlew|mvn) .*(lint|test)' "$f"
done | head -20
[ -f Makefile ] && grep -nHE '^(lint|test|unit-test|test-unit|verify|check):' Makefile
[ -f package.json ] && jq -r '.scripts // {} | to_entries[] | "package.json: \(.key): \(.value)"' package.json
```

Guarding with `[ -f ]` keeps missing files from printing errors, so nothing has
to be redirected away and a real failure stays visible.

If none of these name the commands, ask the user. Do not guess a build system.

Record three things, not two: `{lint-command}`, `{test-command}`, and
`{command-source}` — the file (and line, where grep printed one) each command
came from, e.g. `AGENTS.md:42` or `Makefile:17`. When the user supplies the
commands instead, `{command-source}` is `user-supplied`.

Echo all three back before running anything:

> Lint: `{lint-command}` (from `{command-source}`)
> Test: `{test-command}` (from `{command-source}`)

Carry `{command-source}` into every failure message in Step 5, so a failing or
missing command names the file that defined it rather than appearing out of
nowhere.

## Step 5: Run the Suite

Build the branch list from the mode:

```bash
# {mode} = tip
jq -r '.validationBranch' .artifacts/rebase-stack/context.json

# {mode} = all   (bottom to top)
jq -r '.branches[].name' .artifacts/rebase-stack/context.json
```

First invalidate any previous record. A failed attempt must never leave a
passing record behind for `/push` to accept:

```bash
rm -f .artifacts/rebase-stack/validated
```

Then run `validate-branches.sh` with that list. It creates and removes its own
worktrees, writes one log per branch, and stops at the first failure. Resolve
`{scripts}` as described in `preflight.md` Step 1.

**Never splice a branch name into the command text.** Branch names come from
the repository, not from you: `git` permits `;`, `$(…)`, backticks, spaces and
newlines in a ref name, so a name pasted into a shell line is executable
syntax. Read the names into shell variables from `context.json` at runtime and
pass the variables, quoted. Then a hostile name is only ever an argument that
fails to resolve — never a command. The same rule applies to `{push-remote}`,
`{base-remote}` and `{base}` in Step 7 and in the bisect hint below.

**Default — the trunk-adjacent branch:**

```bash
scripts="{scripts}"
ctx=.artifacts/rebase-stack/context.json
branch=$(jq -r '.validationBranch' "$ctx")
bash "$scripts/validate-branches.sh" \
  --lint "{lint-command}" --test "{test-command}" \
  "$branch"
echo "validate exit: $?"
```

**`--all` — every branch, bottom to top:**

Pass them in `.branches[]` order, which is bottom to top.
`{validation-branch}` is `.branches[0]` — the trunk-adjacent layer — so it is
always the **first** argument, not the last. The script stops at the first
failure, so this order is what attributes a failure to the lowest layer that
breaks. `mapfile` preserves that order and keeps each name a single argument:

```bash
scripts="{scripts}"
ctx=.artifacts/rebase-stack/context.json
mapfile -t branches < <(jq -r '.branches[].name' "$ctx")
bash "$scripts/validate-branches.sh" \
  --lint "{lint-command}" --test "{test-command}" \
  "${branches[@]}"
echo "validate exit: $?"
```

Each branch other than the one already checked out is validated in a throwaway
worktree, so the main working tree is never disturbed. If the suite needs
dependencies installed in the main tree — `node_modules`, `vendor`, `.venv` —
worktrees will fail on missing files. Switch to sequential checkouts:

```bash
scripts="{scripts}"
ctx=.artifacts/rebase-stack/context.json
mapfile -t branches < <(jq -r '.branches[].name' "$ctx")
bash "$scripts/validate-branches.sh" \
  --mode checkout --lint "{lint-command}" --test "{test-command}" \
  "${branches[@]}"
```

Logs are written to `.artifacts/rebase-stack/logs/{branch}-{digest}.log` and
deleted on pass. Never pipe the suite through `head` or `tail` — a truncated
log hides the failure that matters.

**Exit 0** — every requested branch passed. Go to Step 6.

**Exit 1** — a branch failed. The script printed which one and its log path.
Show the tail of that log, then stop:

```bash
tail -40 {log path printed by the script}
```

Name the command that failed **and where it came from** — `{command-source}`
from Step 4 — so the user knows which file to fix if the command itself is
wrong rather than the code.

For `{mode} = all`, the failing branch is the attribution — the first layer
bottom-to-top that breaks:

> `{failing-branch}` failed `{failed-command}` (from `{command-source}`).
> Layers above it were not run; they contain its commits and would fail the
> same way.
> Fix it on that layer: `gh stack checkout {failing-branch}`, commit, then
> `gh stack rebase --upstack --remote {base-remote}`, then `/validate --all`.

For `{mode} = tip`, the failure belongs to `{validation-branch}` — it is the
only layer that ran:

> `{validation-branch}` is the trunk-adjacent layer, so this failure of
> `{failed-command}` (from `{command-source}`) is already
> attributed to it. Fix it there: `gh stack checkout {validation-branch}`,
> commit, then `gh stack rebase --upstack --remote {base-remote}`, then
> `/validate`.
>
> The layers above it were never exercised. Once this one is green, run
> `/validate --all` to cover them.
>
> To narrow the failure to a single commit within this layer:
>
> ```bash
> ctx=.artifacts/rebase-stack/context.json
> branch=$(jq -r '.validationBranch' "$ctx")
> base="$(jq -r '.baseRemote' "$ctx")/$(jq -r '.trunk' "$ctx")"
> git log --oneline "${base}..${branch}"
> git bisect start "$branch" "$base"
> ```

**Do not proceed to Step 6 or `/push` on a failure.**

## Step 6: Record What Was Validated

`/push` reads this record to confirm the validation still matches the current
tips. Record **every** branch in the stack, not only the ones the suite ran against.
`/push` needs to detect an intermediate branch moving even when the tip did
not — otherwise a changed layer gets published having never been tested at that
SHA. The first field says which branches actually ran.

Bind `{validated-branches}` before you run the block below. Its format is
fixed: **the bare branch names the suite actually passed in Step 5, joined by
single ASCII spaces** — exactly the arguments you gave `validate-branches.sh`,
in the same order.

- Separator: one space between names. Nothing else — no commas, no quotes, no
  brackets, no newlines, no leading or trailing space.
- Contents: branch names only, verbatim as they appear in `.branches[].name`.
  No remote prefix, no SHA, no `refs/heads/`.
- Git branch names cannot contain spaces, so the space-delimited `case` match
  below is exact.

It is assigned to a shell **variable** in the block below, never spliced into a
command line, so the names are compared as data and are not shell syntax even
if a branch name contains metacharacters. The value must still expand to text
like `story-1 story-2` and never to `"story-1","story-2"` or
`[story-1 story-2]`.

- `{mode} = tip` → exactly one name, `{validation-branch}` — the
  trunk-adjacent branch, which is `.branches[0]`: `story-1`
- `{mode} = all` → every branch in `{push-list}`, bottom to top, starting with
  `{validation-branch}`: `story-1 story-2 story-3`

Getting the format wrong fails silently: a comma-separated list matches
nothing, every line is written `not-run`, and in `--all` mode `/push` then
reports that no layer was validated.

```bash
# {validated-branches}: branch names that passed Step 5, single-space
# separated, no commas/quotes/brackets — e.g. story-1 story-2
validated_branches="{validated-branches}"
mode="{mode}"
{
  echo "mode=$mode"
  jq -r '.branches[].name' .artifacts/rebase-stack/context.json | while read -r b; do
    case " $validated_branches " in
      *" $b "*) state=validated ;;
      *)        state=not-run ;;
    esac
    printf '%s %s %s\n' "$state" "$b" "$(git rev-parse "$b")"
  done
} > .artifacts/rebase-stack/validated
cat .artifacts/rebase-stack/validated
```

In `--all` mode every line reads `validated`. In the default mode only the
trunk-adjacent branch does, and the rest are recorded as `not-run` so their
SHAs are still pinned.

## Step 7: Push Overview

Return to the branch the user started on (`.currentBranch` in the context),
then build the overview:

`git show-ref --quiet` tests a ref without printing anything, so the
unpublished case needs no error suppression.

The push remote and the branch names are read into variables here for the same
reason as in Step 5: a name that contains shell metacharacters is then only
ever an argument. The trailing `--` in each `git log` separates the ref from
any pathspec, so a branch sharing a filename is never read as a path:

```bash
ctx=.artifacts/rebase-stack/context.json
start_branch=$(jq -r '.currentBranch' "$ctx")
push_remote=$(jq -r '.pushRemote' "$ctx")
git checkout "$start_branch"
jq -r '.branches[].name' "$ctx" | while read -r b; do
  if git show-ref --quiet --verify "refs/remotes/${push_remote}/${b}"; then
    remote_tip=$(git log --oneline -1 "${push_remote}/${b}" --)
  else
    remote_tip='(unpublished)'
  fi
  printf '%-28s local=%s remote=%s\n' "$b" "$(git log --oneline -1 "$b" --)" "$remote_tip"
done
```

Present it as a table. Mark each branch with what actually happened to it —
`PASS` only for branches the suite ran against.

Default mode — only the trunk-adjacent layer, `story-1`, was built and tested:

```text
Branch                      Validation   New tip (local)                 Remote tip (before push)
-----------------------------------------------------------------------------------------------------
story-1 (trunk-adjacent)    PASS         abc1234 EDM-4100: add routing   9f0e1d2 (old)
story-2                     not run      def5678 EDM-4200: add handler   e3f1a2b (old)
story-3 (tip)               not run      ghi9012 EDM-4300: add test      cba3210 (old)
```

`--all` mode:

```text
Branch                      Validation   New tip (local)                 Remote tip (before push)
-----------------------------------------------------------------------------------------------------
story-1 (trunk-adjacent)    PASS         abc1234 EDM-4100: add routing   9f0e1d2 (old)
story-2                     PASS         def5678 EDM-4200: add handler   e3f1a2b (old)
story-3 (tip)               PASS         ghi9012 EDM-4300: add test      cba3210 (old)
```

`not run` is accurate and intentional in the default mode — say so rather than
implying those layers were checked, and mention that `/validate --all` covers
them if the user needs it.

## Step 8: Hand Off

The handoff must state the coverage that was actually achieved. "All layers
validated" is only true in `--all` mode; saying it after a default run is the
claim this workflow exists to avoid.

**`{mode} = tip`** — one layer was built and tested; the rest were pinned, not
checked:

> `{validation-branch}` (trunk-adjacent) passed `{lint-command}` and
> `{test-command}`. Not run: `{other-branches}` — recorded as `not-run` with
> their current SHAs, so `/push` will still refuse if any of them moves.
>
> Coverage: 1 of `{N}` layers built and tested locally. Per-PR CI is the first
> independent check on the layers above it. Run `/validate --all` to cover them
> here instead.
>
> Run `/push` to publish the stack to `{push-remote}` and open any missing PRs.

**`{mode} = all`** — every layer ran:

> `{validated-branches}` passed `{lint-command}` and `{test-command}` —
> all `{N}` layers, bottom to top.
>
> Coverage: `{N}` of `{N}` layers built and tested locally.
>
> Run `/push` to publish the stack to `{push-remote}` and open any missing PRs.

In either case take the branch list from the record just written, not from
memory — `grep '^validated '` and `grep '^not-run '` on
`.artifacts/rebase-stack/validated` give the two sets exactly as `/push` will
read them.
