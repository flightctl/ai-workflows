# Story Test Plan — {issue-key}

- **Source:** {docs-repo-path}/testplan.md
- **Story:** {issue-key} — {story-title}
- **Test cases:** {count}
- **Qualification gates:** {count or 0}

One `## {tc-id}` section per filtered story test case:

## {tc-id}: {scenario title}

| Requirement | Interface Change | Priority | Automation |
|-------------|------------------|----------|------------|
| {requirement-id} | {interface-change-id} | {priority} | {automation} |

### Preconditions

- {precondition}

### Steps

1. {step}
2. {step}

### Expected Results

- {expected outcome}

---

For qualification-gate TCs, use this format instead:

## {tc-id}: {scenario title} [Qualification gate]

| Requirement | Interface Change | Priority | Verification |
|-------------|------------------|----------|--------------|
| {requirement-id} | {interface-change-id} | {priority} | {verification-method} |

- **Source artifact:** {source-filename, e.g., testplan.md or hw-validation.md}
- **Designated environment:** {e.g., hardware device lab, security audit tooling}
- **Required evidence:** {what must be produced — test report, certification, sign-off}
- **Evidence status:** not-started

The `[Qualification gate]` suffix in the heading and the `Verification`
column (instead of `Automation`) distinguish these from automatable TCs.
Evidence status values: `not-started`, `pending`, `verified`, `failed`.
