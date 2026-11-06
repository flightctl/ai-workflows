# Story Test Plan — {issue-key}

- **Source:** {comma-separated list of contributing source files, e.g., testplan.md, hw-validation.md}
- **Story:** {issue-key} — {story-title}
- **Test cases:** {count of automatable + manual TCs}
- **Manual verification:** {count or 0}
- **Qualification gates:** {count or 0}

One `## {tc-id}` section per filtered story test case:

## {tc-id}: {scenario title}

| Requirement | Interface Change | Priority | Automation | Source |
|-------------|------------------|----------|------------|--------|
| {requirement-id} | {interface-change-id} | {priority} | {automation} | {source-filename} |

{For TCs from companion artifacts, Source names the companion file
 (e.g., hw-validation.md). For primary testplan TCs, Source is
 testplan.md. The Source column preserves TC origin for traceability.}

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
- **Evidence status:** not-started

The `[Qualification gate]` / `[Manual verification]` suffix in the
heading and the `Verification` / `manual` Automation value distinguish
these from automatable TCs.
Evidence status values: `not-started`, `pending`, `verified`, `failed`.
