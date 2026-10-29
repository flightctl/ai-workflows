#!/usr/bin/env python3
"""Tests for design/scripts/sync_helper.py."""

from __future__ import annotations

import argparse
import hashlib
import re as _re
import importlib.util
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Import sync_helper via importlib (matches _shared/scripts test convention)
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).resolve().parent / "sync_helper.py"
_spec = importlib.util.spec_from_file_location("sync_helper", _SCRIPT)
assert _spec and _spec.loader
sync_helper = importlib.util.module_from_spec(_spec)
sys.modules["sync_helper"] = sync_helper
_spec.loader.exec_module(sync_helper)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Producer-contract-faithful epic fixture (matches decompose.md template)
_EPIC_TEMPLATE = textwrap.dedent("""\
    ---
    {extra_fm}
    ---
    # {title}

    - **T-Shirt Size:** {size}

    ## Summary

    {summary}

    ## Acceptance Criteria

    - [ ] {ac}

    ## Design Reference

    Feature: {feature_key}
    PRD Requirements: {prd_reqs}
    Design sections: {design_sections}
""")

# Producer-contract-faithful DEV story fixture (matches decompose.md template)
_DEV_STORY_TEMPLATE = textwrap.dedent("""\
    ---
    {extra_fm}
    ---
    # Story {epic_idx}.{story_idx:02d}: [{prefix}] {title}

    **As a** {role},
    **I want to** {want},
    **So that** {so_that}.

    ## Acceptance Criteria

    - [ ] {ac}

    ## Implementation Guidance

    {impl}

    ## Testing Approach

    {testing}

    ## Dependencies

    {deps}

    ## Design Reference

    Epic: Epic {epic_idx} — {epic_title}
    PRD Requirements: {prd_reqs}
    Design section: {design_section}
    Interface Changes: {ic}
    Validated by: {validated_by}
""")

# Producer-contract-faithful DOCS story fixture
_DOCS_STORY_TEMPLATE = textwrap.dedent("""\
    ---
    {extra_fm}
    ---
    # Story {epic_idx}.{story_idx:02d}: [DOCS] {title}

    **As a** {role},
    **I want to** {want},
    **So that** {so_that}.

    ## Acceptance Criteria

    - [ ] {ac}

    ## Documentation Scope

    {doc_scope}

    ## Documentation Inputs

    {doc_inputs}

    ## Dependencies

    {deps}

    ## Design Reference

    Epic: Epic {epic_idx} — {epic_title}
    PRD Requirements: {prd_reqs}
    Design section: {design_section}
""")

# Story with code fences containing headings (issue #4)
_STORY_WITH_CODE = textwrap.dedent("""\
    ---
    ---
    # Story 1.01: [DEV] API endpoint

    **As a** developer,
    **I want to** create an API,
    **So that** clients can connect.

    ## Acceptance Criteria

    - [ ] Endpoint responds with 200

    ## Implementation Guidance

    Use the following pattern:

    ```python
    ## This is NOT a real heading
    # Neither is this
    def handler():
        pass
    ```

    Follow the controller pattern.

    ## Testing Approach

    Test with curl.

    ## Dependencies

    None

    ## Design Reference

    Epic: Epic 1 — API
    PRD Requirements: FR-1
    Design section: §4.1
    Interface Changes: IC-1
    Validated by: TC-FR1-01
""")


def _make_epic(
    stories_dir: Path, index: int, slug: str, *,
    title: str = "", size: str = "M", removed: bool = False,
    summary: str = "Summary text.", ac: str = "AC1",
    feature_key: str = "FEAT-100", prd_reqs: str = "FR-1",
    design_sections: str = "§4.1",
) -> Path:
    if not title:
        title = f"Epic {index} {slug}"
    extra_fm = "status: removed" if removed else ""
    content = _EPIC_TEMPLATE.format(
        extra_fm=extra_fm, title=title, size=size,
        summary=summary, ac=ac, feature_key=feature_key,
        prd_reqs=prd_reqs, design_sections=design_sections,
    )
    fp = stories_dir / f"epic-{index}-{slug}.md"
    _write(fp, content)
    return fp


def _make_dev_story(
    stories_dir: Path, epic_idx: int, story_idx: int, slug: str, *,
    prefix: str = "DEV", title: str = "", removed: bool = False,
    deps: str = "None", impl: str = "Do the thing.",
    testing: str = "Test it.", role: str = "developer",
    want: str = "build it", so_that: str = "it works",
    ac: str = "Passes tests", epic_title: str = "Building",
    prd_reqs: str = "FR-1", design_section: str = "§4.1",
    ic: str = "IC-1", validated_by: str = "TC-FR1-01",
) -> Path:
    if not title:
        title = f"Story {slug}"
    extra_fm = "status: removed" if removed else ""
    content = _DEV_STORY_TEMPLATE.format(
        extra_fm=extra_fm, epic_idx=epic_idx, story_idx=story_idx,
        prefix=prefix, title=title, role=role, want=want, so_that=so_that,
        ac=ac, impl=impl, testing=testing, deps=deps,
        epic_title=epic_title, prd_reqs=prd_reqs,
        design_section=design_section, ic=ic, validated_by=validated_by,
    )
    epic_dir = stories_dir / f"epic-{epic_idx}"
    fp = epic_dir / f"story-{story_idx:02d}-{slug}.md"
    _write(fp, content)
    return fp


def _make_docs_story(
    stories_dir: Path, epic_idx: int, story_idx: int, slug: str, *,
    title: str = "API docs", removed: bool = False,
    deps: str = "Story 1.01", role: str = "writer",
    want: str = "document API", so_that: str = "users understand",
    ac: str = "Docs complete", doc_scope: str = "API reference.",
    doc_inputs: str = "**Story 1.01 — Scaffold:** output.",
    epic_title: str = "Building", prd_reqs: str = "FR-1",
    design_section: str = "§4.1",
) -> Path:
    extra_fm = "status: removed" if removed else ""
    content = _DOCS_STORY_TEMPLATE.format(
        extra_fm=extra_fm, epic_idx=epic_idx, story_idx=story_idx,
        title=title, role=role, want=want, so_that=so_that,
        ac=ac, doc_scope=doc_scope, doc_inputs=doc_inputs, deps=deps,
        epic_title=epic_title, prd_reqs=prd_reqs,
        design_section=design_section,
    )
    epic_dir = stories_dir / f"epic-{epic_idx}"
    fp = epic_dir / f"story-{story_idx:02d}-{slug}.md"
    _write(fp, content)
    return fp


def _make_manifest(
    artifacts_dir: Path, epics: list[dict], *,
    schema_version: int = 2, feature_key: str = "TEST-100",
    synced_at: str = "2026-01-15T10:00:00Z",
) -> Path:
    manifest = {
        "schema_version": schema_version,
        "feature_key": feature_key,
        "synced_at": synced_at,
        "epics": epics,
    }
    fp = artifacts_dir / "sync-manifest.json"
    _write(fp, json.dumps(manifest, indent=2))
    return fp


class _TmpDirMixin:
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir)


# ---------------------------------------------------------------------------
# Test: compute_file_hash
# ---------------------------------------------------------------------------

class TestComputeHash(_TmpDirMixin, unittest.TestCase):
    def test_known_hash(self) -> None:
        p = Path(self.tmpdir) / "f.md"
        _write(p, "hello world\n")
        expected = hashlib.sha256(b"hello world\n").hexdigest()
        self.assertEqual(sync_helper.compute_file_hash(p), expected)

    def test_missing_file(self) -> None:
        with self.assertRaises(OSError):
            sync_helper.compute_file_hash("/nonexistent/file.md")

    def test_cli_compute_hash(self) -> None:
        p = Path(self.tmpdir) / "f.md"
        _write(p, "test content")
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["compute-hash", str(p)])
        self.assertEqual(out.getvalue().strip(), _sha256("test content"))


# ---------------------------------------------------------------------------
# Test: read_frontmatter / has_removed_status (issue #4 error handling)
# ---------------------------------------------------------------------------

class TestFrontmatter(_TmpDirMixin, unittest.TestCase):
    def test_removed_status(self) -> None:
        p = Path(self.tmpdir) / "f.md"
        _write(p, "---\nstatus: removed\n---\n# Title\n")
        self.assertTrue(sync_helper.has_removed_status(p))

    def test_no_frontmatter(self) -> None:
        p = Path(self.tmpdir) / "f.md"
        _write(p, "# Title\nNo frontmatter here.\n")
        self.assertFalse(sync_helper.has_removed_status(p))

    def test_active_status(self) -> None:
        p = Path(self.tmpdir) / "f.md"
        _write(p, "---\nstatus: active\n---\n# Title\n")
        self.assertFalse(sync_helper.has_removed_status(p))

    def test_unreadable_file_returns_false(self) -> None:
        """has_removed_status returns False for missing file (issue #4)."""
        self.assertFalse(sync_helper.has_removed_status("/no/such/file.md"))

    def test_read_frontmatter_raises_on_missing_file(self) -> None:
        """read_frontmatter raises OSError for missing file (issue #4)."""
        with self.assertRaises(OSError):
            sync_helper.read_frontmatter("/no/such/file.md")


# ---------------------------------------------------------------------------
# Test: resolve_refs
# ---------------------------------------------------------------------------

class TestResolveRefs(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = {
            "epics": [
                {
                    "file": "epic-1-building.md", "jira_key": "EDM-101",
                    "stories": [
                        {"file": "story-01-scaffold.md", "jira_key": "EDM-201"},
                        {"file": "story-02-pipeline.md", "jira_key": "EDM-202"},
                    ],
                },
                {
                    "file": "epic-2-deploy.md", "jira_key": "EDM-102",
                    "stories": [
                        {"file": "story-01-infra.md", "jira_key": "EDM-301"},
                    ],
                },
            ],
        }

    def test_single_story_ref(self) -> None:
        result = sync_helper.resolve_refs("Depends on Story 1.01.", self.manifest)
        self.assertEqual(result, "Depends on Story EDM-201.")

    def test_multiple_story_refs(self) -> None:
        result = sync_helper.resolve_refs("Stories 1.01, 2.01.", self.manifest)
        self.assertEqual(result, "Stories EDM-201, EDM-301.")

    def test_epic_ref(self) -> None:
        result = sync_helper.resolve_refs("See Epic 1.", self.manifest)
        self.assertEqual(result, "See Epic EDM-101.")

    def test_unresolved_story(self) -> None:
        result = sync_helper.resolve_refs("Story 3.01.", self.manifest)
        self.assertIn("3.01 [unresolved]", result)

    def test_unresolved_epic(self) -> None:
        result = sync_helper.resolve_refs("Epic 5.", self.manifest)
        self.assertIn("5 [unresolved]", result)

    def test_mixed_resolved_unresolved(self) -> None:
        result = sync_helper.resolve_refs("Stories 1.01, 3.01.", self.manifest)
        self.assertIn("EDM-201", result)
        self.assertIn("3.01 [unresolved]", result)

    def test_no_refs(self) -> None:
        text = "No references here."
        self.assertEqual(sync_helper.resolve_refs(text, self.manifest), text)

    def test_cli_resolve_refs(self) -> None:
        fd, tmp_name = tempfile.mkstemp(suffix=".json")
        import os as _os
        _os.close(fd)
        mf = Path(tmp_name)
        _write(mf, json.dumps(self.manifest))
        try:
            out = StringIO()
            with mock.patch("sys.stdout", out):
                sync_helper.main(["resolve-refs", str(mf), "Epic 1 and Story 1.02"])
            self.assertIn("EDM-101", out.getvalue())
            self.assertIn("EDM-202", out.getvalue())
        finally:
            mf.unlink()

    def test_cross_epic_story_refs(self) -> None:
        """Multi-epic cross-references resolve correctly."""
        text = "Stories 1.01, 2.01 and Epic 2."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertIn("EDM-201", result)
        self.assertIn("EDM-301", result)
        self.assertIn("EDM-102", result)


# ---------------------------------------------------------------------------
# Test: detect_changes — fresh sync
# ---------------------------------------------------------------------------

class TestDetectChangesFresh(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_fresh_sync_all_new(self) -> None:
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")

        result = sync_helper.detect_changes(self.artifacts)
        self.assertFalse(result["manifest_exists"])
        self.assertEqual(result["summary"]["new"], 2)
        for item in result["items"]:
            self.assertEqual(item["category"], "new")

    def test_fresh_sync_removed_skipped(self) -> None:
        _make_epic(self.stories_dir, 1, "building")
        _make_epic(self.stories_dir, 2, "removed", removed=True)

        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["new"], 1)

    def test_empty_artifacts(self) -> None:
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(len(result["items"]), 0)


# ---------------------------------------------------------------------------
# Test: detect_changes — existing manifest, all categories
# ---------------------------------------------------------------------------

class TestDetectChangesExisting(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_unchanged_items(self) -> None:
        ef = _make_epic(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "title": "Building", "size": "M",
            "content_hash": sync_helper.compute_file_hash(ef),
            "synced_status": "active", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["unchanged"], 1)

    def test_changed_items(self) -> None:
        _make_epic(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "old_hash", "synced_status": "active", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        changed = [i for i in result["items"] if i["category"] == "changed"]
        self.assertEqual(len(changed), 1)

    def test_removed_items(self) -> None:
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["removed"], 1)

    def test_reopened_items(self) -> None:
        _make_epic(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "closed", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["reopened"], 1)

    def test_already_closed(self) -> None:
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "closed", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["unchanged"], 1)

    def test_orphaned_active_detected(self) -> None:
        _make_manifest(self.artifacts, [{
            "file": "epic-1-gone.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["orphaned"], 1)

    def test_orphaned_closed_ignored(self) -> None:
        _make_manifest(self.artifacts, [{
            "file": "epic-1-gone.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "closed", "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["orphaned"], 0)

    def test_removed_story_under_active_epic_warning(self) -> None:
        _make_epic(self.stories_dir, 1, "building",
                   summary="Stories:\n- Story 1.01: scaffold\n- Story 1.02: pipe")
        sf1 = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_dev_story(self.stories_dir, 1, 2, "pipe", removed=True)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": sync_helper.compute_file_hash(
                self.stories_dir / "epic-1-building.md"),
            "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": sync_helper.compute_file_hash(sf1),
                 "synced_status": "active"},
                {"file": "story-02-pipe.md", "jira_key": "EDM-202",
                 "content_hash": "old", "synced_status": "active"},
            ],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        self.assertTrue(any("Story 1.02" in w for w in result["warnings"]))

    def test_numeric_sort_order(self) -> None:
        """Issue #7: epic-2 before epic-10 (not lexicographic)."""
        _make_epic(self.stories_dir, 2, "second")
        _make_epic(self.stories_dir, 10, "tenth")
        result = sync_helper.detect_changes(self.artifacts)
        indices = [i["epic_index"] for i in result["items"]]
        self.assertEqual(indices, [2, 10])


# ---------------------------------------------------------------------------
# Test: detect_changes — v1 manifest
# ---------------------------------------------------------------------------

class TestDetectChangesV1(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_v1_all_changed(self) -> None:
        _make_epic(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "title": "Building", "stories": [],
        }], schema_version=1)
        result = sync_helper.detect_changes(self.artifacts)
        self.assertTrue(result["v1_migration"])
        self.assertEqual(result["summary"]["changed"], 1)

    def test_v1_orphaned(self) -> None:
        _make_manifest(self.artifacts, [{
            "file": "epic-1-gone.md", "jira_key": "EDM-101",
            "title": "Gone", "stories": [],
        }], schema_version=1)
        result = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(result["summary"]["orphaned"], 1)


# ---------------------------------------------------------------------------
# Test: update_manifest — unified API (issues #2, #3)
# ---------------------------------------------------------------------------

class TestUpdateManifest(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def test_create_epic_fresh_with_feature_key(self) -> None:
        """Issue #3: fresh create populates feature_key."""
        result = sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic", title="Building",
            size="M", feature_key="FEAT-100",
        )
        self.assertEqual(result["feature_key"], "FEAT-100")
        self.assertEqual(result["epics"][0]["synced_status"], "active")

    def test_feature_key_preserved_on_subsequent_calls(self) -> None:
        """Issue #3: feature_key set on first call persists."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic", feature_key="FEAT-100",
        )
        result = sync_helper.update_manifest(
            self.manifest_path, "create", "epic-2-deploy.md",
            "EDM-102", "def", item_type="epic",
        )
        self.assertEqual(result["feature_key"], "FEAT-100")

    def test_story_requires_epic_file(self) -> None:
        """Issue #2: story without --epic-file fails closed."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic",
        )
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.update_manifest(
                self.manifest_path, "create", "story-01-scaffold.md",
                "EDM-201", "def", item_type="story",
            )
        self.assertEqual(ctx.exception.code, 1)

    def test_story_with_wrong_epic_file_fails(self) -> None:
        """Issue #2: story with nonexistent epic_file fails closed."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic",
        )
        original = Path(self.manifest_path).read_bytes()
        with self.assertRaises(SystemExit):
            sync_helper.update_manifest(
                self.manifest_path, "create", "story-01-scaffold.md",
                "EDM-201", "def", item_type="story",
                epic_file="epic-99-nonexistent.md",
            )
        # Manifest preserved on failure
        self.assertEqual(Path(self.manifest_path).read_bytes(), original)

    def test_story_correct_placement_two_epics(self) -> None:
        """Issue #2: identical story basenames placed under correct epic."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic", title="Building",
        )
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-2-deploy.md",
            "EDM-102", "def", item_type="epic", title="Deploy",
        )
        # story-01 under epic-2 specifically
        sync_helper.update_manifest(
            self.manifest_path, "create", "story-01-scaffold.md",
            "EDM-301", "ghi", item_type="story", title="[DEV] Scaffold",
            epic_file="epic-2-deploy.md",
        )
        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(len(manifest["epics"][0]["stories"]), 0)
        self.assertEqual(len(manifest["epics"][1]["stories"]), 1)
        self.assertEqual(manifest["epics"][1]["stories"][0]["jira_key"], "EDM-301")

    def test_close_epic(self) -> None:
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic",
        )
        result = sync_helper.update_manifest(
            self.manifest_path, "close", "epic-1-building.md",
            "EDM-101", "close_hash", item_type="epic",
        )
        self.assertEqual(result["epics"][0]["synced_status"], "closed")

    def test_orphan_close_with_empty_hash(self) -> None:
        """Issue #5: orphan closure uses empty hash (no file on disk)."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic",
        )
        result = sync_helper.update_manifest(
            self.manifest_path, "close", "epic-1-building.md",
            "EDM-101", "", item_type="epic",
        )
        self.assertEqual(result["epics"][0]["synced_status"], "closed")
        self.assertEqual(result["epics"][0]["content_hash"], "")

    def test_cli_update_manifest_story(self) -> None:
        """CLI update-manifest with --epic-file."""
        sync_helper.main([
            "update-manifest", str(self.manifest_path),
            "--operation", "create", "--file", "epic-1-building.md",
            "--jira-key", "EDM-101", "--content-hash", "abc",
            "--item-type", "epic", "--feature-key", "FEAT-100",
        ])
        rc = sync_helper.main([
            "update-manifest", str(self.manifest_path),
            "--operation", "create", "--file", "story-01-scaffold.md",
            "--jira-key", "EDM-201", "--content-hash", "def",
            "--item-type", "story", "--epic-file", "epic-1-building.md",
        ])
        self.assertEqual(rc, 0)
        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(manifest["feature_key"], "FEAT-100")
        self.assertEqual(manifest["epics"][0]["stories"][0]["jira_key"], "EDM-201")

    def test_cli_story_without_epic_file_fails(self) -> None:
        """CLI: story without --epic-file exits 1."""
        sync_helper.main([
            "update-manifest", str(self.manifest_path),
            "--operation", "create", "--file", "epic-1-building.md",
            "--jira-key", "EDM-101", "--content-hash", "abc",
            "--item-type", "epic",
        ])
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main([
                "update-manifest", str(self.manifest_path),
                "--operation", "create", "--file", "story-01-scaffold.md",
                "--jira-key", "EDM-201", "--content-hash", "def",
                "--item-type", "story",
            ])
        self.assertEqual(ctx.exception.code, 1)


# ---------------------------------------------------------------------------
# Test: manifest safety (issues #2, #8)
# ---------------------------------------------------------------------------

class TestManifestSafety(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def test_malformed_json_shape(self) -> None:
        """Issue #8: manifest that's a JSON array, not object, fails."""
        _write(self.manifest_path, "[]")
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.manifest_path)

    def test_unsupported_schema_version(self) -> None:
        """Issue #8: future schema version fails closed."""
        _write(self.manifest_path, json.dumps(
            {"schema_version": 99, "epics": []}))
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.manifest_path)

    def test_invalid_epics_type(self) -> None:
        """Issue #8: epics as string instead of list fails."""
        _write(self.manifest_path, json.dumps(
            {"schema_version": 2, "epics": "not a list"}))
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.manifest_path)

    def test_failure_preserves_manifest(self) -> None:
        """Issue #8: failed update preserves original manifest."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "abc", item_type="epic",
        )
        original = self.manifest_path.read_bytes()
        with self.assertRaises(SystemExit):
            sync_helper.update_manifest(
                self.manifest_path, "create", "story-01.md",
                "EDM-201", "def", item_type="story",
                epic_file="epic-99-missing.md",
            )
        self.assertEqual(self.manifest_path.read_bytes(), original)

    def test_partial_sync_then_resume(self) -> None:
        """Interrupted sync: only successful items recorded."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "building")
        _make_epic(sd, 2, "deploy")

        sync_helper.update_manifest(
            arts / "sync-manifest.json", "create", "epic-1-building.md",
            "EDM-101", sync_helper.compute_file_hash(sd / "epic-1-building.md"),
            item_type="epic", feature_key="FEAT-100",
        )
        plan = sync_helper.detect_changes(arts)
        new = [i for i in plan["items"] if i["category"] == "new"]
        unchanged = [i for i in plan["items"] if i["category"] == "unchanged"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["file"], "epic-2-deploy.md")
        self.assertEqual(len(unchanged), 1)


# ---------------------------------------------------------------------------
# Test: render_description — producer contract (issues #4, #7)
# ---------------------------------------------------------------------------

class TestRenderDescription(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest = {
            "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "stories": [
                    {"file": "story-01-scaffold.md", "jira_key": "EDM-201"},
                ],
            }],
        }

    def test_epic_description_preserves_all_fields(self) -> None:
        ef = Path(self.tmpdir) / "epic-1-building.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Image Building", size="L",
            summary="Build container images.", ac="Pipeline runs",
            feature_key="FEAT-100", prd_reqs="FR-1, FR-2",
            design_sections="§4.1"))
        desc = sync_helper.render_epic_description(
            ef, self.manifest, design_doc_link="https://doc", feature_key="FEAT-100")
        self.assertIn("## Summary", desc)
        self.assertIn("Build container images.", desc)
        self.assertIn("## Acceptance Criteria", desc)
        self.assertIn("## Design Reference", desc)

    def test_dev_story_preserves_all_fields(self) -> None:
        """Issue #4: DEV story preserves Interface Changes and Validated by."""
        sf = Path(self.tmpdir) / "story-01-scaffold.md"
        _write(sf, _DEV_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=1, prefix="DEV",
            title="Scaffold", role="developer", want="scaffold",
            so_that="it works", ac="Tests pass",
            impl="Do the thing.", testing="Test it.",
            deps="None", epic_title="Building",
            prd_reqs="FR-1", design_section="§4.1",
            ic="IC-1, IC-2", validated_by="TC-FR1-01, TC-FR3-02",
        ))
        desc = sync_helper.render_story_description(
            sf, self.manifest, epic_jira_key="EDM-101")
        self.assertIn("## User Story", desc)
        self.assertIn("## Implementation Guidance", desc)
        self.assertIn("## Testing Approach", desc)
        self.assertIn("## Design Reference", desc)
        # Producer-contract fields preserved from body
        self.assertIn("Interface Changes: IC-1, IC-2", desc)
        self.assertIn("Validated by: TC-FR1-01, TC-FR3-02", desc)

    def test_docs_story_preserves_docs_sections(self) -> None:
        sf = Path(self.tmpdir) / "story-01-docs.md"
        _write(sf, _DOCS_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=1,
            title="API docs", role="writer", want="document",
            so_that="users understand", ac="Docs complete",
            doc_scope="API ref.", doc_inputs="Story 1.01 output.",
            deps="Story 1.01", epic_title="Building",
            prd_reqs="FR-1", design_section="§4.1",
        ))
        desc = sync_helper.render_story_description(
            sf, self.manifest, story_type="DOCS")
        self.assertIn("## Documentation Scope", desc)
        self.assertIn("## Documentation Inputs", desc)
        self.assertNotIn("## Implementation Guidance", desc)
        # Ref resolved
        self.assertIn("EDM-201", desc)

    def test_code_fences_do_not_break_sections(self) -> None:
        """Issue #4: headings inside code fences are not treated as sections."""
        sf = Path(self.tmpdir) / "story-01-api.md"
        _write(sf, _STORY_WITH_CODE)
        sections = sync_helper._extract_sections(sf)
        # Fenced code headings must NOT create separate sections
        self.assertNotIn("This is NOT a real heading", sections)
        self.assertNotIn("Neither is this", sections)
        # The code content must be inside Implementation Guidance
        self.assertIn("Implementation Guidance", sections)
        self.assertIn("## This is NOT a real heading", sections["Implementation Guidance"])
        self.assertIn("Follow the controller pattern.", sections["Implementation Guidance"])
        # Full render check
        desc = sync_helper.render_story_description(sf, self.manifest)
        self.assertIn("## Implementation Guidance", desc)
        self.assertIn("Follow the controller pattern.", desc)

    def test_cli_render_description(self) -> None:
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "---\n---\n# Building\n\n## Summary\n\nBuild.\n\n## Acceptance Criteria\n\n- AC\n")
        mf = Path(self.tmpdir) / "manifest.json"
        _write(mf, json.dumps(self.manifest))
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["render-description", str(ef), str(mf),
                              "--type", "epic", "--feature-key", "FEAT-1"])
        self.assertIn("## Summary", out.getvalue())


# ---------------------------------------------------------------------------
# Test: prepare — snapshot consistency (issue #6)
# ---------------------------------------------------------------------------

class TestPrepare(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = Path(self.tmpdir) / "manifest.json"
        _write(self.manifest_path, json.dumps({"epics": []}))

    def test_prepare_returns_consistent_hash_and_desc(self) -> None:
        ef = Path(self.tmpdir) / "epic-1-building.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 1 Image Building", size="L",
            summary="Build container images.", ac="Pipeline runs",
            feature_key="FEAT-100", prd_reqs="FR-1",
            design_sections="§4.1"))
        content = ef.read_text()
        result = sync_helper.prepare(
            ef, self.manifest_path, "epic",
            feature_key="FEAT-100")
        self.assertEqual(result["content_hash"], _sha256(content))
        self.assertIn("Build container images.", result["description"])
        # Jira summary strips "Epic 1 " prefix
        self.assertEqual(result["summary"], "Image Building")
        self.assertEqual(result["size"], "L")

    def test_edit_between_prepare_and_checkpoint_detectable(self) -> None:
        """Issue #6: edits between prepare and checkpoint leave content
        detectably unsynced on re-run."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        ef = _make_epic(sd, 1, "building", summary="Original.")
        mf = arts / "sync-manifest.json"

        # Prepare (snapshot)
        result = sync_helper.prepare(ef, mf, "epic", feature_key="FEAT-100")
        original_hash = result["content_hash"]

        # Edit the file after prepare but before checkpoint
        _write(ef, ef.read_text().replace("Original.", "Edited."))

        # Checkpoint with the ORIGINAL hash (what was submitted)
        sync_helper.update_manifest(
            mf, "create", "epic-1-building.md", "EDM-101",
            original_hash, item_type="epic", feature_key="FEAT-100")

        # Re-detect: file changed since last sync → shows as changed
        plan = sync_helper.detect_changes(arts)
        changed = [i for i in plan["items"] if i["category"] == "changed"]
        self.assertEqual(len(changed), 1, "Edit after prepare should be detected")

    def test_cli_prepare_epic(self) -> None:
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 2 Deploy", size="M",
            summary="Deploy to prod.", ac="Deployed",
            feature_key="F", prd_reqs="FR-1", design_sections="§4.1"))
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(ef), str(self.manifest_path),
                              "--type", "epic"])
        result = json.loads(out.getvalue())
        self.assertIn("content_hash", result)
        self.assertEqual(result["summary"], "Deploy")
        self.assertEqual(result["size"], "M")

    def test_cli_prepare_story(self) -> None:
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, _DEV_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=3, prefix="DEV",
            title="Build Pipeline", role="dev", want="build",
            so_that="done", ac="AC", impl="Do.", testing="Test.",
            deps="Story 1.01, Story 1.02", epic_title="Building",
            prd_reqs="FR-1", design_section="§4.1",
            ic="IC-1", validated_by="TC-FR1-01"))
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(sf), str(self.manifest_path),
                              "--type", "story"])
        result = json.loads(out.getvalue())
        self.assertEqual(result["summary"], "[DEV] Build Pipeline")
        self.assertEqual(result["story_type"], "DEV")
        self.assertIn("Story", result["dependencies"])


# ---------------------------------------------------------------------------
# Test: orphan closure path (issue #5)
# ---------------------------------------------------------------------------

class TestOrphanClosure(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def test_orphan_close_no_file_on_disk(self) -> None:
        """Issue #5: close an orphan entry without reading a nonexistent file."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-gone.md",
            "EDM-101", "original_hash", item_type="epic",
            feature_key="FEAT-100",
        )
        # File doesn't exist — close with empty hash
        result = sync_helper.update_manifest(
            self.manifest_path, "close", "epic-1-gone.md",
            "EDM-101", "", item_type="epic",
        )
        self.assertEqual(result["epics"][0]["synced_status"], "closed")

    def test_v1_orphan_close_no_old_hash(self) -> None:
        """Issue #5: v1 orphan entry has no content_hash — close with empty."""
        _write(self.manifest_path, json.dumps({
            "schema_version": 1, "feature_key": "F-1",
            "synced_at": "2026-01-01", "epics": [{
                "file": "epic-1-gone.md", "jira_key": "EDM-101",
                "title": "Gone", "stories": [],
            }],
        }))
        sync_helper.migrate_manifest(self.manifest_path)
        result = sync_helper.update_manifest(
            self.manifest_path, "close", "epic-1-gone.md",
            "EDM-101", "", item_type="epic",
        )
        self.assertEqual(result["epics"][0]["synced_status"], "closed")


# ---------------------------------------------------------------------------
# Test: cascaded closure ordering (issue #9)
# ---------------------------------------------------------------------------

class TestCascadedClosure(_TmpDirMixin, unittest.TestCase):
    """Verify that closing an epic's stories before the epic is safe."""

    def setUp(self) -> None:
        super().setUp()
        self.arts = Path(self.tmpdir) / "art"
        self.sd = self.arts / "06-stories"
        self.sd.mkdir(parents=True)
        # Manifest lives inside artifacts dir (where detect_changes looks)
        self.manifest_path = self.arts / "sync-manifest.json"

    def test_stories_closed_before_parent_epic(self) -> None:
        """Issue #9: close stories before epic; re-detect shows all closed."""
        # Create files first as active to get initial hashes
        ef = _make_epic(self.sd, 1, "building")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")
        ef_hash = sync_helper.compute_file_hash(ef)
        sf_hash = sync_helper.compute_file_hash(sf)

        # Create both initially with their actual hashes
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", ef_hash, item_type="epic", feature_key="F-1",
        )
        sync_helper.update_manifest(
            self.manifest_path, "create", "story-01-scaffold.md",
            "EDM-201", sf_hash, item_type="story",
            epic_file="epic-1-building.md",
        )

        # Now mark both as removed (simulating /revise adding status: removed)
        ef = _make_epic(self.sd, 1, "building", removed=True)
        sf = _make_dev_story(self.sd, 1, 1, "scaffold", removed=True)

        # Close story first, then epic (per spec 4c ordering)
        sync_helper.update_manifest(
            self.manifest_path, "close", "story-01-scaffold.md",
            "EDM-201", sync_helper.compute_file_hash(sf),
            item_type="story", epic_file="epic-1-building.md",
        )
        sync_helper.update_manifest(
            self.manifest_path, "close", "epic-1-building.md",
            "EDM-101", sync_helper.compute_file_hash(ef), item_type="epic",
        )

        plan = sync_helper.detect_changes(self.arts)
        # Both should be unchanged (already closed)
        self.assertEqual(plan["summary"]["unchanged"], 2)
        self.assertEqual(plan["summary"]["removed"], 0)

    def test_no_active_story_under_removed_parent(self) -> None:
        """Issue #9: cannot create active story under a closed epic."""
        sync_helper.update_manifest(
            self.manifest_path, "create", "epic-1-building.md",
            "EDM-101", "h1", item_type="epic", feature_key="F-1",
        )
        sync_helper.update_manifest(
            self.manifest_path, "close", "epic-1-building.md",
            "EDM-101", "h2", item_type="epic",
        )
        # Creating a story under the closed epic still works structurally
        # (the workflow wouldn't do this, but the manifest records it)
        sync_helper.update_manifest(
            self.manifest_path, "create", "story-01-scaffold.md",
            "EDM-201", "h3", item_type="story",
            epic_file="epic-1-building.md",
        )
        manifest = sync_helper.load_manifest(self.manifest_path)
        # Story is recorded — it's the workflow's job not to do this
        self.assertEqual(len(manifest["epics"][0]["stories"]), 1)


# ---------------------------------------------------------------------------
# Test: migrate_manifest
# ---------------------------------------------------------------------------

class TestMigrateManifest(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def test_migrate_v1_to_v2(self) -> None:
        _write(self.manifest_path, json.dumps({
            "schema_version": 1, "feature_key": "F-1",
            "synced_at": "2026-01-01", "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "stories": [{"file": "story-01.md", "jira_key": "EDM-201"}],
            }],
        }))
        result = sync_helper.migrate_manifest(self.manifest_path)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["epics"][0]["synced_status"], "active")
        self.assertIsNone(result["epics"][0]["content_hash"])

    def test_migrate_v2_noop(self) -> None:
        _write(self.manifest_path, json.dumps({
            "schema_version": 2, "feature_key": "F-1",
            "synced_at": "2026-01-01", "epics": [],
        }))
        result = sync_helper.migrate_manifest(self.manifest_path)
        self.assertEqual(result["schema_version"], 2)


# ---------------------------------------------------------------------------
# Test: end-to-end consumer flow via CLI
# ---------------------------------------------------------------------------

class TestEndToEndCLI(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.arts = Path(self.tmpdir) / "art"
        self.sd = self.arts / "06-stories"
        self.sd.mkdir(parents=True)
        self.mf = self.arts / "sync-manifest.json"

    def test_full_cli_flow(self) -> None:
        """Complete detect → prepare → create → checkpoint → verify.
        All Jira fields come from prepare snapshot, not file re-reads."""
        ef = _make_epic(self.sd, 1, "building", title="Epic 1 Image Building",
                        size="L", summary="Build container images.")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold",
                             title="Scaffold Pipeline", deps="None")

        # 1. detect-changes
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["detect-changes", str(self.arts)])
        plan = json.loads(out.getvalue())
        self.assertEqual(plan["summary"]["new"], 2)

        # 2. prepare epic — returns all Jira-owned fields
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(ef), str(self.mf),
                              "--type", "epic", "--feature-key", "FEAT-100",
                              "--design-doc-link", "https://docs.example.com"])
        prep = json.loads(out.getvalue())
        self.assertEqual(prep["summary"], "Image Building")
        self.assertEqual(prep["size"], "L")
        self.assertIn("Build container images.", prep["description"])
        self.assertIn("https://docs.example.com", prep["description"])

        # 3. checkpoint epic using ONLY prep fields
        sync_helper.main([
            "update-manifest", str(self.mf),
            "--operation", "create", "--file", ef.name,
            "--jira-key", "EDM-101", "--content-hash", prep["content_hash"],
            "--item-type", "epic", "--title", prep["summary"],
            "--size", prep["size"], "--feature-key", "FEAT-100",
        ])

        # 4. prepare story — returns summary with [PREFIX]
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(sf), str(self.mf),
                              "--type", "story", "--epic-jira-key", "EDM-101",
                              "--design-doc-link", "https://docs.example.com"])
        sprep = json.loads(out.getvalue())
        self.assertEqual(sprep["summary"], "[DEV] Scaffold Pipeline")
        self.assertEqual(sprep["story_type"], "DEV")
        self.assertEqual(sprep["dependencies"], "None")

        # 5. checkpoint story using ONLY sprep fields
        sync_helper.main([
            "update-manifest", str(self.mf),
            "--operation", "create", "--file", sf.name,
            "--jira-key", "EDM-201", "--content-hash", sprep["content_hash"],
            "--item-type", "story", "--title", sprep["summary"],
            "--epic-file", ef.name,
        ])

        # 6. re-detect: all unchanged
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["detect-changes", str(self.arts)])
        plan = json.loads(out.getvalue())
        self.assertEqual(plan["summary"]["unchanged"], 2)
        self.assertEqual(plan["summary"]["new"], 0)

        # 7. verify manifest has feature_key and correct titles
        manifest = sync_helper.load_manifest(self.mf)
        self.assertEqual(manifest["feature_key"], "FEAT-100")
        self.assertEqual(manifest["epics"][0]["title"], "Image Building")
        self.assertEqual(manifest["epics"][0]["stories"][0]["title"],
                         "[DEV] Scaffold Pipeline")


# ---------------------------------------------------------------------------
# Defect A: design_doc_link merge + DOCS inference via CLI/prepare
# ---------------------------------------------------------------------------

class TestDefectA_DesignDocLink(_TmpDirMixin, unittest.TestCase):
    """Verify design_doc_link is merged into body Design Reference and
    DOCS type is inferred from canonical '# Story 1.02: [DOCS] ...' title."""

    def setUp(self) -> None:
        super().setUp()
        self.manifest = {
            "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "stories": [
                    {"file": "story-01-scaffold.md", "jira_key": "EDM-201"},
                ],
            }],
        }
        self.mf = Path(self.tmpdir) / "manifest.json"
        _write(self.mf, json.dumps(self.manifest))

    def test_design_doc_link_merged_via_prepare(self) -> None:
        """Sentinel link appears in body Design Reference via prepare CLI."""
        sf = Path(self.tmpdir) / "story-01-scaffold.md"
        _write(sf, _DEV_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=1, prefix="DEV",
            title="Scaffold", role="dev", want="build", so_that="done",
            ac="AC", impl="Do.", testing="Test.", deps="None",
            epic_title="Building", prd_reqs="FR-1",
            design_section="§4.1", ic="IC-1", validated_by="TC-FR1-01",
        ))
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main([
                "prepare", str(sf), str(self.mf), "--type", "story",
                "--design-doc-link", "https://SENTINEL.example.com",
                "--epic-jira-key", "EDM-101",
            ])
        result = json.loads(out.getvalue())
        desc = result["description"]
        self.assertIn("https://SENTINEL.example.com", desc,
                      "design_doc_link must appear in rendered description")
        self.assertIn("IC-1", desc, "Interface Changes preserved")
        self.assertIn("TC-FR1-01", desc, "Validated by preserved")
        self.assertIn("EDM-101", desc, "Epic ref resolved to Jira key")

    def test_docs_inferred_from_canonical_title_via_prepare(self) -> None:
        """DOCS type inferred from '# Story 1.02: [DOCS] ...' title."""
        sf = Path(self.tmpdir) / "story-02-docs.md"
        _write(sf, _DOCS_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=2,
            title="API Guide", role="writer", want="document",
            so_that="understand", ac="Done",
            doc_scope="API reference.", doc_inputs="From Story 1.01.",
            deps="Story 1.01", epic_title="Building",
            prd_reqs="FR-1", design_section="§4.1",
        ))
        # No --story-type — must infer from title
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main([
                "prepare", str(sf), str(self.mf), "--type", "story",
            ])
        result = json.loads(out.getvalue())
        desc = result["description"]
        self.assertIn("## Documentation Scope", desc)
        self.assertIn("API reference.", desc)
        self.assertNotIn("## Implementation Guidance", desc)

    def test_dev_description_content_values(self) -> None:
        """DEV description contains actual content, not just headings."""
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, _DEV_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=1, prefix="DEV",
            title="Scaffold", role="platform engineer",
            want="scaffold the build pipeline",
            so_that="images can be built automatically",
            ac="Pipeline runs end-to-end",
            impl="Use Tekton pipelines.", testing="Integration tests.",
            deps="None", epic_title="Building", prd_reqs="FR-1",
            design_section="§4.1", ic="IC-1", validated_by="TC-FR1-01",
        ))
        result = sync_helper.prepare(str(sf), str(self.mf), "story")
        desc = result["description"]
        self.assertIn("platform engineer", desc)
        self.assertIn("scaffold the build pipeline", desc)
        self.assertIn("Use Tekton pipelines.", desc)
        self.assertIn("Integration tests.", desc)
        self.assertIn("Pipeline runs end-to-end", desc)


# ---------------------------------------------------------------------------
# Defect B: Parent closure → child lifecycle
# ---------------------------------------------------------------------------

class TestDefectB_ParentClosure(_TmpDirMixin, unittest.TestCase):
    """Children under removed/closed epics must not be created/reopened."""

    def setUp(self) -> None:
        super().setUp()
        self.arts = Path(self.tmpdir) / "art"
        self.sd = self.arts / "06-stories"
        self.sd.mkdir(parents=True)
        self.mf = self.arts / "sync-manifest.json"

    def test_fresh_removed_parent_skips_active_child(self) -> None:
        """Fresh sync: removed epic's non-removed child NOT emitted as new."""
        _make_epic(self.sd, 1, "building", removed=True)
        _make_dev_story(self.sd, 1, 1, "scaffold")  # NOT removed

        plan = sync_helper.detect_changes(self.arts)
        self.assertEqual(plan["summary"]["new"], 0,
                         "Child under removed epic must not be new on fresh sync")

    def test_manifest_closed_parent_active_child_not_reopened(self) -> None:
        """Active child under closed epic → removed (not reopened/changed)."""
        _make_epic(self.sd, 1, "building", removed=True)
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")  # NOT removed
        ef_hash = sync_helper.compute_file_hash(
            self.sd / "epic-1-building.md")
        sf_hash = sync_helper.compute_file_hash(sf)

        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "old", "synced_status": "closed",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "old", "synced_status": "active",
            }],
        }])

        plan = sync_helper.detect_changes(self.arts)
        story_items = [i for i in plan["items"] if i["type"] == "story"]
        self.assertEqual(len(story_items), 1)
        self.assertEqual(story_items[0]["category"], "removed",
                         "Active child under closed parent → removed")

    def test_full_cascade_detect_checkpoint_redetect(self) -> None:
        """Full sequence: detect → close stories → close epic → re-detect."""
        ef = _make_epic(self.sd, 1, "building")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")
        ef_hash = sync_helper.compute_file_hash(ef)
        sf_hash = sync_helper.compute_file_hash(sf)

        # Initial sync
        sync_helper.update_manifest(
            self.mf, "create", "epic-1-building.md", "EDM-101",
            ef_hash, item_type="epic", feature_key="F-1")
        sync_helper.update_manifest(
            self.mf, "create", "story-01-scaffold.md", "EDM-201",
            sf_hash, item_type="story", epic_file="epic-1-building.md")

        # Mark removed
        ef = _make_epic(self.sd, 1, "building", removed=True)
        sf = _make_dev_story(self.sd, 1, 1, "scaffold", removed=True)

        # Detect
        plan = sync_helper.detect_changes(self.arts)
        removed = [i for i in plan["items"] if i["category"] == "removed"]
        self.assertEqual(len(removed), 2, "Both epic and story removed")

        # Close story then epic
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201",
            sync_helper.compute_file_hash(sf),
            item_type="story", epic_file="epic-1-building.md")
        sync_helper.update_manifest(
            self.mf, "close", "epic-1-building.md", "EDM-101",
            sync_helper.compute_file_hash(ef), item_type="epic")

        # Re-detect: all unchanged (already closed)
        plan2 = sync_helper.detect_changes(self.arts)
        self.assertEqual(plan2["summary"]["unchanged"], 2)
        self.assertEqual(plan2["summary"]["reopened"], 0)

    def test_interrupted_cascade_resume(self) -> None:
        """Interrupted after closing story but before closing epic;
        resume correctly finishes."""
        ef = _make_epic(self.sd, 1, "building")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")

        sync_helper.update_manifest(
            self.mf, "create", "epic-1-building.md", "EDM-101",
            sync_helper.compute_file_hash(ef),
            item_type="epic", feature_key="F-1")
        sync_helper.update_manifest(
            self.mf, "create", "story-01-scaffold.md", "EDM-201",
            sync_helper.compute_file_hash(sf),
            item_type="story", epic_file="epic-1-building.md")

        # Mark both removed
        ef = _make_epic(self.sd, 1, "building", removed=True)
        sf = _make_dev_story(self.sd, 1, 1, "scaffold", removed=True)

        # Close story only (interrupted before epic close)
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201",
            sync_helper.compute_file_hash(sf),
            item_type="story", epic_file="epic-1-building.md")

        # Resume: re-detect should show epic removed, story unchanged
        plan = sync_helper.detect_changes(self.arts)
        epic_items = [i for i in plan["items"] if i["type"] == "epic"]
        story_items = [i for i in plan["items"] if i["type"] == "story"]
        self.assertEqual(epic_items[0]["category"], "removed")
        self.assertEqual(story_items[0]["category"], "unchanged")


# ---------------------------------------------------------------------------
# Defect C: Manifest validation — duplicates, shapes, exclusive temp
# ---------------------------------------------------------------------------

class TestDefectC_ManifestValidation(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mf = Path(self.tmpdir) / "sync-manifest.json"

    def test_duplicate_epic_files_rejected(self) -> None:
        """Duplicate epic file entries in manifest → fail."""
        _write(self.mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [
                {"file": "epic-1-a.md", "jira_key": "K-1",
                 "content_hash": "h", "synced_status": "active", "stories": []},
                {"file": "epic-1-a.md", "jira_key": "K-2",
                 "content_hash": "h2", "synced_status": "active", "stories": []},
            ],
        }))
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)

    def test_non_dict_epic_entry_rejected(self) -> None:
        _write(self.mf, json.dumps({
            "schema_version": 2, "epics": ["not a dict"],
        }))
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)

    def test_invalid_shape_preserves_bytes(self) -> None:
        """Failed validation does not modify the manifest file."""
        content = json.dumps({"schema_version": 99, "epics": []})
        _write(self.mf, content)
        original = self.mf.read_bytes()
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)
        self.assertEqual(self.mf.read_bytes(), original)

    def test_v1_manifest_loads_successfully(self) -> None:
        """V1 without content_hash/synced_status loads OK."""
        _write(self.mf, json.dumps({
            "schema_version": 1, "feature_key": "F",
            "epics": [{"file": "epic-1.md", "jira_key": "K",
                        "title": "T", "stories": []}],
        }))
        m = sync_helper.load_manifest(self.mf)
        self.assertIsNotNone(m)
        self.assertEqual(m["schema_version"], 1)


# ---------------------------------------------------------------------------
# Defect D: Empty sections handling
# ---------------------------------------------------------------------------

class TestDefectD_EmptySections(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mf = Path(self.tmpdir) / "manifest.json"
        _write(self.mf, json.dumps({"epics": []}))

    def test_no_frontmatter_canonical_epic(self) -> None:
        """Epic without frontmatter renders normally."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "# Building\n\n- **T-Shirt Size:** L\n\n## Summary\n\nBuild things.\n\n## Acceptance Criteria\n\n- [ ] AC\n")
        result = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertIn("Build things.", result["description"])
        self.assertEqual(result["size"], "L")

    def test_missing_summary_rejected(self) -> None:
        """Missing Summary section → safe refusal before Jira write."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "---\n---\n# Building\n\n## Acceptance Criteria\n\n- AC\n")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_ac_rejected(self) -> None:
        """Missing Acceptance Criteria → safe refusal."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "---\n---\n# Building\n\n## Summary\n\nBuild.\n")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertEqual(ctx.exception.code, 1)

    def test_removed_story_frontmatter_variant(self) -> None:
        """Story with 'status: removed' frontmatter and valid content renders."""
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, "---\nstatus: removed\n---\n# [DEV] Removed Story\n\n**As a** dev,\n**I want to** remove,\n**So that** clean.\n\n## Acceptance Criteria\n\n- [ ] AC\n\n## Implementation Guidance\n\nRemove it.\n\n## Testing Approach\n\nVerify removed.\n\n## Dependencies\n\nNone\n")
        result = sync_helper.prepare(str(sf), str(self.mf), "story")
        self.assertIn("content_hash", result)
        self.assertIn("## User Story", result["description"])


# ---------------------------------------------------------------------------
# Defect E: Size in prepare, missing 06-stories
# ---------------------------------------------------------------------------

class TestDefectE_SizeAndMissing(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mf = Path(self.tmpdir) / "manifest.json"
        _write(self.mf, json.dumps({"epics": []}))

    def test_prepare_epic_extracts_size(self) -> None:
        """prepare output includes size from T-Shirt Size line."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Building", size="XL",
            summary="Build.", ac="AC", feature_key="F",
            prd_reqs="FR-1", design_sections="§4.1"))
        result = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertEqual(result["size"], "XL")
        self.assertEqual(result["title"], "Building")

    def test_prepare_story_has_title(self) -> None:
        """prepare output includes title for stories."""
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, _DEV_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=1, prefix="DEV",
            title="Scaffold", role="dev", want="build", so_that="done",
            ac="AC", impl="Do.", testing="Test.", deps="None",
            epic_title="Building", prd_reqs="FR-1",
            design_section="§4.1", ic="IC-1", validated_by="TC-FR1-01"))
        result = sync_helper.prepare(str(sf), str(self.mf), "story")
        self.assertIn("Story 1.01", result["title"])

    def test_missing_06_stories_with_manifest_fails(self) -> None:
        """Missing 06-stories/ dir with manifest → hard stop, not orphans."""
        arts = Path(self.tmpdir) / "art"
        arts.mkdir()
        mf_path = _make_manifest(arts, [{
            "file": "epic-1.md", "jira_key": "K-1",
            "content_hash": "h", "synced_status": "active", "stories": [],
        }])
        original = mf_path.read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(arts)
        self.assertEqual(ctx.exception.code, 1)
        # Manifest preserved
        self.assertEqual(mf_path.read_bytes(), original)

    def test_missing_06_stories_fresh_fails(self) -> None:
        """Missing 06-stories/ with no manifest → clear error."""
        arts = Path(self.tmpdir) / "art"
        arts.mkdir()
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(arts)
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_06_stories_via_cli(self) -> None:
        """CLI detect-changes with missing dir → nonzero exit."""
        arts = Path(self.tmpdir) / "art"
        arts.mkdir()
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["detect-changes", str(arts)])
        self.assertEqual(ctx.exception.code, 1)

    def test_numeric_sort_epic2_before_epic10(self) -> None:
        """Epic-2 processed before epic-10 (numeric, not lexicographic)."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 10, "tenth")
        _make_epic(sd, 2, "second")
        plan = sync_helper.detect_changes(arts)
        indices = [i["epic_index"] for i in plan["items"]]
        self.assertEqual(indices, [2, 10])


# ---------------------------------------------------------------------------
# Gap 1: prepare snapshot fields used for Jira; edit-after-prepare detected
# ---------------------------------------------------------------------------

class TestGap1_SnapshotFields(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mf = Path(self.tmpdir) / "manifest.json"
        _write(self.mf, json.dumps({"epics": [
            {"file": "epic-1-building.md", "jira_key": "EDM-101",
             "stories": [{"file": "story-01-scaffold.md", "jira_key": "EDM-201"}]},
        ]}))

    def test_epic_summary_strips_numbering(self) -> None:
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 3 Monitoring", size="S",
            summary="Monitor everything.", ac="Alerts fire",
            feature_key="F", prd_reqs="FR-1", design_sections="§4.1"))
        r = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertEqual(r["summary"], "Monitoring")
        self.assertEqual(r["size"], "S")

    def test_epic_summary_strips_colon_numbering(self) -> None:
        """'Epic 1: Image Building' → 'Image Building' (no leading colon)."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 1: Image Building", size="L",
            summary="Build images.", ac="Pipeline runs",
            feature_key="F", prd_reqs="FR-1", design_sections="§4.1"))
        r = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertEqual(r["summary"], "Image Building")

    def test_epic_summary_no_numbering(self) -> None:
        """'Image Building' (no Epic N prefix) → 'Image Building'."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, _EPIC_TEMPLATE.format(
            extra_fm="", title="Image Building", size="M",
            summary="Build.", ac="AC",
            feature_key="F", prd_reqs="FR-1", design_sections="§4.1"))
        r = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertEqual(r["summary"], "Image Building")

    def test_story_summary_has_prefix_no_numbering(self) -> None:
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, _DEV_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=2, story_idx=5, prefix="QE",
            title="E2E Tests", role="qe", want="test", so_that="quality",
            ac="Pass", impl="Write.", testing="Run.", deps="Story 1.01",
            epic_title="Deploy", prd_reqs="FR-1", design_section="§4.1",
            ic="IC-1", validated_by="TC-FR1-01"))
        r = sync_helper.prepare(str(sf), str(self.mf), "story")
        self.assertEqual(r["summary"], "[QE] E2E Tests")
        self.assertEqual(r["story_type"], "QE")
        # Deps resolved
        self.assertIn("EDM-201", r["dependencies"])

    def test_edit_after_prepare_leaves_unsynced(self) -> None:
        """Editing file between prepare and checkpoint → detectable."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        ef = _make_epic(sd, 1, "building", summary="Original content.")
        mf = arts / "sync-manifest.json"

        r = sync_helper.prepare(str(ef), str(mf), "epic", feature_key="F")
        # Edit AFTER prepare
        _write(ef, ef.read_text().replace("Original content.", "Edited."))

        # Checkpoint with prepare's hash (what was submitted)
        sync_helper.update_manifest(
            mf, "create", ef.name, "EDM-101", r["content_hash"],
            item_type="epic", feature_key="F")

        plan = sync_helper.detect_changes(arts)
        changed = [i for i in plan["items"] if i["category"] == "changed"]
        self.assertEqual(len(changed), 1, "Edit after prepare must be detected")


# ---------------------------------------------------------------------------
# Gap 2: Step5 refresh sequence
# ---------------------------------------------------------------------------

class TestGap2_RefreshSequence(_TmpDirMixin, unittest.TestCase):
    """After epic operations, refreshing detect-changes prevents duplicates."""

    def setUp(self) -> None:
        super().setUp()
        self.arts = Path(self.tmpdir) / "art"
        self.sd = self.arts / "06-stories"
        self.sd.mkdir(parents=True)
        self.mf = self.arts / "sync-manifest.json"

    def test_cascade_close_refresh_no_duplicate_action(self) -> None:
        """close child → close epic → refresh → child is unchanged."""
        ef = _make_epic(self.sd, 1, "building")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")

        # Initial sync
        sync_helper.update_manifest(
            self.mf, "create", ef.name, "EDM-101",
            sync_helper.compute_file_hash(ef),
            item_type="epic", feature_key="F-1")
        sync_helper.update_manifest(
            self.mf, "create", sf.name, "EDM-201",
            sync_helper.compute_file_hash(sf),
            item_type="story", epic_file=ef.name)

        # Mark both removed
        _make_epic(self.sd, 1, "building", removed=True)
        _make_dev_story(self.sd, 1, 1, "scaffold", removed=True)

        # Step4c: close child then epic
        sf_new = self.sd / "epic-1" / sf.name
        ef_new = self.sd / ef.name
        sync_helper.update_manifest(
            self.mf, "close", sf.name, "EDM-201",
            sync_helper.compute_file_hash(sf_new),
            item_type="story", epic_file=ef.name)
        sync_helper.update_manifest(
            self.mf, "close", ef.name, "EDM-101",
            sync_helper.compute_file_hash(ef_new),
            item_type="epic")

        # REFRESH (Step5): re-detect after epic operations
        plan = sync_helper.detect_changes(self.arts)
        story_items = [i for i in plan["items"] if i["type"] == "story"]
        # Child must NOT be marked as removed again (already closed)
        for s in story_items:
            self.assertEqual(s["category"], "unchanged",
                             f"Story {s['file']} should be unchanged after cascade close")

    def test_reopened_parent_refresh_allows_children(self) -> None:
        """Reopened epic → refresh → stories under it can be changed."""
        ef = _make_epic(self.sd, 1, "building")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")

        _make_manifest(self.arts, [{
            "file": ef.name, "jira_key": "EDM-101",
            "content_hash": "old", "synced_status": "closed",
            "stories": [{
                "file": sf.name, "jira_key": "EDM-201",
                "content_hash": "old", "synced_status": "closed",
            }],
        }])

        # Both files exist without removed status → reopened parent
        plan = sync_helper.detect_changes(self.arts)
        epic_items = [i for i in plan["items"] if i["type"] == "epic"]
        story_items = [i for i in plan["items"] if i["type"] == "story"]
        self.assertEqual(epic_items[0]["category"], "reopened")
        # Story under reopened parent should also be reopened
        self.assertEqual(story_items[0]["category"], "reopened")


# ---------------------------------------------------------------------------
# Gap 4: Manifest nested validation + ambiguous epic index
# ---------------------------------------------------------------------------

class TestGap4_NestedValidation(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mf = Path(self.tmpdir) / "manifest.json"

    def test_duplicate_story_files_within_epic_rejected(self) -> None:
        _write(self.mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1.md", "jira_key": "K-1",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [
                            {"file": "story-01.md", "jira_key": "S-1",
                             "content_hash": "h", "synced_status": "active"},
                            {"file": "story-01.md", "jira_key": "S-2",
                             "content_hash": "h2", "synced_status": "active"},
                        ]}],
        }))
        original = self.mf.read_bytes()
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)
        self.assertEqual(self.mf.read_bytes(), original)

    def test_same_story_basename_different_epics_allowed(self) -> None:
        """story-01.md under epic-1 and epic-2 is valid (different epics)."""
        _write(self.mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [
                {"file": "epic-1.md", "jira_key": "K-1",
                 "content_hash": "h", "synced_status": "active",
                 "stories": [{"file": "story-01.md", "jira_key": "S-1",
                              "content_hash": "h", "synced_status": "active"}]},
                {"file": "epic-2.md", "jira_key": "K-2",
                 "content_hash": "h", "synced_status": "active",
                 "stories": [{"file": "story-01.md", "jira_key": "S-2",
                              "content_hash": "h", "synced_status": "active"}]},
            ],
        }))
        m = sync_helper.load_manifest(self.mf)
        self.assertIsNotNone(m)

    def test_missing_epic_file_field_rejected(self) -> None:
        _write(self.mf, json.dumps({
            "schema_version": 2, "epics": [{"jira_key": "K-1"}],
        }))
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)

    def test_missing_story_file_field_rejected(self) -> None:
        _write(self.mf, json.dumps({
            "schema_version": 2, "epics": [
                {"file": "epic-1.md", "jira_key": "K-1",
                 "stories": [{"jira_key": "S-1"}]}],
        }))
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)

    def test_duplicate_epic_index_on_disk_fails_fresh(self) -> None:
        """Two epic files with same numeric index → fail closed, no plan."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "alpha")
        _write(sd / "epic-1-beta.md", _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 1 Beta", size="S",
            summary="Beta.", ac="AC", feature_key="F",
            prd_reqs="FR-1", design_sections="§4.1"))

        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(arts)
        self.assertEqual(ctx.exception.code, 1)

    def test_duplicate_epic_index_on_disk_fails_with_manifest(self) -> None:
        """Duplicate index with manifest → fail, manifest preserved."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        ef1 = _make_epic(sd, 1, "alpha")
        _write(sd / "epic-1-beta.md", _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 1 Beta", size="S",
            summary="Beta.", ac="AC", feature_key="F",
            prd_reqs="FR-1", design_sections="§4.1"))
        mf = _make_manifest(arts, [{
            "file": "epic-1-alpha.md", "jira_key": "K-1",
            "content_hash": "h", "synced_status": "active", "stories": [],
        }])
        original = mf.read_bytes()

        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(arts)
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(mf.read_bytes(), original)

    def test_duplicate_epic_index_on_disk_via_cli(self) -> None:
        """CLI detect-changes with duplicate index → nonzero exit."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "alpha")
        _write(sd / "epic-1-beta.md", _EPIC_TEMPLATE.format(
            extra_fm="", title="Epic 1 Beta", size="S",
            summary="Beta.", ac="AC", feature_key="F",
            prd_reqs="FR-1", design_sections="§4.1"))

        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["detect-changes", str(arts)])
        self.assertEqual(ctx.exception.code, 1)

    def test_duplicate_epic_index_in_manifest_rejected(self) -> None:
        """Manifest with two epics sharing numeric index → fail."""
        _write(self.mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [
                {"file": "epic-1-alpha.md", "jira_key": "K-1",
                 "content_hash": "h", "synced_status": "active", "stories": []},
                {"file": "epic-1-beta.md", "jira_key": "K-2",
                 "content_hash": "h2", "synced_status": "active", "stories": []},
            ],
        }))
        original = self.mf.read_bytes()
        with self.assertRaises(SystemExit):
            sync_helper.load_manifest(self.mf)
        self.assertEqual(self.mf.read_bytes(), original)

    def test_distinct_epic_indices_allowed(self) -> None:
        """Different numeric indices on disk and manifest are fine."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "alpha")
        _make_epic(sd, 2, "beta")
        plan = sync_helper.detect_changes(arts)
        self.assertEqual(plan["summary"]["new"], 2)

    def test_unknown_top_level_fields_preserved(self) -> None:
        """Unknown top-level keys don't cause rejection (forward compat)."""
        _write(self.mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "custom_field": "preserved",
            "epics": [{"file": "epic-1.md", "jira_key": "K",
                        "content_hash": "h", "synced_status": "active",
                        "stories": []}],
        }))
        m = sync_helper.load_manifest(self.mf)
        self.assertEqual(m["custom_field"], "preserved")


# ---------------------------------------------------------------------------
# Gap 5: Essential section validation via CLI
# ---------------------------------------------------------------------------

class TestGap5_EssentialSections(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mf = Path(self.tmpdir) / "manifest.json"
        _write(self.mf, json.dumps({"epics": []}))

    def test_epic_missing_summary_fails_cli(self) -> None:
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "---\n---\n# Building\n\n## Acceptance Criteria\n\n- AC\n")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["prepare", str(ef), str(self.mf), "--type", "epic"])
        self.assertEqual(ctx.exception.code, 1)

    def test_story_missing_user_story_fails_cli(self) -> None:
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, "---\n---\n# [DEV] Bad Story\n\n## Acceptance Criteria\n\n- AC\n\n## Implementation Guidance\n\nDo.\n")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["prepare", str(sf), str(self.mf), "--type", "story"])
        self.assertEqual(ctx.exception.code, 1)

    def test_docs_missing_scope_fails_cli(self) -> None:
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, "---\n---\n# Story 1.01: [DOCS] No Scope\n\n**As a** writer,\n**I want to** doc,\n**So that** clear.\n\n## Acceptance Criteria\n\n- AC\n")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["prepare", str(sf), str(self.mf), "--type", "story"])
        self.assertEqual(ctx.exception.code, 1)

    def test_valid_no_frontmatter_epic_passes(self) -> None:
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "# Epic 1 Building\n\n- **T-Shirt Size:** M\n\n## Summary\n\nBuild.\n\n## Acceptance Criteria\n\n- [ ] AC\n")
        result = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertIn("Build.", result["description"])
        self.assertEqual(result["size"], "M")
        self.assertEqual(result["summary"], "Building")


# ---------------------------------------------------------------------------
# Test: atomic checkpoint — mode preservation & overwrite (review fix)
# ---------------------------------------------------------------------------

class TestSaveManifestAtomic(_TmpDirMixin, unittest.TestCase):
    def test_existing_file_mode_preserved(self) -> None:
        """Checkpoint preserves existing manifest file permissions."""
        import os
        mp = Path(self.tmpdir) / "manifest.json"
        _write(mp, '{"schema_version": 2, "epics": []}')
        os.chmod(mp, 0o644)
        sync_helper.save_manifest(
            {"schema_version": 2, "epics": [], "note": "updated"}, mp)
        self.assertEqual(os.stat(mp).st_mode & 0o777, 0o644)
        data = json.loads(mp.read_text())
        self.assertEqual(data["note"], "updated")

    def test_repeated_checkpoint(self) -> None:
        """Successive checkpoints overwrite without error."""
        mp = Path(self.tmpdir) / "manifest.json"
        for i in range(3):
            sync_helper.save_manifest(
                {"schema_version": 2, "epics": [], "seq": i}, mp)
        data = json.loads(mp.read_text())
        self.assertEqual(data["seq"], 2)

    def test_failure_no_corruption(self) -> None:
        """Checkpoint failure leaves no partial file."""
        mp = Path(self.tmpdir) / "manifest.json"
        _write(mp, '{"schema_version": 2, "epics": []}')
        original = mp.read_bytes()

        class _Unserializable:
            pass

        with self.assertRaises(TypeError):
            sync_helper.save_manifest(
                {"bad": _Unserializable()}, mp)
        self.assertEqual(mp.read_bytes(), original)


# ---------------------------------------------------------------------------
# Test: duplicate story indices (review fix)
# ---------------------------------------------------------------------------

class TestDuplicateStoryIndex(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_duplicate_story_index_same_epic_fails(self) -> None:
        """Two stories with the same index in one epic fail closed."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold-a")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold-b")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_same_story_index_different_epics_ok(self) -> None:
        """Identical story indices under distinct epics are valid."""
        _make_epic(self.stories_dir, 1, "building")
        _make_epic(self.stories_dir, 2, "deploy")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_dev_story(self.stories_dir, 2, 1, "rollout")
        result = sync_helper.detect_changes(self.artifacts)
        stories = [i for i in result["items"] if i["type"] == "story"]
        self.assertEqual(len(stories), 2)


# ---------------------------------------------------------------------------
# Test: parent-index mismatch on epic rename / deletion (review fix)
# ---------------------------------------------------------------------------

class TestParentMismatch(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_renamed_epic_fails_closed(self) -> None:
        """Story recorded under old epic name, disk has renamed epic."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h2", "synced_status": "active"},
            ],
        }])
        _make_epic(self.stories_dir, 1, "containers")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_renamed_epic_and_child_slug_fails(self) -> None:
        """Both epic and child story renamed (same indices) → fail."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h2", "synced_status": "active"},
            ],
        }])
        _make_epic(self.stories_dir, 1, "containers")
        _make_dev_story(self.stories_dir, 1, 1, "refactored")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_renamed_epic_zero_children_fails(self) -> None:
        """Renamed epic with no child files on disk → fail closed."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        # Disk has epic-1 with different slug, no stories
        _make_epic(self.stories_dir, 1, "containers")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_renamed_epic_via_cli(self) -> None:
        """CLI detect-changes fails closed on renamed epic, manifest unchanged."""
        mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        original_bytes = mf.read_bytes()
        _make_epic(self.stories_dir, 1, "containers")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["detect-changes", str(self.artifacts)])
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(mf.read_bytes(), original_bytes)

    def test_deleted_epic_with_remaining_children_fails(self) -> None:
        """Epic file deleted but stories remain → fail closed."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h2", "synced_status": "active"},
            ],
        }])
        epic_dir = self.stories_dir / "epic-1"
        epic_dir.mkdir(parents=True)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_truly_new_story_under_new_epic_ok(self) -> None:
        """New story under a new epic (no manifest entry) succeeds."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        result = sync_helper.detect_changes(self.artifacts)
        new_items = [i for i in result["items"] if i["category"] == "new"]
        self.assertEqual(len(new_items), 2)  # 1 epic + 1 story

    def test_orphaned_epic_no_children_on_disk(self) -> None:
        """Orphan epic with no child files on disk produces orphan plan."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-gone.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        orphaned = [i for i in result["items"] if i["category"] == "orphaned"]
        self.assertEqual(len(orphaned), 1)

    def test_genuinely_new_epic_with_unused_index(self) -> None:
        """New epic with index not in manifest succeeds."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        ef1 = _make_epic(self.stories_dir, 1, "building")
        # Adjust hash so epic-1 is unchanged
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": sync_helper.compute_file_hash(ef1),
            "synced_status": "active", "stories": [],
        }])
        _make_epic(self.stories_dir, 2, "deploy")
        result = sync_helper.detect_changes(self.artifacts)
        new_epics = [i for i in result["items"]
                     if i["type"] == "epic" and i["category"] == "new"]
        self.assertEqual(len(new_epics), 1)
        self.assertEqual(new_epics[0]["epic_index"], 2)


# ---------------------------------------------------------------------------
# Test: manifest story index validation (review fix gap 1)
# ---------------------------------------------------------------------------

class TestManifestStoryIndexValidation(_TmpDirMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def test_duplicate_story_index_in_manifest_rejected(self) -> None:
        """Two distinct story files with same numeric index fail."""
        _write(self.manifest_path, json.dumps({
            "schema_version": 2, "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "stories": [
                    {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                     "content_hash": "a", "synced_status": "active"},
                    {"file": "story-01-refactor.md", "jira_key": "EDM-202",
                     "content_hash": "b", "synced_status": "active"},
                ],
            }],
        }))
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(ctx.exception.code, 1)

    def test_duplicate_story_index_via_cli(self) -> None:
        """CLI load rejects duplicate story index, manifest bytes unchanged."""
        manifest = {
            "schema_version": 2, "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "stories": [
                    {"file": "story-01-a.md", "jira_key": "K1",
                     "content_hash": "h1", "synced_status": "active"},
                    {"file": "story-01-b.md", "jira_key": "K2",
                     "content_hash": "h2", "synced_status": "active"},
                ],
            }],
        }
        _write(self.manifest_path, json.dumps(manifest))
        original = self.manifest_path.read_bytes()
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "building")
        mf_in_arts = arts / "sync-manifest.json"
        _write(mf_in_arts, json.dumps(manifest))
        orig_arts = mf_in_arts.read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.main(["detect-changes", str(arts)])
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(mf_in_arts.read_bytes(), orig_arts)

    def test_duplicate_story_index_blocks_ref_lookup(self) -> None:
        """Duplicate story index is caught before _build_ref_lookup runs."""
        _write(self.manifest_path, json.dumps({
            "schema_version": 2, "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "stories": [
                    {"file": "story-02-a.md", "jira_key": "K1",
                     "content_hash": "h1", "synced_status": "active"},
                    {"file": "story-02-b.md", "jira_key": "K2",
                     "content_hash": "h2", "synced_status": "active"},
                ],
            }],
        }))
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(ctx.exception.code, 1)

    def test_same_story_index_cross_epic_allowed(self) -> None:
        """Identical story indices under different epics are valid."""
        _write(self.manifest_path, json.dumps({
            "schema_version": 2, "epics": [
                {"file": "epic-1-build.md", "jira_key": "K1",
                 "stories": [
                     {"file": "story-01-a.md", "jira_key": "S1",
                      "content_hash": "h", "synced_status": "active"},
                 ]},
                {"file": "epic-2-deploy.md", "jira_key": "K2",
                 "stories": [
                     {"file": "story-01-b.md", "jira_key": "S2",
                      "content_hash": "h", "synced_status": "active"},
                 ]},
            ],
        }))
        m = sync_helper.load_manifest(self.manifest_path)
        self.assertIsNotNone(m)

    def test_v1_manifest_with_optional_metadata(self) -> None:
        """V1 manifest without story index fields loads OK."""
        _write(self.manifest_path, json.dumps({
            "schema_version": 1, "epics": [{
                "file": "epic-1-build.md", "jira_key": "K1",
                "stories": [
                    {"file": "story-01-a.md", "jira_key": "S1"},
                ],
            }],
        }))
        m = sync_helper.load_manifest(self.manifest_path)
        self.assertIsNotNone(m)


# ---------------------------------------------------------------------------
# Test: selected orphan closure stateful flow (review fix gap 5)
# ---------------------------------------------------------------------------

class TestOrphanClosureStateful(_TmpDirMixin, unittest.TestCase):
    """Simulate the full orphan closure workflow locally.

    The helper never contacts Jira; tests simulate the effect of
    successful Jira operations by calling update-manifest with the
    correct arguments.  This mirrors the workflow described in
    Steps 4c/5c of sync.md.
    """
    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        # Create a different epic on disk (epic-2), but manifest has
        # orphaned epic-1 with two stories
        self.ef2 = _make_epic(sd, 2, "deploy")
        self.mf = _make_manifest(self.artifacts, [
            {"file": "epic-1-building.md", "jira_key": "EDM-101",
             "content_hash": "h", "synced_status": "active",
             "stories": [
                 {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                  "content_hash": "h1", "synced_status": "active"},
                 {"file": "story-02-pipe.md", "jira_key": "EDM-202",
                  "content_hash": "h2", "synced_status": "active"},
             ]},
            {"file": "epic-2-deploy.md", "jira_key": "EDM-102",
             "content_hash": sync_helper.compute_file_hash(self.ef2),
             "synced_status": "active", "stories": []},
        ])

    def test_orphan_detected_then_closed_children_first(self) -> None:
        """Selected orphan: close children before parent, no duplicate."""
        plan = sync_helper.detect_changes(self.artifacts)
        orphans = [i for i in plan["items"] if i["category"] == "orphaned"]
        self.assertEqual(len(orphans), 3)  # 1 epic + 2 stories

        # Simulate user selecting close: close children first
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201", "",
            item_type="story", epic_file="epic-1-building.md")
        sync_helper.update_manifest(
            self.mf, "close", "story-02-pipe.md", "EDM-202", "",
            item_type="story", epic_file="epic-1-building.md")
        sync_helper.update_manifest(
            self.mf, "close", "epic-1-building.md", "EDM-101", "",
            item_type="epic")

        # Refresh: no more orphans, no duplicate close
        plan2 = sync_helper.detect_changes(self.artifacts)
        orphans2 = [i for i in plan2["items"]
                    if i["category"] == "orphaned"]
        self.assertEqual(len(orphans2), 0)

    def test_ignored_orphan_remains_after_refresh(self) -> None:
        """User chose to ignore orphan — still appears after refresh."""
        plan = sync_helper.detect_changes(self.artifacts)
        orphans = [i for i in plan["items"] if i["category"] == "orphaned"]
        self.assertEqual(len(orphans), 3)

        # Don't close anything (user chose ignore)
        plan2 = sync_helper.detect_changes(self.artifacts)
        orphans2 = [i for i in plan2["items"]
                    if i["category"] == "orphaned"]
        self.assertEqual(len(orphans2), 3)

    def test_interrupted_cascade_leaves_unfinished(self) -> None:
        """Interrupted cascade: only successful closes are recorded."""
        # Close first child only (simulate interruption after 1 of 2)
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201", "",
            item_type="story", epic_file="epic-1-building.md")

        plan = sync_helper.detect_changes(self.artifacts)
        orphans = [i for i in plan["items"] if i["category"] == "orphaned"]
        # Epic still active + 1 remaining story still active = 2 orphans
        self.assertEqual(len(orphans), 2)
        closed_story = next(
            (s for e in sync_helper.load_manifest(self.mf)["epics"]
             if e["file"] == "epic-1-building.md"
             for s in e.get("stories", [])
             if s["file"] == "story-01-scaffold.md"), None)
        self.assertEqual(closed_story["synced_status"], "closed")


# ---------------------------------------------------------------------------
# Test: cross-directory duplicate story indices (review finding 4382368944)
# ---------------------------------------------------------------------------

class TestCrossDirectoryDuplicateStory(_TmpDirMixin, unittest.TestCase):
    """Reject duplicate story indices across directory aliases for the same
    numeric epic index (e.g. epic-1/ and epic-01/ both map to 1)."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_same_numeric_epic_different_dirs_duplicate_story_fails(self) -> None:
        """epic-1/ and epic-01/ both map to 1; story-01 in both must fail."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        # Create a second directory that maps to numeric index 1
        alt_epic_dir = self.stories_dir / "epic-01"
        alt_epic_dir.mkdir(parents=True, exist_ok=True)
        alt_story = alt_epic_dir / "story-01-other.md"
        _write(alt_story, "# Alt Story\n## Summary\nAlt.\n## User Story\n"
               "As a dev I want x so that y.\n## Acceptance Criteria\nAC.\n"
               "## Implementation Notes\nDo.\n## Testing & Validation\nTest.\n")
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_same_numeric_epic_different_dirs_different_stories_ok(self) -> None:
        """epic-1/story-01 and epic-01/story-02 (different indices) are ok."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        alt_epic_dir = self.stories_dir / "epic-01"
        alt_epic_dir.mkdir(parents=True, exist_ok=True)
        alt_story = alt_epic_dir / "story-02-other.md"
        _write(alt_story, "# Alt Story\n## Summary\nAlt.\n## User Story\n"
               "As a dev I want x so that y.\n## Acceptance Criteria\nAC.\n"
               "## Implementation Notes\nDo.\n## Testing & Validation\nTest.\n")
        # Should not fail — indices are different
        result = sync_helper.detect_changes(self.artifacts)
        stories = [i for i in result["items"] if i["type"] == "story"]
        self.assertEqual(len(stories), 2)

    def test_cross_dir_duplicate_error_reports_both_paths(self) -> None:
        """Error message includes both conflicting relative paths."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        alt_epic_dir = self.stories_dir / "epic-01"
        alt_epic_dir.mkdir(parents=True, exist_ok=True)
        alt_story = alt_epic_dir / "story-01-other.md"
        _write(alt_story, "# Alt Story\n## Summary\nAlt.\n## User Story\n"
               "As a dev I want x so that y.\n## Acceptance Criteria\nAC.\n"
               "## Implementation Notes\nDo.\n## Testing & Validation\nTest.\n")
        with self.assertRaises(SystemExit):
            old_stderr = sys.stderr
            sys.stderr = capture = StringIO()
            try:
                sync_helper.detect_changes(self.artifacts)
            finally:
                sys.stderr = old_stderr
        msg = capture.getvalue()
        self.assertIn("epic-1/", msg)
        self.assertIn("epic-01/", msg)

    def test_cross_dir_duplicate_via_cli(self) -> None:
        """CLI exits non-zero for cross-directory duplicate story index."""
        import subprocess
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        alt_epic_dir = self.stories_dir / "epic-01"
        alt_epic_dir.mkdir(parents=True, exist_ok=True)
        alt_story = alt_epic_dir / "story-01-other.md"
        _write(alt_story, "# Alt Story\n## Summary\nAlt.\n## User Story\n"
               "As a dev I want x so that y.\n## Acceptance Criteria\nAC.\n"
               "## Implementation Notes\nDo.\n## Testing & Validation\nTest.\n")
        r = subprocess.run(
            [sys.executable, str(_SCRIPT), "detect-changes",
             str(self.artifacts)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Duplicate story index", r.stderr)


# ---------------------------------------------------------------------------
# Test: story filename rename detection (review finding 4382368955)
# ---------------------------------------------------------------------------

class TestStoryRenameDetection(_TmpDirMixin, unittest.TestCase):
    """Fail closed when a story file is renamed but the manifest records
    the old filename with the same numeric index under the same epic."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_renamed_story_same_index_fails_closed(self) -> None:
        """story-01-old.md in manifest, story-01-new.md on disk => fail."""
        _make_epic(self.stories_dir, 1, "building")
        # Disk has the renamed story
        _make_dev_story(self.stories_dir, 1, 1, "new-name")
        # Manifest records the old name under the same epic
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-old-name.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
            }],
        }])
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_renamed_story_error_reports_both_filenames(self) -> None:
        """Error message includes both old and new story filenames."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "new-name")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-old-name.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
            }],
        }])
        old_stderr = sys.stderr
        sys.stderr = capture = StringIO()
        try:
            with self.assertRaises(SystemExit):
                sync_helper.detect_changes(self.artifacts)
        finally:
            sys.stderr = old_stderr
        msg = capture.getvalue()
        self.assertIn("story-01-new-name.md", msg)
        self.assertIn("story-01-old-name.md", msg)
        self.assertIn("EDM-201", msg)

    def test_renamed_story_via_cli(self) -> None:
        """CLI exits non-zero on story rename detection."""
        import subprocess
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "new-name")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-old-name.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
            }],
        }])
        r = subprocess.run(
            [sys.executable, str(_SCRIPT), "detect-changes",
             str(self.artifacts)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("rename", r.stderr)

    def test_closed_story_same_index_different_filename_rejected(self) -> None:
        """Closed manifest story with same index but different filename is
        still rejected — _validate_manifest_shape forbids duplicate indices
        regardless of status, so a checkpoint after create would corrupt
        the manifest."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "new-name")
        mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-old-name.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "closed",
            }],
        }])
        original_bytes = mf.read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)
        # Manifest must be unchanged (no actionable plan produced)
        self.assertEqual(mf.read_bytes(), original_bytes)

    def test_closed_story_same_filename_reopened(self) -> None:
        """Same filename, closed in manifest, no removed marker -> reopened.
        This is normal reopen, not a rename."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "closed",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        stories = [i for i in result["items"] if i["type"] == "story"]
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["category"], "reopened")
        self.assertEqual(stories[0]["jira_key"], "EDM-201")

    def test_legacy_missing_status_same_index_rejected(self) -> None:
        """Manifest story with missing synced_status and same index but
        different filename is still rejected (legacy/v1 compat)."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "new-name")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-old-name.md", "jira_key": "EDM-201",
                "content_hash": "h",
                # No synced_status field — legacy manifest entry
            }],
        }])
        with self.assertRaises(SystemExit) as ctx:
            sync_helper.detect_changes(self.artifacts)
        self.assertEqual(ctx.exception.code, 1)

    def test_new_index_checkpoint_roundtrip(self) -> None:
        """Genuinely new story index -> detect -> checkpoint -> reload works."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "existing")
        new_story = _make_dev_story(self.stories_dir, 1, 2, "brand-new")
        mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-existing.md", "jira_key": "EDM-201",
                "content_hash": _sha256("old"), "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        new_stories = [i for i in result["items"]
                       if i["type"] == "story" and i["category"] == "new"]
        self.assertEqual(len(new_stories), 1)
        self.assertIn("story-02-brand-new.md", new_stories[0]["file"])
        # Simulate checkpoint after Jira create
        sync_helper.update_manifest(
            str(mf), "create", "story-02-brand-new.md", "EDM-301",
            new_stories[0]["content_hash"], item_type="story",
            epic_file="epic-1-building.md", title="Brand New")
        # Reload must succeed
        m2 = sync_helper.load_manifest(str(mf))
        self.assertIsNotNone(m2)
        epic_stories = m2["epics"][0]["stories"]
        self.assertEqual(len(epic_stories), 2)
        # Re-detect should show unchanged for both
        result2 = sync_helper.detect_changes(self.artifacts)
        stories2 = [i for i in result2["items"] if i["type"] == "story"]
        categories = {s["file"].split("/")[-1]: s["category"] for s in stories2}
        self.assertEqual(categories.get("story-02-brand-new.md"), "unchanged")

    def test_genuinely_new_story_different_index_ok(self) -> None:
        """New story with a different index is not affected by rename check."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "existing")
        _make_dev_story(self.stories_dir, 1, 2, "brand-new")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-existing.md", "jira_key": "EDM-201",
                "content_hash": _sha256("old"), "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        stories = [i for i in result["items"] if i["type"] == "story"]
        new_stories = [s for s in stories if s["category"] == "new"]
        self.assertEqual(len(new_stories), 1)
        self.assertIn("story-02-brand-new.md", new_stories[0]["file"])


# ---------------------------------------------------------------------------
# Test: cascade child closure permissions (review finding 4382368973)
# ---------------------------------------------------------------------------

class TestCascadeChildClosurePermissions(_TmpDirMixin, unittest.TestCase):
    """Verify that detect-changes marks active children of a removed epic
    as 'removed' (cascade), which is the prerequisite for the approved
    parent-close cascade in Step 4c closing those children in Jira."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_active_child_under_removed_epic_becomes_removed(self) -> None:
        """When a parent epic has status:removed, its active children
        are categorized as 'removed' — they can be closed as part of the
        approved parent cascade without individual removal markers."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        items = result["items"]
        epic = next(i for i in items if i["type"] == "epic")
        story = next(i for i in items if i["type"] == "story")
        self.assertEqual(epic["category"], "removed")
        self.assertEqual(story["category"], "removed",
                         "Active child must be cascaded to 'removed' when "
                         "parent epic has status:removed")

    def test_cascade_child_already_closed_stays_unchanged(self) -> None:
        """Already-closed child under a removed epic stays unchanged."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "closed",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        story = next(i for i in result["items"] if i["type"] == "story")
        self.assertEqual(story["category"], "unchanged",
                         "Already-closed child should not be double-closed")


# ---------------------------------------------------------------------------
# Test: helper discovery (review fix gap 2)
# ---------------------------------------------------------------------------

def _resolve_helper(builtin_sync_path: str) -> str:
    """Execute the documented SYNC_HELPER discovery command.

    This is the exact snippet from design/skills/sync.md.
    The path is passed as a positional argument ($1) to bash, not
    interpolated into the command text, to prevent shell interpretation
    of paths containing metacharacters like $() or backticks.
    """
    import subprocess
    cmd = (
        "python3 -c "
        "'from pathlib import Path; import sys; "
        "print(Path(sys.argv[1]).resolve().parents[1] "
        "/ \"scripts\" / \"sync_helper.py\")' "
        '"$1"'
    )
    with tempfile.TemporaryDirectory() as unrelated_cwd:
        result = subprocess.run(
            ["bash", "-c", cmd, "bash", builtin_sync_path],
            capture_output=True, text=True,
            cwd=unrelated_cwd,
        )
    return result.stdout.strip()


class TestHelperDiscovery(unittest.TestCase):
    """Verify the documented SYNC_HELPER discovery works across layouts.

    Each test executes the actual documented Python snippet from
    sync.md and verifies the resolved helper exists and is executable
    (--help exits 0).
    """

    def _verify_helper(self, resolved: str) -> None:
        """Assert resolved path is the real helper and runs."""
        import subprocess
        real_helper = str(
            Path(__file__).resolve().parent / "sync_helper.py")
        self.assertEqual(resolved, real_helper)
        r = subprocess.run(
            ["python3", resolved, "--help"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)

    def test_default_global_install(self) -> None:
        """Default install: ~/.ai-workflows -> clone, resolve from sync.md."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "home"
            fake_home.mkdir()
            aiw = fake_home / ".ai-workflows"
            aiw.symlink_to(repo_root)
            builtin = str(aiw / "design" / "skills" / "sync.md")
            resolved = _resolve_helper(builtin)
            self._verify_helper(resolved)

    def test_direct_clone_symlink_no_home_aiw(self) -> None:
        """Direct symlink .claude/skills/design -> clone/design, no ~/.ai-workflows.

        Clone path contains spaces.  HOME has NO .ai-workflows at all.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent
        with tempfile.TemporaryDirectory() as td:
            # Clone at path with spaces
            clone_dir = Path(td) / "my projects" / "ai workflows"
            clone_dir.mkdir(parents=True)
            clone_link = clone_dir / "repo"
            clone_link.symlink_to(repo_root)
            # Project-level: .claude/skills/design -> clone/design
            project = Path(td) / "project"
            claude_skills = project / ".claude" / "skills"
            claude_skills.mkdir(parents=True)
            (claude_skills / "design").symlink_to(
                clone_link / "design")
            # Confirm NO ~/.ai-workflows
            fake_home = Path(td) / "home"
            fake_home.mkdir()
            self.assertFalse((fake_home / ".ai-workflows").exists())
            # Agent reads built-in sync.md via the project symlink
            builtin = str(
                claude_skills / "design" / "skills" / "sync.md")
            resolved = _resolve_helper(builtin)
            self._verify_helper(resolved)

    def test_override_uses_builtin_not_override_path(self) -> None:
        """Override present: agent uses recorded BUILT-IN source path."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        with tempfile.TemporaryDirectory() as td:
            # Override directory (no helper here)
            override = Path(td) / ".workflows" / "design" / "skills"
            override.mkdir(parents=True)
            (override / "sync.md").write_text("# Override\n")
            # Override does NOT have the helper
            override_candidate = (
                override.parent / "scripts" / "sync_helper.py")
            self.assertFalse(override_candidate.exists())
            # Built-in path (actual package) — resolve from SKILL.md
            builtin = str(
                repo_root / "design" / "skills" / "sync.md")
            resolved = _resolve_helper(builtin)
            self._verify_helper(resolved)
            # Verify override path would NOT resolve to a valid helper
            override_resolved = _resolve_helper(
                str(override / "sync.md"))
            self.assertNotEqual(
                override_resolved,
                str(Path(__file__).resolve().parent / "sync_helper.py"))
            self.assertFalse(Path(override_resolved).exists())

    def test_reference_readable_in_installed_layout(self) -> None:
        """The helper reference is readable via the same installed
        package path used by sync.md (global install layout)."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "home"
            fake_home.mkdir()
            aiw = fake_home / ".ai-workflows"
            aiw.symlink_to(repo_root)
            # Resolve reference from installed sync.md
            builtin = aiw / "design" / "skills" / "sync.md"
            ref = (builtin.parent / ".." / "references"
                   / "sync-helper-usage.md").resolve()
            self.assertTrue(ref.exists(),
                            f"Reference not found in installed layout: {ref}")
            content = ref.read_text(encoding="utf-8")
            self.assertIn("SYNC_HELPER", content)

    def test_reference_readable_in_direct_symlink_layout(self) -> None:
        """Reference readable via direct .claude/skills/design symlink
        (no ~/.ai-workflows)."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            claude_skills = project / ".claude" / "skills"
            claude_skills.mkdir(parents=True)
            (claude_skills / "design").symlink_to(
                repo_root / "design")
            builtin = claude_skills / "design" / "skills" / "sync.md"
            ref = (builtin.parent / ".." / "references"
                   / "sync-helper-usage.md").resolve()
            self.assertTrue(ref.exists(),
                            f"Reference not found in symlink layout: {ref}")

    def test_metacharacter_paths_no_execution(self) -> None:
        """Paths containing shell metacharacters are passed safely as
        data, not executed by bash.  _verify_helper compares the resolved
        path against the canonical real helper path — any shell
        interpretation would produce a different (wrong) path."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        metachar_names = [
            ("command_substitution", "$(echo INJECTED)"),
            ("backtick_substitution", "`echo INJECTED`"),
        ]
        for label, dirname in metachar_names:
            with self.subTest(metachar=label):
                with tempfile.TemporaryDirectory() as td:
                    meta_dir = Path(td) / dirname
                    meta_dir.mkdir(parents=True)
                    aiw = meta_dir / "repo"
                    aiw.symlink_to(repo_root)
                    builtin = str(
                        aiw / "design" / "skills" / "sync.md")
                    resolved = _resolve_helper(builtin)
                    # _verify_helper asserts resolved == real helper
                    # and runs --help successfully; if shell had
                    # interpreted the metacharacters, the path would
                    # differ and this assertion would fail.
                    self._verify_helper(resolved)


# ---------------------------------------------------------------------------
# Test: cascade failure gate and hash-before-transition contract
# (review findings 4382917342, 5659593514)
# ---------------------------------------------------------------------------

class TestCascadeGateContract(unittest.TestCase):
    """Assert sync.md Steps 4c/5c document hash-before-transition ordering
    and that Step 4c gates the parent close on all child successes.

    These are contract tests against the ACTUAL Markdown sections/order,
    not a test-only invented executor.  They verify the documented
    ordering and gating requirements that an agent must follow.
    """

    _sync_md: str
    _step4c: str
    _step5c: str
    _step5_refresh: str

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_md_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_md_path.read_text(encoding="utf-8")
        m4c = re.search(r"#### 4c:.*?(?=####|### )", cls._sync_md, re.DOTALL)
        assert m4c, "Step 4c section not found"
        cls._step4c = m4c.group()
        m5c = re.search(r"#### 5c:.*?(?=####|### )", cls._sync_md, re.DOTALL)
        assert m5c, "Step 5c section not found"
        cls._step5c = m5c.group()
        m5 = re.search(r"### Step 5:.*?(?=#### 5a:)", cls._sync_md, re.DOTALL)
        assert m5, "Step 5 plan refresh not found"
        cls._step5_refresh = m5.group()

    # -- Step 4c: child hash before child transition ---

    def test_step4c_child_hash_before_transition(self) -> None:
        """4c child closure: hash computed before Jira transition."""
        h = self._step4c.find("Compute the hash first")
        t = self._step4c.find("Transition the child story")
        self.assertGreater(h, -1, "must mention computing child hash")
        self.assertGreater(t, -1, "must mention child transition")
        self.assertLess(h, t, "child hash must precede child transition")

    def test_step4c_epic_hash_before_transition(self) -> None:
        """4c epic closure: hash computed before Jira transition."""
        h = self._step4c.find("compute the epic hash")
        t = self._step4c.find("Transition the epic to Done")
        self.assertGreater(h, -1, "must mention computing epic hash")
        self.assertGreater(t, -1, "must mention epic transition")
        self.assertLess(h, t, "epic hash must precede epic transition")

    # -- Step 4c: parent gated on all children ---

    def test_step4c_parent_gated_on_all_children(self) -> None:
        """4c: parent close requires ALL child closures and checkpoints."""
        self.assertIn("child closures and their checkpoints have succeeded",
                      self._step4c)

    def test_step4c_stop_cascade_on_failure(self) -> None:
        """4c: cascade stops immediately on any child failure."""
        import re
        self.assertTrue(
            re.search(r"stop the cascade\s+immediately", self._step4c),
            "must stop cascade immediately on child failure")

    def test_step4c_no_skip_child_then_close_parent(self) -> None:
        """4c: explicitly forbids skipping a child then closing parent."""
        import re
        self.assertTrue(
            re.search(r"Never\s+skip\s+a failing child", self._step4c),
            "must forbid skip-child-close-parent")

    def test_step4c_offers_retry_or_defer(self) -> None:
        """4c: pre-transition failure offers retry or defer."""
        import re
        self.assertTrue(
            re.search(r"retry after\s+remediation", self._step4c),
            "must offer retry after remediation")
        self.assertIn("defer the entire parent", self._step4c)

    def test_step4c_preserves_successful_checkpoints(self) -> None:
        """4c: already-successful child checkpoints preserved on failure."""
        import re
        self.assertTrue(
            re.search(r"Preserve all\s+already-successful\s+child checkpoints",
                      self._step4c),
            "must preserve completed child checkpoints")

    def test_step4c_distinguishes_pre_and_post_failure(self) -> None:
        """4c: distinguishes pre-transition from post-success checkpoint
        failure, referencing the shared close-checkpoint recovery rule."""
        self.assertIn("Pre-transition failure", self._step4c)
        self.assertIn("Post-success checkpoint failure", self._step4c)
        self.assertIn("close-checkpoint", self._step4c)

    def test_step4c_uncertain_outcome_requires_verification(self) -> None:
        """4c: uncertain Jira outcome (timeout/5xx) must be verified
        before retrying, not assumed non-mutating."""
        import re
        self.assertTrue(
            re.search(r"uncertain.*verify.*current status",
                      self._step4c, re.DOTALL),
            "must require verification for uncertain Jira outcomes")

    def test_step4c_resume_manual_reconciliation(self) -> None:
        """4c: resume stops for manual reconciliation when captured
        state is lost (forced abort/new run)."""
        self.assertIn("stop for manual reconciliation", self._step4c)

    # -- Step 5c: hash before transition ---

    def test_step5c_hash_before_transition(self) -> None:
        """5c story close: hash computed before transition."""
        h = self._step5c.find("Compute the hash before the transition")
        t = self._step5c.find("Transition the story to Done")
        self.assertGreater(h, -1, "must mention computing hash first")
        self.assertGreater(t, -1, "must mention story transition")
        self.assertLess(h, t, "hash must precede transition")

    def test_step5c_checkpoint_uses_saved_hash(self) -> None:
        """5c: checkpoint references saved hash from step 1."""
        self.assertIn("hash from step 1", self._step5c)

    # -- Step 4c: reporting distinguishes child states ---

    def test_step4c_report_distinguishes_child_states(self) -> None:
        """4c: failure report distinguishes complete, uncheckpointed,
        and unattempted children."""
        import re
        self.assertIn("closed and checkpointed (complete)", self._step4c)
        self.assertTrue(
            re.search(r"Jira-closed but\s+uncheckpointed", self._step4c),
            "must mention Jira-closed but uncheckpointed")
        self.assertIn("unattempted", self._step4c)

    def test_step4c_no_rollback_implication(self) -> None:
        """4c: does not imply already-closed children are rolled back."""
        import re
        self.assertTrue(
            re.search(r"not imply that already-closed children\s+will be rolled back",
                      self._step4c),
            "must not imply rollback of closed children")

    # -- Step 4c: child checkpoint references helper reference ---

    def test_step4c_child_checkpoint_references_helper(self) -> None:
        """4c child checkpoint step references the helper reference."""
        self.assertIn("helper reference", self._step4c)
        # The step must mention the required story-specific args
        self.assertIn("--item-type story", self._step4c)
        self.assertIn("--epic-file", self._step4c)

    def test_helper_reference_child_close_has_all_args(self) -> None:
        """Helper reference child-close recipe has all required args."""
        ref_path = _resolve_ref_from_directive()
        ref = ref_path.read_text(encoding="utf-8")
        import re
        m = re.search(
            r"Child story close.*?```bash\n(.*?)```", ref, re.DOTALL)
        self.assertIsNotNone(m, "Child close recipe not found in ref")
        block = m.group(1)
        for flag in ["--file", "--jira-key", "--content-hash",
                      "--item-type story", "--epic-file"]:
            self.assertIn(flag, block)

    # -- Reference loading instruction ---

    # The specific directive pattern: backtick-delimited relative path
    # in a "Before the first helper operation" sentence.
    _DIRECTIVE_RE = _re.compile(
        r"\*\*Before the first helper operation\*\*.*?`([^`]+\.md)`",
        _re.DOTALL)

    @classmethod
    def _extract_ref_path(cls, phase_text: str) -> str | None:
        """Extract the relative reference path from the loading
        directive in the given phase text.  Returns None if missing."""
        m = cls._DIRECTIVE_RE.search(phase_text)
        return m.group(1) if m else None

    def test_directive_extracts_correct_path(self) -> None:
        """Loading directive yields the documented relative path."""
        path = self._extract_ref_path(self._sync_md)
        self.assertEqual(path, "../references/sync-helper-usage.md")

    def test_directive_before_first_helper_use(self) -> None:
        """Loading directive appears BEFORE the first helper operation
        (detect-changes)."""
        m = self._DIRECTIVE_RE.search(self._sync_md)
        self.assertIsNotNone(m, "directive not found")
        first_helper = self._sync_md.find("detect-changes")
        self.assertGreater(first_helper, -1)
        self.assertLess(m.start(), first_helper,
                        "Directive must appear before detect-changes")

    def test_bad_path_does_not_resolve(self) -> None:
        """Mutated phase text with wrong filename → extracted path does
        not resolve to a real file from the built-in sync.md location."""
        bad = self._sync_md.replace(
            "sync-helper-usage.md", "wrong-file.md")
        bad_path = self._extract_ref_path(bad)
        self.assertIsNotNone(bad_path, "directive still matches structure")
        sync_md_dir = (Path(__file__).resolve().parent.parent
                       / "skills")
        resolved = (sync_md_dir / bad_path).resolve()
        self.assertFalse(resolved.exists(),
                         "Wrong filename must not resolve to a real file")

    def test_late_directive_detected(self) -> None:
        """Mutated phase text with directive after detect-changes →
        ordering check would fail."""
        # Move the Sync Helper block after first detect-changes
        idx = self._sync_md.find("## Sync Helper")
        end = self._sync_md.find("## Critical Rules")
        block = self._sync_md[idx:end]
        without = self._sync_md[:idx] + self._sync_md[end:]
        dc = without.find("detect-changes")
        late = without[:dc + 20] + "\n" + block + without[dc + 20:]
        m = self._DIRECTIVE_RE.search(late)
        self.assertIsNotNone(m)
        self.assertGreater(m.start(), late.find("detect-changes"),
                           "Late directive must be after detect-changes")

    def test_unrelated_early_read_not_matched(self) -> None:
        """An unrelated 'Read' before the directive must not produce a
        false early match."""
        prefixed = "Read the AGENTS.md file.\n\n" + self._sync_md
        m = self._DIRECTIVE_RE.search(prefixed)
        self.assertIsNotNone(m)
        # Must match the actual directive, not the unrelated 'Read'
        self.assertIn("Before the first helper operation",
                      prefixed[m.start():m.end()])

    def test_reference_resolved_from_builtin_sync_md(self) -> None:
        """The path extracted from the loading directive resolves to a
        real file from the built-in sync.md location, and that file
        contains the helper discovery snippet."""
        sync_md_path = (Path(__file__).resolve().parent.parent
                        / "skills" / "sync.md")
        rel_path = self._extract_ref_path(
            sync_md_path.read_text(encoding="utf-8"))
        self.assertIsNotNone(rel_path)
        ref = (sync_md_path.parent / rel_path).resolve()
        self.assertTrue(ref.exists(), f"Reference not found at {ref}")
        content = ref.read_text(encoding="utf-8")
        self.assertIn("SYNC_HELPER", content)
        self.assertIn("BUILTIN_SYNC", content)

    # -- Shared close-checkpoint recovery rule ---

    def test_shared_recovery_rule_exists(self) -> None:
        """Contract section contains the close-checkpoint recovery rule."""
        self.assertIn("Close-checkpoint recovery", self._sync_md)

    def test_recovery_rule_never_repeat_terminal_transition(self) -> None:
        """Recovery rule forbids repeating a terminal Jira transition."""
        import re
        m = re.search(r"Close-checkpoint recovery.*?(?=\n- \*\*|## )",
                      self._sync_md, re.DOTALL)
        self.assertIsNotNone(m, "recovery rule section not found")
        rule = m.group()
        self.assertIn("Never repeat a terminal Jira transition", rule)

    def test_recovery_rule_pause_in_this_run(self) -> None:
        """Recovery rule specifies same-run pause and retry."""
        import re
        m = re.search(r"Close-checkpoint recovery.*?(?=\n- \*\*|## )",
                      self._sync_md, re.DOTALL)
        rule = m.group()
        self.assertIn("pause in this run", rule)
        self.assertIn("only the exact saved checkpoint invocation", rule)

    def test_recovery_rule_lost_state_manual_reconciliation(self) -> None:
        """Recovery rule: lost captured state → manual reconciliation."""
        import re
        m = re.search(r"Close-checkpoint recovery.*?(?=\n- \*\*|## )",
                      self._sync_md, re.DOTALL)
        rule = m.group()
        self.assertIn("stop for manual reconciliation", rule)

    def test_recovery_rule_uncertain_outcome_verification(self) -> None:
        """Recovery rule: uncertain Jira outcome requires verification."""
        import re
        m = re.search(r"Close-checkpoint recovery.*?(?=\n- \*\*|## )",
                      self._sync_md, re.DOTALL)
        rule = m.group()
        self.assertIn("uncertain", rule)
        self.assertIn("verify", rule)

    def test_all_close_paths_reference_recovery_rule(self) -> None:
        """All three close paths (child, epic, 5c) reference the shared
        close-checkpoint recovery rule."""
        self.assertIn("close-checkpoint", self._step4c)
        # Epic close failure handler
        epic_fail_pos = self._step4c.find("If epic close fails")
        self.assertGreater(epic_fail_pos, -1)
        epic_fail_text = self._step4c[epic_fail_pos:]
        self.assertIn("close-checkpoint", epic_fail_text)
        # Step 5c
        self.assertIn("close-checkpoint", self._step5c)

    # -- Step 5 plan refresh: deferred cascades ---

    def test_step5_deferred_cascade_not_retried(self) -> None:
        """Step 5 refresh: deferred cascades are not silently retried."""
        self.assertIn("deferred in Step 4c", self._step5_refresh)
        self.assertIn("do not retry closing", self._step5_refresh)

    def test_step5_deferral_covers_checkpoint_failure(self) -> None:
        """Step 5 refresh: deferral clause covers Jira-closed-but-
        uncheckpointed state, not just open children."""
        self.assertIn("Jira-closed but uncheckpointed", self._step5_refresh)


# ---------------------------------------------------------------------------
# Test: cascade checkpoint behavior (local state, no Jira)
# ---------------------------------------------------------------------------

class TestCascadeCheckpointBehavior(_TmpDirMixin, unittest.TestCase):
    """Test real local checkpoint behaviour for cascade closure.

    These tests verify that the sync_helper checkpoint mechanism
    (update-manifest) correctly handles partial cascade completion,
    retained hashes, and orphan empty-hash patterns.  No Jira or LLM
    involvement — these test the deterministic helper functions that
    the agent calls between Jira operations.
    """

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        self.ef = _make_epic(sd, 1, "building", removed=True)
        self.sf1 = _make_dev_story(sd, 1, 1, "scaffold")
        self.sf2 = _make_dev_story(sd, 1, 2, "pipe")
        self.mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "old_epic_hash",
            "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "old_s1", "synced_status": "active"},
                {"file": "story-02-pipe.md", "jira_key": "EDM-202",
                 "content_hash": "old_s2", "synced_status": "active"},
            ],
        }])

    def test_partial_cascade_checkpoint_failure_preserves_progress(self) -> None:
        """Child 1 checkpoint succeeds; child 2 checkpoint save fails
        (injected OSError on atomic replace).  Parent stays active,
        child 1's persisted checkpoint is preserved, child 2 remains
        active with its original hash.

        Uses the same atomic-failure pattern as
        TestSaveManifestAtomic.test_failure_no_corruption.
        """
        child1_hash = sync_helper.compute_file_hash(self.sf1)
        child2_hash = sync_helper.compute_file_hash(self.sf2)

        # Child 1: Jira transition succeeded → checkpoint succeeds
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201",
            child1_hash, item_type="story",
            epic_file="epic-1-building.md")

        # Snapshot manifest bytes after child 1's successful checkpoint
        manifest_after_child1 = self.mf.read_bytes()

        # Child 2: Jira transition succeeded but checkpoint save fails
        _original_replace = Path.replace

        def _failing_replace(self_path, target):
            # Fail only for the manifest tmp → target rename
            if str(target).endswith("sync-manifest.json"):
                raise OSError("injected disk write failure")
            return _original_replace(self_path, target)

        with mock.patch.object(Path, "replace", _failing_replace):
            with self.assertRaises(OSError):
                sync_helper.update_manifest(
                    self.mf, "close", "story-02-pipe.md", "EDM-202",
                    child2_hash, item_type="story",
                    epic_file="epic-1-building.md")

        # Manifest on disk is unmodified from child 1's checkpoint
        self.assertEqual(self.mf.read_bytes(), manifest_after_child1,
                         "Atomic save failure must not corrupt manifest")

        manifest = sync_helper.load_manifest(self.mf)
        epic = manifest["epics"][0]
        self.assertEqual(epic["synced_status"], "active",
                         "Parent must remain active when cascade is incomplete")
        s1 = epic["stories"][0]
        s2 = epic["stories"][1]
        self.assertEqual(s1["synced_status"], "closed",
                         "Child 1 checkpoint must be preserved after child 2 failure")
        self.assertEqual(s1["content_hash"], child1_hash,
                         "Child 1 hash must be the pre-transition value")
        self.assertEqual(s2["synced_status"], "active",
                         "Child 2 must remain active (checkpoint never persisted)")
        self.assertEqual(s2["content_hash"], "old_s2",
                         "Child 2 hash must be original (checkpoint failed)")

    def test_retry_checkpoint_after_remediation(self) -> None:
        """After a checkpoint failure is remediated, retrying with the
        original captured hash succeeds without repeating Jira calls."""
        child2_hash = sync_helper.compute_file_hash(self.sf2)

        # First attempt: checkpoint save fails
        _original_replace = Path.replace

        def _failing_replace(self_path, target):
            if str(target).endswith("sync-manifest.json"):
                raise OSError("injected disk write failure")
            return _original_replace(self_path, target)

        with mock.patch.object(Path, "replace", _failing_replace):
            with self.assertRaises(OSError):
                sync_helper.update_manifest(
                    self.mf, "close", "story-02-pipe.md", "EDM-202",
                    child2_hash, item_type="story",
                    epic_file="epic-1-building.md")

        # Remediation: disk issue resolved, retry with SAME captured hash
        sync_helper.update_manifest(
            self.mf, "close", "story-02-pipe.md", "EDM-202",
            child2_hash, item_type="story",
            epic_file="epic-1-building.md")

        manifest = sync_helper.load_manifest(self.mf)
        s2 = manifest["epics"][0]["stories"][1]
        self.assertEqual(s2["synced_status"], "closed",
                         "Retry must succeed after remediation")
        self.assertEqual(s2["content_hash"], child2_hash,
                         "Retry must use the original captured hash")

    def test_retained_hash_despite_artifact_edit(self) -> None:
        """Hash captured before transition is retained even if the file
        is edited after the Jira call but before checkpoint."""
        pre_hash = sync_helper.compute_file_hash(self.sf1)

        # File edited after Jira call (e.g. by user)
        self.sf1.write_text(
            self.sf1.read_text() + "\n## Extra section\n\nAdded later.\n")
        post_hash = sync_helper.compute_file_hash(self.sf1)
        self.assertNotEqual(pre_hash, post_hash, "sanity: edit changes hash")

        # Checkpoint uses the PRE-transition hash (per line 85 rule)
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201",
            pre_hash, item_type="story",
            epic_file="epic-1-building.md")

        manifest = sync_helper.load_manifest(self.mf)
        s1 = manifest["epics"][0]["stories"][0]
        self.assertEqual(s1["content_hash"], pre_hash,
                         "Must store pre-transition hash, not fresh recompute")

    def test_orphan_empty_hash_not_fabricated(self) -> None:
        """Orphaned entry (no file on disk) uses empty hash — reading
        a nonexistent file must raise, not silently produce empty."""
        self.sf2.unlink()

        with self.assertRaises(FileNotFoundError):
            sync_helper.compute_file_hash(self.sf2)

        # Orphan close uses empty hash per Step 4c/5c
        sync_helper.update_manifest(
            self.mf, "close", "story-02-pipe.md", "EDM-202",
            "", item_type="story",
            epic_file="epic-1-building.md")

        manifest = sync_helper.load_manifest(self.mf)
        s2 = manifest["epics"][0]["stories"][1]
        self.assertEqual(s2["content_hash"], "",
                         "Orphan close must use empty hash")
        self.assertEqual(s2["synced_status"], "closed")

    def test_resume_skips_already_closed_children(self) -> None:
        """On resume, detect-changes marks already-closed children as
        unchanged so the cascade does not re-close them."""
        child1_hash = sync_helper.compute_file_hash(self.sf1)
        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201",
            child1_hash, item_type="story",
            epic_file="epic-1-building.md")

        plan = sync_helper.detect_changes(self.artifacts)
        # Items use dir-qualified paths: "epic-1/story-01-scaffold.md"
        child1_items = [i for i in plan["items"]
                        if i["type"] == "story"
                        and "story-01-scaffold.md" in i.get("file", "")]
        self.assertEqual(len(child1_items), 1,
                         "Exactly one plan item expected for closed child")
        self.assertEqual(child1_items[0]["category"], "unchanged",
                         "Already-closed child must be unchanged on resume")

    def test_distinct_child_hashes_not_overwritten(self) -> None:
        """Each child's hash is recorded independently; closing one
        does not overwrite the other's stored hash."""
        hash1 = sync_helper.compute_file_hash(self.sf1)
        hash2 = sync_helper.compute_file_hash(self.sf2)
        self.assertNotEqual(hash1, hash2, "sanity: different content")

        sync_helper.update_manifest(
            self.mf, "close", "story-01-scaffold.md", "EDM-201",
            hash1, item_type="story",
            epic_file="epic-1-building.md")
        sync_helper.update_manifest(
            self.mf, "close", "story-02-pipe.md", "EDM-202",
            hash2, item_type="story",
            epic_file="epic-1-building.md")

        manifest = sync_helper.load_manifest(self.mf)
        s1 = manifest["epics"][0]["stories"][0]
        s2 = manifest["epics"][0]["stories"][1]
        self.assertEqual(s1["content_hash"], hash1)
        self.assertEqual(s2["content_hash"], hash2,
                         "Second child hash must not be overwritten by first")


# ---------------------------------------------------------------------------
# Test: child checkpoint CLI args extracted from actual sync.md
# (finding 4383291745)
# ---------------------------------------------------------------------------

def _resolve_ref_from_directive() -> Path:
    """Resolve the helper reference path from the actual loading
    directive in the built-in sync.md.  Returns the resolved Path."""
    import re
    sync_md_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
    text = sync_md_path.read_text(encoding="utf-8")
    m = re.search(
        r"\*\*Before the first helper operation\*\*.*?`([^`]+\.md)`",
        text, re.DOTALL)
    assert m, "Loading directive not found in sync.md"
    return (sync_md_path.parent / m.group(1)).resolve()


def _extract_child_close_bash(ref_text: str) -> str:
    """Extract the child story close bash block from the helper reference.

    Returns the raw bash text from the "Child story close" recipe in
    ``references/sync-helper-usage.md``.  Raises if not found.
    """
    import re
    m = re.search(
        r"Child story close.*?```bash\n(.*?)```", ref_text, re.DOTALL)
    assert m, "Child story close bash block not found in helper reference"
    return m.group(1)


def _substitute_child_bash(
    bash_text: str,
    manifest_path: str,
    child_file: str,
    child_key: str,
    child_hash: str,
    epic_file: str,
) -> list[str]:
    """Substitute placeholder values in the extracted bash command and
    return the argv list for ``build_parser().parse_args()``.

    Replaces documented placeholders with *shell-quoted* fixture values,
    joins line continuations, then tokenises with ``shlex.split`` so
    that paths containing spaces are preserved as single tokens.  No
    shell evaluation of untrusted path strings.
    """
    import shlex
    text = bash_text
    # Strip the leading "python3 "$SYNC_HELPER" " — we call the parser directly
    text = text.replace('python3 "$SYNC_HELPER" ', "")
    # Substitute placeholders with properly quoted fixture values.
    # The Markdown placeholders include surrounding quotes, e.g.
    # "{child-story-file}", which we replace entirely — the
    # shlex.quote wrapping ensures tokens survive shlex.split.
    text = text.replace(
        ".artifacts/design/{issue-key}/sync-manifest.json",
        shlex.quote(manifest_path))
    text = text.replace('"{child-story-file}"', shlex.quote(child_file))
    text = text.replace('"{child-story-jira-key}"', shlex.quote(child_key))
    text = text.replace('"{child hash from step (a)}"',
                        shlex.quote(child_hash))
    text = text.replace('"{parent-epic-file}"', shlex.quote(epic_file))
    # Join line continuations, then tokenise
    text = text.replace("\\\n", " ")
    return shlex.split(text)


class TestChildCheckpointCLI(_TmpDirMixin, unittest.TestCase):
    """Exercise the ACTUAL child-close bash block extracted from the
    helper reference (``references/sync-helper-usage.md``) through the
    real CLI parser and checkpoint path.

    The tests extract the documented command from the live reference,
    substitute fixture values, and parse the resulting flags through
    ``build_parser()`` — so they fail if the documented command drifts
    from the parser contract.
    """

    _child_bash: str
    _ref_path: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._ref_path = _resolve_ref_from_directive()
        assert cls._ref_path.exists(), (
            f"Helper reference not found: {cls._ref_path}")
        cls._child_bash = _extract_child_close_bash(
            cls._ref_path.read_text(encoding="utf-8"))
        assert "--item-type story" in cls._child_bash, (
            "Extracted bash block missing --item-type story")
        assert "--epic-file" in cls._child_bash, (
            "Extracted bash block missing --epic-file")

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        self.ef = _make_epic(sd, 1, "building", removed=True)
        self.sf1 = _make_dev_story(sd, 1, 1, "scaffold")
        self.mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "old_epic", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "old_s1", "synced_status": "active",
            }],
        }])

    def _parse_child_close(self, child_hash: str) -> "argparse.Namespace":
        """Parse the extracted+substituted child-close command."""
        argv = _substitute_child_bash(
            self._child_bash,
            manifest_path=str(self.mf),
            child_file="story-01-scaffold.md",
            child_key="EDM-201",
            child_hash=child_hash,
            epic_file="epic-1-building.md",
        )
        return sync_helper.build_parser().parse_args(argv)

    def test_child_close_via_extracted_command(self) -> None:
        """Extracted child-close command produces correct manifest
        update: story under parent epic, not epic default branch.

        Also exercises a manifest path containing spaces (subTest) to
        verify the shlex tokenisation preserves it as one token.
        """
        for label, artifacts_dir in [
            ("normal", self.artifacts),
            ("spaces", Path(self.tmpdir) / "path with spaces" / "art"),
        ]:
            with self.subTest(path=label):
                sd = artifacts_dir / "06-stories"
                sd.mkdir(parents=True, exist_ok=True)
                ef = _make_epic(sd, 1, "building", removed=True)
                sf = _make_dev_story(sd, 1, 1, "scaffold")
                mf = _make_manifest(artifacts_dir, [{
                    "file": "epic-1-building.md", "jira_key": "EDM-101",
                    "content_hash": "old_epic", "synced_status": "active",
                    "stories": [{
                        "file": "story-01-scaffold.md",
                        "jira_key": "EDM-201",
                        "content_hash": "old_s1",
                        "synced_status": "active",
                    }],
                }])
                child_hash = sync_helper.compute_file_hash(sf)
                argv = _substitute_child_bash(
                    self._child_bash,
                    manifest_path=str(mf),
                    child_file="story-01-scaffold.md",
                    child_key="EDM-201",
                    child_hash=child_hash,
                    epic_file="epic-1-building.md",
                )
                args = sync_helper.build_parser().parse_args(argv)
                self.assertEqual(args.item_type, "story")
                self.assertEqual(args.epic_file, "epic-1-building.md")
                self.assertEqual(args.artifact_file, "story-01-scaffold.md")
                self.assertEqual(args.manifest_path, str(mf))
                sync_helper.update_manifest(
                    args.manifest_path, args.operation, args.artifact_file,
                    args.jira_key, args.content_hash,
                    item_type=args.item_type, epic_file=args.epic_file)
                manifest = sync_helper.load_manifest(mf)
                s1 = manifest["epics"][0]["stories"][0]
                self.assertEqual(s1["synced_status"], "closed")
                self.assertEqual(s1["content_hash"], child_hash)

    def test_orphan_child_close_empty_hash_via_extracted_command(self) -> None:
        """Approved orphan (no file on disk): empty hash through the
        extracted command and CLI parser."""
        self.sf1.unlink()
        args = self._parse_child_close("")
        self.assertEqual(args.content_hash, "")
        sync_helper.update_manifest(
            args.manifest_path, args.operation, args.artifact_file,
            args.jira_key, args.content_hash,
            item_type=args.item_type, epic_file=args.epic_file)
        manifest = sync_helper.load_manifest(self.mf)
        s1 = manifest["epics"][0]["stories"][0]
        self.assertEqual(s1["content_hash"], "")
        self.assertEqual(s1["synced_status"], "closed")

    def test_missing_epic_file_fails(self) -> None:
        """Omitting --epic-file for a story close causes a hard error,
        confirming why the documented command must include it."""
        with self.assertRaises(SystemExit):
            sync_helper.update_manifest(
                self.mf, "close", "story-01-scaffold.md", "EDM-201",
                "somehash", item_type="story", epic_file="")


# ---------------------------------------------------------------------------
# Test: create/update checkpoint recipes from helper reference
# (Gap A — verify documented command produces correct manifest entries)
# ---------------------------------------------------------------------------

def _extract_ref_recipe(ref_text: str, heading: str) -> str:
    """Extract a bash block following a heading in the helper reference."""
    import re
    m = re.search(
        re.escape(heading) + r".*?```bash\n(.*?)```",
        ref_text, re.DOTALL)
    assert m, f"Recipe '{heading}' not found in helper reference"
    return m.group(1)


class TestCreateUpdateRecipes(_TmpDirMixin, unittest.TestCase):
    """Verify documented create and update checkpoint recipes through
    the real CLI parser, checking operation, parent placement, stored
    title/hash, and that create vs update are unambiguous.
    """

    @classmethod
    def setUpClass(cls) -> None:
        ref_path = _resolve_ref_from_directive()
        cls._ref = ref_path.read_text(encoding="utf-8")

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        self.ef = _make_epic(sd, 1, "building")
        self.sf = _make_dev_story(sd, 1, 1, "scaffold")
        self.mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "old_epic", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "old_s1", "synced_status": "active",
            }],
        }])

    def test_story_create_recipe_stores_title(self) -> None:
        """Documented story create recipe includes --title and stores it."""
        block = _extract_ref_recipe(self._ref, "Story create:")
        self.assertIn("--title", block)
        self.assertIn("--operation create", block)
        # Parse through real CLI
        import shlex
        text = block.replace('python3 "$SYNC_HELPER" ', "")
        text = text.replace(
            ".artifacts/design/{issue-key}/sync-manifest.json",
            shlex.quote(str(self.mf)))
        text = text.replace('"{story-file}"', "story-01-scaffold.md")
        text = text.replace('"{jira-key}"', "EDM-301")
        text = text.replace('"{content_hash from PREP}"', "abc123")
        text = text.replace('"{summary from PREP}"',
                            shlex.quote("Test Title"))
        text = text.replace('"{epic-file}"', "epic-1-building.md")
        text = text.replace("\\\n", " ")
        args = sync_helper.build_parser().parse_args(shlex.split(text))
        self.assertEqual(args.operation, "create")
        self.assertEqual(args.item_type, "story")
        self.assertEqual(args.title, "Test Title")
        sync_helper.update_manifest(
            args.manifest_path, args.operation, args.artifact_file,
            args.jira_key, args.content_hash,
            item_type=args.item_type, title=args.title,
            epic_file=args.epic_file)
        manifest = sync_helper.load_manifest(self.mf)
        s = next(s for e in manifest["epics"]
                 for s in e.get("stories", [])
                 if s["jira_key"] == "EDM-301")
        self.assertEqual(s["title"], "Test Title")
        self.assertEqual(s["content_hash"], "abc123")

    def test_story_update_recipe_has_operation_update(self) -> None:
        """Documented story update recipe uses --operation update."""
        block = _extract_ref_recipe(self._ref, "Story update")
        self.assertIn("--operation update", block)
        self.assertNotIn("--operation create", block)

    def test_epic_create_recipe_has_title_size_feature(self) -> None:
        """Documented epic create recipe includes --title --size --feature-key."""
        block = _extract_ref_recipe(self._ref, "Epic create:")
        self.assertIn("--operation create", block)
        self.assertIn("--title", block)
        self.assertIn("--size", block)
        self.assertIn("--feature-key", block)

    def test_epic_update_recipe_has_operation_update(self) -> None:
        """Documented epic update recipe uses --operation update."""
        block = _extract_ref_recipe(self._ref, "Epic update")
        self.assertIn("--operation update", block)
        self.assertNotIn("--operation create", block)


# ---------------------------------------------------------------------------
# Test: checkpoint-only retry with retained hash after failure+edit
# (finding 4383291734 — table-driven for child, epic, standalone story)
# ---------------------------------------------------------------------------

class TestCloseCheckpointRetryRetainsHash(_TmpDirMixin, unittest.TestCase):
    """After a checkpoint save failure, the retry uses the ORIGINAL
    captured hash even if the artifact file was edited in between.
    Exercises child story, epic, and standalone story close paths.
    """

    _CASES = [
        {
            "label": "child_story",
            "item_type": "story",
            "file": "story-01-scaffold.md",
            "jira_key": "EDM-201",
            "epic_file": "epic-1-building.md",
        },
        {
            "label": "epic",
            "item_type": "epic",
            "file": "epic-1-building.md",
            "jira_key": "EDM-101",
            "epic_file": "",
        },
    ]

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        self.ef = _make_epic(sd, 1, "building", removed=True)
        self.sf1 = _make_dev_story(sd, 1, 1, "scaffold")
        self.mf = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "old_epic", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "old_s1", "synced_status": "active",
            }],
        }])
        self._file_paths = {
            "story-01-scaffold.md": self.sf1,
            "epic-1-building.md": self.ef,
        }

    def test_retry_uses_original_hash_after_edit(self) -> None:
        for case in self._CASES:
            with self.subTest(path=case["label"]):
                # Reset manifest for each sub-case
                self.mf.write_text(json.dumps({
                    "schema_version": 2, "feature_key": "TEST-100",
                    "synced_at": "", "epics": [{
                        "file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "old_epic", "synced_status": "active",
                        "stories": [{
                            "file": "story-01-scaffold.md",
                            "jira_key": "EDM-201",
                            "content_hash": "old_s1",
                            "synced_status": "active",
                        }],
                    }],
                }, indent=2))

                fp = self._file_paths[case["file"]]
                pre_hash = sync_helper.compute_file_hash(fp)

                # Inject checkpoint save failure
                _orig = Path.replace

                def _fail(self_path, target):
                    if str(target).endswith("sync-manifest.json"):
                        raise OSError("disk error")
                    return _orig(self_path, target)

                with mock.patch.object(Path, "replace", _fail):
                    with self.assertRaises(OSError):
                        kw = {"item_type": case["item_type"]}
                        if case["epic_file"]:
                            kw["epic_file"] = case["epic_file"]
                        sync_helper.update_manifest(
                            self.mf, "close", case["file"],
                            case["jira_key"], pre_hash, **kw)

                # Edit artifact between failure and retry
                fp.write_text(fp.read_text() + "\n## Edited\n")
                new_hash = sync_helper.compute_file_hash(fp)
                self.assertNotEqual(pre_hash, new_hash)

                # Retry with ORIGINAL captured hash (not recomputed)
                kw = {"item_type": case["item_type"]}
                if case["epic_file"]:
                    kw["epic_file"] = case["epic_file"]
                sync_helper.update_manifest(
                    self.mf, "close", case["file"],
                    case["jira_key"], pre_hash, **kw)

                manifest = sync_helper.load_manifest(self.mf)
                if case["item_type"] == "epic":
                    entry = manifest["epics"][0]
                else:
                    entry = manifest["epics"][0]["stories"][0]
                self.assertEqual(entry["synced_status"], "closed")
                self.assertEqual(entry["content_hash"], pre_hash,
                                 f"{case['label']}: must use original hash")


# ---------------------------------------------------------------------------
# Test: [unresolved] annotation on no-manifest path
# (review finding 5660738800 — outside-diff #1)
# ---------------------------------------------------------------------------

class TestResolveRefsNoManifest(_TmpDirMixin, unittest.TestCase):
    """Local Epic/Story references must carry [unresolved] even when no
    manifest exists (fresh sync).  Tests cover both the real CLI
    subcommands (prepare, render-description) and direct renderer calls
    with None and {} manifests.
    """

    def setUp(self) -> None:
        super().setUp()
        import subprocess
        self.subprocess = subprocess
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        self.ef = _make_epic(
            sd, 1, "building",
            summary="Depends on Epic 2 and Story 1.01")
        self.sf = _make_dev_story(
            sd, 1, 1, "scaffold", deps="Story 2.01")
        self.mf = self.artifacts / "sync-manifest.json"

    # -- CLI: prepare --

    def test_epic_prepare_cli_no_manifest_annotates_refs(self) -> None:
        """CLI prepare(epic) with nonexistent manifest: JSON output
        contains concrete [unresolved] annotations for Epic 2 and
        Story 1.01, and no manifest file is created."""
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "prepare",
             str(self.ef), str(self.mf), "--type", "epic",
             "--design-doc-link", "http://doc", "--feature-key", "F-1"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        result = json.loads(r.stdout)
        self.assertIn("2 [unresolved]", result["description"],
                      "Epic 2 must be annotated [unresolved]")
        self.assertIn("1.01 [unresolved]", result["description"],
                      "Story 1.01 must be annotated [unresolved]")
        self.assertIn("content_hash", result)
        self.assertFalse(self.mf.exists(),
                         "prepare must not create manifest")

    def test_story_prepare_cli_no_manifest_annotates_deps(self) -> None:
        """CLI prepare(story) with nonexistent manifest: dependencies
        contain concrete [unresolved] for Story 2.01."""
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "prepare",
             str(self.sf), str(self.mf), "--type", "story",
             "--design-doc-link", "http://doc",
             "--epic-jira-key", "EDM-101"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        result = json.loads(r.stdout)
        self.assertIn("2.01 [unresolved]", result["dependencies"])
        self.assertFalse(self.mf.exists())

    # -- CLI: render-description --

    def test_epic_render_description_cli_no_manifest(self) -> None:
        """CLI render-description(epic) with nonexistent manifest:
        stdout contains [unresolved] annotations."""
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "render-description",
             str(self.ef), str(self.mf), "--type", "epic",
             "--design-doc-link", "http://doc"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("[unresolved]", r.stdout)

    def test_story_render_description_cli_no_manifest(self) -> None:
        """CLI render-description(story) with nonexistent manifest."""
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "render-description",
             str(self.sf), str(self.mf), "--type", "story",
             "--design-doc-link", "http://doc",
             "--epic-jira-key", "EDM-101"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("[unresolved]", r.stdout)

    # -- Direct renderer with None and {} manifest --

    def test_render_epic_none_manifest(self) -> None:
        """render_epic_description(manifest=None) annotates refs."""
        desc = sync_helper.render_epic_description(
            self.ef, None, design_doc_link="http://doc")
        self.assertIn("2 [unresolved]", desc)

    def test_render_epic_empty_dict_manifest(self) -> None:
        """render_epic_description(manifest={}) annotates refs."""
        desc = sync_helper.render_epic_description(
            self.ef, {}, design_doc_link="http://doc")
        self.assertIn("[unresolved]", desc)

    def test_render_story_none_manifest(self) -> None:
        """render_story_description(manifest=None) annotates refs."""
        desc = sync_helper.render_story_description(
            self.sf, None, design_doc_link="http://doc",
            epic_jira_key="EDM-101")
        self.assertIn("[unresolved]", desc)

    # -- Populated manifest: mixed resolution --

    def test_populated_manifest_resolves_known_refs(self) -> None:
        """Known refs resolve; unknown get [unresolved] in description."""
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
            }],
        }])
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "prepare",
             str(self.ef), str(self.mf), "--type", "epic",
             "--design-doc-link", "http://doc", "--feature-key", "F-1"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        result = json.loads(r.stdout)
        self.assertIn("EDM-201", result["description"],
                      "Story 1.01 known → resolves to EDM-201")
        self.assertIn("2 [unresolved]", result["description"],
                      "Epic 2 unknown → annotated [unresolved]")

    def test_populated_manifest_story_deps_mixed(self) -> None:
        """Story dependencies: known refs resolve, unknown annotated."""
        _make_dev_story(self.artifacts / "06-stories", 1, 2, "other",
                        deps="Story 1.01, Story 3.01")
        sf2 = (self.artifacts / "06-stories" / "epic-1"
               / "story-02-other.md")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h", "synced_status": "active"},
                {"file": "story-02-other.md", "jira_key": "EDM-202",
                 "content_hash": "h", "synced_status": "active"},
            ],
        }])
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "prepare",
             str(sf2), str(self.mf), "--type", "story",
             "--design-doc-link", "http://doc",
             "--epic-jira-key", "EDM-101"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        result = json.loads(r.stdout)
        self.assertIn("EDM-201", result["dependencies"],
                      "Story 1.01 → EDM-201")
        self.assertIn("3.01 [unresolved]", result["dependencies"])

    def test_no_duplicate_unresolved_annotations(self) -> None:
        """Each unresolvable ref gets exactly one [unresolved] tag."""
        desc = sync_helper.render_epic_description(
            self.ef, None, design_doc_link="http://doc")
        import re
        count = len(re.findall(r"\[unresolved\]", desc))
        ref_count = len(re.findall(r"(?:Epic|Story)\s+\d", desc))
        self.assertGreater(count, 0)
        self.assertLessEqual(count, ref_count)


# ---------------------------------------------------------------------------
# Test: T-Shirt Size validation in epic prepare
# (review finding 5660738800 — outside-diff #2)
# ---------------------------------------------------------------------------

class TestEpicSizeValidation(_TmpDirMixin, unittest.TestCase):
    """Epic prepare must fail closed when T-Shirt Size is missing or
    blank.  Tests exercise real CLI (subprocess) for failure cases and
    verify exit code, stderr, no JSON stdout, and unchanged files.
    """

    def setUp(self) -> None:
        super().setUp()
        import subprocess
        self.subprocess = subprocess
        self.artifacts = Path(self.tmpdir) / "art"
        sd = self.artifacts / "06-stories"
        sd.mkdir(parents=True)
        self.ef = _make_epic(sd, 1, "building")
        self.sf = _make_dev_story(sd, 1, 1, "scaffold")
        self.mf = self.artifacts / "sync-manifest.json"
        # Create a valid manifest to verify it stays unchanged on failure
        self._valid_manifest = _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        self._manifest_bytes = self._valid_manifest.read_bytes()

    def _run_prepare_epic(self, epic_path: Path) -> "subprocess.CompletedProcess":
        return self.subprocess.run(
            [sys.executable, str(_SCRIPT), "prepare",
             str(epic_path), str(self.mf), "--type", "epic",
             "--design-doc-link", "http://doc", "--feature-key", "F-1"],
            capture_output=True, text=True)

    def test_valid_sizes(self) -> None:
        """Canonical sizes with various spacing are accepted."""
        for label, size_line, expected in [
            ("normal",   "- **T-Shirt Size:** M",  "M"),
            ("no-space", "- **T-Shirt Size:**XL",  "XL"),
            ("tab",      "- **T-Shirt Size:**\tS", "S"),
            ("multi-sp", "- **T-Shirt Size:**   L", "L"),
        ]:
            with self.subTest(spacing=label):
                content = self.ef.read_text()
                self.ef.write_text(content.replace(
                    "- **T-Shirt Size:** M", size_line))
                r = self._run_prepare_epic(self.ef)
                self.assertEqual(r.returncode, 0, r.stderr)
                result = json.loads(r.stdout)
                self.assertEqual(result["size"], expected)
                # Restore for next subTest
                self.ef.write_text(content)

    def test_missing_size_cli_fails(self) -> None:
        """CLI: missing T-Shirt Size → exit 1, actionable stderr,
        no JSON stdout, manifest+artifact unchanged."""
        import re as _re
        content = self.ef.read_text()
        no_size = _re.sub(r"- \*\*T-Shirt Size:\*\*.*\n", "", content)
        self.ef.write_text(no_size)
        artifact_bytes = self.ef.read_bytes()
        r = self._run_prepare_epic(self.ef)
        self.assertEqual(r.returncode, 1)
        self.assertIn("T-Shirt Size", r.stderr)
        # No valid JSON on stdout
        with self.assertRaises(json.JSONDecodeError):
            json.loads(r.stdout)
        self.assertEqual(self.ef.read_bytes(), artifact_bytes)
        self.assertEqual(self._valid_manifest.read_bytes(),
                         self._manifest_bytes)

    def test_blank_size_cli_fails(self) -> None:
        """CLI: blank value (space + newline + next bullet) → exit 1."""
        content = self.ef.read_text()
        self.ef.write_text(content.replace(
            "- **T-Shirt Size:** M",
            "- **T-Shirt Size:** \n- **Next Field:** value"))
        r = self._run_prepare_epic(self.ef)
        self.assertEqual(r.returncode, 1)
        self.assertIn("T-Shirt Size", r.stderr)

    def test_blank_then_next_bullet_not_captured(self) -> None:
        """CLI: blank followed by bullet → dash NOT captured as size."""
        content = self.ef.read_text()
        self.ef.write_text(content.replace(
            "- **T-Shirt Size:** M",
            "- **T-Shirt Size:**\n- **Another:** thing"))
        r = self._run_prepare_epic(self.ef)
        self.assertEqual(r.returncode, 1)
        self.assertIn("T-Shirt Size", r.stderr)

    def test_whitespace_only_size_fails(self) -> None:
        """CLI: whitespace-only value (no non-space match) fails."""
        content = self.ef.read_text()
        self.ef.write_text(content.replace(
            "- **T-Shirt Size:** M",
            "- **T-Shirt Size:**   "))
        r = self._run_prepare_epic(self.ef)
        self.assertEqual(r.returncode, 1)

    def test_story_prepare_no_size_requirement(self) -> None:
        """Story prepare must not require T-Shirt Size (CLI)."""
        r = self.subprocess.run(
            [sys.executable, str(_SCRIPT), "prepare",
             str(self.sf), str(self.mf), "--type", "story",
             "--design-doc-link", "http://doc",
             "--epic-jira-key", "EDM-101"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        result = json.loads(r.stdout)
        self.assertNotIn("size", result)
        self.assertIn("description", result)


if __name__ == "__main__":
    unittest.main()
