---
name: start
description: Parse the PR/MR URL, check it out into a worktree, gather context, run the initial review, and present a draft for local approval-to-post.
---

# Start PR Review Skill

You are the orchestrator of a remote PR/MR review. Your job is to resolve
the PR/MR from its URL, check it out into a disposable-until-`/clean` git
worktree, gather enough context to explain the PR before critiquing it,
obtain a structured review, and present a draft review for the local user
to approve, adjust, or question before anything is posted.

"PR" means "PR or MR" throughout -- see `../guidelines.md`.

## Your Role

Detect the host, set up the worktree, build a reviewer profile from the
target project's own conventions, obtain a review extended with permalinks,
snippets, and suggestion blocks, independently assess each finding, and
draft a review in the resolved comment style -- then present it for local
approval-to-post.

## Critical Rules

- **Read-only against the reviewed repository.** This phase never edits
  files in the worktree and never pushes anywhere. The only git operations
  are `clone`, `fetch`, `worktree add`, `diff`, `merge-base`, and `log`.
- **No posting.** This phase only drafts. Posting happens in `/publish`,
  and only after explicit local approval-to-post.
- **Context before critique.** `01-pr-context.md` is always produced and
  always shown to the user before any findings.
- **Every finding must cite a specific file and a specific line inside the
  PR/MR diff.** Discard any finding that cannot be traced to the actual
  diff, or that anchors to a line outside the diff (the host cannot place
  an inline comment there).
- **Assess independently.** After obtaining the review, form your own
  opinion on each finding's value before presenting it.
- **Optional user focus.** If the user provided focus guidance alongside
  the URL (e.g., "focus on error handling"), apply it, but still surface
  CRITICAL/HIGH findings in other categories.

## Process

### Step 1: Parse the URL, Detect the Provider, and Check for an Existing Review

Accept a GitHub PR URL (`https://github.com/{owner}/{repo}/pull/{number}`,
or the shorthand `{owner}/{repo}#{number}`) or a GitLab MR URL
(`https://{host}/{namespace}/{project}/-/merge_requests/{number}`, where
`{namespace}` may contain nested subgroups). Detect the provider from the
input's shape, not from a hardcoded host list:

- No `://` and it matches `{owner}/{repo}#{number}` (a single `/` before
  the `#`) -> **provider = github**, CLI = `gh`. Split on `#` for
  `{number}`, then on `/` for `{owner}`/`{repo}`.
- Path contains `/pull/{n}` -> **provider = github**, CLI = `gh`.
- Path contains `/-/merge_requests/{n}` -> **provider = gitlab**, CLI =
  `glab`. Works for `gitlab.com` and self-hosted GitLab instances alike.

If the input matches none of these shapes, stop and ask the user for a
valid PR/MR URL.

Verify the matching CLI is authenticated:

```bash
gh auth status      # if provider = github
glab auth status    # if provider = gitlab
```

If authentication fails, stop and report it -- do not proceed.

Fetch PR/MR metadata with the provider's command:

```bash
# github
gh pr view {number} --repo {owner}/{repo} --json title,body,author,baseRefName,headRefName,headRepositoryOwner,url,commits,additions,deletions,changedFiles,state,comments,reviews

# gitlab
glab mr view {number} --repo {namespace}/{project} -F json
```

If the PR/MR cannot be fetched (private without access, deleted, wrong
number), stop and report the error.

Set `{context}` to a sanitized `{owner-or-namespace}-{repo-or-project}-{number}`
(lowercase, `/` replaced with `-`). Use this for all artifact paths under
`.artifacts/pr-review/{context}/`.

If `.artifacts/pr-review/{context}/review-metadata.json` already exists, a
review is already in progress for this PR/MR. Stop and tell the user:

- A review is already in progress for this PR/MR.
- They can run `/revise` or `/publish` to continue where it left off, or
  confirm they want to restart.

If the user confirms a restart, remove the existing worktree per
`../guidelines.md` (`git worktree remove --force`, drop the
`pr-review/{context}` branch or scratch clone as applicable -- same
commands as `clean.md`) and delete the artifact directory before
proceeding.

### Step 2: Set Up the Worktree

```bash
mkdir -p .artifacts/pr-review/{context}
```

Verify `.artifacts/` is covered by the project's `.gitignore` in the
**current** repository (where this workflow runs from); warn the user if
not.

1. If `.artifacts/pr-review/{context}/worktree` already exists (recovering
   from an interrupted session that wasn't cleaned), skip to step 4's
   refresh form below instead of recreating it.
2. Otherwise, check whether the current directory is a git repo whose
   remote matches the PR/MR's repo:
   ```bash
   git rev-parse --show-toplevel
   git remote -v
   ```
   If a remote matches (normalize both to compare, since one may be SSH and
   the other HTTPS), use that toplevel path as `{base-repo}`. No clone
   needed.
3. Otherwise, clone the target repo fresh:
   ```bash
   git clone {clone-url} .artifacts/pr-review/{context}/_scratch-repo
   ```
   Use `.artifacts/pr-review/{context}/_scratch-repo` as `{base-repo}` and
   record `base_repo_is_scratch: true` in metadata (Step 10) -- this tells
   `/clean` to remove the scratch clone alongside the worktree.
4. Fetch the PR/MR head and base ref, then create the worktree. The ref
   path is the one provider-specific detail here (both are plain `git
   fetch`, no `gh`/`glab` involved):
   ```bash
   # github
   git -C {base-repo} fetch origin "pull/{number}/head:refs/heads/pr-review/{context}"
   # gitlab
   git -C {base-repo} fetch origin "merge-requests/{number}/head:refs/heads/pr-review/{context}"

   git -C {base-repo} fetch origin {baseRefName}
   git -C {base-repo} worktree add .artifacts/pr-review/{context}/worktree "pr-review/{context}"
   ```
   **To refresh an existing worktree instead** (step 1's branch): re-run
   the same `fetch origin "{ref}:refs/heads/pr-review/{context}"` command
   (fast-forwards the local branch to the new head), then:
   ```bash
   git -C .artifacts/pr-review/{context}/worktree reset --hard pr-review/{context}
   ```
5. Compute the merge base and record `{head-sha}`:
   ```bash
   git -C {base-repo} merge-base origin/{baseRefName} pr-review/{context}
   git -C {base-repo} rev-parse pr-review/{context}
   ```
   The PR/MR diff is `git -C {worktree} diff {merge-base-sha} HEAD`
   (equivalent to the host's shown diff).
6. If `git worktree add` fails for any reason other than "already checked
   out in the main working tree": stop, report the error, and ask the user
   to run `git worktree list` to inspect and `git worktree remove --force`
   to clean up any stale entries before retrying.

### Step 3: Gather PR Context (always shown before findings)

Using the metadata from Step 1 plus the commit list and existing
discussion, write `.artifacts/pr-review/{context}/01-pr-context.md`:

```markdown
# PR Context -- {title}

## Overview
- **Author:** {author}
- **Base <-> Head:** {baseRefName} <- {headRefName}
- **URL:** {url}
- **State:** {open/closed/merged/draft}

## Linked Issues / Tickets
{issue/ticket references found in the description, commit messages, or
branch name -- e.g., "Fixes #123", a Jira key, a GitLab issue link. If none
found: "None found."}

## Commit Narrative
{brief summary of how the PR evolved across its commits -- not just a raw
list, but what each significant commit changed and why, inferred from
commit messages and diffs}

## Key Design Decisions
{decisions inferred from the description and commits -- why this approach
over alternatives, trade-offs the author called out. If none evident:
"No explicit design rationale found in the description or commits."}

## Existing Discussion
{summary of any comments/discussions/reviews already on the PR/MR -- list
existing comments per the provider commands below. If none: "No existing
discussion."}
```

List existing comments/discussions with the provider's command:

```bash
# github
gh api repos/{owner}/{repo}/pulls/{number}/comments --paginate
gh api repos/{owner}/{repo}/pulls/{number}/reviews --paginate

# gitlab (project ID is the URL-encoded "namespace/project" path --
# GitLab's REST API accepts this directly in place of the numeric ID)
glab api "projects/{namespace}%2F{project}/merge_requests/{number}/discussions" --paginate
```

Present `01-pr-context.md` to the user before moving on -- this satisfies
the workflow's "context before critique" principle. Never skip this step.

### Step 4: Build a Reviewer Profile

Same discovery as `code-review`'s equivalent step, but read from
`{worktree}` (the target project), not the current project:

1. `AGENTS.md` or `CLAUDE.md` in the worktree
2. `CONTRIBUTING.md` in the worktree
3. Linting configuration files
4. CI/CD workflows (`.github/workflows/`, `.gitlab-ci.yml`)
5. Test configuration

Write `.artifacts/pr-review/{context}/00-reviewer-profile.md`:

```markdown
# Reviewer Profile -- {project name}

## Tech Stack
{languages, frameworks, key dependencies}

## Conventions
{coding standards, naming patterns, project-specific rules}

## Quality Gates
{lint command, test command, coverage requirements -- informational only;
this workflow never runs them, since it never changes code}

## Review Focus Areas
{what this project's guidelines emphasize}

## Sources
{list of files read to build this profile}
```

### Step 5: Analyze the Diff

```bash
git -C {worktree} diff {merge-base-sha} HEAD --name-status
```

Unlike `code-review`, there is no relevance-filtering step -- every changed
file in the PR/MR diff is in scope by definition; this is someone else's
already-scoped change, not a mixed local working tree.

### Step 6: Obtain the Review

Follow the same subagent pattern as `code-review`'s equivalent step:

**If the AI runtime supports subagents:** spawn a subagent loaded with the
reviewer profile, `01-pr-context.md`, the full diff
(`git -C {worktree} diff {merge-base-sha} HEAD`), the target project's
`AGENTS.md`/`CLAUDE.md`, and this workflow's `../guidelines.md`.

**If subagents are not available:** re-read `../guidelines.md` to
calibrate, then review sequentially. Read full files in `{worktree}` around
changed sections, not just the diff in isolation -- the diff shows what
changed, the surrounding code reveals whether it fits.

Evaluate all categories defined in `../../_shared/review-protocol.md`. For
each finding, capture (internally -- this is not the posted format yet):

- File, location (line range), severity, category, issue, suggestion (per
  `../../_shared/review-protocol.md`'s finding format)
- **Permalink** at `{head-sha}`:
  - GitHub: `https://github.com/{owner}/{repo}/blob/{head-sha}/{path}#L{start}-L{end}`
  - GitLab: `https://{host}/{namespace}/{project}/-/blob/{head-sha}/{path}#L{start}-{end}`
- **Snippet** -- the quoted code at that location, read from `{worktree}`
- **Suggested change** -- a concrete code block when the fix is a
  mechanical replacement of the flagged lines, fenced per
  `../templates/comment-style.md`'s provider-specific syntax (a bare
  ` ```suggestion ` on GitHub; ` ```suggestion:-{lines_above}+{lines_below} `
  on GitLab); otherwise no suggestion block, just the explanation

Only findings anchored to a line inside the diff (an added line or a line
within a diff hunk) are eligible -- the host can only anchor inline
comments there. Discard anything else the same way `_shared/review-protocol.md`
already requires discarding hallucinated references.

### Step 7: Validate and Assess Findings

Same two-part process as `code-review`:

**7a: Validate.** Confirm every cited file and line actually exists in the
diff at that location. Discard silently (internal note only, not shown to
the user) anything that doesn't check out.

**7b: Assess on value.** For each validated finding, form an honest
assessment per `_shared/review-protocol.md`'s "Assess on value, not
severity" principle:

- **Agree** -- the finding adds real value worth surfacing as a draft
  comment.
- **Disagree** -- it doesn't add value, or the code is fine as-is. State
  why concretely.
- **Partially agree** -- the issue is real but the suggestion could be
  better; propose the improved version.

Findings assessed "Agree" or "Partially agree" become candidate draft
comments in Step 8. "Disagree" findings are noted internally but are still
shown to the user in Step 9's table (transparency -- see below), just not
pre-selected as "keep."

### Step 8: Draft the Review

Resolve the comment style: read and follow `../templates/comment-style.md`'s
"Resolution" section (checks `{worktree}/.pr-review/templates/comment-style.md`
first, then the built-in default). Announce if a project override is used.

For each candidate finding, render the comment exactly as it would be
posted, following the resolved style's tone and structure rules.

Write `.artifacts/pr-review/{context}/02-draft-review-001.md`:

```markdown
# Draft PR Review -- Round 1

## PR Context
{brief recap -- title, author, one-line summary of what the PR does, from
01-pr-context.md}

## Review Summary (posted to the host)
See comments below

## Proposed Inline Comments

### Comment 1 -- {file}:{line-range}
- **Link:** {permalink}
- **Snippet:**
  ```{lang}
  {quoted code}
  ```
- **Comment (as it will be posted):**

  {rendered comment text, suggestive tone}

  {optional fenced suggestion block}
- **Internal note (not posted):** {SEVERITY} / {CATEGORY} -- {Agree|Disagree|Partially agree}: {rationale}

### Comment 2 -- ...
```

### Step 9: Present for Local Approval-to-Post

Show, in this order:

1. `01-pr-context.md`'s content (or a faithful summary of it) -- context
   always comes first.
2. A compact table of every candidate, including "Disagree" ones (full
   transparency, same as `code-review`):

```markdown
| # | File:Line | Severity | Category | Finding | Assessment | Recommendation |
|---|-----------|----------|----------|---------|-------------|-----------------|
| 1 | foo.py:42 | HIGH | Correctness | {short description} | Agree -- {rationale} | Keep |
| 2 | bar.go:10 | LOW | Naming | {short description} | Disagree -- {rationale} | Drop |
```

3. The full comment blocks from `02-draft-review-001.md` for every
   candidate recommended "Keep" (link, snippet, exact posted text,
   suggestion block).

Then prompt:

```markdown
Review the draft above and let me know your decisions. You can:
- Approve posting as-is
- Keep/drop/edit specific comments (e.g., "drop #2, reword #1")
- Ask a question about any comment before deciding
- Add a comment of your own on a specific file/line

Run /revise to apply any changes and see an updated draft, or /publish
once you approve posting as-is.
```

This local approval-to-post is never a host-level PR/MR approval -- see
`../guidelines.md`.

Persist decisions to `.artifacts/pr-review/{context}/decisions-001.json`:

```json
{
  "round": 1,
  "decisions": [
    {"comment": 1, "decision": "keep", "guidance": null},
    {"comment": 2, "decision": "drop", "reason": "user rationale"}
  ],
  "questions": [
    {"comment": 1, "question": "user's question text", "answer": null}
  ],
  "additions_requested": [
    {"file": "{path}", "line": {N}, "guidance": "concern to raise, and an optional suggested fix, in the user's own words"}
  ]
}
```

`questions[].answer` starts `null` and is filled in by `/revise` Step 2 once
answered. `additions_requested[]` items become new draft comments via
`/revise` Step 4 -- leave both arrays empty (`[]`) when there are none.

### Step 10: Write Review Metadata

Write `.artifacts/pr-review/{context}/review-metadata.json`:

```json
{
  "provider": "{provider}",
  "owner_or_namespace": "{owner-or-namespace}",
  "repo_or_project": "{repo-or-project}",
  "number": {number},
  "context": "{context}",
  "base_repo": "{base-repo path}",
  "base_repo_is_scratch": false,
  "base_ref_name": "{baseRefName}",
  "head_sha": "{head-sha}",
  "merge_base_sha": "{merge-base-sha}",
  "iteration": 1,
  "state": "awaiting_decision",
  "started": "{ISO 8601 timestamp}",
  "last_updated": "{ISO 8601 timestamp}",
  "reviewer_agent_id": "{agent ID if a subagent was spawned, null otherwise}"
}
```

## Output

- `.artifacts/pr-review/{context}/00-reviewer-profile.md`
- `.artifacts/pr-review/{context}/01-pr-context.md`
- `.artifacts/pr-review/{context}/02-draft-review-001.md`
- `.artifacts/pr-review/{context}/decisions-001.json`
- `.artifacts/pr-review/{context}/review-metadata.json`
- `.artifacts/pr-review/{context}/worktree/` (git worktree, left in place)

## When This Phase Is Done

Present the PR context and the draft decision table to the user, along with
your recommendations.

Then **re-read the controller** (`controller.md`) for next-step guidance.
