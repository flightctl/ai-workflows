#!/usr/bin/env python3
"""Tests for _shared/scripts/resolve-phase.py."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent / "resolve-phase.py"
_spec = importlib.util.spec_from_file_location("resolve_phase", _SCRIPT)
assert _spec and _spec.loader
resolve_phase = importlib.util.module_from_spec(_spec)
sys.modules["resolve_phase"] = resolve_phase
_spec.loader.exec_module(resolve_phase)


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Verify argparse configuration."""

    def test_basic_args(self) -> None:
        """Positional arguments are parsed correctly."""
        parser = resolve_phase.build_parser()
        args = parser.parse_args(["bugfix", "assess.md"])
        self.assertEqual(args.workflow, "bugfix")
        self.assertEqual(args.phase_file, "assess.md")

    def test_workflow_with_hyphens(self) -> None:
        """Workflow names with hyphens are parsed correctly."""
        parser = resolve_phase.build_parser()
        args = parser.parse_args(["docs-writer", "gather-context.md"])
        self.assertEqual(args.workflow, "docs-writer")
        self.assertEqual(args.phase_file, "gather-context.md")

    def test_missing_workflow(self) -> None:
        """Missing workflow argument exits with code 2."""
        parser = resolve_phase.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args([])
        self.assertEqual(ctx.exception.code, 2)

    def test_missing_phase_file(self) -> None:
        """Missing phase_file argument exits with code 2."""
        parser = resolve_phase.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["bugfix"])
        self.assertEqual(ctx.exception.code, 2)

    def test_extra_args_rejected(self) -> None:
        """Extra positional arguments are rejected."""
        parser = resolve_phase.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["bugfix", "assess.md", "extra"])
        self.assertEqual(ctx.exception.code, 2)


# ---------------------------------------------------------------------------
# Exit code contract tests
# ---------------------------------------------------------------------------


class TestExitCodes(unittest.TestCase):
    """Verify the documented exit code contract."""

    def test_exit_code_constants(self) -> None:
        """Exit code constants match the documented contract."""
        self.assertEqual(resolve_phase.EXIT_SUCCESS, 0)
        self.assertEqual(resolve_phase.EXIT_RESOLUTION_ERROR, 1)


# ---------------------------------------------------------------------------
# Resolution logic tests
# ---------------------------------------------------------------------------


class TestResolvePhaseOverride(unittest.TestCase):
    """Verify override detection: .workflows/{WORKFLOW}/skills/{PHASE_FILE}."""

    def test_override_found(self) -> None:
        """When an override file exists, its path is returned."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create the override file
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            override_file = override_dir / "assess.md"
            override_file.write_text("# Custom assess phase\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    result,
                    str(Path(".workflows") / "bugfix" / "skills" / "assess.md"),
                )
            finally:
                os.chdir(original_cwd)

    def test_override_info_message(self) -> None:
        """Override resolution prints an INFO message to stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "design" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "draft.md").write_text("# Custom\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf):
                    resolve_phase.resolve_phase("design", "draft.md")
                self.assertIn(
                    "Using project override: design/draft.md",
                    buf.getvalue(),
                )
            finally:
                os.chdir(original_cwd)

    def test_no_override_directory(self) -> None:
        """When .workflows/ does not exist, falls back to built-in."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                # resolve_phase will look for a built-in; mock is_file
                # to verify it falls through the override check
                with (
                    mock.patch.object(
                        Path, "is_file",
                        side_effect=lambda self=None: (  # type: ignore[assignment]
                            False  # override doesn't exist
                        ),
                    ),
                    self.assertRaises(SystemExit),
                ):
                    resolve_phase.resolve_phase("bugfix", "assess.md")
            finally:
                os.chdir(original_cwd)


class TestResolvePhaseBuiltin(unittest.TestCase):
    """Verify built-in fallback resolution."""

    def test_builtin_fallback(self) -> None:
        """When no override exists, the built-in path is returned."""
        # The script lives at _shared/scripts/resolve-phase.py
        # Built-in phases are at {repo_root}/{workflow}/skills/{phase_file}
        # Use a real workflow/phase that exists in the repo
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent.parent

        # Verify a known built-in exists (bugfix/skills/assess.md)
        builtin = repo_root / "bugfix" / "skills" / "assess.md"
        self.assertTrue(
            builtin.is_file(),
            f"Expected built-in at {builtin}",
        )

        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(result, str(builtin))
            finally:
                os.chdir(original_cwd)

    def test_builtin_not_found_exits_1(self) -> None:
        """Missing built-in phase exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.resolve_phase(
                        "nonexistent-workflow", "nonexistent.md",
                    )
                self.assertEqual(
                    ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_builtin_error_message(self) -> None:
        """Missing built-in prints an ERROR message with the phase path."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with (
                    mock.patch("sys.stderr", buf),
                    self.assertRaises(SystemExit),
                ):
                    resolve_phase.resolve_phase("nope", "nope.md")
                err = buf.getvalue()
                self.assertIn("ERROR:", err)
                self.assertIn("nope/skills/nope.md", err)
            finally:
                os.chdir(original_cwd)


class TestResolvePhaseOverridePriority(unittest.TestCase):
    """Verify that override takes priority over built-in."""

    def test_override_preferred_over_builtin(self) -> None:
        """Override path is returned even when built-in also exists."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create the override file
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                # Should return the override, not the built-in
                self.assertTrue(
                    result.startswith(".workflows"),
                    f"Expected override path, got: {result}",
                )
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Path traversal protection tests
# ---------------------------------------------------------------------------


class TestPathTraversal(unittest.TestCase):
    """Verify path traversal and unsafe input rejection."""

    def test_workflow_dotdot_rejected(self) -> None:
        """Workflow containing '..' is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("../etc", "passwd")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_phase_file_dotdot_rejected(self) -> None:
        """Phase file containing '..' is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("bugfix", "../../etc/passwd")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_absolute_workflow_rejected(self) -> None:
        """Absolute path as workflow is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("/etc", "passwd")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_absolute_phase_file_rejected(self) -> None:
        """Absolute path as phase_file is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("bugfix", "/etc/passwd")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_workflow_with_slash_rejected(self) -> None:
        """Workflow containing '/' is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("a/b", "phase.md")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_phase_with_slash_rejected(self) -> None:
        """Phase file containing '/' is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("bugfix", "a/b.md")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_backslash_rejected(self) -> None:
        """Backslash in path component is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("bugfix", "a\\b.md")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_empty_workflow_rejected(self) -> None:
        """Empty workflow is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("", "phase.md")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_empty_phase_file_rejected(self) -> None:
        """Empty phase_file is rejected."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.resolve_phase("bugfix", "")
        self.assertEqual(
            ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
        )

    def test_safe_names_accepted(self) -> None:
        """Valid workflow/phase names with hyphens, dots pass validation.

        Uses a real workflow (docs-writer) with a real phase file to
        verify the path validation passes and resolution succeeds.
        """
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                # docs-writer/skills/gather-context.md is a real built-in
                result = resolve_phase.resolve_phase(
                    "docs-writer", "gather-context.md",
                )
                self.assertIn("docs-writer", result)
                self.assertIn("gather-context.md", result)
            finally:
                os.chdir(original_cwd)

    def test_nonexistent_safe_name_fails_with_resolution_error(self) -> None:
        """Safe but nonexistent names fail with resolution, not validation."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.resolve_phase(
                        "not-a-workflow", "not-a-phase.md",
                    )
                # Should fail with resolution error (not found), proving
                # that validation passed
                self.assertEqual(
                    ctx.exception.code,
                    resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_traversal_error_message(self) -> None:
        """Path traversal error includes the offending value."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf), self.assertRaises(SystemExit):
            resolve_phase.resolve_phase("../etc", "passwd")
        self.assertIn("..", buf.getvalue())


# ---------------------------------------------------------------------------
# Built-in content validation tests
# ---------------------------------------------------------------------------


class TestBuiltinContentValidation(unittest.TestCase):
    """Verify built-in file is readable and non-empty."""

    @staticmethod
    def _builtin_only_is_file(path: Path) -> bool:
        """Return True only for built-in paths, False for overrides.

        This lets the override check fall through to the built-in path.
        """
        return ".workflows" not in str(path)

    def test_empty_builtin_rejected(self) -> None:
        """Empty built-in file exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with (
                    mock.patch.object(
                        Path, "is_file", self._builtin_only_is_file,
                    ),
                    mock.patch.object(
                        Path, "read_text", return_value="   \n  \n",
                    ),
                    self.assertRaises(SystemExit) as ctx,
                ):
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    ctx.exception.code,
                    resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_empty_builtin_error_message(self) -> None:
        """Empty built-in includes the phase path in the error."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with (
                    mock.patch("sys.stderr", buf),
                    mock.patch.object(
                        Path, "is_file", self._builtin_only_is_file,
                    ),
                    mock.patch.object(
                        Path, "read_text", return_value="",
                    ),
                    self.assertRaises(SystemExit),
                ):
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                err = buf.getvalue()
                self.assertIn("empty", err)
                self.assertIn("bugfix/skills/assess.md", err)
            finally:
                os.chdir(original_cwd)

    def test_unreadable_builtin_rejected(self) -> None:
        """Unreadable built-in file exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with (
                    mock.patch.object(
                        Path, "is_file", self._builtin_only_is_file,
                    ),
                    mock.patch.object(
                        Path, "read_text",
                        side_effect=OSError("permission denied"),
                    ),
                    self.assertRaises(SystemExit) as ctx,
                ):
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    ctx.exception.code,
                    resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_unreadable_error_message(self) -> None:
        """Unreadable built-in includes the OS error in the message."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with (
                    mock.patch("sys.stderr", buf),
                    mock.patch.object(
                        Path, "is_file", self._builtin_only_is_file,
                    ),
                    mock.patch.object(
                        Path, "read_text",
                        side_effect=OSError("permission denied"),
                    ),
                    self.assertRaises(SystemExit),
                ):
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                err = buf.getvalue()
                self.assertIn("permission denied", err)
                self.assertIn("not readable", err)
            finally:
                os.chdir(original_cwd)

    def test_valid_builtin_accepted(self) -> None:
        """Non-empty readable built-in is accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertIn("bugfix", result)
                self.assertIn("assess.md", result)
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Symlink escape protection tests
# ---------------------------------------------------------------------------


class TestSymlinkEscape(unittest.TestCase):
    """Verify symlinks in override paths cannot escape the project root."""

    def test_file_symlink_escape_rejected(self) -> None:
        """Override file that is a symlink pointing outside project is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create an external file outside the project
            external_dir = Path(tmp) / "external"
            external_dir.mkdir()
            external_file = external_dir / "malicious.md"
            external_file.write_text("# Evil override\n")

            # Create the project directory and override as a symlink
            project = Path(tmp) / "project"
            project.mkdir()
            override_dir = project / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            symlink = override_dir / "assess.md"
            symlink.symlink_to(external_file)

            original_cwd = os.getcwd()
            try:
                os.chdir(project)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    ctx.exception.code,
                    resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_parent_dir_symlink_escape_rejected(self) -> None:
        """Override directory symlink pointing outside project is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create an external skills directory outside the project
            external_skills = Path(tmp) / "external" / "skills"
            external_skills.mkdir(parents=True)
            (external_skills / "assess.md").write_text("# Evil\n")

            # Create project with .workflows/bugfix as a symlink
            project = Path(tmp) / "project"
            project.mkdir()
            workflows_dir = project / ".workflows"
            workflows_dir.mkdir()
            # bugfix symlink -> external directory that has skills/assess.md
            bugfix_link = workflows_dir / "bugfix"
            bugfix_link.symlink_to(Path(tmp) / "external")

            original_cwd = os.getcwd()
            try:
                os.chdir(project)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    ctx.exception.code,
                    resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_symlink_escape_error_message(self) -> None:
        """Symlink escape error includes the phase path."""
        with tempfile.TemporaryDirectory() as tmp:
            external_file = Path(tmp) / "external.md"
            external_file.write_text("# Evil\n")

            project = Path(tmp) / "project"
            project.mkdir()
            override_dir = project / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").symlink_to(external_file)

            original_cwd = os.getcwd()
            try:
                os.chdir(project)
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf), self.assertRaises(SystemExit):
                    resolve_phase.resolve_phase("bugfix", "assess.md")
                err = buf.getvalue()
                self.assertIn("escapes project boundary", err)
                self.assertIn("bugfix/assess.md", err)
            finally:
                os.chdir(original_cwd)

    def test_valid_symlink_within_project_accepted(self) -> None:
        """Override symlink pointing within the project root is accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a real override file in the project
            project = Path(tmp) / "project"
            project.mkdir()
            real_dir = project / ".workflows" / "bugfix" / "skills"
            real_dir.mkdir(parents=True)
            real_file = real_dir / "real-assess.md"
            real_file.write_text("# Valid override\n")

            # Create a symlink to the real file (within same dir)
            symlink = real_dir / "assess.md"
            symlink.symlink_to(real_file)

            original_cwd = os.getcwd()
            try:
                os.chdir(project)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    result,
                    str(Path(".workflows/bugfix/skills/assess.md")),
                )
            finally:
                os.chdir(original_cwd)

    def test_regular_file_override_still_works(self) -> None:
        """Non-symlink regular file override remains unaffected."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertTrue(
                    result.startswith(".workflows"),
                    f"Expected override path, got: {result}",
                )
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# End-to-end main() tests
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    """Verify main() end-to-end behaviour."""

    def test_main_prints_builtin_path(self) -> None:
        """main() prints the resolved path to stdout and exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = resolve_phase.main(["bugfix", "assess.md"])
                self.assertEqual(code, 0)
                output = buf.getvalue().strip()
                self.assertIn("bugfix", output)
                self.assertIn("assess.md", output)
            finally:
                os.chdir(original_cwd)

    def test_main_prints_override_path(self) -> None:
        """main() prints the override path when it exists."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = resolve_phase.main(["bugfix", "assess.md"])
                self.assertEqual(code, 0)
                output = buf.getvalue().strip()
                self.assertEqual(
                    output,
                    str(Path(".workflows/bugfix/skills/assess.md")),
                )
            finally:
                os.chdir(original_cwd)

    def test_main_missing_args_exits_2(self) -> None:
        """main() with no arguments exits with code 2 (argparse)."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_main_nonexistent_workflow_exits_1(self) -> None:
        """main() with a nonexistent workflow exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.main([
                        "nonexistent-workflow", "nonexistent.md",
                    ])
                self.assertEqual(
                    ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    """Verify helper functions."""

    def test_info_writes_to_stderr(self) -> None:
        """info() writes an INFO-prefixed message to stderr."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            resolve_phase.info("test message")
        self.assertIn("INFO: test message", buf.getvalue())

    def test_fail_exits_with_code(self) -> None:
        """fail() exits with the specified code."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.fail("something broke", code=1)
        self.assertEqual(ctx.exception.code, 1)

    def test_fail_writes_to_stderr(self) -> None:
        """fail() writes an ERROR-prefixed message to stderr."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf), self.assertRaises(SystemExit):
            resolve_phase.fail("bad thing")
        self.assertIn("ERROR: bad thing", buf.getvalue())

    def test_fail_default_code(self) -> None:
        """fail() defaults to EXIT_RESOLUTION_ERROR."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.fail("error")
        self.assertEqual(ctx.exception.code, resolve_phase.EXIT_RESOLUTION_ERROR)


# ---------------------------------------------------------------------------
# --builtin-only tests
# ---------------------------------------------------------------------------


class TestBuiltinOnly(unittest.TestCase):
    """Verify --builtin-only skips override check."""

    def test_builtin_only_skips_override(self) -> None:
        """With builtin_only=True, override file is ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create an override that would normally be selected
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase(
                    "bugfix", "assess.md", builtin_only=True,
                )
                # Should NOT return the override
                self.assertNotIn(".workflows", result)
                # Should return the built-in
                self.assertIn("bugfix", result)
                self.assertIn("assess.md", result)
            finally:
                os.chdir(original_cwd)

    def test_builtin_only_no_info_message(self) -> None:
        """With builtin_only=True, no override announcement is made."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf):
                    resolve_phase.resolve_phase(
                        "bugfix", "assess.md", builtin_only=True,
                    )
                self.assertNotIn("override", buf.getvalue().lower())
            finally:
                os.chdir(original_cwd)

    def test_builtin_only_via_cli(self) -> None:
        """--builtin-only flag works via main() CLI interface."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = resolve_phase.main([
                        "--builtin-only", "bugfix", "assess.md",
                    ])
                self.assertEqual(code, 0)
                output = buf.getvalue().strip()
                self.assertNotIn(".workflows", output)
                self.assertIn("bugfix", output)
            finally:
                os.chdir(original_cwd)

    def test_default_still_finds_override(self) -> None:
        """Without --builtin-only, override is still selected (no regression)."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertTrue(
                    result.startswith(".workflows"),
                    f"Expected override path, got: {result}",
                )
            finally:
                os.chdir(original_cwd)

    def test_builtin_only_nonexistent_fails(self) -> None:
        """--builtin-only still fails for nonexistent workflows."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.resolve_phase(
                        "nonexistent", "nope.md", builtin_only=True,
                    )
                self.assertEqual(
                    ctx.exception.code,
                    resolve_phase.EXIT_RESOLUTION_ERROR,
                )
            finally:
                os.chdir(original_cwd)


class TestBuiltinOnlyArgparse(unittest.TestCase):
    """Verify --builtin-only argparse configuration."""

    def test_builtin_only_default_false(self) -> None:
        """--builtin-only defaults to False."""
        parser = resolve_phase.build_parser()
        args = parser.parse_args(["bugfix", "assess.md"])
        self.assertFalse(args.builtin_only)

    def test_builtin_only_flag_parsed(self) -> None:
        """--builtin-only sets the flag to True."""
        parser = resolve_phase.build_parser()
        args = parser.parse_args(["--builtin-only", "bugfix", "assess.md"])
        self.assertTrue(args.builtin_only)


if __name__ == "__main__":
    unittest.main()
