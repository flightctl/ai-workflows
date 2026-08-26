---
name: content-rules
version: 0.1.0
---
# Generated Content Rules

Shared rules for what must not appear in workflow-generated content — artifacts,
published documents, commit messages, PR descriptions, code comments added by
the workflow, and other output produced during workflow execution.

All workflows must follow these rules.

## No Personal Names in Generated Content

Replace references to individuals from Jira tickets, comments, commit history,
code comments, or other source material with role-based descriptions (e.g.,
"the security reviewer noted…", "the reporter described…", "the author noted…").
When the person's role is unknown, use a generic attribution ("a reviewer noted…",
"feedback identified…") or drop the attribution and state the finding directly.

**Exempt:** Author metadata fields in planning documents (PRDs, designs) that
identify the document author, not individuals referenced in the source material.

## No Customer-Specific Data in Generated Content

Do not include information that identifies or describes a specific customer's
environment, deployment, or business context in any workflow artifact or
published output. When source material contains customer-specific details,
generalize them while preserving requirement or issue intent:

- Replace customer or organization names with generic descriptions ("a customer",
  "an enterprise deployment")
- Omit or generalize hostnames, IP addresses, cluster names, namespaces, account
  or subscription IDs, and region-specific topology
- Describe scale and constraints generically ("large multi-node clusters",
  "air-gapped environments") rather than a particular customer's infrastructure
  footprint
- Omit support case numbers, internal account references, and other identifiers
  tied to a specific customer

Verbatim reproduction of customer-identifying content from Jira, tickets, logs,
or user input is not permitted — abstract the requirement or issue, not the
customer's identity.

**When capturing source material:** Generalize customer-specific details at
capture time (ingest, gather, or equivalent early phases). Preserve what the
feature or issue must support, not who reported it or where they run it.
