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
# 25. Snapshot/Git consumer regressions
# ===========================================================================

class TestSnapshotGitConsumerRegressions(unittest.TestCase):
    """Real snapshot/diff/retire lifecycle with temp Git repos.

    Exercises the documented publish workflow paths:
    - First publish: no previous snapshot
    - Stale snapshot with missing source
    - Valid published index round-trip
    - Canonical legacy snapshot (testplan.md only)
    - Invalid previous snapshot stops before doc mutation
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
        """Initialize a bare git repo with an initial commit."""
        subprocess.run(["git", "init", str(path)],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(path), "config",
                        "user.email", "test@test.com"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(path), "config",
                        "user.name", "Test"],
                       capture_output=True, check=True)
        # Create initial commit
        (path / ".gitkeep").write_text("")
        subprocess.run(["git", "-C", str(path), "add", ".gitkeep"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(path), "commit",
                        "-m", "initial"],
                       capture_output=True, check=True)

    def test_first_publish_no_previous_snapshot(self):
        """First publish: empty old → diff shows all artifacts as added."""
        with tempfile.TemporaryDirectory() as td:
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


if __name__ == "__main__":
    unittest.main()
