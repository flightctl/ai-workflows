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
    3 — template or rendered output failed smoke validation

The analyzed.json and ai-synthesis.json inputs are validated against the
renderer contract documented in triage/schemas/ before any HTML is emitted.
The template is checked for "[object Object]" literals, every required
placeholder token, and required section containers before rendering, and the
rendered HTML is re-checked for those containers after placeholder
replacement.
"""

from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
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

# Section container ids the template contract requires.  The report's
# inline JavaScript populates these at runtime; a template that removes or
# renames one of them silently hides a dashboard section.
REQUIRED_SECTION_IDS = (
    "statsContainer",
    "execSummaryContainer",
    "riskContainer",
    "keyRecsContainer",
    "priorityBreakdown",
    "assigneeLoad",
    "agingAnalysis",
    "statusDistribution",
    "clustersContainer",
    "issuesTableBody",
)

ALLOWED_RECOMMENDATIONS = frozenset({
    "CLOSE", "FIX_NOW", "AUTO_FIX", "BACKLOG", "NEEDS_INFO", "DUPLICATE",
    "ESCALATE", "WONT_FIX",
})

# The exact whitespace set matched by Python's str.isspace(), shared with
# the JSON Schema patterns.  ECMA-262's \s differs (it excludes
# U+001C-U+001F and U+0085), so the class is explicit rather than \S.
NON_WHITESPACE_PATTERN = (
    r"[^\t\n\v\f\r\x1c-\x1f\u0020\u0085\u00a0\u1680"
    r"\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
)
_NON_WHITESPACE_RE = re.compile(NON_WHITESPACE_PATTERN)


def _has_non_whitespace(value: str) -> bool:
    """Return True when value contains at least one non-whitespace char."""
    return _NON_WHITESPACE_RE.search(value) is not None

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


def validate_analyzed(analyzed: object) -> None:
    """Validate the analyzed.json renderer contract before rendering.

    This is the runtime enforcement point for the schema documented in
    ``triage/schemas/analyzed.schema.json``.  It exists so that shape drift
    between the analysis phase and the HTML template (for example,
    ``keyRecommendations`` changing from strings to objects) fails loudly
    instead of rendering ``[object Object]`` or hiding a section.
    """
    if not isinstance(analyzed, dict):
        raise ValueError("analyzed.json must contain a JSON object")

    issues = analyzed.get("issues")
    if not isinstance(issues, list):
        raise ValueError("analyzed.json must contain an issues array")
    for index, issue in enumerate(issues):
        label = f"issues[{index}]"
        if not isinstance(issue, dict):
            raise ValueError(f"{label} must be an object")
        key = issue.get("key")
        if not isinstance(key, str) or not _has_non_whitespace(key):
            raise ValueError(f"{label}.key must be a non-empty string")
        if not isinstance(issue.get("summary"), str):
            raise ValueError(f"{label}.summary must be a string")
        recommendation = issue.get("recommendation")
        if (
            not isinstance(recommendation, str)
            or recommendation not in ALLOWED_RECOMMENDATIONS
        ):
            raise ValueError(
                f"{label}.recommendation must be one of: "
                f"{', '.join(sorted(ALLOWED_RECOMMENDATIONS))}"
            )
        reason = issue.get("reason")
        if not isinstance(reason, str) or not _has_non_whitespace(reason):
            raise ValueError(f"{label}.reason must be a non-empty string")
        confidence = issue.get("confidence")
        if not isinstance(confidence, str) or confidence not in {"High", "Medium", "Low"}:
            raise ValueError(f"{label}.confidence must be High, Medium, or Low")
        components = issue.get("components")
        if components is not None and (
            not isinstance(components, list)
            or not all(isinstance(component, str) for component in components)
        ):
            raise ValueError(f"{label}.components must be an array of strings or null")

    clusters = analyzed.get("clusters")
    if not isinstance(clusters, list):
        raise ValueError("analyzed.json must contain a clusters array")
    for index, cluster in enumerate(clusters):
        label = f"clusters[{index}]"
        if not isinstance(cluster, dict):
            raise ValueError(f"{label} must be an object")
        if not isinstance(cluster.get("id"), str) or not _has_non_whitespace(cluster["id"]):
            raise ValueError(f"{label}.id must be a non-empty string")
        theme = cluster.get("theme")
        if not isinstance(theme, str) or not _has_non_whitespace(theme):
            raise ValueError(f"{label}.theme must be a non-empty string")
        members = cluster.get("issues")
        if (
            not isinstance(members, list)
            or len(members) < 2
            or not all(
                isinstance(member, str) and _has_non_whitespace(member)
                for member in members
            )
        ):
            raise ValueError(f"{label}.issues must be an array of at least two issue keys")
        link_type = cluster.get("suggestedLinkType")
        if (
            not isinstance(link_type, str)
            or link_type not in {"relates to", "is caused by", "is duplicated by", "blocks"}
        ):
            raise ValueError(f"{label}.suggestedLinkType is not a supported link type")
        next_steps = cluster.get("nextSteps")
        if (
            not isinstance(next_steps, list)
            or not 2 <= len(next_steps) <= 4
            or not all(
                isinstance(step, str) and _has_non_whitespace(step)
                for step in next_steps
            )
        ):
            raise ValueError(f"{label}.nextSteps must contain 2-4 non-empty strings")

    key_recommendations = analyzed.get("keyRecommendations")
    if (
        not isinstance(key_recommendations, list)
        or len(key_recommendations) > 10
        or not all(
            isinstance(item, str) and _has_non_whitespace(item)
            for item in key_recommendations
        )
    ):
        raise ValueError(
            "keyRecommendations must be an array of at most 10 non-empty "
            "strings (objects are not part of the renderer contract)"
        )


def validate_rendered_html(rendered: str) -> None:
    """Smoke-check rendered HTML for silent template failures.

    Catches a template that dropped a section container the dashboard
    JavaScript expects to populate.  The check runs after placeholder
    replacement but before the browser executes JavaScript, so it inspects
    structure only — never embedded data text.
    """
    ids = _collect_html_ids(rendered)
    missing_ids = [
        section_id
        for section_id in REQUIRED_SECTION_IDS
        if section_id not in ids
    ]
    if missing_ids:
        raise ValueError(
            "rendered HTML is missing required section container(s): "
            + ", ".join(missing_ids)
        )


def validate_template(template: str) -> None:
    """Validate the template before any data is substituted into it.

    The template is controlled code, so a literal ``[object Object]`` in it
    is always a defect.  Scanning the template — not the rendered output —
    avoids rejecting schema-valid issue text that legitimately contains
    that string, while still catching hardcoded coercion artifacts in the
    template markup or JavaScript.
    """
    if "[object Object]" in template:
        raise ValueError(
            'template contains "[object Object]" — fix the template before '
            "rendering"
        )
    missing_placeholders = [
        name for name in ALL_PLACEHOLDERS if "{" + name + "}" not in template
    ]
    if missing_placeholders:
        raise ValueError(
            "template is missing required placeholder(s): "
            + ", ".join(missing_placeholders)
        )
    ids = _collect_html_ids(template)
    missing_ids = [
        section_id
        for section_id in REQUIRED_SECTION_IDS
        if section_id not in ids
    ]
    if missing_ids:
        raise ValueError(
            "template is missing required section container(s): "
            + ", ".join(missing_ids)
        )


class _IdCollector(HTMLParser):
    """Collect element ids from rendered HTML, ignoring script content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)


def _collect_html_ids(rendered: str) -> set[str]:
    collector = _IdCollector()
    collector.feed(rendered)
    collector.close()
    return collector.ids


def validate_ai_synthesis(ai_input: object, issue_count: int) -> None:
    """Validate the semantic report-synthesis contract before rendering."""
    if not isinstance(ai_input, dict):
        raise ValueError("AI input must be an object")
    executive_summary = ai_input.get("executiveSummary")
    if not isinstance(executive_summary, list) or not all(
        isinstance(item, str) and _has_non_whitespace(item)
        for item in executive_summary
    ):
        raise ValueError("executiveSummary must be an array of non-empty strings")
    if issue_count and not 3 <= len(executive_summary) <= 5:
        raise ValueError("non-empty reports require 3-5 executiveSummary bullets")

    if "releaseRisk" not in ai_input:
        raise ValueError(
            "releaseRisk is required (use null for reports with fewer than "
            "five issues)"
        )
    release_risk = ai_input["releaseRisk"]
    if issue_count < 5 and release_risk is not None:
        raise ValueError("releaseRisk must be null for reports with fewer than five issues")
    if issue_count >= 5 and release_risk is None:
        raise ValueError("releaseRisk must be an object for reports with five or more issues")
    if release_risk is None:
        return
    if not isinstance(release_risk, dict):
        raise ValueError("releaseRisk must be an object or null")
    risk_level = release_risk.get("riskLevel")
    if not isinstance(risk_level, str) or risk_level not in {"High", "Medium", "Low"}:
        raise ValueError("releaseRisk.riskLevel must be High, Medium, or Low")
    if (
        not isinstance(release_risk.get("summary"), str)
        or not _has_non_whitespace(release_risk["summary"])
    ):
        raise ValueError("releaseRisk.summary must be a non-empty string")
    factors = release_risk.get("factors")
    if not isinstance(factors, list) or not all(isinstance(item, dict) for item in factors):
        raise ValueError("releaseRisk.factors must be an array of objects")
    for factor in factors:
        if not all(
            isinstance(factor.get(name), str) and _has_non_whitespace(factor[name])
            for name in ("signal", "severity", "detail")
        ):
            raise ValueError("releaseRisk factors require signal, severity, and detail strings")
        if factor["severity"] not in {"High", "Medium", "Low"}:
            raise ValueError("releaseRisk factor severity must be High, Medium, or Low")
    mitigations = release_risk.get("mitigations")
    if not isinstance(mitigations, list) or not all(
        isinstance(item, str) and _has_non_whitespace(item) for item in mitigations
    ):
        raise ValueError("releaseRisk.mitigations must be an array of non-empty strings")


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

    analyzed_issues = analyzed.get("issues", []) if isinstance(analyzed, dict) else []
    issue_count = len(analyzed_issues) if isinstance(analyzed_issues, list) else 0
    try:
        validate_analyzed(analyzed)
        validate_ai_synthesis(ai_input, issue_count)
    except ValueError as exc:
        print(f"Error: invalid renderer input schema: {exc}", file=sys.stderr)
        return 1

    try:
        validate_template(template)
    except ValueError as exc:
        print(f"Error: template validation failed: {exc}", file=sys.stderr)
        return 3

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

    try:
        validate_rendered_html(rendered)
    except ValueError as exc:
        print(f"Error: post-render validation failed: {exc}", file=sys.stderr)
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")

    project_key = replacements["PROJECT_KEY"]
    total = replacements["TOTAL_ISSUES"]
    print(f"Report rendered: {args.output}")
    print(f"Project: {project_key} — {total} issues")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
