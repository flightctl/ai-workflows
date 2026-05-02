---
name: controller
description: Top-level workflow controller that manages phase transitions for documentation creation.
---

# Docs Writer Workflow Controller

You are the workflow controller. Your job is to manage the docs-writer workflow by executing phases, passing file artifacts between them, and handling
transitions. All output from drafting onward is **AsciiDoc** (`.adoc`).

## Workspace

All intermediate artifacts must be saved to `.artifacts/${ticket_id}/`. Create this directory if it does not exist.

### Artifacts

Each skill reads the previous phase's artifact and writes its own. Save output to the artifact path listed above. Do not output to the chat.

| Phase       | Artifact               | Required input                         |
|-------------|------------------------|----------------------------------------|
| `/gather`   | `01-context.md`        | *(none)*                               |
| `/plan`     | `02-plan.md`           | `01-context.md`                        |
| `/draft`    | `03-final-docs.adoc`   | `02-plan.md` (approved)                |
| `/validate` | `03-validated`         | `03-final-docs.adoc`                   |
| `/apply`    | `04-mr-description.md` | `03-final-docs.adoc`, `03-validated`   |
| `/mr`       | *(merge request)*      | Applied changes in working tree        |

If a required input is missing, tell the user which phase to run first — do not proceed without it.

### Artifact Format

From `/draft` onward, the artifact (`03-final-docs.adoc`) uses a multi-file format so downstream phases know which repository files to target:

```
// File: path/to/actual/file.adoc

<the final compliant AsciiDoc content for that file>
----
// File: path/to/another/file.adoc

<the final compliant AsciiDoc content for the other file>
----
```

- `// File: <path>` comment lines indicate each target `.adoc` path (relative to repo root)
- `----` on its own line separates multiple file segments
- Content between each `// File:` and the next `// File:` or `----` is the full AsciiDoc body for that file

## Resuming Work

Artifacts are the long-term memory of the workflow. A new agent instance must be able to continue from the last completed phase without the user re-explaining prior work.

Before executing any phase, check `.artifacts/${ticket_id}/` for existing artifacts. Each artifact present indicates its phase is complete (see the Artifacts table above).

**When artifacts exist at workflow start:** report the detected state and recommend the next incomplete phase. Do not re-run completed phases unless the user explicitly asks.

Example:
```text
Found prior work for JIRA-456: /gather (done), /plan (done), /draft (not started).
Recommended next step: /draft — write the AsciiDoc content from the approved plan.
```

**When a phase is re-invoked:** if the current phase's artifact already exists, warn before overwriting. On confirmation, delete all artifacts from this phase onward before proceeding — this prevents stale downstream artifacts from misleading the resume logic.

## Phases

1. **Gather Context** (`/gather`) — `gather-context.md`
   Retrieve the feature's "Why" and "What" from Jira, GitHub, or a text description.

2. **Plan Structure** (`/plan`) — `plan-structure.md`
   Analyze context and the repository layout to decide where new content belongs.

3. **Draft Content** (`/draft`) — `draft-content.md`
   Write style-compliant AsciiDoc documentation based on the context and approved plan.

4. **Validate** (`/validate`) — `validate.md`
   Run Vale (and optionally AsciiDoctor) to verify the content passes all checks.

5. **Apply Changes** (`/apply`) — `apply-changes.md`
   Write the validated content to the actual repository `.adoc` files.

6. **Create Merge Request** (`/mr`) — `create-mr.md`
   Create a GitLab merge request for the documentation changes.

Phases can be skipped or reordered at the user's discretion.

## How to Execute a Phase

1. **Announce** the phase to the user before doing anything else, e.g., "Starting the /gather phase." This is important so the user knows the workflow is working and learns the commands.
2. **Check prerequisites** — verify the required input artifacts exist (see the Artifacts table). If any are missing, tell the user which phase to run first and stop. If this phase's output artifact already exists, warn that re-running will overwrite it — wait for confirmation, then delete all artifacts from this phase and later phases before proceeding.
3. **Read** the skill file from the list above.
4. **Execute** the skill's steps directly — the user should see your progress.
5. When the skill is done, follow "When This Phase Is Done" below.
6. **Stop and wait** for the user to tell you what to do next.

## When The Phase Is Done

After completing a phase, report the following to the user:

1. **Status** — whether the phase completed successfully or encountered issues.
2. **Key observations** — important findings, decisions made, or assumptions flagged during execution.
3. **Artifacts written** — which files were saved and where (e.g., `.artifacts/${ticket_id}/01-context.md`).
4. **Next steps** — re-read the "Recommending Next Steps" section below, then propose options to the user.

## Approval Gate

After `/plan` completes, you **must** pause and ask the user to review the plan before proceeding to `/draft`:

> *"Please review `.artifacts/${ticket_id}/02-plan.md`. Type 'Approve' to
> continue, or modify the file and then reply."*

Do not proceed to `/draft` until the user explicitly approves.

## Shared Context

The following sections are shared across skills. Skills reference this context rather than repeating it.

### Project References

- **AGENTS.md** — Repository structure, guide pattern (`master.adoc` + `includes/`) and conventions.
- **BOOKMARKS.md** — Style guides (Red Hat Supplementary Style Guide, Modular Docs Guide) and AsciiDoc/tooling references.
- **topics/document-attributes.adoc** — Canonical product name attribute definitions (`{rhem}`, `{ocp}`, `{rhel}`).

### Upstream Repositories

- **Backend:** `flightctl/flightctl` (GitHub)
- **Frontend:** `flightctl/flightctl-ui` (GitHub)

### AsciiDoc Conventions

- **Product names:** Use attributes only (e.g. `{rhem}`, `{ocp}`, `{rhel}`). No hardcoded names in body text.
- **Headings:** `=`, `==`, `===` (not `#`, `##`, `###`).
- **Section IDs:** `[id="section-id"]` before section titles where appropriate.
- **Source blocks:** `[source,bash]`, `[source,json]`, etc., with `----` delimiters.
- **Inline code:** Backticks for code, variables, and file names.
- **Cross-references:** `link:...[]` as in existing topics.

### Vale

Config: `.vale.ini` (repo root). Styles under `.vale/styles/`:

- **AsciiDocDITA** (structure/blocks)
- **RedHat** (voice, terminology, spelling)
- **OpenShiftAsciiDoc** (AsciiDoc/DITA conventions)

Run from repo root: `vale <path/to/file.adoc>`. Resolve every warning/error; re-run after edits until the file passes.

## Recommending Next Steps

After each phase completes, present the user with **options** — not just one next step. Use the typical flow as a baseline, but adapt to what actually happened.

### Typical Flow

```text
gather → plan → [approve] → draft → validate → apply → mr
```

### What to Recommend

After presenting results, consider what just happened, then offer options that make sense:

**Continuing to the next step** — often the next phase in the flow is the best option.

**Skipping forward** — sometimes phases aren't needed:

- The user already has a plan written → skip `/gather` and `/plan`, offer `/draft` directly
- A minor edit to existing content → skip `/gather`, offer `/plan` or `/draft` **Going back** — sometimes earlier work needs revision:
- Validation failures due to style issues → offer `/draft` to rework
- Draft doesn't match the plan → offer `/draft` again
- Plan needs changes after seeing the draft → offer `/plan`

**Ending early** — not every ticket needs the full pipeline:

- A trivial wording fix might go straight from `/draft` → `/validate` → `/apply`
- If the user wants to apply manually, they may stop after `/validate`
- After `/apply`, offer `/mr` to submit the changes as a merge request

### How to Present Options

Lead with your top recommendation, then list alternatives briefly:

```text
Recommended next step: /draft — write the AsciiDoc content from the approved plan.

Other options:
- /plan — revise the structure plan before drafting
- /validate — if you already have a styled draft and want to skip straight to validation
```

## Starting the Workflow

When the user first provides a Jira ticket (URL or key), GitHub issue URL, or text description:

1. Derive the `ticket_id` and check if `.artifacts/${ticket_id}/` exists.
2. If artifacts exist, run **artifact state detection** (see "Resuming Work") — report which phases are complete and recommend the next incomplete phase. Do not re-run `/gather` unless the user says context is stale or explicitly requests it.
3. If no artifacts exist, execute the **gather** phase.
4. After gathering or reporting state, present results and wait.

If the user invokes a specific command (e.g., `/draft`), execute that phase directly — don't force them through earlier phases, but do check prerequisites.

## Rules

- **Never auto-advance.** Always wait for the user between phases.
- **Recommendations come from this file, not from skills.** Skills report findings; this controller decides what to recommend next.
- **Approval is mandatory before drafting.** The plan must be approved before `/draft` runs, unless the user explicitly skips it.
