---
name: ingest
description: Fetch the Jira story, load design and PRD context, explore the codebase, and build a validation profile.
---

# Ingest Story Context Skill

Fetch the Jira story, load upstream design/PRD/testplan slices, index the
affected code, and write `01-context.md` for `/plan`.

## Critical Rules

- Jira is read-only. Capture, don't implement. Note unknowns explicitly.
- Explore relevant areas only. Don't map the entire codebase. Focus on components the story will affect.
- Re-invocation diffs before overwriting. If `01-context.md` already exists, preserve it before exploring. After compiling new context, diff against the previous version and present changes to the user before overwriting (see Steps 2a and 7a).
- Ingest is an index. `/plan` opens cited files. Paths, section refs, signatures — not dumps.
- Never Read the same path twice. Never Grep the same (path, pattern) pair twice.
- Do not glob this workflow. Do not load `guidelines.md` or `gh-stack`.
- Do not re-read `AGENTS.md` / `CLAUDE.md` if already in session.
- Grep locates; Read loads. Never grep `.`. Never grep `-A`/`-B`/`-C`. Never grep `.git/`.
- Do not glob the docs repo root. After Step 5b, search only the feature directory.
- **Write each output path once.** No Delete+rewrite, no second Write to the same file.
- Do not call `GetDynamicTools` / list Jira tools. Use the shared fetch-issue script.

## Shared Script

This skill delegates deterministic Jira issue fetching to a shared
script. Reference it using a relative path from this file:

```
../../_shared/scripts/fetch-issue.py
```

The script provides subcommands: `get` and `search`. See the script
header for full usage. It requires `JIRA_URL` and `JIRA_TOKEN`
environment variables.

## Jira call (use as-is)

Resolve the shared script to an absolute path so it remains valid
regardless of working directory:

```bash
FETCH_ISSUE_SCRIPT="${HOME}/.ai-workflows/_shared/scripts/fetch-issue.py"
```

Use `$FETCH_ISSUE_SCRIPT` instead of the relative path in all subsequent
commands.

- **Story:** `python3 "$FETCH_ISSUE_SCRIPT" get {KEY} --fields summary,description,issuetype,status,labels,fixVersions --parent --parent-fields summary,status,issuetype,parent --links --link-fields summary,status`
- **Parent epic/feature:** skip if `parent.key` (and its parent) are already in the story payload. Use those keys for docs lookup. Fetch only if a key is missing: `python3 "$FETCH_ISSUE_SCRIPT" get {KEY} --fields summary,status,issuetype --parent --parent-fields summary,status,issuetype,parent`
- **Blocking deps only:** `python3 "$FETCH_ISSUE_SCRIPT" get {KEY} --fields summary,status`

## Process

### Step 1: Identify the Story

The user will provide one of:
- A Jira issue key or URL
- A path to an existing story file from the design workflow

Extract the full Jira issue key, including the project prefix (e.g.,
`PROJ-1234`, not just `1234`). Use this as `{issue-key}` throughout
the workflow — it is the context identifier for the artifact directory
and all downstream phases.

### Step 2: Create Artifact Directory

```bash
mkdir -p .artifacts/implement/{issue-key}
```

Verify that `.artifacts/` is covered by the project's `.gitignore`. If it
is not, warn the user that implementation artifacts could be accidentally
committed with the code.

### Step 2a: Check for Prior Ingest

If `.artifacts/implement/{issue-key}/01-context.md` already exists, this is a
re-invocation. Copy the existing file to `01-context.md.prev` so it is
preserved for the diff in Step 7a.

### Step 3: Fetch the Jira Story

One `fetch-issue.py get` call for the story (using the Story command from
the Jira call section).

Capture:
- Summary and description
- User story (As a... I want... So that...)
- Acceptance criteria
- Implementation guidance (if present)
- Testing approach (if present)
- `Validated by` TC IDs and `PRD Requirements` from the Design Reference (used to filter the testplan in Step 5d)
- Design refs
- Story type prefix (`[DEV]`, `[UI]`, etc.)
- Parent key (epic) and its parent key (feature), from the `--parent --parent-fields` response
- Story dependencies (linked issues — "depends on", "is blocked by")
- Fix version / sprint (if set)

### Step 4: Check Story Dependencies

For each dependency identified in Step 3:
1. Check if the dependent story's Jira status indicates completion
   (Done, Closed, Resolved). Fetch with `fetch-issue.py get` (Blocking deps
   command from the Jira call section).
2. Check if the dependent story's code has been merged to the main branch:
   `git log main --oneline --grep="{key}" -5`.

If dependencies are unresolved, **warn the user** but do not block. Report:
- Which dependencies are unresolved
- What risk this presents (merge conflicts, missing APIs, etc.)
- A recommendation to proceed with caution or wait

### Step 5: Load Upstream Context

The PRD and design document are published to a docs repo by the prd and
design workflows. Fetch them from there.

#### 5a: Resolve the Docs Repo

Check for an existing docs repo configuration at `.artifacts/config.json`.
This config is workspace-level and shared across all workflows — a prior
workflow run may have already created it.

If it exists, Read it and validate:
1. Path exists on disk
2. Directory is a git repo
3. `git remote get-url origin` matches `docs_repo_remote`

If any check fails, tell the user and re-ask. Resolve `~` to an absolute path before saving.

If it does not exist, ask for docs repo local path and remote. Resolve `~` to absolute. Write `.artifacts/config.json` with `docs_repo_path` and `docs_repo_remote`.

#### 5b: Find the PRD and Design Document

The docs repo organizes documents by Feature-level Jira issue. To find the
right directory, walk the Jira hierarchy from the story:

1. The story (e.g., `PROJ-1234`) has a parent **Epic** — its key is in the
   `parent.key` field of the story payload from Step 3
2. The Epic has a parent **Feature** — its key is in `parent.parent.key`
   (or `parent.fields.parent.key`) of the story payload, since the Story
   command fetches `--parent-fields summary,status,issuetype,parent`

If the Feature key is not in the story payload (the `--parent-fields parent`
did not return a grandparent), fetch the Epic with `fetch-issue.py get`
(Parent epic/feature command from the Jira call section) to get its parent.

The docs repo structure is `{release}/{feature-slug}/prd.md` and
`{release}/{feature-slug}/design.md`, where `{feature-slug}` includes the
Feature issue key (e.g., `port-mappings-PROJ-1100`).

Search the docs repo for the Feature key:

```bash
find "{docs_repo_path}" -type d -name "*{feature-key}*"
```

If multiple directories match (e.g., the same Feature across releases),
prefer the one whose release matches the story's fix version. If ambiguous,
ask the user to choose.

If the hierarchy traversal fails or no directory is found, ask the user
for the path to the PRD and design document within the docs repo.

#### 5c: Read Upstream Documents (section-scoped)

Do **not** Read an entire `design.md`, `prd.md`, or `testplan.md`. Those
files are often thousands of lines. Search, then slice.

1. Collect search terms from the Jira story: issue key, design section
   refs, FR/NFR IDs, AC keywords, component names.
2. Grep `design.md` / `prd.md` / `testplan.md` for those terms and for
   heading lines (`^#`).
3. Read **only** the matching heading ranges (`offset`/`limit`). Prefer
   one contiguous range per relevant section.
4. If grep finds nothing useful, Read the first ~80 lines of `design.md`
   (title, TOC, or overview) and grep again using TOC entries — still
   do not Read the rest of the file.

Need:

1. **Design document** (`design.md`) — sections that bind this story
2. **PRD** (`prd.md`) — FR/NFR this story covers
3. **Testplan** (`testplan.md`) — candidate test cases for Step 5d

If the design document or PRD are not found, ask the user for their
location or proceed with only the Jira story content. The design
document and PRD are valuable context but not strictly required — the
story's acceptance criteria are the primary contract.

#### 5d: Filter Testplan to Story Scope

Match the story's `Validated by` TC IDs (captured in Step 3) against the
testplan's test-case headings. If `Validated by` is missing, empty, or
`None` (no TC IDs), fall back to requirement match: collect every test case
whose requirement heading matches a `PRD Requirements` ID from the story's
Design Reference.

| Outcome | Condition | Action |
|---------|-----------|--------|
| Normal | Matches found | Write `testplan.md` **once** from `../templates/story-testplan.md` |
| Expected zero | No matches and type is `[QE]`/`[DOCS]`/`[UX]`/`[CI]` | Note expected; delete stale story testplan if present |
| Anomalous zero | No matches and type is `[DEV]`/`[UI]` (or unknown) | Warn; delete stale story testplan if present |

No feature testplan: note and continue.

### Step 6: Explore the Codebase

Based on the story's scope, explore the areas of the codebase that will be
affected.

**Budgets (hard):**
- ≤ **20** Greps, each `head_limit` ≤ 25. **One** Makefile grep for `lint|test|generate|tidy|cover`.
- ≤ **4** Globs. Never `**/*` on `.artifacts`. Never repo-wide `**/*{story-keyword}*`.
- Repo-wide Grep: `output_mode: files_with_matches`. Then signature Reads.
- ≤ **8** source Reads, `offset`/`limit` ≤ 80 around signatures.
- Stop after 3 consecutive Reads with no new pattern.
- Stack: `git branch --show-current`, `git log --oneline -8`, `gh stack view --json`. No `.git/` listing.
- Topology: parse `{owner}/{repo}` from `git remote get-url origin` (never substitute a well-known upstream name). Then `gh repo view {owner}/{repo} --json isFork,parent`. If `gh` fails, ask the user whether this is a fork and, if so, for upstream `{owner}/{repo}`.

**Validation cache:** If `.artifacts/implement/_validation-profile.md` exists and `.meta.json` hashes/mtimes still match, merge the profile into the in-memory context draft, skip config Reads, and do not Write `01-context.md` until Step 7 or Step 7a. Else one discovery pass: bounded Greps of present `AGENTS.md` and `CONTRIBUTING.md` (unless already in session) for lint/test/coverage commands, one Makefile grep, plus CI filenames via `git ls-files '.github/workflows/*.yml' '.github/workflows/*.yaml'`. For each listed workflow, Grep command-bearing keys (`run:`, `make`, lint/test targets) — not full workflow bodies. Then Write cache files **once**.

Skip `AGENTS.md` and `CONTRIBUTING.md` Reads if already in session. Path-only for PR template unless the body is required.

`.artifacts/implement/.meta.json` schema (write **once** on cache miss; compare these keys on hit):

```json
{
  "AGENTS.md": {"mtime": "{unix}", "sha256": "{hex or empty}"},
  "CONTRIBUTING.md": {"mtime": "{unix}", "sha256": "{hex or empty}"},
  "Makefile": {"mtime": "{unix}", "sha256": "{hex or empty}"},
  "ci_workflows": {
    "{filename}": {"mtime": "{unix}", "sha256": "{hex or empty}"}
  }
}
```

Focus on:

1. **Project configuration** (skip this block when the validation cache
   hits):
   - `AGENTS.md`, `CLAUDE.md` — only if not already in session; grep for
     coverage thresholds and commit/PR conventions
   - Makefile or equivalent — grep build, test, lint commands
   - CI/CD workflows — grep what checks run on PRs; Read a workflow
     file only if grep cannot name the make target
   - `CONTRIBUTING.md` — grep PR and commit message conventions
   - `.github/PULL_REQUEST_TEMPLATE.md` or `.github/PULL_REQUEST_TEMPLATE/` —
     path is enough; Read only if the template body is needed for the
     profile

2. **Affected components:**
   - Which packages, modules, or services will this story touch?
   - Grep for types/funcs; Read signatures (`offset`/`limit`), not full files
   - Note existing test file paths from glob/grep; Read a test file only
     to capture the test pattern (table-driven vs Ginkgo, helpers), not
     the whole suite

3. **Testing infrastructure:**
   - What test frameworks are used?
   - How are tests organized (co-located, separate directory, both)?
   - What test helpers and harnesses exist?
   - How do integration tests get their infrastructure (auto-started, manual)?

4. **Relevant data models and APIs:**
   - What existing types and interfaces will be extended or consumed?
   - What API specifications exist (OpenAPI, protobuf)?

Record components as path + signature + test path. `/plan` opens cited files.

**Must-record (index, not dump):**

- **Design:** For each cited section, 2–5 binding bullets for *this* story (identity/key, where a check runs, write vs read target, failure/CAS, timeout/limit, explicit out of scope). One `[Design: §x.y]` each. Not a restatement of the chapter.
- **PRD:** One clause per FR/NFR ID from the story or from slices already Read. Do not Read whole `prd.md`.
- **Cite what `/plan` would not guess** (path + one line; extra grep hits stay unread): sibling implementation in another component/language ("pattern only, do not import"); deploy/runtime surface if the story needs a tool on PATH or in an image (Containerfile/Dockerfile/packaging); neighboring unit **and** integration test paths if grep found them. List leftover `files_with_matches` hits under **Cited, not opened**.
- **Open questions:** Fill or mark `N/A (reason)` for: inbound contract; story boundary vs dependency/successor; spec vs AC conflict (record both, do not pick); named knob missing in code; placement (existing package vs new); runtime dependency not on the current deploy path; shared-state predicate (CAS/lock/idempotency) if the story mutates shared records. Concrete question or N/A. No vague "how should errors work?"

### Step 7: Compile Context

Compile all findings into `01-context.md`. If this is a re-invocation
(Step 2a found an existing file), **do not write the file yet** — hold the
compiled content and proceed to Step 7a first.

If this is a first invocation: Read `../templates/01-context.md` **once**,
fill it tightly (must-record bullets; 5–8 lines per component; signatures
only; every open-question slot filled or N/A), Write `01-context.md`
**once**.

### Step 7a: Diff Against Prior Ingest (Re-invocation Only)

Diff compiled content vs `.prev`. Focus on:
- Acceptance criteria
- Implementation guidance or testing approach
- Dependency status
- New components or patterns
- Validation profile

If `02-plan.md` or later artifacts exist, list them. Wait for confirmation. If confirmed, Write `01-context.md` **once** and delete `.prev`. If declined, delete `.prev` and stop without overwriting.

### Step 8: Report

8–12 lines. Do not paste `01-context.md`. Point at the file. Include:
- Story scope and key ACs
- Design/PRD loaded (or missing)
- Dependency warnings
- Affected components
- Validation cache hit/miss and profile summary
- Testplan status (matches / expected zero / anomalous zero / none)
- Open questions as `/plan` work, not blockers
- Readiness for `/plan`

If the user declined overwrite in 7a, report the diff and that existing context was kept.

## Output

- `.artifacts/implement/{issue-key}/01-context.md`
- `.artifacts/implement/{issue-key}/testplan.md` (normal testplan outcome only)
- `.artifacts/implement/_validation-profile.md` (+ `.meta.json`) on cache miss

## Done

Return to the invoking workflow router for completion guidance.
