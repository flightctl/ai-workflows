#!/usr/bin/env python3
"""Tests for triage/scripts/render_report.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "render_report.py"
_spec = importlib.util.spec_from_file_location("render_report", _SCRIPT)
assert _spec and _spec.loader
render_report = importlib.util.module_from_spec(_spec)
sys.modules["render_report"] = render_report
_spec.loader.exec_module(render_report)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_TEMPLATE = (
    "<title>{PROJECT_KEY}</title>"
    "<time>{REPORT_DATE}</time>"
    "<span>{TOTAL_ISSUES}</span>"
    '<script>var B="{JIRA_BASE_URL}";'
    "var I={ISSUES_JSON};"
    "var C={CLUSTERS_JSON};"
    "var K={KEY_RECOMMENDATIONS_JSON};"
    "var E={EXECUTIVE_SUMMARY_JSON};"
    "var R={RELEASE_RISK_JSON};</script>"
)

SAMPLE_ISSUES = [
    {"key": "EDM-101", "summary": "Bug one", "status": "Open"},
    {"key": "EDM-102", "summary": "Bug two", "status": "Closed"},
]

SAMPLE_CLUSTERS = [
    {"id": "c1", "theme": "Timeouts", "issues": ["EDM-101"]},
]

SAMPLE_KEY_RECS = ["Fix timeouts first", "Triage duplicates"]

SAMPLE_ANALYZED = {
    "issues": SAMPLE_ISSUES,
    "clusters": SAMPLE_CLUSTERS,
    "keyRecommendations": SAMPLE_KEY_RECS,
}

SAMPLE_EXEC_SUMMARY = ["Backlog is healthy.", "3 regressions found."]

SAMPLE_RELEASE_RISK = {
    "riskLevel": "Medium",
    "summary": "Some risk.",
    "factors": [{"signal": "Regressions", "severity": "High", "detail": "3 found"}],
    "mitigations": ["Fix regressions before release."],
}

SAMPLE_AI_INPUT = {
    "executiveSummary": SAMPLE_EXEC_SUMMARY,
    "releaseRisk": SAMPLE_RELEASE_RISK,
}


def _write_json(directory: Path, name: str, data: object) -> Path:
    """Write a JSON file into a directory and return its path."""
    path = directory / name
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _write_text(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit tests — pure functions (no file I/O)
# ---------------------------------------------------------------------------


class TestExtractProjectKey(unittest.TestCase):
    def test_standard_key(self) -> None:
        self.assertEqual(
            render_report.extract_project_key([{"key": "EDM-1234"}]),
            "EDM",
        )

    def test_multi_segment_project(self) -> None:
        self.assertEqual(
            render_report.extract_project_key([{"key": "MY-PROJ-42"}]),
            "MY-PROJ",
        )

    def test_empty_list(self) -> None:
        self.assertIsNone(render_report.extract_project_key([]))

    def test_no_hyphen(self) -> None:
        self.assertIsNone(render_report.extract_project_key([{"key": "NOHYPHEN"}]))

    def test_missing_key_field(self) -> None:
        self.assertIsNone(render_report.extract_project_key([{"summary": "x"}]))


class TestBuildReplacements(unittest.TestCase):
    def setUp(self) -> None:
        self.replacements = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://issues.redhat.com/",
        )

    def test_project_key_derived(self) -> None:
        self.assertEqual(self.replacements["PROJECT_KEY"], "EDM")

    def test_project_key_override(self) -> None:
        r = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com",
            project_key="OVERRIDE",
        )
        self.assertEqual(r["PROJECT_KEY"], "OVERRIDE")

    def test_jira_url_trailing_slash_stripped(self) -> None:
        self.assertEqual(
            self.replacements["JIRA_BASE_URL"],
            "https://issues.redhat.com",
        )

    def test_total_issues_is_string(self) -> None:
        self.assertEqual(self.replacements["TOTAL_ISSUES"], "2")

    def test_report_date_is_iso(self) -> None:
        self.assertRegex(
            self.replacements["REPORT_DATE"],
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        )

    def test_all_placeholders_present(self) -> None:
        for name in render_report.ALL_PLACEHOLDERS:
            self.assertIn(name, self.replacements, f"missing replacement for {name}")

    def test_json_values_are_valid(self) -> None:
        for name in ("ISSUES_JSON", "CLUSTERS_JSON", "KEY_RECOMMENDATIONS_JSON",
                      "EXECUTIVE_SUMMARY_JSON", "RELEASE_RISK_JSON"):
            json.loads(self.replacements[name])

    def test_empty_analyzed(self) -> None:
        r = render_report.build_replacements(
            analyzed={},
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com",
        )
        self.assertEqual(r["TOTAL_ISSUES"], "0")
        self.assertEqual(r["PROJECT_KEY"], "UNKNOWN")
        self.assertEqual(json.loads(r["ISSUES_JSON"]), [])

    def test_script_tag_escaped_in_json(self) -> None:
        """A </script> in issue data must be escaped to prevent HTML breakage."""
        malicious_issues = [{"key": "X-1", "summary": "</script><script>alert(1)"}]
        r = render_report.build_replacements(
            analyzed={"issues": malicious_issues, "clusters": [], "keyRecommendations": []},
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com",
        )
        self.assertNotIn("</script>", r["ISSUES_JSON"])
        self.assertIn("<\\/script>", r["ISSUES_JSON"])
        # \/ is valid JSON per RFC 8259 — json.loads handles it directly
        parsed = json.loads(r["ISSUES_JSON"])
        self.assertEqual(parsed[0]["summary"], "</script><script>alert(1)")

    def test_html_comment_escaped_in_json(self) -> None:
        """A <!-- in issue data must be escaped inside a script block."""
        issues = [{"key": "X-1", "summary": "<!-- hidden -->"}]
        r = render_report.build_replacements(
            analyzed={"issues": issues, "clusters": [], "keyRecommendations": []},
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com",
        )
        self.assertNotIn("<!--", r["ISSUES_JSON"])
        self.assertIn("\\u003c!--", r["ISSUES_JSON"])
        # Verify the escaped JSON is still valid
        parsed = json.loads(r["ISSUES_JSON"])
        self.assertEqual(parsed[0]["summary"], "<!-- hidden -->")

    def test_null_release_risk(self) -> None:
        r = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input={"executiveSummary": [], "releaseRisk": None},
            jira_url="https://x.com",
        )
        self.assertEqual(r["RELEASE_RISK_JSON"], "null")

    def test_project_key_html_escaped(self) -> None:
        """PROJECT_KEY is embedded in HTML text nodes and must be escaped."""
        r = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com",
            project_key="<script>alert(1)</script>",
        )
        self.assertNotIn("<script>", r["PROJECT_KEY"])
        self.assertIn("&lt;script&gt;", r["PROJECT_KEY"])

    def test_jira_url_js_escaped(self) -> None:
        """JIRA_BASE_URL is embedded in a JS string literal and must be
        escaped for that context."""
        r = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url='https://x.com/";alert(1)//',
        )
        self.assertNotIn('"alert', r["JIRA_BASE_URL"])
        self.assertIn('\\"', r["JIRA_BASE_URL"])

    def test_jira_url_script_close_escaped(self) -> None:
        """A </script> in the URL must not break the script block."""
        r = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com/</script>",
        )
        self.assertNotIn("</script>", r["JIRA_BASE_URL"])

    def test_empty_executive_summary(self) -> None:
        r = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input={"executiveSummary": [], "releaseRisk": None},
            jira_url="https://x.com",
        )
        self.assertEqual(json.loads(r["EXECUTIVE_SUMMARY_JSON"]), [])


class TestRender(unittest.TestCase):
    def test_all_placeholders_replaced(self) -> None:
        replacements = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://issues.redhat.com",
        )
        html = render_report.render(MINIMAL_TEMPLATE, replacements)

        for name in render_report.ALL_PLACEHOLDERS:
            self.assertNotIn(
                "{" + name + "}",
                html,
                f"placeholder {{{name}}} was not replaced",
            )

    def test_values_appear_in_output(self) -> None:
        replacements = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://issues.redhat.com",
        )
        html = render_report.render(MINIMAL_TEMPLATE, replacements)

        self.assertIn("EDM", html)
        self.assertIn("issues.redhat.com", html)
        self.assertIn("EDM-101", html)
        self.assertIn("Bug one", html)

    def test_no_double_replacement(self) -> None:
        """A replacement value containing placeholder-like text must not
        be re-expanded."""
        template = "<p>{PROJECT_KEY}</p>"
        replacements = {"PROJECT_KEY": "VALUE_WITH_{ISSUES_JSON}_INSIDE"}
        # Only PROJECT_KEY is in the mapping; ISSUES_JSON should not
        # cause a KeyError or secondary replacement.
        html = render_report.render(template, replacements)
        self.assertIn("VALUE_WITH_{ISSUES_JSON}_INSIDE", html)

    def test_javascript_braces_untouched(self) -> None:
        """JavaScript empty-object literals ({}) must survive rendering."""
        template = "var x = {}; var y = {PROJECT_KEY};"
        replacements = render_report.build_replacements(
            analyzed=SAMPLE_ANALYZED,
            ai_input=SAMPLE_AI_INPUT,
            jira_url="https://x.com",
        )
        html = render_report.render(template, replacements)
        self.assertIn("var x = {};", html)

    def test_missing_key_leaves_placeholder(self) -> None:
        """A placeholder with no matching key is left intact, not KeyError."""
        template = "{PROJECT_KEY} and {ISSUES_JSON}"
        html = render_report.render(template, {"PROJECT_KEY": "EDM"})
        self.assertIn("EDM", html)
        self.assertIn("{ISSUES_JSON}", html)


class TestValidateNoUnreplaced(unittest.TestCase):
    def test_clean_output(self) -> None:
        self.assertEqual(render_report.validate_no_unreplaced("<p>hello</p>"), [])

    def test_detects_remaining_placeholder(self) -> None:
        result = render_report.validate_no_unreplaced("<p>{PROJECT_KEY}</p>")
        self.assertEqual(result, ["PROJECT_KEY"])

    def test_ignores_javascript_braces(self) -> None:
        self.assertEqual(render_report.validate_no_unreplaced("var x = {};"), [])

    def test_ignores_unknown_brace_patterns(self) -> None:
        self.assertEqual(
            render_report.validate_no_unreplaced("var counts = {};"),
            [],
        )

    def test_catches_leftover_placeholder(self) -> None:
        """Verify detection of a known placeholder still present in output."""
        html_with_leftover = "<p>Done</p>{PROJECT_KEY}"
        remaining = render_report.validate_no_unreplaced(html_with_leftover)
        self.assertEqual(remaining, ["PROJECT_KEY"])


# ---------------------------------------------------------------------------
# Integration tests — file I/O through main()
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    def _run(self, tmpdir: Path, **overrides: str) -> int:
        """Set up standard fixture files and run main().

        Only creates default fixture files when no override is provided
        for that input, preventing the default from clobbering a file
        the test wrote at the same path.
        """
        if "analyzed" not in overrides:
            _write_json(tmpdir, "analyzed.json", SAMPLE_ANALYZED)
        if "ai_input" not in overrides:
            _write_json(tmpdir, "ai-input.json", SAMPLE_AI_INPUT)
        if "template" not in overrides:
            _write_text(tmpdir, "template.html", MINIMAL_TEMPLATE)

        analyzed_path = overrides.get("analyzed", str(tmpdir / "analyzed.json"))
        ai_input_path = overrides.get("ai_input", str(tmpdir / "ai-input.json"))
        template_path = overrides.get("template", str(tmpdir / "template.html"))
        output_path = overrides.get("output", str(tmpdir / "output" / "report.html"))

        argv = [
            "--analyzed", analyzed_path,
            "--template", template_path,
            "--jira-url", overrides.get("jira_url", "https://issues.redhat.com"),
            "--ai-input", ai_input_path,
            "--output", output_path,
        ]
        if "project_key" in overrides:
            argv.extend(["--project-key", overrides["project_key"]])

        return render_report.main(argv)

    def test_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = self._run(Path(tmpdir))
            self.assertEqual(rc, 0)
            output = (Path(tmpdir) / "output" / "report.html").read_text()
            self.assertIn("EDM", output)
            self.assertIn("EDM-101", output)

    def test_creates_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            deep_output = Path(tmpdir) / "a" / "b" / "c" / "report.html"
            rc = self._run(Path(tmpdir), output=str(deep_output))
            self.assertEqual(rc, 0)
            self.assertTrue(deep_output.exists())

    def test_project_key_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = self._run(Path(tmpdir), project_key="CUSTOM")
            self.assertEqual(rc, 0)
            output = (Path(tmpdir) / "output" / "report.html").read_text()
            self.assertIn("CUSTOM", output)

    def test_missing_analyzed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SystemExit) as ctx:
                self._run(Path(tmpdir), analyzed="/nonexistent/analyzed.json")
            self.assertEqual(ctx.exception.code, 1)

    def test_missing_template_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SystemExit) as ctx:
                self._run(Path(tmpdir), template="/nonexistent/template.html")
            self.assertEqual(ctx.exception.code, 1)

    def test_missing_ai_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SystemExit) as ctx:
                self._run(Path(tmpdir), ai_input="/nonexistent/ai-input.json")
            self.assertEqual(ctx.exception.code, 1)

    def test_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = _write_text(Path(tmpdir), "bad.json", "not json at all")
            with self.assertRaises(SystemExit) as ctx:
                self._run(Path(tmpdir), analyzed=str(bad))
            self.assertEqual(ctx.exception.code, 1)

    def test_null_release_risk_renders_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ai_input = {"executiveSummary": [], "releaseRisk": None}
            ai_path = _write_json(Path(tmpdir), "ai-input.json", ai_input)
            rc = self._run(Path(tmpdir), ai_input=str(ai_path))
            self.assertEqual(rc, 0)
            output = (Path(tmpdir) / "output" / "report.html").read_text()
            self.assertIn("var R=null;", output)

    def test_renders_real_template(self) -> None:
        """Render against the actual report.html template to catch
        regressions in placeholder naming or template structure."""
        real_template = Path(__file__).resolve().parent.parent / "templates" / "report.html"
        if not real_template.exists():
            self.skipTest("real template not found at expected path")

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzed_path = _write_json(Path(tmpdir), "analyzed.json", SAMPLE_ANALYZED)
            ai_path = _write_json(Path(tmpdir), "ai-input.json", SAMPLE_AI_INPUT)
            output_path = Path(tmpdir) / "report.html"

            rc = render_report.main([
                "--analyzed", str(analyzed_path),
                "--template", str(real_template),
                "--jira-url", "https://issues.redhat.com",
                "--ai-input", str(ai_path),
                "--output", str(output_path),
            ])
            self.assertEqual(rc, 0)
            html = output_path.read_text()
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("EDM-101", html)
            self.assertNotIn("{PROJECT_KEY}", html)
            self.assertNotIn("{JIRA_BASE_URL}", html)


if __name__ == "__main__":
    unittest.main()
