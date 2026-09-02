---
name: report-bug
version: 0.1.0
description: >-
  Draft and submit a well-specified Jira bug report after explicit confirmation. Use
  when a user wants to report, file, log, or open a bug rather than fix it now.
---

# Report Bug

Create a truthful, reproducible report useful to triage and a bug-fixing agent.

1. Resolve the target and template with [configuration.md](references/configuration.md),
   select capabilities with [jira-integration.md](references/jira-integration.md),
   and read [bug-report-contract.md](references/bug-report-contract.md).
2. Gather evidence from the conversation and user-approved local sources. Ask
   only for material gaps; never invent observations, impact, or severity.
3. Search Jira read-only for likely duplicates and resolved predecessors. Show
   candidates and offer to add evidence to a matching open issue when supported.
4. Draft the new issue or matching-issue evidence comment and its optional fields.
5. For user-requested or offered attachments, follow
   [references/attachments.md](references/attachments.md).
6. Run the applicable quality gate, then preview the target, action, content,
   fields, and attachment manifest. For a new issue, Priority remains unset.
7. Wait for explicit confirmation; approval of a draft is not approval to create.
8. Once confirmed, follow [references/jira-creation.md](references/jira-creation.md).
9. Return the issue key and URL, or the exact failure without retrying an
   uncertain write. This skill is attended by design; do not diagnose or fix.
