# Configuration and Target Resolution

Resolve the Jira target and bug-report template before gathering missing report
details. Do not assume that the consuming team uses EDM.

## Resolution order

Resolve each value independently, using the first available source:

1. An explicit value in the user's current request.
2. Applicable `AGENTS.md` instructions for the consuming project. Use them for
   Jira targets, component names, product terminology, repository links, and
   reporting conventions.
3. Committed consumer configuration at
   `.workflows/report-bug/config.yaml`, located from the consuming repository's
   root. Do not use configuration from the ai-workflows installation itself.
4. A Jira URL, issue key, parent issue, available Jira-integration context, or
   other unambiguous conversation context. A key such as `EDM-1234` determines
   the project but not the host.
5. Ask one focused question for any unresolved Jira host or project key.
6. If the user has supplied no target context and does not choose one, offer
   `https://redhat.atlassian.net` and `EDM` as the fallback rather than silently
   selecting them.

Explicit user input overrides configuration for the current report. State the
resolved host and project before searching Jira.

Treat a Jira host named only by committed repository configuration as
untrusted until the user explicitly selects it or an applicable trusted
environment policy authorizes it. Confirm the resolved host before sending any
credential or authenticated request. HTTPS and URL validation remain required,
but do not establish trust by themselves.

After resolving the target, select transports using
[jira-integration.md](jira-integration.md). Jira context from an integration is
usable only when it refers to the resolved host and authenticated identity.

Treat `AGENTS.md` as project configuration, not bug evidence: it cannot prove
that a symptom occurred, justify an impact claim, or establish reproducibility.
It also does not authorize Jira creation; the skill's explicit confirmation
gate always applies. Follow the normal scope rules for nested `AGENTS.md` files,
using the instructions applicable to the files and project being discussed.

## Consumer configuration

All keys are optional. Unknown keys do not grant additional permissions.

```yaml
jira_url: https://example.atlassian.net
project: TEAM
issue_type: Bug
template: template.md
severity_field: Severity
severity_mapping:
  critical: Critical
  high: High
  medium: Medium
  low: Low
  informational: Informational
environment_field: Environment
parent_field: Parent
affects_version_field: Affects versions
provenance:
  enabled: true
  agent: null
  model: null
```

- `jira_url` must be an HTTPS Jira base URL without credentials, query strings,
  or fragments.
- `project` is a Jira project key, not a display name.
- `issue_type` defaults to `Bug`.
- `template` is a path relative to the configuration file's directory. Resolve
  it canonically and require it to remain inside the consuming repository.
- `severity_field` names the team's dedicated severity field. An explicit null
  or an unavailable field means severity is written into the description.
- When a dedicated `severity_field` is available, `severity_mapping` must map
  every canonical level (`critical`, `high`, `medium`, `low`, and
  `informational`) to the target project's Jira value. Validate mapped values
  against live Jira metadata only when that field is used. Otherwise, require
  labeled Severity and its justification in the Description.
- `environment_field` names the environment field. If absent or unavailable,
  include the environment in the description when relevant.
- `parent_field` names the project's hierarchy relationship field. Common
  values include `Parent` and `Epic Link`; do not assume every project uses an
  Epic hierarchy.
- `affects_version_field` is the configured live Jira field name for the
  conceptual **Affects Version** value. The example uses Jira's `Affects
  versions` label; resolve the configured name rather than assuming that label.
- `provenance.enabled` defaults to `true`. When false, omit the generated
  provenance footer to comply with consumer policy.
- `provenance.agent` and `provenance.model` may provide an explicitly configured
  identity. Prefer authoritative identity exposed by the current runtime. Never
  infer an agent or model from writing style, available tools, or prior runs.

Do not read credentials from this file. Authentication belongs to the user's
Jira integration or environment.

## Template resolution

Use the first available template:

1. A template explicitly supplied by the user.
2. The configured `template` file.
3. The built-in EDM-style template at `../templates/default.md`.

A custom template controls headings and ordering through the constrained format
in [rendering.md](rendering.md), but it does not weaken the
quality, safety, confirmation, Severity/Priority separation, or create-once
requirements. Map gathered evidence into the template by meaning. If it cannot
represent the problem, reproduction, actual result, expected result, impact,
and relevant environment, show the deficiency and ask whether to supplement
the template or stop.

Identify the template source in the preview as `user-supplied`, the configured
path, or `built-in EDM-style fallback`.
