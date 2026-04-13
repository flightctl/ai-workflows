# {Title}

| Field       | Value                                 |
|-------------|---------------------------------------|
| Author(s)   | {user}                                |
| Status      | Draft                                 |
| Jira        | [{issue-key}]({issue-url})            |
| Date        | {today}                               |

# 1. Overview

{Primary requirement from the PRD and the technical approach being proposed.
1-2 paragraphs. Link to the PRD.}

# 2. Goals and Non-Goals

## 2.1 Goals

- {Design-scoped goals — implementation constraints, not product outcomes}

## 2.2 Non-Goals

- {What this design explicitly does NOT cover}

# 3. Motivation / Background

{The existing problem restated in implementation terms. Limitations of the
current system. Rationale for the proposed approach. Keep brief — this bridges
from the PRD for technical reviewers who may not have read it.}

# 4. Design

## 4.1 Architecture

{High-level overview, component responsibilities, and data flow.}

{Use Mermaid diagrams where they add clarity — any diagram type that best
communicates the concept. Every diagram MUST be accompanied by narrative
explaining what it shows and what the reader should take away from it.}

## 4.2 Data Model / Schema Changes

{New tables, fields, constraints, index changes, or migrations.
If no schema changes: "No schema changes required."}

## 4.3 API Changes

{New endpoints, request/response formats, validation rules, versioning
impact. Include concrete examples where they aid understanding.
If no API changes: "No API changes required."}

## 4.4 Scalability and Performance

Estimate impact on:

- CPU and memory usage
- Database load (reads/writes) and storage
- Data retention and cleanup policies

State assumptions about expected scale and future growth.

{If minimal impact, state so explicitly with brief justification
(e.g., "Processing occurs only during application install/update and
is lightweight for single containers").}

## 4.5 Security Considerations

{Potential vulnerabilities, authentication/authorization changes, data
exposure risks, input validation.
If no new security concerns: state that the feature inherits the existing
security model and explain why.}

## 4.6 Failure Handling and Recovery

{Behavior under partial failure, retries, idempotency, recovery flows.}

## 4.7 RBAC / Tenancy

Describe:

- Role-based access rules
- Tenancy or org/resource isolation
- Visibility constraints and edge cases

{If no changes: "No RBAC or tenancy changes required."}

## 4.8 Extensibility / Future-Proofing

{How the design accommodates future enhancements without over-engineering.
If straightforward: state that briefly.}

# 5. Alternatives Considered

{Other approaches evaluated and why they were not selected. Include at least
one alternative for each non-trivial design decision.}

# 6. Observability and Monitoring

{New metrics, events, alerts, tracing spans, or log events.
If none: "No new observability changes. Existing monitoring mechanisms apply."}

# 7. Impact and Compatibility

Note any:

- Backward-incompatible changes
- DB migration impacts
- Changes to existing APIs or workflows
- Version compatibility considerations

# 8. Open Questions

{Numbered list. Track outcomes as decisions are made — preserve the original
question alongside the resolution.}

1. **{Question}**

   Outcome: {Resolution, or "Open"}

# Appendix: Review Notes

## Assumptions

- [{Section reference}] {Assumption made and rationale}

## Items Needing Resolution

- [{Section reference}] {Item that needs reviewer attention}
