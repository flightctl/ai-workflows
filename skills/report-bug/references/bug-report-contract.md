# Bug Report Contract

## Target-independent rules

Use the Jira target, template, and field vocabulary resolved through
[configuration.md](configuration.md). Set a dedicated **Severity** field when
the target provides one; otherwise include a clearly labeled severity and its
justification in the description. Always leave **Priority** unset. Severity
describes observed impact; Priority is a triage decision about when to act.

## Summary

Write a concise Summary in the form `<component or operation>: <observable
failure>`. Aim for 120 characters or fewer, while retaining the terms needed to
distinguish and search for the defect. Describe the symptom rather than an
unsupported cause or proposed fix. Do not add Severity or Priority prefixes,
credentials, personal data, customer identifiers, or other sensitive content.
Keep Summary as a separate Jira field; it is not part of the rendered Description.

## Evidence to gather

Use conversation context first. Inspect logs, screenshots, configuration, or
source only when the user supplied them or placed them in scope. Before drafting,
establish as many of these as the available evidence supports:

- the user-visible symptom and affected operation;
- minimal, ordered reproduction steps, their source, and any prerequisites;
- expected and actual results;
- observed attempt/success counts when known, including who observed them, plus
  timing, intermittency, and whether the written steps were independently run;
- product/version, OS, architecture, platform, deployment mode, load conditions,
  feature flags, and other relevant configuration;
- exact error type, code, message excerpt, and useful stack frames;
- useful trace, correlation, request, or event IDs and sanitized links to error
  trackers, traces, logs, or dashboards;
- affected component and the narrowest demonstrated scope;
- affected users or workflows, frequency, blast radius, onset/duration, and
  data or security consequences;
- known workaround and whether it is viable;
- first-known-good/first-known-bad versions or a prior fixed issue, when known;
- sanitized supporting evidence and links.

Do not imply that steps were verified merely because they are clear. Identify
whether they were supplied and run by the reporter, derived from supplied
evidence, or rewritten for clarity. The reporting agent must say that it did not
independently execute them unless it has direct evidence otherwise. Keep
conditional reproduction facts with the rate, such as `3/3 under load on ARM64;
0/3 without load`.

When a regression is plausible, ask for the earliest known affected version and
latest known unaffected version. Treat recalled versions as reporter evidence,
not a verified bisection. Preserve exact version or build identifiers.

Format an available text Environment field consistently: product/build;
OS/architecture; deployment mode; relevant flags/configuration; and triggering
conditions. Omit unknown dimensions rather than filling them speculatively.

## Planning and ownership fields

Resolve these optional inputs before the confirmation preview:

- **Parent relationship:** Use the configured parent field. Derive a candidate
  parent from an explicitly referenced Epic, Feature, Story, Task, or other Jira
  issue. If more than one candidate is plausible, ask the user. Validate that
  the selected issue is legal in the target project's hierarchy; omit the field
  when there is no parent. Do not label a generic parent as an Epic unless Jira
  confirms that issue type.
- **Affects Version:** This records the version or release where the bug was
  actually observed. A version from the environment, conversation, or parent
  planning context may be offered as a suggestion, but never set it without the
  user's explicit confirmation. Validate the confirmed value against live Jira
  options. Omit it when unknown or declined.
- **Assignee:** Leave unassigned unless the user explicitly requests an
  assignee. Resolve and validate the requested Jira user before creation; if the
  identity is ambiguous, ask rather than guessing.

Never set **Fix Version** or **Target Version**. They describe planned delivery,
not the observed defect, and belong to triage or planning.

Ask a focused question for information whose absence would prevent another
person from reproducing the failure or judging its impact. Unknown optional
details may be stated as `Unknown`; do not manufacture completeness.

Do not include credentials, tokens, personal data, customer-identifying data,
or internal hostnames. Redact secrets from excerpts. Treat a plausible security
vulnerability as sensitive: stop and ask the user whether the project's
restricted security-reporting path should be used.

## Severity

Choose the highest level supported by demonstrated impact, not by urgency,
reporter importance, target release, or ease of repair:

| Canonical level | Evidence-based meaning |
|---|---|
| Critical | Catastrophic impact such as widespread outage, unrecoverable data loss/corruption, or critical security exposure with no viable mitigation |
| High | Major functionality unavailable, serious regression, or broad user impact; a workaround is absent or costly |
| Medium | Material defect affecting a bounded workflow; a reasonable workaround or limited blast radius exists |
| Low | Minor functional or usability impact with an easy workaround |
| Informational | Cosmetic, documentation, or negligible operational impact |

Map the canonical level to the target project's configured and live-validated
severity vocabulary. For EDM, the mapping is Critical → Critical, High →
Important, Medium → Moderate, Low → Low, and Informational → Informational.
For other projects, use an explicit `severity_mapping`. If none exists, ask the
user to map the live Jira options before selecting Severity; do not guess from
their order or labels.
When evidence falls between levels, choose the lower level and state what
missing fact could raise it. Include the impact facts in the description so
triage can independently validate Severity. Never set or recommend Priority
during reporting.

## Duplicate and regression check

Before the confirmation gate, search the target project from up to three
angles: exact error/code, component plus symptom (including reasonable
synonyms), and distinctive summary terms. Also search resolved bugs in the same
area. A resolved issue is a regression candidate only if it was resolved before
this bug began. Compare retrieved candidates by underlying symptom, conditions,
and evidence rather than requiring identical wording.

Present strong candidates with links and a short comparison. Recommend updating
an existing open issue only when it describes the same underlying failure and
already contains an equally actionable report. Offer a previewed evidence comment
when the selected integration supports it; otherwise provide the proposed comment
for the user to apply. Do not create a duplicate merely because commenting is
unavailable.

For a new report, preserve comparisons that would matter to a later fixer or
auditor. Put a concise `Related issue comparison` in the Description and link the
candidate when supported. Omit weak search results and routine rejected matches.

## Evidence-comment quality gate

Before requesting confirmation for a comment, show the exact target issue and
comment body. Ensure the comment contributes material new evidence, identifies
the observation and step-verification source, distinguishes this occurrence from
the existing report when necessary, contains no sensitive content, and does not
claim to change Severity, Priority, ownership, or planning fields. Apply the
attachment manifest and safety gate to any proposed uploads.

## Built-in EDM-style fallback template

The executable template is `../templates/default.md`; follow
[rendering.md](rendering.md). It produces these headings in this order. Omit
empty optional content, not required headings.

```markdown
## Description of the problem

<Concise user-visible failure, affected scope, impact, and workaround. Separate
observed facts from any explicitly labeled, evidence-backed analysis.>

## How reproducible

<Observed frequency and actor, such as "5/5 attempts by reporter"; state the
source of the written steps and whether the reporting agent independently ran them.>

## Steps to reproduce

1. <Precondition or starting state>
2. <Minimal action with concrete inputs>
3. <Action that triggers the failure>

## Actual results

<Specific observable result. Preserve exact error codes and short sanitized
messages in code formatting or a fenced block.>

## Expected results

<Specific observable behavior that defines success.>
```

Put environment details in the target's configured environment field when
available. Set **Components**, labels, and attachments only when supported by
evidence or explicitly requested. Resolve parent, Affects Version, and assignee
through the rules above.

## New-issue quality gate

Do not request creation confirmation until all of the following are true:

- the summary identifies the affected operation/component and failure symptom;
- actual and expected results are observably different;
- steps are executable by someone without access to this conversation, or the
  report clearly explains why reliable steps cannot yet be provided;
- the report distinguishes observed frequency from the source and independent
  verification status of its written steps;
- impact claims justify the selected Severity without exaggeration; when a
  dedicated Severity field is used, its mapped value exists in live metadata,
  otherwise the Description contains the labeled level and justification;
- exact diagnostic signals and environment/version are included when known;
- unknowns and intermittency are explicit;
- no proposed fix is presented as fact and no unsupported root cause is claimed;
- sensitive content is removed;
- optional attachments have an approved manifest and passed the attachment
  safety review;
- parent, Affects Version, and assignee are either validated or explicitly
  shown as not set;
- material duplicate/regression comparisons have been checked and retained; and
- the report is bounded enough for a fixing agent to identify a testable outcome.

If the gate fails on essential reproduction, outcome, or impact information,
ask for it instead of creating an incomplete ticket by default. If the user
explicitly chooses to report despite a remaining gap, retain the gap visibly
and lower confidence/severity as appropriate.
