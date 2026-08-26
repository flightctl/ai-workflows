---
name: ingest
description: Fetch the Jira story, load design and PRD context, explore the codebase, and build a validation profile.
---

# Ingest Story Context Skill

Fetch the Jira story, load upstream design/PRD/testplan slices, index the
affected code, and write `01-context.md` for `/plan`.

## Critical Rules

- Jira is read-only. Capture, don't implement. Note unknowns explicitly.
- Ingest is an index. `/plan` opens cited files. Paths, section refs, signatures — not dumps.
- Never Read the same path twice. Never Grep the same (path, pattern) pair twice.
- Do not glob this workflow. Do not load `guidelines.md` or `gh-stack`.
- Do not re-read `AGENTS.md` / `CLAUDE.md` if already in session.
- Grep locates; Read loads. Never grep `.`. Never grep `-A`/`-B`/`-C`. Never grep `.git/`.
- Do not glob the docs repo root. After 5b, search only the feature directory.
- **Write each output path once.** No Delete+rewrite, no second Write to the same file.
- Do not call `GetDynamicTools` / list Jira tools. Call `jira_get_issue` with the args below.

## Jira call (use as-is)

`jira_get_issue`: `comment_limit: 0`, `update_history: false`, never `*all`, never changelog expand.

- **Story:** `fields=summary,description,issuetype,status,parent,issuelinks,labels`
- **Parent epic/feature:** skip if `parent.key` (and its parent) are already in the story payload. Use those keys for docs lookup. Fetch only if a key is missing: `fields=summary,status,issuetype,parent`
- **Blocking deps only:** `fields=summary,status`

## Process

### 1. Identify the story

Issue key with project prefix → `{issue-key}`.

### 2. Artifact directory

```bash
mkdir -p .artifacts/implement/{issue-key}
```

Warn if `.artifacts/` is not gitignored.

If `01-context.md` exists (re-ingest): copy to `01-context.md.prev` **before** exploring. Do not Write the new file until Step 7a confirms.

### 3. Fetch the Jira story

One `jira_get_issue` for the story. Capture summary, description, AC, guidance, testing notes, `Validated by` TC IDs and `PRD Requirements` from the Design Reference (used to filter the testplan in 5d), design refs, type prefix, parent key, blocking links, fix version/sprint.

### 4. Dependencies

For each blocking link: `jira_get_issue` (narrow fields) + `git log --oneline --grep={key} -5` on main. Warn if unresolved; do not block.

### 5. Upstream docs

**5a.** Check `.artifacts/config.json` (workspace-level, shared across workflows).

If it exists, Read it and validate:
1. Path exists on disk
2. Directory is a git repo
3. `git remote get-url origin` matches `docs_repo_remote`

If any check fails, tell the user and re-ask. Resolve `~` to an absolute path before saving.

If it does not exist, ask for docs repo local path and remote. Resolve `~` to absolute. Write `.artifacts/config.json` with `docs_repo_path` and `docs_repo_remote`.

**5b.** Feature directory: `find "{docs_repo_path}" -type d -name "*{feature-key}*"` using keys from the story payload. Ask the user only if not found.

**5c.** Do not Read whole `design.md` / `prd.md` / `testplan.md`.
1. Grep those files for issue key, FR/NFR IDs, AC keywords, `^#`.
2. Read matching heading ranges (`offset`/`limit`).
3. If nothing hits, Read the first ~80 lines of `design.md` (TOC) and grep TOC entries — still not the rest.

**5d.** Filter the testplan to this story's scope. Match the story's `Validated by` TC IDs (captured in Step 3) against the testplan's test-case headings. If `Validated by` is missing, empty, or `None` (no TC IDs), fall back to requirement match: collect every test case whose requirement heading matches a `PRD Requirements` ID from the story's Design Reference.

| Outcome | Condition | Action |
|---------|-----------|--------|
| Normal | Matches found | Write `testplan.md` **once** from `../templates/story-testplan.md` |
| Expected zero | No matches and type is `[QE]`/`[DOCS]`/`[UX]`/`[CI]` | Note expected; delete stale story testplan if present |
| Anomalous zero | No matches and type is `[DEV]`/`[UI]` (or unknown) | Warn; delete stale story testplan if present |

No feature testplan: note and continue.

### 6. Codebase

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
  "ci_workflows": ["{filenames from git ls-files}"]
}
```

Record components as path + signature + test path. `/plan` opens cited files.

**Must-record (index, not dump):**

- **Design:** For each cited section, 2–5 binding bullets for *this* story (identity/key, where a check runs, write vs read target, failure/CAS, timeout/limit, explicit out of scope). One `[Design: §x.y]` each. Not a restatement of the chapter.
- **PRD:** One clause per FR/NFR ID from the story or from slices already Read. Do not Read whole `prd.md`.
- **Cite what `/plan` would not guess** (path + one line; extra grep hits stay unread): sibling implementation in another component/language ("pattern only, do not import"); deploy/runtime surface if the story needs a tool on PATH or in an image (Containerfile/Dockerfile/packaging); neighboring unit **and** integration test paths if grep found them. List leftover `files_with_matches` hits under **Cited, not opened**.
- **Open questions:** Fill or mark `N/A (reason)` for: inbound contract; story boundary vs dependency/successor; spec vs AC conflict (record both, do not pick); named knob missing in code; placement (existing package vs new); runtime dependency not on the current deploy path; shared-state predicate (CAS/lock/idempotency) if the story mutates shared records. Concrete question or N/A. No vague "how should errors work?"

### 7. Compile context

If re-ingest: hold content, go to 7a.

If first ingest: Read `../templates/01-context.md` **once**, fill it tightly (must-record bullets; 5–8 lines per component; signatures only; every open-question slot filled or N/A), Write `01-context.md` **once**.

### 7a. Re-ingest diff

Diff compiled content vs `.prev`. Focus on:
- Acceptance criteria
- Implementation guidance or testing approach
- Dependency status
- New components or patterns
- Validation profile

If `02-plan.md` or later artifacts exist, list them. Wait for confirmation. If confirmed, Write `01-context.md` **once** and delete `.prev`. If declined, delete `.prev` and stop without overwriting.

### 8. Report

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

Follow `controller.md` only if already in session.
