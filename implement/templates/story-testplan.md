# Story Test Plan — {issue-key}

- **Source:** {comma-separated list of contributing source files, e.g., testplan.md, hw-validation.md}
- **Story:** {issue-key} — {story-title}
- **Test cases:** {count of automatable + manual TCs}
- **Manual verification:** {count or 0}
- **Qualification gates:** {count or 0}
- **Companion artifacts:** {comma-separated list of companion files with purposes, e.g., "hw-validation.md (Hardware qualification)" or "None — primary testplan only"}

One `## {tc-id}` section per filtered story test case:

## {tc-id}: {scenario title}

| Requirement | Interface Change | Priority | Automation | Source |
|-------------|------------------|----------|------------|--------|
| {requirement-id} | {interface-change-id} | {priority} | {automation} | {source-filename} |

{For TCs from companion artifacts, Source names the companion file
 (e.g., hw-validation.md). For primary testplan TCs, Source is the
 filename discovered via the validation index (e.g., testplan.md)
 — use the actual discovered primary filename, not a hardcoded
 literal. The Source column preserves TC origin for traceability.}

### Preconditions

- {precondition}

### Steps

1. {step}
2. {step}

### Expected Results

- {expected outcome}

---

For manual verification TCs, use this format:

## {tc-id}: {scenario title} [Manual verification]

| Requirement | Interface Change | Priority | Automation | Source |
|-------------|------------------|----------|------------|--------|
| {requirement-id} | {interface-change-id} | {priority} | manual | {source-filename} |

- **Verification method:** {what the human verifier checks}
- **Original criteria:** {steps and expected results from the source TC, or "see source TC {tc-id} in {source-filename}"}
- **Evidence status:** not-started

---

For qualification-gate TCs, use this format:

## {tc-id}: {scenario title} [Qualification gate]

| Requirement | Interface Change | Priority | Verification | Source |
|-------------|------------------|----------|--------------|--------|
| {requirement-id} | {interface-change-id} | {priority} | {verification-method} | {source-filename} |

- **Source artifact:** {source-filename, e.g., testplan.md or hw-validation.md}
- **Designated environment:** {e.g., hardware device lab, security audit tooling}
- **Required evidence:** {what must be produced — test report, certification, sign-off}
- **Expected Results:** {copy the source TC's Expected Results verbatim; if unavailable, "criteria not available from source — clarification needed"}
- **Evidence status:** not-started

The `[Qualification gate]` / `[Manual verification]` suffix in the
heading and the `Verification` / `manual` Automation value distinguish
these from automatable TCs.
Evidence status values: `not-started`, `pending`, `verified`, `failed`.

---

## Qualification Gates

{Non-TC qualification gates that apply to this story. These are
 gates from the source testplan that are NOT individual test cases
 but represent cross-cutting validation requirements (e.g., hardware
 certification, security audit, performance benchmark threshold).
 Include this section when the source testplan contains non-TC
 qualification gates, regardless of whether TC sections also exist.
 Omit this section entirely when no non-TC qualification gates apply.}

| Gate | Requirement | Source | Type | Required Evidence | Reviewer | Status |
|------|-------------|--------|------|-------------------|----------|--------|
| {gate-heading} | {requirement-id} | {source-filename} | {gate-type} | {what must be produced} | {designated reviewer or "unassigned"} | not-started |

{For gate-only plans (zero TC sections), this is the only content
 section. For mixed plans (TC sections above plus gates), this
 section follows the TC sections. Preserve the gate's original
 provenance: type, requirements, interface changes, and required
 evidence from the source testplan. When a gate's details are
 unavailable from the source, mark as "clarification needed" —
 do not invent requirements or evidence criteria.}
