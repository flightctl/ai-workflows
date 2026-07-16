#!/usr/bin/env python3
"""Tests for triage/scripts/scan.py."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SCRIPT = Path(__file__).resolve().parent / "scan.py"
_spec = importlib.util.spec_from_file_location("scan", _SCRIPT)
assert _spec and _spec.loader
scan = importlib.util.module_from_spec(_spec)
sys.modules["scan"] = scan
_spec.loader.exec_module(scan)


# ---------------------------------------------------------------------------
# Jira API response fixtures
# ---------------------------------------------------------------------------

def _raw_issue(
    key: str,
    *,
    summary: str = "Bug summary",
    status: str = "Open",
    priority: str = "High",
    assignee: str | None = "Alice",
    reporter: str = "Bob",
    created: str = "2026-01-15T10:00:00.000+0000",
    updated: str = "2026-01-16T10:00:00.000+0000",
    labels: list[str] | None = None,
    components: list[str] | None = None,
    description: str | dict | None = "Description text",
    resolution: str | None = None,
    resolutiondate: str | None = None,
) -> dict:
    """Build a raw Jira API issue object."""
    fields: dict = {
        "summary": summary,
        "status": {"name": status},
        "priority": {"name": priority},
        "assignee": {"displayName": assignee} if assignee else None,
        "reporter": {"displayName": reporter},
        "created": created,
        "updated": updated,
        "labels": labels or [],
        "components": [{"name": c} for c in (components or [])],
        "description": description,
    }
    if resolution is not None:
        fields["resolution"] = {"name": resolution}
    if resolutiondate is not None:
        fields["resolutiondate"] = resolutiondate
    return {"key": key, "fields": fields}


def _search_response(issues: list[dict]) -> dict:
    """Wrap issues in a Jira search response envelope."""
    return {"issues": issues, "total": len(issues)}


# ---------------------------------------------------------------------------
# extract_text — pure function tests
# ---------------------------------------------------------------------------

class TestExtractText(unittest.TestCase):

    def test_none_returns_empty(self) -> None:
        self.assertEqual(scan.extract_text(None), "")

    def test_plain_string_passthrough(self) -> None:
        self.assertEqual(scan.extract_text("hello world"), "hello world")

    def test_empty_string(self) -> None:
        self.assertEqual(scan.extract_text(""), "")

    def test_adf_text_node(self) -> None:
        node = {"type": "text", "text": "inline text"}
        self.assertEqual(scan.extract_text(node), "inline text")

    def test_adf_text_node_missing_text_key(self) -> None:
        node = {"type": "text"}
        self.assertEqual(scan.extract_text(node), "")

    def test_adf_paragraph(self) -> None:
        doc = {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "first "},
                {"type": "text", "text": "second"},
            ],
        }
        self.assertEqual(scan.extract_text(doc), "first second")

    def test_adf_document_with_paragraphs(self) -> None:
        doc = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Line one"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Line two"}],
                },
            ],
        }
        self.assertEqual(scan.extract_text(doc), "Line one\nLine two")

    def test_adf_heading(self) -> None:
        doc = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [{"type": "text", "text": "Title"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Body"}],
                },
            ],
        }
        self.assertEqual(scan.extract_text(doc), "Title\nBody")

    def test_adf_bullet_list(self) -> None:
        doc = {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "item one"}],
                        },
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "item two"}],
                        },
                    ],
                },
            ],
        }
        self.assertEqual(scan.extract_text(doc), "item one\nitem two")

    def test_adf_inline_marks_ignored(self) -> None:
        node = {
            "type": "text",
            "text": "bold text",
            "marks": [{"type": "strong"}],
        }
        self.assertEqual(scan.extract_text(node), "bold text")

    def test_adf_empty_content(self) -> None:
        doc = {"type": "doc", "content": []}
        self.assertEqual(scan.extract_text(doc), "")

    def test_adf_unknown_inline_type(self) -> None:
        node = {
            "type": "emoji",
            "attrs": {"shortName": ":smile:"},
        }
        self.assertEqual(scan.extract_text(node), "")

    def test_list_of_values(self) -> None:
        values = ["first", "second", "third"]
        self.assertEqual(scan.extract_text(values), "first\nsecond\nthird")

    def test_numeric_value(self) -> None:
        self.assertEqual(scan.extract_text(42), "")

    def test_adf_expand(self) -> None:
        doc = {
            "type": "expand",
            "attrs": {"title": "Details"},
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hidden content"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "More hidden"}],
                },
            ],
        }
        self.assertEqual(scan.extract_text(doc), "Hidden content\nMore hidden")

    def test_adf_nested_expand(self) -> None:
        doc = {
            "type": "nestedExpand",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Nested"}],
                },
            ],
        }
        self.assertEqual(scan.extract_text(doc), "Nested")

    def test_adf_layout_section(self) -> None:
        doc = {
            "type": "layoutSection",
            "content": [
                {
                    "type": "layoutColumn",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Col 1"}],
                        },
                    ],
                },
                {
                    "type": "layoutColumn",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Col 2"}],
                        },
                    ],
                },
            ],
        }
        self.assertEqual(scan.extract_text(doc), "Col 1\nCol 2")

    def test_nested_codeblock(self) -> None:
        doc = {
            "type": "codeBlock",
            "attrs": {"language": "python"},
            "content": [{"type": "text", "text": "print('hi')"}],
        }
        self.assertEqual(scan.extract_text(doc), "print('hi')")


# ---------------------------------------------------------------------------
# _name_or_default — pure function tests
# ---------------------------------------------------------------------------

class TestNameOrDefault(unittest.TestCase):

    def test_dict_with_key(self) -> None:
        self.assertEqual(scan._name_or_default({"name": "High"}), "High")

    def test_dict_missing_key(self) -> None:
        self.assertEqual(scan._name_or_default({"id": "1"}), "")

    def test_dict_custom_key(self) -> None:
        self.assertEqual(
            scan._name_or_default({"displayName": "Alice"}, "displayName"),
            "Alice",
        )

    def test_dict_custom_default(self) -> None:
        self.assertEqual(
            scan._name_or_default({}, "displayName", "Unassigned"),
            "Unassigned",
        )

    def test_none_returns_default(self) -> None:
        self.assertEqual(scan._name_or_default(None), "")

    def test_none_returns_custom_default(self) -> None:
        self.assertEqual(
            scan._name_or_default(None, "displayName", "Unassigned"),
            "Unassigned",
        )

    def test_string_returns_default(self) -> None:
        self.assertEqual(scan._name_or_default("not a dict"), "")

    def test_list_returns_default(self) -> None:
        self.assertEqual(scan._name_or_default([1, 2]), "")


# ---------------------------------------------------------------------------
# normalize_issue — pure function tests
# ---------------------------------------------------------------------------

class TestNormalizeIssue(unittest.TestCase):

    def test_full_unresolved_issue(self) -> None:
        raw = _raw_issue(
            "EDM-101",
            summary="Login fails",
            status="Open",
            priority="Critical",
            assignee="Alice",
            reporter="Bob",
            labels=["regression", "auth"],
            components=["Backend", "API"],
            description="Login page returns 500",
        )
        result = scan.normalize_issue(raw)
        self.assertEqual(result["key"], "EDM-101")
        self.assertEqual(result["summary"], "Login fails")
        self.assertEqual(result["status"], "Open")
        self.assertEqual(result["priority"], "Critical")
        self.assertEqual(result["assignee"], "Alice")
        self.assertEqual(result["reporter"], "Bob")
        self.assertEqual(result["labels"], ["regression", "auth"])
        self.assertEqual(result["components"], ["Backend", "API"])
        self.assertEqual(result["description"], "Login page returns 500")
        self.assertNotIn("resolution", result)
        self.assertNotIn("resolved", result)

    def test_unassigned(self) -> None:
        raw = _raw_issue("EDM-102", assignee=None)
        result = scan.normalize_issue(raw)
        self.assertEqual(result["assignee"], "Unassigned")

    def test_resolved_issue_with_resolution_fields(self) -> None:
        raw = _raw_issue(
            "EDM-103",
            resolution="Fixed",
            resolutiondate="2026-01-20T14:00:00.000+0000",
        )
        result = scan.normalize_issue(raw, include_resolution=True)
        self.assertEqual(result["resolution"], "Fixed")
        self.assertEqual(result["resolved"], "2026-01-20T14:00:00.000+0000")

    def test_resolved_issue_without_resolution_date(self) -> None:
        raw = _raw_issue("EDM-104", resolution="Won't Fix")
        result = scan.normalize_issue(raw, include_resolution=True)
        self.assertEqual(result["resolution"], "Won't Fix")
        self.assertEqual(result["resolved"], "")

    def test_missing_fields_produce_safe_defaults(self) -> None:
        raw = {"key": "EDM-105", "fields": {}}
        result = scan.normalize_issue(raw)
        self.assertEqual(result["key"], "EDM-105")
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["status"], "")
        self.assertEqual(result["priority"], "")
        self.assertEqual(result["assignee"], "Unassigned")
        self.assertEqual(result["reporter"], "")
        self.assertEqual(result["labels"], [])
        self.assertEqual(result["components"], [])
        self.assertEqual(result["description"], "")

    def test_completely_empty_raw(self) -> None:
        result = scan.normalize_issue({})
        self.assertEqual(result["key"], "")

    def test_adf_description_extracted(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "ADF content"}],
                },
            ],
        }
        raw = _raw_issue("EDM-106", description=adf)
        result = scan.normalize_issue(raw)
        self.assertEqual(result["description"], "ADF content")

    def test_components_with_non_dict_entries_filtered(self) -> None:
        raw = {"key": "EDM-107", "fields": {
            "components": [{"name": "UI"}, "stray string", {"name": "API"}],
        }}
        result = scan.normalize_issue(raw)
        self.assertEqual(result["components"], ["UI", "API"])


# ---------------------------------------------------------------------------
# build_summary — pure function tests
# ---------------------------------------------------------------------------

class TestBuildSummary(unittest.TestCase):

    def test_grouped_counts(self) -> None:
        issues = [
            {"priority": "High", "status": "Open"},
            {"priority": "High", "status": "Open"},
            {"priority": "Low", "status": "In Progress"},
        ]
        summary = scan.build_summary(issues)
        self.assertIn("High: 2", summary)
        self.assertIn("Low: 1", summary)
        self.assertIn("Open: 2", summary)
        self.assertIn("In Progress: 1", summary)

    def test_empty_list(self) -> None:
        self.assertEqual(scan.build_summary([]), "")

    def test_missing_fields_counted_as_unknown(self) -> None:
        issues = [{"priority": "", "status": None}]
        summary = scan.build_summary(issues)
        self.assertIn("Unknown: 1", summary)

    def test_none_priority_counted_as_unknown(self) -> None:
        issues = [{"priority": None, "status": "Open"}]
        summary = scan.build_summary(issues)
        self.assertIn("Unknown: 1", summary)


# ---------------------------------------------------------------------------
# build_output — pure function tests
# ---------------------------------------------------------------------------

class TestBuildOutput(unittest.TestCase):

    def test_basic_structure(self) -> None:
        issues = [{"key": "EDM-1"}, {"key": "EDM-2"}]
        result = scan.build_output(
            "EDM", "https://jira.example.com", issues,
            "2026-03-19T12:00:00Z",
        )
        self.assertEqual(result["project"], "EDM")
        self.assertEqual(result["jiraBaseUrl"], "https://jira.example.com")
        self.assertEqual(result["scannedAt"], "2026-03-19T12:00:00Z")
        self.assertEqual(result["totalCount"], 2)
        self.assertEqual(result["issues"], issues)
        self.assertNotIn("windowDays", result)

    def test_trailing_slash_stripped(self) -> None:
        result = scan.build_output(
            "X", "https://jira.example.com/", [],
            "2026-01-01T00:00:00Z",
        )
        self.assertEqual(result["jiraBaseUrl"], "https://jira.example.com")

    def test_with_window_days(self) -> None:
        result = scan.build_output(
            "X", "https://jira.example.com", [],
            "2026-01-01T00:00:00Z", window_days=90,
        )
        self.assertEqual(result["windowDays"], 90)

    def test_empty_issues(self) -> None:
        result = scan.build_output(
            "X", "https://jira.example.com", [],
            "2026-01-01T00:00:00Z",
        )
        self.assertEqual(result["totalCount"], 0)
        self.assertEqual(result["issues"], [])


# ---------------------------------------------------------------------------
# write_json_file — I/O tests
# ---------------------------------------------------------------------------

class TestWriteJsonFile(unittest.TestCase):

    def test_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            data = {"key": "value", "list": [1, 2, 3]}
            scan.write_json_file(path, data)

            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.endswith("\n"))
            loaded = json.loads(content)
            self.assertEqual(loaded, data)

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "output.json"
            scan.write_json_file(path, {"ok": True})
            self.assertTrue(path.is_file())

    def test_pretty_printed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            scan.write_json_file(path, {"a": 1})
            content = path.read_text(encoding="utf-8")
            self.assertIn("\n", content.rstrip("\n"))


# ---------------------------------------------------------------------------
# fetch_all_issues — pagination tests with fake search function
# ---------------------------------------------------------------------------

def _fake_search(pages: list[list[dict]]):
    """Return a search function that yields pages in order.

    The returned callable also records each JQL it received, enabling
    assertions on the cursor progression.
    """
    call_log: list[str] = []
    page_iter = iter(pages)

    def search(jql: str, fields: str, max_results: int = scan.PAGE_SIZE) -> dict:
        call_log.append(jql)
        page = next(page_iter, [])
        return _search_response(page)

    search.call_log = call_log  # type: ignore[attr-defined]
    return search


class TestFetchAllIssues(unittest.TestCase):

    def test_single_partial_page(self) -> None:
        issues = [_raw_issue(f"EDM-{i}") for i in range(1, 4)]
        search = _fake_search([issues])
        result = scan.fetch_all_issues(search, "project = EDM", "summary")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["key"], "EDM-1")

    def test_multiple_full_pages(self) -> None:
        page1 = [_raw_issue(f"EDM-{i}") for i in range(1, scan.PAGE_SIZE + 1)]
        page2 = [_raw_issue(f"EDM-{scan.PAGE_SIZE + i}") for i in range(1, 4)]
        search = _fake_search([page1, page2])
        result = scan.fetch_all_issues(search, "project = EDM", "summary")
        self.assertEqual(len(result), scan.PAGE_SIZE + 3)

    def test_cursor_appears_in_jql(self) -> None:
        page1 = [_raw_issue(f"EDM-{i}") for i in range(1, scan.PAGE_SIZE + 1)]
        page2 = [_raw_issue(f"EDM-{scan.PAGE_SIZE + 1}")]
        search = _fake_search([page1, page2])
        scan.fetch_all_issues(search, "project = EDM", "summary")

        self.assertEqual(len(search.call_log), 2)
        self.assertNotIn("key >", search.call_log[0])
        self.assertIn(f"key > 'EDM-{scan.PAGE_SIZE}'", search.call_log[1])

    def test_order_by_appended(self) -> None:
        search = _fake_search([[_raw_issue("EDM-1")]])
        scan.fetch_all_issues(search, "project = EDM", "summary")
        self.assertTrue(search.call_log[0].endswith("ORDER BY key ASC"))

    def test_empty_result(self) -> None:
        search = _fake_search([[]])
        result = scan.fetch_all_issues(search, "project = EDM", "summary")
        self.assertEqual(result, [])

    def test_exact_page_boundary(self) -> None:
        page = [_raw_issue(f"EDM-{i}") for i in range(1, scan.PAGE_SIZE + 1)]
        search = _fake_search([page, []])
        result = scan.fetch_all_issues(search, "project = EDM", "summary")
        self.assertEqual(len(result), scan.PAGE_SIZE)
        self.assertEqual(len(search.call_log), 2)

    def test_deduplication(self) -> None:
        issues = [
            _raw_issue("EDM-1"),
            _raw_issue("EDM-2"),
            _raw_issue("EDM-1"),
        ]
        search = _fake_search([issues])
        result = scan.fetch_all_issues(search, "project = EDM", "summary")
        keys = [r["key"] for r in result]
        self.assertEqual(keys, ["EDM-1", "EDM-2"])

    def test_non_advancing_cursor_raises(self) -> None:
        stuck_page = [_raw_issue(f"EDM-{i}") for i in range(1, scan.PAGE_SIZE + 1)]

        def stuck_search(jql: str, fields: str, max_results: int = scan.PAGE_SIZE) -> dict:
            return _search_response(stuck_page)

        with self.assertRaises(scan.ScanError) as ctx:
            scan.fetch_all_issues(stuck_search, "project = EDM", "summary")
        self.assertIn("did not advance", str(ctx.exception))


# ---------------------------------------------------------------------------
# main — integration tests
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    _ENV = {
        "JIRA_URL": "https://jira.example.com",
        "JIRA_TOKEN": "test-token",
    }

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._output_dir = Path(self._tmpdir) / "output"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _run_main(
        self,
        search_responses: list[list[dict]],
        *,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> int:
        """Run main() with a mocked jira_search. Output goes to self._output_dir."""
        page_iter = iter(search_responses)

        def fake_jira_search(
            base_url: str,
            auth_header: str,
            jql: str,
            fields: str,
            max_results: int = scan.PAGE_SIZE,
        ) -> dict:
            page = next(page_iter, [])
            return _search_response(page)

        argv = ["EDM", "--output-dir", str(self._output_dir)]
        if extra_args:
            argv.extend(extra_args)

        effective_env = self._ENV if env is None else env
        with (
            patch.dict(os.environ, effective_env, clear=True),
            patch.object(scan, "jira_search", fake_jira_search),
        ):
            return scan.main(argv)

    def test_successful_scan(self) -> None:
        unresolved = [_raw_issue("EDM-1"), _raw_issue("EDM-2")]
        resolved = [
            _raw_issue(
                "EDM-3",
                resolution="Fixed",
                resolutiondate="2026-01-20T14:00:00.000+0000",
            ),
        ]
        code = self._run_main([unresolved, resolved])

        self.assertEqual(code, 0)
        self.assertTrue((self._output_dir / "issues.json").is_file())
        self.assertTrue((self._output_dir / "resolved.json").is_file())

        issues_data = json.loads(
            (self._output_dir / "issues.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(issues_data["project"], "EDM")
        self.assertEqual(issues_data["totalCount"], 2)
        self.assertEqual(len(issues_data["issues"]), 2)
        self.assertEqual(
            issues_data["jiraBaseUrl"], "https://jira.example.com",
        )
        self.assertIn("scannedAt", issues_data)

        resolved_data = json.loads(
            (self._output_dir / "resolved.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(resolved_data["totalCount"], 1)
        self.assertEqual(resolved_data["windowDays"], 90)
        self.assertEqual(resolved_data["issues"][0]["resolution"], "Fixed")

    def test_empty_project(self) -> None:
        code = self._run_main([[], []])

        self.assertEqual(code, 0)
        issues_data = json.loads(
            (self._output_dir / "issues.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(issues_data["totalCount"], 0)
        self.assertEqual(issues_data["issues"], [])

    def test_custom_window_days(self) -> None:
        code = self._run_main(
            [[], []],
            extra_args=["--window-days", "30"],
        )
        self.assertEqual(code, 0)
        resolved_data = json.loads(
            (self._output_dir / "resolved.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(resolved_data["windowDays"], 30)

    def test_missing_jira_url(self) -> None:
        code = self._run_main(
            [],
            env={"JIRA_TOKEN": "tok"},
        )
        self.assertEqual(code, 1)

    def test_missing_jira_token(self) -> None:
        code = self._run_main(
            [],
            env={"JIRA_URL": "https://jira.example.com"},
        )
        self.assertEqual(code, 1)

    def test_jira_api_error_returns_1(self) -> None:
        def failing_search(
            base_url: str,
            auth_header: str,
            jql: str,
            fields: str,
            max_results: int = scan.PAGE_SIZE,
        ) -> dict:
            raise scan.JiraAPIError(403, "Forbidden")

        argv = ["EDM", "--output-dir", str(self._output_dir)]
        with (
            patch.dict(os.environ, self._ENV, clear=False),
            patch.object(scan, "jira_search", failing_search),
        ):
            code = scan.main(argv)
        self.assertEqual(code, 1)

    def test_normalized_fields_in_output(self) -> None:
        raw = [_raw_issue(
            "EDM-1",
            summary="Test bug",
            status="Open",
            priority="High",
            assignee="Alice",
            reporter="Bob",
            labels=["regression"],
            components=["Backend"],
        )]
        code = self._run_main([raw, []])
        self.assertEqual(code, 0)

        issues_data = json.loads(
            (self._output_dir / "issues.json").read_text(encoding="utf-8"),
        )
        issue = issues_data["issues"][0]
        self.assertEqual(issue["key"], "EDM-1")
        self.assertEqual(issue["summary"], "Test bug")
        self.assertEqual(issue["status"], "Open")
        self.assertEqual(issue["priority"], "High")
        self.assertEqual(issue["assignee"], "Alice")
        self.assertEqual(issue["reporter"], "Bob")
        self.assertEqual(issue["labels"], ["regression"])
        self.assertEqual(issue["components"], ["Backend"])

    def test_multi_page_scan(self) -> None:
        page1 = [_raw_issue(f"EDM-{i}") for i in range(1, scan.PAGE_SIZE + 1)]
        page2 = [_raw_issue(f"EDM-{scan.PAGE_SIZE + 1}")]
        code = self._run_main([page1, page2, []])

        self.assertEqual(code, 0)
        issues_data = json.loads(
            (self._output_dir / "issues.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(issues_data["totalCount"], scan.PAGE_SIZE + 1)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TestExceptions(unittest.TestCase):

    def test_jira_api_error_attributes(self) -> None:
        exc = scan.JiraAPIError(404, "Not found")
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(exc.body, "Not found")
        self.assertIn("404", str(exc))

    def test_jira_api_error_truncates_long_body(self) -> None:
        exc = scan.JiraAPIError(500, "x" * 1000)
        self.assertTrue(len(str(exc)) < 600)

    def test_scan_error_is_base(self) -> None:
        self.assertTrue(issubclass(scan.JiraAPIError, scan.ScanError))


# ---------------------------------------------------------------------------
# validate_project_key — pure function tests
# ---------------------------------------------------------------------------

class TestValidateProjectKey(unittest.TestCase):

    def test_valid_keys(self) -> None:
        for key in ("EDM", "FLIGHTCTL", "MY_PROJ", "A1"):
            scan.validate_project_key(key)

    def test_lowercase_rejected(self) -> None:
        with self.assertRaises(scan.ScanError):
            scan.validate_project_key("edm")

    def test_empty_rejected(self) -> None:
        with self.assertRaises(scan.ScanError):
            scan.validate_project_key("")

    def test_injection_rejected(self) -> None:
        with self.assertRaises(scan.ScanError):
            scan.validate_project_key("EDM' OR 1=1 --")

    def test_path_traversal_rejected(self) -> None:
        with self.assertRaises(scan.ScanError):
            scan.validate_project_key("../../etc")


# ---------------------------------------------------------------------------
# validate_jira_url — pure function tests
# ---------------------------------------------------------------------------

class TestValidateJiraUrl(unittest.TestCase):

    def test_valid_https_url(self) -> None:
        scan.validate_jira_url("https://redhat.atlassian.net")

    def test_http_rejected(self) -> None:
        with self.assertRaises(scan.ScanError) as ctx:
            scan.validate_jira_url("http://jira.example.com")
        self.assertIn("https", str(ctx.exception))

    def test_no_scheme_rejected(self) -> None:
        with self.assertRaises(scan.ScanError):
            scan.validate_jira_url("jira.example.com")

    def test_file_scheme_rejected(self) -> None:
        with self.assertRaises(scan.ScanError):
            scan.validate_jira_url("file:///etc/passwd")


# ---------------------------------------------------------------------------
# _retry_delay — pure function tests
# ---------------------------------------------------------------------------

class _FakeHeaders:
    """Minimal headers object for testing _retry_delay."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self._mapping = mapping or {}

    def get(self, key: str, default: object = None) -> object:
        return self._mapping.get(key, default)


class TestRetryDelay(unittest.TestCase):

    def test_valid_retry_after_header(self) -> None:
        headers = _FakeHeaders({"Retry-After": "5"})
        self.assertEqual(scan._retry_delay(headers, 0), 5)

    def test_retry_after_zero_clamps_to_one(self) -> None:
        headers = _FakeHeaders({"Retry-After": "0"})
        self.assertEqual(scan._retry_delay(headers, 0), 1)

    def test_retry_after_negative_clamps_to_one(self) -> None:
        headers = _FakeHeaders({"Retry-After": "-3"})
        self.assertEqual(scan._retry_delay(headers, 0), 1)

    def test_no_retry_after_falls_back_to_backoff(self) -> None:
        headers = _FakeHeaders()
        self.assertEqual(scan._retry_delay(headers, 2), scan.RETRY_BACKOFF_BASE ** 2)

    def test_non_integer_retry_after_falls_back_to_backoff(self) -> None:
        headers = _FakeHeaders({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
        self.assertEqual(scan._retry_delay(headers, 1), scan.RETRY_BACKOFF_BASE ** 1)


# ---------------------------------------------------------------------------
# build_auth_header
# ---------------------------------------------------------------------------

class TestBuildAuthHeader(unittest.TestCase):

    def test_bearer_without_email(self) -> None:
        header = scan.build_auth_header("my-pat-token")
        self.assertEqual(header, "Bearer my-pat-token")

    def test_bearer_with_none_email(self) -> None:
        header = scan.build_auth_header("my-pat-token", None)
        self.assertEqual(header, "Bearer my-pat-token")

    def test_basic_with_email(self) -> None:
        header = scan.build_auth_header("my-api-token", "user@example.com")
        self.assertTrue(header.startswith("Basic "))
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        self.assertEqual(decoded, "user@example.com:my-api-token")


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs(unittest.TestCase):

    def test_minimal_args(self) -> None:
        args = scan.parse_args(["EDM"])
        self.assertEqual(args.project, "EDM")
        self.assertEqual(args.window_days, 90)
        self.assertIsNone(args.output_dir)

    def test_all_args(self) -> None:
        args = scan.parse_args([
            "PROJ", "--window-days", "30", "--output-dir", "/tmp/out",
        ])
        self.assertEqual(args.project, "PROJ")
        self.assertEqual(args.window_days, 30)
        self.assertEqual(args.output_dir, Path("/tmp/out"))

    def test_missing_project_exits(self) -> None:
        with self.assertRaises(SystemExit):
            scan.parse_args([])


if __name__ == "__main__":
    unittest.main()
