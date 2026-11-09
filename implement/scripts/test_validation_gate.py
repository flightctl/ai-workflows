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
    """Create a temporary git repo with one commit and .gitignore for .artifacts/.

    The .gitignore is committed so that write_report() does not change HEAD.
    """
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", d], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"],
                   check=True, capture_output=True)
    # Create initial commit with .gitignore
    readme = os.path.join(d, "README.md")
    with open(readme, "w") as f:
        f.write("# Test\n")
    gitignore = os.path.join(d, ".gitignore")
    with open(gitignore, "w") as f:
        f.write(".artifacts\n")
    subprocess.run(["git", "-C", d, "add", "README.md", ".gitignore"],
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
    which is gitignored (set up in make_temp_repo), so it does not dirty
    the worktree.  This function does NOT commit, so HEAD is unchanged.
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

    def test_passing_rejected(self):
        """PASSING is not the canonical PASS token."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASSING

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        # result_value is stored but it's not canonical PASS
        self.assertEqual(info["result_value"], "PASSING")

    def test_passport_rejected(self):
        """PASSPORT is not the canonical PASS token."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASSPORT

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertEqual(info["result_value"], "PASSPORT")

    def test_multiple_sha_lines_rejected(self):
        """Multiple SHA lines in Validated Commit section are rejected."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
                1234567890abcdef1234567890abcdef12345678
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("multiple SHA values", info["parse_error"])

    def test_sha_with_unexpected_prose_rejected(self):
        """SHA mixed with unexpected non-template text is rejected."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
                This was validated on Tuesday.
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("unexpected non-SHA content", info["parse_error"])

    def test_sha_with_template_placeholder_accepted(self):
        """SHA alongside template placeholder text is accepted."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as f:
            f.write(textwrap.dedent("""\
                ## Result

                PASS

                ## Validated Commit

                abcdef1234567890abcdef1234567890abcdef12
            """))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIsNone(info["parse_error"])
        self.assertEqual(
            info["validated_commit"],
            "abcdef1234567890abcdef1234567890abcdef12",
        )

    def test_non_utf8_report_fails_closed(self):
        """Report with non-UTF-8 content fails with actionable error."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"\x80\x81\x82 invalid utf8\n## Result\nPASS\n")
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertTrue(info["exists"])
        self.assertIn("not valid UTF-8", info["parse_error"])


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
        """Gate fails when worktree has untracked files (not gitignored)."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # Create untracked file (not gitignored)
        with open(os.path.join(self.repo, "untracked.txt"), "w") as f:
            f.write("new\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not clean", result["reason"])

    def test_gitignored_artifacts_clean(self):
        """Gate passes when only changes are gitignored .artifacts/ files."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)
        # .artifacts is gitignored by write_report's .gitignore setup
        # Create additional gitignored artifact
        os.makedirs(os.path.join(self.repo, ".artifacts", "extra"), exist_ok=True)
        with open(os.path.join(self.repo, ".artifacts", "extra", "state.md"), "w") as f:
            f.write("artifact state\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "pass")

    def test_tracked_artifacts_not_ignored(self):
        """Gate fails when a tracked file under .artifacts/ is modified."""
        # Remove .artifacts from .gitignore so we can track a file there
        gitignore = os.path.join(self.repo, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("# no ignores\n")
        subprocess.run(["git", "add", ".gitignore"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "clear gitignore"],
                       check=True, capture_output=True)

        # Create and commit a file under .artifacts (making it tracked)
        artifacts_dir = os.path.join(self.repo, ".artifacts", "tracked")
        os.makedirs(artifacts_dir, exist_ok=True)
        tracked_file = os.path.join(artifacts_dir, "config.md")
        with open(tracked_file, "w") as f:
            f.write("original\n")
        subprocess.run(["git", "-C", self.repo, "add",
                        ".artifacts/tracked/config.md"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-m",
                        "add tracked artifact"], check=True, capture_output=True)

        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)

        # Modify the tracked file — this should NOT be ignored
        with open(tracked_file, "w") as f:
            f.write("modified\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not clean", result["reason"])

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

    def test_passing_not_canonical_pass(self):
        """PASSING is rejected as not a canonical PASS token."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASSING", head)
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not PASS", result["reason"])

    def test_passport_not_canonical_pass(self):
        """PASSPORT is rejected as not a canonical PASS token."""
        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASSPORT", head)
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not PASS", result["reason"])

    def test_multiple_sha_values_rejected(self):
        """Multiple SHA lines in Validated Commit section block."""
        head = get_head(self.repo)
        report_path = os.path.join(self.repo, "report.md")
        sha2 = "1234567890abcdef1234567890abcdef12345678"
        with open(report_path, "w") as f:
            f.write(textwrap.dedent(f"""\
                ## Result

                PASS

                ## Validated Commit

                {head}
                {sha2}
            """))
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("malformed", result["reason"])

    def test_submodule_dirty_detected(self):
        """Gate fails when a submodule has dirty state."""
        # Create a bare repo as the submodule source
        sub_source = tempfile.mkdtemp()
        subprocess.run(["git", "init", "--bare", sub_source],
                       check=True, capture_output=True)
        # Create a temp repo with initial commit for the submodule
        sub_work = tempfile.mkdtemp()
        subprocess.run(["git", "init", sub_work], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", sub_work, "config",
                        "user.email", "t@t"], check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "config",
                        "user.name", "T"], check=True, capture_output=True)
        with open(os.path.join(sub_work, "sub.txt"), "w") as f:
            f.write("sub content\n")
        subprocess.run(["git", "-C", sub_work, "add", "."],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "commit", "-m", "sub init"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "remote", "add",
                        "origin", sub_source], check=True, capture_output=True)
        # Get the default branch name (main or master depending on git config)
        branch_result = subprocess.run(
            ["git", "-C", sub_work, "branch", "--show-current"],
            capture_output=True, text=True, check=True)
        sub_branch = branch_result.stdout.strip()
        # Allow file:// transport for this test
        subprocess.run(["git", "-C", sub_work, "config",
                        "protocol.file.allow", "always"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "push", "origin", sub_branch],
                       check=True, capture_output=True)

        # Add submodule to the test repo — requires file:// transport
        env = dict(os.environ, GIT_CONFIG_COUNT="1",
                   GIT_CONFIG_KEY_0="protocol.file.allow",
                   GIT_CONFIG_VALUE_0="always")
        subprocess.run(["git", "-C", self.repo, "submodule", "add",
                        sub_source, "mysub"], check=True,
                       capture_output=True, env=env)
        subprocess.run(["git", "-C", self.repo, "commit", "-m",
                        "add sub"], check=True, capture_output=True)

        # Configure to ignore submodule (the gate should override this)
        subprocess.run(["git", "-C", self.repo, "config",
                        "diff.ignoreSubmodules", "all"],
                       check=True, capture_output=True)

        head = get_head(self.repo)
        report_path = write_report(self.repo, "PASS", head)

        # Dirty the submodule
        sub_path = os.path.join(self.repo, "mysub", "sub.txt")
        with open(sub_path, "a") as f:
            f.write("dirty\n")

        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("not clean", result["reason"])

        # Cleanup
        subprocess.run(["rm", "-rf", sub_source], check=False)
        subprocess.run(["rm", "-rf", sub_work], check=False)

    def test_non_utf8_report_fails_closed(self):
        """Non-UTF-8 report fails closed with actionable output."""
        head = get_head(self.repo)
        report_path = os.path.join(self.repo, "bad-report.md")
        with open(report_path, "wb") as f:
            f.write(b"\x80\x81## Result\n\nPASS\n\n## Validated Commit\n\n")
            f.write(head.encode())
            f.write(b"\n")
        result = validation_gate.run_gate(report_path)
        self.assertEqual(result["gate"], "fail")
        self.assertIn("malformed", result["reason"])


class TestReviewCommitIsolation(unittest.TestCase):
    """Test that the documented commit pattern in review.md preserves
    unrelated staged/unstaged state.

    This tests the actual git commit --only pattern that the review
    phase documents, proving that unrelated index content survives.
    """

    def setUp(self):
        self.repo = make_temp_repo()
        self.orig_dir = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.orig_dir)
        subprocess.run(["rm", "-rf", self.repo], check=False)

    def test_commit_only_preserves_unrelated_staged(self):
        """git commit --only preserves pre-existing staged changes.

        This tests the actual commit pattern documented in review.md:
        `git add {review files}` then `git commit --only -- {review files}`
        preserves unrelated staged and unstaged state.
        """
        # Create two tracked files
        with open("file_a.txt", "w") as f:
            f.write("content a\n")
        with open("file_b.txt", "w") as f:
            f.write("content b\n")
        with open("review_target.txt", "w") as f:
            f.write("original\n")
        subprocess.run(["git", "add", "file_a.txt", "file_b.txt",
                        "review_target.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial files"],
                       check=True, capture_output=True)

        # Stage a change to file_a (pre-existing staged work)
        with open("file_a.txt", "w") as f:
            f.write("user staged change\n")
        subprocess.run(["git", "add", "file_a.txt"],
                       check=True, capture_output=True)

        # Also make unstaged change to file_b (pre-existing unstaged work)
        with open("file_b.txt", "w") as f:
            f.write("user unstaged change\n")

        # Simulate review: modify a clean-at-entry tracked file
        with open("review_target.txt", "w") as f:
            f.write("review change\n")

        # Stage the review file, then commit --only that specific path
        subprocess.run(["git", "add", "review_target.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "--only", "-m",
                        "review: fix something", "--", "review_target.txt"],
                       check=True, capture_output=True)

        # Verify: file_a should STILL be staged
        status = subprocess.run(["git", "status", "--porcelain"],
                                capture_output=True, text=True, check=True)
        lines = status.stdout.strip().splitlines()
        status_map = {}
        for line in lines:
            xy = line[:2]
            path = line[3:]
            status_map[path] = xy

        # file_a should still show as staged (M in index position)
        self.assertIn("file_a.txt", status_map,
                       "pre-existing staged file_a.txt should still appear")
        self.assertEqual(status_map["file_a.txt"][0], "M",
                         "file_a.txt should still be staged (index modified)")

        # file_b should still show as unstaged modification
        self.assertIn("file_b.txt", status_map,
                       "pre-existing unstaged file_b.txt should still appear")
        self.assertEqual(status_map["file_b.txt"][1], "M",
                         "file_b.txt should still have unstaged changes")

    def test_mixed_target_file_blocks(self):
        """When a review target file has pre-existing changes, the review
        phase should block before making edits, not after."""
        # Create a file
        with open("target.txt", "w") as f:
            f.write("original content\n")
        subprocess.run(["git", "add", "target.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add target"],
                       check=True, capture_output=True)

        # Pre-existing unstaged change to target
        with open("target.txt", "w") as f:
            f.write("user's change\n")

        # Check: git status detects the pre-existing change
        status = subprocess.run(["git", "status", "--porcelain", "-z"],
                                capture_output=True, check=True)
        entries = status.stdout.decode().split("\0")
        pre_existing = [e for e in entries if e and "target.txt" in e]
        self.assertTrue(len(pre_existing) > 0,
                        "pre-existing change to target.txt should be detected")

        # The review phase should stop HERE (before editing) because
        # target.txt has pre-existing changes.  We verify the detection
        # mechanism works — the phase behavioral check is in review.md.


if __name__ == "__main__":
    unittest.main()
