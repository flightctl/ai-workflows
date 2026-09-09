#!/usr/bin/env python3
"""Tests for _shared/scripts/publish.py."""

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

_SCRIPT = Path(__file__).resolve().parent / "publish.py"
_spec = importlib.util.spec_from_file_location("publish", _SCRIPT)
assert _spec and _spec.loader
publish = importlib.util.module_from_spec(_spec)
sys.modules["publish"] = publish
_spec.loader.exec_module(publish)


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Verify argparse configuration for each subcommand."""

    def test_preflight_defaults(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args(["preflight"])
        self.assertEqual(args.subcommand, "preflight")
        self.assertEqual(args.platform, "github")

    def test_preflight_gitlab(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args(["preflight", "--platform", "gitlab"])
        self.assertEqual(args.platform, "gitlab")

    def test_push_args(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args(["push", "--remote", "fork", "--branch", "feat/x"])
        self.assertEqual(args.subcommand, "push")
        self.assertEqual(args.remote, "fork")
        self.assertEqual(args.branch, "feat/x")

    def test_push_missing_remote(self) -> None:
        parser = publish.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["push", "--branch", "feat/x"])

    def test_check_existing_args(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "check-existing", "--repo", "acme/proj", "--head", "feat/x",
        ])
        self.assertEqual(args.subcommand, "check-existing")
        self.assertEqual(args.repo, "acme/proj")
        self.assertEqual(args.head, "feat/x")
        self.assertEqual(args.platform, "github")

    def test_check_existing_gitlab(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "check-existing", "--repo", "group/proj",
            "--head", "feat/x", "--platform", "gitlab",
        ])
        self.assertEqual(args.platform, "gitlab")

    def test_create_pr_args(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "create-pr", "--base", "main", "--head", "user:feat/x",
            "--title", "Fix bug", "--repo", "acme/proj",
        ])
        self.assertEqual(args.subcommand, "create-pr")
        self.assertEqual(args.base, "main")
        self.assertEqual(args.head, "user:feat/x")
        self.assertEqual(args.title, "Fix bug")
        self.assertTrue(args.draft)

    def test_create_pr_no_draft(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "create-pr", "--base", "main", "--head", "feat/x",
            "--title", "Fix", "--no-draft",
        ])
        self.assertFalse(args.draft)

    def test_create_mr_args(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "create-mr", "--source", "docs/fix", "--target", "main",
            "--title", "Update docs",
        ])
        self.assertEqual(args.subcommand, "create-mr")
        self.assertEqual(args.source, "docs/fix")
        self.assertEqual(args.target, "main")
        self.assertEqual(args.title, "Update docs")
        self.assertTrue(args.draft)

    def test_create_mr_no_draft(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "create-mr", "--source", "x", "--target", "main",
            "--title", "T", "--no-draft",
        ])
        self.assertFalse(args.draft)

    def test_save_metadata_args(self) -> None:
        parser = publish.build_parser()
        args = parser.parse_args([
            "save-metadata", "--file", "out.json",
            "key1=val1", "key2=val2",
        ])
        self.assertEqual(args.subcommand, "save-metadata")
        self.assertEqual(args.file, "out.json")
        self.assertEqual(args.pair, ["key1=val1", "key2=val2"])

    def test_no_subcommand(self) -> None:
        result = publish.main([])
        self.assertEqual(result, publish.EXIT_ARG_ERROR)


# ---------------------------------------------------------------------------
# save-metadata tests
# ---------------------------------------------------------------------------


class TestSaveMetadata(unittest.TestCase):
    """Verify save-metadata JSON output and edge cases."""

    def test_basic_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            code = publish.main([
                "save-metadata", "--file", out,
                "repo=acme/proj",
                "branch=feat/x",
            ])
            self.assertEqual(code, 0)
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(data["repo"], "acme/proj")
            self.assertEqual(data["branch"], "feat/x")

    def test_keys_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "z_key=last",
                "a_key=first",
                "m_key=middle",
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            keys = list(data.keys())
            self.assertEqual(keys, ["a_key", "m_key", "z_key"])

    def test_newlines_in_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "body=line1\nline2\nline3",
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(data["body"], "line1\nline2\nline3")

    def test_quotes_and_backslashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                'msg=He said "hello\\world"',
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(data["msg"], 'He said "hello\\world"')

    def test_control_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "tab=a\tb",
                "cr=a\rb",
            ])
            raw = Path(out).read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertEqual(data["tab"], "a\tb")
            self.assertEqual(data["cr"], "a\rb")

    def test_leading_zero_strings(self) -> None:
        """Values with leading zeros must remain strings, not become integers."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "pr_number=007",
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertIsInstance(data["pr_number"], str)
            self.assertEqual(data["pr_number"], "007")

    def test_unicode_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "name=Renée",
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "Renée")

    def test_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "nested", "dir", "meta.json")
            code = publish.main([
                "save-metadata", "--file", out,
                "key=val",
            ])
            self.assertEqual(code, 0)
            self.assertTrue(Path(out).is_file())

    def test_no_pairs_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            with self.assertRaises(SystemExit) as ctx:
                publish.main(["save-metadata", "--file", out])
            self.assertEqual(ctx.exception.code, publish.EXIT_ARG_ERROR)

    def test_invalid_pair_format_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            with self.assertRaises(SystemExit) as ctx:
                publish.main([
                    "save-metadata", "--file", out,
                    "noequalssign",
                ])
            self.assertEqual(ctx.exception.code, publish.EXIT_ARG_ERROR)

    def test_empty_value_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "empty=",
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(data["empty"], "")

    def test_value_with_equals(self) -> None:
        """Values containing '=' should work (only first '=' is the delimiter)."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "meta.json")
            publish.main([
                "save-metadata", "--file", out,
                "url=https://example.com?a=1&b=2",
            ])
            data = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(data["url"], "https://example.com?a=1&b=2")


# ---------------------------------------------------------------------------
# Exit code contract tests
# ---------------------------------------------------------------------------


class TestExitCodes(unittest.TestCase):
    """Verify the documented exit code contract."""

    def test_exit_code_constants(self) -> None:
        self.assertEqual(publish.EXIT_SUCCESS, 0)
        self.assertEqual(publish.EXIT_ARG_ERROR, 1)
        self.assertEqual(publish.EXIT_PUSH_FAIL, 3)
        self.assertEqual(publish.EXIT_CREATE_FAIL, 4)
        self.assertEqual(publish.EXIT_EXISTING_FOUND, 5)

    def test_push_missing_remote_exits_1(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            publish.main(["push", "--remote", "", "--branch", "x"])
        self.assertEqual(ctx.exception.code, publish.EXIT_ARG_ERROR)

    def test_push_missing_branch_exits_1(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            publish.main(["push", "--remote", "origin", "--branch", ""])
        self.assertEqual(ctx.exception.code, publish.EXIT_ARG_ERROR)

    @mock.patch.object(publish, "run")
    def test_push_nonexistent_remote_exits_3(self, mock_run: mock.Mock) -> None:
        # git remote get-url fails
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 1, "", ""),  # git remote get-url
            subprocess.CompletedProcess([], 0, "", ""),  # git remote (listing)
        ]
        with self.assertRaises(SystemExit) as ctx:
            publish.main(["push", "--remote", "nope", "--branch", "x"])
        self.assertEqual(ctx.exception.code, publish.EXIT_PUSH_FAIL)

    def test_create_pr_missing_base_exits_2(self) -> None:
        """argparse exits with code 2 when required args are missing."""
        with self.assertRaises(SystemExit) as ctx:
            publish.main(["create-pr", "--head", "x", "--title", "T"])
        self.assertEqual(ctx.exception.code, 2)

    @mock.patch.object(publish, "run")
    def test_create_pr_failure_exits_4(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 1, "", "Resource not accessible",
        )
        with self.assertRaises(SystemExit) as ctx:
            publish.main([
                "create-pr", "--base", "main", "--head", "feat/x",
                "--title", "Fix bug",
            ])
        self.assertEqual(ctx.exception.code, publish.EXIT_CREATE_FAIL)


# ---------------------------------------------------------------------------
# Preflight tests (with subprocess mocking)
# ---------------------------------------------------------------------------


class TestPreflight(unittest.TestCase):
    """Verify preflight JSON output structure."""

    @mock.patch.object(publish, "run")
    def test_preflight_github_authenticated(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = [
            # gh auth status
            subprocess.CompletedProcess([], 0, "", ""),
            # gh api user --jq .login
            subprocess.CompletedProcess([], 0, "jsmith\n", ""),
            # git branch --show-current
            subprocess.CompletedProcess([], 0, "feat/x\n", ""),
            # git remote
            subprocess.CompletedProcess([], 0, "origin\nfork\n", ""),
            # git diff --quiet
            subprocess.CompletedProcess([], 1, "", ""),
            # git diff --cached --quiet
            subprocess.CompletedProcess([], 0, "", ""),
            # git ls-files --others
            subprocess.CompletedProcess([], 0, "", ""),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main(["preflight"])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertTrue(output["auth_ok"])
        self.assertEqual(output["auth_user"], "jsmith")
        self.assertEqual(output["branch"], "feat/x")
        self.assertEqual(output["remote"], "fork")
        self.assertTrue(output["has_uncommitted"])
        self.assertFalse(output["has_staged"])
        self.assertFalse(output["has_untracked"])
        self.assertEqual(output["platform"], "github")

    @mock.patch.object(publish, "run")
    def test_preflight_not_authenticated(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = [
            # gh auth status -> fail
            subprocess.CompletedProcess([], 1, "", ""),
            # git branch --show-current
            subprocess.CompletedProcess([], 0, "main\n", ""),
            # git remote
            subprocess.CompletedProcess([], 0, "origin\n", ""),
            # git diff --quiet
            subprocess.CompletedProcess([], 0, "", ""),
            # git diff --cached --quiet
            subprocess.CompletedProcess([], 0, "", ""),
            # git ls-files --others
            subprocess.CompletedProcess([], 0, "newfile.txt\n", ""),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main(["preflight"])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertFalse(output["auth_ok"])
        self.assertEqual(output["auth_user"], "")
        self.assertTrue(output["has_untracked"])
        self.assertEqual(output["remote"], "origin")

    @mock.patch.object(publish, "run")
    def test_preflight_gitlab(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = [
            # glab auth status
            subprocess.CompletedProcess([], 0, "", ""),
            # glab api user --jq .username
            subprocess.CompletedProcess([], 0, "gluser\n", ""),
            # git branch --show-current
            subprocess.CompletedProcess([], 0, "docs/fix\n", ""),
            # git remote
            subprocess.CompletedProcess([], 0, "origin\n", ""),
            # git diff --quiet
            subprocess.CompletedProcess([], 0, "", ""),
            # git diff --cached --quiet
            subprocess.CompletedProcess([], 0, "", ""),
            # git ls-files --others
            subprocess.CompletedProcess([], 0, "", ""),
        ]

        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main(["preflight", "--platform", "gitlab"])

        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertTrue(output["auth_ok"])
        self.assertEqual(output["auth_user"], "gluser")
        self.assertEqual(output["platform"], "gitlab")


# ---------------------------------------------------------------------------
# check-existing tests (with subprocess mocking)
# ---------------------------------------------------------------------------


class TestCheckExisting(unittest.TestCase):
    """Verify check-existing behavior for both platforms."""

    @mock.patch.object(publish, "run")
    def test_github_no_existing_pr(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "[]", "",
        )
        code = publish.main([
            "check-existing", "--repo", "acme/proj", "--head", "feat/x",
        ])
        self.assertEqual(code, publish.EXIT_SUCCESS)

    @mock.patch.object(publish, "run")
    def test_github_existing_pr_exits_5(self, mock_run: mock.Mock) -> None:
        pr_data = [{"number": 42, "url": "https://github.com/acme/proj/pull/42"}]
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps(pr_data), "",
        )
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main([
                "check-existing", "--repo", "acme/proj", "--head", "feat/x",
            ])
        self.assertEqual(code, publish.EXIT_EXISTING_FOUND)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["number"], 42)

    @mock.patch.object(publish, "run")
    def test_github_fork_owner_filter(self, mock_run: mock.Mock) -> None:
        """Fork-aware check: filters by headRepositoryOwner."""
        pr_data = [
            {
                "number": 10,
                "url": "https://github.com/acme/proj/pull/10",
                "headRepositoryOwner": {"login": "other-user"},
            },
            {
                "number": 20,
                "url": "https://github.com/acme/proj/pull/20",
                "headRepositoryOwner": {"login": "jsmith"},
            },
        ]
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps(pr_data), "",
        )
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main([
                "check-existing", "--repo", "acme/proj",
                "--head", "jsmith:feat/x",
            ])
        self.assertEqual(code, publish.EXIT_EXISTING_FOUND)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["number"], 20)

    @mock.patch.object(publish, "run")
    def test_github_fork_no_match(self, mock_run: mock.Mock) -> None:
        """Fork-aware check: no matching owner exits 0."""
        pr_data = [
            {
                "number": 10,
                "url": "https://github.com/acme/proj/pull/10",
                "headRepositoryOwner": {"login": "other-user"},
            },
        ]
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps(pr_data), "",
        )
        code = publish.main([
            "check-existing", "--repo", "acme/proj",
            "--head", "jsmith:feat/x",
        ])
        self.assertEqual(code, publish.EXIT_SUCCESS)

    @mock.patch.object(publish, "run")
    def test_gitlab_existing_mr_exits_5(self, mock_run: mock.Mock) -> None:
        mr_data = [{"iid": 7, "web_url": "https://gitlab.com/grp/proj/-/merge_requests/7"}]
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps(mr_data), "",
        )
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main([
                "check-existing", "--repo", "grp/proj",
                "--head", "feat/x", "--platform", "gitlab",
            ])
        self.assertEqual(code, publish.EXIT_EXISTING_FOUND)

    @mock.patch.object(publish, "run")
    def test_gitlab_fork_filter_by_project_id(self, mock_run: mock.Mock) -> None:
        """Fork-aware GitLab: filters by source_project_id."""
        mr_data = [
            {"iid": 1, "source_project_id": 100},
            {"iid": 2, "source_project_id": 200},
        ]
        mock_run.side_effect = [
            # glab mr list
            subprocess.CompletedProcess([], 0, json.dumps(mr_data), ""),
            # glab api projects/...
            subprocess.CompletedProcess([], 0, "200\n", ""),
        ]
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = publish.main([
                "check-existing", "--repo", "grp/proj",
                "--head", "jsmith/proj:feat/x", "--platform", "gitlab",
            ])
        self.assertEqual(code, publish.EXIT_EXISTING_FOUND)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["iid"], 2)


# ---------------------------------------------------------------------------
# JSON encoding edge case tests
# ---------------------------------------------------------------------------


class TestJSONEncoding(unittest.TestCase):
    """Verify json.dumps handles the edge cases that motivated the rewrite."""

    def test_newlines_roundtrip(self) -> None:
        data = {"body": "line1\nline2\nline3"}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertEqual(parsed["body"], "line1\nline2\nline3")

    def test_quotes_roundtrip(self) -> None:
        data = {"msg": 'He said "hello"'}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertEqual(parsed["msg"], 'He said "hello"')

    def test_backslash_roundtrip(self) -> None:
        data = {"path": "C:\\Users\\test"}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertEqual(parsed["path"], "C:\\Users\\test")

    def test_control_chars_roundtrip(self) -> None:
        data = {"tab": "a\tb", "cr": "x\ry", "null": "a\x00b"}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertEqual(parsed["tab"], "a\tb")
        self.assertEqual(parsed["cr"], "x\ry")
        self.assertEqual(parsed["null"], "a\x00b")

    def test_leading_zero_string_preserved(self) -> None:
        """The whole point: '007' stays '007', not 7."""
        data = {"pr_number": "007"}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertIsInstance(parsed["pr_number"], str)
        self.assertEqual(parsed["pr_number"], "007")

    def test_unicode_preserved(self) -> None:
        data = {"emoji": "\U0001f600", "accent": "café"}
        raw = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(raw)
        self.assertEqual(parsed["emoji"], "\U0001f600")
        self.assertEqual(parsed["accent"], "café")

    def test_empty_string_value(self) -> None:
        data = {"empty": ""}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertEqual(parsed["empty"], "")

    def test_mixed_special_chars(self) -> None:
        """Combo: newlines + quotes + backslashes in one value."""
        val = 'line1\n"quoted"\npath\\to\\file'
        data = {"complex": val}
        raw = json.dumps(data)
        parsed = json.loads(raw)
        self.assertEqual(parsed["complex"], val)


# ---------------------------------------------------------------------------
# create-pr / create-mr argument validation
# ---------------------------------------------------------------------------


class TestCreatePRValidation(unittest.TestCase):
    """Verify create-pr argument validation."""

    def test_body_file_not_found(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            publish.main([
                "create-pr", "--base", "main", "--head", "feat/x",
                "--title", "Fix", "--body-file", "/nonexistent/file.md",
            ])
        self.assertEqual(ctx.exception.code, publish.EXIT_ARG_ERROR)

    @mock.patch.object(publish, "run")
    def test_body_file_used(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "https://github.com/acme/proj/pull/1\n", "",
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("PR body content")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = publish.main([
                        "create-pr", "--base", "main", "--head", "feat/x",
                        "--title", "Fix", "--body-file", f.name,
                    ])
                self.assertEqual(code, 0)
                # Verify --body-file was in the command
                call_args = mock_run.call_args[0][0]
                self.assertIn("--body-file", call_args)
                self.assertIn(f.name, call_args)
            finally:
                os.unlink(f.name)

    @mock.patch.object(publish, "run")
    def test_inline_body_used(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "https://github.com/acme/proj/pull/1\n", "",
        )
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            publish.main([
                "create-pr", "--base", "main", "--head", "feat/x",
                "--title", "Fix", "--body", "Inline body text",
            ])
        call_args = mock_run.call_args[0][0]
        self.assertIn("--body", call_args)
        idx = call_args.index("--body")
        self.assertEqual(call_args[idx + 1], "Inline body text")

    @mock.patch.object(publish, "run")
    def test_empty_body_default(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "https://github.com/acme/proj/pull/1\n", "",
        )
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            publish.main([
                "create-pr", "--base", "main", "--head", "feat/x",
                "--title", "Fix",
            ])
        call_args = mock_run.call_args[0][0]
        self.assertIn("--body", call_args)
        idx = call_args.index("--body")
        self.assertEqual(call_args[idx + 1], "")

    @mock.patch.object(publish, "run")
    def test_labels_passed(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "https://github.com/acme/proj/pull/1\n", "",
        )
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            publish.main([
                "create-pr", "--base", "main", "--head", "feat/x",
                "--title", "Fix", "--labels", "bug,urgent",
            ])
        call_args = mock_run.call_args[0][0]
        self.assertIn("--label", call_args)
        idx = call_args.index("--label")
        self.assertEqual(call_args[idx + 1], "bug,urgent")


class TestCreateMRValidation(unittest.TestCase):
    """Verify create-mr argument validation."""

    def test_desc_file_not_found(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            publish.main([
                "create-mr", "--source", "x", "--target", "main",
                "--title", "T", "--desc-file", "/nonexistent/file.md",
            ])
        self.assertEqual(ctx.exception.code, publish.EXIT_ARG_ERROR)

    @mock.patch.object(publish, "run")
    def test_desc_file_read(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, "https://gitlab.com/grp/proj/-/merge_requests/1\n", "",
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("MR description from file")
            f.flush()
            try:
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    publish.main([
                        "create-mr", "--source", "docs/fix",
                        "--target", "main", "--title", "Docs update",
                        "--desc-file", f.name,
                    ])
                call_args = mock_run.call_args[0][0]
                self.assertIn("--description", call_args)
                idx = call_args.index("--description")
                self.assertEqual(call_args[idx + 1], "MR description from file")
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# Push tests (with subprocess mocking)
# ---------------------------------------------------------------------------


class TestPush(unittest.TestCase):
    """Verify push behavior."""

    @mock.patch.object(publish, "run")
    def test_push_success(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = [
            # git remote get-url -> success
            subprocess.CompletedProcess([], 0, "https://github.com/user/repo.git\n", ""),
            # git push -u -> success
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        code = publish.main(["push", "--remote", "fork", "--branch", "feat/x"])
        self.assertEqual(code, 0)

    @mock.patch.object(publish, "run")
    def test_push_failure_exits_3(self, mock_run: mock.Mock) -> None:
        mock_run.side_effect = [
            # git remote get-url -> success
            subprocess.CompletedProcess([], 0, "https://github.com/user/repo.git\n", ""),
            # git push -u -> failure
            subprocess.CompletedProcess([], 128, "", "permission denied"),
        ]
        with self.assertRaises(SystemExit) as ctx:
            publish.main(["push", "--remote", "fork", "--branch", "feat/x"])
        self.assertEqual(ctx.exception.code, publish.EXIT_PUSH_FAIL)


if __name__ == "__main__":
    unittest.main()
