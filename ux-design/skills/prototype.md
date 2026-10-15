---
name: prototype
description: Generate design prototypes informed by research findings for evaluation.
---

# Prototype — Design Exploration

Generate prototypes that let the researcher react to a design direction and
iterate before handoff. A prototype should focus on the riskiest user flows and
states rather than polish that cannot yet be validated.

## Dependencies

This phase requires `uxd-prototype-create` from the `uxd-prototype` plugin. If
the skill is unavailable, stop and ask the researcher to run `./install.sh`.

## Artifact Path Safety

Run `git rev-parse --show-toplevel` and store the result as
`source_repo_root`. If it fails, stop and ask the researcher to open the
source-repository workspace.

Before using `{issue-key}` in a path, require it to match
`[A-Za-z0-9][A-Za-z0-9._-]*` and reject `.` or `..`. Treat it as one path
component.

The upstream create skill returns a prototype `{ID}`; a refinement receives
the existing `{ID}` from `prototype-notes.md`. Before using an ID in a path or
command, require it to match the same pattern and reject `.` or `..`. Assign
the validated value to `prototype_id`. Do not use an unchecked ID for restore,
copy, or cleanup operations. If a newly created ID fails validation, stop,
report the invalid ID, and leave the native artifacts in place for manual
inspection.

Resolve `.artifacts` under the source repo root and require it to be a real
directory, not a symlink. Resolve `.artifacts/{ID}` and require it to be a
non-symlink directory whose resolved parent is exactly the resolved
`.artifacts` directory. If any check fails, stop before reading, copying, or
removing the native directory. Repeat the containment check immediately before
cleanup.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/01-discovery.md` for the problem, user
groups, and competitive landscape. If it is missing, ask for an equivalent
problem framing. If none is available, recommend `/ingest` and stop.

Read `00-context.md` when present. Record the discovery revision and research
synthesis used for each prototype iteration. If the context was enriched after
the current prototype was created, compare its decisions with the current
discovery and research reconciliation. Present which flows and decisions can
carry forward and which need revision; wait for the researcher to approve the
direction. An early prototype is a reference for exploration, not a validated
design for the enriched context.

When returning from `/evaluate`, read `04-evaluation.md` and use the
researcher-approved findings to guide the next iteration.

## Process

The create skill conducts its own onboarding and extracts user stories. This
phase sets a strategic direction from discovery and research, supplies the
answers already agreed with the researcher, and maps the generated artifacts
into the UX Design namespace.

### Step 1: Set the Design Direction

Using `01-discovery.md` and `02-research.md` when present, propose one or two
design directions. For each, identify the user needs it prioritizes, the core
interaction pattern, its tradeoffs, and how it compares with patterns from
discovery. Present the directions and wait for the researcher to choose or
suggest another.

Settle the create skill's onboarding answers with the researcher:

- **Source:** Jira RFE, published PRD path, Figma link, feature description,
  or idea from discovery.
  Pass a Figma link directly to `uxd-prototype-create`; it reads Figma itself.
  Do not also run `uxd-figma-read` for the same source.
- **Workspace:** `standalone` or a local path / Git URL for the codebase to
  prototype in. The create skill clones a workspace into its artifact area.
  Use the frontend repo path from the **Frontend repo** field in
  `01-discovery.md` § Current State when available; do not default to the
  source repo root if it is not the frontend codebase.
- **Decisions:** use `human` for an initial prototype so the researcher chooses
  among design options; use `auto` for a refinement when the researcher wants
  the skill to recommend options. `skip` is the upstream default and means no
  decision kit, so pass a choice explicitly.

#### Workspace Strategy Selection

Choose the workspace strategy based on the **Frontend repo** field in
`01-discovery.md` § Current State:

**Contextual affected-page review** (recommended for existing UI):
When the frontend source is accessible — a local path or a Git URL — and the
feature modifies existing pages or components, pass it as `--workspace`. For
a Git URL, use `--workspace-branch` to select the clone branch; for a local
path the resolver validates it exists (`type: local`) and ignores
`--workspace-branch`. For a Git URL the resolver clones into
`.artifacts/{ID}/code/`. For a monorepo, record the frontend subdirectory.

**Baseline SHA — pre-invocation (local workspace only):** Before invoking
the create skill, capture the local workspace commit SHA
(`git -C <path> rev-parse HEAD`) and read the expected **commit SHA** from
`01-discovery.md` § Current State. Compare them:

- **Match:** proceed with create invocation.
- **Differ (both known):** the baseline differs from discovery. Stop and
  present both SHAs. The researcher must either refresh discovery with
  `/ingest` or explicitly accept the new baseline — recording both SHAs and
  the reason in `prototype-notes.md`, and refreshing affected Current State
  context before claiming fidelity.
- **Unknown (discovery has no SHA):** baseline is unverified. Stop, explain
  that discovery did not capture a SHA, and ask the researcher to confirm the
  current workspace as the intended baseline. Record the confirmed SHA.

Do not silently switch the researcher's checkout. Standalone mode has no
workspace SHA — record "standalone — N/A" and skip this check.

For a Git URL workspace, the clone happens inside the create skill during
Step 2; the pre-edit baseline SHA is not available until then. Handle it in
Step 2 below. The prototype should reuse
unchanged page scaffolding and real components, replacing only the
scenario-specific parts with mocks — no full production backend or reusable
production code required. Mark which page sections are unchanged (reused from
source), changed (new or modified), and mocked (stand-in data or interactions)
in `prototype-notes.md`.

**Standalone exploration** (for greenfield features or no accessible source):
When there is no existing UI to modify, or the frontend source is neither
locally available nor accessible as a Git URL, use `standalone`. When the
source is inaccessible for a feature that modifies existing UI, acknowledge
this to the researcher: the prototype explores the design direction without
existing page integration. Do not claim faithful integration when working
standalone without source access. If the researcher has screenshots or design
references, agree on a labeled baseline: note what is approximated from
references and what is explored without source verification.

Record the chosen strategy and rationale in `prototype-notes.md`.

### Step 2: Generate the Prototype

When invoking the create skill with a workspace (local or Git URL), supply
the expected discovery baseline SHA as task context alongside the source and
flags — not as a CLI flag, but as an explicit constraint in the invocation
prompt: "The discovery baseline for this frontend is commit {SHA}. After
resolving the workspace, capture the pre-edit commit SHA at the workspace
root and compare it with the expected baseline before generating. Pause and
report if they differ or the expected SHA is unknown." For a local workspace,
this SHA was already verified in Step 1; for a Git URL, this is where the
clone resolves and the pre-edit SHA becomes available — it must be captured
and compared before generation begins. If create cannot provide a trustworthy
pre-edit baseline SHA, record the baseline as **unverified** and do not
accept the output as faithful contextual integration. Standalone mode skips
this constraint.

Invoke the skill with the source and agreed choices. For example:

```text
uxd-prototype-create "{source}" --workspace "{path-or-standalone}" --decisions human
```

For a refinement, use the same prototype ID and `--decisions auto` after
staging current evaluator artifacts described below. If the discovery revision
changed since the evaluation, do not feed that stale evaluation into the
refinement; use the researcher-approved context and design feedback instead.
`--workspace` is the codebase to build in; `--target` is only a later MR/PR
destination. Do not pass a target unless the researcher requested publishing
and approved the destination.

Keep the scope focused on:

- The primary user flow
- Important empty, loading, error, and populated states
- The user need with the greatest uncertainty or risk

The new create skill also records user journeys and page scenarios. Preserve
those artifacts because its evaluate and export skills consume them.

**Runtime paths:** Upstream skill files refer to `CLAUDE_SKILL_DIR` and
`CLAUDE_PLUGIN_ROOT`. Claude Code supplies those variables. In other runtimes,
resolve the installed create skill at
`${HOME}/.uxd-ai-skills/plugins/uxd-prototype/skills/uxd-prototype-create` and
the plugin root at `${HOME}/.uxd-ai-skills/plugins/uxd-prototype`. Set the
expected variable for a helper invocation or substitute its absolute path.
Do not assume a plugin path based on another runtime.

### Refinement After `/evaluate`

`uxd-prototype-create refine {ID}` now reads
`.artifacts/{ID}/eval/evaluation-report.csv` and
`.artifacts/{ID}/eval/refinement-suggestions.json`. It no longer reads
`reviews/summary.md` or accepts the former `--mode` flag.

Before refining:

1. Validate `{ID}` using **Artifact Path Safety** before restoring the
   prototype's native layout under `.artifacts/{ID}/` from the
   mirrored files in `03-prototype/` as described in Step 3.
2. If Full evaluation ran and both refinement inputs exist, copy
   `evaluation-report.csv` and `refinement-suggestions.json` from the private
   evaluator run directory
   (`04-eval-raw/prototype-evaluate/{run-id}/.artifacts/{ID}/eval/`) into
   `.artifacts/{ID}/eval/`. If either input is missing, do not invent it or
   use `refine`; start a new `uxd-prototype-create` run with the source and
   researcher-approved feedback as context.
3. Before a refinement or replacement changes the native prototype, preserve
   the current
   `.artifacts/ux-design/{issue-key}/03-prototype/` tree under
   `history/prototype-iteration-{N}/`, unless that exact tree is already in the
   current context-revision snapshot. Do not overwrite an existing snapshot.

Use `refine` only when both evaluator inputs are staged:

```text
uxd-prototype-create refine {ID} --decisions auto
```

Keep either the refined output or the new prototype output under
`.artifacts/{ID}/` until Step 3 mirrors it. Do not mirror output or remove the
native directory in this step.

### Step 3: Map Skill Output Into Our Artifact Structure

The create skill writes to `.artifacts/{ID}/`, where `{ID}` is the Jira key or a
slug. Read the returned ID from the create skill's output, then validate it
using **Artifact Path Safety** before constructing paths or reading
`metadata.json`.

**Awaiting-decisions guard (check before any mirroring):** When
`decisions/` exists under `.artifacts/{ID}/`, read `decisions.json` for
per-decision statuses (`pending`, `auto-resolved`, `user-decided`). If any
decision has status `pending`, the skill is paused awaiting researcher
input — not failed and not complete. Surface the pending decision pages and
`decisions/index.html` to the researcher. Keep all native artifacts under
`.artifacts/{ID}/` intact so the skill can resume after choices are made.
Do not snapshot, mirror, delete native output, or advance to evaluation or
handoff. Stop here and wait for the researcher to resolve decisions, then
re-enter Step 3 after the skill resumes and completes.

**Complete-run metadata:** When no decisions are pending (or `--decisions
skip`), `rfe-snapshot.md` and `metadata.json` are required. If either is
missing after the skill exits, stop and report that prototype creation did
not complete — never treat absent metadata as silent success.

**Baseline SHA gate (workspace mode, before mirroring):** Use the pre-edit
baseline SHA — the Step 1 pre-invocation capture for a local path, or the
pre-edit SHA reported by create for a Git URL clone (per the Step 2
constraint). Do not re-read HEAD from a post-generation workspace: generated
changes may include commits, making HEAD unreliable as baseline evidence.
If create did not report a pre-edit SHA for a Git URL workspace, record the
baseline as **unverified** and do not accept the output as faithful. Apply
the same match/differ/unknown rules from Step 1: do not mirror or accept
completed output until the baseline is confirmed or the researcher
explicitly accepts a new baseline — recording both SHAs, the reason, and
refreshing affected Current State context. Standalone mode: skip.

For a refinement, Step 2 has already preserved the prior active tree;
reuse that snapshot and do not archive it again. For any other replacement,
preserve the current tree under
`.artifacts/ux-design/{issue-key}/history/prototype-iteration-{N}/` before
mirroring, unless that exact tree is already preserved in the current
context-revision snapshot. Never archive the new output as the previous
iteration. Mirror the new output under
`.artifacts/ux-design/{issue-key}/03-prototype/`, preserving the prototype's
native layout so a later refinement can restore it without flattening files.

**Standalone prototype:**

- `.artifacts/{ID}/prototype/` → `03-prototype/prototype/`

**Workspace prototype:**

- `.artifacts/{ID}/code/` contains the cloned codebase and prototype changes.
  Preserve it under `03-prototype/code/` or record its durable path; note the
  prototype's app entry point in `prototype-notes.md`.
- Mirror `changeset.md` and `workspace-analysis.json` to `03-prototype/`.

**Create metadata:** mirror each file when the skill produces it:

- `rfe-snapshot.md`
- `metadata.json`
- `user-stories.json`
- `journeys.json`
- `scenarios.json`
- `prototype-summary.yaml`
- `prototype-bar.json`
- `verification.json`
- `decisions/` and `exports/`, when present

**Complete prototype verification:** Beyond the required metadata, a
complete prototype must have:

- **Agreed page/flow output:** For standalone mode, non-empty rendered
  content under `prototype/`. For workspace mode, the codebase and changes
  under `code/`, or a durable local workspace path recorded in
  `workspace-analysis.json` (`workspace_path`) when the resolver used an
  existing local directory (`type: local`). An empty output directory with
  only metadata or decision cards is not complete.
- **Verified page/flow review:** Serve or open the prototype entry point
  and confirm the agreed user flow is navigable with the expected
  unchanged/changed/mocked sections visible. If the entry point cannot be
  served or opened, record the verification as **unverified** with the
  reason rather than claiming completion. Copied unchanged app scaffolding
  alone is not proof that the requested prototype content exists.

Do not diagnose completion or failure from the presence or absence of a
directory alone. Check for the actual agreed output artifacts.

The new evaluator can consume `rfe-snapshot.md` and `decisions/` when staged
into its private run root. Record the create skill's `{ID}` in
`prototype-notes.md`.

After mirroring the canonical prototype files, remove the native
`.artifacts/{ID}/` created by the create or refine skill. This cleanup happens
only here, after the refined output is safely mirrored. Recheck the ID and
resolved-path containment immediately before deletion. Never run `rm -rf` on a
path assembled directly from `{ID}`. Remove only the validated direct child of
`.artifacts`, using the source-repo root and ID as quoted arguments:

```bash
python3 - "${source_repo_root}" "${prototype_id}" <<'PY'
import re
import shutil
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve(strict=True)
prototype_id = sys.argv[2]
if (
    not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prototype_id)
    or prototype_id in {".", ".."}
):
    raise SystemExit("Refusing to remove an invalid prototype ID")

artifact_root_path = repo_root / ".artifacts"
if artifact_root_path.is_symlink():
    raise SystemExit("Refusing to remove files through a symlinked .artifacts directory")
artifact_root = artifact_root_path.resolve(strict=True)
if artifact_root.parent != repo_root or not artifact_root.is_dir():
    raise SystemExit("Refusing to remove files outside the source repo's .artifacts directory")

native_dir = artifact_root / prototype_id
if native_dir.is_symlink() or not native_dir.is_dir():
    raise SystemExit("Refusing to remove a missing, non-directory, or symlinked prototype path")
resolved_native_dir = native_dir.resolve(strict=True)
if resolved_native_dir.parent != artifact_root:
    raise SystemExit("Refusing to remove a prototype path outside .artifacts")

shutil.rmtree(resolved_native_dir)
PY
```

The evaluator uses a separate private run root under `04-eval-raw/`; do not
move its outputs into `.artifacts/{ID}/` except for the two temporary
refinement inputs described above.

## Step 4: Document Design Rationale

For each significant design decision, connect it to a research finding or
researcher direction. If neither supports it, identify it as an assumption.
Do not invent research evidence.

## Output

`.artifacts/ux-design/{issue-key}/03-prototype/`

```text
03-prototype/
├── prototype-notes.md        # Direction, rationale, and open questions
├── iteration-{N}.md          # Notes for each iteration
├── prototype/                # Standalone prototype, when applicable
├── code/                     # Workspace clone and prototype, when applicable
├── user-stories.json         # User stories and acceptance criteria
├── journeys.json             # Primary user journeys
├── scenarios.json            # On-load scenarios per page
├── rfe-snapshot.md           # Frozen source requirements
├── metadata.json             # Prototype metadata and decision mode
├── prototype-summary.yaml    # Machine-readable summary
├── prototype-bar.json        # Prototype Bar configuration
├── changeset.md              # Workspace mode only
├── workspace-analysis.json   # Workspace mode only
├── verification.json         # Workspace mode only
├── decisions/                # When decisions are auto or human
└── exports/                  # When export was requested
```

`prototype-notes.md` records:

```markdown
# Prototype — {issue-key}

**Date:** {date}
**Iteration:** {N}
**Discovery revision:** {revision used to make this iteration}
**Research basis:** {research revision/findings or "Research skipped"}
**Revalidated against discovery revision:** {revision or "Not yet revalidated"}
**Skill prototype ID:** {ID}
**Design direction:** {chosen direction}
**Prototype mode:** {standalone / workspace}
**Workspace strategy:** {contextual affected-page review / standalone exploration / standalone greenfield}
**Workspace input:** {local path, Git URL, or "standalone"}
**Workspace ref:** {branch used for Git URL clone, or "N/A" for local/standalone}
**Workspace baseline SHA:** {resolved commit SHA, or "standalone — N/A"}
**Discovery baseline SHA:** {SHA from 01-discovery.md, or "none recorded"}
**Baseline match:** {yes / accepted-new — reason / standalone — N/A}
**Frontend subdir:** {subdirectory within workspace, or "root" / "N/A"}
**Decision mode:** {skip / auto / human}
**Input source:** {Jira RFE / published PRD / Figma / feature description / idea}

## Design Decisions

| Decision | Rationale | Research Reference |
|----------|-----------|-------------------|
| {what} | {why} | {finding or researcher direction} |

## User Stories Covered

| Story | Acceptance Criteria | Status |
|-------|-------------------|--------|
| {story} | {criteria} | {covered / partial / deferred} |

## Page Context

| Section | Status | Source |
|---------|--------|--------|
| {page area} | {unchanged / changed / mocked} | {component or source reference} |

{For contextual affected-page review, list each page section and whether it is
reused unchanged from existing source, changed by this prototype, or mocked
with stand-in data. Omit for standalone greenfield prototypes. For standalone
exploration without source access, state: "Page context not available —
prototype explores design direction without existing page integration."}

## Scope

**Covered in this prototype:**
- {flow or interaction covered}

**Not yet covered:**
- {flow or interaction not represented}

## Open Questions for Evaluation

- {What should the evaluator focus on?}
- {Where is the design most uncertain?}
```

Present the prototype and its scope to the researcher. Wait for feedback before
revising or recommending `/evaluate`, then re-read `controller.md` for
next-step guidance.

Update `00-context.md` with the active prototype iteration and the discovery
revision it has been reviewed against. If the design is materially changed,
increment the iteration and preserve the prior tree first. If no design change
is needed after enrichment, record the review against the new discovery
revision without changing the prototype's original iteration or basis.
