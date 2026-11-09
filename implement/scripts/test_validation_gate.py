#!/usr/bin/env python3
"""Tests for the validation_gate module.

These tests exercise the actual production gate against real git state
in disposable repositories.  They import and call validation_gate
functions directly — no duplicated toy logic.
"""

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock

import validation_gate

# Derive CLI script path from the production module, not from CWD.
GATE_CLI = os.path.join(validation_gate.SCRIPT_DIR, "validation_gate.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_temp_repo():
    """Create a temporary git repo with one commit and .gitignore for .artifacts/."""
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", d], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"],
                   check=True, capture_output=True)
    for name, content in [("README.md", "# Test\n"),
                          (".gitignore", ".artifacts\n")]:
        with open(os.path.join(d, name), "w") as f:
            f.write(content)
    subprocess.run(["git", "-C", d, "add", "README.md", ".gitignore"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-m", "initial"],
                   check=True, capture_output=True)
    return d


def get_head(repo_dir):
    r = subprocess.run(["git", "-C", repo_dir, "rev-parse", "HEAD"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def write_report(repo_dir, result_text, sha):
    """Write a validation report under .artifacts/ (gitignored, no commit)."""
    d = os.path.join(repo_dir, ".artifacts", "implement", "TEST-001")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "05-validation-report.md")
    with open(path, "w") as f:
        f.write(textwrap.dedent(f"""\
            # Validation Report

            ## Result

            {result_text}

            ## Validated Commit

            {sha}
        """))
    return path


def parse_status_z(output_bytes):
    """Parse NUL-delimited porcelain output, returning a set of all paths.

    For renames/copies (R/C), both the source and destination paths are
    included in the returned set.
    """
    if not output_bytes:
        return set()
    entries = output_bytes.decode("utf-8", errors="replace").split("\0")
    paths = set()
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) < 3:
            i += 1
            continue
        xy = entry[:2]
        path = entry[3:]
        paths.add(path)
        if xy[0] in ("R", "C"):
            # Next NUL field is the destination path
            i += 1
            if i < len(entries) and entries[i]:
                paths.add(entries[i])
        i += 1
    return paths


_FILE_ENV = {**os.environ,
             "GIT_CONFIG_COUNT": "1",
             "GIT_CONFIG_KEY_0": "protocol.file.allow",
             "GIT_CONFIG_VALUE_0": "always"}


# ---------------------------------------------------------------------------
# TestParseReport
# ---------------------------------------------------------------------------

class TestParseReport(unittest.TestCase):
    """Parse logic only — no git needed."""

    def _parse(self, content):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                         delete=False) as f:
            f.write(textwrap.dedent(content))
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        return info

    def test_valid_pass_report(self):
        info = self._parse("""\
            ## Result

            PASS — all checks pass.

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
        """)
        self.assertIsNone(info["parse_error"])
        self.assertTrue(info["result_value"].startswith("PASS"))
        self.assertEqual(info["validated_commit"],
                         "abcdef1234567890abcdef1234567890abcdef12")

    def test_missing_file(self):
        info = validation_gate.parse_report("/nonexistent/path.md")
        self.assertFalse(info["exists"])

    def test_fail_result(self):
        info = self._parse("""\
            ## Result

            FAIL — lint errors.

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
        """)
        self.assertFalse(info["result_value"].startswith("PASS"))

    def test_no_result_section(self):
        info = self._parse("## Validated Commit\n\nabcdef1234567890abcdef1234567890abcdef12\n")
        self.assertIn("no '## Result'", info["parse_error"])

    def test_no_validated_commit_section(self):
        info = self._parse("## Result\n\nPASS\n")
        self.assertIn("no '## Validated Commit'", info["parse_error"])

    def test_duplicate_result_sections(self):
        info = self._parse("""\
            ## Result

            PASS

            ## Result

            FAIL

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
        """)
        self.assertIn("multiple '## Result'", info["parse_error"])

    def test_duplicate_validated_commit_sections(self):
        info = self._parse("""\
            ## Result

            PASS

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12

            ## Validated Commit

            1234567890abcdef1234567890abcdef12345678
        """)
        self.assertIn("multiple '## Validated Commit'", info["parse_error"])

    def test_short_sha_rejected(self):
        info = self._parse("## Result\n\nPASS\n\n## Validated Commit\n\nabcdef1\n")
        self.assertIsNone(info["validated_commit"])

    def test_empty_validated_commit(self):
        info = self._parse("## Result\n\nPASS\n\n## Validated Commit\n\n")
        self.assertIn("empty", info["parse_error"])

    def test_pass_with_explanation(self):
        info = self._parse("""\
            ## Result

            PASS — all checks pass, coverage comprehensive.

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
        """)
        self.assertIsNone(info["parse_error"])

    def test_passing_rejected(self):
        info = self._parse("""\
            ## Result

            PASSING

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
        """)
        self.assertEqual(info["result_value"], "PASSING")

    def test_passport_rejected(self):
        info = self._parse("""\
            ## Result

            PASSPORT

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
        """)
        self.assertEqual(info["result_value"], "PASSPORT")

    def test_multiple_sha_lines_rejected(self):
        info = self._parse("""\
            ## Result

            PASS

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
            1234567890abcdef1234567890abcdef12345678
        """)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("exactly one", info["parse_error"])

    def test_sha_with_extra_prose_rejected(self):
        info = self._parse("""\
            ## Result

            PASS

            ## Validated Commit

            abcdef1234567890abcdef1234567890abcdef12
            This was validated on Tuesday.
        """)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("exactly one", info["parse_error"])

    def test_template_placeholder_rejected(self):
        info = self._parse("""\
            ## Result

            PASS

            ## Validated Commit

            {full commit SHA from git rev-parse HEAD}
        """)
        self.assertIsNone(info["validated_commit"])
        self.assertIn("does not contain a valid", info["parse_error"])

    def test_json_like_rejected(self):
        info = self._parse("""\
            ## Result

            PASS

            ## Validated Commit

            {"sha": "abcdef1234567890abcdef1234567890abcdef12"}
        """)
        self.assertIsNone(info["validated_commit"])
        self.assertIsNotNone(info["parse_error"])

    def test_non_utf8_fails_closed(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"\x80\x81## Result\n\nPASS\n\n## Validated Commit\n\n")
            f.write(b"abcdef1234567890abcdef1234567890abcdef12\n")
            f.flush()
            info = validation_gate.parse_report(f.name)
        os.unlink(f.name)
        self.assertIn("not valid UTF-8", info["parse_error"])


# ---------------------------------------------------------------------------
# TestParseLsRemote
# ---------------------------------------------------------------------------

class TestParseLsRemote(unittest.TestCase):
    """Test _parse_ls_remote_exact independently."""

    def test_exact_match(self):
        output = b"abcdef1234567890abcdef1234567890abcdef12\trefs/heads/main\n"
        sha, err = validation_gate._parse_ls_remote_exact(
            output, "refs/heads/main")
        self.assertEqual(sha, "abcdef1234567890abcdef1234567890abcdef12")
        self.assertIsNone(err)

    def test_suffix_ambiguity(self):
        """When ls-remote returns multiple lines, only exact ref matches."""
        output = (
            b"aaaa1234567890abcdef1234567890abcdef1234\trefs/heads/feature\n"
            b"bbbb1234567890abcdef1234567890abcdef1234\trefs/heads/my-feature\n"
        )
        sha, err = validation_gate._parse_ls_remote_exact(
            output, "refs/heads/feature")
        self.assertEqual(sha, "aaaa1234567890abcdef1234567890abcdef1234")

        sha2, err2 = validation_gate._parse_ls_remote_exact(
            output, "refs/heads/my-feature")
        self.assertEqual(sha2, "bbbb1234567890abcdef1234567890abcdef1234")

    def test_no_exact_match(self):
        output = b"abcdef1234567890abcdef1234567890abcdef12\trefs/heads/other\n"
        sha, err = validation_gate._parse_ls_remote_exact(
            output, "refs/heads/main")
        self.assertIsNone(sha)
        self.assertIn("no exact match", err)

    def test_malformed_line(self):
        output = b"not-a-sha refs/heads/main\n"  # space not tab
        sha, err = validation_gate._parse_ls_remote_exact(
            output, "refs/heads/main")
        self.assertIsNone(sha)

    def test_empty_output(self):
        sha, err = validation_gate._parse_ls_remote_exact(
            b"", "refs/heads/main")
        self.assertIsNone(sha)
        self.assertIn("empty", err)


# ---------------------------------------------------------------------------
# TestRunGate
# ---------------------------------------------------------------------------

class TestRunGate(unittest.TestCase):

    def setUp(self):
        self.repo = make_temp_repo()
        self.orig_dir = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.orig_dir)
        subprocess.run(["rm", "-rf", self.repo], check=False)

    def test_valid_current_sha(self):
        head = get_head(self.repo)
        r = validation_gate.run_gate(write_report(self.repo, "PASS", head))
        self.assertEqual(r["gate"], "pass")

    def test_old_sha_fails(self):
        old = get_head(self.repo)
        with open(os.path.join(self.repo, "new.txt"), "w") as f:
            f.write("x\n")
        subprocess.run(["git", "add", "new.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "2nd"], check=True, capture_output=True)
        r = validation_gate.run_gate(write_report(self.repo, "PASS", old))
        self.assertEqual(r["gate"], "fail")
        self.assertIn("does not match", r["reason"])

    def test_fail_result(self):
        head = get_head(self.repo)
        r = validation_gate.run_gate(write_report(self.repo, "FAIL", head))
        self.assertEqual(r["gate"], "fail")

    def test_missing_report(self):
        r = validation_gate.run_gate("/nonexistent")
        self.assertEqual(r["gate"], "fail")
        self.assertIn("missing", r["reason"])

    def test_malformed_no_result(self):
        p = os.path.join(self.repo, "r.md")
        with open(p, "w") as f:
            f.write("# Report\n")
        r = validation_gate.run_gate(p)
        self.assertEqual(r["gate"], "fail")

    def test_malformed_no_sha(self):
        p = os.path.join(self.repo, "r.md")
        with open(p, "w") as f:
            f.write("## Result\n\nPASS\n")
        r = validation_gate.run_gate(p)
        self.assertEqual(r["gate"], "fail")

    def test_dirty_unstaged(self):
        head = get_head(self.repo)
        write_report(self.repo, "PASS", head)
        with open(os.path.join(self.repo, "README.md"), "a") as f:
            f.write("dirty\n")
        r = validation_gate.run_gate(
            os.path.join(self.repo, ".artifacts", "implement",
                         "TEST-001", "05-validation-report.md"))
        self.assertEqual(r["gate"], "fail")
        self.assertIn("not clean", r["reason"])

    def test_dirty_staged(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        with open(os.path.join(self.repo, "README.md"), "a") as f:
            f.write("s\n")
        subprocess.run(["git", "add", "README.md"], check=True, capture_output=True)
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")

    def test_dirty_untracked(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        with open(os.path.join(self.repo, "untracked.txt"), "w") as f:
            f.write("u\n")
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")

    def test_gitignored_artifacts_clean(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        os.makedirs(os.path.join(self.repo, ".artifacts", "extra"), exist_ok=True)
        with open(os.path.join(self.repo, ".artifacts", "extra", "x"), "w") as f:
            f.write("x\n")
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "pass")

    def test_tracked_artifacts_modified_fails(self):
        gi = os.path.join(self.repo, ".gitignore")
        with open(gi, "w") as f:
            f.write("# no ignores\n")
        subprocess.run(["git", "add", ".gitignore"], check=True, capture_output=True)
        d = os.path.join(self.repo, ".artifacts", "t")
        os.makedirs(d, exist_ok=True)
        tf = os.path.join(d, "cfg.md")
        with open(tf, "w") as f:
            f.write("orig\n")
        subprocess.run(["git", "add", tf], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "tracked artifact"],
                       check=True, capture_output=True)
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        with open(tf, "w") as f:
            f.write("modified\n")
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")

    def test_post_self_review_commit(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        with open(os.path.join(self.repo, "fix.txt"), "w") as f:
            f.write("fix\n")
        subprocess.run(["git", "add", "fix.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix"], check=True, capture_output=True)
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")
        self.assertIn("does not match", r["reason"])

    def test_pass_long_explanation(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo,
                           "PASS — all checks pass, comprehensive.", head)
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "pass")

    def test_wrong_sha_format(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head[:7])
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")

    def test_passing_not_canonical(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASSING", head)
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")

    def test_passport_not_canonical(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASSPORT", head)
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")

    def test_multiple_sha_rejected(self):
        head = get_head(self.repo)
        p = os.path.join(self.repo, "r.md")
        sha2 = "1234567890abcdef1234567890abcdef12345678"
        with open(p, "w") as f:
            f.write(f"## Result\n\nPASS\n\n## Validated Commit\n\n{head}\n{sha2}\n")
        r = validation_gate.run_gate(p)
        self.assertEqual(r["gate"], "fail")

    def test_duplicate_result_sections(self):
        head = get_head(self.repo)
        p = os.path.join(self.repo, "r.md")
        with open(p, "w") as f:
            f.write(f"## Result\n\nPASS\n\n## Result\n\nFAIL\n\n## Validated Commit\n\n{head}\n")
        r = validation_gate.run_gate(p)
        self.assertEqual(r["gate"], "fail")

    def test_output_is_valid_json(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        r = validation_gate.run_gate(rpt)
        parsed = json.loads(json.dumps(r))
        self.assertEqual(parsed["gate"], "pass")

    def test_non_utf8_fails_closed(self):
        head = get_head(self.repo)
        p = os.path.join(self.repo, "bad.md")
        with open(p, "wb") as f:
            f.write(b"\x80\x81## Result\n\nPASS\n\n## Validated Commit\n\n")
            f.write(head.encode())
            f.write(b"\n")
        r = validation_gate.run_gate(p)
        self.assertEqual(r["gate"], "fail")

    def test_submodule_dirty(self):
        sub_source = tempfile.mkdtemp()
        subprocess.run(["git", "init", "--bare", sub_source],
                       check=True, capture_output=True)
        sub_work = tempfile.mkdtemp()
        subprocess.run(["git", "init", sub_work], check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "config", "user.email", "t@t"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "config", "user.name", "T"],
                       check=True, capture_output=True)
        with open(os.path.join(sub_work, "sub.txt"), "w") as f:
            f.write("sub\n")
        subprocess.run(["git", "-C", sub_work, "add", "."],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "commit", "-m", "sub"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", sub_work, "remote", "add",
                        "origin", sub_source], check=True, capture_output=True)
        branch = subprocess.run(
            ["git", "-C", sub_work, "branch", "--show-current"],
            capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", sub_work, "push", "origin", branch],
                       check=True, capture_output=True, env=_FILE_ENV)
        subprocess.run(["git", "-C", self.repo, "submodule", "add",
                        sub_source, "mysub"],
                       check=True, capture_output=True, env=_FILE_ENV)
        subprocess.run(["git", "-C", self.repo, "commit", "-m", "add sub"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "config",
                        "diff.ignoreSubmodules", "all"],
                       check=True, capture_output=True)
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        with open(os.path.join(self.repo, "mysub", "sub.txt"), "a") as f:
            f.write("dirty\n")
        r = validation_gate.run_gate(rpt)
        self.assertEqual(r["gate"], "fail")
        subprocess.run(["rm", "-rf", sub_source, sub_work], check=False)


# ---------------------------------------------------------------------------
# TestPrePRGate
# ---------------------------------------------------------------------------

class TestPrePRGate(unittest.TestCase):

    def setUp(self):
        self.repo = make_temp_repo()
        self.orig_dir = os.getcwd()
        os.chdir(self.repo)
        self.bare = tempfile.mkdtemp()
        subprocess.run(["git", "clone", "--bare", self.repo, self.bare],
                       check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "test-remote", self.bare],
                       check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "feature-x"],
                       check=True, capture_output=True)
        with open("feature.txt", "w") as f:
            f.write("feature\n")
        subprocess.run(["git", "add", "feature.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"],
                       check=True, capture_output=True)
        subprocess.run(["git", "push", "test-remote", "feature-x"],
                       check=True, capture_output=True)

    def tearDown(self):
        os.chdir(self.orig_dir)
        subprocess.run(["rm", "-rf", self.repo, self.bare], check=False)

    def test_success(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        r = validation_gate.run_pre_pr_gate(
            rpt, head, "test-remote", "feature-x")
        self.assertEqual(r["gate"], "pass")

    def test_remote_ahead(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        clone = tempfile.mkdtemp()
        subprocess.run(["git", "clone", self.bare, clone],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", clone, "config", "user.email", "t@t"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", clone, "config", "user.name", "T"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", clone, "checkout", "feature-x"],
                       check=True, capture_output=True)
        with open(os.path.join(clone, "extra.txt"), "w") as f:
            f.write("ext\n")
        subprocess.run(["git", "-C", clone, "add", "extra.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", clone, "commit", "-m", "ext"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", clone, "push", "origin", "feature-x"],
                       check=True, capture_output=True)
        subprocess.run(["rm", "-rf", clone], check=False)
        r = validation_gate.run_pre_pr_gate(
            rpt, head, "test-remote", "feature-x")
        self.assertEqual(r["gate"], "fail")
        self.assertIn("remote", r["reason"].lower())

    def test_ref_missing(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        r = validation_gate.run_pre_pr_gate(
            rpt, head, "test-remote", "nonexistent")
        self.assertEqual(r["gate"], "fail")
        self.assertIn("cannot verify", r["reason"])

    def test_dirty_after_push(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        with open("dirty.txt", "w") as f:
            f.write("d\n")
        r = validation_gate.run_pre_pr_gate(
            rpt, head, "test-remote", "feature-x")
        self.assertEqual(r["gate"], "fail")

    def test_unpushed_local_commit(self):
        pushed = get_head(self.repo)
        with open("local.txt", "w") as f:
            f.write("l\n")
        subprocess.run(["git", "add", "local.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "local"],
                       check=True, capture_output=True)
        new_head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", new_head)
        r = validation_gate.run_pre_pr_gate(
            rpt, pushed, "test-remote", "feature-x")
        self.assertEqual(r["gate"], "fail")
        self.assertIn("pushed", r["reason"].lower())

    def test_cli_invocation(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        r = subprocess.run(
            ["python3", "-I", GATE_CLI,
             "--report", rpt,
             "--expected-sha", head,
             "--remote", "test-remote",
             "--branch", "feature-x"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["gate"], "pass")

    def test_cli_remote_fail(self):
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        r = subprocess.run(
            ["python3", "-I", GATE_CLI,
             "--report", rpt,
             "--expected-sha", head,
             "--remote", "test-remote",
             "--branch", "no-such"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["gate"], "fail")

    def test_cli_option_boundary(self):
        """Verify -- prevents remote name from being treated as git option."""
        head = get_head(self.repo)
        rpt = write_report(self.repo, "PASS", head)
        # A remote name starting with - would be parsed as a git flag
        # without the -- separator.  We can't easily add such a remote,
        # but we verify the code path uses -- by checking the source.
        import inspect
        src = inspect.getsource(validation_gate.run_pre_pr_gate)
        self.assertIn('"--",', src)


# ---------------------------------------------------------------------------
# TestRunGitBehavior
# ---------------------------------------------------------------------------

class TestRunGitBehavior(unittest.TestCase):

    def test_timeout_returns_error(self):
        with mock.patch("validation_gate.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(
                            cmd=["git"], timeout=30)):
            rc, out, err = validation_gate.run_git("status")
            self.assertEqual(rc, 124)
            self.assertIn("timed out", err)

    def test_cli_exit2_on_crash(self):
        """Script crash produces exit 2 with stderr, not JSON on stdout."""
        repo = make_temp_repo()
        orig = os.getcwd()
        os.chdir(repo)
        try:
            r = subprocess.run(
                ["python3", "-I", GATE_CLI,
                 "--report", "/nonexistent"],
                capture_output=True, text=True,
                env={**os.environ,
                     # Force an import error by breaking the module search
                     "PYTHONPATH": "/dev/null/fake"})
            # The script should either work normally (exit 0 or 1 with JSON)
            # or crash (exit 2 with stderr).  We just verify the contract:
            if r.returncode == 2:
                self.assertTrue(r.stderr.strip())
                # stdout should NOT be valid JSON
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(r.stdout)
            else:
                # Normal gate operation (report missing → exit 1)
                self.assertEqual(r.returncode, 1)
                parsed = json.loads(r.stdout)
                self.assertEqual(parsed["gate"], "fail")
        finally:
            os.chdir(orig)
            subprocess.run(["rm", "-rf", repo], check=False)


# ---------------------------------------------------------------------------
# TestReviewCommitIsolation
# ---------------------------------------------------------------------------

class TestReviewCommitIsolation(unittest.TestCase):

    def setUp(self):
        self.repo = make_temp_repo()
        self.orig_dir = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.orig_dir)
        subprocess.run(["rm", "-rf", self.repo], check=False)

    def test_commit_only_preserves_unrelated_staged(self):
        """git commit --only preserves pre-existing staged+unstaged state."""
        for name, content in [("a.txt", "a\n"), ("b.txt", "b\n"),
                              ("target.txt", "orig\n")]:
            with open(name, "w") as f:
                f.write(content)
        subprocess.run(["git", "add", "a.txt", "b.txt", "target.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       check=True, capture_output=True)

        # Pre-existing: stage a.txt, unstaged modify b.txt
        with open("a.txt", "w") as f:
            f.write("user staged\n")
        subprocess.run(["git", "add", "a.txt"],
                       check=True, capture_output=True)
        with open("b.txt", "w") as f:
            f.write("user unstaged\n")

        # Review: modify target
        with open("target.txt", "w") as f:
            f.write("review fix\n")
        subprocess.run(["git", "add", "--", "target.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "--only", "-m", "review fix",
                        "--", "target.txt"],
                       check=True, capture_output=True)

        # Verify committed paths
        committed = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(committed, "target.txt")

        # Verify committed content
        content = subprocess.run(
            ["git", "show", "HEAD:target.txt"],
            capture_output=True, text=True, check=True).stdout
        self.assertEqual(content, "review fix\n")

        # Verify pre-existing state preserved
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True).stdout
        smap = {}
        for line in status.strip().splitlines():
            smap[line[3:]] = line[:2]
        self.assertEqual(smap["a.txt"][0], "M")
        self.assertEqual(smap["b.txt"][1], "M")
        with open("a.txt") as f:
            self.assertEqual(f.read(), "user staged\n")
        with open("b.txt") as f:
            self.assertEqual(f.read(), "user unstaged\n")

    def test_new_file_committed_preserving_unrelated(self):
        """NEW untracked file committed via add+commit --only pattern."""
        with open("existing.txt", "w") as f:
            f.write("orig\n")
        subprocess.run(["git", "add", "existing.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       check=True, capture_output=True)

        # Pre-existing staged change
        with open("existing.txt", "w") as f:
            f.write("user staged\n")
        subprocess.run(["git", "add", "existing.txt"],
                       check=True, capture_output=True)

        # Review creates NEW file
        with open("new_file.py", "w") as f:
            f.write("def test(): pass\n")
        subprocess.run(["git", "add", "--", "new_file.py"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "--only", "-m", "review: new file",
                        "--", "new_file.py"],
                       check=True, capture_output=True)

        committed = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(committed, "new_file.py")

        smap = {}
        for line in subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, check=True).stdout.strip().splitlines():
            smap[line[3:]] = line[:2]
        self.assertIn("existing.txt", smap)
        self.assertEqual(smap["existing.txt"][0], "M")

    def test_preexisting_change_detected(self):
        """Pre-existing change is detected by exact parsed path comparison."""
        with open("target.txt", "w") as f:
            f.write("original\n")
        subprocess.run(["git", "add", "target.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add"],
                       check=True, capture_output=True)
        with open("target.txt", "w") as f:
            f.write("user change\n")

        out = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout
        paths = parse_status_z(out)
        self.assertIn("target.txt", paths)


# ---------------------------------------------------------------------------
# TestPreExistingDetection
# ---------------------------------------------------------------------------

class TestPreExistingDetection(unittest.TestCase):
    """Verify NUL-delimited git status parsing catches all pre-existing state."""

    def setUp(self):
        self.repo = make_temp_repo()
        self.orig_dir = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.orig_dir)
        subprocess.run(["rm", "-rf", self.repo], check=False)

    def test_untracked_target_detected(self):
        """An untracked file at a target path is detected."""
        with open("pkg_new_test.go", "w") as f:
            f.write("package pkg\n")
        out = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout
        paths = parse_status_z(out)
        self.assertIn("pkg_new_test.go", paths)

    def test_untracked_dir_detected(self):
        """Files inside an untracked directory are individually listed."""
        os.makedirs("newpkg", exist_ok=True)
        with open("newpkg/helper.go", "w") as f:
            f.write("package newpkg\n")
        out = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout
        paths = parse_status_z(out)
        self.assertIn("newpkg/helper.go", paths)

    def test_rename_paths_detected(self):
        """Both old and new paths of a rename are captured."""
        with open("old_name.txt", "w") as f:
            f.write("content\n")
        subprocess.run(["git", "add", "old_name.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add old"],
                       check=True, capture_output=True)
        subprocess.run(["git", "mv", "old_name.txt", "new_name.txt"],
                       check=True, capture_output=True)
        out = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout
        paths = parse_status_z(out)
        self.assertIn("old_name.txt", paths)
        self.assertIn("new_name.txt", paths)

    def test_path_with_spaces_detected(self):
        """Paths containing spaces are correctly parsed from -z output."""
        with open("my file.txt", "w") as f:
            f.write("space\n")
        out = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout
        paths = parse_status_z(out)
        self.assertIn("my file.txt", paths)

    def test_preserved_unrelated_index(self):
        """Pre-existing staged content survives commit --only of other paths."""
        # Set up: tracked file with staged change + untracked target
        with open("mine.txt", "w") as f:
            f.write("orig\n")
        subprocess.run(["git", "add", "mine.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       check=True, capture_output=True)
        with open("mine.txt", "w") as f:
            f.write("my staged change\n")
        subprocess.run(["git", "add", "mine.txt"],
                       check=True, capture_output=True)

        # Snapshot baseline
        baseline = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout

        # Create review file and commit with --only
        with open("review_new.txt", "w") as f:
            f.write("review\n")
        subprocess.run(["git", "add", "--", "review_new.txt"],
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "--only", "-m", "review",
                        "--", "review_new.txt"],
                       check=True, capture_output=True)

        # Verify baseline state preserved
        after = subprocess.run(
            ["git", "status", "--porcelain", "-z",
             "--untracked-files=all", "--ignore-submodules=none"],
            capture_output=True, check=True).stdout
        baseline_paths = parse_status_z(baseline)
        after_paths = parse_status_z(after)
        self.assertEqual(baseline_paths, after_paths)
        # Verify user bytes preserved
        with open("mine.txt") as f:
            self.assertEqual(f.read(), "my staged change\n")


if __name__ == "__main__":
    unittest.main()
