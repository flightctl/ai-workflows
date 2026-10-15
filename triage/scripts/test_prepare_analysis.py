#!/usr/bin/env python3
"""Tests for triage/scripts/prepare_analysis.py CLI behavior."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "prepare_analysis.py"
_spec = importlib.util.spec_from_file_location("prepare_analysis", _SCRIPT)
assert _spec and _spec.loader
prepare_analysis = importlib.util.module_from_spec(_spec)
sys.modules["prepare_analysis"] = prepare_analysis
_spec.loader.exec_module(prepare_analysis)


SAMPLE_ISSUES_DOC = {
    "project": "EDM",
    "jiraBaseUrl": "https://redhat.atlassian.net",
    "issues": [
        {
            "key": "EDM-101",
            "summary": "Login times out",
            "description": "Steps to reproduce: log in slowly.",
            "status": "Open",
            "priority": "High",
            "assignee": "Alice",
            "reporter": "Bob",
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-06-01T00:00:00.000+0000",
            "labels": [],
            "components": ["auth"],
        }
    ],
}


class TestSourceRootEnforcement(unittest.TestCase):
    def _write_inputs(self, directory: Path) -> tuple[Path, Path]:
        issues = directory / "issues.json"
        issues.write_text(json.dumps(SAMPLE_ISSUES_DOC), encoding="utf-8")
        output = directory / "analysis-input.json"
        return issues, output

    def test_rejects_missing_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            issues, output = self._write_inputs(root)
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                rc = prepare_analysis.main([
                    "--issues", str(issues),
                    "--source-root", str(root / "not-a-checkout"),
                    "--output", str(output),
                ])

            self.assertEqual(rc, 1)
            self.assertIn("not a Git checkout", stderr.getvalue())
            self.assertIn("source context is required", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_accepts_real_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subprocess.run(
                ["git", "init", "--quiet", str(root)],
                check=True,
                capture_output=True,
            )
            issues, output = self._write_inputs(root)

            rc = prepare_analysis.main([
                "--issues", str(issues),
                "--source-root", str(root),
                "--output", str(output),
            ])

            self.assertEqual(rc, 0)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["sourceCount"], 1)

    def test_rejects_stale_git_worktree_marker(self) -> None:
        """A .git file pointing at a missing worktree must not pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").write_text("gitdir: ../missing-worktree\n", encoding="utf-8")
            issues, output = self._write_inputs(root)
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                rc = prepare_analysis.main([
                    "--issues", str(issues),
                    "--source-root", str(root),
                    "--output", str(output),
                ])

            self.assertEqual(rc, 1)
            self.assertIn("not a Git checkout", stderr.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
