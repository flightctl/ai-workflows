---
name: continue
description: Resume a gh stack rebase after conflict resolution.
---

# Continue Rebase Stack

## Process

### Step 1: Verify Conflicts Are Resolved

```bash
git diff --name-only --diff-filter=U
```

If any files are listed, conflicts are still unresolved. Tell the user to
resolve them and `git add` each file before running `/continue` again.

### Step 2: Continue the Rebase

```bash
gh stack rebase --continue --remote origin
```

Capture the full output. Three outcomes:

---

**On conflict** — another commit in the stack conflicted. Show the user:

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
then `git add <resolved files>` (do **not** `git commit`), then run `/continue` again.

---

**On unexpected non-zero exit (not a conflict)** — stop and report the full output to
the user. Do not attempt to continue the rebase. Common causes: no rebase is in progress,
network failure, or an unexpected git state. The user must diagnose and resolve before
retrying.

---

**On success** — proceed to Step 3.

---

### Step 3: Report and Hand Off

Tell the user:

> Rebase complete. Run `/validate` to validate each branch before pushing.
