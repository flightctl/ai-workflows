# Optional Attachments

Attachments are optional. A file being mentioned, inspected, or used as
evidence does not imply approval to upload it.

## Select files

Consider only files explicitly supplied by the user, named in the conversation,
or found within a user-approved narrow location. Do not scan broad directories
for possible attachments. Resolve each path canonically, reject broken links and
non-regular files, and do not follow a symlink outside the approved scope without
asking.

Ask whether each candidate should be:

- used to extract or summarize evidence in the description;
- uploaded to Jira; both; or neither.

Do not require an attachment when the report is already actionable. Prefer a
short, sanitized diagnostic excerpt in the description for information central
to reproduction or triage; an attachment alone should not hide essential facts.

## Inspect and sanitize

Inspect every proposed upload before the confirmation gate. Use an appropriate
reader for the type; visually inspect screenshots when image viewing is
available. Check at least for credentials, tokens, cookies, private keys,
authorization headers, personal or customer data, internal hostnames/IPs,
account identifiers, and unrelated confidential content.

- **Logs:** retain the smallest useful time window and redact secrets and
  identifiers while preserving timestamps, error codes, and relevant context.
- **Configuration:** prefer a minimal sanitized copy containing only relevant
  keys. Replace sensitive values with explicit markers such as `<redacted>`;
  do not merely hide them from the description while uploading the original.
- **Screenshots:** crop or redact unrelated windows, notifications, usernames,
  URLs, identifiers, and secrets. If safe editing is unavailable, ask the user
  for a sanitized image or omit it.
- **Archives/binary files:** do not assume their contents are safe. Before
  extraction, enforce entry-count and expanded-size limits; reject absolute or
  parent-traversal paths, symlinks, and hard links. Extract into a secure
  temporary directory only after verifying every canonical destination remains
  inside it, then inspect the listing and relevant contents. Otherwise, ask the
  user to provide a reviewable form.

Never modify the original. Create a clearly named sanitized derivative in a
securely created, owner-only temporary directory outside the repository and its
artifact directories. Show the user what categories were removed. If safe
sanitization would destroy material
evidence or cannot be verified, do not upload the file; direct the user to the
team's approved secure evidence-handling process instead.

Check live Jira attachment constraints, including permission, maximum size, and
supported upload mechanism. Report an unsupported or oversized file before
confirmation; do not silently compress, split, or transform it.

## Confirmation manifest

Include an exact manifest with the full issue preview:

| Source | Jira filename | Purpose | Description use | Upload | Safety action |
|---|---|---|---|---|---|
| `/path/error.log` | `error-sanitized.log` | Failure diagnostics | Key excerpt | Yes | Token and hostname redacted |

Use `None` when there are no attachments. Approval applies only to the listed
files, filenames, and sanitized versions. Any later addition or changed file
requires a new preview and confirmation. Recheck that each approved file still
matches the reviewed file immediately before upload; if it changed, stop and
review it again.

## Upload and report

Upload approved attachments only after the bug exists, using the attachment
transport selected through [jira-integration.md](jira-integration.md). An MCP
create capability does not imply an MCP attachment capability. Do not print file
contents or credentials during upload. Record success or failure per file.

An attachment failure does not invalidate the created bug. Do not delete or
recreate it, and do not retry automatically when the outcome is uncertain.
Return the issue URL, the status of every approved attachment, and a safe manual
next step for anything not uploaded.

Remove sanitized derivatives and their temporary directory after upload, after
the user cancels, or after any failure. If the user explicitly requests
retention, agree on an approved secure destination and exact retained files
before copying them. Never retain the structured report merely because an
attachment must be retained.
