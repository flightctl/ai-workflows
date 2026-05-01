---
name: docs-writer
description: Documentation workflow that converts requirements into structured AsciiDoc sections, runs Vale for style compliance, and produces merge-ready content. Use when creating or updating AsciiDoc documentation from Jira tickets, GitHub issues, or feature descriptions.
---
# Docs Writer Workflow Orchestrator

## Quick Start

1. Read `skills/controller.md` to load the workflow controller
2. If a `ticket_id` is known, check `.artifacts/${ticket_id}/` for existing artifacts. If artifacts exist, report which phases are complete and recommend the next incomplete phase — do not re-run completed phases unless the user explicitly requests it
3. If no artifacts exist and the user provided a Jira ticket, GitHub issue URL, or feature description, execute the `/gather` phase
4. Otherwise, execute the first phase the user requests (e.g. `/plan` if they already have context)

```bash
# Artifact directory and example validation
mkdir -p .artifacts/JIRA-123
vale .artifacts/JIRA-123/03-final-docs.adoc
```

## Phases

| Phase | Exit Criteria |
|---|---|
| **`/gather`** — Research the feature from Jira, GitHub, or a description | `01-context.md` saved |
| **`/plan`** — Determine where content belongs in the repository | `02-plan.md` saved; **user approval** required before `/draft` |
| **`/draft`** — Write style-compliant AsciiDoc content | `03-final-docs.adoc` written |
| **`/validate`** — Run Vale (and optionally AsciiDoctor); loop until clean | Vale passes |
| **`/apply`** — Write validated content to repository files | Repository files updated |
| **`/mr`** — Create a GitLab merge request | Merge request created |

## Example: /gather Phase

For a Jira ticket:
```bash
# Fetch ticket via Jira MCP, then find and diff any linked PRs
gh issue view 456 --repo owner/repo
gh pr diff 78 --repo owner/repo
```

Expected output written to `.artifacts/JIRA-456/01-context.md`:
```markdown
## Why
<problem statement from ticket description>

## What
<feature summary from acceptance criteria>

## Technical Changes
<key diffs: new flags, changed configs, added modules>
```

## Example: /draft Phase

A section written to `03-final-docs.adoc` follows AsciiDoc conventions:
```asciidoc
== Configuring the Cache TTL

Use the `cache.ttl` parameter to control how long entries remain valid.

.Procedure
. Open `config/settings.yaml`.
. Set `cache.ttl` to the desired duration in seconds:
+
[source,yaml]
----
cache:
  ttl: 300
----
. Restart the service to apply the change.
```

## Example: /validate Phase

```bash
vale .artifacts/JIRA-456/03-final-docs.adoc
```

Example Vale output with errors:
```
.artifacts/JIRA-456/03-final-docs.adoc:12:1  error  Use 'select' instead of 'click'.  Vale.Terms
.artifacts/JIRA-456/03-final-docs.adoc:18:5  warning  Avoid passive voice.             Vale.Passive
```

Fix each flagged line in `03-final-docs.adoc`, overwrite the file, and re-run `vale` until output is clean:
```
✔ 0 errors, 0 warnings and 0 suggestions in 1 file.
```

Then optionally verify the build:
```bash
./template_build.sh   # or ./buildGuide.sh from the guide directory
```

## File Layout

- `skills/controller.md` — workflow controller (phase execution, resumption, transitions)
- `skills/{name}.md` — individual phase skills
- `guidelines.md` — principles, hard limits, safety, quality, and escalation rules
