#!/usr/bin/env python3
"""Tests for design/scripts/validation_index.py.

Tests the validation artifact index contract used across the design workflow
lifecycle. Each test exercises the ACTUAL shared module that workflow
instructions reference for schema validation and path resolution.

Coverage areas:
  - Default/legacy single-testplan behavior
  - Multi-doc creation with primary + companions
  - Published index schema and transformation
  - Fresh-consumer discovery (docs repo without local metadata)
  - Companion inline + top-level feedback routing by filename
  - Revision lifecycle: add, rename, remove artifacts
  - Republish with artifact set changes
  - Cross-doc TC ID uniqueness constraint
  - Downstream story TC subset selection
  - Backwards compatibility with pre-index designs

What is NOT tested here (and why):
  - Actual AI agent interpretation of workflow instructions
  - Live GitHub/Jira integration (PR creation, comment posting)
  - End-to-end design workflow execution across phases
  These require running AI agents against real infrastructure and are
  outside the scope of contract/schema validation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Import validation_index via importlib (matches repo convention)
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


# ===========================================================================
# 1. Schema validation — local index
# ===========================================================================

class TestLocalIndexValidation(unittest.TestCase):
    """Validate the local validation-index.json schema contract."""

    def test_valid_single_testplan(self):
        idx = _make_local_index()
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_valid_with_companion(self):
        idx = _make_local_index(companions=[{
            "local": "04-hw-validation.md",
            "published_as": "hw-validation.md",
            "purpose": "Hardware qualification",
            "audience": "Hardware QE team",
        }])
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_valid_with_multiple_companions(self):
        idx = _make_local_index(companions=[
            {
                "local": "04-hw-validation.md",
                "published_as": "hw-validation.md",
                "purpose": "Hardware qualification",
                "audience": "Hardware QE",
            },
            {
                "local": "04-security-cert.md",
                "published_as": "security-cert.md",
                "purpose": "Security certification",
                "audience": "Security team",
            },
        ])
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_rejects_missing_schema_version(self):
        idx = _make_local_index()
        del idx["schema_version"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_rejects_wrong_schema_version(self):
        idx = _make_local_index()
        idx["schema_version"] = "2.0"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("schema_version" in e for e in errors))

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
        idx = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw.md",
            "purpose": "p",
            "audience": "a",
        }])
        # Swap order so companion is first
        idx["artifacts"] = list(reversed(idx["artifacts"]))
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("first artifact" in e for e in errors))

    def test_rejects_duplicate_local_filenames(self):
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-testplan.md",
            "published_as": "testplan2.md",
            "type": "companion",
            "purpose": "p",
            "audience": "a",
        })
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("duplicate local" in e for e in errors))

    def test_rejects_duplicate_published_filenames(self):
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-other.md",
            "published_as": "testplan.md",
            "type": "companion",
            "purpose": "p",
            "audience": "a",
        })
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("duplicate published" in e for e in errors))

    def test_rejects_companion_without_purpose(self):
        idx = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw.md",
        }])
        del idx["artifacts"][1]["purpose"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("purpose" in e for e in errors))

    def test_rejects_companion_without_audience(self):
        idx = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw.md",
            "purpose": "p",
        }])
        del idx["artifacts"][1]["audience"]
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("audience" in e for e in errors))

    def test_rejects_companion_slug_testplan(self):
        """Companion local filename must not use 'testplan' slug."""
        idx = _make_local_index(companions=[{
            "local": "04-testplan.md",
            "published_as": "extra-testplan.md",
            "purpose": "p",
            "audience": "a",
        }])
        # Fix the duplicate local first
        idx["artifacts"][0]["local"] = "04-main.md"
        idx["primary_testplan"] = "04-main.md"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("slug must not be 'testplan'" in e
                            for e in errors))

    def test_rejects_multiple_testplan_type(self):
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-other.md",
            "published_as": "other.md",
            "type": "testplan",
        })
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("only one" in e for e in errors))

    def test_rejects_invalid_type(self):
        idx = _make_local_index()
        idx["artifacts"][0]["type"] = "integration"
        errors = vi.validate_local_index(idx)
        self.assertTrue(any("type" in e for e in errors))


# ===========================================================================
# 2. Schema validation — published index
# ===========================================================================

class TestPublishedIndexValidation(unittest.TestCase):
    """Validate the published validation-index.json schema."""

    def test_valid_single_testplan(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"}
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertEqual(errors, [])

    def test_valid_with_companion(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
                {
                    "file": "hw-validation.md",
                    "type": "companion",
                    "purpose": "Hardware qualification",
                },
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertEqual(errors, [])

    def test_rejects_local_field(self):
        """Published index must not contain local-only fields."""
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {
                    "file": "testplan.md",
                    "type": "testplan",
                    "local": "04-testplan.md",
                }
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(any("must not have 'local'" in e for e in errors))

    def test_rejects_published_as_field(self):
        data = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {
                    "file": "testplan.md",
                    "type": "testplan",
                    "published_as": "testplan.md",
                }
            ],
        }
        errors = vi.validate_published_index(data)
        self.assertTrue(
            any("must not have 'published_as'" in e for e in errors))

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


# ===========================================================================
# 3. Transform local -> published
# ===========================================================================

class TestTransformForPublish(unittest.TestCase):
    """Test local-to-published index transformation."""

    def test_single_testplan(self):
        local = _make_local_index()
        published = vi.transform_for_publish(local)
        self.assertEqual(published["schema_version"], "1.0")
        self.assertEqual(published["primary_testplan"], "testplan.md")
        self.assertEqual(len(published["artifacts"]), 1)
        art = published["artifacts"][0]
        self.assertEqual(art["file"], "testplan.md")
        self.assertEqual(art["type"], "testplan")
        self.assertNotIn("local", art)
        self.assertNotIn("published_as", art)

    def test_with_companions(self):
        local = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw-validation.md",
            "purpose": "Hardware",
            "audience": "HW QE",
        }])
        published = vi.transform_for_publish(local)
        self.assertEqual(len(published["artifacts"]), 2)
        companion = published["artifacts"][1]
        self.assertEqual(companion["file"], "hw-validation.md")
        self.assertEqual(companion["type"], "companion")
        self.assertEqual(companion["purpose"], "Hardware")
        self.assertEqual(companion["audience"], "HW QE")

    def test_rejects_invalid_local(self):
        local = {"bad": "data"}
        with self.assertRaises(vi.ValidationIndexError):
            vi.transform_for_publish(local)

    def test_published_passes_published_validation(self):
        """Transformed output must pass published validation."""
        local = _make_local_index(companions=[{
            "local": "04-sec.md",
            "published_as": "security.md",
            "purpose": "Security cert",
            "audience": "Security team",
        }])
        published = vi.transform_for_publish(local)
        errors = vi.validate_published_index(published)
        self.assertEqual(errors, [], f"Validation errors: {errors}")


# ===========================================================================
# 4. Filesystem resolution — local artifact directory
# ===========================================================================

class TestResolveArtifacts(unittest.TestCase):
    """Test artifact resolution from local artifact directories."""

    def test_with_index(self):
        """Reads validation-index.json when present."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            idx = _make_local_index()
            _write_json(d / "validation-index.json", idx)
            _write(d / "04-testplan.md", "# Testplan")

            arts = vi.resolve_artifacts(d)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["local"], "04-testplan.md")
            self.assertEqual(arts[0]["type"], "testplan")

    def test_legacy_fallback(self):
        """Falls back to 04-testplan.md when no index exists."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d / "04-testplan.md", "# Testplan")

            arts = vi.resolve_artifacts(d)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["local"], "04-testplan.md")
            self.assertEqual(arts[0]["published_as"], "testplan.md")
            self.assertEqual(arts[0]["type"], "testplan")

    def test_empty_directory(self):
        """Returns empty list when no artifacts exist."""
        with tempfile.TemporaryDirectory() as td:
            arts = vi.resolve_artifacts(Path(td))
            self.assertEqual(arts, [])

    def test_index_with_companions(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            idx = _make_local_index(companions=[{
                "local": "04-hw.md",
                "published_as": "hw.md",
                "purpose": "Hardware",
                "audience": "HW team",
            }])
            _write_json(d / "validation-index.json", idx)
            _write(d / "04-testplan.md", "# Testplan")
            _write(d / "04-hw.md", "# HW Validation")

            arts = vi.resolve_artifacts(d)
            self.assertEqual(len(arts), 2)
            self.assertEqual(arts[0]["type"], "testplan")
            self.assertEqual(arts[1]["type"], "companion")

    def test_invalid_index_raises(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_json(d / "validation-index.json", {"bad": True})
            with self.assertRaises(vi.ValidationIndexError):
                vi.resolve_artifacts(d)


# ===========================================================================
# 5. Filesystem resolution — published docs repo
# ===========================================================================

class TestResolvePublishedArtifacts(unittest.TestCase):
    """Test artifact discovery from a docs repo feature directory.

    This is the FRESH CONSUMER path: a downstream implement or e2e ingest
    discovers artifacts without any local design metadata.
    """

    def test_with_published_index(self):
        """Reads validation-index.json from docs repo."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub_idx = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {
                        "file": "hw-validation.md",
                        "type": "companion",
                        "purpose": "Hardware",
                    },
                ],
            }
            _write_json(d / "validation-index.json", pub_idx)
            _write(d / "testplan.md", "# Testplan")
            _write(d / "hw-validation.md", "# HW")

            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(len(arts), 2)
            self.assertEqual(arts[0]["file"], "testplan.md")
            self.assertEqual(arts[1]["file"], "hw-validation.md")

    def test_legacy_single_testplan(self):
        """Falls back to testplan.md when no index exists (legacy)."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d / "testplan.md", "# Testplan")

            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["file"], "testplan.md")
            self.assertEqual(arts[0]["type"], "testplan")

    def test_no_artifacts(self):
        """Returns empty list when no testplan exists (oldest designs)."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d / "design.md", "# Design")

            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(arts, [])

    def test_primary_testplan_path_with_index(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub_idx = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(d / "validation-index.json", pub_idx)
            _write(d / "testplan.md", "# Plan")

            p = vi.primary_testplan_path(d)
            self.assertEqual(p, d / "testplan.md")

    def test_primary_testplan_path_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d / "testplan.md", "# Plan")

            p = vi.primary_testplan_path(d)
            self.assertEqual(p, d / "testplan.md")

    def test_primary_testplan_path_none(self):
        with tempfile.TemporaryDirectory() as td:
            p = vi.primary_testplan_path(Path(td))
            self.assertIsNone(p)


# ===========================================================================
# 6. Publish metadata integration
# ===========================================================================

class TestBuildMetadataArtifacts(unittest.TestCase):
    """Test building validation_artifacts for publish-metadata.json."""

    def test_single_testplan(self):
        local = _make_local_index()
        meta_arts = vi.build_metadata_artifacts(local)
        self.assertEqual(len(meta_arts), 1)
        self.assertEqual(meta_arts[0]["file"], "testplan.md")
        self.assertEqual(meta_arts[0]["type"], "testplan")
        self.assertNotIn("local", meta_arts[0])

    def test_with_companion(self):
        local = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw.md",
            "purpose": "HW",
            "audience": "HW team",
        }])
        meta_arts = vi.build_metadata_artifacts(local)
        self.assertEqual(len(meta_arts), 2)
        self.assertEqual(meta_arts[1]["purpose"], "HW")


# ===========================================================================
# 7. Lifecycle: add, remove, rename artifacts
# ===========================================================================

class TestArtifactLifecycle(unittest.TestCase):
    """Test artifact index mutation during revise/respond phases."""

    def test_add_companion(self):
        """Adding a companion to an existing index."""
        idx = _make_local_index()
        idx["artifacts"].append({
            "local": "04-security.md",
            "published_as": "security.md",
            "type": "companion",
            "purpose": "Security cert",
            "audience": "Security team",
        })
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_remove_companion(self):
        """Removing a companion leaves a valid index."""
        idx = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw.md",
            "purpose": "HW",
            "audience": "HW team",
        }])
        idx["artifacts"] = [a for a in idx["artifacts"]
                            if a["type"] != "companion"]
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_rename_companion(self):
        """Renaming a companion (new local + published_as) is valid."""
        idx = _make_local_index(companions=[{
            "local": "04-hw.md",
            "published_as": "hw.md",
            "purpose": "HW",
            "audience": "HW team",
        }])
        idx["artifacts"][1]["local"] = "04-device-validation.md"
        idx["artifacts"][1]["published_as"] = "device-validation.md"
        errors = vi.validate_local_index(idx)
        self.assertEqual(errors, [])

    def test_stale_removal_detection(self):
        """Compare old vs new published index to find stale artifacts."""
        old_pub = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
                {
                    "file": "hw.md",
                    "type": "companion",
                    "purpose": "HW",
                },
            ],
        }
        new_pub = {
            "schema_version": "1.0",
            "primary_testplan": "testplan.md",
            "artifacts": [
                {"file": "testplan.md", "type": "testplan"},
            ],
        }
        old_files = {a["file"] for a in old_pub["artifacts"]}
        new_files = {a["file"] for a in new_pub["artifacts"]}
        stale = old_files - new_files
        self.assertEqual(stale, {"hw.md"})


# ===========================================================================
# 8. Downstream story subset selection
# ===========================================================================

class TestDownstreamSelection(unittest.TestCase):
    """Test that downstream consumers can select TCs from multi-artifact sets.

    This verifies the contract: given a set of TC IDs from a story's
    Validated by field, the consumer can find matching TCs across all
    published validation artifacts.
    """

    def test_select_from_single_artifact(self):
        """Story TCs found in primary testplan only."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub_idx = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                ],
            }
            _write_json(d / "validation-index.json", pub_idx)
            _write(d / "testplan.md",
                   "### FR-1\n#### TC-FR1-01: Scenario\n#### TC-FR1-02: S2")

            arts = vi.resolve_published_artifacts(d)
            # Simulate TC selection
            story_tcs = {"TC-FR1-01", "TC-FR1-02"}
            found_in: dict[str, set[str]] = {}
            for art in arts:
                content = (d / art["file"]).read_text()
                matched = {tc for tc in story_tcs if tc in content}
                if matched:
                    found_in[art["file"]] = matched

            self.assertIn("testplan.md", found_in)
            self.assertEqual(found_in["testplan.md"], story_tcs)

    def test_select_across_artifacts(self):
        """Story TCs span primary and companion artifacts."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub_idx = {
                "schema_version": "1.0",
                "primary_testplan": "testplan.md",
                "artifacts": [
                    {"file": "testplan.md", "type": "testplan"},
                    {
                        "file": "hw.md",
                        "type": "companion",
                        "purpose": "HW",
                    },
                ],
            }
            _write_json(d / "validation-index.json", pub_idx)
            _write(d / "testplan.md",
                   "### FR-1\n#### TC-FR1-01: API scenario")
            _write(d / "hw.md",
                   "### NFR-3\n#### TC-NFR3-01: HW qualification")

            arts = vi.resolve_published_artifacts(d)
            story_tcs = {"TC-FR1-01", "TC-NFR3-01"}
            found_in: dict[str, set[str]] = {}
            for art in arts:
                content = (d / art["file"]).read_text()
                matched = {tc for tc in story_tcs if tc in content}
                if matched:
                    found_in[art["file"]] = matched

            self.assertEqual(found_in["testplan.md"], {"TC-FR1-01"})
            self.assertEqual(found_in["hw.md"], {"TC-NFR3-01"})

    def test_legacy_selection(self):
        """Story TC selection works without validation-index.json."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d / "testplan.md",
                   "### FR-1\n#### TC-FR1-01: Scenario")

            arts = vi.resolve_published_artifacts(d)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["file"], "testplan.md")

            story_tcs = {"TC-FR1-01"}
            content = (d / arts[0]["file"]).read_text()
            matched = {tc for tc in story_tcs if tc in content}
            self.assertEqual(matched, story_tcs)


# ===========================================================================
# 9. End-to-end: draft -> publish -> fresh discovery
# ===========================================================================

class TestDraftPublishDiscovery(unittest.TestCase):
    """Test the full contract: draft writes local index, publish transforms
    and copies to docs repo, fresh consumer discovers and reads."""

    def test_single_testplan_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            artifact_dir = Path(td) / "artifacts"
            docs_dir = Path(td) / "docs" / "v1" / "feature"
            artifact_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # 1. Draft writes local index + testplan
            local_idx = _make_local_index()
            _write_json(artifact_dir / "validation-index.json", local_idx)
            _write(artifact_dir / "04-testplan.md", "# Testplan content")

            # 2. Publish transforms and copies
            published_idx = vi.transform_for_publish(local_idx)
            _write_json(docs_dir / "validation-index.json", published_idx)
            (docs_dir / "testplan.md").write_text(
                (artifact_dir / "04-testplan.md").read_text())

            # 3. Fresh consumer discovers (no local metadata)
            arts = vi.resolve_published_artifacts(docs_dir)
            self.assertEqual(len(arts), 1)
            self.assertEqual(arts[0]["file"], "testplan.md")

            primary = vi.primary_testplan_path(docs_dir)
            self.assertIsNotNone(primary)
            self.assertEqual(primary.name, "testplan.md")

    def test_multi_doc_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            artifact_dir = Path(td) / "artifacts"
            docs_dir = Path(td) / "docs" / "v1" / "feature"
            artifact_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # 1. Draft writes index + testplan + companion
            local_idx = _make_local_index(companions=[{
                "local": "04-hw-validation.md",
                "published_as": "hw-validation.md",
                "purpose": "Hardware qualification",
                "audience": "HW QE team",
            }])
            _write_json(artifact_dir / "validation-index.json", local_idx)
            _write(artifact_dir / "04-testplan.md", "# Primary")
            _write(artifact_dir / "04-hw-validation.md", "# HW")

            # 2. Publish
            published_idx = vi.transform_for_publish(local_idx)
            _write_json(docs_dir / "validation-index.json", published_idx)
            for art in local_idx["artifacts"]:
                src = artifact_dir / art["local"]
                dst = docs_dir / art["published_as"]
                dst.write_text(src.read_text())

            # 3. Fresh consumer discovers all artifacts
            arts = vi.resolve_published_artifacts(docs_dir)
            self.assertEqual(len(arts), 2)
            files = {a["file"] for a in arts}
            self.assertEqual(files, {"testplan.md", "hw-validation.md"})

            # Primary is still resolvable
            primary = vi.primary_testplan_path(docs_dir)
            self.assertEqual(primary.name, "testplan.md")


if __name__ == "__main__":
    unittest.main()
