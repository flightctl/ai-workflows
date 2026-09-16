#!/usr/bin/env python3
"""Tests for _shared/scripts/fetch-issue.py."""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent / "fetch-issue.py"
_spec = importlib.util.spec_from_file_location("fetch_issue", _SCRIPT)
assert _spec and _spec.loader
fetch_issue = importlib.util.module_from_spec(_spec)
sys.modules["fetch_issue"] = fetch_issue
_spec.loader.exec_module(fetch_issue)


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Verify argparse configuration for each subcommand."""

    def test_get_basic(self) -> None:
        """Get subcommand parses the issue key."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args(["get", "EDM-123"])
        self.assertEqual(args.subcommand, "get")
        self.assertEqual(args.key, "EDM-123")
        self.assertEqual(args.fields, fetch_issue.DEFAULT_FIELDS)
        self.assertFalse(args.comments)
        self.assertEqual(args.comment_limit, 0)
        self.assertFalse(args.links)
        self.assertEqual(args.link_fields, fetch_issue.DEFAULT_LINK_FIELDS)
        self.assertFalse(args.parent)
        self.assertEqual(args.parent_fields, fetch_issue.DEFAULT_PARENT_FIELDS)

    def test_get_all_options(self) -> None:
        """Get subcommand parses all optional arguments."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args([
            "get", "PROJ-456",
            "--fields", "summary,status",
            "--comments",
            "--comment-limit", "5",
            "--links",
            "--link-fields", "summary,priority",
            "--parent",
            "--parent-fields", "summary,issuetype",
        ])
        self.assertEqual(args.key, "PROJ-456")
        self.assertEqual(args.fields, "summary,status")
        self.assertTrue(args.comments)
        self.assertEqual(args.comment_limit, 5)
        self.assertTrue(args.links)
        self.assertEqual(args.link_fields, "summary,priority")
        self.assertTrue(args.parent)
        self.assertEqual(args.parent_fields, "summary,issuetype")

    def test_get_missing_key(self) -> None:
        """Get exits with code 2 when the issue key is missing."""
        parser = fetch_issue.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["get"])
        self.assertEqual(ctx.exception.code, 2)

    def test_search_basic(self) -> None:
        """Search subcommand parses the JQL query."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args(["search", "project = EDM"])
        self.assertEqual(args.subcommand, "search")
        self.assertEqual(args.jql, "project = EDM")
        self.assertEqual(args.fields, fetch_issue.DEFAULT_FIELDS)
        self.assertEqual(args.max_results, 200)

    def test_search_all_options(self) -> None:
        """Search subcommand parses all optional arguments."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args([
            "search", "status = Open",
            "--fields", "summary,priority",
            "--max-results", "10",
        ])
        self.assertEqual(args.jql, "status = Open")
        self.assertEqual(args.fields, "summary,priority")
        self.assertEqual(args.max_results, 10)

    def test_search_missing_jql(self) -> None:
        """Search exits with code 2 when the JQL query is missing."""
        parser = fetch_issue.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["search"])
        self.assertEqual(ctx.exception.code, 2)

    def test_no_subcommand(self) -> None:
        """No subcommand returns EXIT_ERROR."""
        result = fetch_issue.main([])
        self.assertEqual(result, fetch_issue.EXIT_ERROR)


# ---------------------------------------------------------------------------
# Exit code contract tests
# ---------------------------------------------------------------------------


class TestExitCodes(unittest.TestCase):
    """Verify the documented exit code contract."""

    def test_exit_code_constants(self) -> None:
        """Exit code constants match the documented contract."""
        self.assertEqual(fetch_issue.EXIT_SUCCESS, 0)
        self.assertEqual(fetch_issue.EXIT_ERROR, 1)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    """Verify helper functions."""

    def test_info_writes_to_stderr(self) -> None:
        """info() writes an INFO-prefixed message to stderr."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            fetch_issue.info("test message")
        self.assertIn("INFO: test message", buf.getvalue())

    def test_fail_exits_with_code(self) -> None:
        """fail() exits with the specified code."""
        with self.assertRaises(SystemExit) as ctx:
            fetch_issue.fail("something broke", code=1)
        self.assertEqual(ctx.exception.code, 1)

    def test_fail_writes_to_stderr(self) -> None:
        """fail() writes an ERROR-prefixed message to stderr."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf), self.assertRaises(SystemExit):
            fetch_issue.fail("bad thing")
        self.assertIn("ERROR: bad thing", buf.getvalue())

    def test_fail_default_code(self) -> None:
        """fail() defaults to EXIT_ERROR."""
        with self.assertRaises(SystemExit) as ctx:
            fetch_issue.fail("error")
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)


# ---------------------------------------------------------------------------
# Environment variable tests
# ---------------------------------------------------------------------------


class TestEnvVars(unittest.TestCase):
    """Verify environment variable handling."""

    def test_missing_jira_url(self) -> None:
        """Missing JIRA_URL exits with code 1."""
        env = {"JIRA_TOKEN": "tok123"}
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                fetch_issue.main(["get", "EDM-1"])
            self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_missing_jira_token(self) -> None:
        """Missing JIRA_TOKEN exits with code 1."""
        env = {"JIRA_URL": "https://jira.example.com"}
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                fetch_issue.main(["get", "EDM-1"])
            self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_missing_env_error_message(self) -> None:
        """Missing env var prints the variable name in the error."""
        env: dict[str, str] = {}
        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit),
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertIn("JIRA_URL", buf.getvalue())


# ---------------------------------------------------------------------------
# Auth header tests
# ---------------------------------------------------------------------------


class TestAuthHeader(unittest.TestCase):
    """Verify auth header construction."""

    def test_bearer_auth(self) -> None:
        """Bearer auth is used when only JIRA_TOKEN is set."""
        env = {"JIRA_URL": "https://jira.example.com", "JIRA_TOKEN": "my-pat"}
        with mock.patch.dict("os.environ", env, clear=True):
            header = fetch_issue._build_auth_header()
        self.assertEqual(header, "Bearer my-pat")

    def test_basic_auth(self) -> None:
        """Basic auth is used when JIRA_EMAIL is also set."""
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "api-token",
            "JIRA_EMAIL": "user@example.com",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            header = fetch_issue._build_auth_header()
        expected = base64.b64encode(b"user@example.com:api-token").decode("ascii")
        self.assertEqual(header, f"Basic {expected}")

    def test_basic_auth_empty_email_uses_bearer(self) -> None:
        """Empty JIRA_EMAIL falls back to Bearer auth."""
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "my-pat",
            "JIRA_EMAIL": "",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            header = fetch_issue._build_auth_header()
        self.assertEqual(header, "Bearer my-pat")


# ---------------------------------------------------------------------------
# get subcommand tests
# ---------------------------------------------------------------------------


def _mock_urlopen(response_data: dict[str, Any]) -> mock.MagicMock:
    """Create a mock for urllib.request.urlopen that returns JSON."""
    mock_response = mock.MagicMock()
    mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_response.__enter__ = mock.Mock(return_value=mock_response)
    mock_response.__exit__ = mock.Mock(return_value=False)
    return mock_response


# Import Any for type hints in helper
from typing import Any


class TestGetSubcommand(unittest.TestCase):
    """Verify get subcommand behavior."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_get_basic_issue(self) -> None:
        """Fetches an issue and returns key + fields as JSON."""
        api_response = {
            "key": "EDM-123",
            "fields": {
                "summary": "Fix the widget",
                "status": {"name": "Open"},
                "priority": {"name": "High"},
                "description": "Detailed description",
                "issuetype": {"name": "Bug"},
                "labels": ["backend"],
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main(["get", "EDM-123"])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["key"], "EDM-123")
        self.assertEqual(output["fields"]["summary"], "Fix the widget")
        self.assertNotIn("comments", output)
        self.assertNotIn("links", output)
        self.assertNotIn("parent", output)

    def test_get_custom_fields(self) -> None:
        """Custom --fields limits which fields appear in output."""
        api_response = {
            "key": "EDM-10",
            "fields": {
                "summary": "Summary text",
                "status": {"name": "Closed"},
                "priority": {"name": "Low"},
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-10", "--fields", "summary,status",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertIn("summary", output["fields"])
        self.assertIn("status", output["fields"])
        # priority was not requested
        self.assertNotIn("priority", output["fields"])

    def test_get_with_comments(self) -> None:
        """--comments includes comments in the output."""
        api_response = {
            "key": "EDM-5",
            "fields": {
                "summary": "Test",
                "comment": {
                    "comments": [
                        {
                            "id": "1001",
                            "author": {"displayName": "Alice"},
                            "body": "First comment",
                            "created": "2025-01-15T10:00:00.000+0000",
                        },
                        {
                            "id": "1002",
                            "author": {"displayName": "Bob"},
                            "body": "Second comment",
                            "created": "2025-01-16T11:00:00.000+0000",
                        },
                    ],
                },
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-5", "--fields", "summary", "--comments",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output["comments"]), 2)
        self.assertEqual(output["comments"][0]["author"], "Alice")
        self.assertEqual(output["comments"][0]["body"], "First comment")
        self.assertEqual(output["comments"][1]["id"], "1002")

    def test_get_comment_limit(self) -> None:
        """--comment-limit caps the number of comments returned."""
        api_response = {
            "key": "EDM-5",
            "fields": {
                "summary": "Test",
                "comment": {
                    "comments": [
                        {"id": "1", "author": {"displayName": "A"},
                         "body": "c1", "created": "2025-01-01"},
                        {"id": "2", "author": {"displayName": "B"},
                         "body": "c2", "created": "2025-01-02"},
                        {"id": "3", "author": {"displayName": "C"},
                         "body": "c3", "created": "2025-01-03"},
                    ],
                },
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-5", "--fields", "summary",
                    "--comments", "--comment-limit", "2",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output["comments"]), 2)

    def test_get_with_links(self) -> None:
        """--links includes linked issues in the output."""
        api_response = {
            "key": "EDM-10",
            "fields": {
                "summary": "Main issue",
                "issuelinks": [
                    {
                        "type": {"name": "Blocks"},
                        "outwardIssue": {
                            "key": "EDM-20",
                            "fields": {
                                "summary": "Blocked issue",
                                "status": {"name": "Open"},
                            },
                        },
                    },
                    {
                        "type": {"name": "Relates"},
                        "inwardIssue": {
                            "key": "EDM-30",
                            "fields": {
                                "summary": "Related issue",
                                "status": {"name": "Closed"},
                            },
                        },
                    },
                ],
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-10", "--fields", "summary", "--links",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output["links"]), 2)
        self.assertEqual(output["links"][0]["key"], "EDM-20")
        self.assertEqual(output["links"][0]["direction"], "outward")
        self.assertEqual(output["links"][0]["type"], "Blocks")
        self.assertEqual(output["links"][1]["key"], "EDM-30")
        self.assertEqual(output["links"][1]["direction"], "inward")

    def test_get_link_fields(self) -> None:
        """--link-fields controls which fields are returned for links."""
        api_response = {
            "key": "EDM-10",
            "fields": {
                "summary": "Main",
                "issuelinks": [
                    {
                        "type": {"name": "Blocks"},
                        "outwardIssue": {
                            "key": "EDM-20",
                            "fields": {
                                "summary": "Blocked",
                                "status": {"name": "Open"},
                                "priority": {"name": "High"},
                            },
                        },
                    },
                ],
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-10", "--fields", "summary",
                    "--links", "--link-fields", "summary",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        link_fields = output["links"][0]["fields"]
        self.assertIn("summary", link_fields)
        self.assertNotIn("priority", link_fields)

    def test_get_with_parent(self) -> None:
        """--parent includes parent issue data in the output."""
        api_response = {
            "key": "EDM-50",
            "fields": {
                "summary": "Child task",
                "parent": {
                    "key": "EDM-40",
                    "fields": {
                        "summary": "Parent epic",
                        "status": {"name": "In Progress"},
                        "issuetype": {"name": "Epic"},
                    },
                },
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-50", "--fields", "summary", "--parent",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["parent"]["key"], "EDM-40")
        self.assertEqual(output["parent"]["fields"]["summary"], "Parent epic")

    def test_get_parent_fields(self) -> None:
        """--parent-fields controls which fields are returned for parent."""
        api_response = {
            "key": "EDM-50",
            "fields": {
                "summary": "Child",
                "parent": {
                    "key": "EDM-40",
                    "fields": {
                        "summary": "Parent",
                        "status": {"name": "Done"},
                        "issuetype": {"name": "Epic"},
                        "priority": {"name": "High"},
                    },
                },
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-50", "--fields", "summary",
                    "--parent", "--parent-fields", "summary,status",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertIn("summary", output["parent"]["fields"])
        self.assertIn("status", output["parent"]["fields"])
        self.assertNotIn("priority", output["parent"]["fields"])

    def test_get_no_parent(self) -> None:
        """--parent returns null when the issue has no parent."""
        api_response = {
            "key": "EDM-99",
            "fields": {
                "summary": "Standalone",
                "parent": None,
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-99", "--fields", "summary", "--parent",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertIsNone(output["parent"])

    def test_get_url_construction(self) -> None:
        """Verify the URL sent to the Jira API is correctly constructed."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main(["get", "EDM-1", "--fields", "summary"])

        # Inspect the Request object passed to urlopen
        request = mock_open.call_args[0][0]
        self.assertIn("/rest/api/3/issue/EDM-1", request.full_url)
        self.assertIn("fields=summary", request.full_url)

    def test_get_auth_header_sent(self) -> None:
        """Verify the Authorization header is included in the request."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main(["get", "EDM-1", "--fields", "summary"])

        request = mock_open.call_args[0][0]
        self.assertEqual(
            request.get_header("Authorization"), "Bearer test-token",
        )

    def test_get_trailing_slash_stripped(self) -> None:
        """Trailing slash on JIRA_URL is stripped from the API URL."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)
        env = {**self.env, "JIRA_URL": "https://jira.example.com/"}

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main(["get", "EDM-1", "--fields", "summary"])

        request = mock_open.call_args[0][0]
        self.assertNotIn("//rest", request.full_url)
        self.assertIn("/rest/api/3/issue/EDM-1", request.full_url)


# ---------------------------------------------------------------------------
# search subcommand tests
# ---------------------------------------------------------------------------


class TestSearchSubcommand(unittest.TestCase):
    """Verify search subcommand behavior."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_search_basic(self) -> None:
        """Searches and returns total + issues array."""
        api_response = {
            "total": 2,
            "isLast": True,
            "issues": [
                {
                    "key": "EDM-1",
                    "fields": {
                        "summary": "First issue",
                        "status": {"name": "Open"},
                    },
                },
                {
                    "key": "EDM-2",
                    "fields": {
                        "summary": "Second issue",
                        "status": {"name": "Closed"},
                    },
                },
            ],
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary,status",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total"], 2)
        self.assertEqual(len(output["issues"]), 2)
        self.assertEqual(output["issues"][0]["key"], "EDM-1")
        self.assertEqual(
            output["issues"][0]["fields"]["summary"], "First issue",
        )

    def test_search_custom_fields(self) -> None:
        """--fields limits which fields appear in search results."""
        api_response = {
            "total": 1,
            "isLast": True,
            "issues": [
                {
                    "key": "EDM-1",
                    "fields": {
                        "summary": "Issue",
                        "status": {"name": "Open"},
                        "priority": {"name": "High"},
                    },
                },
            ],
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertIn("summary", output["issues"][0]["fields"])
        self.assertNotIn("priority", output["issues"][0]["fields"])

    def test_search_url_construction(self) -> None:
        """Verify the search URL uses v3 search/jql endpoint."""
        api_response = {"total": 0, "issues": [], "isLast": True}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "search", "project = EDM",
                    "--max-results", "25",
                ])

        request = mock_open.call_args[0][0]
        self.assertIn("/rest/api/3/search/jql", request.full_url)
        self.assertIn("maxResults=25", request.full_url)
        self.assertIn("jql=", request.full_url)
        # First request should NOT have nextPageToken
        self.assertNotIn("nextPageToken", request.full_url)

    def test_search_empty_results(self) -> None:
        """Empty search results return total 0 and empty issues array."""
        api_response = {"total": 0, "issues": [], "isLast": True}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main(["search", "project = NOTHING"])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total"], 0)
        self.assertEqual(output["issues"], [])


# ---------------------------------------------------------------------------
# Search pagination tests (nextPageToken / isLast cursor pagination)
# ---------------------------------------------------------------------------


class TestSearchPagination(unittest.TestCase):
    """Verify internal cursor-based pagination in cmd_search."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    @staticmethod
    def _make_issues(start: int, count: int) -> list[dict[str, Any]]:
        """Generate a list of mock Jira issue dicts."""
        return [
            {
                "key": f"EDM-{start + i}",
                "fields": {"summary": f"Issue {start + i}"},
            }
            for i in range(count)
        ]

    def test_multi_page_pagination(self) -> None:
        """Fetches multiple pages using nextPageToken until isLast=True."""
        page_size = fetch_issue.SEARCH_PAGE_SIZE  # 50
        page1 = _mock_urlopen({
            "total": 60,
            "isLast": False,
            "nextPageToken": "cursor-abc",
            "issues": self._make_issues(1, page_size),
        })
        page2 = _mock_urlopen({
            "total": 60,
            "isLast": True,
            "issues": self._make_issues(page_size + 1, 10),
        })

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch(
                "urllib.request.urlopen",
                side_effect=[page1, page2],
            ),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                    "--max-results", "200",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total"], 60)
        self.assertEqual(len(output["issues"]), 60)

    def test_max_results_cap_stops_early(self) -> None:
        """--max-results cap stops iteration before exhausting results."""
        page1 = _mock_urlopen({
            "total": 100,
            "isLast": False,
            "nextPageToken": "cursor-xyz",
            "issues": self._make_issues(1, 30),
        })

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=page1),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                    "--max-results", "30",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total"], 100)
        self.assertEqual(len(output["issues"]), 30)

    def test_single_page_result(self) -> None:
        """Fewer results than page size — isLast=True on first request."""
        resp = _mock_urlopen({
            "total": 3,
            "isLast": True,
            "issues": self._make_issues(1, 3),
        })

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch(
                "urllib.request.urlopen", return_value=resp,
            ) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total"], 3)
        self.assertEqual(len(output["issues"]), 3)
        self.assertEqual(mock_open.call_count, 1)

    def test_total_from_api_reported(self) -> None:
        """Output total comes from the API response."""
        resp = _mock_urlopen({
            "total": 500,
            "isLast": True,
            "issues": self._make_issues(1, 50),
        })

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                    "--max-results", "50",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total"], 500)
        self.assertEqual(len(output["issues"]), 50)

    def test_total_omitted_when_api_omits_it(self) -> None:
        """Output omits total when the API response has no total field."""
        resp = _mock_urlopen({
            "isLast": True,
            "issues": self._make_issues(1, 2),
        })

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertNotIn("total", output)
        self.assertEqual(len(output["issues"]), 2)

    def test_pagination_sends_next_page_token(self) -> None:
        """Second request includes nextPageToken from first response."""
        page1 = _mock_urlopen({
            "total": 60,
            "isLast": False,
            "nextPageToken": "tok-page2",
            "issues": self._make_issues(1, fetch_issue.SEARCH_PAGE_SIZE),
        })
        page2 = _mock_urlopen({
            "total": 60,
            "isLast": True,
            "issues": self._make_issues(51, 10),
        })

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch(
                "urllib.request.urlopen",
                side_effect=[page1, page2],
            ) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary",
                    "--max-results", "200",
                ])

        self.assertEqual(mock_open.call_count, 2)
        first_url = mock_open.call_args_list[0][0][0].full_url
        second_url = mock_open.call_args_list[1][0][0].full_url
        # First request: no nextPageToken
        self.assertNotIn("nextPageToken", first_url)
        # Second request: includes the token from page 1
        self.assertIn("nextPageToken=tok-page2", second_url)
        # No startAt in either request
        self.assertNotIn("startAt", first_url)
        self.assertNotIn("startAt", second_url)

    def test_default_max_results_is_200(self) -> None:
        """Default --max-results is 200."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args(["search", "project = EDM"])
        self.assertEqual(args.max_results, 200)

    def test_search_uses_v3_search_jql_endpoint(self) -> None:
        """Search always uses /rest/api/3/search/jql."""
        resp = _mock_urlopen({"issues": [], "isLast": True})
        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main(["search", "project = EDM"])
        request = mock_open.call_args[0][0]
        self.assertIn("/rest/api/3/search/jql", request.full_url)


# ---------------------------------------------------------------------------
# HTTP error handling tests
# ---------------------------------------------------------------------------


class TestHTTPErrors(unittest.TestCase):
    """Verify HTTP error handling."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_404_error(self) -> None:
        """HTTP 404 exits with code 1 and includes 'not found' message."""
        error = urllib.error.HTTPError(
            "https://jira.example.com/rest/api/2/issue/NOPE-1",
            404, "Not Found", {}, io.BytesIO(b"Issue Does Not Exist"),
        )

        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=error),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "NOPE-1"])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)
        self.assertIn("not found", buf.getvalue().lower())

    def test_401_error(self) -> None:
        """HTTP 401 exits with code 1 and includes status code."""
        error = urllib.error.HTTPError(
            "https://jira.example.com/rest/api/2/issue/EDM-1",
            401, "Unauthorized", {}, io.BytesIO(b"Bad credentials"),
        )

        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=error),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)
        self.assertIn("401", buf.getvalue())

    def test_500_error(self) -> None:
        """HTTP 500 exits with code 1."""
        error = urllib.error.HTTPError(
            "https://jira.example.com/rest/api/2/issue/EDM-1",
            500, "Internal Server Error", {},
            io.BytesIO(b"Server error"),
        )

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=error),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_url_error(self) -> None:
        """Network failures (URLError) exit with code 1."""
        error = urllib.error.URLError("Connection refused")

        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=error),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)
        self.assertIn("Request failed", buf.getvalue())

    def test_search_http_error(self) -> None:
        """Search subcommand also handles HTTP errors."""
        error = urllib.error.HTTPError(
            "https://jira.example.com/rest/api/2/search",
            400, "Bad Request", {},
            io.BytesIO(b"Invalid JQL"),
        )

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=error),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["search", "invalid jql %%%"])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)


# ---------------------------------------------------------------------------
# SUBCOMMAND_MAP tests
# ---------------------------------------------------------------------------


class TestSubcommandMap(unittest.TestCase):
    """Verify subcommand routing."""

    def test_subcommand_map_entries(self) -> None:
        """SUBCOMMAND_MAP has entries for all subcommands."""
        self.assertIn("get", fetch_issue.SUBCOMMAND_MAP)
        self.assertIn("search", fetch_issue.SUBCOMMAND_MAP)
        self.assertEqual(fetch_issue.SUBCOMMAND_MAP["get"], fetch_issue.cmd_get)
        self.assertEqual(
            fetch_issue.SUBCOMMAND_MAP["search"], fetch_issue.cmd_search,
        )

    def test_unknown_subcommand_not_in_map(self) -> None:
        """Unknown subcommands are not in the map."""
        self.assertNotIn("delete", fetch_issue.SUBCOMMAND_MAP)


# ---------------------------------------------------------------------------
# Fields appending tests (internal API field list construction)
# ---------------------------------------------------------------------------


class TestFieldsAppending(unittest.TestCase):
    """Verify that --links/--parent/--comments append to the API fields."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_links_appends_issuelinks(self) -> None:
        """--links adds issuelinks to the API request fields."""
        api_response = {
            "key": "EDM-1",
            "fields": {"summary": "Test", "issuelinks": []},
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary", "--links",
                ])

        request = mock_open.call_args[0][0]
        self.assertIn("issuelinks", request.full_url)

    def test_parent_appends_parent_field(self) -> None:
        """--parent adds parent to the API request fields."""
        api_response = {
            "key": "EDM-1",
            "fields": {"summary": "Test", "parent": None},
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary", "--parent",
                ])

        request = mock_open.call_args[0][0]
        self.assertIn("parent", request.full_url)

    def test_comments_appends_comment_field(self) -> None:
        """--comments adds comment to the API request fields."""
        api_response = {
            "key": "EDM-1",
            "fields": {
                "summary": "Test",
                "comment": {"comments": []},
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary", "--comments",
                ])

        request = mock_open.call_args[0][0]
        self.assertIn("comment", request.full_url)

    def test_no_duplicate_fields(self) -> None:
        """If issuelinks is already in --fields, it is not duplicated."""
        api_response = {
            "key": "EDM-1",
            "fields": {"summary": "Test", "issuelinks": []},
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1",
                    "--fields", "summary,issuelinks",
                    "--links",
                ])

        request = mock_open.call_args[0][0]
        url = request.full_url
        # Count occurrences of issuelinks -- should appear exactly once
        fields_part = url.split("fields=")[1]
        self.assertEqual(fields_part.count("issuelinks"), 1)


# ---------------------------------------------------------------------------
# Timeout handling tests (review item #1)
# ---------------------------------------------------------------------------


class TestTimeout(unittest.TestCase):
    """Verify request timeout handling."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_timeout_constant_exists(self) -> None:
        """REQUEST_TIMEOUT constant is defined and positive."""
        self.assertIsInstance(fetch_issue.REQUEST_TIMEOUT, int)
        self.assertGreater(fetch_issue.REQUEST_TIMEOUT, 0)

    def test_timeout_passed_to_urlopen(self) -> None:
        """urlopen is called with the timeout parameter."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main(["get", "EDM-1", "--fields", "summary"])

        _, kwargs = mock_open.call_args
        self.assertEqual(kwargs["timeout"], fetch_issue.REQUEST_TIMEOUT)

    def test_timeout_error_exits_1(self) -> None:
        """TimeoutError exits with code 1 and includes timeout message."""
        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=TimeoutError),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)
        self.assertIn("timed out", buf.getvalue().lower())


# ---------------------------------------------------------------------------
# URL encoding tests (review item #2)
# ---------------------------------------------------------------------------


class TestURLEncoding(unittest.TestCase):
    """Verify percent-encoding of key and fields in get URLs."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_get_key_with_special_chars_encoded(self) -> None:
        """Keys with special characters are percent-encoded in the URL."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary",
                ])

        request = mock_open.call_args[0][0]
        # Normal keys should pass through cleanly
        self.assertIn("/issue/EDM-1", request.full_url)

    def test_get_fields_commas_preserved(self) -> None:
        """Commas in field lists are preserved (safe chars)."""
        api_response = {"key": "EDM-1", "fields": {"summary": "T", "status": {"name": "O"}}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary,status",
                ])

        request = mock_open.call_args[0][0]
        self.assertIn("fields=summary,status", request.full_url)


# ---------------------------------------------------------------------------
# Negative comment-limit validation tests (review item #4)
# ---------------------------------------------------------------------------


class TestNegativeCommentLimit(unittest.TestCase):
    """Verify that negative --comment-limit values are rejected."""

    def test_negative_comment_limit_rejected(self) -> None:
        """--comment-limit with a negative value exits with code 2."""
        with self.assertRaises(SystemExit) as ctx:
            fetch_issue.main([
                "get", "EDM-1", "--comment-limit", "-1",
            ])
        self.assertEqual(ctx.exception.code, 2)

    def test_zero_comment_limit_accepted(self) -> None:
        """--comment-limit 0 (meaning all) is accepted."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args(["get", "EDM-1", "--comment-limit", "0"])
        self.assertEqual(args.comment_limit, 0)

    def test_positive_comment_limit_accepted(self) -> None:
        """--comment-limit with a positive value is accepted."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args(["get", "EDM-1", "--comment-limit", "10"])
        self.assertEqual(args.comment_limit, 10)


# ---------------------------------------------------------------------------
# --max-results validation tests
# ---------------------------------------------------------------------------


class TestMaxResultsValidation(unittest.TestCase):
    """Verify --max-results must be >= 1."""

    def test_zero_max_results_rejected(self) -> None:
        """--max-results 0 is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            fetch_issue.main(["search", "project = X", "--max-results", "0"])
        self.assertEqual(ctx.exception.code, 2)

    def test_negative_max_results_rejected(self) -> None:
        """--max-results -1 is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            fetch_issue.main(["search", "project = X", "--max-results", "-5"])
        self.assertEqual(ctx.exception.code, 2)

    def test_positive_max_results_accepted(self) -> None:
        """--max-results 1 is accepted."""
        parser = fetch_issue.build_parser()
        args = parser.parse_args(["search", "project = X", "--max-results", "1"])
        self.assertEqual(args.max_results, 1)


# ---------------------------------------------------------------------------
# Exact field token matching tests (review item #5)
# ---------------------------------------------------------------------------


class TestExactFieldMatching(unittest.TestCase):
    """Verify field presence uses exact token matching, not substring."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_comment_not_confused_with_commentCount(self) -> None:
        """--comments appends 'comment' even if 'commentCount' is in fields."""
        api_response = {
            "key": "EDM-1",
            "fields": {
                "commentCount": 5,
                "comment": {"comments": []},
            },
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1",
                    "--fields", "commentCount",
                    "--comments",
                ])

        request = mock_open.call_args[0][0]
        # "comment" should be appended because "commentCount" != "comment"
        url = request.full_url
        fields_part = url.split("fields=")[1]
        self.assertIn("commentCount", fields_part)
        self.assertIn(",comment", fields_part)

    def test_parent_not_confused_with_parentKey(self) -> None:
        """--parent appends 'parent' even if 'parentKey' is in fields."""
        api_response = {
            "key": "EDM-1",
            "fields": {"parentKey": "EDM-0", "parent": None},
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1",
                    "--fields", "parentKey",
                    "--parent",
                ])

        request = mock_open.call_args[0][0]
        url = request.full_url
        fields_part = url.split("fields=")[1]
        self.assertIn("parentKey", fields_part)
        self.assertIn(",parent", fields_part)

    def test_exact_match_does_not_duplicate(self) -> None:
        """When the exact token is present, it is not duplicated."""
        api_response = {
            "key": "EDM-1",
            "fields": {"summary": "T", "comment": {"comments": []}},
        }
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-1",
                    "--fields", "summary,comment",
                    "--comments",
                ])

        request = mock_open.call_args[0][0]
        url = request.full_url
        fields_part = url.split("fields=")[1]
        self.assertEqual(fields_part.count("comment"), 1)


# ---------------------------------------------------------------------------
# HTTPS enforcement tests (review item: scheme enforcement)
# ---------------------------------------------------------------------------


class TestHTTPSEnforcement(unittest.TestCase):
    """Verify HTTPS enforcement on JIRA_URL with urlsplit validation."""

    def test_http_url_rejected(self) -> None:
        """HTTP JIRA_URL is rejected by default."""
        env = {"JIRA_URL": "http://jira.local:8080", "JIRA_TOKEN": "tok"}
        with (
            mock.patch.dict("os.environ", env, clear=True),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_file_url_rejected(self) -> None:
        """file:// JIRA_URL is always rejected even with opt-in."""
        env = {
            "JIRA_URL": "file:///etc/passwd",
            "JIRA_TOKEN": "tok",
            "JIRA_ALLOW_INSECURE_HTTP": "1",
        }
        with (
            mock.patch.dict("os.environ", env, clear=True),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_ftp_url_rejected(self) -> None:
        """ftp:// JIRA_URL is always rejected even with opt-in."""
        env = {
            "JIRA_URL": "ftp://jira.example.com",
            "JIRA_TOKEN": "tok",
            "JIRA_ALLOW_INSECURE_HTTP": "1",
        }
        with (
            mock.patch.dict("os.environ", env, clear=True),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_https_without_hostname_rejected(self) -> None:
        """https:// with no hostname is rejected."""
        env = {"JIRA_URL": "https://", "JIRA_TOKEN": "tok"}
        with (
            mock.patch.dict("os.environ", env, clear=True),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_malformed_url_rejected(self) -> None:
        """Malformed JIRA_URL (no scheme) is rejected."""
        env = {"JIRA_URL": "jira.example.com", "JIRA_TOKEN": "tok"}
        with (
            mock.patch.dict("os.environ", env, clear=True),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)

    def test_http_url_accepted_with_opt_in(self) -> None:
        """HTTP JIRA_URL is accepted when JIRA_ALLOW_INSECURE_HTTP=1."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)
        env = {
            "JIRA_URL": "http://jira.local:8080",
            "JIRA_TOKEN": "test-token",
            "JIRA_ALLOW_INSECURE_HTTP": "1",
        }

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main(["get", "EDM-1", "--fields", "summary"])

        self.assertEqual(code, 0)

    def test_https_url_always_accepted(self) -> None:
        """HTTPS JIRA_URL is always accepted without opt-in."""
        api_response = {"key": "EDM-1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main(["get", "EDM-1", "--fields", "summary"])

        self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# Reserved-character encoding in issue key (review item: encoding)
# ---------------------------------------------------------------------------


class TestReservedCharEncoding(unittest.TestCase):
    """Verify that reserved characters in issue keys are percent-encoded."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_key_with_reserved_chars_encoded(self) -> None:
        """Issue key containing reserved chars is percent-encoded in URL."""
        api_response = {"key": "A&B=1", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "A&B=1", "--fields", "summary",
                ])

        request = mock_open.call_args[0][0]
        url = request.full_url
        # Raw "&" and "=" in the path would break URL parsing.
        # They must be percent-encoded as %26 and %3D.
        self.assertIn("/issue/A%26B%3D1", url)
        self.assertNotIn("/issue/A&B=1", url)

    def test_key_with_space_encoded(self) -> None:
        """Issue key containing a space is percent-encoded."""
        api_response = {"key": "X Y", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "X Y", "--fields", "summary",
                ])

        request = mock_open.call_args[0][0]
        url = request.full_url
        self.assertIn("/issue/X%20Y", url)
        self.assertNotIn("/issue/X Y", url)

    def test_normal_key_unchanged(self) -> None:
        """A normal issue key (letters, digits, hyphen) passes through."""
        api_response = {"key": "EDM-123", "fields": {"summary": "Test"}}
        mock_resp = _mock_urlopen(api_response)

        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_open,
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                fetch_issue.main([
                    "get", "EDM-123", "--fields", "summary",
                ])

        request = mock_open.call_args[0][0]
        self.assertIn("/issue/EDM-123", request.full_url)


# ---------------------------------------------------------------------------
# urlsplit ValueError handling tests
# ---------------------------------------------------------------------------


class TestUrlsplitValueError(unittest.TestCase):
    """Verify _get_jira_url handles malformed URLs that raise ValueError."""

    def test_malformed_bracket_url_rejected(self) -> None:
        """A URL with an invalid bracketed host triggers ValueError catch."""
        env = {"JIRA_URL": "https://[invalid", "JIRA_TOKEN": "tok"}
        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main(["get", "EDM-1"])
        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)
        self.assertIn("malformed", buf.getvalue().lower())


# ---------------------------------------------------------------------------
# nextPageToken duplicate detection tests
# ---------------------------------------------------------------------------


class TestPaginationDuplicateToken(unittest.TestCase):
    """Verify cmd_search stops on duplicate nextPageToken."""

    def setUp(self) -> None:
        self.env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

    def test_duplicate_token_causes_exit(self) -> None:
        """Repeated nextPageToken triggers fail() with loop message."""
        page1 = _mock_urlopen({
            "total": 100,
            "isLast": False,
            "nextPageToken": "tok-A",
            "issues": [
                {"key": "EDM-1", "fields": {"summary": "a"}},
            ],
        })
        page2 = _mock_urlopen({
            "total": 100,
            "isLast": False,
            "nextPageToken": "tok-A",  # same token again
            "issues": [
                {"key": "EDM-2", "fields": {"summary": "b"}},
            ],
        })

        buf = io.StringIO()
        with (
            mock.patch.dict("os.environ", self.env, clear=True),
            mock.patch(
                "urllib.request.urlopen",
                side_effect=[page1, page2],
            ),
            mock.patch("sys.stderr", buf),
            self.assertRaises(SystemExit) as ctx,
        ):
            fetch_issue.main([
                "search", "project = EDM",
                "--fields", "summary",
                "--max-results", "200",
            ])

        self.assertEqual(ctx.exception.code, fetch_issue.EXIT_ERROR)
        self.assertIn("loop detected", buf.getvalue().lower())


# ---------------------------------------------------------------------------
# ADF flattening tests
# ---------------------------------------------------------------------------


class TestFlattenADF(unittest.TestCase):
    """Verify ADF-to-plain-text flattening."""

    def test_simple_paragraph(self) -> None:
        """Single paragraph with one text node."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Hello world"},
                    ],
                },
            ],
        }
        self.assertEqual(fetch_issue._flatten_adf(adf), "Hello world")

    def test_nested_structure(self) -> None:
        """Multiple paragraphs with inline formatting nodes."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "First "},
                        {"type": "text", "text": "paragraph"},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Second paragraph"},
                    ],
                },
            ],
        }
        result = fetch_issue._flatten_adf(adf)
        self.assertIn("First paragraph", result)
        self.assertIn("Second paragraph", result)

    def test_plain_string_passthrough(self) -> None:
        """Plain string input is returned as-is."""
        self.assertEqual(fetch_issue._flatten_adf("plain text"), "plain text")

    def test_none_returns_none(self) -> None:
        """None input passes through as None."""
        self.assertIsNone(fetch_issue._flatten_adf(None))

    def test_string_passes_through(self) -> None:
        """Plain string passes through unchanged."""
        self.assertEqual(fetch_issue._flatten_adf("hello"), "hello")

    def test_int_passes_through(self) -> None:
        """Non-dict non-string values pass through unchanged."""
        self.assertEqual(fetch_issue._flatten_adf(42), 42)

    def test_hardbreak_produces_newline(self) -> None:
        """hardBreak inline node produces a newline character."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Line one"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "Line two"},
                    ],
                },
            ],
        }
        result = fetch_issue._flatten_adf(adf)
        self.assertEqual(result, "Line one\nLine two")

    def test_mention_preserves_display_text(self) -> None:
        """mention inline node preserves attrs.text as display text."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Assigned to "},
                        {
                            "type": "mention",
                            "attrs": {
                                "id": "abc123",
                                "text": "@alice",
                                "accessLevel": "",
                            },
                        },
                        {"type": "text", "text": " for review"},
                    ],
                },
            ],
        }
        result = fetch_issue._flatten_adf(adf)
        self.assertEqual(result, "Assigned to @alice for review")

    def test_emoji_preserves_shortname(self) -> None:
        """emoji inline node preserves attrs.shortName."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Great work "},
                        {
                            "type": "emoji",
                            "attrs": {
                                "shortName": ":thumbsup:",
                                "id": "1f44d",
                            },
                        },
                    ],
                },
            ],
        }
        result = fetch_issue._flatten_adf(adf)
        self.assertEqual(result, "Great work :thumbsup:")

    def test_adf_description_flattened_in_get(self) -> None:
        """cmd_get flattens ADF description to plain text in output."""
        adf_desc = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Bug description here"},
                    ],
                },
            ],
        }
        api_response = {
            "key": "EDM-1",
            "fields": {
                "summary": "Test",
                "description": adf_desc,
            },
        }
        mock_resp = _mock_urlopen(api_response)
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary,description",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["fields"]["description"], "Bug description here")

    def test_adf_comment_body_flattened_in_get(self) -> None:
        """cmd_get flattens ADF comment bodies to plain text."""
        adf_body = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Comment text"},
                    ],
                },
            ],
        }
        api_response = {
            "key": "EDM-1",
            "fields": {
                "summary": "Test",
                "comment": {
                    "comments": [
                        {
                            "id": "100",
                            "author": {"displayName": "Alice"},
                            "body": adf_body,
                            "created": "2025-01-01",
                        },
                    ],
                },
            },
        }
        mock_resp = _mock_urlopen(api_response)
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "get", "EDM-1", "--fields", "summary", "--comments",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output["comments"][0]["body"], "Comment text")

    def test_adf_description_flattened_in_search(self) -> None:
        """cmd_search flattens ADF description to plain text in output."""
        adf_desc = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Search result description"},
                    ],
                },
            ],
        }
        api_response = {
            "total": 1,
            "isLast": True,
            "issues": [
                {
                    "key": "EDM-1",
                    "fields": {
                        "summary": "Test",
                        "description": adf_desc,
                    },
                },
            ],
        }
        mock_resp = _mock_urlopen(api_response)
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary,description",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(
            output["issues"][0]["fields"]["description"],
            "Search result description",
        )

    def test_search_null_description_preserved(self) -> None:
        """cmd_search preserves None description (not converted to '')."""
        api_response = {
            "total": 1,
            "isLast": True,
            "issues": [
                {
                    "key": "EDM-1",
                    "fields": {
                        "summary": "Test",
                        "description": None,
                    },
                },
            ],
        }
        mock_resp = _mock_urlopen(api_response)
        env = {
            "JIRA_URL": "https://jira.example.com",
            "JIRA_TOKEN": "test-token",
        }

        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = fetch_issue.main([
                    "search", "project = EDM",
                    "--fields", "summary,description",
                ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertIsNone(output["issues"][0]["fields"]["description"])


    def test_table_cell_paragraphs_separated_by_newlines(self) -> None:
        """Multiple paragraphs inside a tableCell are separated by newlines."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "table",
                    "content": [
                        {
                            "type": "tableRow",
                            "content": [
                                {
                                    "type": "tableCell",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "First paragraph"},
                                            ],
                                        },
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Second paragraph"},
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        result = fetch_issue._flatten_adf(adf)
        self.assertIn("First paragraph\nSecond paragraph", result)


if __name__ == "__main__":
    unittest.main()
