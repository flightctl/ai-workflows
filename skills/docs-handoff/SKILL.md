---
name: docs-handoff
version: 0.1.0
description: >-
  Post-delivery documentation handoff for a single [DOCS] Jira issue. Gathers
  implementation evidence from contributing stories, validates delivery, and
  produces a bounded enrichment plan. Use after implementation PRs merge.
---

# Docs Handoff

Gather delivery evidence for one `[DOCS]` Jira issue and produce an
actionable handoff for the documentation writer.

1. Read [references/evidence-schema.md](references/evidence-schema.md)
   for input validation, contributor extraction, and evidence contracts.
2. Read [references/jira-enrichment.md](references/jira-enrichment.md)
   for the approved metadata and PR Remote Link write protocol.
3. Read [references/handoff-protocol.md](references/handoff-protocol.md)
   for the preview/apply two-phase workflow and source-change proposals.

Inputs: one DOCS issue key, a selected release/target, and an optional
caller-supplied consumer profile. Outputs: delivery-evidence findings,
enrichment plan, and an owning-source narrative proposal when supported.
