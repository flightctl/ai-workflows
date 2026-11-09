#!/usr/bin/env python3
"""Tests for the validation_gate module.

These tests exercise the actual production gate against real git state
in disposable repositories. They do NOT duplicate toy logic — they import
and call validation_gate.run_gate() and validation_gate.parse_report()
directly.
"""

import json
import os
import subprocess
import tempfile
import textwrap
import unittest

# Import the production module
import validation_gate


def make_temp_repo():
    """Create a temporary git repo with one commit and return its path."""
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", d], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"],
                   check=True, capture_output=True)
    # Create initial commit
    readme = os.path.join(d, "README.md")
    with open(readme, "w") as f:
        f.write("# Test\n")
    subprocess.run(["git", "-C", d, "add", "README.md"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-m", "initial"],
                   check=True, capture_output=True)
    return d


def get_head(repo_dir):
    """Get HEAD SHA of a repo."""
    result = subprocess.run(
        ["git", "-C", repo_dir, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def write_report(repo_dir, result_text, sha, extra_sections=""):
    """Write a valid validation report under .artifacts/ in the repo.

    In production the report lives at .artifacts/implement/{key}/05-validation-report.md
    which is gitignored, so it does not dirty the worktree.
    """
    artifacts_dir = os.path.join(repo_dir, ".artifacts", "implement", "TEST-001")
    os.makedirs(artifacts_dir, exist_ok=True)
    report_path = os.path.join(artifacts_dir, "05-validation-report.md")
    content = textwrap.dedent(f"""\
        # Validation Report — TEST-001

        ## Check Results

        | Check | Command | Result | Notes |
        |-------|---------|--------|-------|
        | lint | `make lint` | pass | clean |

        ## Coverage Analysis

        No decomposition concern.

        ## Regressions

        No regressions detected.

        ## Acceptance Criteria Verification

        All acceptance criteria verified.

        ## Quality Review Findings

        No quality review findings.

        ## Pre-existing Issues

        No pre-existing issues observed.

        ## Validation Commits

        No additional commits needed during validation.

        ## Result

        {result_text}
        {extra_sections}
        ## Validated Commit

        {sha}
    """)
    with open(report_path, "w") as f:
        f.write(content)
    return report_path


class TestParseReport(unittest.TestCase):
    """Test report parsing logic in isolation (no git needed)."""

    def test_missing_file(self):
        info = validation_gate.parse_report("/nonexistent/path.md")
        self.assertFalse(info["exists"])
        self.assertIn("does not exist", info["parse_error"])

    def test_valid_pass_report(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                # Report

                ## Result

                PASS — all checks pass.

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertTrue(info["exists"])
        self.assertIsNone(info["parse_error"])
        self.assertTrue(info["result_value"].startswith("PASS"))
        self.assertEqual(
            info["validated_commit"],
            "abcdef1234567890abcdef1234567890abcdef12",
        )

    def test_fail_result(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                FAIL — lint errors remain.

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertTrue(info["exists"])
        self.assertIsNone(info["parse_error"])
        self.assertFalse(info["result_value"].startswith("PASS"))

    def test_no_result_section(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                # Report

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIn("no '## Result' section", info["parse_error"])

    def test_no_validated_commit_section(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS — all good.
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIn("no '## Validated Commit' section", info["parse_error"])

    def test_duplicate_result_sections(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Result

                FAIL

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertEqual(info["result_count"], 2)
        self.assertIn("multiple '## Result' sections", info["parse_error"])

    def test_duplicate_validated_commit_sections(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12

                ## Validated Commit

                1234567890abcdef1234567890abcdef12345678
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertEqual(info["commit_count"], 2)
        self.assertIn("multiple '## Validated Commit' sections",
                       info["parse_error"])

    def test_short_sha_rejected(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Validated Commit

                abcdef1
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("does not contain a valid", info["parse_error"])

    def test_empty_validated_commit(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Validated Commit

            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("empty", info["parse_error"])

    def test_pass_with_explanation(self):
        """PASS text with explanation after the keyword is accepted."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS — all checks pass, coverage is comprehensive, all acceptance
                criteria satisfied, no regressions.

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIsNone(info["parse_error"])
        self.assertTrue(info["result_value"].startswith("PASS"))


class TestRunGate(unittest.TestCase):
    """Test the full gate against real git repos."""

    def setUp(self):
        self.repo = make_temp_repo()
        self.orig_dir = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.orig_dir)
        subprocess.run(["rm", "-rf", self.repo], check=False)

    def test_valid_current_sha(self):
        """Gate passes when report PASS matches current HEAD, worktree clean."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS — all good.", head)
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "pass")
        self.assertEqual(result["head"], head)
        self.assertEqual(result["validated_commit"], head)

    def test_old_sha_fails(self):
        """Gate fails when report SHA is from a prior commit."""
        old_head = get_head(self.repo)
        # Make a new commit
        with open(os.path.join(self.repo, "new.txt"), "w") as f:
            f.write("new content\n")
        subprocess.run(["git", "add", "new.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "second"],
                       check=True, capture_output=True)
        new_head = get_head(self.repo)
        self.assertNotEqual(old_head, new_head)

        report_path = write_report(self.repo, "PASS", old_head)
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("does not match", result["reason"])
        self.assertEqual(result["head"], new_head)
        self.assertEqual(result["validated_commit"], old_head)

    def test_fail_result(self):
        """Gate fails when report says FAIL."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "FAIL — lint errors.", head)
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not PASS", result["reason"])

    def test_missing_report(self):
        """Gate fails when report file does not exist."""
        result = validation_gate.run_gate("/nonexistent/report.md")
        self.assertEqual(result["gate"], "fail")
        self.assertIn("missing", result["reason"])

    def test_malformed_no_result(self):
        """Gate fails when report has no Result section."""
        report_path = os.path.join(self.repo, "report.md")
        with open(report_path, "w") as f:
            f.write("# Report\n\nSome content.\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("malformed", result["reason"])

    def test_malformed_no_sha(self):
        """Gate fails when report has PASS but no Validated Commit."""
        report_path = os.path.join(self.repo, "report.md")
        with open(report_path, "w") as f:
            f.write("## Result\n\nPASS\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("malformed", result["reason"])

    def test_dirty_worktree_unstaged(self):
        """Gate fails when worktree has unstaged changes."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # Make a tracked file dirty
        with open(os.path.join(self.repo, "README.md"), "a") as f:
            f.write("dirty\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not clean", result["reason"])

    def test_dirty_worktree_staged(self):
        """Gate fails when worktree has staged changes."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # Stage a change
        with open(os.path.join(self.repo, "README.md"), "a") as f:
            f.write("staged\n")
        subprocess.run(["git", "add", "README.md"],
                       check=True, capture_output=True)
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not clean", result["reason"])

    def test_dirty_worktree_untracked(self):
        """Gate fails when worktree has untracked files."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # Create untracked file
        with open(os.path.join(self.repo, "untracked.txt"), "w") as f:
            f.write("new\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not clean", result["reason"])

    def test_artifacts_ignored(self):
        """Gate ignores changes under .artifacts/ prefix."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # Create file under .artifacts
        os.makedirs(os.path.join(self.repo, ".artifacts", "impl"), exist_ok=True)
        with open(os.path.join(self.repo, ".artifacts", "impl", "state.md"), "w") as f:
            f.write("artifact state\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "pass")

    def test_post_self_review_new_commit(self):
        """Gate fails when a new commit is made after validated commit."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # Simulate self-review fix: new commit changes HEAD
        with open(os.path.join(self.repo, "fix.txt"), "w") as f:
            f.write("review fix\n")
        subprocess.run(["git", "add", "fix.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "self-review fix"],
                       check=True, capture_output=True)
        new_head = get_head(self.repo)
        self.assertNotEqual(head, new_head)

        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("does not match", result["reason"])

    def test_pass_text_with_long_explanation(self):
        """PASS text followed by explanation is accepted."""
        head = get_head(self.repo)
        report_path = write_report(
            self.repo,
            "PASS — all checks pass, coverage is comprehensive, "
            "all acceptance criteria satisfied, no regressions.",
            head,
        )
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "pass")

    def test_wrong_sha_format(self):
        """Gate fails when validated commit is not a valid full SHA."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head[:7])
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("malformed", result["reason"])

    def test_output_is_valid_json(self):
        """Gate output is parseable JSON."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        result = validation_gate.run_gate(report_path)
        # Verify it serializes to valid JSON
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["gate"], "pass")

    def test_duplicate_result_sections_rejected(self):
        """Gate fails when report has multiple Result sections."""
        head = get_head(self.repo)
        report_path = os.path.join(self.repo, "report.md")
        with open(report_path, "w") as f:
            f.write(textwrap.dedent(f"""\
                ## Result

                PASS

                ## Result

                FAIL

                ## Validated Commit

                {head}
            """))
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("malformed", result["reason"])


if __name__ == "__main__":
    unittest.main()
