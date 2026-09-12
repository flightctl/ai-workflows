#!/usr/bin/env python3
"""Tests for _shared/scripts/pr-comments.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent / "pr-comments.py"
_spec = importlib.util.spec_from_file_location("pr_comments", _SCRIPT)
assert _spec and _spec.loader
pr_comments = importlib.util.module_from_spec(_spec)
sys.modules["pr_comments"] = pr_comments
_spec.loader.exec_module(pr_comments)


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Verify argparse configuration for each subcommand."""

    def test_fetch_required_args(self) -> None:
        """Fetch subcommand parses required arguments correctly."""
        parser = pr_comments.build_parser()
        args = parser.parse_args([
            "fetch", "--owner", "acme", "--repo", "proj", "--pr", "42",
        ])
        self.assertEqual(args.subcommand, "fetch")
        self.assertEqual(args.owner, "acme")
        self.assertEqual(args.repo, "proj")
        self.assertEqual(args.pr, 42)
        self.assertEqual(args.since, "")
        self.assertEqual(args.responses_log, "")
        self.assertFalse(args.include_review_threads)

    def test_fetch_all_options(self) -> None:
        """Fetch subcommand parses all optional arguments."""
        parser = pr_comments.build_parser()
        args = parser.parse_args([
            "fetch", "--owner", "acme", "--repo", "proj", "--pr", "10",
            "--since", "2025-01-01T00:00:00Z",
            "--responses-log", "/tmp/log.jsonl",
            "--include-review-threads",
        ])
        self.assertEqual(args.since, "2025-01-01T00:00:00Z")
        self.assertEqual(args.responses_log, "/tmp/log.jsonl")
        self.assertTrue(args.include_review_threads)

    def test_fetch_missing_owner(self) -> None:
        """Fetch exits with code 2 when --owner is missing."""
        parser = pr_comments.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["fetch", "--repo", "proj", "--pr", "1"])
        self.assertEqual(ctx.exception.code, 2)

    def test_fetch_missing_repo(self) -> None:
        """Fetch exits with code 2 when --repo is missing."""
        parser = pr_comments.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["fetch", "--owner", "acme", "--pr", "1"])
        self.assertEqual(ctx.exception.code, 2)

    def test_fetch_missing_pr(self) -> None:
        """Fetch exits with code 2 when --pr is missing."""
        parser = pr_comments.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["fetch", "--owner", "acme", "--repo", "proj"])
        self.assertEqual(ctx.exception.code, 2)

    def test_reply_required_args(self) -> None:
        """Reply subcommand parses required arguments correctly."""
        parser = pr_comments.build_parser()
        args = parser.parse_args([
            "reply", "--owner", "acme", "--repo", "proj",
            "--pr", "5", "--body-file", "/tmp/body.md",
        ])
        self.assertEqual(args.subcommand, "reply")
        self.assertEqual(args.owner, "acme")
        self.assertEqual(args.repo, "proj")
        self.assertEqual(args.pr, 5)
        self.assertEqual(args.body_file, "/tmp/body.md")
        self.assertEqual(args.comment_id, "")

    def test_reply_with_comment_id(self) -> None:
        """Reply subcommand parses optional --comment-id."""
        parser = pr_comments.build_parser()
        args = parser.parse_args([
            "reply", "--owner", "acme", "--repo", "proj",
            "--pr", "5", "--body-file", "/tmp/body.md",
            "--comment-id", "12345",
        ])
        self.assertEqual(args.comment_id, "12345")

    def test_reply_missing_body_file(self) -> None:
        """Reply exits with code 2 when --body-file is missing."""
        parser = pr_comments.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args([
                "reply", "--owner", "acme", "--repo", "proj", "--pr", "5",
            ])
        self.assertEqual(ctx.exception.code, 2)

    def test_log_required_args(self) -> None:
        """Log subcommand parses required arguments correctly."""
        parser = pr_comments.build_parser()
        args = parser.parse_args([
            "log", "--responses-log", "/tmp/log.jsonl",
            "--comment-id", "99",
        ])
        self.assertEqual(args.subcommand, "log")
        self.assertEqual(args.responses_log, "/tmp/log.jsonl")
        self.assertEqual(args.comment_id, "99")
        self.assertEqual(args.response_summary, "")

    def test_log_with_summary(self) -> None:
        """Log subcommand parses optional --response-summary."""
        parser = pr_comments.build_parser()
        args = parser.parse_args([
            "log", "--responses-log", "/tmp/log.jsonl",
            "--comment-id", "99", "--response-summary", "Fixed typo",
        ])
        self.assertEqual(args.response_summary, "Fixed typo")

    def test_log_missing_responses_log(self) -> None:
        """Log exits with code 2 when --responses-log is missing."""
        parser = pr_comments.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["log", "--comment-id", "99"])
        self.assertEqual(ctx.exception.code, 2)

    def test_log_missing_comment_id(self) -> None:
        """Log exits with code 2 when --comment-id is missing."""
        parser = pr_comments.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["log", "--responses-log", "/tmp/log.jsonl"])
        self.assertEqual(ctx.exception.code, 2)

    def test_no_subcommand(self) -> None:
        """No subcommand returns EXIT_RUNTIME_ERROR."""
        result = pr_comments.main([])
        self.assertEqual(result, pr_comments.EXIT_RUNTIME_ERROR)


# ---------------------------------------------------------------------------
# Exit code contract tests
# ---------------------------------------------------------------------------


class TestExitCodes(unittest.TestCase):
    """Verify the documented exit code contract."""

    def test_exit_code_constants(self) -> None:
        """Exit code constants match the documented contract."""
        self.assertEqual(pr_comments.EXIT_SUCCESS, 0)
        self.assertEqual(pr_comments.EXIT_RUNTIME_ERROR, 1)


# ---------------------------------------------------------------------------
# Fetch tests (with subprocess mocking)
# ---------------------------------------------------------------------------


class TestFetch(unittest.TestCase):
    """Verify fetch subcommand behaviour."""

    def _make_review_comment(
        self,
        *,
        cid: int = 100,
        author: str = "reviewer",
        body: str = "Fix this",
        created_at: str = "2025-06-01T10:00:00Z",
        path: str = "src/main.py",
        line: int = 42,
        in_reply_to_id: int | None = None,
        html_url: str = "https://github.com/acme/proj/pull/1#r100",
    ) -> dict:
        """Build a mock review comment dict matching GitHub REST API shape."""
        d: dict = {
            "id": cid,
            "user": {"login": author},
            "body": body,
            "created_at": created_at,
            "path": path,
            "line": line,
            "html_url": html_url,
        }
        if in_reply_to_id is not None:
            d["in_reply_to_id"] = in_reply_to_id
        return d

    def _make_pr_data(
        self,
        *,
        comments: list | None = None,
        reviews: list | None = None,
        url: str = "https://github.com/acme/proj/pull/1",
    ) -> dict:
        """Build a mock PR data dict matching gh pr view --json shape."""
        return {
            "comments": comments or [],
            "reviews": reviews or [],
            "url": url,
        }

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_basic(self, mock_run: mock.Mock) -> None:
        """Fetch with no filters returns all comments."""
        # --slurp wraps single page in an outer array
        review_comments = [self._make_review_comment()]
        pr_data = self._make_pr_data(
            comments=[{
                "id": "IC_200",
                "author": {"login": "user1"},
                "body": "Looks good",
                "createdAt": "2025-06-02T12:00:00Z",
                "url": "https://github.com/acme/proj/pull/1#issuecomment-200",
            }],
            reviews=[{
                "id": "RV_300",
                "author": {"login": "lead"},
                "body": "LGTM",
                "submittedAt": "2025-06-02T14:00:00Z",
            }],
        )

        mock_run.side_effect = [
            # gh api .../comments --paginate --slurp
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            # gh pr view --json
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 3)

        # Check line comment
        lc = output[0]
        self.assertEqual(lc["type"], "line_comment")
        self.assertEqual(lc["id"], 100)
        self.assertEqual(lc["author"], "reviewer")
        self.assertEqual(lc["path"], "src/main.py")
        self.assertEqual(lc["line"], 42)

        # Check top-level comment uses per-comment URL
        tl = output[1]
        self.assertEqual(tl["type"], "top_level")
        self.assertEqual(tl["id"], "IC_200")
        self.assertEqual(tl["author"], "user1")
        self.assertEqual(
            tl["url"],
            "https://github.com/acme/proj/pull/1#issuecomment-200",
        )

        # Check review
        rv = output[2]
        self.assertEqual(rv["type"], "review")
        self.assertEqual(rv["id"], "RV_300")
        self.assertEqual(rv["author"], "lead")

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_since_filter(self, mock_run: mock.Mock) -> None:
        """--since excludes older comments."""
        review_comments = [
            self._make_review_comment(
                cid=1, created_at="2025-01-01T00:00:00Z",
            ),
            self._make_review_comment(
                cid=2, created_at="2025-06-15T00:00:00Z",
            ),
        ]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                "--since", "2025-06-01T00:00:00Z",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["id"], 2)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_since_with_timezone_offset(
        self, mock_run: mock.Mock,
    ) -> None:
        """--since handles timezone offsets via datetime comparison.

        A comment at 2025-06-15T00:00:00Z is included when --since is
        2025-06-14T20:00:00-05:00 (which is 2025-06-15T01:00:00Z) because
        datetime comparison correctly identifies the cutoff is later than
        the comment.  A naive string comparison would incorrectly include
        comments because '2025-06-14' < '2025-06-15'.
        """
        review_comments = [
            self._make_review_comment(
                cid=1, created_at="2025-06-15T00:00:00Z",
            ),
            self._make_review_comment(
                cid=2, created_at="2025-06-15T02:00:00Z",
            ),
        ]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                # This is 2025-06-15T01:00:00Z — should exclude cid=1
                "--since", "2025-06-14T20:00:00-05:00",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        # Comment 1 (00:00Z) is before the cutoff (01:00Z); excluded
        # Comment 2 (02:00Z) is after the cutoff; included
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["id"], 2)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_since_naive_datetime(self, mock_run: mock.Mock) -> None:
        """--since without timezone info is treated as UTC, not rejected.

        A naive --since like '2025-06-01T00:00:00' (no Z or offset)
        must compare correctly against aware GitHub timestamps (which
        always have 'Z').  Without normalisation, this would raise
        TypeError on Python 3.10+.
        """
        review_comments = [
            self._make_review_comment(
                cid=1, created_at="2025-01-01T00:00:00Z",
            ),
            self._make_review_comment(
                cid=2, created_at="2025-06-15T00:00:00Z",
            ),
        ]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                # Naive datetime — no timezone suffix
                "--since", "2025-06-01T00:00:00",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        # Comment 1 (Jan) is before cutoff (Jun); excluded
        # Comment 2 (Jun 15) is after cutoff; included
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["id"], 2)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_responses_log_filter(self, mock_run: mock.Mock) -> None:
        """--responses-log excludes already-addressed comment IDs."""
        review_comments = [
            self._make_review_comment(cid=10),
            self._make_review_comment(cid=20),
            self._make_review_comment(cid=30),
        ]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            f.write(json.dumps({"comment_id": 10, "timestamp": "x"}) + "\n")
            f.write(json.dumps({"comment_id": 30, "timestamp": "y"}) + "\n")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = pr_comments.main([
                        "fetch", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--responses-log", f.name,
                    ])

                self.assertEqual(code, 0)
                output = json.loads(buf.getvalue())
                self.assertEqual(len(output), 1)
                self.assertEqual(output[0]["id"], 20)
            finally:
                os.unlink(f.name)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_combined_filters(self, mock_run: mock.Mock) -> None:
        """--since and --responses-log applied together."""
        review_comments = [
            self._make_review_comment(
                cid=1, created_at="2025-01-01T00:00:00Z",
            ),
            self._make_review_comment(
                cid=2, created_at="2025-06-15T00:00:00Z",
            ),
            self._make_review_comment(
                cid=3, created_at="2025-06-20T00:00:00Z",
            ),
        ]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            # Mark comment 2 as addressed
            f.write(json.dumps({"comment_id": 2}) + "\n")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = pr_comments.main([
                        "fetch", "--owner", "acme", "--repo", "proj",
                        "--pr", "1",
                        "--since", "2025-06-01T00:00:00Z",
                        "--responses-log", f.name,
                    ])

                self.assertEqual(code, 0)
                output = json.loads(buf.getvalue())
                # Comment 1: excluded by --since
                # Comment 2: excluded by --responses-log
                # Comment 3: passes both filters
                self.assertEqual(len(output), 1)
                self.assertEqual(output[0]["id"], 3)
            finally:
                os.unlink(f.name)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_nonexistent_responses_log(self, mock_run: mock.Mock) -> None:
        """--responses-log pointing to a non-existent file is fine (no IDs)."""
        review_comments = [self._make_review_comment(cid=1)]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                "--responses-log", "/nonexistent/path/log.jsonl",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 1)

    def test_fetch_responses_log_read_failure_exits_1(self) -> None:
        """OSError reading the responses log exits with code 1."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            f.write('{"comment_id": 1}\n')
            f.flush()
            try:
                with mock.patch(
                    "pathlib.Path.read_text",
                    side_effect=OSError("permission denied"),
                ):
                    with self.assertRaises(SystemExit) as ctx:
                        pr_comments.main([
                            "fetch", "--owner", "acme", "--repo", "proj",
                            "--pr", "1", "--responses-log", f.name,
                        ])
                    self.assertEqual(
                        ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR,
                    )
            finally:
                os.unlink(f.name)

    def test_fetch_malformed_jsonl_exits_1(self) -> None:
        """Malformed JSON in responses log exits with code 1."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            f.write('{"comment_id": 1}\n')
            f.write('NOT VALID JSON\n')
            f.flush()
            try:
                with self.assertRaises(SystemExit) as ctx:
                    pr_comments.main([
                        "fetch", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--responses-log", f.name,
                    ])
                self.assertEqual(
                    ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR,
                )
            finally:
                os.unlink(f.name)

    def test_fetch_non_object_jsonl_exits_1(self) -> None:
        """Non-object JSON record in responses log exits with code 1."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            f.write('{"comment_id": 1}\n')
            f.write('[1, 2, 3]\n')  # valid JSON but not a dict
            f.flush()
            try:
                with self.assertRaises(SystemExit) as ctx:
                    pr_comments.main([
                        "fetch", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--responses-log", f.name,
                    ])
                self.assertEqual(
                    ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR,
                )
            finally:
                os.unlink(f.name)

    def test_fetch_non_object_jsonl_reports_type(self) -> None:
        """Error message includes the unexpected type name."""
        import io
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            f.write('"just a string"\n')  # valid JSON, wrong type
            f.flush()
            try:
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf):
                    with self.assertRaises(SystemExit):
                        pr_comments.main([
                            "fetch", "--owner", "acme", "--repo", "proj",
                            "--pr", "1", "--responses-log", f.name,
                        ])
                err = buf.getvalue()
                self.assertIn("line 1", err)
                self.assertIn("str", err)
            finally:
                os.unlink(f.name)

    def test_fetch_malformed_jsonl_reports_line_number(self) -> None:
        """Error message includes file path and line number."""
        import io
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False,
        ) as f:
            f.write('{"comment_id": 1}\n')
            f.write('\n')  # blank line (skipped)
            f.write('{bad json\n')  # line 3 of file
            f.flush()
            try:
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf):
                    with self.assertRaises(SystemExit):
                        pr_comments.main([
                            "fetch", "--owner", "acme", "--repo", "proj",
                            "--pr", "1", "--responses-log", f.name,
                        ])
                err = buf.getvalue()
                self.assertIn("line 3", err)
                self.assertIn(f.name, err)
            finally:
                os.unlink(f.name)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_include_review_threads(self, mock_run: mock.Mock) -> None:
        """--include-review-threads annotates line comments with is_resolved."""
        review_comments = [
            self._make_review_comment(cid=100),
            self._make_review_comment(cid=200),
        ]
        pr_data = self._make_pr_data()
        gql_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {"nodes": [
                                        {"id": "PRC_1", "databaseId": 100},
                                    ]},
                                },
                                {
                                    "isResolved": False,
                                    "comments": {"nodes": [
                                        {"id": "PRC_2", "databaseId": 200},
                                    ]},
                                },
                            ],
                        },
                    },
                },
            },
        }

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
            # GraphQL query
            subprocess.CompletedProcess(
                [], 0, json.dumps(gql_response), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                "--include-review-threads",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 2)
        self.assertTrue(output[0]["is_resolved"])
        self.assertFalse(output[1]["is_resolved"])

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_review_threads_pagination(
        self, mock_run: mock.Mock,
    ) -> None:
        """Paginated GraphQL responses map all comment databaseIds per thread.

        Verifies two things:
          1. Threads from multiple GraphQL pages are accumulated.
          2. ALL comments within a thread (not just the first) get their
             databaseId mapped to the thread's isResolved status — so
             replies within a resolved thread also receive is_resolved.
        """
        # cid=100 is the root comment, cid=101 is a reply in the same thread
        review_comments = [
            self._make_review_comment(cid=100),
            self._make_review_comment(cid=101, in_reply_to_id=100),
            self._make_review_comment(cid=200),
            self._make_review_comment(cid=300),
        ]
        pr_data = self._make_pr_data()
        # Page 1: one thread with TWO comments (root + reply)
        gql_page1 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": True,
                                "endCursor": "cursor_abc",
                            },
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {"nodes": [
                                        {"id": "PRC_1", "databaseId": 100},
                                        {"id": "PRC_1r", "databaseId": 101},
                                    ]},
                                },
                            ],
                        },
                    },
                },
            },
        }
        # Page 2: threads for cid=200 and 300, hasNextPage=false
        gql_page2 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": "cursor_def",
                            },
                            "nodes": [
                                {
                                    "isResolved": False,
                                    "comments": {"nodes": [
                                        {"id": "PRC_2", "databaseId": 200},
                                    ]},
                                },
                                {
                                    "isResolved": True,
                                    "comments": {"nodes": [
                                        {"id": "PRC_3", "databaseId": 300},
                                    ]},
                                },
                            ],
                        },
                    },
                },
            },
        }

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
            # GraphQL page 1
            subprocess.CompletedProcess(
                [], 0, json.dumps(gql_page1), "",
            ),
            # GraphQL page 2
            subprocess.CompletedProcess(
                [], 0, json.dumps(gql_page2), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                "--include-review-threads",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 4)
        # cid=100 (root) from page 1: resolved
        self.assertTrue(output[0]["is_resolved"])
        # cid=101 (reply in same thread) from page 1: also resolved
        self.assertTrue(output[1]["is_resolved"])
        # cid=200 from page 2: not resolved
        self.assertFalse(output[2]["is_resolved"])
        # cid=300 from page 2: resolved
        self.assertTrue(output[3]["is_resolved"])

        # Verify 4 _run calls: review comments, pr view, gql page1, gql page2
        self.assertEqual(mock_run.call_count, 4)
        # Verify the second GraphQL call includes the cursor
        gql_call2_args = mock_run.call_args_list[3][0][0]
        self.assertIn("cursor=cursor_abc", " ".join(gql_call2_args))

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_review_threads_graphql_failure(
        self, mock_run: mock.Mock,
    ) -> None:
        """GraphQL failure is non-fatal; comments returned without is_resolved."""
        review_comments = [self._make_review_comment(cid=100)]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
            # GraphQL fails
            subprocess.CompletedProcess([], 1, "", "auth error"),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
                "--include-review-threads",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 1)
        self.assertNotIn("is_resolved", output[0])

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_review_comments_failure(
        self, mock_run: mock.Mock,
    ) -> None:
        """gh api failure for review comments exits with code 1."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], 1, "", "Not Found",
        )
        with self.assertRaises(SystemExit) as ctx:
            pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])
        self.assertEqual(ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_pr_view_failure(self, mock_run: mock.Mock) -> None:
        """gh pr view failure exits with code 1."""
        mock_run.side_effect = [
            # Review comments OK
            subprocess.CompletedProcess([], 0, "[]", ""),
            # gh pr view fails
            subprocess.CompletedProcess([], 1, "", "repo not found"),
        ]
        with self.assertRaises(SystemExit) as ctx:
            pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])
        self.assertEqual(ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_empty_results(self, mock_run: mock.Mock) -> None:
        """No comments returns an empty JSON array."""
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess(
                [], 0, json.dumps(self._make_pr_data()), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output, [])

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_in_reply_to_id(self, mock_run: mock.Mock) -> None:
        """Reply comments include in_reply_to_id field."""
        review_comments = [
            self._make_review_comment(cid=100),
            self._make_review_comment(cid=101, in_reply_to_id=100),
        ]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([review_comments]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertIsNone(output[0]["in_reply_to_id"])
        self.assertEqual(output[1]["in_reply_to_id"], 100)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_multipage_slurp(self, mock_run: mock.Mock) -> None:
        """--slurp with multiple pages flattens array-of-arrays."""
        page1 = [self._make_review_comment(cid=1)]
        page2 = [self._make_review_comment(cid=2)]
        page3 = [self._make_review_comment(cid=3)]
        # --slurp produces [[page1], [page2], [page3]]
        slurped = [page1, page2, page3]
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps(slurped), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 3)
        self.assertEqual([c["id"] for c in output], [1, 2, 3])

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_top_level_comment_url_fallback(
        self, mock_run: mock.Mock,
    ) -> None:
        """Top-level comment falls back to pr_url when comment has no url."""
        pr_data = self._make_pr_data(
            comments=[{
                "id": "IC_1",
                "author": {"login": "user1"},
                "body": "No url field",
                "createdAt": "2025-06-01T00:00:00Z",
            }],
            url="https://github.com/acme/proj/pull/1",
        )

        mock_run.side_effect = [
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        # Falls back to PR-level URL
        self.assertEqual(
            output[0]["url"], "https://github.com/acme/proj/pull/1",
        )

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_timeout_returns_failure(self, mock_run: mock.Mock) -> None:
        """Timeout during gh api call returns a failure result."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], -1, "", "Command timed out after 120s: gh api ...",
        )
        with self.assertRaises(SystemExit) as ctx:
            pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])
        self.assertEqual(ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR)

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_null_author_handled(self, mock_run: mock.Mock) -> None:
        """Null/missing author objects produce empty string instead of crashing."""
        # Review comment with user: null (e.g. bot or deleted account)
        rc_null_user = {
            "id": 100,
            "user": None,
            "body": "Bot comment",
            "created_at": "2025-06-01T10:00:00Z",
            "path": "src/main.py",
            "line": 1,
            "html_url": "https://github.com/acme/proj/pull/1#r100",
        }
        # Review comment with no user key at all
        rc_missing_user = {
            "id": 101,
            "body": "No user key",
            "created_at": "2025-06-01T10:00:00Z",
            "path": "src/main.py",
            "line": 2,
            "html_url": "https://github.com/acme/proj/pull/1#r101",
        }
        pr_data = self._make_pr_data(
            comments=[{
                "id": "IC_200",
                "author": None,
                "body": "Top-level with null author",
                "createdAt": "2025-06-02T12:00:00Z",
            }],
            reviews=[{
                "id": "RV_300",
                "body": "Review with missing author key",
                "submittedAt": "2025-06-02T14:00:00Z",
            }],
        )

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0, json.dumps([[rc_null_user, rc_missing_user]]), "",
            ),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(len(output), 4)
        # All should have author = "" (empty string)
        for comment in output:
            self.assertEqual(comment["author"], "")

    @mock.patch.object(pr_comments, "_run")
    def test_fetch_original_line_fallback(self, mock_run: mock.Mock) -> None:
        """Uses original_line when line is null."""
        rc = {
            "id": 100,
            "user": {"login": "reviewer"},
            "body": "Fix this",
            "created_at": "2025-06-01T10:00:00Z",
            "path": "src/main.py",
            "line": None,
            "original_line": 55,
            "html_url": "https://github.com/acme/proj/pull/1#r100",
        }
        pr_data = self._make_pr_data()

        mock_run.side_effect = [
            subprocess.CompletedProcess([], 0, json.dumps([[rc]]), ""),
            subprocess.CompletedProcess(
                [], 0, json.dumps(pr_data), "",
            ),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = pr_comments.main([
                "fetch", "--owner", "acme", "--repo", "proj", "--pr", "1",
            ])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertEqual(output[0]["line"], 55)


# ---------------------------------------------------------------------------
# Reply tests (with subprocess mocking)
# ---------------------------------------------------------------------------


class TestReply(unittest.TestCase):
    """Verify reply subcommand behaviour."""

    @mock.patch.object(pr_comments, "_run")
    def test_reply_inline(self, mock_run: mock.Mock) -> None:
        """Inline reply uses gh api with comment ID."""
        response = {
            "id": 501,
            "html_url": "https://github.com/acme/proj/pull/1#r501",
        }
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps(response), "",
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write("Thanks, fixed!")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = pr_comments.main([
                        "reply", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--body-file", f.name,
                        "--comment-id", "100",
                    ])

                self.assertEqual(code, 0)
                output = json.loads(buf.getvalue())
                self.assertEqual(output["comment_id"], 501)
                self.assertIn("r501", output["url"])

                # Verify gh api was called with correct endpoint
                call_args = mock_run.call_args[0][0]
                self.assertIn("gh", call_args)
                self.assertIn("api", call_args)
                self.assertIn(
                    "repos/acme/proj/pulls/1/comments/100/replies",
                    call_args,
                )
            finally:
                os.unlink(f.name)

    @mock.patch.object(pr_comments, "_run")
    def test_reply_top_level(self, mock_run: mock.Mock) -> None:
        """Top-level reply uses gh pr comment (no --comment-id)."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "https://github.com/acme/proj/pull/1#issuecomment-999\n",
            "",
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write("Overall feedback here.")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = pr_comments.main([
                        "reply", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--body-file", f.name,
                    ])

                self.assertEqual(code, 0)
                output = json.loads(buf.getvalue())
                self.assertIsNone(output["comment_id"])
                self.assertIn("issuecomment-999", output["url"])

                # Verify gh pr comment was called
                call_args = mock_run.call_args[0][0]
                self.assertIn("gh", call_args)
                self.assertIn("pr", call_args)
                self.assertIn("comment", call_args)
                self.assertIn("--body-file", call_args)
            finally:
                os.unlink(f.name)

    def test_reply_body_file_not_found(self) -> None:
        """Missing body file exits with code 1."""
        with self.assertRaises(SystemExit) as ctx:
            pr_comments.main([
                "reply", "--owner", "acme", "--repo", "proj",
                "--pr", "1", "--body-file", "/nonexistent/body.md",
            ])
        self.assertEqual(ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR)

    @mock.patch.object(pr_comments, "_run")
    def test_reply_gh_failure(self, mock_run: mock.Mock) -> None:
        """gh CLI failure exits with code 1."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], 1, "", "permission denied",
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write("body text")
            f.flush()
            try:
                with self.assertRaises(SystemExit) as ctx:
                    pr_comments.main([
                        "reply", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--body-file", f.name,
                    ])
                self.assertEqual(
                    ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR,
                )
            finally:
                os.unlink(f.name)

    @mock.patch.object(pr_comments, "_run")
    def test_reply_inline_empty_stdout(self, mock_run: mock.Mock) -> None:
        """Inline reply with empty stdout returns null fields."""
        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write("body")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = pr_comments.main([
                        "reply", "--owner", "acme", "--repo", "proj",
                        "--pr", "1", "--body-file", f.name,
                        "--comment-id", "100",
                    ])

                self.assertEqual(code, 0)
                output = json.loads(buf.getvalue())
                self.assertIsNone(output["comment_id"])
                self.assertEqual(output["url"], "")
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# Log tests
# ---------------------------------------------------------------------------


class TestLog(unittest.TestCase):
    """Verify log subcommand behaviour."""

    def test_log_creates_new_file(self) -> None:
        """Log creates the file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "responses.jsonl")
            code = pr_comments.main([
                "log", "--responses-log", log_path,
                "--comment-id", "42",
            ])
            self.assertEqual(code, 0)
            self.assertTrue(Path(log_path).is_file())

            lines = Path(log_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["comment_id"], "42")
            self.assertIn("timestamp", entry)
            self.assertEqual(entry["summary"], "")

    def test_log_appends_to_existing(self) -> None:
        """Log appends to an existing file without overwriting."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "responses.jsonl")

            # First entry
            pr_comments.main([
                "log", "--responses-log", log_path,
                "--comment-id", "10",
            ])
            # Second entry
            pr_comments.main([
                "log", "--responses-log", log_path,
                "--comment-id", "20",
                "--response-summary", "Addressed feedback",
            ])

            lines = Path(log_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

            e1 = json.loads(lines[0])
            e2 = json.loads(lines[1])
            self.assertEqual(e1["comment_id"], "10")
            self.assertEqual(e2["comment_id"], "20")
            self.assertEqual(e2["summary"], "Addressed feedback")

    def test_log_with_summary(self) -> None:
        """Log records the --response-summary value."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "responses.jsonl")
            pr_comments.main([
                "log", "--responses-log", log_path,
                "--comment-id", "99",
                "--response-summary", "Fixed the null check",
            ])

            entry = json.loads(
                Path(log_path).read_text(encoding="utf-8").strip(),
            )
            self.assertEqual(entry["summary"], "Fixed the null check")

    def test_log_creates_parent_directories(self) -> None:
        """Log creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "nested", "dir", "responses.jsonl")
            code = pr_comments.main([
                "log", "--responses-log", log_path,
                "--comment-id", "1",
            ])
            self.assertEqual(code, 0)
            self.assertTrue(Path(log_path).is_file())

    def test_log_timestamp_is_iso8601(self) -> None:
        """Log timestamp is a valid ISO 8601 string."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "responses.jsonl")
            pr_comments.main([
                "log", "--responses-log", log_path,
                "--comment-id", "1",
            ])

            entry = json.loads(
                Path(log_path).read_text(encoding="utf-8").strip(),
            )
            # Should not raise
            from datetime import datetime
            dt = datetime.fromisoformat(entry["timestamp"])
            self.assertIsNotNone(dt)

    def test_log_write_failure_exits_1(self) -> None:
        """OSError during file write exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "test-log.jsonl")
            with mock.patch("builtins.open", side_effect=OSError("disk full")):
                with self.assertRaises(SystemExit) as ctx:
                    pr_comments.main([
                        "log", "--responses-log", log_path,
                        "--comment-id", "42",
                    ])
                self.assertEqual(
                    ctx.exception.code, pr_comments.EXIT_RUNTIME_ERROR,
                )

    def test_log_write_failure_message(self) -> None:
        """OSError message includes the file path and OS error detail."""
        import io
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "log.jsonl")
            buf = io.StringIO()
            with mock.patch("sys.stderr", buf):
                with mock.patch(
                    "builtins.open",
                    side_effect=OSError("permission denied"),
                ):
                    with self.assertRaises(SystemExit):
                        pr_comments.main([
                            "log", "--responses-log", log_path,
                            "--comment-id", "42",
                        ])
            err = buf.getvalue()
            self.assertIn(log_path, err)
            self.assertIn("permission denied", err)

    def test_log_each_line_is_valid_json(self) -> None:
        """Each line in the log file is independently parseable as JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "responses.jsonl")
            for i in range(5):
                pr_comments.main([
                    "log", "--responses-log", log_path,
                    "--comment-id", str(i),
                ])

            lines = Path(log_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 5)
            for line in lines:
                entry = json.loads(line)
                self.assertIn("comment_id", entry)
                self.assertIn("timestamp", entry)
                self.assertIn("summary", entry)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    """Verify helper functions."""

    def test_emit_json_outputs_to_stdout(self) -> None:
        """_emit_json writes valid JSON to stdout."""
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            pr_comments._emit_json({"key": "value"})
        output = json.loads(buf.getvalue())
        self.assertEqual(output["key"], "value")

    def test_emit_json_list(self) -> None:
        """_emit_json handles list values."""
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            pr_comments._emit_json([1, 2, 3])
        output = json.loads(buf.getvalue())
        self.assertEqual(output, [1, 2, 3])

    def test_info_writes_to_stderr(self) -> None:
        """info() writes an INFO-prefixed message to stderr."""
        import io
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            pr_comments.info("test message")
        self.assertIn("INFO: test message", buf.getvalue())

    def test_fail_exits_with_code(self) -> None:
        """fail() exits with the specified code."""
        with self.assertRaises(SystemExit) as ctx:
            pr_comments.fail("something broke", code=1)
        self.assertEqual(ctx.exception.code, 1)

    def test_fail_writes_to_stderr(self) -> None:
        """fail() writes an ERROR-prefixed message to stderr."""
        import io
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            with self.assertRaises(SystemExit):
                pr_comments.fail("bad thing")
        self.assertIn("ERROR: bad thing", buf.getvalue())

    @mock.patch("subprocess.run")
    def test_run_timeout_returns_failure(self, mock_sub: mock.Mock) -> None:
        """_run catches TimeoutExpired and returns a synthetic failure."""
        mock_sub.side_effect = subprocess.TimeoutExpired(
            cmd=["gh", "api", "..."], timeout=120,
        )
        result = pr_comments._run(["gh", "api", "..."], timeout=120)
        self.assertEqual(result.returncode, -1)
        self.assertIn("timed out", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
