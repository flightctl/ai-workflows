---
name: start
description: Verify gh-stack, detect or initialize the stack, then rebase onto the updated base.
---

# Start Rebase Stack

## Process

### Step 1: Verify gh-stack Extension

```bash
gh extension list 2>/dev/null | grep -q 'github/gh-stack'
```

If not found, install it:

```bash
gh extension install github/gh-stack
```

If the installation fails, stop and report the error. Do not proceed.

Then configure git:

```bash
git config rerere.enabled true
```

If multiple remotes are configured (check with `git remote`), also run:

```bash
git config remote.pushDefault origin
```

### Step 2: Verify Clean Working Tree

```bash
git status
```

If there are unstaged changes or untracked files that could interfere, stop
and ask the user to stash or commit them first.

### Step 3: Detect or Initialize the Stack

Check if the current branch belongs to a tracked stack:

```bash
gh stack view --json 2>&1; echo "exit:$?"
```

**If exit code 0**: stack already exists. Proceed to Step 4.

**If exit code 2 ("not in a stack")**: adopt the existing branches.

**Any other exit code**: stop and report the full output to the user. Do not proceed.

Discover branches from the commit graph. If the user provided a base branch,
use it; otherwise default to `main`:

```bash
git log --reverse --oneline --decorate origin/{base}..HEAD
```

Read through the output and collect each local branch label the first time it
appears, in that order. Exclude `HEAD ->` aliases and `origin/` remote-tracking
refs. The resulting list is ordered bottom-to-top (closest to trunk first).

Present the discovered list to the user and confirm the order before proceeding.
If the order is incorrect, ask the user to provide the correct branch list
(bottom to top) and use their provided order in the `gh stack init` call.

Then initialize the stack:

```bash
gh stack init --base {base} \
  {branch-1} \
  {branch-2} \
  ...
```

If `gh stack init` fails for any reason (missing base, bad branch names, nonexistent
branches), stop and report the error. Do not proceed.

`gh stack` will report "Adopted N branches" and detect any existing PRs
automatically. Verify with:

```bash
gh stack view --json
```

### Step 4: Rebase

```bash
gh stack rebase --remote origin
```

Capture the full output. Two outcomes:

---

**On success** — proceed to Step 5.

---

**On conflict** — `gh stack rebase` will stop. Show the user:

1. The commit that caused the conflict:
   ```bash
   git rebase --show-current-patch 2>/dev/null | head -10
   ```
2. The conflicting files:
   ```bash
   git diff --name-only --diff-filter=U
   ```

Then ask:

> A conflict was detected. How would you like to proceed?
> - **Fix it for me** — I'll attempt to resolve the conflicts and continue.
> - **I'll fix it** — Pause here; I'll resolve the conflicts manually and run `/continue` when ready.

**Stop here.** Wait for the user's choice before doing anything.

If the user asks you to fix it: examine each conflicting file. For files where
the conflict is "old version vs evolved version" (this branch carries a stale
copy of a commit that the lower branch already updated), apply `--ours` — in a
rebase, `--ours` is the onto-branch (the lower branch's updated tip):

```bash
git checkout --ours <file>
git add <file>
```

For files with genuinely new code on both sides, show the conflict markers and
ask the user which version to keep before proceeding.

Once all files are resolved and staged, run `gh stack rebase --continue --remote origin` automatically.

If the user wants to fix it themselves: instruct them to resolve the conflicts,
then `git add <resolved files>` (do **not** `git commit`), then run `/continue`.

---

### Step 5: Hand Off

Tell the user:

> Rebase onto `origin/{base}` complete. Run `/validate` to validate each
> branch before pushing.
