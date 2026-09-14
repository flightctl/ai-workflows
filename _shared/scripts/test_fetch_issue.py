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
        self.assertEqual(args.max_results, 50)

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
        self.assertIn("/rest/api/2/issue/EDM-1", request.full_url)
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
        self.assertIn("/rest/api/2/issue/EDM-1", request.full_url)


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
        """Verify the search URL includes JQL and maxResults."""
        api_response = {"total": 0, "issues": []}
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
        self.assertIn("/rest/api/2/search", request.full_url)
        self.assertIn("maxResults=25", request.full_url)
        # JQL should be URL-encoded
        self.assertIn("jql=", request.full_url)

    def test_search_empty_results(self) -> None:
        """Empty search results return total 0 and empty issues array."""
        api_response = {"total": 0, "issues": []}
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


if __name__ == "__main__":
    unittest.main()
