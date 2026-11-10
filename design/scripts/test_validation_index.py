#!/usr/bin/env python3
"""Tests for design/scripts/validation_index.py.

Exercises the ACTUAL CLI subcommands and production API that workflow
instructions invoke for validation-index.json operations.  Each test
calls the same entry points agents use via the CLI or Python API.

Coverage areas (deterministic contract/file tests):
  1. Schema validation — local and published index formats
  2. Path safety — traversal, reserved filenames, symlink patterns
  3. CLI subcommands — validate, resolve, transform, diff, build-legacy
  4. Legacy fallback — single testplan.md without index
  5. Fresh consumer discovery — docs repo without local metadata
  6. Lifecycle — add, rename, remove companions
  7. Publish order — snapshot-before-write, stale removal
  8. Multi-artifact downstream selection
  9. Routing — companion names, path resolution, ambiguity
  10. Error handling — malformed index, missing files, type errors

What is NOT tested (and why):
  - AI agent interpretation of workflow markdown instructions
  - Live GitHub/Jira integration (PR creation, comment posting)
  - End-to-end design workflow execution across phases
  These require running AI agents against real infrastructure.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Import validation_index via importlib (matches repo test convention)
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).resolve().parent / "validation_index.py"
_spec = importlib.util.spec_from_file_location("validation_index", _SCRIPT)
assert _spec and _spec.loader
vi = importlib.util.module_from_spec(_spec)
sys.modules["validation_index"] = vi
_spec.loader.exec_module(vi)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: object) -> None:
    _write(path, json.dumps(data, indent=2))


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the validation_index.py CLI."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True, text=True, timeout=10,
    )


def _init_git_repo(path):
    """Initialize a Git repository with an initial commit.

    Isolates from host Git configuration: disables signing and sets
    an empty hooks directory to prevent global hooks from interfering
    with test commits.
    """
    subprocess.run(["git", "init", str(path)],
                   capture_output=True, check=True)
    hooks_dir = tempfile.mkdtemp(prefix="empty-git-hooks-",
                                 dir=str(path.parent))
    subprocess.run(["git", "-C", str(path), "config",
                    "core.hooksPath", hooks_dir],
                   capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "config",
                    "commit.gpgsign", "false"],
                   capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "config",
                    "user.email", "test@test.com"],
                   capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "config",
                    "user.name", "Test"],
                   capture_output=True, check=True)
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(path), "add", ".gitkeep"],
                   capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "commit",
                    "-m", "initial"],
                   capture_output=True, check=True)


def _make_local_index(
    *,
    companions: list[dict[str, str]] | None = None,
) -> dict:
    """Build a valid local index with optional companions."""
    artifacts = [
        {
            "local": "04-testplan.md",
            "published_as": "testplan.md",
            "type": "testplan",
        }
    ]
    if companions:
        for c in companions:
            artifacts.append({
                "local": c["local"],
                "published_as": c["published_as"],
                "type": "companion",
                "purpose": c.get("purpose", "Test purpose"),
                "audience": c.get("audience", "Test audience"),
            })
    return {
        "schema_version": "1.0",
        "primary_testplan": "04-testplan.md",
        "artifacts": artifacts,
    }


_HW_COMPANION = {
    "local": "04-hw-validation.md",
    "published_as": "hw-validation.md",
    "purpose": "Hardware qualification",
    "audience": "Hardware QE team",
}

_SEC_COMPANION = {
    "local": "04-security-cert.md",
    "published_as": "security-cert.md",
    "purpose": "Security certification",
    "audience": "Security team",
}


# ===========================================================================
# 1. Schema validation — local index
# ===========================================================================

class TestLocalIndexValidation(unittest.TestCase):
    """Test validate_local_index against production schema."""

    def test_valid_single_testplan(self):
        self.assertEqual(vi.validate_local_index(_make_local_index()), [])

    def test_valid_with_companion(self):
        idx = _make_local_index(companions=[_HW_COMPANION])
        self.assertEqual(vi.validate_local_index(idx), [])

    def test_valid_with_multiple_companions(self):
        idx = _make_local_index(companions=[_HW_COMPANION, _SEC_COMPANION])
        self.assertEqual(vi.validate_local_index(idx), [])

    def test_rejects_unsupported_schema_version(self):
        idx = _make_local_index()
        idx["schema_version"] = "2.0"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("unsupported" in e for e in errors))

    def test_rejects_missing_primary(self):
        idx = _make_local_index()
        del idx["primary_testplan"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("primary_testplan" in e for e in errors))

    def test_rejects_empty_artifacts(self):
        idx = _make_local_index()
        idx["artifacts"] = []
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("non-empty" in e for e in errors))

    def test_rejects_non_testplan_first(self):
        idx = _make_local_index(companions=[_HW_COMPANION])
        idx["artifacts"] = list(reversed(idx["artifacts"]))
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("first artifact" in e for e in errors))

    def test_rejects_duplicate_local(self):
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-testplan.md",
            "published_as": "tp2.md",
            "type": "companion", "purpose": "p", "audience": "a",
        })
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("duplicate local" in e for e in errors))

    def test_rejects_duplicate_published(self):
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-other.md",
            "published_as": "testplan.md",
            "type": "companion", "purpose": "p", "audience": "a",
        })
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("duplicate published" in e for e in errors))

    def test_rejects_companion_without_purpose(self):
        idx = _make_local_index(companions=[_HW_COMPANION])
        del idx["artifacts"][1]["purpose"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("purpose" in e for e in errors))

    def test_rejects_companion_without_audience(self):
        idx = _make_local_index(companions=[_HW_COMPANION])
        del idx["artifacts"][1]["audience"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("audience" in e for e in errors))

    def test_rejects_exactly_two_testplans(self):
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-extra.md",
            "published_as": "extra.md",
            "type": "testplan",
        })
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("exactly one" in e for e in errors))

    def test_rejects_zero_testplans(self):
        idx = _make_local_index()
        idx["artifacts"][0]["type"] = "companion"
        idx["artifacts"][0]["purpose"] = "p"
        idx["artifacts"][0]["audience"] = "a"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("exactly one" in e for e in errors))

    def test_rejects_dict_in_type_field(self):
        idx = _make_local_index()
        idx["artifacts"][0]["type"] = {"nested": True}
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("must be a string" in e for e in errors))

    def test_rejects_list_in_purpose_field(self):
        idx = _make_local_index(companions=[_HW_COMPANION])
        idx["artifacts"][1]["purpose"] = ["list", "val"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("must be a string" in e for e in errors))

    def test_companion_rejects_testplan_md_published_as(self):
        """Companion with published_as=testplan.md → validation error."""
        idx = _make_local_index(companions=[{
            "local": "04-extra.md",
            "published_as": "testplan.md",
            "purpose": "Extra validation",
            "audience": "QE team",
        }])
        errs = vi.validate_local_index(idx)
        reserved = [e for e in errs if "reserved" in e.lower()]
        self.assertTrue(reserved,
                        f"Expected testplan.md reservation error, got: {errs}")


# ===========================================================================
# 2. Path safety
# ===========================================================================

class TestPathSafety(unittest.TestCase):
    """Test filename safety checks used by production validators."""

    def test_rejects_absolute_path(self):
        errors = vi.safe_filename("/etc/passwd", "test")
        self.assertTrue(any("absolute" in e for e in errors))

    def test_rejects_traversal(self):
        errors = vi.safe_filename("../secret.md", "test")
        self.assertTrue(any("traversal" in e for e in errors))

    def test_rejects_slash(self):
        errors = vi.safe_filename("sub/file.md", "test")
        self.assertTrue(any("separator" in e for e in errors))

    def test_rejects_reserved_design_md(self):
        errors = vi.safe_filename("design.md", "test")
        self.assertTrue(any("reserved" in e for e in errors))

    def test_rejects_reserved_validation_index(self):
        errors = vi.safe_filename("validation-index.json", "test")
        self.assertTrue(any("reserved" in e for e in errors))

    def test_rejects_reserved_publish_metadata(self):
        errors = vi.safe_filename("publish-metadata.json", "test")
        self.assertTrue(any("reserved" in e for e in errors))

    def test_accepts_valid_filenames(self):
        for name in ("testplan.md", "hw-validation.md",
                      "04-testplan.md", "04-hw-validation.md"):
            errors = vi.safe_filename(name, "test")
            self.assertEqual(errors, [], f"rejected valid: {name}")

    def test_rejects_whitespace(self):
        errors = vi.safe_filename(" testplan.md ", "test")
        self.assertTrue(any("whitespace" in e for e in errors))

    def test_rejects_non_string(self):
        errors = vi.safe_filename(42, "test")
        self.assertTrue(any("must be a string" in e for e in errors))

    def test_rejects_uppercase_format(self):
        """safe_filename directly rejects non-lowercase filenames."""
        errors = vi.safe_filename("UpperCase.md", "test")
        self.assertTrue(any("lowercase" in e for e in errors),
                        f"Expected format error, got: {errors}")

    def test_accepts_valid_lowercase_format(self):
        """safe_filename accepts valid lowercase filenames."""
        for name in ("testplan.md", "hw-validation.md",
                      "04-testplan.md", "security-cert.md"):
            errors = vi.safe_filename(name, "test")
            self.assertEqual(errors, [], f"rejected valid: {name}")

    def test_reserved_in_full_local_validation(self):
        """Reserved filenames rejected in full local index validation."""
        idx = _make_local_index()
        idx["artifacts"][0]["published_as"] = "design.md"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("reserved" in e for e in errors))


# ===========================================================================
# 3. Published index validation
# ===========================================================================

class TestPublishedIndexValidation(unittest.TestCase):

    def test_valid_single(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"}
            ],
        }
        self.assertEqual(vi.validate_published_index(data), [])

    def test_valid_with_companion(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
                {
                    "file": "hw-validation.md", "type": "companion",
                    "purpose": "HW", "audience": "HW team",
                },
            ],
        }
        self.assertEqual(vi.validate_published_index(data), [])

    def test_rejects_companion_without_audience(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
                {"file": "hw.md", "type": "companion", "purpose": "p"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("audience" in e for e in errors))

    def test_rejects_local_field(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan",
                 "local": "04-testplan.md"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("must not have 'local'" in e for e in errors))

    def test_rejects_primary_mismatch(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "other.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"}
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("must match" in e for e in errors))

    def test_requires_exactly_one_testplan(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "companion",
                 "purpose": "p", "audience": "a"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("exactly one" in e for e in errors))


# ===========================================================================
# 4. CLI: validate subcommand
# ===========================================================================

class TestCLIValidate(unittest.TestCase):
    """Test CLI validate subcommand (production entry point)."""

    def test_valid_local_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            idx = _make_local_index()
            p = Path(td) / "validation-index.json"
            _write_json(p, idx)
            _write(Path(td) / "04-testplan.md", "# Plan")
            r = _run_cli("validate", "--local", str(p),
                         "--artifact-dir", td)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_invalid_local_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "validation-index.json"
            _write_json(p, {"bad": True})
            r = _run_cli("validate", "--local", str(p))
            self.assertEqual(r.returncode, 1)

    def test_missing_file_exits_1(self):
        r = _run_cli("validate", "--local", "/nonexistent/path.json")
        self.assertEqual(r.returncode, 1)

    def test_artifact_dir_missing_file(self):
        """--artifact-dir checks listed files exist."""
        with tempfile.TemporaryDirectory() as td:
            idx = _make_local_index()
            p = Path(td) / "validation-index.json"
            _write_json(p, idx)
            # Don't create 04-testplan.md
            r = _run_cli("validate", "--local", str(p),
                         "--artifact-dir", td)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not found", r.stderr)


# ===========================================================================
# 5. CLI: resolve subcommand
# ===========================================================================

class TestCLIResolve(unittest.TestCase):

    def test_resolve_local_with_index(self):
        with tempfile.TemporaryDirectory() as td:
            idx = _make_local_index()
            _write_json(Path(td) / "validation-index.json", idx)
            _write(Path(td) / "04-testplan.md", "# Plan")
            r = _run_cli("resolve", "--local", td)
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["local"], "04-testplan.md")

    def test_resolve_local_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "04-testplan.md", "# Plan")
            r = _run_cli("resolve", "--local", td)
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["type"], "testplan")

    def test_resolve_local_empty_exits_0(self):
        """Empty directory: exit 0 with [] (success, not error)."""
        with tempfile.TemporaryDirectory() as td:
            r = _run_cli("resolve", "--local", td)
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(arts, [])

    def test_resolve_local_malformed_exits_1(self):
        """Malformed index: exit 1 (error, not empty fallback)."""
        with tempfile.TemporaryDirectory() as td:
            _write_json(Path(td) / "validation-index.json", {"bad": True})
            _write(Path(td) / "04-testplan.md", "# Plan")
            r = _run_cli("resolve", "--local", td)
            self.assertEqual(r.returncode, 1)
            self.assertIn("ERROR", r.stderr)

    def test_resolve_published_with_index(self):
        with tempfile.TemporaryDirectory() as td:
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "HW team"},
                ],
            }
            _write_json(Path(td) / "validation-index.json", pub)
            _write(Path(td) / "testplan.md", "# Plan")
            _write(Path(td) / "hw.md", "# HW")
            r = _run_cli("resolve", "--published", td)
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 2)

    def test_resolve_published_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "testplan.md", "# Plan")
            r = _run_cli("resolve", "--published", td)
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 1)

    def test_resolve_local_missing_listed_file(self):
        """Index lists a file that doesn't exist on disk — error."""
        with tempfile.TemporaryDirectory() as td:
            idx = _make_local_index(companions=[_HW_COMPANION])
            _write_json(Path(td) / "validation-index.json", idx)
            _write(Path(td) / "04-testplan.md", "# Plan")
            # Don't create 04-hw-validation.md
            r = _run_cli("resolve", "--local", td)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not found", r.stderr)


# ===========================================================================
# 6. CLI: transform subcommand
# ===========================================================================

class TestCLITransform(unittest.TestCase):

    def test_transform_single(self):
        with tempfile.TemporaryDirectory() as td:
            local = _make_local_index()
            src = Path(td) / "local.json"
            dst = Path(td) / "published.json"
            _write_json(src, local)
            r = _run_cli("transform", str(src), str(dst))
            self.assertEqual(r.returncode, 0, r.stderr)
            pub = json.loads(dst.read_text())
            self.assertEqual(pub["primary_testplan"], "testplan.md")
            self.assertNotIn("local", pub["artifacts"][0])
            self.assertEqual(pub["artifacts"][0]["file"], "testplan.md")

    def test_transform_with_companion(self):
        with tempfile.TemporaryDirectory() as td:
            local = _make_local_index(companions=[_HW_COMPANION])
            src = Path(td) / "local.json"
            dst = Path(td) / "published.json"
            _write_json(src, local)
            r = _run_cli("transform", str(src), str(dst))
            self.assertEqual(r.returncode, 0, r.stderr)
            pub = json.loads(dst.read_text())
            self.assertEqual(len(pub["artifacts"]), 2)
            c = pub["artifacts"][1]
            self.assertEqual(c["file"], "hw-validation.md")
            self.assertEqual(c["purpose"], "Hardware qualification")

    def test_transformed_passes_published_validation(self):
        local = _make_local_index(companions=[_SEC_COMPANION])
        pub = vi.transform_for_publish(local)
        errors = vi.validate_published_index(pub)
        self.assertEqual(errors, [], f"Validation errors: {errors}")


# ===========================================================================
# 7. CLI: diff subcommand
# ===========================================================================

class TestCLIDiff(unittest.TestCase):

    def test_diff_no_change(self):
        with tempfile.TemporaryDirectory() as td:
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            old_p = Path(td) / "old.json"
            new_p = Path(td) / "new.json"
            _write_json(old_p, pub)
            _write_json(new_p, pub)
            r = _run_cli("diff", str(old_p), str(new_p))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], [])
            self.assertEqual(d["removed"], [])
            self.assertEqual(d["unchanged"], ["testplan.md"])

    def test_diff_added_companion(self):
        with tempfile.TemporaryDirectory() as td:
            old_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "p", "audience": "a"},
                ],
            }
            _write_json(Path(td) / "old.json", old_pub)
            _write_json(Path(td) / "new.json", new_pub)
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["hw.md"])
            self.assertEqual(d["removed"], [])

    def test_diff_removed_companion(self):
        with tempfile.TemporaryDirectory() as td:
            old_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "p", "audience": "a"},
                ],
            }
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", old_pub)
            _write_json(Path(td) / "new.json", new_pub)
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            d = json.loads(r.stdout)
            self.assertEqual(d["removed"], ["hw.md"])


# ===========================================================================
# 8. CLI: build-legacy subcommand
# ===========================================================================

class TestCLIBuildLegacy(unittest.TestCase):

    def test_builds_from_legacy_dir(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "04-testplan.md", "# Plan")
            out = Path(td) / "validation-index.json"
            r = _run_cli("build-legacy", td, str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            idx = json.loads(out.read_text())
            errors = vi.validate_local_index(idx)
            self.assertEqual(errors, [])
            self.assertEqual(idx["primary_testplan"], "04-testplan.md")

    def test_fails_without_testplan(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "index.json"
            r = _run_cli("build-legacy", td, str(out))
            self.assertEqual(r.returncode, 1)


# ===========================================================================
# 9. API: resolve_artifacts (file existence checks)
# ===========================================================================

class TestResolveArtifacts(unittest.TestCase):

    def test_with_index_and_files(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            idx = _make_local_index()
            _write_json(d / "validation-index.json", idx)
            _write(d / "04-testplan.md", "# Plan")
            arts = vi.resolve_artifacts(d)
            self.assertEqual(len(arts), 1)

    def test_rejects_missing_listed_file(self):
        """Index lists a file not on disk → error, not silent fallback."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            idx = _make_local_index(companions=[_HW_COMPANION])
            _write_json(d / "validation-index.json", idx)
            _write(d / "04-testplan.md", "# Plan")
            # 04-hw-validation.md NOT created
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(d)
            self.assertIn("not found", str(ctx.exception))

    def test_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "04-testplan.md", "# Plan")
            arts = vi.resolve_artifacts(Path(td))
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["type"], "testplan")

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            arts = vi.resolve_artifacts(Path(td))
            self.assertEqual(arts, [])

    def test_malformed_index_fails_closed(self):
        """Malformed index is an error, not silent legacy fallback."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_json(d / "validation-index.json", {"bad": True})
            _write(d / "04-testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError):
                vi.resolve_artifacts(d)


# ===========================================================================
# 10. API: resolve_published_artifacts + primary_testplan_path
# ===========================================================================

class TestResolvePublished(unittest.TestCase):
    """Fresh consumer path: discover artifacts from docs repo."""

    def test_with_index(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            _write(d / "testplan.md", "# Plan")
            _write(d / "hw.md", "# HW")
            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(len(arts), 2)

    def test_legacy_single_testplan(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "testplan.md", "# Plan")
            arts = vi.resolve_published_artifacts(Path(td))
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["file"], "testplan.md")

    def test_no_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "design.md", "# Design only")
            arts = vi.resolve_published_artifacts(Path(td))
            self.assertEqual(arts, [])

    def test_primary_path_with_index(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            _write(d / "testplan.md", "# Plan")
            p = vi.primary_testplan_path(d)
            self.assertEqual(p, d / "testplan.md")

    def test_primary_path_malformed_fails_closed(self):
        """Malformed index → error, not silent fallback."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_json(d / "validation-index.json", {"bad": True})
            _write(d / "testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError):
                vi.primary_testplan_path(d)


# ===========================================================================
# 11. diff_published API
# ===========================================================================

class TestDiffPublished(unittest.TestCase):

    def test_identical(self):
        pub = {
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
            ],
        }
        d = vi.diff_published(pub, pub)
        self.assertEqual(d["added"], [])
        self.assertEqual(d["removed"], [])
        self.assertEqual(d["unchanged"], ["testplan.md"])

    def test_add(self):
        old = {"artifacts": [{"file": "testplan.md", "type": "testplan"}]}
        new = {"artifacts": [
            {"file": "testplan.md", "type": "testplan"},
            {"file": "hw.md", "type": "companion"},
        ]}
        d = vi.diff_published(old, new)
        self.assertEqual(d["added"], ["hw.md"])
        self.assertEqual(d["removed"], [])

    def test_remove(self):
        old = {"artifacts": [
            {"file": "testplan.md", "type": "testplan"},
            {"file": "hw.md", "type": "companion"},
        ]}
        new = {"artifacts": [{"file": "testplan.md", "type": "testplan"}]}
        d = vi.diff_published(old, new)
        self.assertEqual(d["removed"], ["hw.md"])

    def test_empty_old(self):
        """First publish — all artifacts are added."""
        new = {"artifacts": [{"file": "testplan.md", "type": "testplan"}]}
        d = vi.diff_published({}, new)
        self.assertEqual(d["added"], ["testplan.md"])
        self.assertEqual(d["removed"], [])


# ===========================================================================
# 12. End-to-end lifecycle: draft → publish → discover → revise
# ===========================================================================

class TestLifecycle(unittest.TestCase):
    """Full lifecycle through CLI and API entry points."""

    def test_single_plan_draft_publish_discover(self):
        """Default single-testplan lifecycle."""
        with tempfile.TemporaryDirectory() as td:
            art_dir = Path(td) / "artifacts"
            docs_dir = Path(td) / "docs" / "v1" / "feature"
            art_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # Draft: build-legacy (simulates draft writing just testplan)
            _write(art_dir / "04-testplan.md", "# Plan\n## TC-FR1-01")
            r = _run_cli("build-legacy", str(art_dir),
                         str(art_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)

            # Publish: transform + copy
            r = _run_cli("transform",
                         str(art_dir / "validation-index.json"),
                         str(docs_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            (docs_dir / "testplan.md").write_text(
                (art_dir / "04-testplan.md").read_text())

            # Fresh consumer discovers
            r = _run_cli("resolve", "--published", str(docs_dir))
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["file"], "testplan.md")

    def test_multi_doc_draft_publish_discover(self):
        """Multi-doc lifecycle with companion."""
        with tempfile.TemporaryDirectory() as td:
            art_dir = Path(td) / "artifacts"
            docs_dir = Path(td) / "docs" / "v1" / "feature"
            art_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # Draft: write testplan + companion + index
            _write(art_dir / "04-testplan.md",
                   "# Plan\n## TC-FR1-01\n## TC-FR1-02")
            _write(art_dir / "04-hw-validation.md",
                   "# HW\n## TC-NFR3-01")
            idx = _make_local_index(companions=[_HW_COMPANION])
            _write_json(art_dir / "validation-index.json", idx)

            # Validate local
            r = _run_cli("validate", "--local",
                         str(art_dir / "validation-index.json"),
                         "--artifact-dir", str(art_dir))
            self.assertEqual(r.returncode, 0, r.stderr)

            # Publish: transform
            r = _run_cli("transform",
                         str(art_dir / "validation-index.json"),
                         str(docs_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)

            for art in idx["artifacts"]:
                (docs_dir / art["published_as"]).write_text(
                    (art_dir / art["local"]).read_text())

            # Fresh consumer discovers both
            r = _run_cli("resolve", "--published", str(docs_dir))
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 2)
            files = {a["file"] for a in arts}
            self.assertEqual(files, {"testplan.md", "hw-validation.md"})

    def test_revise_add_companion(self):
        """Revise: add a companion, diff shows it as added."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = Path(td)
            # Old state: single testplan
            old_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(docs_dir / "old.json", old_pub)

            # New state: testplan + companion
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(docs_dir / "new.json", new_pub)

            r = _run_cli("diff",
                         str(docs_dir / "old.json"),
                         str(docs_dir / "new.json"))
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["hw.md"])
            self.assertEqual(d["removed"], [])

    def test_revise_remove_companion(self):
        """Revise: remove a companion, diff shows it as removed."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = Path(td)
            old_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(docs_dir / "old.json", old_pub)
            _write_json(docs_dir / "new.json", new_pub)
            r = _run_cli("diff",
                         str(docs_dir / "old.json"),
                         str(docs_dir / "new.json"))
            d = json.loads(r.stdout)
            self.assertEqual(d["removed"], ["hw.md"])

    def test_rename_companion(self):
        """Rename appears as add + remove in diff."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = Path(td)
            old_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "device-validation.md", "type": "companion",
                     "purpose": "Device", "audience": "team"},
                ],
            }
            _write_json(docs_dir / "old.json", old_pub)
            _write_json(docs_dir / "new.json", new_pub)
            r = _run_cli("diff",
                         str(docs_dir / "old.json"),
                         str(docs_dir / "new.json"))
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["device-validation.md"])
            self.assertEqual(d["removed"], ["hw.md"])

    def test_downstream_story_selection(self):
        """Downstream consumer discovers artifacts via resolve API.

        Verifies the production resolve_published_artifacts API returns
        the correct artifact list including type metadata.  TC-level
        selection (grep-based heading matching) is performed by the AI
        agent following workflow instructions; this test verifies the
        deterministic discovery contract only.
        """
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            _write(d / "testplan.md",
                   "### FR-1\n#### TC-FR1-01: API test\n"
                   "#### TC-FR1-02: Another")
            _write(d / "hw.md",
                   "### NFR-3\n#### TC-NFR3-01: HW qual")

            # Use production API to resolve artifacts
            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(len(arts), 2)

            # Verify type metadata is preserved for routing
            types = {a["file"]: a["type"] for a in arts}
            self.assertEqual(types["testplan.md"], "testplan")
            self.assertEqual(types["hw.md"], "companion")

            # Verify primary testplan path API
            primary = vi.primary_testplan_path(d)
            self.assertEqual(primary, d / "testplan.md")

    def test_companion_not_named_testplan(self):
        """Companion with non-testplan slug validates and resolves.

        Verifies the production API correctly validates and resolves
        companion artifacts with non-testplan names. Comment routing
        (matching PR comment paths to artifact files) is performed by
        the AI agent using exact full-path matching per workflow
        instructions; this test verifies the deterministic resolution
        contract and companion metadata preservation.
        """
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "security-cert.md", "type": "companion",
                     "purpose": "Cert", "audience": "Sec"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            _write(d / "testplan.md", "# Plan")
            _write(d / "security-cert.md", "# Security")
            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(len(arts), 2)

            # Verify companion metadata is preserved
            companion = [a for a in arts if a["type"] == "companion"][0]
            self.assertEqual(companion["file"], "security-cert.md")
            self.assertEqual(companion["purpose"], "Cert")

            # Verify companion slug 'testplan' is rejected via the
            # companion-slug check — use a DIFFERENT primary so
            # duplicate-local does not trigger first.
            idx = {
                "schema_version": "1.0",
                "primary_testplan": "04-primary.md",
                "artifacts": [
                    {
                        "local": "04-primary.md",
                        "published_as": "primary.md",
                        "type": "testplan",
                    },
                    {
                        "local": "04-testplan.md",
                        "published_as": "testplan-extra.md",
                        "type": "companion",
                        "purpose": "p", "audience": "a",
                    },
                ],
            }
            errors = vi.validate_local_index(idx)
            self.assertTrue(
                any("companion slug must not be 'testplan'" in e
                    for e in errors),
                f"Expected companion-slug error, got: {errors}")

            # Negative control: non-testplan slug passes
            idx["artifacts"][1]["local"] = "04-security.md"
            errors2 = vi.validate_local_index(idx)
            self.assertFalse(
                any("companion slug" in e for e in errors2),
                f"Non-testplan slug should pass, got: {errors2}")


# ===========================================================================
# 13. Safety: symlink rejection
# ===========================================================================

class TestSymlinkRejection(unittest.TestCase):
    """Symlink artifacts are rejected to prevent escape attacks."""

    def test_symlink_local_artifact_rejected(self):
        """Symlink source file in local resolve → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            real = d / "real-testplan.md"
            _write(real, "# Plan")
            link = d / "04-testplan.md"
            link.symlink_to(real)
            idx = _make_local_index()
            _write_json(d / "validation-index.json", idx)
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_symlink_index_rejected(self):
        """Symlink index file in local resolve → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            real_dir = d / "real"
            real_dir.mkdir()
            idx = _make_local_index()
            _write_json(real_dir / "validation-index.json", idx)
            _write(real_dir / "04-testplan.md", "# Plan")
            link = d / "art"
            link.mkdir()
            (link / "validation-index.json").symlink_to(
                real_dir / "validation-index.json")
            _write(link / "04-testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(link)
            self.assertIn("symlink", str(ctx.exception))

    def test_symlink_published_artifact_rejected(self):
        """Symlink file in published resolve → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            real = d / "real-plan.md"
            _write(real, "# Plan")
            link = d / "testplan.md"
            link.symlink_to(real)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_published_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_symlink_legacy_rejected(self):
        """Symlink 04-testplan.md in legacy fallback → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            real = d / "real.md"
            _write(real, "# Plan")
            link = d / "04-testplan.md"
            link.symlink_to(real)
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_primary_path_symlink_rejected(self):
        """Symlink primary testplan in docs repo → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            real = d / "real.md"
            _write(real, "# Plan")
            link = d / "testplan.md"
            link.symlink_to(real)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.primary_testplan_path(d)
            self.assertIn("symlink", str(ctx.exception))


# ===========================================================================
# 13b. Safety: dangling symlinks and directory-as-index
# ===========================================================================

class TestDanglingSymlinkAndDirectory(unittest.TestCase):
    """Dangling symlinks and directories must fail closed, not fall
    through to legacy behavior."""

    def test_dangling_symlink_index_local(self):
        """Dangling symlink validation-index.json → error, not legacy."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "validation-index.json").symlink_to("/nonexistent/target")
            _write(d / "04-testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_dangling_symlink_index_published(self):
        """Dangling symlink validation-index.json in published dir."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "validation-index.json").symlink_to("/nonexistent/target")
            _write(d / "testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_published_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_dangling_symlink_index_primary_path(self):
        """Dangling symlink validation-index.json in primary_testplan_path."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "validation-index.json").symlink_to("/nonexistent/target")
            _write(d / "testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.primary_testplan_path(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_directory_as_index_local(self):
        """Directory named validation-index.json → error, not legacy."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "validation-index.json").mkdir()
            _write(d / "04-testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(d)
            self.assertIn("not a regular file", str(ctx.exception))

    def test_directory_as_index_published(self):
        """Directory named validation-index.json in published dir."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "validation-index.json").mkdir()
            _write(d / "testplan.md", "# Plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_published_artifacts(d)
            self.assertIn("not a regular file", str(ctx.exception))

    def test_dangling_symlink_legacy_local(self):
        """Dangling symlink 04-testplan.md → error, not empty."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "04-testplan.md").symlink_to("/nonexistent/plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))

    def test_dangling_symlink_legacy_published(self):
        """Dangling symlink testplan.md in published dir → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "testplan.md").symlink_to("/nonexistent/plan")
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_published_artifacts(d)
            self.assertIn("symlink", str(ctx.exception))


# ===========================================================================
# 14. Safety: primary_testplan_path errors on missing listed file
# ===========================================================================

class TestPrimaryTestplanPath(unittest.TestCase):
    """primary_testplan_path raises on missing listed primary."""

    def test_listed_primary_missing_raises(self):
        """Index valid but primary file missing → error, not None."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            # Don't create testplan.md
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.primary_testplan_path(d)
            self.assertIn("not found", str(ctx.exception))

    def test_no_artifacts_returns_none(self):
        """No index and no legacy file → None (not error)."""
        with tempfile.TemporaryDirectory() as td:
            result = vi.primary_testplan_path(Path(td))
            self.assertIsNone(result)


# ===========================================================================
# 15. Safety: resolve_published verifies file existence
# ===========================================================================

class TestPublishedFileExistence(unittest.TestCase):
    """resolve_published_artifacts verifies listed files exist."""

    def test_missing_published_file_raises(self):
        """Published index lists file that doesn't exist → error."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(d / "validation-index.json", pub)
            _write(d / "testplan.md", "# Plan")
            # Don't create hw.md
            with self.assertRaises(vi.ValidationIndexError) as ctx:
                vi.resolve_published_artifacts(d)
            self.assertIn("not found", str(ctx.exception))


# ===========================================================================
# 16. Safety: published index first-artifact ordering
# ===========================================================================

class TestPublishedOrdering(unittest.TestCase):
    """Published index must have testplan as first artifact."""

    def test_companion_first_rejected(self):
        """Published index with companion first → validation error."""
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "hw.md", "type": "companion",
                 "purpose": "HW", "audience": "team"},
                {"file": "testplan.md", "type": "testplan"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("first artifact" in e for e in errors))


# ===========================================================================
# 17. cmd_diff input validation
# ===========================================================================

class TestDiffValidation(unittest.TestCase):
    """cmd_diff validates inputs before diffing."""

    def test_diff_rejects_non_object(self):
        """Non-object input → error exit."""
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "old.json", '"just a string"')
            _write_json(Path(td) / "new.json",
                        {"artifacts": []})
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("must be a JSON object", r.stderr)

    def test_diff_rejects_unsafe_filename(self):
        """Unsafe filename in artifact → error exit."""
        with tempfile.TemporaryDirectory() as td:
            old = {"artifacts": [
                {"file": "../escape.md", "type": "testplan"},
            ]}
            new = {"artifacts": [
                {"file": "testplan.md", "type": "testplan"},
            ]}
            _write_json(Path(td) / "old.json", old)
            _write_json(Path(td) / "new.json", new)
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("traversal", r.stderr)


# ===========================================================================
# 18. Filename safety: control characters
# ===========================================================================

class TestControlCharSafety(unittest.TestCase):
    """safe_filename rejects control characters and null bytes."""

    def test_null_byte(self):
        errors = vi.safe_filename("test\x00.md", "test")
        self.assertTrue(any("control" in e for e in errors))

    def test_tab(self):
        errors = vi.safe_filename("test\t.md", "test")
        self.assertTrue(any("control" in e for e in errors))


# ===========================================================================
# 19. Filename format validation (allowlist regexes)
# ===========================================================================

class TestFilenameFormatValidation(unittest.TestCase):
    """_SAFE_FILENAME_RE and _LOCAL_FILENAME_RE are now enforced."""

    def test_local_filename_format_rejected(self):
        """Local artifact with bad format → validation error."""
        idx = _make_local_index()
        idx["artifacts"][0]["local"] = "Testplan.MD"
        idx["artifacts"][0]["published_as"] = "testplan.md"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("04-" in e for e in errors),
                        f"Expected 04-slug convention error, got: {errors}")

    def test_published_filename_format_rejected(self):
        """Published filename with bad format → validation error."""
        data = {
            "schema_version": "1.0",
            "primary_testplan": "Test Plan.md",
            "artifacts": [
                {"file": "Test Plan.md", "type": "testplan"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("lowercase" in e for e in errors),
                        f"Expected format error, got: {errors}")

    def test_valid_local_format_accepted(self):
        """Valid 04-slug.md format passes."""
        idx = _make_local_index()
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_valid_published_format_accepted(self):
        """Valid lowercase-with-hyphens.ext passes."""
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertEqual(errors, [])


# ===========================================================================
# 20. cmd_validate symlink rejection
# ===========================================================================

class TestCLIValidateSymlinks(unittest.TestCase):
    """cmd_validate rejects symlinked index files."""

    def test_symlinked_index_file_rejected(self):
        """Symlink index file → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "real-index.json"
            _write_json(real, _make_local_index())
            link = Path(td) / "link-index.json"
            link.symlink_to(real)
            r = _run_cli("validate", "--local", str(link))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())

    def test_symlinked_artifact_dir_file_rejected(self):
        """Symlink artifact in --artifact-dir → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            idx = _make_local_index()
            _write_json(Path(td) / "validation-index.json", idx)
            real = Path(td) / "real-plan.md"
            _write(real, "# Plan")
            link = Path(td) / "04-testplan.md"
            link.symlink_to(real)
            r = _run_cli("validate", "--local",
                         str(Path(td) / "validation-index.json"),
                         "--artifact-dir", td)
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())


# ===========================================================================
# 21. Safe output writes
# ===========================================================================

class TestSafeOutputWrites(unittest.TestCase):
    """cmd_transform/cmd_build_legacy reject symlink outputs."""

    def test_transform_rejects_symlink_output(self):
        """Symlink output path → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            real = Path(td) / "real-output.json"
            _write(real, "{}")
            link = Path(td) / "link-output.json"
            link.symlink_to(real)
            r = _run_cli("transform", str(src), str(link))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())

    def test_build_legacy_rejects_symlink_output(self):
        """Symlink output path → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "04-testplan.md", "# Plan")
            real = Path(td) / "real-output.json"
            _write(real, "{}")
            link = Path(td) / "link-output.json"
            link.symlink_to(real)
            r = _run_cli("build-legacy", td, str(link))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())


# ===========================================================================
# 22. cmd_diff published schema validation
# ===========================================================================

class TestDiffSchemaValidation(unittest.TestCase):
    """cmd_diff validates both inputs as published indexes."""

    def _valid_pub(self):
        return {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
            ],
        }

    def test_diff_missing_file_exits_1(self):
        """diff with missing file → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "nonexistent.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("not found", r.stderr)

    def test_diff_rejects_null_file_in_artifact(self):
        """file: null in artifact → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            bad = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": None, "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", bad)
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("ERROR", r.stderr)

    def test_diff_rejects_local_format_fields(self):
        """Published index with 'local' field → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            bad = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan",
                     "local": "04-testplan.md"},
                ],
            }
            _write_json(Path(td) / "old.json", bad)
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("must not have 'local'", r.stderr)

    def test_diff_rejects_malformed_schema_version(self):
        """Malformed schema_version → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            bad = {
                "schema_version": "99.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", self._valid_pub())
            _write_json(Path(td) / "new.json", bad)
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("unsupported", r.stderr)

    def test_diff_allows_intentional_empty_old(self):
        """Intentional empty old {} → exit 0 (first-publish case)."""
        with tempfile.TemporaryDirectory() as td:
            _write_json(Path(td) / "old.json", {})
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["testplan.md"])

    def test_diff_allows_intentional_empty_artifacts_old(self):
        """Intentional empty old {"artifacts": []} → exit 0."""
        with tempfile.TemporaryDirectory() as td:
            _write_json(Path(td) / "old.json", {"artifacts": []})
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["testplan.md"])

    def test_diff_rejects_non_string_file(self):
        """Non-string file in artifact → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            bad = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": 42, "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", bad)
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)

    def test_diff_rejects_missing_primary(self):
        """Published index with missing primary_testplan → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            bad = {
                "schema_version": "1.0",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", bad)
            _write_json(Path(td) / "new.json", self._valid_pub())
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("primary_testplan", r.stderr)


# ===========================================================================
# 23. Parent-symlink and write-safety regressions
# ===========================================================================

class TestSafeWriteParentSymlink(unittest.TestCase):
    """_safe_write_output rejects symlink parents and symlink targets."""

    def test_transform_rejects_parent_symlink_outside(self):
        """Output parent is symlink to outside temp dir → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            with tempfile.TemporaryDirectory() as outside:
                src = Path(td) / "local.json"
                _write_json(src, _make_local_index())
                link_dir = Path(td) / "escaped"
                link_dir.symlink_to(outside)
                dst = link_dir / "output.json"
                r = _run_cli("transform", str(src), str(dst))
                self.assertEqual(r.returncode, 1)
                self.assertIn("symlink", r.stderr.lower())
                # Verify nothing was written outside
                self.assertFalse((Path(outside) / "output.json").exists())

    def test_build_legacy_rejects_parent_symlink_outside(self):
        """build-legacy output parent is symlink → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            with tempfile.TemporaryDirectory() as outside:
                _write(Path(td) / "04-testplan.md", "# Plan")
                link_dir = Path(td) / "escaped"
                link_dir.symlink_to(outside)
                dst = link_dir / "output.json"
                r = _run_cli("build-legacy", td, str(dst))
                self.assertEqual(r.returncode, 1)
                self.assertIn("symlink", r.stderr.lower())
                self.assertFalse((Path(outside) / "output.json").exists())

    def test_build_legacy_rejects_symlink_testplan(self):
        """build-legacy with symlinked 04-testplan.md → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "real.md"
            _write(real, "# Plan")
            link = Path(td) / "04-testplan.md"
            link.symlink_to(real)
            out = Path(td) / "index.json"
            r = _run_cli("build-legacy", td, str(out))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())

    def test_transform_rejects_symlink_final_target(self):
        """Output path is a symlink to a real file → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            real = Path(td) / "real-output.json"
            _write(real, "{}")
            link = Path(td) / "link-output.json"
            link.symlink_to(real)
            r = _run_cli("transform", str(src), str(link))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())

    def test_transform_rejects_ancestor_symlink_with_nonexistent_child(self):
        """Ancestor symlink with nonexistent descendant → exit 1.

        Tests the case where output is link/nonexistent/output.json
        and link→outside.  The walk must NOT stop at the nonexistent
        intermediate — it must continue upward and catch the symlink.
        """
        with tempfile.TemporaryDirectory() as td:
            with tempfile.TemporaryDirectory() as outside:
                src = Path(td) / "local.json"
                _write_json(src, _make_local_index())
                link = Path(td) / "link"
                link.symlink_to(outside)
                # Output: link/nonexistent/output.json
                dst = link / "nonexistent" / "output.json"
                r = _run_cli("transform", str(src), str(dst))
                self.assertEqual(r.returncode, 1)
                self.assertIn("symlink", r.stderr.lower())
                # Nothing created outside
                self.assertEqual(
                    list(Path(outside).iterdir()), [],
                    "No files/dirs should be created at outside target")

    def test_build_legacy_rejects_ancestor_symlink_with_nonexistent_child(self):
        """build-legacy: ancestor symlink + nonexistent child → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            with tempfile.TemporaryDirectory() as outside:
                _write(Path(td) / "04-testplan.md", "# Plan")
                link = Path(td) / "link"
                link.symlink_to(outside)
                dst = link / "deep" / "output.json"
                r = _run_cli("build-legacy", td, str(dst))
                self.assertEqual(r.returncode, 1)
                self.assertIn("symlink", r.stderr.lower())
                self.assertEqual(
                    list(Path(outside).iterdir()), [],
                    "No files/dirs should be created at outside target")

    def test_transform_input_read_error(self):
        """Unreadable input → exit 1 with ERROR, no traceback.

        Calls cmd_transform directly with mocked Path.read_text
        OSError — portable to privileged runners.
        """
        import argparse as _argparse
        import io
        import unittest.mock
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = Path(td) / "output.json"
            original_read = Path.read_text
            def failing_read(self_path, *a, **kw):
                if str(self_path) == str(src):
                    raise OSError("Permission denied")
                return original_read(self_path, *a, **kw)
            err = io.StringIO()
            with unittest.mock.patch.object(Path, "read_text",
                                            failing_read), \
                 unittest.mock.patch("sys.stderr", err):
                ns = _argparse.Namespace(
                    local_index=str(src), output=str(dst),
                    trusted_output_base=None)
                rc = vi.cmd_transform(ns)
            self.assertEqual(rc, 1)
            self.assertIn("ERROR", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    def test_transform_trusted_base_allows_ancestor_symlink(self):
        """--trusted-output-base: symlink above base is permitted."""
        with tempfile.TemporaryDirectory() as td:
            real_dir = Path(td) / "real"
            real_dir.mkdir()
            link = Path(td) / "via_link"
            link.symlink_to(real_dir)
            docs = real_dir / "docs"
            docs.mkdir()
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = link / "docs" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(link / "docs"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((real_dir / "docs" / "output.json").exists())

    def test_transform_trusted_base_rejects_symlink_below(self):
        """--trusted-output-base: symlink BELOW base still rejected.

        The symlink resolves outside the base, so the guard may report
        either 'symlink' or 'escapes trusted base' — both are correct.
        """
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            outside = Path(td) / "outside"
            outside.mkdir()
            (base / "escape").symlink_to(outside)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = base / "escape" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)
            err = r.stderr.lower()
            self.assertTrue(
                "symlink" in err or "escape" in err,
                f"Expected symlink or escape error, got: {r.stderr}")

    def test_transform_trusted_base_rejects_internal_symlink(self):
        """--trusted-output-base: symlink inside base to another dir
        inside base still rejected by the ancestor walk."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            target = base / "realdir"
            target.mkdir()
            (base / "linked").symlink_to(target)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            # linked → realdir (both under base), but it's still a
            # symlink component below the trusted base — rejected.
            dst = base / "linked" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())

    def test_transform_trusted_base_rejects_escape(self):
        """--trusted-output-base: output outside base is rejected."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            outside = Path(td) / "elsewhere"
            outside.mkdir()
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = outside / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)
            self.assertIn("escape", r.stderr.lower())

    def test_transform_no_trusted_base_rejects_ancestor_symlink(self):
        """Without --trusted-output-base, ancestor symlinks rejected."""
        with tempfile.TemporaryDirectory() as td:
            real_dir = Path(td) / "real"
            real_dir.mkdir()
            link = Path(td) / "via_link"
            link.symlink_to(real_dir)
            (real_dir / "sub").mkdir()
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = link / "sub" / "output.json"
            r = _run_cli("transform", str(src), str(dst))
            self.assertEqual(r.returncode, 1)
            self.assertIn("symlink", r.stderr.lower())


# ===========================================================================
# 23c. Trusted-base self-link regression (lexical boundary)
# ===========================================================================

class TestTrustedBaseSelfLink(unittest.TestCase):
    """Trusted-base guard rejects symlink components below base even
    when they resolve to the base itself (lexical boundary, not
    resolved identity)."""

    def test_selflink_to_base_rejected(self):
        """base/selflink → base; output under selflink → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = base / "selflink" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1,
                             "selflink to base must be rejected")
            err = r.stderr.lower()
            self.assertTrue("symlink" in err or "escape" in err,
                            f"Expected symlink/escape error, got: {r.stderr}")
            self.assertFalse(dst.exists(),
                             "No output should be written through selflink")

    def test_selflink_subdirs_rejected(self):
        """base/selflink/subdir/output.json → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = base / "selflink" / "subdir" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)
            err = r.stderr.lower()
            self.assertTrue("symlink" in err or "escape" in err,
                            f"Expected symlink/escape diagnostic: {r.stderr}")
            self.assertFalse(dst.exists(),
                             "No output through symlink subdir")

    def test_nonexistent_under_selflink_rejected(self):
        """base/selflink/nonexistent/output.json → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = base / "selflink" / "nonexistent" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)
            err = r.stderr.lower()
            self.assertTrue("symlink" in err or "escape" in err,
                            f"Expected symlink/escape diagnostic: {r.stderr}")
            self.assertFalse(dst.exists(),
                             "No output through symlink path")

    def test_build_legacy_selflink_rejected(self):
        """build-legacy --trusted-output-base also rejects selflink."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            _write(Path(td) / "04-testplan.md", "# Plan")
            dst = base / "selflink" / "output.json"
            r = _run_cli("build-legacy", td, str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)

    def test_regular_subdir_under_base_allowed(self):
        """base/realdir/output.json → exit 0 (no symlinks)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "realdir").mkdir()
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = base / "realdir" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(dst.exists())

    def test_internal_link_to_sibling_under_base_rejected(self):
        """base/link → base/other; output under link → exit 1.
        Internal symlinks below the base are still rejected."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "other").mkdir()
            (base / "link").symlink_to(base / "other")
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = base / "link" / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base", str(base))
            self.assertEqual(r.returncode, 1)

    def test_mixed_form_relative_output_absolute_base_rejected(self):
        """Relative output + absolute trusted base: selflink rejected.

        Exercises the normalization path — both forms must be
        compared as absolute paths to detect the symlink."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            # Run from base, output relative, trusted base absolute
            r = subprocess.run(
                [sys.executable, str(_SCRIPT), "transform",
                 str(src), "selflink/output.json",
                 "--trusted-output-base", str(base)],
                capture_output=True, text=True, timeout=10,
                cwd=str(base))
            self.assertEqual(r.returncode, 1,
                             f"Mixed form must reject selflink: {r.stderr}")
            self.assertFalse(
                (base / "selflink" / "output.json").exists())

    def test_mixed_form_absolute_output_relative_base_rejected(self):
        """Absolute output + relative trusted base: selflink rejected."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            r = subprocess.run(
                [sys.executable, str(_SCRIPT), "transform",
                 str(src), str(base / "selflink" / "output.json"),
                 "--trusted-output-base", "."],
                capture_output=True, text=True, timeout=10,
                cwd=str(base))
            self.assertEqual(r.returncode, 1,
                             f"Mixed form must reject selflink: {r.stderr}")
            self.assertFalse(
                (base / "selflink" / "output.json").exists())

    def test_mixed_form_positive_relative_base_allowed(self):
        """Relative base + absolute output under base: no symlink → ok."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "realdir").mkdir()
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            r = subprocess.run(
                [sys.executable, str(_SCRIPT), "transform",
                 str(src), str(base / "realdir" / "output.json"),
                 "--trusted-output-base", "."],
                capture_output=True, text=True, timeout=10,
                cwd=str(base))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(
                (base / "realdir" / "output.json").exists())

    def test_build_legacy_mixed_form_rejected(self):
        """build-legacy: relative output + absolute base rejects selflink."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base"
            base.mkdir()
            (base / "selflink").symlink_to(base)
            _write(base / "04-testplan.md", "# Plan")
            r = subprocess.run(
                [sys.executable, str(_SCRIPT), "build-legacy",
                 str(base), "selflink/output.json",
                 "--trusted-output-base", str(base)],
                capture_output=True, text=True, timeout=10,
                cwd=str(base))
            self.assertEqual(r.returncode, 1,
                             f"build-legacy mixed form must reject: {r.stderr}")

    def test_trusted_base_must_be_existing_dir(self):
        """Non-existent trusted base → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            dst = Path(td) / "output.json"
            r = _run_cli("transform", str(src), str(dst),
                         "--trusted-output-base",
                         str(Path(td) / "nonexistent"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("not an existing directory", r.stderr)


# ===========================================================================
# 23d. O_NOFOLLOW absence: fail closed
# ===========================================================================

class TestNoFollowAbsence(unittest.TestCase):
    """When O_NOFOLLOW is unavailable, _safe_write_output must fail
    closed — no file creation, no truncation, no writes."""

    def test_missing_nofollow_rejects_write(self):
        """Mock absent O_NOFOLLOW → exit 1, no file created."""
        import io
        import os as _os
        import unittest.mock
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "output.json"
            # Temporarily remove O_NOFOLLOW from the os module
            original = getattr(_os, 'O_NOFOLLOW', None)
            if original is not None:
                delattr(_os, 'O_NOFOLLOW')
            try:
                err = io.StringIO()
                with unittest.mock.patch("sys.stderr", err):
                    rc = vi._safe_write_output(dst, '{"test": true}\n')
                self.assertEqual(rc, 1,
                                 "Must fail when O_NOFOLLOW unavailable")
                self.assertIn("O_NOFOLLOW", err.getvalue())
                self.assertFalse(dst.exists(),
                                 "No file should be created")
            finally:
                if original is not None:
                    _os.O_NOFOLLOW = original

    def test_with_nofollow_writes_normally(self):
        """Positive: O_NOFOLLOW present → successful write."""
        import os as _os
        if not hasattr(_os, 'O_NOFOLLOW'):
            self.skipTest("O_NOFOLLOW not available")
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())  # Canonicalize (macOS /var → /private/var)
            dst = Path(td) / "output.json"
            rc = vi._safe_write_output(dst, '{"test": true}\n')
            self.assertEqual(rc, 0)
            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_text(), '{"test": true}\n')


# ===========================================================================
# 24. CLI workflow sequence regressions
# ===========================================================================

class TestCLIWorkflowSequence(unittest.TestCase):
    """CLI-level workflow sequences matching instruction-driven paths."""

    def test_legacy_to_published_lifecycle(self):
        """04-testplan.md only → build-legacy → transform → validate
        published → resolve published from fresh docs dir.

        Exercises the actual CLI consumer sequence: legacy artifact
        directory without validation-index.json, then full publication
        path through CLI subcommands."""
        with tempfile.TemporaryDirectory() as td:
            art_dir = Path(td) / "artifacts"
            docs_dir = Path(td) / "docs" / "v1" / "feature"
            art_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # Legacy directory: only 04-testplan.md, no index
            _write(art_dir / "04-testplan.md", "# Plan\n## TC-FR1-01")

            # Step 1: resolve → NON-EMPTY but index absent
            r = _run_cli("resolve", "--local", str(art_dir))
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 1,
                             "Legacy fallback should return 1 artifact")
            self.assertFalse(
                (art_dir / "validation-index.json").exists(),
                "Index should NOT exist yet")

            # Step 2: build-legacy
            r = _run_cli("build-legacy", str(art_dir),
                         str(art_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(
                (art_dir / "validation-index.json").exists())

            # Step 3: transform → published format
            r = _run_cli("transform",
                         str(art_dir / "validation-index.json"),
                         str(docs_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)

            # Step 4: copy artifact
            (docs_dir / "testplan.md").write_text(
                (art_dir / "04-testplan.md").read_text())

            # Step 5: validate published
            r = _run_cli("validate", "--published",
                         str(docs_dir / "validation-index.json"),
                         "--feature-dir", str(docs_dir))
            self.assertEqual(r.returncode, 0, r.stderr)

            # Step 6: resolve published from fresh docs dir
            r = _run_cli("resolve", "--published", str(docs_dir))
            self.assertEqual(r.returncode, 0, r.stderr)
            pub_arts = json.loads(r.stdout)
            self.assertEqual(len(pub_arts), 1)
            self.assertEqual(pub_arts[0]["file"], "testplan.md")

    def test_artifact_set_transition(self):
        """Published single → add companion (new index) → diff shows
        added companion.

        Exercises the revise path: existing published state transitions
        to a multi-artifact set via diff."""
        with tempfile.TemporaryDirectory() as td:
            # Old published state: single testplan
            old_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            # New published state: testplan + companion
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw-validation.md", "type": "companion",
                     "purpose": "HW qual", "audience": "HW team"},
                ],
            }
            _write_json(Path(td) / "old.json", old_pub)
            _write_json(Path(td) / "new.json", new_pub)

            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["hw-validation.md"])
            self.assertEqual(d["removed"], [])
            self.assertEqual(d["unchanged"], ["testplan.md"])

    def test_invalid_previous_snapshot_guard(self):
        """Malformed prev index → diff rejects before computing changes.

        Ensures that a corrupted snapshot captured during publish
        cannot silently produce wrong removal lists."""
        with tempfile.TemporaryDirectory() as td:
            # Malformed: missing schema_version, wrong type
            malformed_prev = {
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            valid_new = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", malformed_prev)
            _write_json(Path(td) / "new.json", valid_new)
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1,
                             "Malformed snapshot must be rejected")
            self.assertIn("ERROR", r.stderr)

    def test_first_publish_empty_old(self):
        """First publish: empty old {} → diff shows all as added.

        The first publish has no prior published state, so cmd_diff
        receives an intentionally empty old index."""
        with tempfile.TemporaryDirectory() as td:
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "p", "audience": "a"},
                ],
            }
            _write_json(Path(td) / "old.json", {})
            _write_json(Path(td) / "new.json", new_pub)
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertIn("testplan.md", d["added"])
            self.assertIn("hw.md", d["added"])
            self.assertEqual(d["removed"], [])

    def test_diff_rejects_empty_new_index(self):
        """Empty new {} → exit 1 to prevent mass deletion."""
        with tempfile.TemporaryDirectory() as td:
            valid = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", valid)
            _write_json(Path(td) / "new.json", {})
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1,
                             "Empty new index must be rejected")

    def test_diff_rejects_empty_artifacts_new_index(self):
        """Empty new {"artifacts": []} → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            valid = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "old.json", valid)
            _write_json(Path(td) / "new.json", {"artifacts": []})
            r = _run_cli("diff",
                         str(Path(td) / "old.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1,
                             "Empty new index must be rejected")


# ===========================================================================
# 25. Atomic writer regression tests
# ===========================================================================

class TestAtomicWriterRegressions(unittest.TestCase):
    """Atomic write safety for _safe_write_output.

    Exercises the documented atomic-write contract:
    - Partial write + exception leaves destination intact, temp cleaned
    - Successful write replaces with correct content and preserves mode
    - Replace failure leaves destination intact, temp cleaned
    - CLI subcommands (transform/build-legacy) still work end-to-end
    """

    def test_successful_write_correct_content(self):
        """Atomic write produces correct content at destination."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dst = Path(td) / "output.json"
            content = '{"test": true}\n'
            rc = vi._safe_write_output(dst, content)
            self.assertEqual(rc, 0)
            self.assertEqual(dst.read_text(encoding="utf-8"), content)

    def test_successful_write_preserves_existing_mode(self):
        """Atomic replacement preserves the existing file's mode."""
        import os as _os
        import stat as _stat
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dst = Path(td) / "output.json"
            dst.write_text("{}", encoding="utf-8")
            _os.chmod(str(dst), 0o600)
            rc = vi._safe_write_output(dst, '{"updated": true}\n')
            self.assertEqual(rc, 0)
            mode = _stat.S_IMODE(_os.stat(str(dst)).st_mode)
            self.assertEqual(mode, 0o600,
                             "Replacement must preserve 0o600 mode")
            self.assertEqual(dst.read_text(encoding="utf-8"),
                             '{"updated": true}\n')

    def test_new_file_respects_umask_077(self):
        """New file with umask 077 gets 0o600."""
        import os as _os
        import stat as _stat
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dst = Path(td) / "new-output.json"
            old_umask = _os.umask(0o077)
            try:
                rc = vi._safe_write_output(dst, '{"new": true}\n')
            finally:
                _os.umask(old_umask)
            self.assertEqual(rc, 0)
            mode = _stat.S_IMODE(_os.stat(str(dst)).st_mode)
            self.assertEqual(mode, 0o600,
                             "New file with umask 077 must get 0o600")

    def test_new_file_respects_umask_027(self):
        """New file with umask 027 gets 0o640."""
        import os as _os
        import stat as _stat
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dst = Path(td) / "new-output.json"
            old_umask = _os.umask(0o027)
            try:
                rc = vi._safe_write_output(dst, '{"new": true}\n')
            finally:
                _os.umask(old_umask)
            self.assertEqual(rc, 0)
            mode = _stat.S_IMODE(_os.stat(str(dst)).st_mode)
            self.assertEqual(mode, 0o640,
                             "New file with umask 027 must get 0o640")

    def test_rejects_fifo_destination(self):
        """FIFO at destination is rejected before write."""
        import os as _os
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            fifo_path = Path(td) / "output.json"
            _os.mkfifo(str(fifo_path))
            rc = vi._safe_write_output(fifo_path, '{"test": true}\n')
            self.assertEqual(rc, 1, "FIFO destination must be rejected")

    def test_rejects_directory_destination(self):
        """Directory at destination is rejected before write."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dir_path = Path(td) / "output.json"
            dir_path.mkdir()
            rc = vi._safe_write_output(dir_path, '{"test": true}\n')
            self.assertEqual(rc, 1, "Directory destination must be rejected")

    def test_partial_write_then_failure_preserves_destination(self):
        """Short write + subsequent failure: old bytes/mode intact, temp gone."""
        import os as _os
        import stat as _stat
        import unittest.mock as _mock
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dst = Path(td) / "output.json"
            original = '{"original": true}\n'
            dst.write_text(original, encoding="utf-8")
            _os.chmod(str(dst), 0o640)
            orig_mode = _stat.S_IMODE(_os.stat(str(dst)).st_mode)

            # First os.write call: short write (only 5 bytes), so the
            # loop iterates.  Second call: raise to simulate I/O failure.
            real_write = _os.write
            call_count = [0]

            def partial_then_fail(fd, data):
                call_count[0] += 1
                if call_count[0] == 1:
                    return real_write(fd, data[:5])
                raise OSError("simulated write failure after partial")

            with _mock.patch("os.write", side_effect=partial_then_fail):
                rc = vi._safe_write_output(dst, '{"should not appear"}\n')

            self.assertGreaterEqual(call_count[0], 2,
                                    "Must attempt at least two writes")
            self.assertEqual(rc, 1, "Must return error code")
            self.assertEqual(dst.read_text(encoding="utf-8"), original,
                             "Destination bytes must be unchanged")
            self.assertEqual(
                _stat.S_IMODE(_os.stat(str(dst)).st_mode), orig_mode,
                "Destination mode must be unchanged")
            # Temp file must be cleaned up
            temps = [f for f in Path(td).iterdir()
                     if f.name.startswith(".tmp_vi_")]
            self.assertEqual(len(temps), 0,
                             "Temp file must be cleaned up on failure")

    def test_replace_failure_preserves_destination(self):
        """If os.replace fails, destination and mode unchanged, temp gone."""
        import os as _os
        import stat as _stat
        import unittest.mock as _mock
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            dst = Path(td) / "output.json"
            original = '{"original": true}\n'
            dst.write_text(original, encoding="utf-8")
            _os.chmod(str(dst), 0o640)
            orig_mode = _stat.S_IMODE(_os.stat(str(dst)).st_mode)

            real_replace = _os.replace

            def failing_replace(src, dst_path):
                raise OSError("simulated replace failure")

            with _mock.patch("os.replace", side_effect=failing_replace):
                rc = vi._safe_write_output(dst, '{"should not appear"}\n')

            self.assertEqual(rc, 1, "Must return error code")
            self.assertEqual(dst.read_text(encoding="utf-8"), original,
                             "Destination bytes must be unchanged")
            self.assertEqual(
                _stat.S_IMODE(_os.stat(str(dst)).st_mode), orig_mode,
                "Destination mode must be unchanged")
            temps = [f for f in Path(td).iterdir()
                     if f.name.startswith(".tmp_vi_")]
            self.assertEqual(len(temps), 0,
                             "Temp file must be cleaned up on replace failure")

    def test_cli_transform_still_works(self):
        """transform CLI uses atomic writer end-to-end."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            src = Path(td) / "local.json"
            _write_json(src, _make_local_index())
            out = Path(td) / "published.json"
            r = _run_cli("transform", str(src), str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(out.read_text())
            self.assertIn("schema_version", data)

    def test_cli_build_legacy_still_works(self):
        """build-legacy CLI uses atomic writer end-to-end."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            _write(Path(td) / "04-testplan.md", "# Plan\n## TC-FR1-01")
            out = Path(td) / "validation-index.json"
            r = _run_cli("build-legacy", td, str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(out.read_text())
            self.assertEqual(len(data["artifacts"]), 1)


# ===========================================================================
# 26. TC confirmation binding contract (static document test)
# ===========================================================================

class TestTCConfirmationBindingContract(unittest.TestCase):
    """Static contract test for TC confirmation binding.

    Validates the documented SHA-256 confirmation contract that both
    the e2e and implement workflows use: when a user confirms retained
    TCs from an unverified testplan, the confirmation records the
    SHA-256 of the testplan bytes. Later consumers compare this hash
    to detect content changes from re-ingestion.

    This is a STATIC document contract test — it exercises the SHA-256
    computation and comparison that the workflow instructions prescribe,
    not live AI agent behavior.

    NOT tested (requires live AI agents):
    - Actual agent reading plan markdown and extracting confirmation
    - Agent re-prompting users when hash differs
    """

    def test_source_authority_clauses_in_consumers(self):
        """Consumer files contain mutually exclusive authority clauses.

        Reads the actual workflow markdown and verifies each consumer
        has all three authority cases (unresolved-source, unverified,
        authoritative) in the correct exclusive order — unresolved
        checked first, authoritative last."""
        consumers = [
            "implement/skills/validate.md",
            "implement/skills/code.md",
            "e2e/skills/validate.md",
            "e2e/skills/code.md",
        ]
        repo_root = Path(__file__).resolve().parent.parent.parent
        for rel in consumers:
            text = (repo_root / rel).read_text(encoding="utf-8")
            # All three authority states must be documented
            self.assertIn("unresolved-source", text,
                          f"{rel} must handle unresolved-source marker")
            self.assertIn("Freshness: unverified", text,
                          f"{rel} must handle retained unverified plans")
            self.assertIn("authoritative", text,
                          f"{rel} must define authoritative source path")
            # unresolved-source must appear before the authoritative
            # clause to prevent misrouting
            unresolved_pos = text.index("unresolved-source")
            auth_pos = text.index("authoritative")
            self.assertLess(unresolved_pos, auth_pos,
                            f"{rel}: unresolved-source must be checked "
                            f"before authoritative clause")

    def test_per_tc_confirmation_in_code_consumers(self):
        """Code skills require per-TC confirmation for retained plans.

        Verifies the actual code.md files contain per-TC confirmed
        list checking (not just file-level hash) and that authoritative
        plans skip this check."""
        consumers = [
            "implement/skills/code.md",
            "e2e/skills/code.md",
        ]
        repo_root = Path(__file__).resolve().parent.parent.parent
        import re as _re
        for rel in consumers:
            text = (repo_root / rel).read_text(encoding="utf-8")
            normalized = _re.sub(r'\s+', ' ', text.lower())
            # Per-TC check must be conditional on retained testplans
            self.assertIn("retained testplans only", normalized,
                          f"{rel} must scope per-TC check to retained")
            # Authoritative plans must skip the per-TC check
            self.assertIn("authoritative testplans", normalized,
                          f"{rel} must define authoritative skip")
            self.assertIn("confirmed list", normalized,
                          f"{rel} must reference the confirmed TC list")

    def test_stale_hash_clauses_in_consumers(self):
        """Consumer files treat stale SHA-256 hash as unconfirmed.

        Reads actual consumer files and verifies each contains the
        specific clause that a differing hash invalidates confirmation
        — distinct from the missing-binding check."""
        consumers = [
            "implement/skills/validate.md",
            "implement/skills/code.md",
            "e2e/skills/validate.md",
            "e2e/skills/code.md",
        ]
        repo_root = Path(__file__).resolve().parent.parent.parent
        import re as _re
        for rel in consumers:
            text = (repo_root / rel).read_text(encoding="utf-8")
            normalized = _re.sub(r'\s+', ' ', text.lower())
            self.assertTrue(
                "hash differs" in normalized
                or "confirmation is stale" in normalized,
                f"{rel} must treat stale hash as unconfirmed")

    def test_missing_binding_treated_as_unconfirmed_in_consumers(self):
        """Downstream consumers (validate, code) require SHA-256 binding.

        Reads the actual workflow markdown files and verifies each
        consumer file exists and contains a clause that explicitly
        links missing SHA-256 binding to unconfirmed treatment."""
        consumers = [
            "implement/skills/validate.md",
            "implement/skills/code.md",
            "e2e/skills/validate.md",
            "e2e/skills/code.md",
        ]
        repo_root = Path(__file__).resolve().parent.parent.parent
        for rel in consumers:
            path = repo_root / rel
            self.assertTrue(path.is_file(),
                            f"{rel} is missing — consumer file must exist")
            text = path.read_text(encoding="utf-8")
            low = text.lower()
            # Assert the file contains both the SHA-256 binding concept
            # and the unconfirmed consequence in the same context
            self.assertIn(
                "sha-256", low,
                f"{rel} must reference SHA-256 binding")
            self.assertIn(
                "unconfirmed", low,
                f"{rel} must reference unconfirmed treatment")
            # Assert the specific clause linking missing binding to
            # unconfirmed — normalize whitespace for cross-line matches
            import re as _re
            normalized = _re.sub(r'\s+', ' ', low)
            self.assertTrue(
                "missing sha-256 binding" in normalized
                or "no sha-256 recorded" in normalized
                or "no hash recorded" in normalized
                or "binding is missing" in normalized,
                f"{rel} must contain a clause that missing/absent "
                f"SHA-256 binding leads to unconfirmed treatment")


class TestProducerConsumerContracts(unittest.TestCase):
    """Static contract tests verifying producer/consumer field handoff.

    Reads ACTUAL workflow markdown and template files to verify that
    required handoff fields exist at the documented producer and
    consumer entry points. These are document contract checks — they
    do NOT execute live AI agent workflows.
    """

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def test_draft_gate_schema_has_required_evidence(self):
        """design/skills/draft.md gate table includes Required Evidence."""
        text = (self._repo_root() / "design/skills/draft.md").read_text()
        self.assertIn("Required Evidence", text,
                      "Draft gate schema must include Required Evidence column")

    def test_story_template_has_expected_results(self):
        """implement/templates/story-testplan.md has Expected Results."""
        text = (self._repo_root() / "implement/templates/story-testplan.md").read_text()
        self.assertIn("Expected Results", text,
                      "Story template TC gate must include Expected Results")

    def test_validate_report_requires_overall_verdict(self):
        """Both validate files require an explicit Overall: line."""
        for rel in ["implement/skills/validate.md",
                     "e2e/skills/validate.md"]:
            text = (self._repo_root() / rel).read_text()
            self.assertIn("Overall: PASS", text,
                          f"{rel} must document Overall: PASS verdict")
            self.assertIn("Overall: FAIL", text,
                          f"{rel} must document Overall: FAIL verdict")

    def test_publish_checks_overall_verdict(self):
        """Both publish files check for Overall: PASS."""
        for rel in ["implement/skills/publish.md",
                     "e2e/skills/publish.md"]:
            text = (self._repo_root() / rel).read_text()
            self.assertIn("Overall: PASS", text,
                          f"{rel} must check for Overall: PASS")

    def test_ingest_copies_gate_criteria(self):
        """Both ingest files require copying Required Evidence."""
        for rel in ["implement/skills/ingest.md",
                     "e2e/skills/ingest.md"]:
            text = (self._repo_root() / rel).read_text()
            self.assertIn("Required Evidence", text,
                          f"{rel} must instruct copying Required Evidence")

    def test_freshness_readers_accept_both_forms(self):
        """All Freshness readers independently accept plain and bold forms."""
        readers = [
            "implement/skills/plan.md",
            "implement/skills/code.md",
            "implement/skills/validate.md",
            "e2e/skills/plan.md",
            "e2e/skills/code.md",
            "e2e/skills/validate.md",
        ]
        for rel in readers:
            text = (self._repo_root() / rel).read_text()
            self.assertIn("**Freshness:**", text,
                          f"{rel} must accept bold Freshness marker")
            # Verify plain form is accepted independently — not just
            # as a substring of the bold form.  Linear regex replaces
            # the O(n²) per-index tail-slicing scan.
            import re as _re
            plain_hits = [m.start() for m in
                          _re.finditer(r"(?<!\*\*)Freshness:", text)]
            self.assertGreater(
                len(plain_hits), 0,
                f"{rel} must accept plain 'Freshness:' marker "
                f"independently of the bold form")

    def test_unresolved_source_marker_in_ingest_producers(self):
        """Both ingest files produce unresolved-source marker.

        Reads the actual ingest skill files and verifies the documented
        marker format for first-ingest with unresolvable source."""
        import re as _re
        for rel in ["implement/skills/ingest.md",
                     "e2e/skills/ingest.md"]:
            text = (self._repo_root() / rel).read_text(encoding="utf-8")
            normalized = _re.sub(r'\s+', ' ', text.lower())
            self.assertIn("freshness: unresolved-source", normalized,
                          f"{rel} must produce unresolved-source marker")
            self.assertIn("could not be read or resolved", normalized,
                          f"{rel} must document the source failure state")
            # Must be distinct from expected zero
            self.assertIn("distinct from confirmed absence", normalized,
                          f"{rel} must distinguish from confirmed absence")

    def test_validated_identity_in_report_and_publisher(self):
        """Validation reports record identity; publishers compare it.

        Verifies the producer (validate) records ALL identity fields
        and the consumer (publish) compares them against current
        inputs. All four fields must appear in both producer and
        consumer for each workflow."""
        identity_fields = [
            ("Branch HEAD", "branch HEAD"),
            ("Context SHA-256", "01-context.md"),
            ("Plan SHA-256", "02-plan.md"),
            ("Testplan SHA-256", "testplan.md"),
        ]
        for workflow in ["e2e", "implement"]:
            val_text = (self._repo_root() /
                        f"{workflow}/skills/validate.md").read_text()
            pub_text = (self._repo_root() /
                        f"{workflow}/skills/publish.md").read_text()
            # Producer records identity section
            self.assertIn("## Validated Identity", val_text,
                          f"{workflow}/validate must have identity section")
            # Each field must appear in producer AND consumer
            for field_label, file_ref in identity_fields:
                self.assertIn(field_label, val_text,
                              f"{workflow}/validate must record "
                              f"{field_label}")
                pub_lower = pub_text.lower()
                self.assertIn(field_label.lower(), pub_lower,
                              f"{workflow}/publish must compare "
                              f"{field_label}")
            # Consumer requires re-run on mismatch
            self.assertIn("re-run", pub_text.lower(),
                          f"{workflow}/publish must require re-run "
                          f"on mismatch")

    def test_overall_pass_requires_ac_verification(self):
        """Overall PASS criteria include AC verification.

        Reads both validate files and verifies the PASS criteria
        require all ACs to pass their approved method, not just
        automated TC coverage and external evidence."""
        import re as _re
        for rel in ["implement/skills/validate.md",
                     "e2e/skills/validate.md"]:
            text = (self._repo_root() / rel).read_text(encoding="utf-8")
            normalized = _re.sub(r'\s+', ' ', text.lower())
            # Find the Result section
            self.assertIn("acceptance criteria pass their approved", normalized,
                          f"{rel} PASS criteria must include AC verification")

    def test_publish_empty_set_confirmation_before_docs_mutation(self):
        """Empty-set retirement confirmation must precede design copy.

        Reads design/skills/publish.md and verifies that the empty-set
        branch obtains named confirmation BEFORE the design copy step.
        The shared sync recipe handles retirement via PREFLIGHT (all
        approvals) → APPLY (writes), so the publish caller must
        reference the recipe before any design copy, and inline
        empty-set confirmation in the preflight section must precede
        the copy step. Declining stops before any docs-repo mutation.

        This is a static branch-ordering test, not a live agent
        execution claim."""
        publish_text = (self._repo_root() /
                "design/skills/publish.md").read_text(encoding="utf-8")
        recipe_text = (self._repo_root() /
                "_shared/recipes/sync-validation-artifacts.md").read_text(
                    encoding="utf-8")
        design_copy_pos = publish_text.find(
            'cp ".artifacts/design/{issue-key}/03-design.md"')
        self.assertGreater(design_copy_pos, -1,
                           "Design copy command must exist")
        # Recipe reference must precede design copy — the recipe's
        # PREFLIGHT handles all checks including empty-set retirement
        recipe_ref = publish_text.find("sync-validation-artifacts.md")
        self.assertGreater(recipe_ref, -1,
                           "Shared sync recipe must be referenced")
        self.assertLess(recipe_ref, design_copy_pos,
                        "Recipe reference must precede design copy")
        # The shared recipe itself handles empty-set confirmation
        # in its PREFLIGHT phase before any APPLY mutation
        empty_confirm_pos = recipe_text.find(
            "Empty current set with previous snapshot")
        self.assertGreater(empty_confirm_pos, -1,
                           "Recipe PREFLIGHT must handle empty-set retirement")
        apply_phase_pos = recipe_text.find("### APPLY Phase")
        self.assertLess(empty_confirm_pos, apply_phase_pos,
                        "Empty-set confirmation must be in PREFLIGHT, "
                        "before APPLY phase")
        # Caller stages design AFTER recipe APPLY
        after_apply = publish_text.find("After the recipe's APPLY phase")
        self.assertGreater(after_apply, -1,
                           "Must document design copy after recipe APPLY")
        self.assertLess(after_apply, design_copy_pos,
                        "After-APPLY note must precede design copy")

    def test_e2e_validate_step7_three_way_ac_coverage(self):
        """e2e/skills/validate.md Step 7 accepts scenario, manual TC, or gate."""
        text = (self._repo_root() / "e2e/skills/validate.md").read_text()
        import re
        # Extract Step 7 section (up to Step 7b or next ###)
        m = re.search(
            r"### Step 7: Acceptance Criteria Verification\n(.*?)(?=\n### )",
            text, re.DOTALL)
        self.assertIsNotNone(m, "Step 7 section must exist")
        step7 = m.group(1)
        # Must reference all three coverage methods
        self.assertIn("Manual TC", step7,
                      "Step 7 must accept manual TC coverage")
        self.assertIn("Qualification gate", step7,
                      "Step 7 must accept qualification gate coverage")
        self.assertIn("Automated test scenario", step7,
                      "Step 7 must reference automated test scenarios")
        # Must mention evidence gating for non-automated methods
        self.assertIn("pending", step7,
                      "Step 7 must note that pending evidence is not a pass")
        # Must NOT contain old unconditional scenario-only claim
        self.assertNotIn(
            "covered by a test scenario.\nThis is",
            step7,
            "Step 7 must not claim coverage is exclusively test scenarios")

    def test_publish_preflight_and_validate_canonical_verdict(self):
        """Publishers require unqualified Overall: PASS; producers write it."""
        # Both publishers must reject legacy plain PASS
        for rel in ["implement/skills/publish.md",
                     "e2e/skills/publish.md"]:
            text = (self._repo_root() / rel).read_text()
            self.assertIn("Overall: PASS", text,
                          f"{rel} must check for Overall: PASS")
            self.assertIn("legacy", text,
                          f"{rel} must mention legacy plain PASS handling")

        # Both validators must instruct writing the literal line
        for rel in ["implement/skills/validate.md",
                     "e2e/skills/validate.md"]:
            text = (self._repo_root() / rel).read_text()
            self.assertIn("Write `Overall: PASS`", text,
                          f"{rel} must instruct writing literal Overall: PASS")
            self.assertIn("Overall: FAIL", text,
                          f"{rel} must document Overall: FAIL verdict")


# ===========================================================================
# 27. Snapshot/Git consumer regressions
# ===========================================================================

class TestSnapshotGitConsumerRegressions(unittest.TestCase):
    """Real snapshot/diff/retire lifecycle with temp Git repos.

    Exercises the documented publish workflow paths:
    - First publish: no previous snapshot
    - Stale snapshot with missing source
    - Valid published index round-trip
    - Canonical legacy snapshot (testplan.md only)
    - Invalid previous snapshot is rejected by validation and diff
    - Pure retirement: staged deletion of tracked files

    These tests use real temp Git repos because the design publish
    recipe (Step 8) uses plain 'git -C repo commit -m' with no
    pathspec — staging and change detection are the caller's
    responsibility, not a shared commit API.

    NOT tested (requires live AI agents / real infrastructure):
    - End-to-end design workflow execution
    - GitHub PR creation and comment posting
    - Jira integration
    """

    def _init_git_repo(self, path):
        _init_git_repo(path)

    def test_first_publish_no_previous_snapshot(self):
        """First publish: empty old → diff shows all artifacts as added."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            art_dir = Path(td) / "artifacts"
            docs_dir = Path(td) / "docs" / "v1" / "feature"
            art_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)
            self._init_git_repo(Path(td) / "docs")

            # Local artifacts
            _write(art_dir / "04-testplan.md", "# Plan\n## TC-FR1-01")
            r = _run_cli("build-legacy", str(art_dir),
                         str(art_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)

            # Transform to published format
            r = _run_cli("transform",
                         str(art_dir / "validation-index.json"),
                         str(docs_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            (docs_dir / "testplan.md").write_text(
                (art_dir / "04-testplan.md").read_text())

            # Diff against empty old (first publish)
            _write_json(Path(td) / "empty-old.json", {})
            r = _run_cli("diff",
                         str(Path(td) / "empty-old.json"),
                         str(docs_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d["added"], ["testplan.md"])
            self.assertEqual(d["removed"], [])

            # Stage and commit (matching publish Step 8 recipe)
            subprocess.run(["git", "-C", str(Path(td) / "docs"),
                           "add", "v1/feature/testplan.md",
                           "v1/feature/validation-index.json"],
                          capture_output=True, check=True)
            r2 = subprocess.run(
                ["git", "-C", str(Path(td) / "docs"), "commit", "-m",
                 "Add design and validation artifacts"],
                capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, r2.stderr)

    def test_stale_snapshot_source_missing(self):
        """Previous snapshot lists a file that no longer exists on disk.

        validates that resolve --published fails for a stale published
        state (file listed in index but removed from disk)."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = Path(td) / "docs"
            docs_dir.mkdir()

            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(docs_dir / "validation-index.json", pub)
            _write(docs_dir / "testplan.md", "# Plan")
            # hw.md NOT on disk — stale snapshot
            r = _run_cli("resolve", "--published", str(docs_dir))
            self.assertEqual(r.returncode, 1,
                             "Stale snapshot must fail when listed file "
                             "is missing")
            self.assertIn("not found", r.stderr)

    def test_valid_published_index_roundtrip(self):
        """Local → transform → published → resolve → primary_path."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            art_dir = Path(td) / "art"
            docs_dir = Path(td) / "docs"
            art_dir.mkdir()
            docs_dir.mkdir()

            # Build local index with companion
            idx = _make_local_index(companions=[_HW_COMPANION])
            _write_json(art_dir / "validation-index.json", idx)
            _write(art_dir / "04-testplan.md", "# Plan")
            _write(art_dir / "04-hw-validation.md", "# HW")

            # Transform
            r = _run_cli("transform",
                         str(art_dir / "validation-index.json"),
                         str(docs_dir / "validation-index.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            for art in idx["artifacts"]:
                (docs_dir / art["published_as"]).write_text(
                    (art_dir / art["local"]).read_text())

            # Resolve from published
            r = _run_cli("resolve", "--published", str(docs_dir))
            self.assertEqual(r.returncode, 0, r.stderr)
            arts = json.loads(r.stdout)
            self.assertEqual(len(arts), 2)

            # Primary path
            primary = vi.primary_testplan_path(docs_dir)
            self.assertEqual(primary, docs_dir / "testplan.md")

    def test_canonical_legacy_snapshot(self):
        """Legacy published state: testplan.md only, no index.

        The snapshot recipe builds a minimal published index for
        diffing purposes."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = Path(td) / "docs"
            docs_dir.mkdir()
            _write(docs_dir / "testplan.md", "# Plan")

            # Resolve published (legacy fallback)
            arts = vi.resolve_published_artifacts(docs_dir)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["file"], "testplan.md")

            # Build minimal snapshot for diffing (as publish recipe does)
            legacy_snapshot = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "prev-snapshot.json", legacy_snapshot)

            # Validate snapshot
            r = _run_cli("validate", "--published",
                         str(Path(td) / "prev-snapshot.json"))
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_invalid_previous_snapshot_blocks_diff(self):
        """Malformed previous snapshot → diff rejects before computing.

        Ensures corrupted snapshot cannot silently produce wrong
        removal lists. This guards the publish recipe's snapshot
        validation step."""
        with tempfile.TemporaryDirectory() as td:
            # Validate rejects malformed snapshot
            malformed = {
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "prev.json", malformed)
            r = _run_cli("validate", "--published",
                         str(Path(td) / "prev.json"))
            self.assertEqual(r.returncode, 1,
                             "Malformed snapshot must fail validation")

            # And diff also rejects it
            valid_new = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(Path(td) / "new.json", valid_new)
            r = _run_cli("diff",
                         str(Path(td) / "prev.json"),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 1,
                             "Diff must reject malformed snapshot")

    def test_pure_retirement_stages_deletion(self):
        """Pure retirement: tracked file removal staged and committed.

        When current content is unchanged but artifacts are removed,
        git rm stages the deletion. Verifies the recipe's 'git -C
        repo rm' + 'git -C repo commit' path with real git."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            docs_root = Path(td) / "docs"
            feat_dir = docs_root / "v1" / "feature"
            feat_dir.mkdir(parents=True)
            self._init_git_repo(docs_root)

            # Publish initial state (testplan + companion)
            _write(feat_dir / "testplan.md", "# Plan")
            _write(feat_dir / "hw.md", "# HW")
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(feat_dir / "validation-index.json", pub)
            subprocess.run(["git", "-C", str(docs_root), "add", "-A"],
                          capture_output=True, check=True)
            subprocess.run(["git", "-C", str(docs_root), "commit",
                           "-m", "initial publish"],
                          capture_output=True, check=True)

            # Save previous snapshot
            prev_path = Path(td) / "prev.json"
            _write_json(prev_path, pub)

            # Retire companion: new state has only testplan
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(feat_dir / "validation-index.json", new_pub)

            # Diff to find retired artifacts
            _write_json(Path(td) / "new.json", new_pub)
            r = _run_cli("diff", str(prev_path),
                         str(Path(td) / "new.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d["removed"], ["hw.md"])

            # Stage removal (matching publish recipe)
            r2 = subprocess.run(
                ["git", "-C", str(docs_root), "rm", "--",
                 "v1/feature/hw.md"],
                capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, r2.stderr)

            # Stage updated index
            subprocess.run(["git", "-C", str(docs_root), "add",
                           "v1/feature/validation-index.json"],
                          capture_output=True, check=True)

            # Verify staged changes include deletion
            r3 = subprocess.run(
                ["git", "-C", str(docs_root), "diff", "--cached",
                 "--name-status"],
                capture_output=True, text=True)
            self.assertIn("D\tv1/feature/hw.md", r3.stdout)
            self.assertIn("M\tv1/feature/validation-index.json",
                          r3.stdout)

            # Commit (matching publish Step 8: plain git commit -m)
            r4 = subprocess.run(
                ["git", "-C", str(docs_root), "commit", "-m",
                 "Retire companion artifact"],
                capture_output=True, text=True)
            self.assertEqual(r4.returncode, 0, r4.stderr)

            # Verify file is gone but testplan remains
            self.assertFalse((feat_dir / "hw.md").exists())
            self.assertTrue((feat_dir / "testplan.md").exists())
            self.assertTrue(
                (feat_dir / "validation-index.json").exists())


    def test_hostile_global_config_does_not_block_commits(self):
        """Host GIT_CONFIG_GLOBAL with forced signing and hooks is overridden.

        Verifies that _init_git_repo's local config overrides are
        sufficient: even when GIT_CONFIG_GLOBAL points to a config
        that enables commit.gpgsign and sets core.hooksPath to a
        directory with a failing pre-commit hook, the test's local
        repo config (set before the first commit) takes precedence.

        This is a static Git consumer regression test — it exercises
        the actual test helper, not a live AI workflow."""
        import os as _os
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())

            # Create a hostile global config
            hostile_dir = Path(td) / "hostile"
            hostile_dir.mkdir()
            hostile_hooks = hostile_dir / "hooks"
            hostile_hooks.mkdir()
            # Failing pre-commit hook
            hook = hostile_hooks / "pre-commit"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(0o755)
            # Global config forcing signing and hostile hooks
            global_cfg = hostile_dir / "gitconfig"
            global_cfg.write_text(
                "[commit]\n\tgpgsign = true\n"
                f"[core]\n\thooksPath = {hostile_hooks}\n"
            )

            # _init_git_repo must succeed despite hostile global
            repo_path = Path(td) / "repo"
            repo_path.mkdir()
            env = {**_os.environ, "GIT_CONFIG_GLOBAL": str(global_cfg)}

            # Patch subprocess.run to inject hostile env for git commands
            import unittest.mock as _mock
            orig_run = subprocess.run

            def run_with_env(*a, **kw):
                if a and a[0] and a[0][0] == "git":
                    kw.setdefault("env", env)
                return orig_run(*a, **kw)

            with _mock.patch("subprocess.run", side_effect=run_with_env):
                self._init_git_repo(repo_path)
                # Consumer commit: add a file and commit
                (repo_path / "test.txt").write_text("content")
                subprocess.run(["git", "-C", str(repo_path), "add",
                               "test.txt"],
                              capture_output=True, check=True, env=env)
                r = subprocess.run(
                    ["git", "-C", str(repo_path), "commit", "-m",
                     "consumer commit"],
                    capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0,
                             f"Consumer commit must succeed despite "
                             f"hostile global config: {r.stderr}")


# ===========================================================================
# 28. Ancestor symlink rejection for copy destinations
# ===========================================================================

class TestAncestorSymlinkRejection(unittest.TestCase):
    """CLI index-writer guard: symlink ancestors below the docs repo
    root must be rejected by the transform command, preventing writes
    that escape the trusted output directory.

    The validation_index.py _safe_write_output enforces this for CLI
    write paths. These tests verify the *ancestor* check catches
    directory symlinks between the trusted root and the destination.
    The workflow instructions additionally require ancestor checks
    before artifact copy (cp commands) — that is a static document
    contract verified separately, not exercised here."""

    def test_feature_dir_symlink_outside_rejected(self):
        """Symlink feature directory → outside dir: transform rejects."""
        with tempfile.TemporaryDirectory() as td:
            with tempfile.TemporaryDirectory() as outside:
                root = Path(td) / "docs"
                root.mkdir()
                # feature-dir is a symlink pointing outside
                (root / "feature").symlink_to(outside)
                src = Path(td) / "local.json"
                _write_json(src, _make_local_index())
                dst = root / "feature" / "validation-index.json"
                r = _run_cli("transform", str(src), str(dst),
                             "--trusted-output-base", str(root))
                self.assertEqual(r.returncode, 1,
                                 "Ancestor symlink must be rejected")
                low = r.stderr.lower()
                self.assertTrue(
                    "symlink" in low or "escape" in low,
                    f"Expected symlink/escape error, got: {r.stderr}")
                # Outside bytes unchanged
                self.assertFalse(
                    (Path(outside) / "validation-index.json").exists(),
                    "No files should be written outside the root")


# ===========================================================================
# 29. Story-scoped SHA-256 hash path validation
# ===========================================================================

class TestStoryScopedHashPath(unittest.TestCase):
    """SHA-256 commands must hash the full story-scoped artifact path
    (.artifacts/{workflow}/{issue-key}/testplan.md), not a CWD
    testplan.md.

    Verifies that the documented sha256sum command, executed from a
    directory containing a decoy testplan.md, still hashes the
    story-scoped file (static document check is in the next test)."""

    _CONSUMER_FILES = [
        ("implement/skills/plan.md", "implement"),
        ("implement/skills/code.md", "implement"),
        ("implement/skills/validate.md", "implement"),
        ("e2e/skills/plan.md", "e2e"),
        ("e2e/skills/code.md", "e2e"),
        ("e2e/skills/validate.md", "e2e"),
    ]

    def test_decoy_testplan_does_not_affect_story_hash(self):
        """Run the documented sha256sum command with a CWD decoy present."""
        import hashlib
        import re
        import shutil
        if not shutil.which("sha256sum"):
            self.skipTest("sha256sum not available")

        repo_root = Path(__file__).resolve().parent.parent.parent
        # Extract a documented sha256sum command from the first consumer
        for rel, workflow in self._CONSUMER_FILES:
            text = (repo_root / rel).read_text(encoding="utf-8")
            m = re.search(r"sha256sum\s+([^\s`)]+)", text)
            if m:
                cmd_template = m.group(1)
                break
        else:
            self.fail("No documented sha256sum command found in consumers")

        issue_key = "PROJ-1"
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            # Create story-scoped artifact
            story_path = cmd_template.replace(
                "{issue-key}", issue_key)
            full_story = Path(td) / story_path
            full_story.parent.mkdir(parents=True, exist_ok=True)
            story_content = "# Story testplan content\n## TC-FR1-01\n"
            _write(full_story, story_content)

            # Create decoy in project root (CWD)
            decoy_content = "# DECOY — different content\n"
            _write(Path(td) / "testplan.md", decoy_content)

            # Run the documented command from the project root (with decoy)
            r = subprocess.run(
                ["sha256sum", story_path],
                capture_output=True, text=True,
                timeout=10, check=False, cwd=td)
            self.assertEqual(r.returncode, 0,
                             f"sha256sum must succeed: {r.stderr}")
            cmd_hash = r.stdout.split()[0]

            # Verify it hashes the story-scoped file, not the decoy
            expected = hashlib.sha256(
                full_story.read_bytes()).hexdigest()
            decoy_hash = hashlib.sha256(
                (Path(td) / "testplan.md").read_bytes()).hexdigest()
            self.assertEqual(cmd_hash, expected,
                             "sha256sum must hash story-scoped file")
            self.assertNotEqual(cmd_hash, decoy_hash,
                                "sha256sum must NOT match CWD decoy")

    def test_documented_commands_use_story_scoped_paths(self):
        """All sha256sum commands in consumer files use story-scoped paths.

        Extracts sha256sum references from the 6 plan/code/validate
        consumer files and asserts each references .artifacts/ (the
        story-scoped directory), not a bare testplan.md."""
        import re
        consumers = [
            ("implement/skills/plan.md", "implement"),
            ("implement/skills/code.md", "implement"),
            ("implement/skills/validate.md", "implement"),
            ("e2e/skills/plan.md", "e2e"),
            ("e2e/skills/code.md", "e2e"),
            ("e2e/skills/validate.md", "e2e"),
        ]
        repo_root = Path(__file__).resolve().parent.parent.parent
        for rel, workflow in consumers:
            path = repo_root / rel
            self.assertTrue(path.is_file(),
                            f"{rel} must exist as a consumer file")
            text = path.read_text(encoding="utf-8")
            # Find all sha256sum mentions — each consumer must have
            # at least one documented sha256sum command.
            hits = list(re.finditer(
                r"sha256sum\s+([^\s`)]+)", text))
            self.assertGreater(
                len(hits), 0,
                f"{rel}: must contain at least one documented "
                f"sha256sum command")
            for m in hits:
                arg = m.group(1)
                self.assertIn(
                    ".artifacts/", arg,
                    f"{rel}: sha256sum argument '{arg}' must use "
                    f"story-scoped .artifacts/ path, not bare filename")


# ===========================================================================
# 30. Design staging independent of validation-index flow
# ===========================================================================

class TestDesignStagingIndependence(unittest.TestCase):
    """Design file must be staged (git add) independently of
    validation artifacts, so a pure design update or retirement
    commits the design change even when both validation sets
    are empty.

    Uses a real temporary Git repo + actual staging/commit."""

    def _init_git_repo(self, path):
        _init_git_repo(path)

    def test_pure_design_update_no_artifacts_commits(self):
        """Design change stages/commits with empty validation sets."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            self._init_git_repo(docs)

            feat = docs / "v1" / "feature"
            feat.mkdir(parents=True)
            _write(feat / "design.md", "# Design v1\n")
            subprocess.run(["git", "-C", str(docs), "add",
                            "v1/feature/design.md"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", str(docs), "commit", "-m",
                            "initial design"],
                           capture_output=True, check=True)

            # Revise design — no validation artifacts at all
            _write(feat / "design.md", "# Design v2 — revised\n")
            # Stage design independently (the fix)
            subprocess.run(["git", "-C", str(docs), "add",
                            "v1/feature/design.md"],
                           capture_output=True, check=True)
            # Commit with no validation-index changes
            r = subprocess.run(
                ["git", "-C", str(docs), "commit", "-m",
                 "revise design only"],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0,
                             f"Design-only commit must succeed: "
                             f"{r.stderr}")
            # Verify the design was committed
            content = (feat / "design.md").read_text()
            self.assertIn("v2", content)

    def test_partial_retire_preserves_index_and_retained(self):
        """Partial retirement keeps index with retained companions."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            self._init_git_repo(docs)

            feat = docs / "v1" / "feature"
            feat.mkdir(parents=True)
            # Initial publish with testplan + companion
            pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {"file": "hw.md", "type": "companion",
                     "purpose": "HW", "audience": "team"},
                ],
            }
            _write_json(feat / "validation-index.json", pub)
            _write(feat / "testplan.md", "# Plan")
            _write(feat / "hw.md", "# HW")
            subprocess.run(["git", "-C", str(docs), "add", "."],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", str(docs), "commit", "-m",
                            "publish"],
                           capture_output=True, check=True)

            # Partial retire: remove hw.md but keep testplan
            subprocess.run(["git", "-C", str(docs), "rm",
                            str(feat / "hw.md")],
                           capture_output=True, check=True)
            # Update index (retain only testplan)
            new_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(feat / "validation-index.json", new_pub)
            subprocess.run(["git", "-C", str(docs), "add",
                            str(feat / "validation-index.json")],
                           capture_output=True, check=True)
            r = subprocess.run(
                ["git", "-C", str(docs), "commit", "-m",
                 "partial retire"],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

            # Index preserved with retained testplan
            self.assertTrue(
                (feat / "validation-index.json").exists(),
                "Index must be preserved on partial retirement")
            self.assertTrue(
                (feat / "testplan.md").exists(),
                "Retained testplan must still exist")
            self.assertFalse(
                (feat / "hw.md").exists(),
                "Retired companion must be removed")

    def test_full_retire_allows_restoring_with_rebuild(self):
        """After full retirement decision, restoring an artifact
        should allow rebuild of index from restored files."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())  # Canonicalize (macOS /var → /private/var)
            art_dir = Path(td) / "art"
            art_dir.mkdir()
            # Simulate restoring a testplan during retirement
            _write(art_dir / "04-testplan.md", "# Restored plan")
            # Build-legacy creates a valid index from restored file
            out = art_dir / "validation-index.json"
            r = _run_cli("build-legacy", str(art_dir), str(out))
            self.assertEqual(r.returncode, 0,
                             f"build-legacy must succeed from restored "
                             f"file: {r.stderr}")
            idx = json.loads(out.read_text())
            errors = vi.validate_local_index(idx)
            self.assertEqual(errors, [],
                             f"Rebuilt index must be valid: {errors}")


# ===========================================================================
# 32. Gap-fill predicate uses computed effective confirmation state
# ===========================================================================

class TestGapFillPredicateUsesEffectiveState(unittest.TestCase):
    """Static regression: both validate.md files' item 3 gap-fill
    decision must reference the computed effective confirmation state
    (hash present + current hash matches + TC ID listed), not just
    the raw 'confirmed' status word.

    This ensures a raw-confirmed record with a missing or stale hash
    falls into the provisional branch, not the normative gap-fill."""

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def test_e2e_validate_gap_fill_references_effective_state(self):
        """e2e/skills/validate.md item 3 must reference effective
        confirmation criteria, not raw status."""
        text = (self._repo_root() / "e2e/skills/validate.md").read_text()
        # Find the gap-fill decision section (item 3)
        self.assertIn(
            "effectively confirmed",
            text,
            "e2e validate item 3 must reference 'effectively confirmed'")
        # Must NOT rely solely on raw "no confirmed status"
        self.assertNotIn(
            'has not been confirmed (no\n     "confirmed" status)',
            text,
            "e2e validate must not use raw status check in gap-fill")

    def test_implement_validate_gap_fill_references_effective_state(self):
        """implement/skills/validate.md item 3 must reference effective
        confirmation criteria, not raw status."""
        text = (self._repo_root() / "implement/skills/validate.md").read_text()
        self.assertIn(
            "effectively confirmed",
            text,
            "implement validate item 3 must reference 'effectively confirmed'")
        self.assertNotIn(
            'has not been confirmed by the user\n     (no "confirmed" status)',
            text,
            "implement validate must not use raw status check in gap-fill")


# ===========================================================================
# 33. Removal preflight before artifact copy in publish/respond/revise
# ===========================================================================

class TestRemovalPreflightOrder(unittest.TestCase):
    """Static regression: publish, respond, and revise must compute
    removal diffs and obtain user confirmation BEFORE copying current
    artifacts to the docs repo (overwriting published files).

    Verifies the candidate-published-index preflight appears before
    the cp/copy command in each sync section."""

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def _assert_preflight_before_copy(self, rel):
        """Verify that the caller references the shared sync recipe
        and that the recipe itself has preflight before copy.

        Callers delegate sync to the shared recipe rather than inline
        commands, so check the recipe reference exists and the recipe
        has the correct ordering."""
        text = (self._repo_root() / rel).read_text()
        # Caller must reference the shared recipe
        recipe_ref = text.find("sync-validation-artifacts.md")
        self.assertGreater(
            recipe_ref, -1,
            f"{rel} must reference the shared sync recipe")
        # The shared recipe itself must have preflight before copy
        recipe_text = (self._repo_root() /
                       "_shared/recipes/sync-validation-artifacts.md"
                       ).read_text()
        preflight_pos = recipe_text.find(
            "candidate-published-index.json")
        self.assertGreater(
            preflight_pos, -1,
            "Shared recipe must contain candidate-published-index "
            "preflight")
        copy_pos = recipe_text.find('{LOCAL}')
        self.assertGreater(
            copy_pos, -1,
            "Shared recipe must contain artifact copy command")
        self.assertLess(
            preflight_pos, copy_pos,
            "Shared recipe: removal preflight must appear BEFORE "
            "artifact copy commands")

    def test_publish_preflight_order(self):
        self._assert_preflight_before_copy("design/skills/publish.md")

    def test_respond_preflight_order(self):
        self._assert_preflight_before_copy("design/skills/respond.md")

    def test_revise_preflight_order(self):
        self._assert_preflight_before_copy("design/skills/revise.md")


# ===========================================================================
# 34. Respond empty-set retirement via absent sources, not invalid index
# ===========================================================================

class TestRespondEmptySetRetirementRoute(unittest.TestCase):
    """Static regression: respond.md zero-artifact retirement path must
    describe the case where resolve succeeds with empty [] because both
    index AND legacy primary are absent — not a present but empty/invalid
    index (which hits the resolve failure stop)."""

    def test_empty_set_describes_absent_sources(self):
        repo_root = Path(__file__).resolve().parent.parent.parent
        text = (repo_root / "design/skills/respond.md").read_text()
        # Find the zero-artifact retirement section
        section_start = text.find("zero** artifacts")
        self.assertGreater(section_start, -1,
                           "Must contain zero-artifacts section")
        section = text[section_start:section_start + 800]
        low = section.lower()
        # Must clarify this is from resolved empty [], not present
        # invalid index
        self.assertTrue(
            "resolve" in low or "absent" in low,
            "Zero-artifact section must reference resolve/absent "
            "sources, not present invalid index")
        # Must explicitly exclude present but malformed index
        self.assertTrue(
            "malformed" in low or "not this case" in low,
            "Must clarify that present malformed/invalid index "
            "is NOT this case")


# ===========================================================================
# 35. Candidate preflight transform uses project root, not docs root
# ===========================================================================

class TestCandidatePreflightTrustedBase(unittest.TestCase):
    """CLI regression: the candidate-published-index transform command
    documented in publish/respond/revise must use the project root
    (\".\") as --trusted-output-base, not {docs_repo_path}.

    The candidate is written under .artifacts/ (project root), while
    the docs repo is a separate checkout. Using the docs root as
    trusted base causes the helper to reject the output path.

    Each subtest extracts the documented trusted-output-base value
    from the phase markdown, verifies it is ".", and runs the
    equivalent transform and diff argv against a real temporary
    layout with distinct project and docs directories.
    """

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def _extract_candidate_transform_cmd(self, rel):
        """Extract the candidate transform bash line.

        Callers now delegate to the shared sync recipe, so find the
        command in the recipe and verify the caller references it."""
        import re
        caller_text = (self._repo_root() / rel).read_text()
        # Caller must reference the shared recipe
        self.assertIn(
            "sync-validation-artifacts.md", caller_text,
            f"{rel}: must reference shared sync recipe")
        # Find the candidate transform in the shared recipe
        recipe_path = (self._repo_root() /
                       "_shared/recipes/sync-validation-artifacts.md")
        text = recipe_path.read_text()
        pattern = (r'python3\s+"\$VALIDATION_INDEX_SCRIPT"\s+transform\s+'
                   r'"[^"]+validation-index\.json"\s+'
                   r'"[^"]+candidate-published-index\.json"\s+'
                   r'--trusted-output-base\s+"([^"]+)"')
        m = re.search(pattern, text)
        self.assertIsNotNone(
            m, f"shared recipe: candidate transform command not found")
        return m.group(0), m.group(1)

    def _run_preflight(self, rel):
        """Run the candidate preflight for a single phase."""
        _, trusted_base = self._extract_candidate_transform_cmd(rel)

        # The trusted base for candidates must be "." (project root)
        self.assertEqual(
            trusted_base, ".",
            f"{rel}: candidate transform must use \".\" as "
            f"trusted-output-base, got \"{trusted_base}\"")

        script = str(self._repo_root() / "design" / "scripts"
                     / "validation_index.py")

        with tempfile.TemporaryDirectory() as proj, \
             tempfile.TemporaryDirectory() as docs:
            proj = str(Path(proj).resolve())  # Canonicalize (macOS /var → /private/var)
            docs = str(Path(docs).resolve())
            # Build valid local index using existing factory
            art_dir = Path(proj) / ".artifacts" / "design" / "TST-1"
            art_dir.mkdir(parents=True)
            (art_dir / "04-testplan.md").write_text("# Testplan\n")
            (art_dir / "04-companion.md").write_text("# Companion\n")
            # Build legacy for primary, then add companion
            r0 = _run_cli("build-legacy", str(art_dir),
                           str(art_dir / "validation-index.json"))
            self.assertEqual(r0.returncode, 0,
                             f"build-legacy failed: {r0.stderr}")
            idx = json.loads(
                (art_dir / "validation-index.json").read_text())
            idx["artifacts"].append({
                "local": "04-companion.md",
                "published_as": "companion.md",
                "type": "companion",
                "purpose": "supplementary",
                "audience": "reviewers",
            })
            _write_json(art_dir / "validation-index.json", idx)

            # Create a valid previous published snapshot (with
            # companion that will be "removed" in candidate).
            # Published schema requires purpose and audience.
            prev_pub = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan",
                     "purpose": "primary", "audience": "reviewers"},
                    {"file": "companion.md", "type": "companion",
                     "purpose": "supplementary",
                     "audience": "reviewers"},
                    {"file": "old-extra.md", "type": "companion",
                     "purpose": "supplementary",
                     "audience": "reviewers"},
                ],
            }
            _write_json(art_dir / "prev-published-index.json", prev_pub)
            # Place the old-extra.md file in docs so it looks real
            docs_feat = Path(docs) / "v1" / "feat"
            docs_feat.mkdir(parents=True)
            (docs_feat / "old-extra.md").write_text("# Old extra\n")
            (docs_feat / "testplan.md").write_text("# Published TP\n")
            (docs_feat / "companion.md").write_text(
                "# Published companion\n")

            # Execute candidate transform: output under project,
            # using the documented trusted-output-base with cwd=proj
            r1 = subprocess.run(
                [sys.executable, script, "transform",
                 str(art_dir / "validation-index.json"),
                 str(art_dir / "candidate-published-index.json"),
                 "--trusted-output-base", trusted_base],
                capture_output=True, text=True, cwd=proj,
                timeout=10, check=False)
            self.assertEqual(
                r1.returncode, 0,
                f"{rel}: candidate transform must succeed when "
                f"trusted base is project root: {r1.stderr}")
            self.assertTrue(
                (art_dir / "candidate-published-index.json").exists(),
                f"{rel}: candidate file must be written")

            # Execute diff: should report old-extra.md as removed
            r2 = subprocess.run(
                [sys.executable, script, "diff",
                 str(art_dir / "prev-published-index.json"),
                 str(art_dir / "candidate-published-index.json")],
                capture_output=True, text=True, cwd=proj,
                timeout=10, check=False)
            self.assertEqual(r2.returncode, 0,
                             f"diff must succeed: {r2.stderr}")
            diff_result = json.loads(r2.stdout)
            self.assertIn("old-extra.md", diff_result.get("removed", []),
                          "Diff must report removed companion")

            # Verify docs repo files are UNCHANGED (preflight only)
            self.assertEqual(
                (docs_feat / "old-extra.md").read_text(),
                "# Old extra\n",
                "Docs repo old-extra.md must be unchanged by preflight")
            self.assertEqual(
                (docs_feat / "testplan.md").read_text(),
                "# Published TP\n",
                "Docs repo testplan.md must be unchanged by preflight")

    def test_publish_candidate_preflight(self):
        """publish.md candidate transform uses project root."""
        self._run_preflight("design/skills/publish.md")

    def test_respond_candidate_preflight(self):
        """respond.md candidate transform uses project root."""
        self._run_preflight("design/skills/respond.md")

    def test_revise_candidate_preflight(self):
        """revise.md candidate transform uses project root."""
        self._run_preflight("design/skills/revise.md")


# ===========================================================================
# Group 1: SKILL_DIR resource resolution (static filesystem contract)
# ===========================================================================

class TestSkillDirResourceResolution(unittest.TestCase):
    """Static filesystem contract test for SKILL_DIR-based resource resolution.

    Verifies symlink following, decoy rejection, and cross-workflow paths.
    NOT a live agent E2E test — these exercise the bash realpath command
    that phase file instructions document, against controlled filesystem
    layouts."""

    def test_design_skills_symlink_resolves_to_canonical(self):
        """Symlinked phase file resolves ../scripts/validation_index.py
        to the canonical install location, not the symlink's parent."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            # Simulate ai-workflows install layout
            install = Path(td) / "install"
            (install / "design" / "skills").mkdir(parents=True)
            (install / "design" / "scripts").mkdir(parents=True)
            _write(install / "design" / "skills" / "publish.md",
                   "# placeholder")
            target_script = install / "design" / "scripts" / "validation_index.py"
            _write(target_script, "# real script")

            # Project override via symlink
            project = Path(td) / "project"
            override_dir = project / ".workflows" / "design" / "skills"
            override_dir.mkdir(parents=True)
            link = override_dir / "publish.md"
            link.symlink_to(install / "design" / "skills" / "publish.md")

            # Create decoy at project root
            _write(project / "validation_index.py", "# DECOY")

            # Resolve SKILL_DIR from symlinked path (following symlinks)
            r = subprocess.run(
                ["bash", "-c",
                 'SKILL_DIR="$(dirname "$(realpath "$1")")"; '
                 'realpath "${SKILL_DIR}/../scripts/validation_index.py"',
                 "_", str(link)],
                capture_output=True, text=True, timeout=10,
                check=False, cwd=str(project))
            self.assertEqual(r.returncode, 0,
                             f"realpath must succeed: {r.stderr}")
            resolved = r.stdout.strip()
            self.assertEqual(resolved, str(target_script.resolve()),
                             "Must resolve to canonical script, not decoy")
            # Verify decoy NOT selected
            self.assertNotEqual(
                resolved, str(project / "validation_index.py"),
                "Must not resolve to CWD decoy")

    def test_cross_workflow_path_from_implement(self):
        """implement/skills/ → ../../design/scripts/validation_index.py
        resolves correctly through symlink."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            install = Path(td) / "install"
            (install / "implement" / "skills").mkdir(parents=True)
            (install / "design" / "scripts").mkdir(parents=True)
            _write(install / "implement" / "skills" / "ingest.md",
                   "# placeholder")
            target_script = install / "design" / "scripts" / "validation_index.py"
            _write(target_script, "# real script")

            # Symlink from project override
            project = Path(td) / "project"
            link_dir = project / ".workflows" / "implement" / "skills"
            link_dir.mkdir(parents=True)
            link = link_dir / "ingest.md"
            link.symlink_to(
                install / "implement" / "skills" / "ingest.md")

            r = subprocess.run(
                ["bash", "-c",
                 'SKILL_DIR="$(dirname "$(realpath "$1")")"; '
                 'realpath "${SKILL_DIR}/../../design/scripts/validation_index.py"',
                 "_", str(link)],
                capture_output=True, text=True, timeout=10,
                check=False, cwd=str(project))
            self.assertEqual(r.returncode, 0,
                             f"realpath must succeed: {r.stderr}")
            self.assertEqual(r.stdout.strip(),
                             str(target_script.resolve()))

    def test_empty_skill_dir_fails(self):
        """Empty SKILL_DIR causes realpath to fail (non-zero exit)."""
        r = subprocess.run(
            ["bash", "-c",
             'SKILL_DIR=""; '
             'realpath "${SKILL_DIR}/../scripts/validation_index.py"'],
            capture_output=True, text=True, timeout=10, check=False)
        self.assertNotEqual(r.returncode, 0,
                            "Empty SKILL_DIR must cause realpath failure")

    def test_wrong_skill_dir_fails(self):
        """Non-existent SKILL_DIR causes realpath to fail."""
        r = subprocess.run(
            ["bash", "-c",
             'SKILL_DIR="/nonexistent/path/skills"; '
             'realpath "${SKILL_DIR}/../scripts/validation_index.py"'],
            capture_output=True, text=True, timeout=10, check=False)
        self.assertNotEqual(r.returncode, 0,
                            "Non-existent SKILL_DIR must cause failure")


# ===========================================================================
# Group 6: Focused coverage tests
# ===========================================================================

class TestTransformNonZeroGuard(unittest.TestCase):
    """CLI transform exits non-zero on invalid input, proving the
    ``|| { ...; exit 1; }`` guard pattern documented in phase files
    would trigger. Tests the actual CLI exit code, not the API."""

    def test_transform_invalid_index_exits_nonzero(self):
        """Transform with schema-invalid local index → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            src = Path(td) / "bad.json"
            dst = Path(td) / "out.json"
            # Missing required fields
            _write_json(src, {"schema_version": "1.0"})
            r = _run_cli("transform", str(src), str(dst))
            self.assertNotEqual(r.returncode, 0,
                                f"Must exit non-zero for invalid input: "
                                f"stdout={r.stdout}, stderr={r.stderr}")
            self.assertFalse(dst.exists(),
                             "Must not write output on failure")

    def test_transform_missing_file_exits_nonzero(self):
        """Transform with non-existent input file → exit 1."""
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            r = _run_cli("transform",
                          str(Path(td) / "nonexistent.json"),
                          str(Path(td) / "out.json"))
            self.assertNotEqual(r.returncode, 0)


class TestPublishedIndexForbidsPublishedAs(unittest.TestCase):
    """Published index schema explicitly rejects ``published_as`` fields.

    The published format uses ``file`` (not ``published_as`` or
    ``local``). This verifies the schema validation enforces that
    boundary — static schema check, not live agent behavior."""

    def test_rejects_published_as_field(self):
        """validate_published_index rejects an artifact with published_as."""
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan",
                 "published_as": "testplan.md"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(
            any("must not have 'published_as'" in e for e in errors),
            f"Must reject published_as in published index: {errors}")

    def test_accepts_file_only(self):
        """Published index with only ``file`` (no local/published_as) passes."""
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertEqual(errors, [])


class TestSourceDiscoveryMarkerContract(unittest.TestCase):
    """Static document contract: Source-Discovery marker in producer/consumer.

    Verifies that ingest producers write ``Source-Discovery: unresolved``
    and downstream validators check it. Document-level checks, not live
    agent execution."""

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def test_ingest_producers_write_source_discovery(self):
        """Both ingest files produce Source-Discovery: unresolved marker."""
        for rel in ["implement/skills/ingest.md",
                     "e2e/skills/ingest.md"]:
            text = (self._repo_root() / rel).read_text(encoding="utf-8")
            self.assertIn("Source-Discovery: unresolved", text,
                          f"{rel} must produce Source-Discovery marker")

    def test_ingest_unresolved_source_includes_discovery(self):
        """Freshness: unresolved-source marker co-occurs with
        Source-Discovery: unresolved in the minimal marker block."""
        import re as _re
        for rel in ["implement/skills/ingest.md",
                     "e2e/skills/ingest.md"]:
            text = (self._repo_root() / rel).read_text(encoding="utf-8")
            # Find fenced blocks (possibly indented, with optional
            # language specifier after the opening backticks)
            blocks = _re.findall(
                r"[ \t]*```[^\n]*\n(.*?)[ \t]*```", text, _re.DOTALL)
            marker_blocks = [b for b in blocks
                             if "Freshness: unresolved-source" in b]
            self.assertGreater(
                len(marker_blocks), 0,
                f"{rel}: must have a marker block with "
                f"Freshness: unresolved-source")
            for block in marker_blocks:
                self.assertIn("Source-Discovery: unresolved", block,
                              f"{rel}: unresolved-source marker block "
                              f"must also contain Source-Discovery")

    def test_validators_check_source_discovery(self):
        """Both validate files check Source-Discovery for PASS blocking."""
        for rel in ["implement/skills/validate.md",
                     "e2e/skills/validate.md"]:
            text = (self._repo_root() / rel).read_text(encoding="utf-8")
            self.assertIn("Source-Discovery", text,
                          f"{rel} must check Source-Discovery state")
            # Verify it blocks PASS
            import re as _re
            normalized = _re.sub(r'\s+', ' ', text.lower())
            self.assertIn("source-discovery", normalized)
            # Should mention it blocks PASS
            self.assertTrue(
                "cannot be pass" in normalized
                or "cannot pass" in normalized
                or "blocks overall: pass" in normalized
                or "cannot be pass" in normalized,
                f"{rel} must state Source-Discovery blocks PASS")


class TestValidateCleanWorktreeGuards(unittest.TestCase):
    """Static contract: e2e validate has clean-worktree checks at BOTH
    required positions — before tests AND before final identity binding.

    Document-level checks reading actual e2e/skills/validate.md section
    ordering, not live agent execution."""

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def test_e2e_validate_has_pretest_clean_check(self):
        """e2e validate has a clean-worktree guard before test execution."""
        text = (self._repo_root() /
                "e2e/skills/validate.md").read_text(encoding="utf-8")
        # Pre-test check: "clean before running any validation"
        self.assertIn(
            "clean before running any validation", text,
            "e2e/validate must have pre-test clean-worktree guard")

    def test_e2e_validate_has_identity_clean_check(self):
        """e2e validate has a clean-worktree guard before identity binding.

        The guard must appear INSIDE the ## Validated Identity section,
        before the identity fields are recorded."""
        text = (self._repo_root() /
                "e2e/skills/validate.md").read_text(encoding="utf-8")
        identity_pos = text.find("## Validated Identity")
        self.assertGreater(identity_pos, 0,
                           "e2e/validate must have ## Validated Identity")
        result_pos = text.find("## Result", identity_pos)
        self.assertGreater(result_pos, identity_pos,
                           "## Result must follow ## Validated Identity")
        # The clean check must be between ## Validated Identity and
        # ## Result (i.e., inside the identity section)
        identity_section = text[identity_pos:result_pos]
        self.assertIn(
            "git status --porcelain", identity_section,
            "## Validated Identity section must contain "
            "git status --porcelain clean check")
        self.assertIn(
            "uncommitted", identity_section,
            "## Validated Identity section must mention uncommitted "
            "changes as a stop condition")

    def test_identity_clean_check_before_branch_head(self):
        """The clean check appears before the identity fields."""
        text = (self._repo_root() /
                "e2e/skills/validate.md").read_text(encoding="utf-8")
        identity_pos = text.find("## Validated Identity")
        identity_section = text[identity_pos:]
        clean_pos = identity_section.find("git status --porcelain")
        head_pos = identity_section.find("**Branch HEAD:**")
        self.assertGreater(clean_pos, 0,
                           "Must have clean check in identity section")
        self.assertGreater(head_pos, 0,
                           "Must have Branch HEAD field")
        self.assertLess(clean_pos, head_pos,
                        "Clean check must come before Branch HEAD field")


# ---------------------------------------------------------------------------
# Recipe/caller integration: preflight-before-write, copy+provenance-before-stage
# ---------------------------------------------------------------------------

class TestRecipeCallerIntegration(unittest.TestCase):
    """Static instruction-order and real Git fixture tests for the three
    sync-recipe callers (publish, revise, respond).

    These tests verify the documented-event ordering that guarantees:
    1. Recipe PREFLIGHT completes before any DOCS copy/mkdir/stage
    2. Design cp + provenance happen AFTER recipe APPLY (directory exists)
    3. Design is staged AFTER being written (not before)

    Static assertions read the Markdown instructions to verify ordering.
    Git fixture tests execute the actual cp/git-add commands against a
    temporary repository to verify commit contents.

    NOTE: These are static instruction-order proofs and local Git fixture
    tests, NOT live agent or workflow execution claims.
    """

    @classmethod
    def _repo_root(cls) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def _read_caller(self, name: str) -> str:
        return (self._repo_root() /
                f"design/skills/{name}.md").read_text(encoding="utf-8")

    def _read_recipe(self) -> str:
        return (self._repo_root() /
                "_shared/recipes/sync-validation-artifacts.md").read_text(
                    encoding="utf-8")

    # --- Static instruction-order tests ---

    def test_all_callers_recipe_before_design_copy(self):
        """All 3 callers reference sync recipe BEFORE design cp command.
        Static instruction-order proof, not live agent execution."""
        for caller in ("publish", "revise", "respond"):
            text = self._read_caller(caller)
            recipe_pos = text.find("sync-validation-artifacts.md")
            copy_pos = text.find(
                'cp ".artifacts/design/{issue-key}/03-design.md"')
            self.assertGreater(recipe_pos, -1,
                               f"{caller}: must reference sync recipe")
            self.assertGreater(copy_pos, -1,
                               f"{caller}: must have design copy command")
            self.assertLess(recipe_pos, copy_pos,
                            f"{caller}: recipe must precede design copy")

    def test_all_callers_design_copy_before_stage(self):
        """All 3 callers copy design and render provenance BEFORE staging.
        Static instruction-order proof, not live agent execution."""
        for caller in ("publish", "revise", "respond"):
            text = self._read_caller(caller)
            copy_pos = text.find(
                'cp ".artifacts/design/{issue-key}/03-design.md"')
            prov_pos = text.find("render-provenance-footer.md",
                                 copy_pos if copy_pos > -1 else 0)
            # Find the git add for design that follows the copy
            stage_pos = text.find('git -C "{docs_repo_path}" add',
                                  prov_pos if prov_pos > -1 else 0)
            self.assertGreater(copy_pos, -1,
                               f"{caller}: design copy must exist")
            self.assertGreater(prov_pos, -1,
                               f"{caller}: provenance must exist after copy")
            self.assertGreater(stage_pos, -1,
                               f"{caller}: design staging must exist")
            self.assertLess(copy_pos, prov_pos,
                            f"{caller}: copy before provenance")
            self.assertLess(prov_pos, stage_pos,
                            f"{caller}: provenance before staging")

    def test_recipe_preflight_before_apply(self):
        """Recipe defines PREFLIGHT before APPLY, with no mkdir/cp/stage
        in PREFLIGHT. Static proof on recipe file."""
        recipe = self._read_recipe()
        preflight_pos = recipe.find("### PREFLIGHT Phase")
        apply_pos = recipe.find("### APPLY Phase")
        self.assertGreater(preflight_pos, -1)
        self.assertGreater(apply_pos, -1)
        self.assertLess(preflight_pos, apply_pos)
        # No mkdir, cp, or git-add in PREFLIGHT section
        preflight_section = recipe[preflight_pos:apply_pos]
        self.assertNotIn("mkdir -p", preflight_section,
                         "PREFLIGHT must not create directories")
        self.assertNotIn("git add", preflight_section,
                         "PREFLIGHT must not stage files")

    def test_recipe_no_design_staging(self):
        """Recipe does not stage design file — callers handle that after
        copying and rendering provenance. Static proof."""
        recipe = self._read_recipe()
        apply_section = recipe[recipe.find("### APPLY Phase"):]
        # No step that stages DESIGN_FILE_PATH
        self.assertNotIn('add "{DESIGN_FILE_PATH}"', apply_section,
                         "Recipe APPLY must not stage the design file — "
                         "callers stage after copy+provenance")

    def test_publish_no_duplicate_preflight(self):
        """publish.md must not inline its own preflight that duplicates
        the recipe's PREFLIGHT. Static proof."""
        text = self._read_caller("publish")
        recipe_pos = text.find("sync-validation-artifacts.md")
        # Before the recipe reference, there should be no inline
        # resolve --local or transform/diff preflight commands
        before_recipe = text[:recipe_pos]
        self.assertNotIn('resolve --local', before_recipe,
                         "No inline resolve before recipe — "
                         "recipe PREFLIGHT handles this")
        self.assertNotIn('"$VALIDATION_INDEX_SCRIPT" diff', before_recipe,
                         "No inline diff before recipe — "
                         "recipe PREFLIGHT handles this")

    def test_revise_respond_no_mkdir_before_recipe(self):
        """revise.md and respond.md must not mkdir before recipe call.
        Static proof — recipe APPLY creates the directory."""
        for caller in ("revise", "respond"):
            text = self._read_caller(caller)
            recipe_pos = text.find("sync-validation-artifacts.md")
            before_recipe = text[:recipe_pos]
            self.assertNotIn(
                'mkdir -p "{docs_repo_path}', before_recipe,
                f"{caller}: no mkdir before recipe — "
                "recipe APPLY step 5 creates the directory")

    # --- Git fixture tests ---

    def test_first_publish_design_in_commit(self):
        """First publish: design copy + stage after recipe APPLY produces
        a commit containing the design file. Real Git fixture test.

        Simulates the documented caller sequence: recipe APPLY creates
        the directory, then caller copies design + stages it, then commits.
        Verifies the committed tree contains the design content.
        """
        tmpdir = tempfile.mkdtemp(prefix="recipe_integ_")
        try:
            docs = os.path.join(tmpdir, "docs")
            subprocess.run(["git", "init", docs],
                           check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "config", "user.email", "t@t.com"],
                check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "config", "user.name", "T"],
                check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "config", "commit.gpgsign", "false"],
                check=True, capture_output=True)
            empty_hooks = os.path.join(tmpdir, "empty-hooks")
            os.makedirs(empty_hooks, exist_ok=True)
            subprocess.run(
                ["git", "-C", docs, "config", "core.hooksPath", empty_hooks],
                check=True, capture_output=True)
            # Initial commit
            Path(docs, "README.md").write_text("init\n")
            subprocess.run(["git", "-C", docs, "add", "README.md"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", docs, "commit", "-m", "init"],
                           check=True, capture_output=True)

            feature_dir = os.path.join(docs, "v1", "feat")
            design_content = "# Design\nSection content here.\n"

            # Simulate recipe APPLY step 5: mkdir
            os.makedirs(feature_dir, exist_ok=True)

            # Simulate caller: copy design AFTER recipe APPLY
            design_path = os.path.join(feature_dir, "design.md")
            with open(design_path, "w") as f:
                f.write(design_content)

            # Simulate caller: stage design AFTER copy
            subprocess.run(
                ["git", "-C", docs, "add", "v1/feat/design.md"],
                check=True, capture_output=True)

            # Commit
            subprocess.run(
                ["git", "-C", docs, "commit", "-m", "publish design"],
                check=True, capture_output=True)

            # Verify: committed design matches what was copied
            result = subprocess.run(
                ["git", "-C", docs, "show", "HEAD:v1/feat/design.md"],
                check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, design_content,
                             "Committed design must match copied content")
        finally:
            shutil.rmtree(tmpdir)

    def test_design_update_stages_new_content(self):
        """Design update: old design exists, new content is copied and
        staged AFTER recipe APPLY. The commit must contain the NEW content,
        not the old. Real Git fixture test.

        This is the regression case: if staging happens before copy,
        the commit would contain stale content.
        """
        tmpdir = tempfile.mkdtemp(prefix="recipe_integ_")
        try:
            docs = os.path.join(tmpdir, "docs")
            subprocess.run(["git", "init", docs],
                           check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "config", "user.email", "t@t.com"],
                check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "config", "user.name", "T"],
                check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "config", "commit.gpgsign", "false"],
                check=True, capture_output=True)
            empty_hooks = os.path.join(tmpdir, "empty-hooks")
            os.makedirs(empty_hooks, exist_ok=True)
            subprocess.run(
                ["git", "-C", docs, "config", "core.hooksPath", empty_hooks],
                check=True, capture_output=True)

            feature_dir = os.path.join(docs, "v1", "feat")
            os.makedirs(feature_dir, exist_ok=True)

            old_content = "# OLD Design\nStale.\n"
            new_content = "# NEW Design\nFresh content.\n"
            design_path = os.path.join(feature_dir, "design.md")

            # Initial commit with old design
            with open(design_path, "w") as f:
                f.write(old_content)
            subprocess.run(["git", "-C", docs, "add", "."],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", docs, "commit", "-m", "old"],
                           check=True, capture_output=True)

            # Simulate CORRECT order: copy new content THEN stage
            with open(design_path, "w") as f:
                f.write(new_content)
            subprocess.run(
                ["git", "-C", docs, "add", "v1/feat/design.md"],
                check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", docs, "commit", "-m", "update design"],
                check=True, capture_output=True)

            # Verify: committed content is the NEW content
            result = subprocess.run(
                ["git", "-C", docs, "show", "HEAD:v1/feat/design.md"],
                check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, new_content,
                             "Committed design must be NEW content, not stale")

            # Counter-test: if we had staged BEFORE copying (the old bug),
            # the commit would contain old content
            # Reset to old commit
            subprocess.run(
                ["git", "-C", docs, "reset", "--hard", "HEAD~1"],
                check=True, capture_output=True)
            # Stage FIRST (old content), then copy new
            subprocess.run(
                ["git", "-C", docs, "add", "v1/feat/design.md"],
                check=True, capture_output=True)
            with open(design_path, "w") as f:
                f.write(new_content)
            # Commit WITHOUT re-staging
            subprocess.run(
                ["git", "-C", docs, "commit", "-m", "buggy update",
                 "--allow-empty"],
                check=True, capture_output=True)
            result = subprocess.run(
                ["git", "-C", docs, "show", "HEAD:v1/feat/design.md"],
                check=True, capture_output=True, text=True)
            # This demonstrates the bug: staged old, copied new without
            # re-staging → commit has old content
            self.assertEqual(result.stdout, old_content,
                             "Counter-test: stage-before-copy commits stale")
        finally:
            shutil.rmtree(tmpdir)

    def test_sync_recipe_approval_before_apply_contract(self):
        """The sync recipe requires named removal approval in PREFLIGHT
        before APPLY begins. Static contract check: verify the recipe
        text enforces this ordering — approval clauses appear before
        the APPLY Phase heading.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        recipe_path = os.path.join(
            repo_root, "_shared", "recipes", "sync-validation-artifacts.md")
        content = Path(recipe_path).read_text()

        apply_pos = content.find("### APPLY Phase")
        self.assertGreater(apply_pos, 0,
                           "Recipe must contain an APPLY Phase heading")

        # The approval requirement must appear before APPLY
        approval_clause = "require named confirmation"
        approval_pos = content.find(approval_clause)
        self.assertGreater(approval_pos, 0,
                           f"Recipe must contain '{approval_clause}'")
        self.assertLess(approval_pos, apply_pos,
                        "Named removal approval must appear before APPLY Phase")

        # The stop-on-decline rule must also appear before APPLY
        stop_clause = "stop and report"
        # Find the stop clause in the PREFLIGHT section (before APPLY)
        preflight_section = content[:apply_pos]
        self.assertIn(stop_clause, preflight_section,
                      "PREFLIGHT must contain a stop-and-report rule before APPLY")

    def test_sync_recipe_index_destination_check_before_apply(self):
        """The sync recipe must check published index destination
        (symlink/ancestor) in PREFLIGHT before any APPLY writes.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        recipe_path = os.path.join(
            repo_root, "_shared", "recipes", "sync-validation-artifacts.md")
        content = Path(recipe_path).read_text()

        apply_pos = content.find("### APPLY Phase")
        self.assertGreater(apply_pos, 0)

        preflight = content[:apply_pos]
        # Published index destination check must be in PREFLIGHT
        self.assertIn("validation-index.json",
                      preflight.split("#### 4.")[1] if "#### 4." in preflight else "",
                      "Step 4 must check published index destination")
        self.assertIn("dangling symlink", preflight.lower().replace("dangling symlinks", "dangling symlink"),
                      "PREFLIGHT must guard against dangling symlinks at index destination")

    def test_restore_recipe_tc_heading_matches_draft_producer(self):
        """The restore recipe TC heading pattern must match what
        draft.md actually produces (H4 #### TC-{id}:), not the
        story-testplan template (H2 ## {tc-id}:).
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        restore_path = os.path.join(
            repo_root, "_shared", "recipes", "restore-validation-artifacts.md")
        content = Path(restore_path).read_text()

        # Must reference H4 pattern as primary
        self.assertIn("#### TC-{id}:", content,
                      "Restore recipe must reference H4 TC heading pattern")
        # Must NOT use only H2 pattern
        self.assertNotIn("`## TC-xxx`", content,
                         "Restore recipe must not use H2-only TC heading pattern")

    def test_revise_step1_no_impossible_empty_fallback(self):
        """revise.md Step 1 must not have the unreachable
        'empty result + file exists = fallback' branch. The resolver
        already returns the legacy file in its array.
        """
        revise_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "skills", "revise.md")
        content = Path(revise_path).read_text()

        # The old unreachable pattern should be gone
        self.assertNotIn(
            "fall back to reading it directly",
            content,
            "revise.md must not have the impossible empty-result legacy fallback")
        # The correct resolver-handles-legacy language should be present
        self.assertIn(
            "resolver already handles",
            content,
            "revise.md must document that the resolver handles legacy layouts")

    def test_draft_index_write_outside_optional_step(self):
        """draft.md mandatory validation-index.json write must appear
        after the optional companion step ends, before Step 10
        presentation. Static heading-boundary check.
        """
        draft_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "skills", "draft.md")
        content = Path(draft_path).read_text()

        optional_heading = "#### 9e: Companion Validation Plans (Optional)"
        index_heading = "#### Write and Validate the Validation Index (Required)"
        step10_heading = "### Step 10:"
        optional_pos = content.find(optional_heading)
        index_pos = content.find(index_heading)
        step10_pos = content.find(step10_heading)

        self.assertGreater(optional_pos, 0,
                           "draft.md must have the optional companion step")
        self.assertGreater(index_pos, 0,
                           "draft.md must have the required index write subsection")
        self.assertGreater(index_pos, optional_pos,
                           "Index write must follow the optional companion step")
        self.assertGreater(step10_pos, index_pos,
                           "Index write must come before Step 10 presentation")
        # The index write instruction must be inside the required section
        index_write = "**Write the validation index.**"
        write_pos = content.find(index_write)
        self.assertGreater(write_pos, index_pos,
                           "Index write instruction must be after the required heading")

    def test_e2e_validate_source_discovery_precedence_in_gapfill(self):
        """e2e validate gap-fill must check Source-Discovery: unresolved
        before treating confirmed TCs as normative.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        validate_path = os.path.join(
            repo_root, "e2e", "skills", "validate.md")
        content = Path(validate_path).read_text()

        # Find the gap-fill section
        gapfill_marker = "If any automatable TC ID lacks a corresponding test"
        gapfill_pos = content.find(gapfill_marker)
        self.assertGreater(gapfill_pos, 0,
                           "validate.md must have the gap-fill section")

        # Source-Discovery check must appear before the normative gap-fill rule
        gapfill_section = content[gapfill_pos:gapfill_pos + 1500]
        sd_pos = gapfill_section.find("Source-Discovery: unresolved")
        normative_pos = gapfill_section.find("effectively confirmed TCs or verified-source TCs")
        self.assertGreater(sd_pos, 0,
                           "Gap-fill must check Source-Discovery: unresolved")
        self.assertLess(sd_pos, normative_pos,
                        "Source-Discovery check must come before normative gap-fill")

    def test_e2e_publish_nofx_continuation(self):
        """e2e publish must have explicit no-fix PASS continuation to
        Step 3, not unconditional 'fix commit changed HEAD' stop.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        publish_path = os.path.join(
            repo_root, "e2e", "skills", "publish.md")
        content = Path(publish_path).read_text()

        self.assertIn(
            "without making any code fixes",
            content,
            "e2e publish must have the no-fix continuation branch")

    def test_story_testplan_template_has_qualification_gates(self):
        """implement/templates/story-testplan.md must have a standalone
        ## Qualification Gates section for gate-only and mixed plans.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(
            repo_root, "implement", "templates", "story-testplan.md")
        content = Path(template_path).read_text()

        self.assertIn(
            "## Qualification Gates",
            content,
            "Template must have a standalone Qualification Gates section")

    def test_decompose_fallback_loads_all_companions(self):
        """decompose.md fallback re-review must load all resolved
        validation artifacts, not just 04-testplan.md.
        """
        decompose_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "skills", "decompose.md")
        content = Path(decompose_path).read_text()

        fallback_marker = "If resumption is not available"
        fallback_pos = content.find(fallback_marker)
        self.assertGreater(fallback_pos, 0)

        fallback_section = content[fallback_pos:fallback_pos + 500]
        # Must NOT hard-code only 04-testplan.md
        self.assertNotIn(
            "the testplan (`04-testplan.md`)",
            fallback_section,
            "Fallback must not hard-code only 04-testplan.md")
        # Must reference all validation artifacts
        self.assertIn(
            "companions",
            fallback_section,
            "Fallback must reference companion artifacts")

    def test_both_validators_gate_confirmation_procedure(self):
        """Both validators must have an operational non-TC gate
        confirmation procedure for mixed AND gate-only testplans,
        not just report-level classification. Static contract check.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))

        for workflow in ("e2e", "implement"):
            validate_path = os.path.join(
                repo_root, workflow, "skills", "validate.md")
            content = Path(validate_path).read_text()

            # Must have operational gate confirmation procedure
            self.assertIn(
                "Non-TC gate confirmation (mixed and gate-only",
                content,
                f"{workflow}/validate.md must have gate confirmation "
                f"covering both mixed and gate-only plans")
            # Must cover Source-Discovery precedence over gate confirmation
            self.assertIn(
                "Source-Discovery: unresolved" + "` is present, all retained gates",
                content,
                f"{workflow}/validate.md gate confirmation must note "
                f"Source-Discovery precedence")
            # Must NOT silently treat unverified gates as authoritative
            self.assertIn(
                "Do not invent automated gate confirmation",
                content,
                f"{workflow}/validate.md must prohibit automatic "
                f"gate authority")

    def test_both_validators_result_mandatory_classification(self):
        """Both validator report templates must classify mandatory
        entries consistently: confirmed gates, current AC obligations,
        and no override of current method by provisional mentions.
        Static section check.
        """
        repo_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))

        for workflow in ("e2e", "implement"):
            validate_path = os.path.join(
                repo_root, workflow, "skills", "validate.md")
            content = Path(validate_path).read_text()

            # The mandatory classification and verdict text may span
            # External Validation Evidence and Result sections. Check
            # from the first Mandatory entries occurrence to end of file.
            mand_pos = content.find("Mandatory entries are:")
            self.assertGreater(mand_pos, 0,
                               f"{workflow}/validate.md must have mandatory "
                               f"classification")
            result_section = content[mand_pos:]

            # Mandatory entries must reference confirmed gates, not "all required"
            self.assertIn(
                "onfirmed non-TC qualification gates",
                result_section,
                f"{workflow}/validate.md Result must classify gates as "
                f"confirmed, not unconditionally required")
            # Current AC obligations always mandatory
            self.assertIn(
                "Current AC obligations are always mandatory",
                result_section,
                f"{workflow}/validate.md Result must keep ACs mandatory")
            # Provisional mention cannot override current method
            self.assertIn(
                "does not override",
                result_section,
                f"{workflow}/validate.md Result must prevent provisional "
                f"override of current verification method")


if __name__ == "__main__":
    unittest.main()
