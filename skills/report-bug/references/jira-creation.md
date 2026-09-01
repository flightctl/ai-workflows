# Jira Creation

This procedure starts only after the user explicitly approves the complete
preview.

## Revalidate the target

Use the transport plan resolved through
[jira-integration.md](jira-integration.md). For an existing issue, verify its
identity, current status, and comment permission. Before creating, verify the
resolved project and issue type are accessible and resolve configured fields by
name. Do not reuse field or option IDs learned from another Jira project.

The built-in EDM fallback profile expects:

- Project: `EDM` (`Flight Control`)
- Issue type: `Bug`
- Severity: `Critical`, `Important`, `Moderate`, `Low`, `Informational`
- Priority default: `Undefined`

Treat these as expected values, not permanent numeric IDs. Resolve live field
and option IDs when the integration requires IDs. If metadata has changed,
stop and show the discrepancy; do not silently substitute another field/value.

## Add evidence to an existing issue

If the user selected an existing open issue, do not create a new one. Preview
and obtain explicit confirmation for a concise comment containing only the new
reproduction evidence, impact, environment, and diagnostic signals. Do not
change the existing Summary, Severity, Priority, ownership, or planning fields.
Post the approved comment once, then perform only separately approved attachment
follow-up. If the integration cannot comment, return the proposed comment for
the user to apply manually.

If a timeout or connection loss makes the comment outcome uncertain, list the
known issue's recent comments and compare authenticated author, exact or
distinctive comment text, and creation time. If that check cannot establish the
outcome, report it as uncertain and do not post the comment again. Any retry
requires evidence that the first comment was not created and renewed explicit
approval.

## Create once

Submit the approved Summary, Description, configured Environment and Severity
fields when available, validated parent, user-confirmed Affects Version,
explicitly requested assignee, and other approved optional fields. Omit Priority
from every request so the target Jira applies its unset/default value for
triage. Never submit Fix Version or Target Version.

Prefer an integration that returns the created issue key atomically. An MCP or
native create tool must support every approved field; do not silently drop a
field because its schema is inconvenient. With the REST API, send one
`POST /rest/api/3/issue`; render Description as ADF by following
[rendering.md](rendering.md), and use the same structured approach for other
rich-text fields. Encode custom select fields as their resolved option IDs.
Keep credentials out of command arguments, logs, artifacts, and output.

No client-side technique makes creation exactly-once across every supported Jira
transport. Do not use an unbounded or automatic retry. If the request
definitively fails before Jira accepts it, report the response and allow the
user to approve a corrected retry.
If a timeout or connection loss makes the outcome uncertain, search for the
exact summary, reporter, distinctive description text, and creation time window
before doing anything else. State that this reconciliation is best-effort. Never
create again unless the first request is shown not to have succeeded and the user
explicitly approves another attempt.

## Optional follow-up

After a successful create, add only links and attachments that appeared in the
approved preview. For attachments, follow
[attachments.md](attachments.md), including the pre-upload change check and
per-file result reporting. If optional follow-up fails, keep the created bug and
report which operation remains incomplete; do not delete or recreate the issue.

Return:

```text
Bug reported: <Jira URL>
Severity: <value>
Priority: Unset (for triage)
Next step: /bugfix:assess <Jira URL>
```

For an evidence comment, return the issue URL and comment result instead. Suggest
`/bugfix:assess <Jira URL>` only for an ordinary software defect. Do not route a
suspected vulnerability to `bugfix` or `cve-fix`; follow the consuming team's
restricted security-reporting process.
