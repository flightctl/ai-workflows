# Structured Rendering

The canonical description is structured JSON, not Markdown or ADF. Use
`scripts/render_issue.py` to render the confirmation preview and Jira ADF from
the same input. Do not hand-convert Markdown to ADF.

## Input model

```json
{
  "description": "Observed failure, scope, impact, and workaround.",
  "reproducibility": "Observed 5/5 attempts by reporter; reporter-provided steps, not independently run by reporting agent",
  "steps": ["Start from ...", "Run ...", "Observe ..."],
  "actual_results": "The operation fails with HTTP 500.",
  "diagnostics": [{"language": "text", "text": "HTTP 500: failure"}],
  "expected_results": "The operation completes successfully.",
  "links": [{"label": "Related issue", "url": "https://example.test/browse/TEAM-1"}],
  "assistant": {"agent": "Codex", "model": "gpt-5.6-sol"}
}
```

Five fields are required and non-empty: `description`, `reproducibility`,
`steps`, `actual_results`, and `expected_results`. `steps` is a non-empty array
of strings. `diagnostics` and `links` are optional arrays. Keep separate Jira
fields outside this model unless a custom template intentionally includes the
optional `{{environment}}` or `{{severity}}` scalar.

`assistant` is optional provenance metadata, not report content. Populate
`agent` and `model` only from authoritative runtime identity or explicit
consumer configuration. The renderer reads the skill name and version directly
from `SKILL.md` and appends a vendor-neutral footer. Use `--no-provenance` only
when consumer policy disables it. When assistant identity is absent, the footer
identifies only AI assistance and the skill version.

This Jira disclosure is intentionally separate from
`../../../_shared/scripts/provenance.py`. That utility records session and Git
provenance for planning documents; it does not produce the compact Markdown and
ADF disclosure required for Jira descriptions.

## Templates

The default is `templates/default.md`. Consumer templates may contain ATX
headings, plain literal paragraphs, and supported placeholders on lines by
themselves. Required placeholders, exactly once, are `description`,
`reproducibility`, `steps`, `actual_results`, and `expected_results`. Optional
placeholders, at most once, are `diagnostics`, `links`, `environment`, and
`severity`.

Arbitrary Markdown, inline placeholders, HTML, Jira wiki markup, and template
fences/lists are rejected. Values remain data: Markdown-looking characters in
plain text are escaped in the preview and emitted as literal ADF text.

## Commands

Python 3.10 or newer is required. Resolve `{REPORT_BUG_SKILL}` to the installed
skill directory. Create a temporary directory with the platform's secure
temporary-directory facility, ensure it is accessible only to the current user,
and write the structured model there with owner-only permissions:

```bash
python3 "{REPORT_BUG_SKILL}/scripts/render_issue.py" \
  --input "{TEMP_DIR}/issue.json" --template template.md --format markdown
python3 "{REPORT_BUG_SKILL}/scripts/render_issue.py" \
  --input "{TEMP_DIR}/issue.json" --template template.md --format adf
```

Use Markdown only for confirmation and ADF for a transport that accepts ADF. If
an MCP/CLI transport performs documented conversion, preserve the same model and
verify that it can represent every approved block. Never silently drop content.

Remove the temporary directory after creation and attachment follow-up, after
the user cancels, or after any failure. Do not retain the model in the consuming
repository or `.artifacts/`. If the user explicitly requests retention, agree on
an approved secure destination and contents before copying anything.
