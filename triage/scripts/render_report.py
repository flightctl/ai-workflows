#!/usr/bin/env python3
"""Render a triage report by filling an HTML template with analyzed data.

Replaces placeholder tokens in the HTML template with data from the
analysis phase and AI-generated synthesis, producing a single self-contained
HTML file that can be opened in any browser.

Usage:
    render_report.py --analyzed PATH --template PATH --jira-url URL
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


def _read_json(path: Path, label: str) -> Any:
    """Read and parse a JSON file, raising SystemExit on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: {label} not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except OSError as exc:
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
    except OSError as exc:
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
    and any placeholders that had no corresponding replacement value.

    Uses a single regex pass to replace all known placeholders at once,
    avoiding accidental double-replacement when a replacement value
    happens to contain a placeholder-shaped string.

    Missing placeholders are tracked during rendering rather than by
    scanning the final output, so replacement values that happen to
    contain placeholder-shaped text (e.g., a Jira summary containing
    ``{PROJECT_KEY}``) are never flagged as unreplaced.
    """
    missing: list[str] = []

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        if name in replacements:
            return replacements[name]
        missing.append(name)
        return match.group(0)

    html = _PLACEHOLDER_RE.sub(_sub, template)
    return html, missing


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
        "--jira-url",
        required=True,
        help="Jira instance base URL (e.g., https://issues.redhat.com)",
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
    ai_input = _read_json(args.ai_input, "AI input")
    template = _read_text(args.template, "HTML template")

    replacements = build_replacements(
        analyzed=analyzed,
        ai_input=ai_input,
        jira_url=args.jira_url,
        project_key=args.project_key,
    )

    html, missing = render(template, replacements)

    if missing:
        print(
            f"Error: {len(missing)} unreplaced placeholder(s): "
            f"{', '.join(sorted(set(missing)))}",
            file=sys.stderr,
        )
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")

    project_key = replacements["PROJECT_KEY"]
    total = replacements["TOTAL_ISSUES"]
    print(f"Report rendered: {args.output}")
    print(f"Project: {project_key} — {total} issues")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
