#!/usr/bin/env python3
"""Render a triage report by filling an HTML template with analyzed data.

Replaces placeholder tokens in the HTML template with data from the
analysis phase and AI-generated synthesis, producing a single self-contained
HTML file that can be opened in any browser.

Usage:
    render_report.py --analyzed PATH --template PATH --issues PATH
                     --ai-input PATH --output PATH [--project-key KEY]

Exit codes:
    0 — report rendered successfully
    1 — invalid or missing input (file not found, malformed JSON)
    2 — unreplaced placeholders remain in the output
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Placeholders the template expects, grouped by how their replacement
# values are serialized into the HTML.
_STRING_PLACEHOLDERS = ("PROJECT_KEY", "REPORT_DATE", "TOTAL_ISSUES")
_URL_PLACEHOLDERS = ("JIRA_BASE_URL",)
_JSON_PLACEHOLDERS = (
    "ISSUES_JSON",
    "CLUSTERS_JSON",
    "KEY_RECOMMENDATIONS_JSON",
    "EXECUTIVE_SUMMARY_JSON",
    "RELEASE_RISK_JSON",
)
ALL_PLACEHOLDERS = _STRING_PLACEHOLDERS + _URL_PLACEHOLDERS + _JSON_PLACEHOLDERS

# Matches the exact placeholder tokens used in the template.  Must not
# match JavaScript's {} empty-object literals or CSS var(...) values.
_PLACEHOLDER_RE = re.compile(
    r"\{(" + "|".join(re.escape(p) for p in ALL_PLACEHOLDERS) + r")\}"
)

# Matches any ALL-CAPS token in braces (e.g. {RELEASE_RISK}).  Used only
# to scan the template for tokens that are NOT declared in
# ALL_PLACEHOLDERS — i.e. template/script drift such as a typo'd
# {RELEASE_RISK} for {RELEASE_RISK_JSON}.  Never run against replacement
# values, so placeholder-shaped text in issue data is not misread.
_TEMPLATE_TOKEN_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


def _read_json(path: Path, label: str) -> Any:
    """Read and parse a JSON file, raising SystemExit on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: {label} not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except (OSError, UnicodeError) as exc:
        print(f"Error: cannot read {label}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: {label} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(1)


def _read_text(path: Path, label: str) -> str:
    """Read a text file, raising SystemExit on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: {label} not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except (OSError, UnicodeError) as exc:
        print(f"Error: cannot read {label}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def extract_project_key(issues: list[dict]) -> str | None:
    """Derive the Jira project key from the first issue's key.

    Returns None if the issue list is empty or the key has no hyphen.

    >>> extract_project_key([{"key": "EDM-1234"}])
    'EDM'
    >>> extract_project_key([])
    """
    if not issues:
        return None
    key = issues[0].get("key", "")
    if "-" in key:
        return key.rsplit("-", 1)[0]
    return None


def extract_jira_base_url(issues_data: object) -> str:
    """Return the Jira instance base URL recorded by the /scan phase.

    The URL is read from the ``jiraBaseUrl`` field of issues.json rather
    than being passed on the command line. A value that originates from
    the Jira server's ``self`` links must never be interpolated into a
    shell command by the agent — reading it here keeps that
    server-controlled data out of shell source entirely.
    """
    url = issues_data.get("jiraBaseUrl") if isinstance(issues_data, dict) else None
    if not isinstance(url, str) or not url.strip():
        print(
            "Error: issues.json is missing a 'jiraBaseUrl' string; "
            "re-run /scan or add the field",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return url


def _json_for_script_block(data: Any) -> str:
    """Serialize data as compact JSON safe for embedding in an HTML <script>.

    Plain ``json.dumps`` does not escape sequences that terminate or
    interfere with a ``<script>`` block.  This wrapper applies the two
    standard mitigations (see OWASP XSS Prevention Cheat Sheet):

    * ``</``  → ``<\\/``  — prevents a literal ``</script>`` from closing
      the block early.  ``\\/`` is a valid JSON escape per RFC 8259.
    * ``<!--`` → ``\\u003c!--`` — prevents an HTML comment from opening
      inside the script block.  Uses a unicode escape for ``<`` because
      ``\\!`` is not a valid JSON escape sequence.
    """
    raw = json.dumps(data, separators=(",", ":"))
    return raw.replace("</", "<\\/").replace("<!--", "\\u003c!--")


def _escape_for_js_string(value: str) -> str:
    """Escape a value for safe embedding in a JavaScript string literal.

    Handles backslashes, quotes, newlines, and sequences that could
    break out of a ``<script>`` block (``</`` and ``<!--``).
    """
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("</", "<\\/")
    value = value.replace("<!--", "\\u003c!--")
    return value


def build_replacements(
    *,
    analyzed: dict,
    ai_input: dict,
    jira_url: str,
    project_key: str | None = None,
) -> dict[str, str]:
    """Build the placeholder-to-value mapping for template rendering.

    Each value is already serialized as a string suitable for direct
    substitution into the HTML template.
    """
    issues = analyzed.get("issues", [])
    clusters = analyzed.get("clusters", [])
    key_recommendations = analyzed.get("keyRecommendations", [])

    executive_summary = ai_input.get("executiveSummary", [])
    release_risk = ai_input.get("releaseRisk")

    resolved_key = project_key or extract_project_key(issues) or "UNKNOWN"
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_issues = str(len(issues))

    return {
        "PROJECT_KEY": html.escape(resolved_key),
        "REPORT_DATE": html.escape(report_date),
        "TOTAL_ISSUES": html.escape(total_issues),
        "JIRA_BASE_URL": _escape_for_js_string(jira_url.rstrip("/")),
        "ISSUES_JSON": _json_for_script_block(issues),
        "CLUSTERS_JSON": _json_for_script_block(clusters),
        "KEY_RECOMMENDATIONS_JSON": _json_for_script_block(key_recommendations),
        "EXECUTIVE_SUMMARY_JSON": _json_for_script_block(executive_summary),
        "RELEASE_RISK_JSON": _json_for_script_block(release_risk),
    }


def render(template: str, replacements: dict[str, str]) -> tuple[str, list[str]]:
    """Replace placeholder tokens in the template, returning the result
    and any tokens the caller must treat as a failure.

    Uses a single regex pass to replace all known placeholders at once,
    avoiding accidental double-replacement when a replacement value
    happens to contain a placeholder-shaped string.

    Two problem classes are reported through the returned ``missing``
    list, both detected against the template (not the final output), so
    replacement values that happen to contain placeholder-shaped text
    (e.g., a Jira summary containing ``{PROJECT_KEY}``) are never flagged:

    * a declared placeholder with no corresponding replacement value; and
    * an ALL-CAPS brace token in the template that is not a declared
      placeholder at all (template/script drift, e.g. a typo'd
      ``{RELEASE_RISK}`` for ``{RELEASE_RISK_JSON}``), which the narrow
      substitution pass would otherwise leave in the output verbatim.
    """
    missing: list[str] = []

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        if name in replacements:
            return replacements[name]
        missing.append(name)
        return match.group(0)

    rendered = _PLACEHOLDER_RE.sub(_sub, template)

    unknown = {
        match.group(1)
        for match in _TEMPLATE_TOKEN_RE.finditer(template)
        if match.group(1) not in ALL_PLACEHOLDERS
    }
    missing.extend(sorted(unknown))
    return rendered, missing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a triage report HTML from analyzed data.",
    )
    parser.add_argument(
        "--analyzed",
        type=Path,
        required=True,
        help="Path to analyzed.json from the /analyze phase",
    )
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Path to the HTML template (templates/report.html)",
    )
    parser.add_argument(
        "--issues",
        type=Path,
        required=True,
        help=(
            "Path to issues.json from /scan; the Jira base URL is read "
            "from its 'jiraBaseUrl' field"
        ),
    )
    parser.add_argument(
        "--ai-input",
        type=Path,
        required=True,
        help=(
            "Path to JSON file with AI-generated executiveSummary "
            "(array of strings) and releaseRisk (object or null)"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for the rendered report.html",
    )
    parser.add_argument(
        "--project-key",
        default=None,
        help=(
            "Jira project key override (e.g., EDM). "
            "If omitted, derived from the first issue's key."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    analyzed = _read_json(args.analyzed, "analyzed.json")
    issues_data = _read_json(args.issues, "issues.json")
    ai_input = _read_json(args.ai_input, "AI input")
    template = _read_text(args.template, "HTML template")

    jira_url = extract_jira_base_url(issues_data)

    replacements = build_replacements(
        analyzed=analyzed,
        ai_input=ai_input,
        jira_url=jira_url,
        project_key=args.project_key,
    )

    rendered, missing = render(template, replacements)

    if missing:
        print(
            f"Error: {len(missing)} unreplaced placeholder(s): "
            f"{', '.join(sorted(set(missing)))}",
            file=sys.stderr,
        )
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")

    project_key = replacements["PROJECT_KEY"]
    total = replacements["TOTAL_ISSUES"]
    print(f"Report rendered: {args.output}")
    print(f"Project: {project_key} — {total} issues")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
