# Jira Integration Selection

The skill is not coupled to a particular Jira client. Select an integration by
capability, using only tools and credentials already available in the user's
environment.

## Capability routing

For each operation, prefer:

1. An available Jira MCP or native Jira integration with the required
   capability.
2. An installed Jira CLI that supports the required fields and non-interactive
   operation.
3. Jira's REST API.

Use the tool inventory already exposed by the environment. Do not call a write
tool merely to test whether it exists. Tool names and payload schemas vary by
provider; inspect the available tool description instead of assuming names such
as `jira_search` or `jira_create_issue`.

Required capabilities are:

| Stage | Capability | Mutation allowed |
|---|---|---|
| Resolve target | Read project and issue-type metadata | No |
| Validate fields | Read creation fields and allowed values | No |
| Duplicate/regression check | Search and read issues | No |
| Existing match | Add one approved evidence comment | Only after confirmation |
| Create | Create one issue with the approved fields | Only after confirmation |
| Follow-up | Link issues and upload approved attachments | Only after successful creation |

MCP support is valid only when the exposed integration provides the capability
needed for that stage. For example, an MCP server with search and create but no
attachment operation may create the issue through MCP and upload attachments
through REST.

## Consistency and fallback

All transports used in one report must address the same Jira host, project, and
authenticated identity. Before mixing transports, verify those values without
displaying credentials. Do not copy opaque field or option IDs between Jira
hosts or projects.

Choose the transport plan before the confirmation preview and disclose it, for
example: `Search: Jira MCP; Comment/Create: Jira MCP; Attachments: REST`. If a preferred
transport lacks a capability, select the next available option before asking the
user to confirm.

Use [rendering.md](rendering.md) as the content contract. Markdown is a preview,
not the transport-neutral source of truth. Use a transport's Markdown conversion
only when its documented schema guarantees the required structure; otherwise
provide deterministic ADF when supported or choose another transport.

Do not switch create transports automatically after a write failure. A failure
or timeout may have created the issue even if the client did not receive the
response. Follow the uncertain-outcome check in
[jira-creation.md](jira-creation.md) before proposing any retry.

This skill is attended by design. It may gather, search, and draft without
additional approval, but it must never create an issue, comment on an existing
issue, link issues, or upload attachments without an explicit confirmation that
covers that exact mutation.

## Authentication

Use the integration's existing authentication. For REST, use credentials from
the user's approved credential mechanism or environment; never solicit a secret
in chat, embed one in configuration, place one in a command argument, or print
one in output. Missing authentication is a blocker to that transport, not
permission to discover credentials elsewhere.

For authenticated REST requests, use only the trusted host resolved through
[configuration.md](configuration.md). Disable redirects when possible. Never
forward authentication across an origin change or HTTPS downgrade; if a
same-origin redirect is necessary, validate it explicitly before resending.
