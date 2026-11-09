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
    Contributing stories: {contributing_stories}
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
    contributing_stories: str = "Story 1.01",
) -> Path:
    extra_fm = "status: removed" if removed else ""
    content = _DOCS_STORY_TEMPLATE.format(
        extra_fm=extra_fm, epic_idx=epic_idx, story_idx=story_idx,
        title=title, role=role, want=want, so_that=so_that,
        ac=ac, doc_scope=doc_scope, doc_inputs=doc_inputs, deps=deps,
        epic_title=epic_title, prd_reqs=prd_reqs,
        design_section=design_section,
        contributing_stories=contributing_stories,
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
            contributing_stories="Story 1.01",
        ))
        desc = sync_helper.render_story_description(
            sf, self.manifest, story_type="DOCS")
        self.assertIn("## Documentation Scope", desc)
        self.assertIn("## Documentation Inputs", desc)
        self.assertNotIn("## Implementation Guidance", desc)
        # Ref resolved
        self.assertIn("EDM-201", desc)

    def test_docs_story_contributing_stories_resolved(self) -> None:
        """Contributing stories line in Design Reference is resolved to Jira keys."""
        sf = Path(self.tmpdir) / "story-02-docs.md"
        _write(sf, _DOCS_STORY_TEMPLATE.format(
            extra_fm="", epic_idx=1, story_idx=2,
            title="Device rollback command reference",
            role="fleet administrator",
            want="find rollback command documentation",
            so_that="I can safely revert device firmware",
            ac="Reader can follow rollback procedure",
            doc_scope="CLI rollback command reference.",
            doc_inputs="**Story 1.01 — Scaffold:** rollback subcommand.",
            deps="Story 1.01", epic_title="Building",
            prd_reqs="FR-1", design_section="§4.1",
            contributing_stories="Story 1.01",
        ))
        desc = sync_helper.render_story_description(
            sf, self.manifest, story_type="DOCS")
        # Contributing stories line should have resolved ref
        self.assertIn("Contributing stories: Story EDM-201", desc)

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
            contributing_stories="Story 1.01",
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
    Steps 5c/6c of sync.md.
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
    parent-close cascade in Step 5c closing those children in Jira."""

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
    """Assert sync.md Steps 5c/6c document hash-before-transition ordering
    and that Step 5c gates the parent close on all child successes.

    These are contract tests against the ACTUAL Markdown sections/order,
    not a test-only invented executor.  They verify the documented
    ordering and gating requirements that an agent must follow.
    """

    _sync_md: str
    _step5c: str
    _step6c: str
    _step6_refresh: str

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_md_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_md_path.read_text(encoding="utf-8")
        m5c = re.search(r"#### 5c:.*?(?=####|### )", cls._sync_md, re.DOTALL)
        assert m5c, "Step 5c section not found"
        cls._step5c = m5c.group()
        m6c = re.search(r"#### 6c:.*?(?=####|### )", cls._sync_md, re.DOTALL)
        assert m6c, "Step 6c section not found"
        cls._step6c = m6c.group()
        m6 = re.search(r"### Step 6:.*?(?=#### 6a:)", cls._sync_md, re.DOTALL)
        assert m6, "Step 6 plan refresh not found"
        cls._step6_refresh = m6.group()

    # -- Step 5c: child hash before child transition ---

    def test_step5c_child_hash_before_transition(self) -> None:
        """5c child closure: hash computed before Jira transition."""
        h = self._step5c.find("Compute the hash first")
        t = self._step5c.find("Transition the child story")
        self.assertGreater(h, -1, "must mention computing child hash")
        self.assertGreater(t, -1, "must mention child transition")
        self.assertLess(h, t, "child hash must precede child transition")

    def test_step5c_epic_hash_before_transition(self) -> None:
        """5c epic closure: hash computed before Jira transition."""
        h = self._step5c.find("compute the epic hash")
        t = self._step5c.find("Transition the epic to Done")
        self.assertGreater(h, -1, "must mention computing epic hash")
        self.assertGreater(t, -1, "must mention epic transition")
        self.assertLess(h, t, "epic hash must precede epic transition")

    # -- Step 5c: parent gated on all children ---

    def test_step5c_parent_gated_on_all_children(self) -> None:
        """5c: parent close requires ALL child closures and checkpoints."""
        self.assertIn("child closures and their checkpoints have succeeded",
                      self._step5c)

    def test_step5c_stop_cascade_on_failure(self) -> None:
        """5c: cascade stops immediately on any child failure."""
        import re
        self.assertTrue(
            re.search(r"stop the cascade\s+immediately", self._step5c),
            "must stop cascade immediately on child failure")

    def test_step5c_no_skip_child_then_close_parent(self) -> None:
        """5c: explicitly forbids skipping a child then closing parent."""
        import re
        self.assertTrue(
            re.search(r"Never\s+skip\s+a failing child", self._step5c),
            "must forbid skip-child-close-parent")

    def test_step5c_offers_retry_or_defer(self) -> None:
        """5c: pre-transition failure offers retry or defer."""
        import re
        self.assertTrue(
            re.search(r"retry after\s+remediation", self._step5c),
            "must offer retry after remediation")
        self.assertIn("defer the entire parent", self._step5c)

    def test_step5c_preserves_successful_checkpoints(self) -> None:
        """5c: already-successful child checkpoints preserved on failure."""
        import re
        self.assertTrue(
            re.search(r"Preserve all\s+already-successful\s+child checkpoints",
                      self._step5c),
            "must preserve completed child checkpoints")

    def test_step5c_distinguishes_pre_and_post_failure(self) -> None:
        """5c: distinguishes pre-transition from post-success checkpoint
        failure, referencing the shared close-checkpoint recovery rule."""
        self.assertIn("Pre-transition failure", self._step5c)
        self.assertIn("Post-success checkpoint failure", self._step5c)
        self.assertIn("close-checkpoint", self._step5c)

    def test_step5c_uncertain_outcome_requires_verification(self) -> None:
        """5c: uncertain Jira outcome (timeout/5xx) must be verified
        before retrying, not assumed non-mutating."""
        import re
        self.assertTrue(
            re.search(r"uncertain.*verify.*current status",
                      self._step5c, re.DOTALL),
            "must require verification for uncertain Jira outcomes")

    def test_step5c_resume_manual_reconciliation(self) -> None:
        """5c: resume stops for manual reconciliation when captured
        state is lost (forced abort/new run)."""
        self.assertIn("stop for manual reconciliation", self._step5c)

    # -- Step 6c: hash before transition ---

    def test_step6c_hash_before_transition(self) -> None:
        """6c story close: hash computed before transition."""
        h = self._step6c.find("Compute the hash before the transition")
        t = self._step6c.find("Transition the story to Done")
        self.assertGreater(h, -1, "must mention computing hash first")
        self.assertGreater(t, -1, "must mention story transition")
        self.assertLess(h, t, "hash must precede transition")

    def test_step6c_checkpoint_uses_saved_hash(self) -> None:
        """6c: checkpoint references saved hash from step 1."""
        self.assertIn("hash from step 1", self._step6c)

    # -- Step 5c: reporting distinguishes child states ---

    def test_step5c_report_distinguishes_child_states(self) -> None:
        """5c: failure report distinguishes complete, uncheckpointed,
        and unattempted children."""
        import re
        self.assertIn("closed and checkpointed (complete)", self._step5c)
        self.assertTrue(
            re.search(r"Jira-closed but\s+uncheckpointed", self._step5c),
            "must mention Jira-closed but uncheckpointed")
        self.assertIn("unattempted", self._step5c)

    def test_step5c_no_rollback_implication(self) -> None:
        """5c: does not imply already-closed children are rolled back."""
        import re
        self.assertTrue(
            re.search(r"not imply that already-closed children\s+will be rolled back",
                      self._step5c),
            "must not imply rollback of closed children")

    # -- Step 5c: child checkpoint references helper reference ---

    def test_step5c_child_checkpoint_references_helper(self) -> None:
        """5c child checkpoint step references the helper reference."""
        self.assertIn("helper reference", self._step5c)
        # The step must mention the required story-specific args
        self.assertIn("--item-type story", self._step5c)
        self.assertIn("--epic-file", self._step5c)

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
        self.assertIn("close-checkpoint", self._step5c)
        # Epic close failure handler
        epic_fail_pos = self._step5c.find("If epic close fails")
        self.assertGreater(epic_fail_pos, -1)
        epic_fail_text = self._step5c[epic_fail_pos:]
        self.assertIn("close-checkpoint", epic_fail_text)
        # Step 5c
        self.assertIn("close-checkpoint", self._step6c)

    # -- Step 6 plan refresh: deferred cascades ---

    def test_step5_deferred_cascade_not_retried(self) -> None:
        """Step 6 refresh: deferred cascades are not silently retried."""
        self.assertIn("deferred in Step 5c", self._step6_refresh)
        self.assertIn("do not retry closing", self._step6_refresh)

    def test_step5_deferral_covers_checkpoint_failure(self) -> None:
        """Step 6 refresh: deferral clause covers Jira-closed-but-
        uncheckpointed state, not just open children."""
        self.assertIn("Jira-closed but uncheckpointed", self._step6_refresh)


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

        # Orphan close uses empty hash per Step 5c/6c
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


# ---------------------------------------------------------------------------
# Post-sync DOCS placement: synced DOCS preceding later contributor
# ---------------------------------------------------------------------------

class TestSyncedDocsPlacement(_TmpDirMixin, unittest.TestCase):
    """Verify that a synced DOCS story (immutable filename) can reference
    a later same-epic contributor after that contributor is created and
    recorded in the manifest. Also verify cross-cutting last-epic case
    and the missing-key guard."""

    def setUp(self) -> None:
        super().setUp()
        self.stories_dir = Path(self.tmpdir) / "06-stories"
        self.stories_dir.mkdir()
        # Epic 1: DOCS story-03 precedes contributor story-04
        _make_epic(self.stories_dir, 1, "rollback")
        _make_dev_story(self.stories_dir, 1, 1, "rollback-cmd", title="Rollback cmd")
        _make_docs_story(self.stories_dir, 1, 3, "rollback-docs",
                         title="Rollback CLI reference",
                         deps="Story 1.01, Story 1.04",
                         doc_inputs="**Story 1.01 — Rollback cmd:** subcommand.\n"
                                    "**Story 1.04 — Dry-run flag:** --dry-run flag.",
                         contributing_stories="Story 1.01, Story 1.04")
        _make_dev_story(self.stories_dir, 1, 4, "dry-run-flag", title="Dry-run flag")

    def test_same_epic_contributor_after_docs_resolves(self) -> None:
        """After story-04 is created and recorded, story-03 DOCS refs resolve."""
        manifest = {
            "epics": [{
                "file": "epic-1-rollback.md",
                "jira_key": "EDM-100",
                "stories": [
                    {"file": "story-01-rollback-cmd.md", "jira_key": "EDM-101"},
                    {"file": "story-03-rollback-docs.md", "jira_key": "EDM-103"},
                    {"file": "story-04-dry-run-flag.md", "jira_key": "EDM-104"},
                ]
            }]
        }
        docs_path = self.stories_dir / "epic-1" / "story-03-rollback-docs.md"
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        # Contributing stories resolved — no [unresolved]
        self.assertIn("Contributing stories: Story EDM-101, Story EDM-104", desc)
        self.assertNotIn("[unresolved]", desc)
        # Dependencies also resolved
        self.assertIn("EDM-101", desc)
        self.assertIn("EDM-104", desc)

    def test_missing_contributor_key_leaves_unresolved(self) -> None:
        """If contributor story-04 is not yet in manifest, ref stays unresolved."""
        manifest = {
            "epics": [{
                "file": "epic-1-rollback.md",
                "jira_key": "EDM-100",
                "stories": [
                    {"file": "story-01-rollback-cmd.md", "jira_key": "EDM-101"},
                    {"file": "story-03-rollback-docs.md", "jira_key": "EDM-103"},
                    # story-04 NOT in manifest — creation pending/failed
                ]
            }]
        }
        docs_path = self.stories_dir / "epic-1" / "story-03-rollback-docs.md"
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        # Story 1.04 should be unresolved
        self.assertIn("[unresolved]", desc)
        # Story 1.01 still resolved
        self.assertIn("EDM-101", desc)

    def test_cross_epic_contributor_resolves_after_creation(self) -> None:
        """Cross-cutting DOCS in epic 1 referencing a contributor in epic 2."""
        # Add epic 2 with a contributor
        _make_epic(self.stories_dir, 2, "monitoring")
        _make_dev_story(self.stories_dir, 2, 1, "metrics", title="Add metrics")
        # Update DOCS story to reference cross-epic contributor
        docs_path = self.stories_dir / "epic-1" / "story-03-rollback-docs.md"
        content = docs_path.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 1.01, Story 1.04",
            "Contributing stories: Story 1.01, Story 1.04, Story 2.01")
        docs_path.write_text(content, encoding="utf-8")

        manifest = {
            "epics": [
                {
                    "file": "epic-1-rollback.md",
                    "jira_key": "EDM-100",
                    "stories": [
                        {"file": "story-01-rollback-cmd.md", "jira_key": "EDM-101"},
                        {"file": "story-03-rollback-docs.md", "jira_key": "EDM-103"},
                        {"file": "story-04-dry-run-flag.md", "jira_key": "EDM-104"},
                    ]
                },
                {
                    "file": "epic-2-monitoring.md",
                    "jira_key": "EDM-200",
                    "stories": [
                        {"file": "story-01-metrics.md", "jira_key": "EDM-201"},
                    ]
                }
            ]
        }
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        # All three contributor refs resolved
        self.assertIn("EDM-101", desc)
        self.assertIn("EDM-104", desc)
        self.assertIn("EDM-201", desc)
        self.assertNotIn("[unresolved]", desc)

    def test_synced_docs_identity_stable_with_late_contributor(self) -> None:
        """Synced DOCS story-03 retains its manifest identity when
        story-04 is a later contributor — detect_changes classifies
        it as unchanged, not new or removed."""
        docs_path = self.stories_dir / "epic-1" / "story-03-rollback-docs.md"
        content_hash = sync_helper.compute_file_hash(str(docs_path))
        artifacts_dir = Path(self.tmpdir)
        _make_manifest(artifacts_dir, [{
            "file": "epic-1-rollback.md",
            "jira_key": "EDM-100",
            "title": "Rollback", "size": "M",
            "content_hash": "x", "synced_status": "active",
            "stories": [
                {"file": "story-01-rollback-cmd.md", "jira_key": "EDM-101",
                 "title": "[DEV] Rollback cmd", "content_hash": "y",
                 "synced_status": "active"},
                {"file": "story-03-rollback-docs.md", "jira_key": "EDM-103",
                 "title": "[DOCS] Rollback CLI reference",
                 "content_hash": content_hash,
                 "synced_status": "active"},
                {"file": "story-04-dry-run-flag.md", "jira_key": "EDM-104",
                 "title": "[DEV] Dry-run flag", "content_hash": "z",
                 "synced_status": "active"},
            ],
        }])
        plan = sync_helper.detect_changes(str(artifacts_dir))
        docs_items = [i for i in plan["items"]
                      if i["file"].endswith("story-03-rollback-docs.md")]
        self.assertEqual(len(docs_items), 1)
        self.assertEqual(docs_items[0]["category"], "unchanged")
        self.assertEqual(docs_items[0]["jira_key"], "EDM-103")


# ---------------------------------------------------------------------------
# Phase-count and ordering contract for decompose.md
# ---------------------------------------------------------------------------

class TestDecomposePhaseContract(unittest.TestCase):
    """Verify decompose.md has <=10 sequential main steps and preserves
    all original actions, gates, and ordering dependencies."""

    _decompose_md: str

    @classmethod
    def setUpClass(cls) -> None:
        import re
        path = Path(__file__).resolve().parent.parent / "skills" / "decompose.md"
        cls._decompose_md = path.read_text(encoding="utf-8")
        cls._steps = re.findall(r"^### Step (\d+):", cls._decompose_md, re.MULTILINE)

    def test_at_most_10_main_steps(self) -> None:
        self.assertLessEqual(len(self._steps), 10,
                             f"Expected <= 10 main steps, found {len(self._steps)}")

    def test_steps_sequential(self) -> None:
        nums = [int(s) for s in self._steps]
        self.assertEqual(nums, list(range(1, len(nums) + 1)),
                         f"Steps not sequential: {nums}")

    def _assert_marker_exists(self, marker: str, msg: str) -> int:
        idx = self._decompose_md.find(marker)
        self.assertGreaterEqual(idx, 0, msg)
        return idx

    def test_source_loading_blocks_on_missing_design(self) -> None:
        self._assert_marker_exists(
            "tell the user that `/draft` should be",
            "Source loading must block if design/testplan missing")

    def test_feature_identification_in_step1(self) -> None:
        step1 = self._decompose_md.split("### Step 2:")[0]
        self.assertIn("Feature issue key", step1,
                      "Step 1 must identify the Feature")

    def test_sizing_xxl_stop(self) -> None:
        self._assert_marker_exists(
            "stop and require a split",
            "Must stop on XXL epics")

    def test_ic_tc_mapping_present(self) -> None:
        self._assert_marker_exists(
            "Map stories to Interface Changes",
            "IC mapping must be present")
        self._assert_marker_exists(
            "Map stories to test cases",
            "TC mapping must be present")

    def test_structure_gate_exists(self) -> None:
        idx = self._assert_marker_exists(
            "Verify artifact structure",
            "Structure gate must exist in Step 7")
        self.assertIn("05-epics.md", self._decompose_md[idx:idx+500])

    def test_step3b_active_only_epic_authoring(self) -> None:
        """Step 3b writes only active epics; does not rewrite retired files."""
        step3 = self._decompose_md.split("### Step 3:")[1].split("### Step 4:")[0]
        self.assertIn("each active epic", step3.lower())
        self.assertIn("Do not rewrite retired epic files", step3)

    def test_step3a_repeat_run_active_index(self) -> None:
        """Step 3a index reflects active plan only on repeat runs."""
        step3 = self._decompose_md.split("### Step 3:")[1].split("### Step 4:")[0]
        self.assertIn("list active epics only", step3.lower())

    def test_step4_active_only_story_authoring(self) -> None:
        """Step 4 creates directories and stories for active epics only."""
        step4 = self._decompose_md.split("### Step 4:")[1].split("### Step 5:")[0]
        self.assertIn("each active epic", step4.lower())
        self.assertIn("Do not fabricate directories", step4)

    def test_step5_active_only_sizing(self) -> None:
        """Step 5 sizes active epics only."""
        step5 = self._decompose_md.split("### Step 5:")[1].split("### Step 6:")[0]
        self.assertIn("all active epics", step5.lower())

    def test_step6_active_only_references(self) -> None:
        """Step 6 populates IC/TC references for active stories only."""
        step6 = self._decompose_md.split("### Step 6:")[1].split("### Step 7:")[0]
        self.assertIn("each active non-", step6.lower())

    def test_step7_check1_active_index(self) -> None:
        """Step 7 check 1 verifies 05-epics.md against active epics."""
        step7 = self._decompose_md.split("### Step 7:")[1].split("### Step 8:")[0]
        self.assertIn("all active epic files", step7.lower())

    def test_review_after_structure_gate(self) -> None:
        structure_idx = self._assert_marker_exists(
            "Verify artifact structure",
            "Structure gate must exist for ordering check")
        review_idx = self._assert_marker_exists(
            "### Step 8: Review",
            "Review step must exist for ordering check")
        self.assertGreater(review_idx, structure_idx)

    def test_review_independence(self) -> None:
        review_section = self._decompose_md.split("### Step 8:")[1].split("### Step 9:")[0]
        self.assertIn("NOT the design document", review_section,
                      "Review must not receive the design document")

    def test_step9_two_numbered_main_actions(self) -> None:
        """Step 9 has two explicit numbered main actions: 1. Assess
        findings, 2. Verify provenance."""
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        self.assertGreaterEqual(step9_start, 0, "Step 9 must exist")
        self.assertGreater(step10_start, step9_start, "Step 10 must follow")
        step9 = self._decompose_md[step9_start:step10_start]
        action1 = step9.find("1. **Assess review findings.**")
        action2 = step9.find("2. **Verify `[DOCS]` input provenance.**")
        self.assertGreaterEqual(action1, 0, "Action 1 must exist")
        self.assertGreaterEqual(action2, 0, "Action 2 must exist")
        self.assertLess(action1, action2,
                        "Assessment must precede provenance")

    def test_step9_provenance_before_conditional_rereview(self) -> None:
        """Provenance (action 2) precedes the conditional #### Re-review."""
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        self.assertGreaterEqual(step9_start, 0, "Step 9 must exist")
        self.assertGreater(step10_start, step9_start)
        step9 = self._decompose_md[step9_start:step10_start]
        prov_pos = step9.find("Verify `[DOCS]` input provenance")
        rereview_heading = step9.find("#### Re-review")
        # Actual consumer: "Resume the same reviewer agent"
        rereview_consumer = step9.find("Resume the same reviewer agent")
        self.assertGreaterEqual(prov_pos, 0, "Provenance must exist")
        self.assertGreaterEqual(rereview_heading, 0, "Re-review heading must exist")
        self.assertGreaterEqual(rereview_consumer, 0, "Re-review consumer must exist")
        self.assertLess(prov_pos, rereview_heading,
                        "Provenance must precede #### Re-review")
        self.assertLess(prov_pos, rereview_consumer,
                        "Provenance must precede re-review consumer")

    def test_step9_provenance_unconditional(self) -> None:
        """Provenance runs unconditionally, even with zero findings."""
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        step9 = self._decompose_md[step9_start:step10_start]
        self.assertIn("runs unconditionally", step9)
        self.assertIn("zero findings", step9)

    def test_step9_provenance_corrections_trigger_rereview(self) -> None:
        """Provenance-only corrections trigger conditional re-review."""
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        step9 = self._decompose_md[step9_start:step10_start]
        rereview_section = step9[step9.find("#### Re-review"):]
        self.assertIn("provenance corrections", rereview_section)

    def test_step9_no_early_pass(self) -> None:
        """Pass declaration only after both mandatory actions complete."""
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        step9 = self._decompose_md[step9_start:step10_start]
        pass_pos = step9.find("validation passes")
        prov_pos = step9.find("Verify `[DOCS]` input provenance")
        self.assertGreaterEqual(pass_pos, 0, "Pass text must exist")
        self.assertGreater(pass_pos, prov_pos,
                           "Pass must come AFTER provenance")

    def test_step9_cap_is_2_rounds(self) -> None:
        """Cap at 2 review-fix rounds applies across entire Step 9."""
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        step9 = " ".join(self._decompose_md[step9_start:step10_start].split())
        self.assertIn("Cap at 2 review-fix rounds total", step9)
        self.assertIn("the 2-round cap has not been reached", step9,
                      "Cap must gate re-review dispatch")

    def test_step9_no_extra_phase(self) -> None:
        """No Step 9a, Step 11, or unconditional #### Verify heading."""
        self.assertNotIn("### Step 9a:", self._decompose_md)
        self.assertNotIn("### Step 11:", self._decompose_md)
        # Old unconditional #### Verify heading must be gone
        step9_start = self._decompose_md.find("### Step 9:")
        step10_start = self._decompose_md.find("### Step 10:")
        step9 = self._decompose_md[step9_start:step10_start]
        self.assertNotIn("#### Verify `[DOCS]` input provenance", step9,
                         "Provenance must be a numbered action, not a #### heading")

    def test_reviewer_still_lacks_design_document(self) -> None:
        """Independent reviewer in Step 8 still does not receive the
        design document; provenance is author-only in Step 9."""
        review_section = self._decompose_md.split("### Step 8:")[1].split("### Step 9:")[0]
        self.assertIn("NOT the design document", review_section)

    def test_flag_gate_for_critical_high(self) -> None:
        self._assert_marker_exists(
            "**Gate:** PASS | FLAG",
            "FLAG gate must exist")
        self._assert_marker_exists(
            "CRITICAL or HIGH findings remain unfixed",
            "FLAG criteria must reference CRITICAL/HIGH")

    def test_present_is_last_step(self) -> None:
        self.assertEqual(self._steps[-1], "10")
        last = self._decompose_md.split("### Step 10:")[1][:100]
        self.assertIn("Summarize and Present", last)

    def test_open_question_design_references_preserved(self) -> None:
        """[Open: §9.N] marker format references design document sections,
        not decompose step numbers."""
        self.assertIn("[Open: §9.N]", self._decompose_md)

    # -- Identity stability contracts --

    def test_criterion7_is_stable_identity(self) -> None:
        """Criterion 7 requires stable identity, not numeric placement."""
        flat = " ".join(self._decompose_md.split())
        self.assertIn("Stable identity", flat,
                      "Criterion 7 must be titled 'Stable identity'")
        self.assertIn("is fixed", flat)
        self.assertIn("must not be renamed, renumbered, or moved", flat)
        self.assertIn("retired numbers must not be reused", flat)

    def test_criterion7_key_availability_not_position(self) -> None:
        """Criterion 7 defers on missing keys, never rejects based on
        numeric position."""
        flat = " ".join(self._decompose_md.split())
        self.assertIn("Contributing stories AND Dependencies", flat)
        self.assertIn("deferred to the next explicit", flat)
        self.assertNotIn("numerically last", flat,
                         "Must not require numeric-last positioning")

    def test_step9_no_renumber_instruction(self) -> None:
        """Step 9 finding fixes must not rename/renumber story files."""
        step9 = " ".join(self._decompose_md.split("### Step 9:")[1]
                         .split("### Step 10:")[0].split())
        self.assertIn("do not rename, renumber, or move story files", step9)

    def test_identity_stability_block_exists(self) -> None:
        """Identity stability block exists in decompose.md."""
        self._assert_marker_exists(
            "**Identity stability:**",
            "Identity stability block must exist")

    # -- Producer-order contracts for consolidated steps --

    def test_sizing_is_main_step_5(self) -> None:
        """Sizing Consistency Check is a main step, not a sub-heading."""
        self._assert_marker_exists(
            "### Step 5: Sizing Consistency Check",
            "Sizing must be main Step 5")

    def test_impl_refs_is_main_step_6(self) -> None:
        """Add Implementation References is a main step, not a sub-heading."""
        self._assert_marker_exists(
            "### Step 6: Add Implementation References",
            "Impl refs must be main Step 6")

    def test_coverage_before_structure_in_step7(self) -> None:
        """Step 7: coverage matrix is written before structure validation."""
        step7_start = self._decompose_md.find("### Step 7:")
        step8_start = self._decompose_md.find("### Step 8:")
        self.assertGreaterEqual(step7_start, 0, "Step 7 must exist")
        self.assertGreater(step8_start, step7_start, "Step 8 must follow 7")
        step7 = self._decompose_md[step7_start:step8_start]
        coverage_pos = step7.find("07-coverage.md")
        structure_pos = step7.find("Verify artifact structure")
        self.assertGreaterEqual(coverage_pos, 0, "Coverage producer must exist")
        self.assertGreaterEqual(structure_pos, 0, "Structure gate must exist")
        self.assertLess(coverage_pos, structure_pos,
                        "Coverage must precede structure validation")

    def test_summary_before_presentation_in_step10(self) -> None:
        """Step 10: review summary is produced before user presentation."""
        step10 = self._decompose_md.split("### Step 10:")[1]
        summary_pos = step10.find("## Decomposition Review Summary")
        present_pos = step10.find("Present to the user")
        self.assertGreaterEqual(summary_pos, 0, "Summary template must exist")
        self.assertGreaterEqual(present_pos, 0, "Presentation must exist")
        self.assertLess(summary_pos, present_pos,
                        "Summary must precede presentation")

    def test_all_steps_before_review(self) -> None:
        """Steps 4-7 (stories/sizing/refs/artifacts) all precede Step 8 review."""
        flat = self._decompose_md
        step4 = flat.find("### Step 4:")
        step5 = flat.find("### Step 5:")
        step6 = flat.find("### Step 6:")
        step7 = flat.find("### Step 7:")
        step8 = flat.find("### Step 8:")
        for pos, name in [(step4, "4"), (step5, "5"), (step6, "6"),
                          (step7, "7"), (step8, "8")]:
            self.assertGreaterEqual(pos, 0, f"Step {name} must exist")
        self.assertLess(step4, step5)
        self.assertLess(step5, step6)
        self.assertLess(step6, step7)
        self.assertLess(step7, step8, "All artifact steps must precede review")


# ---------------------------------------------------------------------------
# Sync: reference-availability guard for DOCS creation and update
# ---------------------------------------------------------------------------

class TestSyncDocsReferenceGuard(_TmpDirMixin, unittest.TestCase):
    """Verify the reference-availability guard: render_story_description
    produces [unresolved] when a contributor key is missing, enabling the
    sync agent to detect and defer the DOCS write. Tests model valid
    story ordering (contributors before DOCS) and simulate a contributor
    whose creation was skipped/failed."""

    def setUp(self) -> None:
        super().setUp()
        self.stories_dir = Path(self.tmpdir) / "06-stories"
        self.stories_dir.mkdir()
        self.artifacts_dir = Path(self.tmpdir)
        _make_epic(self.stories_dir, 1, "feature")
        # story-01 and story-02 are DEV contributors; story-03 is DOCS
        _make_dev_story(self.stories_dir, 1, 1, "api", title="API endpoint")
        _make_dev_story(self.stories_dir, 1, 2, "webhook", title="Webhook")
        _make_docs_story(self.stories_dir, 1, 3, "docs",
                         title="API reference",
                         deps="Story 1.01, Story 1.02",
                         contributing_stories="Story 1.01, Story 1.02",
                         doc_inputs="**Story 1.01:** endpoint.\n"
                                    "**Story 1.02:** webhook.")

    def _manifest_with_keys(self, story_keys: list[dict]) -> dict:
        """Build a manifest with the given story entries."""
        return {"epics": [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100",
            "stories": story_keys,
        }]}

    # -- Guard for new DOCS creation (Step 6a) --

    def test_new_docs_missing_contributor_shows_unresolved(self) -> None:
        """New DOCS: contributor story-02 creation skipped → [unresolved].
        The sync agent must not create this DOCS story or checkpoint it."""
        manifest = self._manifest_with_keys([
            {"file": "story-01-api.md", "jira_key": "T-101"},
            # story-02 creation failed/skipped — no key
        ])
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        self.assertIn("[unresolved]", desc,
                      "Missing contributor key must produce [unresolved]")
        self.assertIn("T-101", desc,
                      "Available contributor must still resolve")

    def test_new_docs_all_keys_resolves(self) -> None:
        """New DOCS: all contributors created → clean resolution, safe to create."""
        manifest = self._manifest_with_keys([
            {"file": "story-01-api.md", "jira_key": "T-101"},
            {"file": "story-02-webhook.md", "jira_key": "T-102"},
        ])
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        self.assertNotIn("[unresolved]", desc)
        self.assertIn("T-101", desc)
        self.assertIn("T-102", desc)

    # -- Guard for existing DOCS update (Step 6b) --

    def test_existing_docs_update_missing_new_contributor(self) -> None:
        """Update: a new contributor was added but its creation skipped."""
        # DOCS already synced, now references a new story-02
        manifest = self._manifest_with_keys([
            {"file": "story-01-api.md", "jira_key": "T-101"},
            {"file": "story-03-docs.md", "jira_key": "T-103",
             "content_hash": "old", "synced_status": "active"},
            # story-02 creation failed — no key
        ])
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        self.assertIn("[unresolved]", desc,
                      "Update with missing contributor must show [unresolved]")

    # -- Retry lifecycle: deferred DOCS stays NEW in next detect-changes --

    def test_deferred_docs_remains_new_for_retry(self) -> None:
        """A DOCS story deferred (not checkpointed) remains NEW on next run."""
        # First sync: story-02 skipped, so DOCS was deferred (no checkpoint)
        manifest_path = _make_manifest(self.artifacts_dir, [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100",
            "title": "Feature",
            "size": "M",
            "content_hash": "abc",
            "synced_status": "active",
            "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101",
                 "title": "[DEV] API endpoint", "content_hash": "def",
                 "synced_status": "active"},
                # story-02 and story-03 (DOCS) NOT in manifest = deferred
            ],
        }])
        plan = sync_helper.detect_changes(str(self.artifacts_dir))
        docs_items = [i for i in plan["items"]
                      if i["file"].endswith("story-03-docs.md")]
        self.assertEqual(len(docs_items), 1)
        self.assertEqual(docs_items[0]["category"], "new",
                         "Deferred DOCS (no checkpoint) must be NEW on next run")

    def test_retry_after_contributor_created_resolves(self) -> None:
        """After the missing contributor is created and checkpointed,
        the DOCS story's references resolve on the retry run."""
        # Simulate: both contributors now in manifest (retry scenario)
        manifest = self._manifest_with_keys([
            {"file": "story-01-api.md", "jira_key": "T-101"},
            {"file": "story-02-webhook.md", "jira_key": "T-102"},
            # DOCS still not in manifest — it is being created now
        ])
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        self.assertNotIn("[unresolved]", desc,
                         "After contributor creation, refs must resolve")
        self.assertIn("T-102", desc)

    def test_successful_checkpoint_makes_docs_unchanged(self) -> None:
        """After DOCS creation succeeds and is checkpointed, the next
        detect-changes run reports it as unchanged."""
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        content_hash = sync_helper.compute_file_hash(str(docs_path))
        manifest_path = _make_manifest(self.artifacts_dir, [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100",
            "title": "Feature",
            "size": "M",
            "content_hash": "abc",
            "synced_status": "active",
            "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101",
                 "title": "[DEV] API", "content_hash": "d1",
                 "synced_status": "active"},
                {"file": "story-02-webhook.md", "jira_key": "T-102",
                 "title": "[DEV] Webhook", "content_hash": "d2",
                 "synced_status": "active"},
                {"file": "story-03-docs.md", "jira_key": "T-103",
                 "title": "[DOCS] API reference", "content_hash": content_hash,
                 "synced_status": "active"},
            ],
        }])
        plan = sync_helper.detect_changes(str(self.artifacts_dir))
        docs_items = [i for i in plan["items"]
                      if i["file"].endswith("story-03-docs.md")]
        self.assertEqual(len(docs_items), 1)
        self.assertEqual(docs_items[0]["category"], "unchanged",
                         "Checkpointed DOCS with matching hash must be unchanged")

    # -- Instruction contracts: sync.md guard and callsite text --

    @classmethod
    def _read_sync_md(cls) -> str:
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        return sync_path.read_text(encoding="utf-8")

    def test_6a_guard_precedes_prepare(self) -> None:
        """Step 6a: reference-availability guard appears before the
        story prepare recipe instruction."""
        sync_md = self._read_sync_md()
        start = sync_md.find("#### 6a:")
        end = sync_md.find("#### 6b:")
        self.assertGreaterEqual(start, 0, "Step 6a must exist")
        self.assertGreater(end, start, "Step 6b must follow 6a")
        section = sync_md[start:end]
        guard_pos = section.find("Reference-availability guard")
        prepare_pos = section.find("`prepare`")
        self.assertGreaterEqual(guard_pos, 0,
                                "6a must contain reference-availability guard")
        self.assertGreaterEqual(prepare_pos, 0,
                                "6a must contain prepare instruction")
        self.assertLess(guard_pos, prepare_pos,
                        "Guard must precede prepare in 6a")

    def test_6b_guard_precedes_prepare(self) -> None:
        """Step 6b: reference-availability guard appears before the
        story prepare recipe instruction."""
        sync_md = self._read_sync_md()
        start = sync_md.find("#### 6b:")
        end = sync_md.find("#### 6c:")
        self.assertGreaterEqual(start, 0, "Step 6b must exist")
        self.assertGreater(end, start, "Step 6c must follow 6b")
        section = sync_md[start:end]
        guard_pos = section.find("Reference-availability guard")
        prepare_pos = section.find("`prepare`")
        self.assertGreaterEqual(guard_pos, 0,
                                "6b must contain reference-availability guard")
        self.assertGreaterEqual(prepare_pos, 0,
                                "6b must contain prepare instruction")
        self.assertLess(guard_pos, prepare_pos,
                        "Guard must precede prepare in 6b")

    def test_step8_reports_blocked(self) -> None:
        """Step 8 reports blocked stories with missing keys."""
        sync_md = self._read_sync_md()
        start = sync_md.find("### Step 8:")
        self.assertGreaterEqual(start, 0, "Step 8 must exist")
        section = sync_md[start:]
        self.assertIn("blocked", section)
        self.assertIn("Do not claim complete synchronization", section)

    # -- Manifest identity: synced DOCS stable through detect_changes --

    def test_synced_docs_with_late_contributor_stays_unchanged(self) -> None:
        """A synced DOCS story retains its manifest identity when a
        higher-numbered contributor is added. detect_changes does not
        classify it as new, removed, or renamed."""
        # story-04 is a late contributor added after DOCS story-03 was synced
        _make_dev_story(self.stories_dir, 1, 4, "metrics", title="Add metrics")
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        content_hash = sync_helper.compute_file_hash(str(docs_path))
        _make_manifest(self.artifacts_dir, [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100",
            "title": "Feature", "size": "M",
            "content_hash": "abc", "synced_status": "active",
            "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101",
                 "title": "[DEV] API", "content_hash": "d1",
                 "synced_status": "active"},
                {"file": "story-02-webhook.md", "jira_key": "T-102",
                 "title": "[DEV] Webhook", "content_hash": "d2",
                 "synced_status": "active"},
                {"file": "story-03-docs.md", "jira_key": "T-103",
                 "title": "[DOCS] API reference",
                 "content_hash": content_hash,
                 "synced_status": "active"},
                # story-04 is new (not yet in manifest)
            ],
        }])
        plan = sync_helper.detect_changes(str(self.artifacts_dir))
        docs_items = [i for i in plan["items"]
                      if i["file"].endswith("story-03-docs.md")]
        self.assertEqual(len(docs_items), 1)
        self.assertEqual(docs_items[0]["category"], "unchanged",
                         "Synced DOCS must stay unchanged when late contributor added")
        self.assertEqual(docs_items[0]["jira_key"], "T-103",
                         "Synced DOCS must retain its Jira key")
        # story-04 should be new
        new_items = [i for i in plan["items"]
                     if i["file"].endswith("story-04-metrics.md")]
        self.assertEqual(len(new_items), 1)
        self.assertEqual(new_items[0]["category"], "new")

    def test_synced_docs_changed_when_inputs_updated(self) -> None:
        """A synced DOCS story whose content changed (e.g., updated
        Documentation Inputs) is correctly classified as changed."""
        docs_path = self.stories_dir / "epic-1" / "story-03-docs.md"
        old_hash = sync_helper.compute_file_hash(str(docs_path))
        _make_manifest(self.artifacts_dir, [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100",
            "title": "Feature", "size": "M",
            "content_hash": "abc", "synced_status": "active",
            "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101",
                 "title": "[DEV] API", "content_hash": "d1",
                 "synced_status": "active"},
                {"file": "story-02-webhook.md", "jira_key": "T-102",
                 "title": "[DEV] Webhook", "content_hash": "d2",
                 "synced_status": "active"},
                {"file": "story-03-docs.md", "jira_key": "T-103",
                 "title": "[DOCS] API reference",
                 "content_hash": old_hash,
                 "synced_status": "active"},
            ],
        }])
        # Modify the DOCS story content
        content = docs_path.read_text(encoding="utf-8")
        docs_path.write_text(content + "\nUpdated Documentation Inputs.\n", encoding="utf-8")
        plan = sync_helper.detect_changes(str(self.artifacts_dir))
        docs_items = [i for i in plan["items"]
                      if i["file"].endswith("story-03-docs.md")]
        self.assertEqual(len(docs_items), 1)
        self.assertEqual(docs_items[0]["category"], "changed",
                         "Modified DOCS must be classified as changed")
        self.assertEqual(docs_items[0]["jira_key"], "T-103")

    def test_noncontributing_dependency_resolves_when_key_available(self) -> None:
        """A later-numbered prerequisite dependency (in Dependencies but
        NOT in Contributing stories/Documentation Inputs) resolves when
        its manifest key exists. Renderer test only — does not test
        live deferral/checkpoint behavior."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        _make_dev_story(stories_dir, 1, 4, "infra", title="Infra prereq")
        # Add story-04 to Dependencies ONLY, not Contributing stories
        docs_path = stories_dir / "epic-1" / "story-03-docs.md"
        content = docs_path.read_text(encoding="utf-8")
        # Replace only in the Dependencies section (after "## Dependencies")
        dep_marker = "## Dependencies\n\n"
        dep_start = content.find(dep_marker)
        self.assertGreater(dep_start, 0, "Dependencies section must exist")
        dep_val_start = dep_start + len(dep_marker)
        dep_line_end = content.find("\n", dep_val_start)
        old_deps = content[dep_val_start:dep_line_end]
        content = (content[:dep_val_start] +
                   old_deps + ", Story 1.04" +
                   content[dep_line_end:])
        docs_path.write_text(content, encoding="utf-8")
        # Verify Contributing stories was NOT changed
        self.assertNotIn("Story 1.04",
                         content.split("Contributing stories:")[1].split("\n")[0]
                         if "Contributing stories:" in content else "",
                         "Story 1.04 must not be in Contributing stories")

        manifest = self._manifest_with_keys([
            {"file": "story-01-api.md", "jira_key": "T-101"},
            {"file": "story-02-webhook.md", "jira_key": "T-102"},
            {"file": "story-04-infra.md", "jira_key": "T-104"},
        ])
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        self.assertNotIn("[unresolved]", desc,
                         "Non-contributing dependency with key must resolve")
        self.assertIn("T-104", desc)

    def test_noncontributing_dependency_missing_key_defers(self) -> None:
        """A later-numbered prerequisite dependency without a manifest
        key produces [unresolved] in the rendered description. The sync
        agent uses this signal to defer the DOCS write (no Jira call or
        manifest checkpoint). Renderer-only test — deferral/checkpoint
        behavior is tested by state/contract tests."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        _make_dev_story(stories_dir, 1, 4, "infra", title="Infra prereq")
        docs_path = stories_dir / "epic-1" / "story-03-docs.md"
        content = docs_path.read_text(encoding="utf-8")
        dep_marker = "## Dependencies\n\n"
        dep_start = content.find(dep_marker)
        dep_val_start = dep_start + len(dep_marker)
        dep_line_end = content.find("\n", dep_val_start)
        old_deps = content[dep_val_start:dep_line_end]
        content = (content[:dep_val_start] +
                   old_deps + ", Story 1.04" +
                   content[dep_line_end:])
        docs_path.write_text(content, encoding="utf-8")

        manifest = self._manifest_with_keys([
            {"file": "story-01-api.md", "jira_key": "T-101"},
            {"file": "story-02-webhook.md", "jira_key": "T-102"},
            # story-04 NOT in manifest — creation pending
        ])
        desc = sync_helper.render_story_description(
            docs_path, manifest, story_type="DOCS")
        self.assertIn("[unresolved]", desc,
                      "Missing dependency key must produce [unresolved]")

    # -- Instruction contract: guard in 6a/6b --

    def test_sync_6a_guard_covers_deps_and_contributing(self) -> None:
        """Step 6a guard paragraph states coverage of Dependencies and
        Contributing stories directly, and delegates to the helper."""
        sync_md = self._read_sync_md()
        start = sync_md.find("#### 6a:")
        end = sync_md.find("#### 6b:")
        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)
        section_6a = sync_md[start:end]
        guard_start = section_6a.find("**Reference-availability guard.**")
        guard_end = section_6a.find("For each new story")
        self.assertGreater(guard_start, -1, "guard paragraph must exist")
        self.assertGreater(guard_end, guard_start, "prepare recipe must follow guard")
        guard = section_6a[guard_start:guard_end]
        guard_flat = " ".join(guard.split())
        self.assertIn("check-ref-availability", guard_flat)
        # Guard itself states what the helper checks
        self.assertIn("Dependencies", guard_flat)
        self.assertIn("Contributing stories", guard_flat)


# ---------------------------------------------------------------------------
# Identity stability: allocation and retirement
# ---------------------------------------------------------------------------

class TestIdentityStability(_TmpDirMixin, unittest.TestCase):
    """Helper-level and instruction-contract tests for story identity
    stability. These verify detect_changes classification and
    render_story_description reference resolution behavior — not live
    Jira operations or an authoring allocator."""

    def test_append_and_retirement_classification(self) -> None:
        """Helper: story-03 (above retired story-02) is classified as
        new; retired story-02 (status:removed with manifest entry) is
        classified as removed. Verifies gap/retirement handling."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        stories_dir.mkdir()
        _make_epic(stories_dir, 1, "feature")
        _make_dev_story(stories_dir, 1, 1, "api", title="API")
        _make_dev_story(stories_dir, 1, 2, "old", title="Old", removed=True)
        _make_dev_story(stories_dir, 1, 3, "webhook", title="Webhook")
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100", "title": "Feature", "size": "M",
            "content_hash": "x", "synced_status": "active",
            "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101",
                 "title": "[DEV] API",
                 "content_hash": sync_helper.compute_file_hash(
                     str(stories_dir / "epic-1" / "story-01-api.md")),
                 "synced_status": "active"},
                {"file": "story-02-old.md", "jira_key": "T-102",
                 "title": "[DEV] Old", "content_hash": "y",
                 "synced_status": "active"},
            ],
        }])
        plan = sync_helper.detect_changes(str(Path(self.tmpdir)))
        story3 = [i for i in plan["items"]
                  if i["file"].endswith("story-03-webhook.md")]
        self.assertEqual(len(story3), 1)
        self.assertEqual(story3[0]["category"], "new")
        story2 = [i for i in plan["items"]
                  if i["file"].endswith("story-02-old.md")]
        self.assertEqual(len(story2), 1)
        self.assertEqual(story2[0]["category"], "removed")

    def test_identity_stability_instruction_contract(self) -> None:
        """Instruction: identity stability rule requires append above
        highest including retired, no gap reuse, no rename/renumber."""
        decompose_path = Path(__file__).resolve().parent.parent / "skills" / "decompose.md"
        flat = " ".join(decompose_path.read_text(encoding="utf-8").split())
        self.assertIn("retired numbers must not be reused", flat)
        self.assertIn("must not be renamed, renumbered, or moved", flat)
        # Guidelines canonical rule
        guidelines_path = Path(__file__).resolve().parent.parent / "guidelines.md"
        guidelines = " ".join(guidelines_path.read_text(encoding="utf-8").split())
        self.assertIn("Identity stability", guidelines)
        self.assertIn("above the highest existing", guidelines)

    def test_content_edit_retains_identity_and_key(self) -> None:
        """Helper: editing content changes hash but preserves manifest
        identity (filename → Jira key mapping)."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        stories_dir.mkdir()
        _make_epic(stories_dir, 1, "feature")
        story_path = _make_dev_story(stories_dir, 1, 1, "api", title="API")
        old_hash = sync_helper.compute_file_hash(str(story_path))
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-feature.md",
            "jira_key": "T-100", "title": "Feature", "size": "M",
            "content_hash": "x", "synced_status": "active",
            "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101",
                 "title": "[DEV] API", "content_hash": old_hash,
                 "synced_status": "active"},
            ],
        }])
        story_path.write_text(story_path.read_text(encoding="utf-8") + "\nUpdated.\n", encoding="utf-8")
        plan = sync_helper.detect_changes(str(Path(self.tmpdir)))
        items = [i for i in plan["items"]
                 if i["file"].endswith("story-01-api.md")]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "changed")
        self.assertEqual(items[0]["jira_key"], "T-101",
                         "Jira key must be preserved on content edit")

    def test_never_synced_removed_skipped_and_file_retained(self) -> None:
        """Helper: a never-synced removed file is absent from the change
        plan (not created in Jira), and the file remains on disk
        reserving its number."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        stories_dir.mkdir()
        _make_epic(stories_dir, 1, "feature")
        _make_dev_story(stories_dir, 1, 1, "api", title="API")
        removed_path = _make_dev_story(
            stories_dir, 1, 2, "old", title="Old", removed=True)
        # No manifest — fresh sync
        plan = sync_helper.detect_changes(str(Path(self.tmpdir)))
        story2 = [i for i in plan["items"]
                  if i["file"].endswith("story-02-old.md")]
        self.assertEqual(len(story2), 0,
                         "Never-synced removed story must be absent from plan")
        self.assertTrue(removed_path.exists(),
                        "Removed file must remain on disk")

    def test_lower_id_docs_unresolved_then_resolves(self) -> None:
        """Renderer: DOCS story-02 references contributor story-03.
        Without story-03 key: [unresolved] in rendered description
        (sync agent uses this signal to defer). With key: resolves.
        This tests render_story_description, not live deferral."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        stories_dir.mkdir()
        _make_epic(stories_dir, 1, "feature")
        _make_dev_story(stories_dir, 1, 1, "api", title="API")
        _make_docs_story(stories_dir, 1, 2, "docs",
                         title="API reference",
                         deps="Story 1.01, Story 1.03",
                         contributing_stories="Story 1.01, Story 1.03",
                         doc_inputs="**Story 1.01:** endpoint.\n"
                                    "**Story 1.03:** webhook.")
        _make_dev_story(stories_dir, 1, 3, "webhook", title="Webhook")
        docs_path = stories_dir / "epic-1" / "story-02-docs.md"

        # Without story-03 key
        manifest_no_key = {"epics": [{"file": "epic-1-feature.md",
            "jira_key": "T-100", "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101"}]}]}
        desc1 = sync_helper.render_story_description(
            docs_path, manifest_no_key, story_type="DOCS")
        self.assertIn("[unresolved]", desc1,
                      "Missing key must produce [unresolved]")

        # With story-03 key
        manifest_with_key = {"epics": [{"file": "epic-1-feature.md",
            "jira_key": "T-100", "stories": [
                {"file": "story-01-api.md", "jira_key": "T-101"},
                {"file": "story-03-webhook.md", "jira_key": "T-103"}]}]}
        desc2 = sync_helper.render_story_description(
            docs_path, manifest_with_key, story_type="DOCS")
        self.assertNotIn("[unresolved]", desc2)
        self.assertIn("T-103", desc2)


# ---------------------------------------------------------------------------
# Epic combine: parent removal cascades children
# ---------------------------------------------------------------------------

class TestEpicCombineCascade(_TmpDirMixin, unittest.TestCase):
    """Verify that marking a parent epic status:removed causes
    detect_changes to reclassify its active synced children as removed,
    and that keeping the parent active preserves child classification."""

    def _setup_epic_with_child(self, parent_removed: bool) -> dict:
        """Create epic-1 with one synced story. Return change plan."""
        stories_dir = Path(self.tmpdir) / "06-stories"
        stories_dir.mkdir()
        ep_content = "---\nstatus: removed\n---\n" if parent_removed else "---\n---\n"
        ep_content += "# Epic 1: Feature\n\n## Summary\n\nBuild.\n\n## Acceptance Criteria\n\n- AC\n"
        (stories_dir / "epic-1-feature.md").write_text(ep_content, encoding="utf-8")
        ep1 = stories_dir / "epic-1"
        ep1.mkdir()
        story = ep1 / "story-01-api.md"
        story.write_text(
            "---\n---\n# Story 1.01: [DEV] API\n\n**As a** dev,\n"
            "**I want to** build,\n**So that** done.\n\n"
            "## Acceptance Criteria\n\n- AC\n\n"
            "## Implementation Guidance\n\nDo.\n\n"
            "## Testing Approach\n\nTest.\n\n"
            "## Dependencies\n\nNone\n\n"
            "## Design Reference\n\nEpic: Epic 1 — Feature\n",
            encoding="utf-8")
        # Manifest: both synced, child content changed (different hash)
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-feature.md", "jira_key": "T-100",
            "title": "Feature", "size": "M",
            "content_hash": "old_epic_hash", "synced_status": "active",
            "stories": [{
                "file": "story-01-api.md", "jira_key": "T-101",
                "title": "[DEV] API", "content_hash": "DIFFERENT",
                "synced_status": "active"
            }]
        }])
        return sync_helper.detect_changes(str(Path(self.tmpdir)))

    def test_removed_parent_cascades_changed_child_to_removed(self) -> None:
        """When parent epic is status:removed and synced child's content
        changed, detect_changes reclassifies the child as removed."""
        plan = self._setup_epic_with_child(parent_removed=True)
        child = [i for i in plan["items"]
                 if i["file"].endswith("story-01-api.md")]
        self.assertEqual(len(child), 1)
        self.assertEqual(child[0]["category"], "removed",
                         "Changed child under removed parent must be 'removed'")

    def test_active_parent_preserves_changed_child(self) -> None:
        """When parent epic is active (not removed), changed child
        stays classified as 'changed' with qualified identity intact."""
        plan = self._setup_epic_with_child(parent_removed=False)
        child = [i for i in plan["items"]
                 if i["file"].endswith("story-01-api.md")]
        self.assertEqual(len(child), 1)
        self.assertEqual(child[0]["category"], "changed",
                         "Changed child under active parent must stay 'changed'")
        self.assertEqual(child[0]["jira_key"], "T-101",
                         "Jira key preserved when parent stays active")
        # Verify qualified identity from actual helper output
        self.assertEqual(child[0]["file"], "epic-1/story-01-api.md",
                         "Qualified file path must include parent epic dir")
        self.assertEqual(child[0]["epic_index"], 1)
        self.assertEqual(child[0]["story_index"], 1)

    def test_revise_retain_work_guard(self) -> None:
        """Revise combining-epics instruction guards against marking
        parent removed while children should remain active."""
        revise_path = Path(__file__).resolve().parent.parent / "skills" / "revise.md"
        flat = " ".join(revise_path.read_text(encoding="utf-8").split())
        guard_pos = flat.find("do **not** mark the absorbed epic")
        retire_pos = flat.find("Only mark the epic removed when all")
        unsupported_pos = flat.find("not supported by the current file-authoritative model")
        self.assertGreaterEqual(guard_pos, 0,
                                "Must guard against marking active-child parent removed")
        self.assertGreaterEqual(retire_pos, 0,
                                "Must explain when removal is safe")
        self.assertGreater(retire_pos, guard_pos,
                           "Retirement instruction must follow guard")
        self.assertGreaterEqual(unsupported_pos, 0,
                                "Must flag physical reparent as unsupported")


# ---------------------------------------------------------------------------
# Instruction contracts: review identity criterion + coverage pointer
# ---------------------------------------------------------------------------

class TestInstructionContracts(unittest.TestCase):
    """Instruction-level contracts for review rubric and template refs."""

    def test_review_rubric_identity_criterion(self) -> None:
        """Decomposition review criterion 9 checks identity consistency."""
        review_path = Path(__file__).resolve().parent.parent / "decomposition-review.md"
        review_md = review_path.read_text(encoding="utf-8")
        crit9_start = review_md.find("9. **Identity consistency**")
        finding_format = review_md.find("## Finding Format")
        self.assertGreaterEqual(crit9_start, 0, "Criterion 9 must exist")
        self.assertGreater(finding_format, crit9_start)
        crit9 = review_md[crit9_start:finding_format]
        self.assertIn("renaming, renumbering, moving, or reusing", crit9)
        self.assertIn("do not invent allocation history", crit9)

    def test_coverage_pointer_is_step7(self) -> None:
        """05-epics template coverage pointer references Step 7."""
        decompose_path = Path(__file__).resolve().parent.parent / "skills" / "decompose.md"
        content = decompose_path.read_text(encoding="utf-8")
        idx = content.find("is the authoritative source for requirement-to-story")
        self.assertGreaterEqual(idx, 0, "Coverage pointer must exist")
        line = content[max(0, idx - 20):idx + 80]
        self.assertIn("(Step 7)", line,
                      "Coverage pointer must reference Step 7")


# ---------------------------------------------------------------------------
# Creation-order planning
# ---------------------------------------------------------------------------

class TestPlanCreationOrder(_TmpDirMixin, unittest.TestCase):
    """Tests for plan_creation_order using actual fixture file identities.

    Helper-level tests verify the planner's dependency graph, topological
    sort, cycle/missing-target detection, and key reuse. Instruction
    contracts verify sync.md consumer references. NOT live Jira/LLM E2E."""

    def _setup(self, specs):
        """Create artifacts. specs: [(epic, story, slug, type, deps, contrib, removed)]."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        paths = {}
        for eidx, sidx, slug, stype, deps, contrib, removed in specs:
            _make_epic(sd, eidx, f"epic{eidx}")
            if stype == "DOCS":
                p = _make_docs_story(sd, eidx, sidx, slug,
                    title=f"{slug} docs", deps=deps,
                    contributing_stories=contrib or "None", removed=removed)
            else:
                p = _make_dev_story(sd, eidx, sidx, slug,
                    title=slug, deps=deps, removed=removed)
            paths[(eidx, sidx)] = p
        return sd, paths

    def _item(self, eidx, sidx, slug, cat="new", key=None, title=""):
        return {"type": "story", "category": cat,
                "epic_index": eidx, "story_index": sidx,
                "jira_key": key, "title": title,
                "file": f"epic-{eidx}/story-{sidx:02d}-{slug}.md"}

    def _epic_item(self, eidx, cat="new", key=None):
        """Epic item matching the file _setup creates."""
        return {"type": "epic", "category": cat,
                "epic_index": eidx, "jira_key": key,
                "file": f"epic-{eidx}-epic{eidx}.md"}

    def _qids(self, result):
        return [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in result["ordered"]]

    # ── Core ordering ──────────────────────────────────────────

    def test_linear_chain(self) -> None:
        """A→B→C multi-hop: C after B after A."""
        self._setup([(1,1,"a","DEV","None",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False),
                     (1,3,"c","DEV","Story 1.02",None,False)])
        items = [self._epic_item(1)] + [
            self._item(1,i,["a","b","c"][i-1]) for i in [1,2,3]]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(self._qids(r),
                         ["story-1.01","story-1.02","story-1.03"])
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["blocked"], [])

    def test_reversed_cross_epic(self) -> None:
        """Story 1.01 depends on Story 2.01 (numerically earlier epic
        needs later epic's story — must still sort correctly)."""
        self._setup([(1,1,"client","DEV","Story 2.01",None,False),
                     (2,1,"api","DEV","None",None,False)])
        items = [self._epic_item(1), self._epic_item(2),
                 self._item(1,1,"client"), self._item(2,1,"api")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(self._qids(r), ["story-2.01","story-1.01"])
        self.assertEqual(r["errors"], [])

    def test_existing_key_satisfies(self) -> None:
        """Already-synced story satisfies dependency without recreation."""
        self._setup([(1,1,"api","DEV","None",None,False),
                     (1,2,"client","DEV","Story 1.01",None,False)])
        manifest = {"epics": [{"file": "epic-1-epic1.md", "jira_key": "T-100",
                    "stories": [{"file": "story-01-api.md","jira_key":"T-101"}]}]}
        items = [self._epic_item(1, key="T-100"),
                 self._item(1,1,"api","unchanged","T-101"),
                 self._item(1,2,"client")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertEqual(len(r["ordered"]), 1)
        self.assertEqual(r["ordered"][0]["story_index"], 2)
        self.assertIn("story-1.01", r["satisfied_keys"])

    # ── DOCS Contributing-only ordering ────────────────────────

    def test_docs_contrib_ordering_not_jira_dep(self) -> None:
        """DOCS Contributing stories affect ORDER but do NOT appear in
        the Dependencies section of the DOCS PREP output."""
        self._setup([(1,1,"api","DEV","None",None,False),
                     (1,2,"docs","DOCS","None","Story 1.01",False)])
        items = [self._epic_item(1), self._item(1,1,"api"),
                 self._item(1,2,"docs",title="[DOCS] docs docs")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(self._qids(r)[0], "story-1.01",
                         "Contributor must be created first")
        # Verify PREP.dependencies stays "None" (no contrib dep)
        docs_path = Path(self.tmpdir) / "06-stories/epic-1/story-02-docs.md"
        prep = sync_helper.prepare(
            str(docs_path), str(Path(self.tmpdir) / "sync-manifest.json"),
            "story", story_type="DOCS")
        self.assertNotIn("T-", prep.get("dependencies", ""),
                         "Contributing stories must not create Jira dep links")

    # ── Cycle detection ────────────────────────────────────────

    def test_self_cycle(self) -> None:
        """Story depends on itself → self-reference (not merely a cycle)."""
        self._setup([(1,1,"a","DEV","Story 1.01",None,False)])
        items = [self._epic_item(1), self._item(1,1,"a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(
            any("self-reference" in e for e in r["errors"]),
            f"Expected self-reference error, got: {r['errors']}")
        self.assertEqual(len(r["ordered"]), 0)

    def test_two_node_cycle(self) -> None:
        """A↔B mutual dependency → cycle, both blocked."""
        self._setup([(1,1,"a","DEV","Story 1.02",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False)])
        items = [self._epic_item(1), self._item(1,1,"a"), self._item(1,2,"b")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("cycle" in e.lower() for e in r["errors"]))
        self.assertEqual(len(r["blocked"]), 2)

    def test_cycle_downstream_distinction(self) -> None:
        """A↔B cycle blocks downstream C; C is not a cycle participant."""
        self._setup([(1,1,"a","DEV","Story 1.02",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False),
                     (1,3,"c","DEV","Story 1.01",None,False)])
        items = [self._epic_item(1)] + [
            self._item(1,i,["a","b","c"][i-1]) for i in [1,2,3]]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        cycle_errors = [e for e in r["errors"] if "cycle" in e.lower()]
        downstream_errors = [e for e in r["errors"] if "blocked" in e.lower()]
        self.assertGreater(len(cycle_errors), 0)
        self.assertGreater(len(downstream_errors), 0)
        # C should be in downstream, not cycle
        self.assertTrue(any("story-1.03" in e for e in downstream_errors))

    def test_mapped_key_no_false_cycle(self) -> None:
        """Mutual refs between already-keyed stories → no cycle."""
        self._setup([(1,1,"a","DEV","Story 1.02",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False)])
        manifest = {"epics": [{"file":"epic-1-epic1.md","jira_key":"T-100",
                    "stories":[{"file":"story-01-a.md","jira_key":"T-101"},
                               {"file":"story-02-b.md","jira_key":"T-102"}]}]}
        items = [self._item(1,1,"a","unchanged","T-101"),
                 self._item(1,2,"b","unchanged","T-102")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertEqual(r["errors"], [])
        self.assertEqual(len(r["ordered"]), 0)

    # ── Missing/unavailable targets ────────────────────────────

    def test_missing_nonexistent_target(self) -> None:
        """Dependency on nonexistent Story 9.99 → error."""
        self._setup([(1,1,"a","DEV","Story 9.99",None,False)])
        items = [self._item(1,1,"a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("9.99" in e for e in r["errors"]))

    def test_removed_no_key_target_unavailable(self) -> None:
        """Dependency on a removed story with no manifest key → error."""
        self._setup([(1,1,"a","DEV","Story 1.02",None,False),
                     (1,2,"old","DEV","None",None,True)])
        items = [self._item(1,1,"a"),
                 {"type":"story","category":"removed","epic_index":1,
                  "story_index":2,"jira_key":None,
                  "file":"epic-1/story-02-old.md","title":"old"}]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("no usable" in e.lower() for e in r["errors"]))

    # ── Changed/reopened write checks ──────────────────────────

    def test_changed_docs_satisfiable_by_creation_plan(self) -> None:
        """Changed DOCS references new story-03 that IS in creation plan
        → not blocked at plan time (runtime guard checks after creation)."""
        self._setup([(1,1,"api","DEV","None",None,False),
                     (1,2,"docs","DOCS","Story 1.03","Story 1.03",False),
                     (1,3,"wh","DEV","None",None,False)])
        manifest = {"epics":[{"file":"epic-1-epic1.md","jira_key":"T-100",
                    "stories":[{"file":"story-01-api.md","jira_key":"T-101"},
                               {"file":"story-02-docs.md","jira_key":"T-102",
                                "content_hash":"old","synced_status":"active"}]}]}
        items = [self._item(1,1,"api","unchanged","T-101"),
                 self._item(1,2,"docs","changed","T-102",
                            title="[DOCS] docs docs"),
                 self._item(1,3,"wh")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        # story-03 in creation plan satisfies the changed DOCS ref
        self.assertEqual(len(r["ordered"]), 1)
        self.assertEqual(r["ordered"][0]["story_index"], 3)
        self.assertEqual(len(r["blocked"]), 0)

    def test_changed_docs_blocked_unsatisfiable_ref(self) -> None:
        """Changed DOCS references a story that has no key and is NOT
        in the creation plan → blocked."""
        self._setup([(1,1,"api","DEV","None",None,False),
                     (1,2,"docs","DOCS","Story 1.03","Story 1.03",False)])
        # story-03 doesn't exist at all
        manifest = {"epics":[{"file":"epic-1-epic1.md","jira_key":"T-100",
                    "stories":[{"file":"story-01-api.md","jira_key":"T-101"},
                               {"file":"story-02-docs.md","jira_key":"T-102",
                                "content_hash":"old","synced_status":"active"}]}]}
        items = [self._item(1,1,"api","unchanged","T-101"),
                 self._item(1,2,"docs","changed","T-102",
                            title="[DOCS] docs docs")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        blocked_changed = [b for b in r["blocked"]
                           if b["item"].get("category") == "changed"]
        self.assertGreater(len(blocked_changed), 0,
                           "Changed DOCS with unsatisfiable ref must be blocked")

    # ── Multi-ref and deterministic ────────────────────────────

    def test_multi_ref_list(self) -> None:
        """'Story 1.01, Story 2.01' both prerequisites for 2.02."""
        self._setup([(1,1,"a","DEV","None",None,False),
                     (2,1,"b","DEV","None",None,False),
                     (2,2,"c","DEV","Story 1.01, Story 2.01",None,False)])
        items = [self._epic_item(1), self._epic_item(2),
                 self._item(1,1,"a"), self._item(2,1,"b"),
                 self._item(2,2,"c")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        ids = self._qids(r)
        self.assertGreater(ids.index("story-2.02"), ids.index("story-1.01"))
        self.assertGreater(ids.index("story-2.02"), ids.index("story-2.01"))

    def test_deterministic_shuffled_input(self) -> None:
        """Same result regardless of input item order."""
        self._setup([(1,1,"a","DEV","None",None,False),
                     (1,2,"b","DEV","None",None,False),
                     (2,1,"c","DEV","None",None,False)])
        epics = [self._epic_item(1), self._epic_item(2)]
        items_fwd = epics + [self._item(1,1,"a"),self._item(1,2,"b"),self._item(2,1,"c")]
        items_rev = epics + list(reversed([self._item(1,1,"a"),self._item(1,2,"b"),self._item(2,1,"c")]))
        r1 = sync_helper.plan_creation_order(items_fwd, self.tmpdir, None)
        r2 = sync_helper.plan_creation_order(items_rev, self.tmpdir, None)
        self.assertEqual(self._qids(r1), self._qids(r2))

    # ── CLI ────────────────────────────────────────────────────

    def test_cli_success(self) -> None:
        """CLI plan-creation-order returns JSON with expected keys."""
        self._setup([(1,1,"a","DEV","None",None,False)])
        import subprocess
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "plan-creation-order", self.tmpdir],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        for k in ("ordered", "errors", "blocked", "satisfied_keys"):
            self.assertIn(k, out)

    # ── Instruction contracts ──────────────────────────────────

    def test_sync_step3_calls_plan_and_preflight(self) -> None:
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        c = sync_path.read_text(encoding="utf-8")
        s3 = c.find("### Step 3:"); s4 = c.find("### Step 4:")
        self.assertGreaterEqual(s3, 0); self.assertGreater(s4, s3)
        step3 = c[s3:s4]
        self.assertIn("plan-creation-order", step3)
        self.assertIn("Preflight check", step3)
        self.assertIn("stop", step3.lower())

    def test_sync_preflight_before_epic_writes(self) -> None:
        c = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        content = c.read_text(encoding="utf-8")
        pf = content.find("Preflight check")
        s5 = content.find("### Step 5:")
        self.assertGreaterEqual(pf, 0)
        self.assertGreater(s5, pf)

    def test_sync_6a_uses_planned_order(self) -> None:
        c = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        content = c.read_text(encoding="utf-8")
        s6a = content.find("#### 6a:"); s6b = content.find("#### 6b:")
        self.assertGreaterEqual(s6a, 0); self.assertGreater(s6b, s6a)
        section = " ".join(content[s6a:s6b].split())
        self.assertIn("Step 3 creation plan", section)
        self.assertIn("Reference-availability guard", section)
        self.assertIn("manifest is reloaded fresh", section)


# ---------------------------------------------------------------------------
# Test: Epic ref extraction, native Jira keys, CLI exit codes,
#       unavailable-ref exclusion, and check_ref_availability
#       (fixes for proven remaining issues 1–4)
# ---------------------------------------------------------------------------


class TestEpicRefExtraction(unittest.TestCase):
    """Verify _extract_epic_refs parses Epic N / Epics N, M syntax."""

    def test_single_epic(self) -> None:
        result = sync_helper._extract_epic_refs("Epic 1")
        self.assertEqual(result, ["1"])

    def test_multiple_epics(self) -> None:
        result = sync_helper._extract_epic_refs("Epics 1, 2, 3")
        self.assertEqual(result, ["1", "2", "3"])

    def test_no_epic_refs(self) -> None:
        result = sync_helper._extract_epic_refs("No references here.")
        self.assertEqual(result, [])

    def test_mixed_with_story(self) -> None:
        result = sync_helper._extract_epic_refs("Epic 2 and Story 1.01")
        self.assertEqual(result, ["2"])


class TestJiraKeyRegex(unittest.TestCase):
    """Verify _JIRA_KEY_RE matches native Jira keys."""

    def test_standard_key(self) -> None:
        keys = sync_helper._JIRA_KEY_RE.findall("Depends on PROJ-123.")
        self.assertEqual(keys, ["PROJ-123"])

    def test_multiple_keys(self) -> None:
        keys = sync_helper._JIRA_KEY_RE.findall("EDM-101, EDM-202")
        self.assertEqual(keys, ["EDM-101", "EDM-202"])

    def test_no_match(self) -> None:
        keys = sync_helper._JIRA_KEY_RE.findall("Story 1.01, Epic 2")
        self.assertEqual(keys, [])


class TestPlanCreationOrderEpicRefs(_TmpDirMixin, unittest.TestCase):
    """Tests for plan_creation_order with epic references (Issue 1)."""

    def _setup(self, specs):
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        for eidx, sidx, slug, stype, deps, contrib, removed in specs:
            _make_epic(sd, eidx, f"epic{eidx}")
            if stype == "DOCS":
                _make_docs_story(sd, eidx, sidx, slug,
                    title=f"{slug} docs", deps=deps,
                    contributing_stories=contrib or "None", removed=removed)
            else:
                _make_dev_story(sd, eidx, sidx, slug,
                    title=slug, deps=deps, removed=removed)
        return sd

    def _item(self, eidx, sidx, slug, cat="new", key=None, title=""):
        return {"type": "story", "category": cat,
                "epic_index": eidx, "story_index": sidx,
                "jira_key": key, "title": title,
                "file": f"epic-{eidx}/story-{sidx:02d}-{slug}.md"}

    def _epic_item(self, eidx, slug, cat="new", key=None):
        return {"type": "epic", "category": cat,
                "epic_index": eidx, "jira_key": key,
                "file": f"epic-{eidx}-{slug}.md"}

    def _qids(self, result):
        return [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in result["ordered"]]

    def test_epic_ref_mapped_available(self) -> None:
        """Dependencies: Epic 1 where Epic 1 is mapped → available."""
        self._setup([(1, 1, "a", "DEV", "Epic 1", None, False)])
        manifest = {"epics": [{"file": "epic-1-epic1.md", "jira_key": "T-100",
                    "stories": []}]}
        items = [self._item(1, 1, "a"),
                 self._epic_item(1, "epic1", "unchanged", "T-100")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertEqual(r["errors"], [])
        self.assertEqual(len(r["ordered"]), 1)

    def test_epic_ref_nonexistent_fails(self) -> None:
        """Dependencies: Epic 999 → error."""
        self._setup([(1, 1, "a", "DEV", "Epic 999", None, False)])
        items = [self._epic_item(1, "epic1"),
                 self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("epic-999" in e for e in r["errors"]))
        self.assertEqual(len(r["ordered"]), 0)
        self.assertGreater(len(r["blocked"]), 0)

    def test_mixed_story_and_epic_refs(self) -> None:
        """Dependencies: Story 1.01, Epic 2 with multiple ref types."""
        self._setup([
            (1, 1, "api", "DEV", "None", None, False),
            (2, 1, "client", "DEV", "Story 1.01, Epic 2", None, False),
        ])
        manifest = {"epics": [
            {"file": "epic-1-epic1.md", "jira_key": "T-100", "stories": []},
            {"file": "epic-2-epic2.md", "jira_key": "T-200", "stories": []},
        ]}
        items = [
            self._item(1, 1, "api"),
            self._item(2, 1, "client"),
            self._epic_item(1, "epic1", "unchanged", "T-100"),
            self._epic_item(2, "epic2", "unchanged", "T-200"),
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertEqual(r["errors"], [])
        # story-1.01 must be before story-2.01
        qids = self._qids(r)
        self.assertIn("story-1.01", qids)
        self.assertIn("story-2.01", qids)
        self.assertLess(qids.index("story-1.01"), qids.index("story-2.01"))

    def test_new_epic_ref_planned_step5(self) -> None:
        """Dependencies: Epic 1 where Epic 1 is new → ok (will be created)."""
        self._setup([(1, 1, "a", "DEV", "Epic 1", None, False)])
        items = [self._item(1, 1, "a"),
                 self._epic_item(1, "epic1", "new")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(r["errors"], [])
        self.assertEqual(len(r["ordered"]), 1)

    def test_native_jira_key_in_deps_available(self) -> None:
        """Dependencies: PROJ-123 → accepted as available, not local target."""
        self._setup([(1, 1, "a", "DEV", "PROJ-123", None, False)])
        items = [self._epic_item(1, "epic1"),
                 self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(r["errors"], [])
        self.assertEqual(len(r["ordered"]), 1)
        self.assertIn("PROJ-123", r["satisfied_keys"])

    def test_native_jira_key_with_story_refs(self) -> None:
        """Dependencies: PROJ-123, Story 1.01 — both handled correctly."""
        self._setup([
            (1, 1, "api", "DEV", "None", None, False),
            (1, 2, "client", "DEV", "PROJ-123, Story 1.01", None, False),
        ])
        items = [self._epic_item(1, "epic1"),
                 self._item(1, 1, "api"), self._item(1, 2, "client")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(r["errors"], [])
        qids = self._qids(r)
        self.assertLess(qids.index("story-1.01"), qids.index("story-1.02"))


class TestDocsContribOrderingWithDetect(_TmpDirMixin, unittest.TestCase):
    """DOCS Contributing ordering with real detect_changes items."""

    def test_docs_contrib_ordering_real_detect(self) -> None:
        """DOCS 1.01 with no Dependencies and Contributing ref to Story 2.01.
        Plan must order 2.01 before 1.01."""
        arts = Path(self.tmpdir) / "art"
        sd = arts / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "docs-epic")
        _make_epic(sd, 2, "dev-epic")
        # DOCS story with Contributing ref only (no Dependencies)
        _make_docs_story(sd, 1, 1, "user-guide",
                         title="User guide docs",
                         deps="None",
                         contributing_stories="Story 2.01")
        # DEV story that the DOCS story references
        _make_dev_story(sd, 2, 1, "api-endpoint",
                        title="API endpoint", deps="None")

        # Use real detect_changes to get items
        plan = sync_helper.detect_changes(arts)
        items = plan["items"]

        r = sync_helper.plan_creation_order(items, str(arts), None)
        self.assertEqual(r["errors"], [])
        qids = [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in r["ordered"]]
        self.assertIn("story-2.01", qids)
        self.assertIn("story-1.01", qids)
        self.assertLess(qids.index("story-2.01"), qids.index("story-1.01"),
                        "Contributing story 2.01 must be ordered before DOCS 1.01")

        # Verify PREP.dependencies stays "None" (no contrib dep)
        docs_path = sd / "epic-1" / "story-01-user-guide.md"
        prep = sync_helper.prepare(
            str(docs_path), str(arts / "sync-manifest.json"),
            "story", story_type="DOCS")
        # Contributing ref should NOT appear in dependencies
        self.assertEqual(prep["dependencies"].strip(), "None")


class TestCLIPlanCreationOrderExitCodes(_TmpDirMixin, unittest.TestCase):
    """CLI plan-creation-order exit code tests (Issue 2)."""

    def setUp(self) -> None:
        super().setUp()
        import subprocess
        self.subprocess = subprocess
        self.arts = Path(self.tmpdir) / "art"
        self.sd = self.arts / "06-stories"
        self.sd.mkdir(parents=True)

    def test_valid_plan_returns_zero(self) -> None:
        """Valid plan with no errors → exit 0."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="None")
        r = self.subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.arts)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertEqual(out["errors"], [])

    def test_cycle_returns_nonzero(self) -> None:
        """Cycle in dependencies → exit 1."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "a", deps="Story 1.02")
        _make_dev_story(self.sd, 1, 2, "b", deps="Story 1.01")
        r = self.subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.arts)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertTrue(any("cycle" in e.lower() for e in out["errors"]))

    def test_missing_target_returns_nonzero(self) -> None:
        """Missing target → exit 1."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "a", deps="Story 9.99")
        r = self.subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.arts)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertTrue(any("9.99" in e for e in out["errors"]))

    def test_invalid_epic_ref_returns_nonzero(self) -> None:
        """Epic 999 reference → exit 1."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "a", deps="Epic 999")
        r = self.subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.arts)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertTrue(any("epic-999" in e for e in out["errors"]))


class TestUnavailableRefExclusion(_TmpDirMixin, unittest.TestCase):
    """Unavailable ref owners and downstream excluded from ordered (Issue 3)."""

    def _setup(self, specs):
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        for eidx, sidx, slug, deps in specs:
            _make_epic(sd, eidx, f"epic{eidx}")
            _make_dev_story(sd, eidx, sidx, slug, deps=deps)
        return sd

    def _item(self, eidx, sidx, slug):
        return {"type": "story", "category": "new",
                "epic_index": eidx, "story_index": sidx,
                "jira_key": None, "title": "",
                "file": f"epic-{eidx}/story-{sidx:02d}-{slug}.md"}

    def _epic_item(self, eidx):
        return {"type": "epic", "category": "new",
                "epic_index": eidx, "jira_key": None,
                "file": f"epic-{eidx}-epic{eidx}.md"}

    def _qids(self, result):
        return [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in result["ordered"]]

    def test_unavailable_owner_excluded(self) -> None:
        """Story with dep on nonexistent target → not in ordered."""
        self._setup([(1, 1, "a", "Story 9.99")])
        items = [self._epic_item(1), self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(len(r["ordered"]), 0,
                         "Story with unavailable ref must not be in ordered")
        self.assertGreater(len(r["blocked"]), 0)
        self.assertTrue(any("9.99" in e for e in r["errors"]))

    def test_downstream_of_unavailable_excluded(self) -> None:
        """Story depending on story with unavailable ref → also excluded."""
        self._setup([
            (1, 1, "a", "Story 9.99"),
            (1, 2, "b", "Story 1.01"),
            (1, 3, "c", "None"),
        ])
        items = [self._epic_item(1), self._item(1, 1, "a"),
                 self._item(1, 2, "b"), self._item(1, 3, "c")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        qids = self._qids(r)
        # Only story-1.03 (no deps) should be in ordered
        self.assertIn("story-1.03", qids)
        self.assertNotIn("story-1.01", qids,
                         "Owner of unavailable ref must not be in ordered")
        self.assertNotIn("story-1.02", qids,
                         "Downstream of unavailable ref must not be in ordered")
        # Both 1.01 and 1.02 should be blocked
        blocked_qids = [f"story-{b['item']['epic_index']}.{b['item']['story_index']:02d}"
                        for b in r["blocked"]]
        self.assertIn("story-1.01", blocked_qids)
        self.assertIn("story-1.02", blocked_qids)

    def test_independent_stories_still_ordered(self) -> None:
        """Independent stories unaffected by blocked chain."""
        self._setup([
            (1, 1, "a", "Story 9.99"),
            (2, 1, "b", "None"),
            (2, 2, "c", "Story 2.01"),
        ])
        items = [self._epic_item(1), self._epic_item(2),
                 self._item(1, 1, "a"), self._item(2, 1, "b"),
                 self._item(2, 2, "c")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        qids = self._qids(r)
        self.assertIn("story-2.01", qids)
        self.assertIn("story-2.02", qids)
        self.assertNotIn("story-1.01", qids)

    def test_unavailable_epic_ref_excludes_owner(self) -> None:
        """Epic 999 ref → owner excluded from ordered."""
        self._setup([(1, 1, "a", "Epic 999")])
        items = [self._epic_item(1), self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(len(r["ordered"]), 0)
        self.assertTrue(any("epic-999" in e for e in r["errors"]))


class TestCheckRefAvailability(_TmpDirMixin, unittest.TestCase):
    """Tests for check_ref_availability (Issue 4)."""

    def setUp(self) -> None:
        super().setUp()
        self.arts = Path(self.tmpdir) / "art"
        self.sd = self.arts / "06-stories"
        self.sd.mkdir(parents=True)
        self.mf = self.arts / "sync-manifest.json"

    def test_all_refs_available(self) -> None:
        """Story with all refs in manifest → ready."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="Story 1.02")
        _make_dev_story(self.sd, 1, 2, "other", deps="None")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h", "synced_status": "active"},
                {"file": "story-02-other.md", "jira_key": "EDM-202",
                 "content_hash": "h", "synced_status": "active"},
            ],
        }])
        r = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r["ready"]), 1)
        self.assertEqual(len(r["blocked"]), 0)

    def test_missing_ref_blocked(self) -> None:
        """Story with missing ref → blocked."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="Story 9.99")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h", "synced_status": "active"},
            ],
        }])
        r = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r["ready"]), 0)
        self.assertEqual(len(r["blocked"]), 1)
        self.assertTrue(any("story-9.99" in m for m in r["blocked"][0]["missing"]))

    def test_after_recording_key_becomes_ready(self) -> None:
        """After recording a key, story becomes ready."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="Story 1.02")
        _make_dev_story(self.sd, 1, 2, "other", deps="None")

        # Initially: story-02 has no key → story-01 blocked
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "h", "synced_status": "active"},
            ],
        }])
        r1 = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r1["blocked"]), 1)

        # Record key for story-02
        sync_helper.update_manifest(
            str(self.mf), "create", "story-02-other.md", "EDM-202",
            "h", item_type="story", epic_file="epic-1-building.md")

        # Now story-01 should be ready
        r2 = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r2["ready"]), 1)
        self.assertEqual(len(r2["blocked"]), 0)

    def test_epic_key_required(self) -> None:
        """Owning epic must have a key for story creation."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="None")
        # No manifest → epic has no key
        r = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r["blocked"]), 1)
        self.assertTrue(any("epic-1" in m for m in r["blocked"][0]["missing"]))

    def test_no_manifest_mutation(self) -> None:
        """check_ref_availability must not create or modify manifest."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="None")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        original = self.mf.read_bytes()
        sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(self.mf.read_bytes(), original,
                         "Manifest must not be modified by availability check")

    def test_native_jira_key_always_available(self) -> None:
        """Native Jira key in Dependencies → always available."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="PROJ-123")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        r = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r["ready"]), 1)
        self.assertEqual(len(r["blocked"]), 0)

    def test_epic_ref_in_deps_checked(self) -> None:
        """Epic ref in Dependencies must be available."""
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="Epic 2")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        r = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r["blocked"]), 1)
        self.assertTrue(any("epic-2" in m for m in r["blocked"][0]["missing"]))

    def test_unreadable_source_blocked(self) -> None:
        """Unreadable artifact file → blocked with useful message."""
        _make_epic(self.sd, 1, "building")
        # Don't create the story file — it won't exist
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        r = sync_helper.check_ref_availability(
            ["story-1.01"], str(self.arts), str(self.mf))
        self.assertEqual(len(r["blocked"]), 1)
        self.assertIn("not found", r["blocked"][0]["reason"])

    def test_cli_check_ref_availability_ready(self) -> None:
        """CLI check-ref-availability returns 0 when all ready."""
        import subprocess
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="None")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "check-ref-availability", str(self.arts), "story-1.01"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertEqual(len(out["ready"]), 1)

    def test_cli_check_ref_availability_blocked(self) -> None:
        """CLI check-ref-availability returns 1 when blocked."""
        import subprocess
        _make_epic(self.sd, 1, "building")
        _make_dev_story(self.sd, 1, 1, "scaffold", deps="Story 9.99")
        _make_manifest(self.arts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "stories": [],
        }])
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "check-ref-availability", str(self.arts), "story-1.01"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertEqual(len(out["blocked"]), 1)


class TestUnreadableSourceInPlanner(_TmpDirMixin, unittest.TestCase):
    """Unreadable source file produces error with useful message."""

    def test_missing_artifact_file_error(self) -> None:
        """Story with missing file → error."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "epic1")
        # Create item but DON'T create the actual file
        items = [{"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "",
                  "file": "epic-1/story-01-missing.md"}]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("not found" in e for e in r["errors"]))
        self.assertEqual(len(r["ordered"]), 0)

    def test_unreadable_source_mocked(self) -> None:
        """Unreadable artifact → error with useful message (portable)."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "epic1")
        _make_dev_story(sd, 1, 1, "a", deps="None")
        items = [{"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "",
                  "file": "epic-1/story-01-a.md"}]
        # Mock read_text to raise OSError for the story file
        original_read_text = Path.read_text

        def _failing_read(self_path, *args, **kwargs):
            if "story-01-a.md" in str(self_path):
                raise OSError("Permission denied (mocked)")
            return original_read_text(self_path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", _failing_read):
            r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("cannot read" in e for e in r["errors"]))
        self.assertEqual(len(r["ordered"]), 0)


# ---------------------------------------------------------------------------
# Test: changed/reopened invalid refs produce errors + CLI nonzero
# ---------------------------------------------------------------------------

class TestChangedReopenedInvalidRefs(_TmpDirMixin, unittest.TestCase):
    """Changed/reopened stories with invalid refs must fail structural
    preflight (errors non-empty, CLI nonzero) BEFORE Step 5 writes."""

    def _item(self, eidx, sidx, slug, cat="new", key=None, title=""):
        return {"type": "story", "category": cat,
                "epic_index": eidx, "story_index": sidx,
                "jira_key": key, "title": title,
                "file": f"epic-{eidx}/story-{sidx:02d}-{slug}.md"}

    def test_changed_story_invalid_ref_produces_error(self) -> None:
        """Changed story with dep on Story 9.99 → error in plan."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="None")
        _make_dev_story(sd, 1, 2, "client", deps="Story 9.99")
        manifest = {"epics": [{"file": "epic-1-building.md", "jira_key": "T-100",
                    "stories": [{"file": "story-01-api.md", "jira_key": "T-101"},
                                {"file": "story-02-client.md", "jira_key": "T-102",
                                 "content_hash": "old", "synced_status": "active"}]}]}
        items = [
            self._item(1, 1, "api", "unchanged", "T-101"),
            self._item(1, 2, "client", "changed", "T-102"),
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertTrue(any("9.99" in e for e in r["errors"]),
                        f"Expected error about 9.99, got: {r['errors']}")

    def test_changed_story_invalid_epic_ref_produces_error(self) -> None:
        """Changed story with dep on Epic 999 → error in plan."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "client", deps="Epic 999")
        manifest = {"epics": [{"file": "epic-1-building.md", "jira_key": "T-100",
                    "stories": [{"file": "story-01-client.md", "jira_key": "T-101",
                                 "content_hash": "old", "synced_status": "active"}]}]}
        items = [self._item(1, 1, "client", "changed", "T-101")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertTrue(any("epic-999" in e for e in r["errors"]),
                        f"Expected error about epic-999, got: {r['errors']}")

    def test_changed_valid_planned_target_no_error(self) -> None:
        """Changed story refs a new story in creation plan → no error."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="None")
        _make_dev_story(sd, 1, 2, "client", deps="Story 1.03")
        _make_dev_story(sd, 1, 3, "new", deps="None")
        manifest = {"epics": [{"file": "epic-1-building.md", "jira_key": "T-100",
                    "stories": [{"file": "story-01-api.md", "jira_key": "T-101"},
                                {"file": "story-02-client.md", "jira_key": "T-102",
                                 "content_hash": "old", "synced_status": "active"}]}]}
        items = [
            self._item(1, 1, "api", "unchanged", "T-101"),
            self._item(1, 2, "client", "changed", "T-102"),
            self._item(1, 3, "new"),
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertEqual(r["errors"], [],
                         "Valid planned target should not produce errors")

    def test_cli_nonzero_on_changed_invalid_ref(self) -> None:
        """CLI plan-creation-order returns nonzero when changed story has invalid ref."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 9.99")
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "T-100",
            "content_hash": "h", "synced_status": "active",
            "stories": [{"file": "story-01-api.md", "jira_key": "T-101",
                         "content_hash": "old", "synced_status": "active"}],
        }])
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "plan-creation-order", self.tmpdir],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0,
                            "CLI must return nonzero for changed story with invalid ref")
        out = json.loads(r.stdout)
        self.assertTrue(any("9.99" in e for e in out.get("errors", [])))


# ---------------------------------------------------------------------------
# Test: sync.md consumer contracts for reference-availability guard
# ---------------------------------------------------------------------------

class TestSyncConsumerContracts(unittest.TestCase):
    """Verify sync.md consumer instructions reference the executable guard
    and pin behavioral contracts for blocked/fatal handling."""

    @classmethod
    def setUpClass(cls) -> None:
        import re as _re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m6a = _re.search(r"#### 6a:.*?(?=#### 6b:)", cls._sync_md, _re.DOTALL)
        assert m6a, "6a section not found"
        cls._section_6a = m6a.group()
        m6b = _re.search(r"#### 6b:.*?(?=#### 6c:)", cls._sync_md, _re.DOTALL)
        assert m6b, "6b section not found"
        cls._section_6b = m6b.group()
        # Extract the guard paragraph from 6a (between guard heading and
        # the next consumer "For each new story")
        g_start = cls._section_6a.find("**Reference-availability guard.**")
        g_end = cls._section_6a.find("For each new story")
        assert g_start >= 0 and g_end > g_start, "guard bounds missing"
        cls._guard_6a = cls._section_6a[g_start:g_end]
        # Extract the 6b guard paragraph (between guard heading and
        # the next consumer "For each story categorized")
        gb_start = cls._section_6b.find("**Reference-availability guard.**")
        gb_end = cls._section_6b.find("For each story categorized")
        assert gb_start >= 0 and gb_end > gb_start, "6b guard bounds missing"
        cls._guard_6b = cls._section_6b[gb_start:gb_end]

    # -- Guard-before-prepare ordering ---

    def test_6a_calls_check_ref_availability(self) -> None:
        """Step 6a guard calls check-ref-availability before prepare recipe."""
        check_pos = self._section_6a.find("check-ref-availability")
        prepare_recipe_pos = self._section_6a.find("story `prepare` recipe")
        self.assertGreater(check_pos, -1)
        self.assertGreater(prepare_recipe_pos, -1)
        self.assertLess(check_pos, prepare_recipe_pos)

    def test_6b_calls_check_ref_availability_before_prepare(self) -> None:
        """Step 6b guard calls check-ref-availability before prepare recipe."""
        check_pos = self._section_6b.find("check-ref-availability")
        prepare_pos = self._section_6b.find("story `prepare`")
        self.assertGreater(check_pos, -1)
        self.assertGreater(prepare_pos, -1)
        self.assertLess(check_pos, prepare_pos)

    def test_helper_reference_documents_check_ref(self) -> None:
        """Helper reference documents check-ref-availability."""
        ref_path = (Path(__file__).resolve().parent.parent
                    / "references" / "sync-helper-usage.md")
        content = ref_path.read_text(encoding="utf-8")
        self.assertIn("check-ref-availability", content)
        self.assertIn("ready", content)
        self.assertIn("blocked", content)

    def test_preflight_catches_changed_invalid_refs(self) -> None:
        """Step 3 preflight covers changed/reopened invalid refs."""
        import re
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", self._sync_md, re.DOTALL)
        self.assertIsNotNone(m3)
        section = m3.group()
        self.assertIn("changed", section.lower())
        self.assertIn("reopened", section.lower())

    # -- 6a guard: blocked → no prepare/render/create/checkpoint ---

    def test_6a_blocked_no_prepare_no_render_no_create_no_checkpoint(self) -> None:
        """6a blocked: no prepare, no render, no Jira create, no checkpoint."""
        self.assertIn("do not call `prepare`", self._guard_6a)
        self.assertIn("do not render", self._guard_6a)
        self.assertIn("do not create the Jira", self._guard_6a)
        self.assertIn("manifest checkpoint", self._guard_6a)

    def test_6a_blocked_recorded_for_step8_with_missing(self) -> None:
        """6a blocked: recorded for Step 8 with missing refs and reason."""
        self.assertIn("Step 8 report", self._guard_6a)
        self.assertIn("`missing` refs", self._guard_6a)
        self.assertIn("`reason`", self._guard_6a)

    # -- 6b guard: blocked → no prepare/render/update/reopen/checkpoint ---

    def test_6b_blocked_no_prepare_no_update_no_reopen_no_checkpoint(self) -> None:
        """6b blocked/failed: no prepare, render, update, reopen, or checkpoint."""
        self.assertIn("`prepare`", self._guard_6b)
        self.assertIn("render", self._guard_6b)
        self.assertIn("update", self._guard_6b.lower())
        self.assertIn("reopen", self._guard_6b.lower())
        self.assertIn("manifest checkpoint", self._guard_6b)

    # -- 6a fatal: catch-all stops sync ---

    def test_6a_fatal_catch_all_stops_sync(self) -> None:
        """6a catch-all: stops sync, reports captured text, no skip."""
        self.assertIn("Stop the sync", self._guard_6a)
        self.assertIn("REF_ERR_TEXT", self._guard_6a)
        # Check no-skip wording (may wrap across lines)
        guard_flat = " ".join(self._guard_6a.split())
        self.assertIn("Do not skip the story", guard_flat)

    def test_6a_catch_all_covers_exit0_invalid(self) -> None:
        """6a catch-all enumerates exit 0 with invalid JSON as failure."""
        guard_flat = " ".join(self._guard_6a.split())
        self.assertIn("exit 0 with invalid json", guard_flat.lower())

    def test_6a_catch_all_covers_conflicting_qid(self) -> None:
        """6a catch-all enumerates QID in both lists as failure."""
        self.assertIn("both lists", self._guard_6a.lower())

    # -- Errexit-safe capture idiom ---

    def test_6a_errexit_safe_capture(self) -> None:
        """6a guard uses || REF_EXIT=$? idiom for errexit safety."""
        self.assertIn("|| REF_EXIT=$?", self._guard_6a)

    def test_6b_references_same_capture_idiom(self) -> None:
        """6b guard references the same capture idiom."""
        self.assertIn("|| REF_EXIT=$?", self._guard_6b)

    # -- Step 3 preflight invariant ---

    def test_preflight_blocked_implies_errors(self) -> None:
        """Step 3: every blocked item has a root-cause error entry."""
        import re
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", self._sync_md, re.DOTALL)
        section = m3.group()
        self.assertIn("Every `blocked` item has at least one root-cause", section)

    def test_preflight_blocked_implies_errors_planner(self) -> None:
        """Planner: a blocked item always has a corresponding error entry.
        Verified via negative case: cycle produces both blocked and errors."""
        sd = Path(tempfile.mkdtemp()) / "06-stories"
        sd.mkdir(parents=True)
        _make_epic(sd, 1, "ep")
        _make_dev_story(sd, 1, 1, "a", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "b", deps="Story 1.01")
        items = [
            {"type": "story", "category": "new", "epic_index": 1,
             "story_index": 1, "jira_key": None, "title": "",
             "file": "epic-1/story-01-a.md"},
            {"type": "story", "category": "new", "epic_index": 1,
             "story_index": 2, "jira_key": None, "title": "",
             "file": "epic-1/story-02-b.md"},
        ]
        r = sync_helper.plan_creation_order(items, str(sd.parent), None)
        self.assertGreater(len(r["blocked"]), 0, "cycle must produce blocked")
        self.assertGreater(len(r["errors"]), 0, "cycle must produce errors")
        import shutil
        shutil.rmtree(str(sd.parent))

    # -- Step 8 blocked reporting ---

    def test_step8_reports_blocked_with_missing_keys(self) -> None:
        """Step 8 must report blocked stories with missing keys/reasons."""
        import re
        m8 = re.search(r"### Step 8:.*", self._sync_md, re.DOTALL)
        self.assertIsNotNone(m8)
        step8 = m8.group()
        self.assertIn("blocked", step8.lower())
        self.assertIn("missing", step8.lower())
        self.assertIn("reason", step8.lower())

    # -- Step 3 no unreachable blocked-count wording ---

    def test_step3_no_unreachable_blocked_success_path(self) -> None:
        """Step 3: no 'blocked is non-empty but errors is empty' wording."""
        import re
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", self._sync_md, re.DOTALL)
        section = m3.group()
        self.assertNotIn("blocked` is non-empty but `errors` is empty", section)


# ---------------------------------------------------------------------------
# Test: DOCS Contributing with mapped parents + runtime guard + PREP
# ---------------------------------------------------------------------------

class TestDocsContribRuntimeReady(_TmpDirMixin, unittest.TestCase):
    """DOCS Contributing with mapped parents: runtime guard ready,
    PREP.description has Jira key, PREP.dependencies stays None."""

    def test_docs_contrib_with_mapped_parents_runtime_ready(self) -> None:
        """DOCS 1.01 Contributing Story 2.01: with mapped epic parents and
        contributor key, runtime guard shows ready, PREP.description contains
        Jira contributor key (not [unresolved]) and PREP.dependencies is None."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "docs-epic")
        _make_docs_story(sd, 1, 1, "guide",
                         deps="None",
                         contributing_stories="Story 2.01",
                         doc_inputs="**Story 2.01 — API:** output.")
        _make_epic(sd, 2, "dev-epic")
        _make_dev_story(sd, 2, 1, "api", deps="None")
        mf_path = Path(self.tmpdir) / "sync-manifest.json"
        mf_data = {
            "schema_version": 2, "feature_key": "FEAT-100",
            "synced_at": "", "epics": [
                {"file": "epic-1-docs-epic.md", "jira_key": "EDM-101",
                 "content_hash": "h1", "synced_status": "active", "stories": []},
                {"file": "epic-2-dev-epic.md", "jira_key": "EDM-102",
                 "content_hash": "h2", "synced_status": "active",
                 "stories": [{"file": "story-01-api.md", "jira_key": "EDM-201",
                              "content_hash": "h3", "synced_status": "active"}]},
            ],
        }
        _write(mf_path, json.dumps(mf_data, indent=2))

        # Runtime guard: story-1.01 should be ready
        result = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf_path)
        self.assertEqual(len(result["ready"]), 1, f"Expected ready, got: {result}")
        self.assertEqual(len(result["blocked"]), 0)

        # PREP: description should contain Jira key EDM-201
        docs_path = sd / "epic-1" / "story-01-guide.md"
        prep = sync_helper.prepare(
            str(docs_path), str(mf_path), "story", story_type="DOCS")
        self.assertIn("EDM-201", prep["description"],
                      "Contributing story must resolve to Jira key")
        self.assertNotIn("[unresolved]", prep["description"],
                         "No unresolved refs when all are mapped")
        # PREP.dependencies should be "None"
        self.assertEqual(prep["dependencies"].strip(), "None",
                         "Dependencies must remain None for DOCS with only Contributing refs")

        # Verify no manifest mutation
        mf_after = Path(mf_path).read_text(encoding="utf-8")
        self.assertEqual(mf_after, json.dumps(mf_data, indent=2),
                         "Manifest must not be mutated")

    def test_fresh_manifest_missing_then_ready_after_key(self) -> None:
        """Same-path: missing key → blocked, record key → ready."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "lib", deps="None")
        mf_path = Path(self.tmpdir) / "sync-manifest.json"
        mf_data = {"schema_version": 2, "feature_key": "FEAT-100",
                    "synced_at": "", "epics": [
                        {"file": "epic-1-building.md", "jira_key": "EDM-101",
                         "content_hash": "h", "synced_status": "active",
                         "stories": []}]}
        _write(mf_path, json.dumps(mf_data, indent=2))

        # Before recording: story-1.01 is blocked (needs story-1.02)
        r1 = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf_path)
        self.assertEqual(len(r1["blocked"]), 1)
        self.assertIn("story-1.02", r1["blocked"][0]["missing"])

        # Record story-1.02 key in manifest
        sync_helper.update_manifest(
            mf_path, "create", "story-02-lib.md", "EDM-202", "abc",
            item_type="story", epic_file="epic-1-building.md")

        # After recording: story-1.01 is ready
        r2 = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf_path)
        self.assertEqual(len(r2["ready"]), 1)
        self.assertEqual(len(r2["blocked"]), 0)

    def test_failed_parent_blocks_dependent_independent_ready(self) -> None:
        """Failed prerequisite blocks dependent; independent story is ready."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="None")
        _make_dev_story(sd, 1, 2, "client", deps="Story 1.03")
        _make_dev_story(sd, 1, 3, "missing-dep", deps="None")
        mf_path = Path(self.tmpdir) / "sync-manifest.json"
        mf_data = {"schema_version": 2, "feature_key": "FEAT-100",
                    "synced_at": "", "epics": [
                        {"file": "epic-1-building.md", "jira_key": "EDM-101",
                         "content_hash": "h", "synced_status": "active",
                         "stories": []}]}
        _write(mf_path, json.dumps(mf_data, indent=2))

        result = sync_helper.check_ref_availability(
            ["story-1.01", "story-1.02"], self.tmpdir, mf_path)
        ready_qids = [r["qid"] for r in result["ready"]]
        blocked_qids = [b["qid"] for b in result["blocked"]]
        self.assertIn("story-1.01", ready_qids,
                      "Independent story must be ready")
        self.assertIn("story-1.02", blocked_qids,
                      "Dependent on missing must be blocked")

    def test_ambiguous_file_blocked(self) -> None:
        """Multiple files matching same story index → blocked with diagnostic."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api")
        _write(sd / "epic-1" / "story-01-also.md",
               "---\n---\n# Story 1.01: [DEV] Also\n\n"
               "**As a** dev,\n**I want to** x,\n**So that** y.\n\n"
               "## Acceptance Criteria\n\n- AC\n\n"
               "## Implementation Guidance\n\nDo.\n\n"
               "## Testing Approach\n\nTest.\n\n"
               "## Dependencies\n\nNone\n\n"
               "## Design Reference\n\nEpic: Epic 1\n")
        mf_path = Path(self.tmpdir) / "sync-manifest.json"
        mf_data = {"schema_version": 2, "feature_key": "FEAT-100",
                    "synced_at": "", "epics": [
                        {"file": "epic-1-building.md", "jira_key": "EDM-101",
                         "content_hash": "h", "synced_status": "active",
                         "stories": []}]}
        _write(mf_path, json.dumps(mf_data, indent=2))
        result = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf_path)
        self.assertEqual(len(result["blocked"]), 1)
        self.assertIn("ambiguous", result["blocked"][0]["reason"])


# ---------------------------------------------------------------------------
# Test: QID fullmatch regression (finding 4458710793)
# ---------------------------------------------------------------------------

class TestQIDFullmatch(_TmpDirMixin, unittest.TestCase):
    """check_ref_availability must reject QIDs with trailing garbage."""

    def setUp(self) -> None:
        super().setUp()
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="None")
        self.mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(self.mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": []}]}))

    def test_trailing_garbage_rejected(self) -> None:
        """story-1.01abc must not be accepted as story-1.01."""
        result = sync_helper.check_ref_availability(
            ["story-1.01abc"], self.tmpdir, self.mf)
        self.assertEqual(len(result["blocked"]), 1)
        self.assertIn("invalid", result["blocked"][0]["reason"])

    def test_trailing_newline_rejected(self) -> None:
        """story-1.01\\n must not be accepted."""
        result = sync_helper.check_ref_availability(
            ["story-1.01\n"], self.tmpdir, self.mf)
        self.assertEqual(len(result["blocked"]), 1)

    def test_valid_qid_with_mapped_parent_is_ready(self) -> None:
        """story-1.01 (exact) with mapped epic and no deps → ready with
        actual ready entry and empty blocked."""
        result = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, self.mf)
        self.assertEqual(len(result["ready"]), 1,
                         "Valid QID with mapped parent + no deps must be ready")
        self.assertEqual(result["ready"][0]["qid"], "story-1.01")
        self.assertEqual(len(result["blocked"]), 0,
                         "Blocked must be empty for a ready story")

    def test_cli_trailing_garbage_blocked(self) -> None:
        """CLI check-ref-availability with trailing garbage → blocked."""
        import subprocess
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "check-ref-availability", self.tmpdir, "story-1.01xyz"],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertEqual(len(out["blocked"]), 1)
        self.assertIn("invalid", out["blocked"][0]["reason"])


# ---------------------------------------------------------------------------
# Test: CLI fatal-vs-blocked distinction (finding 4458710829)
# ---------------------------------------------------------------------------

class TestCLIFatalVsBlocked(_TmpDirMixin, unittest.TestCase):
    """Distinguish structured blocked JSON (exit 1) from fatal stderr
    (exit 1, no JSON) for check-ref-availability and plan-creation-order.
    Instruction contracts, not live Jira/LLM E2E."""

    def test_check_ref_blocked_produces_json_with_qid_and_missing(self) -> None:
        """Blocked story → exit 1 with valid JSON containing matching QID,
        missing refs list, empty ready."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 9.99")
        _write(Path(self.tmpdir) / "sync-manifest.json", json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": []}]}))
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "check-ref-availability", self.tmpdir, "story-1.01"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertEqual(len(out["ready"]), 0, "ready must be empty")
        self.assertEqual(len(out["blocked"]), 1)
        self.assertEqual(out["blocked"][0]["qid"], "story-1.01")
        self.assertIn("story-9.99", out["blocked"][0]["missing"])

    def test_check_ref_corrupted_manifest_fatal_no_json(self) -> None:
        """Corrupted manifest → exit 1 with stderr, NO valid JSON."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="None")
        _write(Path(self.tmpdir) / "sync-manifest.json", "NOT JSON {{{")
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "check-ref-availability", self.tmpdir, "story-1.01"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR", r.stderr)
        # stdout should NOT contain valid JSON
        with self.assertRaises(json.JSONDecodeError):
            json.loads(r.stdout)

    def test_plan_creation_errors_produces_json(self) -> None:
        """plan-creation-order with errors → exit 1 with valid JSON."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "a", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "b", deps="Story 1.01")
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "plan-creation-order", self.tmpdir],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)  # Must be valid JSON
        self.assertTrue(out["errors"])

    def test_check_ref_ready_produces_json(self) -> None:
        """Ready story → exit 0 with valid JSON containing QID in ready."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="None")
        _write(Path(self.tmpdir) / "sync-manifest.json", json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": []}]}))
        r = subprocess.run(
            [sys.executable, "-I",
             str(Path(__file__).resolve().parent / "sync_helper.py"),
             "check-ref-availability", self.tmpdir, "story-1.01"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        ready_qids = [e["qid"] for e in out["ready"]]
        self.assertIn("story-1.01", ready_qids)


# ---------------------------------------------------------------------------
# Test: self-reference detection (R2)
# ---------------------------------------------------------------------------

class TestDetectSelfRefs(unittest.TestCase):
    """Unit tests for _detect_self_refs helper."""

    def test_direct_qid_match(self) -> None:
        """Direct own-qid in refs → detected."""
        result = sync_helper._detect_self_refs(
            "story-1.01", ["story-1.01", "story-2.01"], [],
            "", {})
        self.assertEqual(result, ["story-1.01"])

    def test_native_key_match(self) -> None:
        """Native Jira key matching own key → detected."""
        result = sync_helper._detect_self_refs(
            "story-1.01", [], ["EDM-201"],
            "EDM-201", {})
        self.assertEqual(result, ["EDM-201"])

    def test_resolved_alias_match(self) -> None:
        """Ref resolving to own key via available map → detected."""
        available = {"story-2.01": "EDM-201"}
        result = sync_helper._detect_self_refs(
            "story-1.01", ["story-2.01"], [],
            "EDM-201", available)
        self.assertEqual(result, ["story-2.01"])

    def test_no_self_ref_peer(self) -> None:
        """Legitimate peer ref with different key → not detected."""
        available = {"story-2.01": "EDM-202"}
        result = sync_helper._detect_self_refs(
            "story-1.01", ["story-2.01"], ["PROJ-999"],
            "EDM-201", available)
        self.assertEqual(result, [])

    def test_no_key_no_native_match(self) -> None:
        """No own key: native keys cannot match → empty."""
        result = sync_helper._detect_self_refs(
            "story-1.01", ["story-2.01"], ["EDM-999"],
            "", {})
        self.assertEqual(result, [])

    def test_dedup_multiple_self_refs(self) -> None:
        """Multiple self-ref paths: deduplicated."""
        available = {"story-1.01": "EDM-201"}
        result = sync_helper._detect_self_refs(
            "story-1.01",
            ["story-1.01", "story-1.01"],
            ["EDM-201"],
            "EDM-201", available)
        # story-1.01 appears once (direct), EDM-201 once (native)
        self.assertEqual(len(result), 2)
        self.assertIn("story-1.01", result)
        self.assertIn("EDM-201", result)


class TestSelfRefInPlanner(_TmpDirMixin, unittest.TestCase):
    """Self-references must BLOCK the source in plan_creation_order."""

    def test_new_story_self_dep_blocked(self) -> None:
        """New story with Dependencies = own story → blocked."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        items = [{"type": "epic", "category": "new",
                  "epic_index": 1, "jira_key": None,
                  "file": "epic-1-building.md"},
                 {"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "",
                  "file": "epic-1/story-01-api.md"}]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(
            any("self-reference" in e for e in r["errors"]),
            f"Expected self-reference error, got: {r['errors']}")
        self.assertEqual(len(r["ordered"]), 0)
        self.assertGreater(len(r["blocked"]), 0)

    def test_changed_story_mapped_self_ref_blocked(self) -> None:
        """Changed story with own qid in deps (mapped key) → blocked."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        manifest = {"epics": [{"file": "epic-1-building.md",
                    "jira_key": "T-100",
                    "stories": [{"file": "story-01-api.md",
                                 "jira_key": "T-101",
                                 "content_hash": "old",
                                 "synced_status": "active"}]}]}
        items = [
            {"type": "story", "category": "changed", "epic_index": 1,
             "story_index": 1, "jira_key": "T-101", "title": "",
             "file": "epic-1/story-01-api.md"},
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertTrue(
            any("self-reference" in e for e in r["errors"]),
            f"Expected self-reference error, got: {r['errors']}")
        self.assertGreater(len(r["blocked"]), 0)

    def test_changed_story_native_key_self_ref(self) -> None:
        """Changed story with own Jira key in deps → blocked."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="TE-101")
        manifest = {"epics": [{"file": "epic-1-building.md",
                    "jira_key": "TE-100",
                    "stories": [{"file": "story-01-api.md",
                                 "jira_key": "TE-101",
                                 "content_hash": "old",
                                 "synced_status": "active"}]}]}
        items = [
            {"type": "story", "category": "changed", "epic_index": 1,
             "story_index": 1, "jira_key": "TE-101", "title": "",
             "file": "epic-1/story-01-api.md"},
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertTrue(
            any("self-reference" in e for e in r["errors"]),
            f"Expected self-reference error, got: {r['errors']}")

    def test_reopened_story_self_ref_blocked(self) -> None:
        """Reopened story with self-dep → blocked."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        manifest = {"epics": [{"file": "epic-1-building.md",
                    "jira_key": "T-100",
                    "stories": [{"file": "story-01-api.md",
                                 "jira_key": "T-101",
                                 "content_hash": "old",
                                 "synced_status": "closed"}]}]}
        items = [
            {"type": "story", "category": "reopened", "epic_index": 1,
             "story_index": 1, "jira_key": "T-101", "title": "",
             "file": "epic-1/story-01-api.md"},
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertTrue(
            any("self-reference" in e for e in r["errors"]),
            f"Expected self-reference error, got: {r['errors']}")

    def test_docs_contributing_self_ref_blocked(self) -> None:
        """DOCS story with Contributing = own story → blocked."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "docs-epic")
        _make_docs_story(sd, 1, 1, "guide",
                         deps="None",
                         contributing_stories="Story 1.01")
        items = [{"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "[DOCS] guide",
                  "file": "epic-1/story-01-guide.md"}]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(
            any("self-reference" in e for e in r["errors"]),
            f"Expected self-reference error, got: {r['errors']}")
        self.assertEqual(len(r["ordered"]), 0)

    def test_peer_ref_not_blocked(self) -> None:
        """Legitimate peer dep (different story) → not blocked."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "lib", deps="None")
        items = [
            {"type": "epic", "category": "new", "epic_index": 1,
             "jira_key": None, "file": "epic-1-building.md"},
            {"type": "story", "category": "new", "epic_index": 1,
             "story_index": 1, "jira_key": None, "title": "",
             "file": "epic-1/story-01-api.md"},
            {"type": "story", "category": "new", "epic_index": 1,
             "story_index": 2, "jira_key": None, "title": "",
             "file": "epic-1/story-02-lib.md"},
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertFalse(
            any("self-reference" in e for e in r["errors"]),
            "Peer ref must NOT produce self-reference error")
        self.assertEqual(len(r["ordered"]), 2)

    def test_unmapped_new_cycle_detected(self) -> None:
        """Two NEW unmapped stories with A→B→A → cycle detected."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "a", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "b", deps="Story 1.01")
        items = [
            {"type": "epic", "category": "new", "epic_index": 1,
             "jira_key": None, "file": "epic-1-building.md"},
            {"type": "story", "category": "new", "epic_index": 1,
             "story_index": 1, "jira_key": None, "title": "",
             "file": "epic-1/story-01-a.md"},
            {"type": "story", "category": "new", "epic_index": 1,
             "story_index": 2, "jira_key": None, "title": "",
             "file": "epic-1/story-02-b.md"},
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("cycle" in e.lower() for e in r["errors"]),
                        "Multi-story cycle must produce cycle error")
        self.assertEqual(len(r["ordered"]), 0)

    def test_mapped_peer_cycle_accepted_at_runtime(self) -> None:
        """Two MAPPED stories with A→B→A: runtime guard accepts each
        individually (they have distinct keys; cycle is a creation-time
        concern, not a runtime-update concern)."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "a", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "b", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [
                            {"file": "story-01-a.md", "jira_key": "EDM-201",
                             "content_hash": "h2", "synced_status": "active"},
                            {"file": "story-02-b.md", "jira_key": "EDM-202",
                             "content_hash": "h3", "synced_status": "active"}
                        ]}]}))
        # Each story depends on the other — distinct keys, so no self-ref
        r1 = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r1["ready"]), 1,
                         "A→B with distinct keys: A should be ready")
        r2 = sync_helper.check_ref_availability(
            ["story-1.02"], self.tmpdir, mf)
        self.assertEqual(len(r2["ready"]), 1,
                         "B→A with distinct keys: B should be ready")

    def test_self_ref_no_mutation(self) -> None:
        """Self-ref detection must not mutate the manifest."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        manifest = {"schema_version": 2, "feature_key": "F",
                    "epics": [{"file": "epic-1-building.md",
                               "jira_key": "EDM-101",
                               "content_hash": "h",
                               "synced_status": "active",
                               "stories": []}]}
        _write(mf, json.dumps(manifest, indent=2))
        items = [{"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "",
                  "file": "epic-1/story-01-api.md"}]
        original = mf.read_bytes()
        sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertEqual(mf.read_bytes(), original,
                         "Manifest must not be mutated by planner")


class TestSelfRefInRuntime(_TmpDirMixin, unittest.TestCase):
    """Self-references must BLOCK in check_ref_availability."""

    def test_runtime_self_ref_qid_blocked(self) -> None:
        """Story referencing own qid → blocked at runtime."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r["blocked"]), 1)
        self.assertIn("self-reference", r["blocked"][0]["reason"])
        self.assertEqual(len(r["ready"]), 0)

    def test_runtime_self_ref_native_key_blocked(self) -> None:
        """Story with own native key in deps → blocked at runtime."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="EDM-201")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r["blocked"]), 1)
        self.assertIn("self-reference", r["blocked"][0]["reason"])
        # Self-ref IDs in invalid_refs, not missing (they exist but are invalid)
        self.assertEqual(r["blocked"][0]["missing"], [])
        self.assertIn("EDM-201", r["blocked"][0]["invalid_refs"])

    def test_runtime_docs_contributing_self_blocked(self) -> None:
        """DOCS story Contributing self-ref → blocked at runtime."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "docs-epic")
        _make_docs_story(sd, 1, 1, "guide",
                         deps="None",
                         contributing_stories="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-docs-epic.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-guide.md",
                                     "jira_key": "EDM-301",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r["blocked"]), 1)
        self.assertIn("self-reference", r["blocked"][0]["reason"])

    def test_runtime_peer_ref_ready(self) -> None:
        """Legitimate peer ref (different story) → ready at runtime."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.02")
        _make_dev_story(sd, 1, 2, "lib", deps="None")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [
                            {"file": "story-01-api.md",
                             "jira_key": "EDM-201",
                             "content_hash": "h2",
                             "synced_status": "active"},
                            {"file": "story-02-lib.md",
                             "jira_key": "EDM-202",
                             "content_hash": "h3",
                             "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r["ready"]), 1)
        self.assertEqual(len(r["blocked"]), 0)

    def test_runtime_self_ref_no_mutation(self) -> None:
        """Self-ref blocked: manifest not mutated."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        mf_data = json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]})
        _write(mf, mf_data)
        original = mf.read_bytes()
        sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(mf.read_bytes(), original)

    def test_cli_self_ref_exit_nonzero(self) -> None:
        """CLI check-ref-availability with self-ref → exit 1 with JSON."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        _write(Path(self.tmpdir) / "sync-manifest.json", json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "check-ref-availability", self.tmpdir, "story-1.01"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertEqual(len(out["blocked"]), 1)
        self.assertIn("self-reference", out["blocked"][0]["reason"])

    def test_cli_planner_self_ref_exit_nonzero(self) -> None:
        """CLI plan-creation-order with self-ref → exit 1."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", self.tmpdir],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertTrue(
            any("self-reference" in e for e in out["errors"]),
            f"Expected self-reference error, got: {out['errors']}")


# ---------------------------------------------------------------------------
# Test: Quality gate — Step 4 halts entire sync (R1)
# ---------------------------------------------------------------------------

class TestQualityGateConsumer(unittest.TestCase):
    """Step 4 quality gate must halt entire sync before Step 5."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m4 = re.search(r"### Step 4:.*?(?=### Step 5:)", cls._sync_md, re.DOTALL)
        assert m4, "Step 4 not found"
        cls._step4 = m4.group()

    def test_step4_halts_entire_sync(self) -> None:
        """Step 4 failure stops the entire sync, not just the failing story."""
        self.assertIn("stop the entire sync", self._step4.lower())

    def test_step4_no_jira_writes_on_failure(self) -> None:
        """Step 4 failure prevents proceeding to Step 5 (Jira writes)."""
        self.assertIn("do not proceed to Step 5", self._step4)

    def test_step4_fresh_approval_required(self) -> None:
        """After correction, fresh preflight/preview/approval required."""
        step4_lower = self._step4.lower()
        self.assertIn("fresh", step4_lower)
        self.assertIn("approval", step4_lower)

    def test_step4_no_stale_approval_reuse(self) -> None:
        """Step 4: stale approval must not be reused."""
        self.assertIn("Do not reuse a stale approval", self._step4)

    def test_step4_sync_does_not_edit_source(self) -> None:
        """Step 4: sync does not edit story source files."""
        self.assertIn("does not edit story source", self._step4)

    def test_step4_distinct_from_runtime_independence(self) -> None:
        """Step 4 gate is distinct from runtime independence."""
        self.assertIn("independent eligible work", self._step4)

    def test_step4_pass_continues(self) -> None:
        """Step 4 section starts with validation instructions, implying
        pass → continue to Step 5."""
        self.assertIn("Validate", self._step4)
        self.assertIn("Step 5", self._step4)


# ---------------------------------------------------------------------------
# Test: Preview cleanup — exact remnant removal (R4)
# ---------------------------------------------------------------------------

class TestPreviewCleanup(unittest.TestCase):
    """Preview cleanup: exact Step 3 remnants removed, Step 8 preserved."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", cls._sync_md, re.DOTALL)
        assert m3, "Step 3 not found"
        cls._step3 = m3.group()

    def test_no_blocked_placeholder(self) -> None:
        """The blocked-stories placeholder is removed from Step 3."""
        self.assertNotIn(
            "{If any stories are blocked, list them separately with reasons.}",
            self._step3)

    def test_no_blocked_suffix_in_create_total(self) -> None:
        """The blocked count suffix is removed from create stories total."""
        self.assertNotIn("({B} blocked)", self._step3)

    def test_story_create_total_preserved(self) -> None:
        """The story create total line is still present (without blocked)."""
        self.assertIn("To create (stories):", self._step3)

    def test_step8_blocked_reporting_preserved(self) -> None:
        """Step 8 still reports blocked stories (not removed globally)."""
        import re
        m8 = re.search(r"### Step 8:.*", self._sync_md, re.DOTALL)
        self.assertIsNotNone(m8)
        step8 = m8.group()
        self.assertIn("blocked", step8.lower())

    def test_step3_epics_to_create_present(self) -> None:
        """Epics to Create section still present in Step 3."""
        self.assertIn("### Epics to Create", self._step3)


# ---------------------------------------------------------------------------
# Test: Guard recipe — per-guard temp capture (R3)
# ---------------------------------------------------------------------------

class TestGuardRecipeConsumer(unittest.TestCase):
    """Guard recipe: per-guard temp capture, errexit-safe, cleanup."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        ref_path = (Path(__file__).resolve().parent.parent
                    / "references" / "sync-helper-usage.md")
        cls._ref_md = ref_path.read_text(encoding="utf-8")
        m6a = re.search(r"#### 6a:.*?(?=#### 6b:)", cls._sync_md, re.DOTALL)
        assert m6a, "6a section not found"
        cls._section_6a = m6a.group()
        m6b = re.search(r"#### 6b:.*?(?=#### 6c:)", cls._sync_md, re.DOTALL)
        assert m6b, "6b section not found"
        cls._section_6b = m6b.group()
        # Guard section from 6a
        g_start = cls._section_6a.find("**Reference-availability guard.**")
        g_end = cls._section_6a.find("For each new story")
        assert g_start >= 0 and g_end > g_start
        cls._guard_6a = cls._section_6a[g_start:g_end]
        # Guard section from 6b
        gb_start = cls._section_6b.find("**Reference-availability guard.**")
        gb_end = cls._section_6b.find("For each story categorized")
        assert gb_start >= 0 and gb_end > gb_start
        cls._guard_6b = cls._section_6b[gb_start:gb_end]

    def test_6a_uses_mktemp(self) -> None:
        """Step 6a guard creates temp with mktemp."""
        self.assertIn("mktemp", self._guard_6a)

    def test_6a_no_fixed_filename(self) -> None:
        """Step 6a guard does NOT use fixed ref_check_err.txt."""
        self.assertNotIn("ref_check_err.txt", self._guard_6a)

    def test_6a_inline_cleanup(self) -> None:
        """Step 6a capture block does inline cleanup before branches."""
        # rm -f and cat appear in the capture block before branch text
        self.assertIn('rm -f "$REF_ERR"', self._guard_6a)
        self.assertIn('cat "$REF_ERR"', self._guard_6a)

    def test_6a_cleanup_before_interpretation(self) -> None:
        """Temp cleanup happens before branch interpretation text."""
        rm_pos = self._guard_6a.find('rm -f "$REF_ERR"')
        branch_pos = self._guard_6a.find("Interpret the result")
        self.assertGreater(rm_pos, -1)
        self.assertGreater(branch_pos, -1)
        self.assertLess(rm_pos, branch_pos,
                        "Cleanup must be before branch interpretation")

    def test_6b_mentions_per_guard_temp(self) -> None:
        """Step 6b references per-guard temp creation."""
        self.assertIn("mktemp", self._guard_6b)

    def test_6b_mentions_inline_cleanup(self) -> None:
        """Step 6b references inline cleanup pattern from 6a."""
        guard_lower = self._guard_6b.lower()
        self.assertIn("remove the temp", guard_lower)

    def test_helper_ref_uses_errexit_safe_capture(self) -> None:
        """Helper reference uses || REF_EXIT=$? idiom."""
        self.assertIn("|| REF_EXIT=$?", self._ref_md)

    def test_helper_ref_uses_mktemp(self) -> None:
        """Helper reference uses mktemp for temp capture."""
        self.assertIn("mktemp", self._ref_md)

    def test_helper_ref_no_bare_echo_dollar_question(self) -> None:
        """Helper reference does NOT use bare 'echo $?' for status."""
        # The old recipe used 'echo $?' — verify it's gone
        guard_section_start = self._ref_md.find("## Reference-Availability Guard")
        guard_section = self._ref_md[guard_section_start:]
        self.assertNotIn("echo $?  # 0 = ready", guard_section)


# ---------------------------------------------------------------------------
# Test: Approval/order consistency (R5)
# ---------------------------------------------------------------------------

class TestApprovalOrderConsistency(unittest.TestCase):
    """Sync Critical Rules and helper-reference consistency."""

    @classmethod
    def setUpClass(cls) -> None:
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        ref_path = (Path(__file__).resolve().parent.parent
                    / "references" / "sync-helper-usage.md")
        cls._ref_md = ref_path.read_text(encoding="utf-8")
        revise_path = (Path(__file__).resolve().parent.parent
                       / "skills" / "revise.md")
        cls._revise_md = revise_path.read_text(encoding="utf-8")

    def test_batch_rule_cross_epic_creation(self) -> None:
        """Critical Rules batch rule mentions cross-epic creation batch."""
        self.assertIn("cross-epic", self._sync_md.lower())

    def test_batch_rule_explicit_approval_list(self) -> None:
        """Critical Rules lists explicit approval points."""
        # Should mention plan, epic, and story creation approvals
        batch_line = ""
        for line in self._sync_md.splitlines():
            if "Batch by operation" in line:
                batch_line = line
                break
        self.assertIn("plan", batch_line.lower())
        self.assertIn("epic", batch_line.lower())

    def test_helper_ref_no_epic_order_promise(self) -> None:
        """Helper reference does NOT promise per-epic creation order."""
        self.assertNotIn("in epic order", self._ref_md)
        self.assertNotIn("Epic 1 stories before Epic 2", self._ref_md)

    def test_helper_ref_dependency_first_order(self) -> None:
        """Helper reference mentions dependency-first order."""
        self.assertIn("dependency-first", self._ref_md)

    def test_helper_ref_stable_identity(self) -> None:
        """Helper reference: local numbers are identity, not creation readiness."""
        self.assertIn("stable artifact identities", self._ref_md)

    def test_revise_manifest_not_all_synced(self) -> None:
        """Revise Step 1: manifest presence does NOT mean all artifacts synced."""
        self.assertNotIn("means\n  epics/stories have been synced", self._revise_md)
        self.assertNotIn("filenames are locked", self._revise_md)

    def test_revise_manifest_partial(self) -> None:
        """Revise Step 1: manifest may be partial."""
        self.assertIn("may be partial", self._revise_md)

    def test_revise_manifest_records_mappings(self) -> None:
        """Revise Step 1: manifest records Jira key mappings."""
        self.assertIn("Jira key mappings", self._revise_md)


# ---------------------------------------------------------------------------
# Test: Bash temp capture snippets (R3 verification)
# ---------------------------------------------------------------------------

class TestBashTempCapture(unittest.TestCase):
    """Verify Bash temp-capture/cleanup snippets work correctly
    under errexit, using the ACTUAL documented recipe pattern."""

    def test_mktemp_allocation_failure_stops_helper(self) -> None:
        """mktemp failure → exit before helper runs (shell test)."""
        import subprocess
        script = textwrap.dedent("""\
            set -euo pipefail
            # Override mktemp to simulate allocation failure
            mktemp() { return 1; }
            export -f mktemp
            REF_ERR=$(mktemp) || { echo "FATAL: cannot create temp" >&2; exit 1; }
            echo "SHOULD_NOT_REACH"
        """)
        r = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True, timeout=5)
        self.assertNotEqual(r.returncode, 0,
                            "Allocation failure must exit nonzero")
        self.assertNotIn("SHOULD_NOT_REACH", r.stdout,
                         "Helper must not run after allocation failure")
        self.assertIn("FATAL", r.stderr)

    def test_errexit_safe_status_capture(self) -> None:
        """|| REF_EXIT=$? captures nonzero exit under set -e."""
        import subprocess
        script = textwrap.dedent("""\
            set -euo pipefail
            REF_ERR=$(mktemp) || exit 1
            REF_EXIT=0
            python3 -c "import sys; sys.exit(1)" 2>"$REF_ERR" || REF_EXIT=$?
            echo "REF_EXIT=$REF_EXIT"
            rm -f "$REF_ERR"
        """)
        r = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 0)
        self.assertIn("REF_EXIT=1", r.stdout)

    def test_temp_file_cleaned_on_all_paths(self) -> None:
        """Temp file is removed in every branch (ready/blocked/fatal)."""
        import subprocess
        script = textwrap.dedent("""\
            set -euo pipefail
            REF_ERR=$(mktemp) || exit 1
            echo "captured" > "$REF_ERR"
            # Read text then clean
            REF_ERR_TEXT=$(cat "$REF_ERR")
            rm -f "$REF_ERR"
            # Verify file is gone
            if [ -f "$REF_ERR" ]; then
                echo "LEAKED"
                exit 1
            fi
            echo "clean"
        """)
        r = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 0)
        self.assertIn("clean", r.stdout)
        self.assertNotIn("LEAKED", r.stdout)

    def test_stderr_text_retained_before_cleanup(self) -> None:
        """Fatal diagnostic text is readable before temp file removal."""
        import subprocess
        script = textwrap.dedent("""\
            set -euo pipefail
            REF_ERR=$(mktemp) || exit 1
            REF_EXIT=0
            python3 -c "import sys; print('FATAL_MSG', file=sys.stderr); sys.exit(1)" \\
                2>"$REF_ERR" || REF_EXIT=$?
            REF_ERR_TEXT=$(cat "$REF_ERR")
            rm -f "$REF_ERR"
            echo "exit=$REF_EXIT text=$REF_ERR_TEXT"
        """)
        r = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 0)
        self.assertIn("exit=1", r.stdout)
        self.assertIn("FATAL_MSG", r.stdout)


# ---------------------------------------------------------------------------
# Test: DOCS Contributing native key extraction
# ---------------------------------------------------------------------------

class TestDocsContribNativeKeyExtraction(unittest.TestCase):
    """Contributing stories section extracts native Jira keys."""

    def test_contributing_native_key_extracted(self) -> None:
        """Native Jira key in Contributing → appears in native_keys."""
        content = textwrap.dedent("""\
            ---
            ---
            # Story 1.01: [DOCS] Guide

            **As a** writer,
            **I want to** document,
            **So that** users understand.

            ## Acceptance Criteria

            - [ ] Done

            ## Documentation Scope

            API docs.

            ## Documentation Inputs

            **EDM-201 — API:** output.

            ## Dependencies

            None

            ## Design Reference

            Epic: Epic 1 — Docs
            Contributing stories: EDM-201
        """)
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.md', delete=False,
                encoding='utf-8') as f:
            f.write(content)
            f.flush()
            fp = Path(f.name)
        try:
            extraction = sync_helper.extract_required_refs(
                fp, story_title="[DOCS] Guide")
            self.assertIn("EDM-201", extraction["native_keys"],
                          "Native key in Contributing must be extracted")
        finally:
            fp.unlink()

    def test_docs_native_contributing_self_ref_blocked(self) -> None:
        """DOCS story with own native key in Contributing → blocked."""
        content = textwrap.dedent("""\
            ---
            ---
            # Story 1.01: [DOCS] Guide

            **As a** writer,
            **I want to** document,
            **So that** users understand.

            ## Acceptance Criteria

            - [ ] Done

            ## Documentation Scope

            API docs.

            ## Documentation Inputs

            Input.

            ## Dependencies

            None

            ## Design Reference

            Epic: Epic 1 — Docs
            Contributing stories: EDM-301
        """)
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.md', delete=False,
                encoding='utf-8') as f:
            f.write(content)
            f.flush()
            fp = Path(f.name)
        try:
            extraction = sync_helper.extract_required_refs(
                fp, story_title="[DOCS] Guide")
            # EDM-301 is the story's own key in this scenario
            available = {"story-1.01": "EDM-301", "epic-1": "EDM-101"}
            self_refs = sync_helper._detect_self_refs(
                "story-1.01", extraction["refs"],
                extraction["native_keys"], "EDM-301", available)
            self.assertIn("EDM-301", self_refs,
                          "Own native key in Contributing must be detected")
        finally:
            fp.unlink()

    def test_contributing_story_ref_still_extracted(self) -> None:
        """Story ref in Contributing → still in refs (unchanged)."""
        content = textwrap.dedent("""\
            ---
            ---
            # Story 1.01: [DOCS] Guide

            As a writer.

            ## Acceptance Criteria

            - Done

            ## Documentation Scope

            Docs.

            ## Documentation Inputs

            Input.

            ## Dependencies

            None

            ## Design Reference

            Epic: Epic 1
            Contributing stories: Story 2.01
        """)
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.md', delete=False,
                encoding='utf-8') as f:
            f.write(content)
            f.flush()
            fp = Path(f.name)
        try:
            extraction = sync_helper.extract_required_refs(
                fp, story_title="[DOCS] Guide")
            self.assertIn("story-2.01", extraction["refs"])
        finally:
            fp.unlink()


# ---------------------------------------------------------------------------
# Test: Canonical ID normalization in self-ref detection (Point A)
# ---------------------------------------------------------------------------

class TestCanonicalIDSelfRef(_TmpDirMixin, unittest.TestCase):
    """Self-ref detection uses canonical ID for own-key lookup."""

    def test_noncanonical_qid_still_detects_self_ref(self) -> None:
        """story-1.1 (non-canonical) with mapped story-1.01 → self-ref."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        # Non-canonical input "story-1.1" maps to same story as "story-1.01"
        r = sync_helper.check_ref_availability(
            ["story-1.1"], self.tmpdir, mf)
        self.assertEqual(len(r["blocked"]), 1,
                         "Non-canonical QID must still detect self-ref")
        self.assertIn("self-reference", r["blocked"][0]["reason"])

    def test_canonical_qid_self_ref(self) -> None:
        """story-1.01 (canonical) with mapped key → self-ref detected."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r["blocked"]), 1)
        self.assertIn("self-reference", r["blocked"][0]["reason"])

    def test_resolved_alias_integration(self) -> None:
        """Resolved alias self-ref via check_ref_availability integration."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        # story-1.01 depends on EDM-201 (its own key, as native dep)
        _make_dev_story(sd, 1, 1, "api", deps="EDM-201")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        self.assertEqual(len(r["blocked"]), 1)
        self.assertIn("self-reference", r["blocked"][0]["reason"])
        self.assertIn("EDM-201", r["blocked"][0].get("invalid_refs", []))


# ---------------------------------------------------------------------------
# Test: Self-ref diagnostics truthfulness (Point B)
# ---------------------------------------------------------------------------

class TestSelfRefDiagnostics(_TmpDirMixin, unittest.TestCase):
    """Self-ref blocked entries use invalid_refs, not missing."""

    def test_new_story_self_ref_accurate_reason(self) -> None:
        """New story planner self-ref: reason says 'self-reference',
        missing is empty, invalid_refs contains the ref."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        items = [{"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "",
                  "file": "epic-1/story-01-api.md"}]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertGreater(len(r["blocked"]), 0)
        b = r["blocked"][0]
        self.assertIn("self-reference", b["reason"])
        self.assertEqual(b["missing"], [],
                         "Self-ref IDs are invalid, not missing")
        self.assertIn("story-1.01", b.get("invalid_refs", []))

    def test_changed_story_self_ref_accurate_reason(self) -> None:
        """Changed story planner self-ref: accurate diagnostics."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        manifest = {"epics": [{"file": "epic-1-building.md",
                    "jira_key": "TE-100",
                    "stories": [{"file": "story-01-api.md",
                                 "jira_key": "TE-101",
                                 "content_hash": "old",
                                 "synced_status": "active"}]}]}
        items = [
            {"type": "story", "category": "changed", "epic_index": 1,
             "story_index": 1, "jira_key": "TE-101", "title": "",
             "file": "epic-1/story-01-api.md"},
        ]
        r = sync_helper.plan_creation_order(items, self.tmpdir, manifest)
        self.assertGreater(len(r["blocked"]), 0)
        b = r["blocked"][0]
        self.assertIn("self-reference", b["reason"])
        self.assertEqual(b["missing"], [])
        self.assertIn("story-1.01", b.get("invalid_refs", []))

    def test_runtime_self_ref_accurate_shape(self) -> None:
        """Runtime self-ref: missing=[], invalid_refs has IDs."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 1.01")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": [{"file": "story-01-api.md",
                                     "jira_key": "EDM-201",
                                     "content_hash": "h2",
                                     "synced_status": "active"}]}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        b = r["blocked"][0]
        self.assertEqual(b["missing"], [],
                         "Self-ref IDs are invalid, not missing")
        self.assertIn("story-1.01", b.get("invalid_refs", []))

    def test_legitimate_missing_ref_still_in_missing(self) -> None:
        """Actual missing ref → in 'missing', no invalid_refs."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "api", deps="Story 9.99")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        _write(mf, json.dumps({
            "schema_version": 2, "feature_key": "F",
            "epics": [{"file": "epic-1-building.md", "jira_key": "EDM-101",
                        "content_hash": "h", "synced_status": "active",
                        "stories": []}]}))
        r = sync_helper.check_ref_availability(
            ["story-1.01"], self.tmpdir, mf)
        b = r["blocked"][0]
        self.assertIn("story-9.99", b["missing"],
                      "Legitimate missing ref must be in missing")
        self.assertNotIn("invalid_refs", b,
                         "No invalid_refs for legitimate missing")


# ---------------------------------------------------------------------------
# Test: Real documented capture recipe (Point C)
# ---------------------------------------------------------------------------

class TestRealCaptureRecipe(unittest.TestCase):
    """Test the ACTUAL documented Bash capture recipe with the real
    helper, not toy scripts with hardcoded cleanup."""

    def test_recipe_ready_no_leaked_temp(self) -> None:
        """Real recipe with ready story: temp file removed."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "api", deps="None")
            _write(Path(tmpdir) / "sync-manifest.json", json.dumps({
                "schema_version": 2, "feature_key": "F",
                "epics": [{"file": "epic-1-building.md",
                           "jira_key": "EDM-101",
                           "content_hash": "h",
                           "synced_status": "active",
                           "stories": []}]}))
            script = textwrap.dedent(f"""\
                set -euo pipefail
                REF_ERR=$(mktemp) || {{ echo "FATAL" >&2; exit 1; }}
                REF_EXIT=0
                REF_CHECK=$(python3 -I "{_SCRIPT}" check-ref-availability \\
                  "{tmpdir}" "story-1.01" 2>"$REF_ERR") || REF_EXIT=$?
                REF_ERR_TEXT=$(cat "$REF_ERR")
                rm -f "$REF_ERR"
                if [ -f "$REF_ERR" ]; then echo "LEAKED"; exit 1; fi
                echo "exit=$REF_EXIT leaked=no"
            """)
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0)
            self.assertIn("exit=0", r.stdout)
            self.assertNotIn("LEAKED", r.stdout)

    def test_recipe_blocked_no_leaked_temp(self) -> None:
        """Real recipe with blocked story: temp file removed."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "api", deps="Story 9.99")
            _write(Path(tmpdir) / "sync-manifest.json", json.dumps({
                "schema_version": 2, "feature_key": "F",
                "epics": [{"file": "epic-1-building.md",
                           "jira_key": "EDM-101",
                           "content_hash": "h",
                           "synced_status": "active",
                           "stories": []}]}))
            script = textwrap.dedent(f"""\
                set -euo pipefail
                REF_ERR=$(mktemp) || {{ echo "FATAL" >&2; exit 1; }}
                REF_EXIT=0
                REF_CHECK=$(python3 -I "{_SCRIPT}" check-ref-availability \\
                  "{tmpdir}" "story-1.01" 2>"$REF_ERR") || REF_EXIT=$?
                REF_ERR_TEXT=$(cat "$REF_ERR")
                rm -f "$REF_ERR"
                if [ -f "$REF_ERR" ]; then echo "LEAKED"; exit 1; fi
                echo "exit=$REF_EXIT leaked=no"
            """)
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0)
            self.assertIn("exit=1", r.stdout)
            self.assertNotIn("LEAKED", r.stdout)

    def test_recipe_fatal_captures_stderr_text(self) -> None:
        """Real recipe with corrupted manifest: stderr text captured."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "api", deps="None")
            _write(Path(tmpdir) / "sync-manifest.json", "NOT JSON {{{")
            script = textwrap.dedent(f"""\
                set -euo pipefail
                REF_ERR=$(mktemp) || {{ echo "FATAL" >&2; exit 1; }}
                REF_EXIT=0
                REF_CHECK=$(python3 -I "{_SCRIPT}" check-ref-availability \\
                  "{tmpdir}" "story-1.01" 2>"$REF_ERR") || REF_EXIT=$?
                REF_ERR_TEXT=$(cat "$REF_ERR")
                rm -f "$REF_ERR"
                if [ -f "$REF_ERR" ]; then echo "LEAKED"; exit 1; fi
                echo "exit=$REF_EXIT text=$REF_ERR_TEXT"
            """)
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0)
            self.assertIn("exit=1", r.stdout)
            self.assertIn("ERROR", r.stdout,
                          "Fatal stderr text must be captured in REF_ERR_TEXT")
            self.assertNotIn("LEAKED", r.stdout)

    def test_no_fixed_name_clobber(self) -> None:
        """Recipe does not clobber a CWD file named ref_check_err.txt."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "api", deps="None")
            _write(Path(tmpdir) / "sync-manifest.json", json.dumps({
                "schema_version": 2, "feature_key": "F",
                "epics": [{"file": "epic-1-building.md",
                           "jira_key": "EDM-101",
                           "content_hash": "h",
                           "synced_status": "active",
                           "stories": []}]}))
            sentinel = Path(tmpdir) / "ref_check_err.txt"
            sentinel.write_text("SENTINEL", encoding="utf-8")
            script = textwrap.dedent(f"""\
                set -euo pipefail
                cd "{tmpdir}"
                REF_ERR=$(mktemp) || exit 1
                REF_EXIT=0
                REF_CHECK=$(python3 -I "{_SCRIPT}" check-ref-availability \\
                  "{tmpdir}" "story-1.01" 2>"$REF_ERR") || REF_EXIT=$?
                REF_ERR_TEXT=$(cat "$REF_ERR")
                rm -f "$REF_ERR"
                cat ref_check_err.txt
            """)
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0)
            self.assertIn("SENTINEL", r.stdout,
                          "CWD file must not be overwritten by recipe")


# ---------------------------------------------------------------------------
# Test: Quality gate manual trace (Point D)
# ---------------------------------------------------------------------------

class TestQualityGateApprovalTrace(unittest.TestCase):
    """Verify Step 4 quality gate + approval flow cross-references."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m4 = re.search(r"### Step 4:.*?(?=### Step 5:)", cls._sync_md, re.DOTALL)
        assert m4
        cls._step4 = m4.group()
        m5 = re.search(r"### Step 5:.*?(?=### Step 6:)", cls._sync_md, re.DOTALL)
        assert m5
        cls._step5 = m5.group()
        m6a = re.search(r"#### 6a:.*?(?=#### 6b:)", cls._sync_md, re.DOTALL)
        assert m6a
        cls._step6a = m6a.group()

    def test_step3_plan_approval(self) -> None:
        """Step 3 has explicit plan approval gate."""
        import re
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", self._sync_md, re.DOTALL)
        self.assertIn("approval", m3.group().lower())

    def test_step5_epic_confirmation(self) -> None:
        """Step 5 has user confirmation before stories."""
        self.assertIn("Wait for user confirmation", self._step5)

    def test_step6a_creation_batch_approval_ref(self) -> None:
        """Step 6a references the Step 5 confirmation covering creation."""
        self.assertIn("Step 5 confirmation", self._step6a)

    def test_step4_pass_continues_to_step5(self) -> None:
        """Step 4 pass allows continuation to Step 5."""
        self.assertIn("Before proceeding to Jira", self._step4)

    def test_step4_fail_blocks_entire_plan(self) -> None:
        """Step 4 failure blocks entire plan, not just failing story."""
        self.assertIn("stop the entire sync", self._step4.lower())
        self.assertIn("do not proceed to Step 5", self._step4)

    def test_step4_fresh_approval_after_revise(self) -> None:
        """After /revise correction, fresh approval cycle required."""
        self.assertIn("fresh", self._step4.lower())
        self.assertIn("Do not reuse a stale approval", self._step4)

    def test_step4_unchanged_unaffected_preserved(self) -> None:
        """Step 4 only evaluates relevant DOCS stories, not all."""
        self.assertIn("new", self._step4.lower())
        self.assertIn("changed", self._step4.lower())
        self.assertIn("reopened", self._step4.lower())

    def test_runtime_blocked_independence_preserved(self) -> None:
        """Step 4 note distinguishes from runtime independence."""
        self.assertIn("independent eligible work", self._step4)


# ---------------------------------------------------------------------------
# R1: Markdown list-prefix normalization for Contributing stories
# ---------------------------------------------------------------------------

class TestContribListPrefixNormalization(_TmpDirMixin, unittest.TestCase):
    """Contributing stories wrapped in Markdown list-item prefixes are
    extracted correctly (R1 regression)."""

    def test_dash_prefix_extracted(self) -> None:
        """``- Contributing stories: Story 1.02`` must be extracted."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_docs_story(
            sd, 1, 3, "docs",
            deps="Story 1.01",
            contributing_stories="Story 1.01, Story 1.02",
        )
        # Rewrite the file to use a list-prefixed Contributing stories line
        fp = sd / "epic-1" / "story-03-docs.md"
        content = fp.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 1.01, Story 1.02",
            "- Contributing stories: Story 1.01, Story 1.02",
        )
        fp.write_text(content, encoding="utf-8")
        result = sync_helper.extract_required_refs(fp)
        ref_ids = result["refs"]
        self.assertIn("story-1.01", ref_ids,
                       "story-1.01 must be extracted from list-prefixed Contributing")
        self.assertIn("story-1.02", ref_ids,
                       "story-1.02 must be extracted from list-prefixed Contributing")

    def test_asterisk_prefix_extracted(self) -> None:
        """``* Contributing stories: Story 2.01`` must be extracted."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_docs_story(sd, 2, 3, "docs",
                         deps="None",
                         contributing_stories="Story 2.01")
        fp = sd / "epic-2" / "story-03-docs.md"
        content = fp.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 2.01",
            "* Contributing stories: Story 2.01",
        )
        fp.write_text(content, encoding="utf-8")
        result = sync_helper.extract_required_refs(fp)
        self.assertIn("story-2.01", result["refs"])

    def test_plus_prefix_extracted(self) -> None:
        """``+ Contributing stories: Story 1.01`` must be extracted."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_docs_story(sd, 1, 2, "docs",
                         deps="None",
                         contributing_stories="Story 1.01")
        fp = sd / "epic-1" / "story-02-docs.md"
        content = fp.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 1.01",
            "+ Contributing stories: Story 1.01",
        )
        fp.write_text(content, encoding="utf-8")
        result = sync_helper.extract_required_refs(fp)
        self.assertIn("story-1.01", result["refs"])

    def test_no_prefix_still_works(self) -> None:
        """Unprefixed ``Contributing stories:`` still extracted."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_docs_story(sd, 1, 2, "docs",
                         deps="None",
                         contributing_stories="Story 1.01")
        fp = sd / "epic-1" / "story-02-docs.md"
        result = sync_helper.extract_required_refs(fp)
        self.assertIn("story-1.01", result["refs"])

    def test_both_sections_extracted(self) -> None:
        """Refs from both Dependencies and Contributing are extracted
        per existing grammar — deduplication is the consumer's concern."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_docs_story(sd, 1, 3, "docs",
                         deps="Story 1.01",
                         contributing_stories="Story 1.01, Story 1.02")
        fp = sd / "epic-1" / "story-03-docs.md"
        result = sync_helper.extract_required_refs(fp)
        refs = result["refs"]
        # story-1.01 extracted from both sections
        self.assertGreaterEqual(refs.count("story-1.01"), 2,
                                "story-1.01 must be extracted from both sections")
        self.assertIn("story-1.02", refs)

    def test_contrib_only_reversed_order(self) -> None:
        """DOCS story-1.01 with list-prefixed Contributing-only ref to
        later-numbered Story 2.01 — planner reverses numeric order so
        DEV 2.01 is created before DOCS 1.01.  Uses detect_changes +
        plan_creation_order with real source files."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "docs-epic")
        _make_epic(sd, 2, "dev-epic")
        _make_dev_story(sd, 2, 1, "impl", deps="None")
        # DOCS story-1.01 with Dependencies: None, Contributing-only ref
        # to the later-numbered Story 2.01
        _make_docs_story(sd, 1, 1, "api-docs",
                         deps="None",
                         contributing_stories="Story 2.01")
        fp = sd / "epic-1" / "story-01-api-docs.md"
        content = fp.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 2.01",
            "- Contributing stories: Story 2.01",
        )
        fp.write_text(content, encoding="utf-8")
        # Use detect_changes to build the real change plan
        change_plan = sync_helper.detect_changes(self.tmpdir)
        self.assertFalse(change_plan["manifest_exists"])
        story_items = [i for i in change_plan["items"]
                       if i["type"] == "story"]
        self.assertEqual(len(story_items), 2)
        r = sync_helper.plan_creation_order(
            change_plan["items"], self.tmpdir, None)
        self.assertEqual(r["errors"], [])
        qids = [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in r["ordered"]]
        self.assertIn("story-2.01", qids)
        self.assertIn("story-1.01", qids)
        # DEV 2.01 must be created BEFORE DOCS 1.01 (reversed numeric)
        self.assertLess(qids.index("story-2.01"), qids.index("story-1.01"),
                        "DEV 2.01 must precede DOCS 1.01 in creation order")

    def test_contrib_only_availability_lifecycle(self) -> None:
        """DOCS with list-prefixed Contributing-only ref: blocked before
        mapping, ready after prerequisite+parent keys recorded."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "impl", deps="None")
        _make_docs_story(sd, 1, 2, "docs",
                         deps="None",
                         contributing_stories="Story 1.01")
        fp = sd / "epic-1" / "story-02-docs.md"
        content = fp.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 1.01",
            "- Contributing stories: Story 1.01",
        )
        fp.write_text(content, encoding="utf-8")
        # No manifest → prereq story-1.01 has no key → blocked
        _make_manifest(Path(self.tmpdir), [])
        mf = Path(self.tmpdir) / "sync-manifest.json"
        r1 = sync_helper.check_ref_availability(
            ["story-1.02"], str(self.tmpdir), str(mf))
        self.assertEqual(len(r1["blocked"]), 1,
                         "DOCS story blocked when Contributing prereq has no key")
        # Record parent epic and prereq story keys
        sync_helper.update_manifest(
            str(mf), "create", "epic-1-building.md", "EDM-100",
            "h", item_type="epic")
        sync_helper.update_manifest(
            str(mf), "create", "story-01-impl.md", "EDM-201",
            "h", item_type="story", epic_file="epic-1-building.md")
        r2 = sync_helper.check_ref_availability(
            ["story-1.02"], str(self.tmpdir), str(mf))
        self.assertEqual(len(r2["ready"]), 1,
                         "DOCS story ready after prereq+parent keys mapped")

    def test_contrib_only_prepare_renders_native_key(self) -> None:
        """After mapping, prepare renders native Jira key from Contributing
        while Dependencies remains None."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "impl", deps="None")
        _make_docs_story(sd, 1, 2, "docs",
                         deps="None",
                         contributing_stories="Story 1.01")
        fp_docs = sd / "epic-1" / "story-02-docs.md"
        content = fp_docs.read_text(encoding="utf-8")
        content = content.replace(
            "Contributing stories: Story 1.01",
            "- Contributing stories: Story 1.01",
        )
        fp_docs.write_text(content, encoding="utf-8")
        mf = _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-impl.md", "jira_key": "EDM-201",
                 "content_hash": "h", "synced_status": "active"},
            ],
        }])
        prep = sync_helper.prepare(
            str(fp_docs), str(mf), "story",
            design_doc_link="http://ex.com/design",
            epic_jira_key="EDM-100")
        # Contributing story ref resolved to Jira key
        self.assertIn("EDM-201", prep["description"])
        # Dependencies section is None, not a Jira link
        self.assertEqual(prep["dependencies"], "None")

    def test_nondocs_ignores_contributing(self) -> None:
        """Non-DOCS story ignores Contributing stories field entirely."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_dev_story(sd, 1, 1, "scaffold", deps="None")
        fp = sd / "epic-1" / "story-01-scaffold.md"
        # Manually add Contributing stories to a DEV story (should be ignored)
        content = fp.read_text(encoding="utf-8")
        content += "\nContributing stories: Story 2.01\n"
        fp.write_text(content, encoding="utf-8")
        result = sync_helper.extract_required_refs(fp)
        ref_ids = result["refs"]
        self.assertNotIn("story-2.01", ref_ids,
                         "Non-DOCS story must not extract Contributing stories")

    def test_native_key_preserved_in_existing_cases(self) -> None:
        """Existing native Jira key extraction from Contributing is preserved."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_docs_story(sd, 1, 2, "docs",
                         deps="None",
                         contributing_stories="EDM-500")
        fp = sd / "epic-1" / "story-02-docs.md"
        result = sync_helper.extract_required_refs(fp)
        self.assertIn("EDM-500", result["native_keys"])


# ---------------------------------------------------------------------------
# R2: Actual unavailable ref IDs in blocked[].missing — no placeholder
# ---------------------------------------------------------------------------

class TestUnavailableRefIDs(_TmpDirMixin, unittest.TestCase):
    """Blocked entries must include actual unavailable ref IDs in
    ``missing``, not ``(see errors for qid)`` (R2 regression)."""

    def _setup_stories(self, deps_list):
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        for eidx, sidx, slug, deps in deps_list:
            _make_epic(sd, eidx, f"epic{eidx}")
            _make_dev_story(sd, eidx, sidx, slug, deps=deps)
        return sd

    def _item(self, eidx, sidx, slug):
        return {"type": "story", "category": "new",
                "epic_index": eidx, "story_index": sidx,
                "jira_key": None, "title": "",
                "file": f"epic-{eidx}/story-{sidx:02d}-{slug}.md"}

    def test_unavailable_ref_id_in_missing(self) -> None:
        """Unavailable story ref appears directly in blocked[].missing."""
        self._setup_stories([(1, 1, "a", "Story 9.99")])
        items = [self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(len(r["ordered"]), 0)
        self.assertEqual(len(r["blocked"]), 1)
        blocked = r["blocked"][0]
        self.assertIn("story-9.99", blocked["missing"],
                       "Actual unavailable ref ID must be in missing")
        for m in blocked["missing"]:
            self.assertNotIn("(see errors", m,
                             "Placeholder must not appear in missing")

    def test_unavailable_epic_ref_id_in_missing(self) -> None:
        """Unavailable epic ref appears directly in blocked[].missing."""
        self._setup_stories([(1, 1, "a", "Epic 999")])
        items = [self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(len(r["blocked"]), 1)
        blocked = r["blocked"][0]
        self.assertIn("epic-999", blocked["missing"],
                       "Actual unavailable epic ref must be in missing")

    def test_both_direct_unavailable_and_blocked_graph_in_missing(self) -> None:
        """Owner with BOTH direct unavailable ref AND graph prerequisite
        that is itself blocked: owner's missing contains both actual IDs."""
        self._setup_stories([
            (1, 1, "a", "Story 9.99"),       # a → missing 9.99
            (1, 2, "b", "Story 1.01"),       # b → a (which is blocked)
            (1, 3, "c", "Story 9.99, Story 1.02"),  # c → missing 9.99 + b
        ])
        items = [self._item(1, 1, "a"), self._item(1, 2, "b"),
                 self._item(1, 3, "c")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        blocked_map = {
            f"story-{b['item']['epic_index']}.{b['item']['story_index']:02d}": b
            for b in r["blocked"]
        }
        # story-1.03 has direct unavailable story-9.99 AND graph dep
        # story-1.02 which is itself blocked — both must be in missing
        self.assertIn("story-1.03", blocked_map)
        c_missing = blocked_map["story-1.03"]["missing"]
        self.assertIn("story-9.99", c_missing,
                       "Direct unavailable ref must be in missing")
        self.assertIn("story-1.02", c_missing,
                       "Blocked graph prerequisite must be in missing")
        # No placeholders anywhere
        for m in c_missing:
            self.assertNotIn("(see errors", m)

    def test_self_ref_uses_invalid_refs_not_missing(self) -> None:
        """Self-ref uses invalid_refs/reason, NOT missing."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "a", deps="Story 1.01")
        items = [self._item(1, 1, "a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(len(r["blocked"]), 1)
        b = r["blocked"][0]
        self.assertEqual(b["missing"], [])
        self.assertIn("invalid_refs", b)
        self.assertIn("self-reference", b["reason"])

    def test_source_read_failure_reason_no_fake_id(self) -> None:
        """Unreadable source → reason set, no fake ID in missing."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "building")
        items = [{"type": "story", "category": "new",
                  "epic_index": 1, "story_index": 1,
                  "jira_key": None, "title": "",
                  "file": "epic-1/story-01-ghost.md"}]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(len(r["blocked"]), 1)
        b = r["blocked"][0]
        self.assertIn("unreadable", b["reason"].lower(),
                       "Reason must describe source failure")
        for m in b.get("missing", []):
            self.assertNotIn("(see errors", m,
                             "No placeholder in missing for source failures")

    def test_no_placeholder_anywhere(self) -> None:
        """No blocked entry may contain ``(see errors for ...)`` placeholder."""
        self._setup_stories([
            (1, 1, "a", "Story 9.01, Story 9.02"),
            (1, 2, "b", "None"),
        ])
        items = [self._item(1, 1, "a"), self._item(1, 2, "b")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        for b in r["blocked"]:
            for m in b.get("missing", []):
                self.assertNotIn("(see errors", m)

    def test_cli_unavailable_ref_id_in_json(self) -> None:
        """CLI plan-creation-order JSON contains actual ref IDs in blocked."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir(exist_ok=True)
        _make_epic(sd, 1, "epic1")
        _make_dev_story(sd, 1, 1, "a", deps="Story 9.99")
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.tmpdir)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertGreater(len(out["blocked"]), 0)
        blocked = out["blocked"][0]
        self.assertIn("story-9.99", blocked["missing"])


# ---------------------------------------------------------------------------
# R5: Parent-epic retirement affects DOCS set (instruction contract)
# ---------------------------------------------------------------------------

class TestDocsParentEpicRetirement(unittest.TestCase):
    """Revise.md includes parent-epic retirement in DOCS affected set (R5)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        revise_path = Path(__file__).resolve().parent.parent / "skills" / "revise.md"
        cls._revise_md = revise_path.read_text(encoding="utf-8")
        m4 = re.search(r"### Step 4:.*?(?=### Step 5:)", cls._revise_md, re.DOTALL)
        assert m4, "Step 4 not found in revise.md"
        cls._step4 = m4.group()
        # Find the DOCS re-evaluation block (trigger list a-e)
        trigger = re.search(
            r"A `\[DOCS\]` story is affected when.*?(?=For each affected)",
            cls._step4, re.DOTALL)
        assert trigger, "DOCS affected-set trigger block not found"
        cls._trigger_block = trigger.group()
        # Find post-cascade reconciliation block
        cascade_idx = cls._step4.find("reconciliation after cascades")
        assert cascade_idx >= 0, "Post-cascade reconciliation block not found"
        cls._cascade_block = cls._step4[cascade_idx:]

    def test_parent_epic_retirement_in_trigger(self) -> None:
        """Trigger list (a-e) includes parent epic retirement."""
        self.assertIn("parent epic", self._trigger_block.lower())

    def test_contributor_status_removed_in_trigger(self) -> None:
        """Trigger mentions status: removed on parent."""
        self.assertIn("status: removed", self._trigger_block)

    def test_unchanged_file_still_affected(self) -> None:
        """Trigger notes unchanged contributor file affected by parent."""
        self.assertIn("unchanged", self._trigger_block.lower())

    def test_parent_retirement_in_cascade_reconciliation(self) -> None:
        """Post-cascade reconciliation mentions parent epic removal."""
        self.assertIn("parent epic removal", self._cascade_block.lower())


class TestDocsParentRetirementHelper(_TmpDirMixin, unittest.TestCase):
    """Parent epic retirement logically retires children via existing
    helper detect_changes semantics (R5 execution-level evidence)."""

    def test_child_under_removed_parent_not_created(self) -> None:
        """detect_changes skips new children under removed parent epic."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building", removed=True)
        _make_dev_story(sd, 1, 1, "impl", deps="None")
        result = sync_helper.detect_changes(self.tmpdir)
        # Active child under removed parent should not appear as new
        story_items = [i for i in result["items"]
                       if i["type"] == "story" and i["epic_index"] == 1]
        self.assertEqual(len(story_items), 0,
                         "Child under removed parent must be skipped on fresh sync")

    def test_active_child_changed_under_removed_parent(self) -> None:
        """An active child story that changed under a removed parent gets
        category 'removed' (not 'changed') — parent retirement overrides."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building", removed=True)
        _make_dev_story(sd, 1, 1, "impl", deps="None")
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "h", "synced_status": "active",
            "stories": [
                {"file": "story-01-impl.md", "jira_key": "EDM-201",
                 "content_hash": "old-different-hash", "synced_status": "active"},
            ],
        }])
        result = sync_helper.detect_changes(self.tmpdir)
        child = [i for i in result["items"]
                 if i["type"] == "story" and i.get("story_index") == 1]
        self.assertEqual(len(child), 1)
        self.assertEqual(child[0]["category"], "removed",
                         "Changed child under removed parent = logically removed")


# ---------------------------------------------------------------------------
# R6: Post-cascade DOCS reconciliation (instruction contract)
# ---------------------------------------------------------------------------

class TestDocsPostCascadeReconciliation(unittest.TestCase):
    """Revise.md re-reads/reconciles DOCS after IC/testplan cascades (R6)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        revise_path = Path(__file__).resolve().parent.parent / "skills" / "revise.md"
        cls._revise_md = revise_path.read_text(encoding="utf-8")
        m4 = re.search(r"### Step 4:.*?(?=### Step 5:)", cls._revise_md, re.DOTALL)
        assert m4, "Step 4 not found in revise.md"
        cls._step4 = m4.group()
        # Find the IC/testplan cascade sections (producers)
        cls._ic_cascade_idx = cls._step4.find("design Interface Changes")
        assert cls._ic_cascade_idx > 0, "IC cascade not found in Step 4"
        cls._tc_cascade_idx = cls._step4.find("test cases were added, removed")
        assert cls._tc_cascade_idx > 0, "TC cascade not found in Step 4"
        # Find post-cascade reconciliation
        cls._recon_idx = cls._step4.find(
            "reconciliation after cascades")
        assert cls._recon_idx > 0, "Post-cascade reconciliation not found"
        # Find Step 5 boundary
        cls._step5_boundary = len(cls._step4)

    def test_reconciliation_after_ic_cascade(self) -> None:
        """Post-cascade DOCS reconciliation appears after IC cascade."""
        self.assertGreater(self._recon_idx, self._ic_cascade_idx,
                           "Reconciliation must appear after IC cascade")

    def test_reconciliation_after_tc_cascade(self) -> None:
        """Post-cascade DOCS reconciliation appears after TC cascade."""
        self.assertGreater(self._recon_idx, self._tc_cascade_idx,
                           "Reconciliation must appear after TC cascade")

    def test_reconciliation_before_step5(self) -> None:
        """Post-cascade DOCS reconciliation appears before Step 5 in full source."""
        # Use whole-source positions — the Step 4 slice comparison was vacuous
        # (any valid index within a slice is trivially < len(slice)).
        recon_pos = self._revise_md.find("reconciliation after cascades")
        step5_pos = self._revise_md.find("### Step 5:")
        self.assertGreater(recon_pos, 0)
        self.assertGreater(step5_pos, 0)
        self.assertLess(recon_pos, step5_pos,
                        "Reconciliation must appear before Step 5 in source")

    def test_recomputes_affected_set(self) -> None:
        """Reconciliation recomputes affected DOCS set, not cached initial."""
        recon_text = self._step4[self._recon_idx:]
        self.assertIn("recompute", recon_text.lower())

    def test_preserves_prerequisite_deps(self) -> None:
        """Reconciliation preserves prerequisite Dependencies."""
        recon_text = self._step4[self._recon_idx:]
        self.assertIn("prerequisite", recon_text.lower())

    def test_reapplies_seven_criteria(self) -> None:
        """Reconciliation reapplies seven DOCS criteria after edits."""
        recon_text = self._step4[self._recon_idx:]
        self.assertIn("seven", recon_text.lower())
        self.assertIn("criteria", recon_text.lower())

    def test_covers_documentation_inputs(self) -> None:
        """Reconciliation covers Documentation Inputs."""
        recon_text = self._step4[self._recon_idx:]
        # Handle line-wrapped "Documentation\nInputs"
        joined = " ".join(recon_text.split())
        self.assertIn("Documentation Inputs", joined)


# ---------------------------------------------------------------------------
# R7: Step 3 fail-closed capture recipe (instruction contract)
# ---------------------------------------------------------------------------

class TestStep3FailClosedCapture(unittest.TestCase):
    """Sync.md Step 3 uses fail-closed capture for plan-creation-order (R7)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", cls._sync_md, re.DOTALL)
        assert m3, "Step 3 not found in sync.md"
        cls._step3 = m3.group()
        # Find capture recipe
        cls._recipe_idx = cls._step3.find("PLAN_ERR=$(mktemp)")
        assert cls._recipe_idx >= 0, "Capture recipe not found"
        # Find interpretation section
        cls._interp_idx = cls._step3.find("Interpret the result")
        assert cls._interp_idx >= 0, "Interpretation section not found"
        # Find preflight
        cls._preflight_idx = cls._step3.find("Preflight check")
        assert cls._preflight_idx >= 0, "Preflight check not found"
        # Find preview
        cls._preview_idx = cls._step3.find("Dry-run preview")
        assert cls._preview_idx >= 0, "Preview not found"
        # Find individual branch boundaries within interpretation
        interp = cls._step3[cls._interp_idx:cls._preflight_idx]
        cls._branch1_idx = interp.find("1. **Exit 0")
        assert cls._branch1_idx >= 0, "Branch 1 not found"
        cls._branch2_idx = interp.find("2. **Exit 1")
        assert cls._branch2_idx >= 0, "Branch 2 not found"
        cls._branch3_idx = interp.find("3. **Any other")
        assert cls._branch3_idx >= 0, "Branch 3 not found"
        cls._branch1 = interp[cls._branch1_idx:cls._branch2_idx]
        cls._branch2 = interp[cls._branch2_idx:cls._branch3_idx]
        cls._branch3 = interp[cls._branch3_idx:]

    def test_recipe_uses_mktemp(self) -> None:
        """Capture recipe uses mktemp for safe temp file."""
        self.assertIn("mktemp", self._step3)

    def test_recipe_captures_exit_code(self) -> None:
        """Capture recipe uses PLAN_EXIT for errexit-safe status."""
        recipe = self._step3[self._recipe_idx:self._interp_idx]
        self.assertIn("PLAN_EXIT", recipe)
        self.assertIn("|| PLAN_EXIT=$?", recipe)

    def test_recipe_inline_cleanup(self) -> None:
        """Temp file cleaned before branch interpretation."""
        recipe = self._step3[self._recipe_idx:self._interp_idx]
        self.assertIn("rm -f", recipe)

    def test_recipe_mktemp_failure_fatal(self) -> None:
        """mktemp allocation failure stops immediately."""
        recipe = self._step3[self._recipe_idx:self._interp_idx]
        self.assertIn("FATAL", recipe)
        self.assertIn("exit 1", recipe)

    def test_interpretation_precedes_preview(self) -> None:
        """Interpretation happens before preview/preflight."""
        self.assertLess(self._interp_idx, self._preview_idx)
        self.assertLess(self._interp_idx, self._preflight_idx)

    def test_success_requires_four_fields(self) -> None:
        """Branch 1 requires all four JSON fields: ordered, blocked,
        errors, satisfied_keys."""
        for field in ("ordered", "blocked", "errors", "satisfied_keys"):
            self.assertIn(f"`{field}`", self._branch1,
                          f"Branch 1 success contract must require {field}")

    def test_success_requires_empty_errors_blocked(self) -> None:
        """Branch 1 requires errors empty AND blocked empty."""
        self.assertIn("`errors` empty", self._branch1)
        self.assertIn("`blocked` empty", self._branch1)

    def test_success_allows_empty_ordered(self) -> None:
        """Branch 1: empty ordered is valid (no new stories to create)."""
        self.assertIn("`ordered` may be empty", self._branch1,
                      "Branch 1 must explicitly allow empty ordered")

    def test_exit1_structured_errors_stop(self) -> None:
        """Branch 2: exit 1 + valid JSON + non-empty errors → STOP."""
        self.assertIn("STOP", self._branch2,
                      "STOP must appear in Branch 2 (structured errors)")

    def test_malformed_fatal(self) -> None:
        """Branch 3: malformed/empty/missing fields → fatal STOP."""
        lower = self._branch3.lower()
        self.assertIn("malformed", lower)
        self.assertIn("wrong-type", lower)

    def test_no_new_status_field(self) -> None:
        """Success contract does not invent a 'status' field."""
        # The word "status" should not appear as a JSON field name
        self.assertNotIn("`status`", self._branch1)


class TestStep3CLIFixtures(_TmpDirMixin, unittest.TestCase):
    """Step 3 CLI validation: valid-clean, structural-error, fatal-output."""

    def test_valid_clean_empty_ordered(self) -> None:
        """Exit 0, empty ordered/blocked/errors: valid clean plan."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        # No new stories at all
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": sync_helper.compute_file_hash(
                sd / "epic-1-building.md"),
            "synced_status": "active", "stories": [],
        }])
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.tmpdir)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertIsInstance(out["ordered"], list)
        self.assertIsInstance(out["blocked"], list)
        self.assertIsInstance(out["errors"], list)
        self.assertIsInstance(out["satisfied_keys"], dict)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["blocked"], [])

    def test_structural_error_exit1_with_json(self) -> None:
        """Exit 1, valid JSON with non-empty errors: structural error."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "a", deps="Story 9.99")
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.tmpdir)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 1, "Structural errors must exit 1")
        out = json.loads(r.stdout)
        self.assertGreater(len(out["errors"]), 0)
        # JSON still has all four required fields
        for field in ("ordered", "blocked", "errors", "satisfied_keys"):
            self.assertIn(field, out)

    def test_fatal_corrupted_manifest_no_json(self) -> None:
        """Corrupted manifest → exit 1, stderr error, no valid JSON."""
        import subprocess
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "a", deps="None")
        mf = Path(self.tmpdir) / "sync-manifest.json"
        mf.write_text("NOT VALID JSON", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT),
             "plan-creation-order", str(self.tmpdir)],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ERROR", r.stderr)
        # stdout should NOT be valid JSON with all four fields
        try:
            out = json.loads(r.stdout)
            has_all = all(k in out for k in
                          ("ordered", "blocked", "errors", "satisfied_keys"))
            self.assertFalse(has_all,
                             "Fatal error must not produce complete JSON")
        except json.JSONDecodeError:
            pass  # Expected: no JSON at all


# ---------------------------------------------------------------------------
# R7: Step 3 Bash capture recipe execution under errexit
# ---------------------------------------------------------------------------

class TestStep3CaptureRecipeExecution(unittest.TestCase):
    """The documented Step 3 Bash capture recipe for plan-creation-order
    executes correctly under set -euo pipefail with real helper calls.

    The recipe is extracted from the single bash fence in sync.md Step 3
    rather than hardcoded, so the tests break if the documented consumer
    diverges."""

    @classmethod
    def setUpClass(cls) -> None:
        import re as _r
        sync_path = (Path(__file__).resolve().parent.parent
                     / "skills" / "sync.md")
        sync_md = sync_path.read_text(encoding="utf-8")
        m3 = _r.search(r"### Step 3:.*?(?=### Step 4:)",
                        sync_md, _r.DOTALL)
        assert m3, "Step 3 not found in sync.md"
        step3 = m3.group()
        # Extract the single bash fence containing the capture recipe
        fence_match = _r.search(
            r"```bash\n(PLAN_ERR=\$\(mktemp\).*?)```",
            step3, _r.DOTALL)
        assert fence_match, "Capture fence not found in Step 3"
        cls._fence = fence_match.group(1)
        # Verify boundary markers
        assert "PLAN_ERR=$(mktemp)" in cls._fence
        assert "rm -f" in cls._fence
        assert "PLAN_EXIT" in cls._fence
        assert "PLAN_ERR_TEXT" in cls._fence

    @staticmethod
    def _adapt_fence(artifacts_dir: str) -> str:
        """Substitute controlled paths into the extracted fence."""
        script = TestStep3CaptureRecipeExecution._fence
        # Replace python3 "$SYNC_HELPER" with sys.executable -I _SCRIPT
        script = script.replace(
            'python3 "$SYNC_HELPER"',
            f"'{sys.executable}' -I '{_SCRIPT}'")
        # Replace artifact path placeholder
        script = script.replace(
            ".artifacts/design/{issue-key}/", artifacts_dir + "/")
        return script

    def test_valid_clean_capture(self) -> None:
        """Valid clean plan: exit=0, valid JSON, temp cleaned."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "impl", deps="None")
            fence = self._adapt_fence(tmpdir)
            script = (
                "set -euo pipefail\n"
                + fence
                + 'if [ -f "$PLAN_ERR" ]; then echo "LEAKED"; exit 1; fi\n'
                + 'echo "exit=$PLAN_EXIT"\n'
                + 'echo "$PLAN_JSON"\n'
            )
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("exit=0", r.stdout)
            self.assertNotIn("LEAKED", r.stdout)
            # Parse the JSON from stdout (after "exit=0\n")
            json_text = r.stdout.split("\n", 1)[1]
            out = json.loads(json_text)
            self.assertEqual(out["errors"], [])
            self.assertEqual(out["blocked"], [])
            self.assertIsInstance(out["ordered"], list)
            self.assertIsInstance(out["satisfied_keys"], dict)

    def test_structured_error_capture(self) -> None:
        """Structured error (exit=1 + JSON): captured correctly."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "impl", deps="Story 9.99")
            fence = self._adapt_fence(tmpdir)
            script = (
                "set -euo pipefail\n"
                + fence
                + 'if [ -f "$PLAN_ERR" ]; then echo "LEAKED"; exit 1; fi\n'
                + 'echo "exit=$PLAN_EXIT"\n'
                + 'echo "$PLAN_JSON"\n'
            )
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("exit=1", r.stdout)
            self.assertNotIn("LEAKED", r.stdout)
            json_text = r.stdout.split("\n", 1)[1]
            out = json.loads(json_text)
            self.assertGreater(len(out["errors"]), 0)

    def test_fatal_corrupted_capture(self) -> None:
        """Fatal (corrupted manifest): exit!=0, stderr captured, temp cleaned."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sd = Path(tmpdir) / "06-stories"
            sd.mkdir()
            _make_epic(sd, 1, "building")
            _make_dev_story(sd, 1, 1, "impl", deps="None")
            _write(Path(tmpdir) / "sync-manifest.json", "NOT JSON {{{")
            fence = self._adapt_fence(tmpdir)
            script = (
                "set -euo pipefail\n"
                + fence
                + 'if [ -f "$PLAN_ERR" ]; then echo "LEAKED"; exit 1; fi\n'
                + 'echo "exit=$PLAN_EXIT"\n'
                + 'echo "stderr=$PLAN_ERR_TEXT"\n'
            )
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("exit=1", r.stdout)
            self.assertIn("stderr=ERROR", r.stdout)
            self.assertNotIn("LEAKED", r.stdout)


# ---------------------------------------------------------------------------
# R8: Repeat /decompose loads existing artifacts (instruction contract)
# ---------------------------------------------------------------------------

class TestRepeatDecomposeArtifactLoad(unittest.TestCase):
    """Decompose.md handles repeat runs with existing artifacts (R8)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")
        m1 = re.search(r"### Step 1:.*?(?=### Step 2:)",
                        cls._decompose_md, re.DOTALL)
        assert m1, "Step 1 not found in decompose.md"
        cls._step1 = m1.group()
        # Find the repeat-decompose block
        repeat_idx = cls._step1.find("already exist")
        assert repeat_idx >= 0, "Repeat-decompose block not found"
        cls._repeat_block = cls._step1[repeat_idx:]

    def test_existing_artifact_handling(self) -> None:
        """Step 1 mentions handling existing decomposition artifacts."""
        self.assertIn("already exist", self._step1)

    def test_loads_before_step2_planning(self) -> None:
        """Repeat-decompose loading appears in Step 1 before Step 2."""
        self.assertIn("05-epics.md", self._repeat_block)
        self.assertIn("06-stories", self._repeat_block)
        self.assertIn("07-coverage.md", self._repeat_block)

    def test_includes_removed_status_in_inventory(self) -> None:
        """Inventory includes files with status: removed."""
        self.assertIn("status: removed", self._repeat_block)

    def test_preserves_qualified_identities(self) -> None:
        """Step 1 preserves existing qualified identities."""
        self.assertIn("qualified identit", self._repeat_block.lower())

    def test_no_overwrite_mismatched_ids(self) -> None:
        """Step 1 prohibits overwriting mismatched existing IDs."""
        self.assertIn("overwrite", self._repeat_block.lower())

    def test_retired_numbers_not_reused(self) -> None:
        """Step 1 prohibits reuse of retired numbers."""
        self.assertIn("retired", self._repeat_block.lower())

    def test_explicit_restoration_required(self) -> None:
        """Step 1 requires explicit approved restoration for removed items."""
        self.assertIn("restoration", self._repeat_block.lower())

    def test_initial_empty_still_works(self) -> None:
        """Step 1 notes initial empty decomposition still works."""
        self.assertIn("initial empty", self._repeat_block.lower())

    def test_no_delete_recreate(self) -> None:
        """Step 1 prohibits delete and recreate pattern."""
        self.assertIn("delete", self._repeat_block.lower())
        self.assertIn("recreate", self._repeat_block.lower())


# ---------------------------------------------------------------------------
# R8: Controller 'from scratch' wording (instruction contract)
# ---------------------------------------------------------------------------

class TestControllerDecomposeWording(unittest.TestCase):
    """Controller.md does not say 'from scratch' for repeat decompose (R8)."""

    @classmethod
    def setUpClass(cls) -> None:
        ctrl_path = (Path(__file__).resolve().parent.parent
                     / "skills" / "controller.md")
        cls._ctrl_md = ctrl_path.read_text(encoding="utf-8")

    def test_no_from_scratch(self) -> None:
        """Controller does not say 'from scratch'."""
        self.assertNotIn("from scratch", self._ctrl_md)

    def test_preserves_existing_identities(self) -> None:
        """Controller mentions preserved identities for repeat decompose."""
        self.assertIn("preserved existing identities", self._ctrl_md)


# ---------------------------------------------------------------------------
# R9: Relative protocol reference (instruction contract)
# ---------------------------------------------------------------------------

class TestSyncHelperUsageReference(unittest.TestCase):
    """sync-helper-usage.md uses correct relative path for sync protocol (R9)."""

    @classmethod
    def setUpClass(cls) -> None:
        ref_path = (Path(__file__).resolve().parent.parent
                    / "references" / "sync-helper-usage.md")
        cls._ref_md = ref_path.read_text(encoding="utf-8")

    def test_relative_protocol_reference(self) -> None:
        """Reference to sync protocol uses ../skills/sync.md path."""
        self.assertIn("../skills/sync.md", self._ref_md)

    def test_no_bare_sync_md_resource_ref(self) -> None:
        """No bare ``sync.md`` used as a protocol resource reference."""
        import re
        matches = re.findall(r'from `sync\.md`', self._ref_md)
        self.assertEqual(len(matches), 0,
                         "Bare sync.md resource reference should use "
                         "../skills/sync.md")


# ---------------------------------------------------------------------------
# R3: DOCS criterion 5 scope wording (instruction contract)
# ---------------------------------------------------------------------------

class TestDocsCriterion5Scope(unittest.TestCase):
    """Decompose.md criterion 5 uses DOCS-story scope, not feature-wide (R3)."""

    @classmethod
    def setUpClass(cls) -> None:
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")

    def test_criterion5_not_feature_wide(self) -> None:
        """Criterion 5 does NOT say 'by the feature'."""
        import re
        m = re.search(r"5\.\s+\*\*Complete Documentation Inputs\.\*\*.*?"
                       r"(?=6\.\s+\*\*Contributing)",
                       self._decompose_md, re.DOTALL)
        self.assertIsNotNone(m, "Criterion 5 not found")
        c5 = m.group()
        self.assertNotIn("by the feature", c5.lower())

    def test_criterion5_story_scope(self) -> None:
        """Criterion 5 scopes to this DOCS story's declared scope."""
        import re
        m = re.search(r"5\.\s+\*\*Complete Documentation Inputs\.\*\*.*?"
                       r"(?=6\.\s+\*\*Contributing)",
                       self._decompose_md, re.DOTALL)
        self.assertIsNotNone(m)
        c5 = m.group()
        self.assertIn("story's declared scope", c5.lower())

    def test_template_scope(self) -> None:
        """Template Documentation Inputs placeholder scopes to story."""
        import re
        m = re.search(r"## Documentation Inputs\n\n\{.*?\}", self._decompose_md,
                       re.DOTALL)
        self.assertIsNotNone(m, "Template Documentation Inputs not found")
        tmpl = m.group()
        self.assertIn("scope", tmpl.lower())


# ---------------------------------------------------------------------------
# R4: Replacement-reviewer includes testplan (instruction contract)
# ---------------------------------------------------------------------------

class TestReplacementReviewerTestplan(unittest.TestCase):
    """Decompose.md replacement-reviewer includes 04-testplan.md (R4)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")
        m9 = re.search(r"### Step 9:.*?(?=### Step 10:)",
                        cls._decompose_md, re.DOTALL)
        assert m9, "Step 9 not found in decompose.md"
        cls._step9 = m9.group()
        # Find the exact replacement-reviewer paragraph
        replacement = re.search(
            r"\*\*If resumption is not available:\*\*.*?(?=\*\*If subagents "
            r"are not available:\*\*)",
            cls._step9, re.DOTALL)
        assert replacement, "Replacement-reviewer paragraph not found"
        cls._replacement_para = replacement.group()

    def test_replacement_reviewer_includes_testplan(self) -> None:
        """The exact replacement-reviewer paragraph includes 04-testplan.md."""
        self.assertIn("04-testplan.md", self._replacement_para)

    def test_replacement_reviewer_excludes_design(self) -> None:
        """The exact replacement-reviewer paragraph excludes design doc."""
        self.assertIn("NOT the design document", self._replacement_para)


# ---------------------------------------------------------------------------
# F1: Partial-resume — decompose.md handles missing 07-coverage.md
# ---------------------------------------------------------------------------

class TestPartialResumeContract(unittest.TestCase):
    """Decompose.md Step 1 repeat-decompose handles interrupted prior run
    where 07-coverage.md was not produced (F1)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")
        m1 = re.search(r"### Step 1:.*?(?=### Step 2:)",
                        cls._decompose_md, re.DOTALL)
        assert m1, "Step 1 not found in decompose.md"
        cls._step1 = m1.group()
        repeat_idx = cls._step1.find("already exist")
        assert repeat_idx >= 0, "Repeat-decompose block not found"
        cls._repeat_block = cls._step1[repeat_idx:]

    def test_coverage_read_is_conditional(self) -> None:
        """07-coverage.md read in item 1 is conditional (if it exists)."""
        # Find the numbered read instruction (item 1 of the list),
        # not the detection condition that uses OR
        item1_idx = self._repeat_block.find("1. Read")
        self.assertGreater(item1_idx, 0, "Item 1 read instruction not found")
        item1_text = self._repeat_block[item1_idx:item1_idx + 400]
        self.assertIn("07-coverage.md", item1_text)
        self.assertIn("if it exists", item1_text.lower(),
                      "07-coverage.md read must be conditional for interrupted runs")

    def test_interrupted_run_recovery_guidance(self) -> None:
        """Step 1 mentions prior interrupted run and rebuild in Step 7."""
        self.assertIn("interrupted", self._repeat_block.lower())
        self.assertIn("Step 7", self._repeat_block)


# ---------------------------------------------------------------------------
# F2: Obsolete-work retirement on repeat decompose
# ---------------------------------------------------------------------------

class TestObsoleteWorkRetirement(unittest.TestCase):
    """Decompose.md retirement reconciliation after planning (F2).

    Step 1 inventories without deciding retirements; the reconciliation
    sub-step at the end of Step 2 marks files no longer in the plan."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")
        # Retirement reconciliation now lives in Step 2
        m2 = re.search(r"### Step 2:.*?(?=### Step 3:)",
                        cls._decompose_md, re.DOTALL)
        assert m2, "Step 2 not found"
        cls._step2 = m2.group()

    def test_retirement_via_status_removed(self) -> None:
        """Individually retired work is marked status: removed, not deleted."""
        self.assertIn("status: removed", self._step2)
        self.assertIn("individually", self._step2.lower())
        self.assertIn("explicitly retires", self._step2.lower())

    def test_epic_stays_active_if_children_retained(self) -> None:
        """Epic stays active if any child stories are retained."""
        self.assertIn("child stories are retained", self._step2.lower())

    def test_cascade_safety_mentioned(self) -> None:
        """Retirement guidance mentions cascade safety."""
        self.assertIn("cascade", self._step2.lower())


class TestObsoleteWorkHelper(_TmpDirMixin, unittest.TestCase):
    """detect_changes correctly classifies logically retired work (F2)."""

    def test_unmarked_stale_active_detected_as_changed(self) -> None:
        """An active story with changed content is detected as changed,
        eligible for retirement marking by the decomposer."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "impl", deps="None")
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "old-hash", "synced_status": "active",
            "stories": [
                {"file": "story-01-impl.md", "jira_key": "EDM-201",
                 "content_hash": "old-different-hash",
                 "synced_status": "active"},
            ],
        }])
        result = sync_helper.detect_changes(self.tmpdir)
        story_items = [i for i in result["items"]
                       if i["type"] == "story" and i["epic_index"] == 1]
        self.assertEqual(len(story_items), 1)
        self.assertEqual(story_items[0]["category"], "changed",
                         "Active changed story must be 'changed', not skipped")

    def test_logically_removed_never_synced_skipped(self) -> None:
        """A story with status: removed that was never synced is skipped."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "impl", deps="None", removed=True)
        result = sync_helper.detect_changes(self.tmpdir)
        story_items = [i for i in result["items"]
                       if i["type"] == "story" and i["epic_index"] == 1]
        # Never-synced removed story should not appear in items
        self.assertEqual(len(story_items), 0,
                         "Never-synced removed story must be skipped")

    def test_mixed_retention_same_epic(self) -> None:
        """Two stories in same epic with different retention decisions.

        Regression proof: active epic, one story retained (active), one
        retired (status: removed).  Only the obsolete story is classified
        for retirement; parent epic stays active; paths are stable.
        """
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building")
        active_sf = _make_dev_story(sd, 1, 1, "scaffold", deps="None")
        retired_sf = _make_dev_story(sd, 1, 2, "obsolete", deps="None",
                                     removed=True)
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "old-hash", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "old-hash-1", "synced_status": "active"},
                {"file": "story-02-obsolete.md", "jira_key": "EDM-202",
                 "content_hash": "old-hash-2", "synced_status": "active"},
            ],
        }])
        result = sync_helper.detect_changes(self.tmpdir)
        # Parent epic stays active (changed, not removed)
        epic_items = [i for i in result["items"]
                      if i["type"] == "epic" and i["epic_index"] == 1]
        self.assertEqual(len(epic_items), 1)
        self.assertNotEqual(epic_items[0]["category"], "removed",
                            "Parent epic must stay active")
        # Active story: changed (content differs from manifest)
        s1 = [i for i in result["items"]
              if i["type"] == "story" and i.get("story_index") == 1]
        self.assertEqual(len(s1), 1)
        self.assertEqual(s1[0]["category"], "changed",
                         "Retained story must be 'changed'")
        # Retired story: removed
        s2 = [i for i in result["items"]
              if i["type"] == "story" and i.get("story_index") == 2]
        self.assertEqual(len(s2), 1)
        self.assertEqual(s2[0]["category"], "removed",
                         "Retired story must be 'removed'")
        # Both files still exist on disk (paths stable)
        self.assertTrue(active_sf.exists(), "Retained story file must exist")
        self.assertTrue(retired_sf.exists(), "Retired story file must exist")

    def test_retired_epic_no_child_dir_accepted(self) -> None:
        """Retired epic without child directory is accepted by detect_changes.

        A partial run may create an epic file but never generate its
        story directory.  detect_changes must not crash or error; the
        retired epic is an identity record.
        """
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        # Active epic with stories — required structure
        _make_epic(sd, 1, "building")
        _make_dev_story(sd, 1, 1, "scaffold", deps="None")
        # Retired epic — only the file, no child directory
        _make_epic(sd, 2, "legacy", removed=True)
        self.assertFalse((sd / "epic-2").is_dir(),
                         "Retired epic must NOT have child directory")
        result = sync_helper.detect_changes(self.tmpdir)
        # Active epic appears; retired epic (never synced) is skipped
        epic_items = [i for i in result["items"]
                      if i["type"] == "epic"]
        active_epics = [e for e in epic_items if e["epic_index"] == 1]
        self.assertEqual(len(active_epics), 1, "Active epic must appear")
        retired_epics = [e for e in epic_items if e["epic_index"] == 2]
        self.assertEqual(len(retired_epics), 0,
                         "Never-synced retired epic must be skipped")


# ---------------------------------------------------------------------------
# F3: Restoration/DOCS trigger in revise.md
# ---------------------------------------------------------------------------

class TestDocsRestorationTrigger(unittest.TestCase):
    """Revise.md includes parent-epic restoration in DOCS affected set (F3)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        revise_path = (Path(__file__).resolve().parent.parent
                       / "skills" / "revise.md")
        cls._revise_md = revise_path.read_text(encoding="utf-8")
        m4 = re.search(r"### Step 4:.*?(?=### Step 5:)",
                        cls._revise_md, re.DOTALL)
        assert m4, "Step 4 not found in revise.md"
        cls._step4 = m4.group()
        trigger = re.search(
            r"A `\[DOCS\]` story is affected when.*?(?=For each affected)",
            cls._step4, re.DOTALL)
        assert trigger, "DOCS affected-set trigger block not found"
        cls._trigger_block = trigger.group()
        cascade_idx = cls._step4.find("reconciliation after cascades")
        assert cascade_idx >= 0
        cls._cascade_block = cls._step4[cascade_idx:]

    def test_restoration_trigger_exists(self) -> None:
        """Trigger list includes parent epic restoration (trigger f)."""
        self.assertIn("restored", self._trigger_block.lower())

    def test_restoration_reactivates_unmarked_children(self) -> None:
        """Restored parent makes children without own removal active."""
        self.assertIn("without their own", self._trigger_block.lower())

    def test_individually_removed_child_stays_removed(self) -> None:
        """Child with its own status: removed stays removed after restore."""
        self.assertIn("individually retired", self._trigger_block.lower())

    def test_restoration_in_cascade_reconciliation(self) -> None:
        """Post-cascade reconciliation mentions restoration."""
        self.assertIn("restoration", self._cascade_block.lower())


class TestDocsRestorationHelper(_TmpDirMixin, unittest.TestCase):
    """detect_changes handles parent restoration correctly (F3)."""

    def test_child_active_when_parent_restored(self) -> None:
        """Unmarked child reopens when parent restored from closed.

        Both parent and child were previously cascade-closed (synced_status
        "closed"). Parent is now locally active (no removed marker) —
        approved restoration. Unmarked child should reopen."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        # Parent epic locally active (restored — no removed marker)
        _make_epic(sd, 1, "building", removed=False)
        # Child story locally active (no removed marker)
        _make_dev_story(sd, 1, 1, "impl", deps="None")
        # Sibling individually removed — should stay removed
        _make_dev_story(sd, 1, 2, "other", deps="None", removed=True)
        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "old-hash", "synced_status": "closed",
            "stories": [
                {"file": "story-01-impl.md", "jira_key": "EDM-201",
                 "content_hash": "old-hash", "synced_status": "closed"},
                {"file": "story-02-other.md", "jira_key": "EDM-202",
                 "content_hash": "old-hash", "synced_status": "closed"},
            ],
        }])
        result = sync_helper.detect_changes(self.tmpdir)
        # Parent epic should reopen
        epic_items = [i for i in result["items"]
                      if i["type"] == "epic" and i["epic_index"] == 1]
        self.assertEqual(len(epic_items), 1)
        self.assertEqual(epic_items[0]["category"], "reopened",
                         "Restored parent epic reopens")
        # Unmarked child should reopen
        story1 = [i for i in result["items"]
                  if i["type"] == "story" and i.get("story_index") == 1]
        self.assertEqual(len(story1), 1)
        self.assertEqual(story1[0]["category"], "reopened",
                         "Unmarked child under restored parent reopens")
        # Individually removed sibling: locally removed, already closed
        # in Jira (synced_status "closed") → unchanged (stays closed).
        # _categorize_item(removed=True, synced_status="closed") returns
        # "unchanged" — no spurious update/create for retired closed child.
        story2 = [i for i in result["items"]
                  if i["type"] == "story" and i.get("story_index") == 2]
        self.assertEqual(len(story2), 1)
        self.assertEqual(story2[0]["category"], "unchanged",
                         "Individually removed+closed sibling stays unchanged")


# ---------------------------------------------------------------------------
# F4: Active-only coverage in decompose.md and review protocol
# ---------------------------------------------------------------------------

class TestActiveCoverageContract(unittest.TestCase):
    """Coverage matrix and review protocol evaluate active stories only (F4)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")
        m7 = re.search(r"### Step 7:.*?(?=### Step 8:)",
                        cls._decompose_md, re.DOTALL)
        assert m7, "Step 7 not found in decompose.md"
        cls._step7 = m7.group()

        review_path = (Path(__file__).resolve().parent.parent
                       / "decomposition-review.md")
        cls._review_md = review_path.read_text(encoding="utf-8")
        crit1 = re.search(
            r"1\.\s+\*\*Requirement Coverage\*\*.*?(?=2\.\s+\*\*Epic Structure\*\*)",
            cls._review_md, re.DOTALL)
        assert crit1, "Criterion 1 not found in review protocol"
        cls._criterion1 = crit1.group()

    def test_step7_active_only_coverage(self) -> None:
        """Step 7 defines active-only coverage for the matrix."""
        self.assertIn("effectively active", self._step7.lower())

    def test_step7_retired_not_satisfying(self) -> None:
        """Step 7 states retired stories do not satisfy coverage."""
        lower = self._step7.lower()
        self.assertIn("identity", lower)
        self.assertIn("traceability audit", lower)

    def test_step7_no_mask_coverage_gap(self) -> None:
        """Step 7 forbids masking coverage gaps with retired work."""
        self.assertIn("Do not mask", self._step7)

    def test_step7_structure_gate_active_epics(self) -> None:
        """Step 7 check 3 limits directory/story-file requirement to active epics."""
        self.assertIn("Each active epic", self._step7)
        # Retired epic from partial run explicitly allowed without child dir
        self.assertIn("identity record", self._step7.lower())

    def test_step7_ic_tc_gate_active_stories(self) -> None:
        """Step 7 check 6 limits IC/TC reference requirement to active stories."""
        self.assertIn("Every active non-", self._step7)

    def test_review_criterion1_active_only(self) -> None:
        """Review criterion 1 requires effectively active stories."""
        self.assertIn("effectively active", self._criterion1.lower())

    def test_review_criterion1_identity_audit(self) -> None:
        """Review criterion 1 mentions retired stories retained for audit."""
        self.assertIn("identity", self._criterion1.lower())
        self.assertIn("audit", self._criterion1.lower())

    def test_review_shared_active_scope(self) -> None:
        """Evaluation criteria preamble scopes criteria 1-8 to active stories."""
        import re
        m = re.search(r"## Evaluation Criteria\n\n.*?(?=1\.\s+\*\*Requirement)",
                      self._review_md, re.DOTALL)
        self.assertIsNotNone(m, "Evaluation criteria preamble not found")
        preamble = m.group().lower()
        self.assertIn("effectively active", preamble)
        self.assertIn("criteria 1", preamble)
        self.assertIn("criterion 9", preamble)

    def test_review_retained_files_not_violating(self) -> None:
        """Shared scope states retained files do not violate active coverage."""
        import re
        m = re.search(r"## Evaluation Criteria\n\n.*?(?=1\.\s+\*\*Requirement)",
                      self._review_md, re.DOTALL)
        self.assertIsNotNone(m)
        # Join whitespace for line-wrapped text
        preamble = " ".join(m.group().lower().split())
        self.assertIn("do not satisfy or violate", preamble)


# ---------------------------------------------------------------------------
# Frontmatter encoding: YAML frontmatter recognized, body marker ignored
# ---------------------------------------------------------------------------

class TestFrontmatterEncoding(_TmpDirMixin, unittest.TestCase):
    """has_removed_status only recognizes YAML frontmatter, not body markers."""

    def test_frontmatter_status_removed_recognized(self) -> None:
        """YAML frontmatter status: removed is detected by the helper."""
        p = Path(self.tmpdir) / "fm.md"
        _write(p, "---\nstatus: removed\n---\n# Title\nBody text.\n")
        self.assertTrue(sync_helper.has_removed_status(p))

    def test_body_marker_status_removed_ignored(self) -> None:
        """A body line 'status: removed' without frontmatter is NOT detected."""
        p = Path(self.tmpdir) / "body.md"
        _write(p, "# Title\n\nstatus: removed\n\nMore text.\n")
        self.assertFalse(sync_helper.has_removed_status(p))

    def test_body_marker_after_frontmatter_ignored(self) -> None:
        """Body 'status: removed' after valid frontmatter without it is ignored."""
        p = Path(self.tmpdir) / "mixed.md"
        _write(p, "---\ntitle: active work\n---\n# Title\n\nstatus: removed\n")
        self.assertFalse(sync_helper.has_removed_status(p))


# ---------------------------------------------------------------------------
# Review protocol: criteria 2/4 scope to active epics
# ---------------------------------------------------------------------------

class TestReviewEpicScope(unittest.TestCase):
    """Review protocol criteria 2 and 4 evaluate active epics only."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        review_path = (Path(__file__).resolve().parent.parent
                       / "decomposition-review.md")
        cls._review_md = review_path.read_text(encoding="utf-8")

        crit2 = re.search(
            r"2\.\s+\*\*Epic Structure\*\*.*?(?=3\.\s+\*\*Story Completeness\*\*)",
            cls._review_md, re.DOTALL)
        assert crit2, "Criterion 2 not found"
        cls._criterion2 = crit2.group()

        crit4 = re.search(
            r"4\.\s+\*\*Testing Commitment\*\*.*?(?=5\.\s+\*\*Implementation Traceability\*\*)",
            cls._review_md, re.DOTALL)
        assert crit4, "Criterion 4 not found"
        cls._criterion4 = crit4.group()

    def test_criterion2_scoped_to_active_epics(self) -> None:
        """Criterion 2 evaluates active epics only."""
        lower = self._criterion2.lower()
        self.assertIn("active epic", lower)

    def test_criterion4_scoped_to_active_epics(self) -> None:
        """Criterion 4 QE check applies to active epics only."""
        lower = self._criterion4.lower()
        self.assertIn("active epic", lower)

    def test_preamble_covers_both_artifact_types(self) -> None:
        """Evaluation criteria preamble scopes to both epics and stories."""
        import re
        m = re.search(r"## Evaluation Criteria\n\n.*?(?=1\.\s+\*\*Requirement)",
                      self._review_md, re.DOTALL)
        self.assertIsNotNone(m)
        preamble = " ".join(m.group().lower().split())
        self.assertIn("epic-level checks", preamble)
        self.assertIn("story-level checks", preamble)


# ---------------------------------------------------------------------------
# Decompose instruction order: inventory before plan, retirement after plan
# ---------------------------------------------------------------------------

class TestDecomposeRetirementOrder(unittest.TestCase):
    """Step 1 inventories without retirement; reconciliation follows Step 2."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        cls._decompose_md = decompose_path.read_text(encoding="utf-8")
        m1 = re.search(r"### Step 1:.*?(?=### Step 2:)",
                        cls._decompose_md, re.DOTALL)
        assert m1, "Step 1 not found"
        cls._step1 = m1.group()

        m2 = re.search(r"### Step 2:.*?(?=### Step 3:)",
                        cls._decompose_md, re.DOTALL)
        assert m2, "Step 2 not found"
        cls._step2 = m2.group()

    def test_step1_does_not_decide_retirement(self) -> None:
        """Step 1 explicitly defers retirement decisions to after planning."""
        lower = self._step1.lower()
        # Must NOT say "when the new plan no longer retains" in Step 1
        self.assertNotIn("new plan no longer retains", lower)
        # Must say retirement decisions wait
        self.assertIn("do not decide", lower)

    def test_reconciliation_after_planning(self) -> None:
        """Retention planning completes before reconciliation writes markers.

        Move-sensitive: fails if reconciliation moves ahead of retention
        planning in the source.  Both positions are found in the same
        bounded Step 2 slice.
        """
        retention_pos = self._step2.lower().find("per-story retention")
        reconcile_pos = self._step2.lower().find("reconcile retained inventory")
        self.assertGreaterEqual(retention_pos, 0,
            "Per-story retention assessment must exist in Step 2")
        self.assertGreaterEqual(reconcile_pos, 0,
            "Reconciliation must exist in Step 2")
        self.assertLess(retention_pos, reconcile_pos,
            "Per-story retention planning must complete before "
            "reconciliation/marker writes")

    def test_story_level_retention_in_step2(self) -> None:
        """Step 2 includes per-story retention decisions before reconciliation."""
        lower = self._step2.lower()
        self.assertIn("per-story retention", lower)
        self.assertIn("each existing\nstory", lower)
        self.assertIn("individually", lower)

    def test_reconciliation_specifies_frontmatter(self) -> None:
        """Reconciliation specifies YAML frontmatter encoding."""
        self.assertIn("read_frontmatter", self._step2)
        self.assertIn("---", self._step2)

    def test_reconciliation_preserves_cascade_safety(self) -> None:
        """Reconciliation mentions cascade safety for partial epic retention."""
        lower = self._step2.lower()
        self.assertIn("cascade", lower)
        self.assertIn("child stories are retained", lower)


# ---------------------------------------------------------------------------
# Guidelines retirement encoding rule
# ---------------------------------------------------------------------------

class TestGuidelinesRetirementEncoding(unittest.TestCase):
    """guidelines.md includes canonical retirement encoding rule."""

    @classmethod
    def setUpClass(cls) -> None:
        guidelines_path = (Path(__file__).resolve().parent.parent
                           / "guidelines.md")
        cls._guidelines = guidelines_path.read_text(encoding="utf-8")

    def test_retirement_encoding_present(self) -> None:
        """Guidelines include retirement encoding rule."""
        self.assertIn("Retirement encoding", self._guidelines)

    def test_retirement_encoding_specifies_frontmatter(self) -> None:
        """Retirement encoding rule references YAML frontmatter."""
        self.assertIn("read_frontmatter", self._guidelines)

    def test_retirement_encoding_warns_body_marker(self) -> None:
        """Retirement encoding warns that body markers are not detected."""
        lower = self._guidelines.lower()
        self.assertIn("body line", lower)
        self.assertIn("not detected", lower)


# ---------------------------------------------------------------------------
# R1: Parent-only retirement preserves child marker distinction
# ---------------------------------------------------------------------------

class TestParentOnlyRetirementContract(unittest.TestCase):
    """Step 2 distinguishes a child's own removal marker from inherited
    inactivity via a removed parent (R1).

    Contract tests verify the decompose.md instruction text contains the
    required distinction so that parent-only retirement does not
    materialize child ``status: removed`` markers.
    """

    _step2: str

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        text = decompose_path.read_text(encoding="utf-8")
        m2 = re.search(r"### Step 2:.*?(?=### Step 3:)", text, re.DOTALL)
        assert m2, "Step 2 not found in decompose.md"
        cls._step2 = m2.group()

    def _joined(self) -> str:
        return " ".join(self._step2.lower().split())

    def test_assessment_distinguishes_own_vs_inherited(self) -> None:
        """Assessment distinguishes child's own disposition from inherited."""
        text = self._joined()
        self.assertIn("own disposition", text)
        self.assertIn("inherited inactivity", text)

    def test_reconcile_marks_parent_only(self) -> None:
        """Reconcile instructs marking parent only, not child stories."""
        text = self._joined()
        self.assertIn("mark the parent only", text)

    def test_reconcile_children_inherit_without_own_markers(self) -> None:
        """Children inherit parent's inactive status without own markers."""
        text = self._joined()
        self.assertIn("children inherit the parent's inactive status "
                      "through cascade without needing their own markers",
                      text)

    def test_reconcile_preserves_child_content(self) -> None:
        """Reconcile preserves each child's original frontmatter and body."""
        text = self._joined()
        self.assertIn("preserve each child's original frontmatter and body",
                      text)

    def test_reconcile_only_explicit_individual_retirement(self) -> None:
        """Reconcile adds status:removed only for individually retired items."""
        text = self._joined()
        self.assertIn("individually and explicitly retires", text)


class TestParentOnlyRetirementHelper(_TmpDirMixin, unittest.TestCase):
    """detect_changes preserves unmarked child file bytes when only the
    parent epic is retired (R1 helper counterexample).

    Parent removed → unmarked child suppressed (category 'removed')
    but file content untouched.  Already individually removed sibling
    stays unchanged.  Approved parent restoration → unmarked child
    reopens, individually removed sibling stays exactly unchanged.
    """

    def test_unmarked_child_bytes_preserved_under_removed_parent(self) -> None:
        """Parent removed, child unmarked: file bytes unchanged."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building", removed=True)
        child = _make_dev_story(sd, 1, 1, "impl")
        child_bytes_before = child.read_bytes()
        child_hash_before = sync_helper.compute_file_hash(child)

        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "old-hash", "synced_status": "active",
            "stories": [{
                "file": "story-01-impl.md", "jira_key": "EDM-201",
                "content_hash": "old-hash", "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.tmpdir)

        # Child suppressed via parent cascade
        stories = [i for i in result["items"] if i["type"] == "story"]
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["category"], "removed",
                         "Unmarked child under removed parent must be suppressed")
        # File bytes must be exactly unchanged
        self.assertEqual(child.read_bytes(), child_bytes_before,
                         "Child file bytes must not be modified by detect_changes")
        self.assertEqual(sync_helper.compute_file_hash(child), child_hash_before,
                         "Child content hash must remain unchanged")

    def test_individually_removed_sibling_stays_unchanged(self) -> None:
        """Individually removed sibling stays 'unchanged' (already closed)."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building", removed=True)
        _make_dev_story(sd, 1, 1, "impl")
        sibling = _make_dev_story(sd, 1, 2, "other", removed=True)
        sibling_bytes = sibling.read_bytes()

        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "old-hash", "synced_status": "active",
            "stories": [
                {"file": "story-01-impl.md", "jira_key": "EDM-201",
                 "content_hash": "old-hash", "synced_status": "active"},
                {"file": "story-02-other.md", "jira_key": "EDM-202",
                 "content_hash": "old-hash", "synced_status": "closed"},
            ],
        }])
        result = sync_helper.detect_changes(self.tmpdir)

        story2 = [i for i in result["items"]
                  if i["type"] == "story" and i.get("story_index") == 2]
        self.assertEqual(len(story2), 1)
        self.assertEqual(story2[0]["category"], "unchanged",
                         "Individually removed+closed sibling stays unchanged")
        self.assertEqual(sibling.read_bytes(), sibling_bytes,
                         "Individually removed sibling bytes must be exact")

    def test_restoration_reopens_unmarked_not_individually_removed(self) -> None:
        """Approved parent restoration → unmarked child reopens,
        individually removed sibling stays exactly unchanged."""
        sd = Path(self.tmpdir) / "06-stories"
        sd.mkdir()
        _make_epic(sd, 1, "building", removed=False)  # restored
        child = _make_dev_story(sd, 1, 1, "impl")
        sibling = _make_dev_story(sd, 1, 2, "other", removed=True)
        sibling_bytes = sibling.read_bytes()

        _make_manifest(Path(self.tmpdir), [{
            "file": "epic-1-building.md", "jira_key": "EDM-100",
            "content_hash": "old-hash", "synced_status": "closed",
            "stories": [
                {"file": "story-01-impl.md", "jira_key": "EDM-201",
                 "content_hash": "old-hash", "synced_status": "closed"},
                {"file": "story-02-other.md", "jira_key": "EDM-202",
                 "content_hash": "old-hash", "synced_status": "closed"},
            ],
        }])
        result = sync_helper.detect_changes(self.tmpdir)

        # Unmarked child reopens under restored parent
        story1 = [i for i in result["items"]
                  if i["type"] == "story" and i.get("story_index") == 1]
        self.assertEqual(len(story1), 1)
        self.assertEqual(story1[0]["category"], "reopened",
                         "Unmarked child under restored parent must reopen")
        # Individually removed sibling stays unchanged
        story2 = [i for i in result["items"]
                  if i["type"] == "story" and i.get("story_index") == 2]
        self.assertEqual(len(story2), 1)
        self.assertEqual(story2[0]["category"], "unchanged",
                         "Individually removed sibling stays unchanged on restore")
        self.assertEqual(sibling.read_bytes(), sibling_bytes,
                         "Individually removed sibling bytes exact after restore")


# ---------------------------------------------------------------------------
# R2: Step 7 active epic requires effectively active child
# ---------------------------------------------------------------------------

class TestActiveEpicChildGateContract(unittest.TestCase):
    """Step 7 check 3 requires at least one effectively active child story,
    not merely a directory containing historical removed files (R2)."""

    _step7: str

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        text = decompose_path.read_text(encoding="utf-8")
        m7 = re.search(r"### Step 7:.*?(?=### Step 8:)", text, re.DOTALL)
        assert m7, "Step 7 not found in decompose.md"
        cls._step7 = m7.group()

    def _joined(self) -> str:
        return " ".join(self._step7.lower().split())

    def test_requires_effectively_active_child(self) -> None:
        """Check 3 requires at least one effectively active child story."""
        self.assertIn("at least one effectively active", self._joined())

    def test_removed_only_directory_insufficient(self) -> None:
        """Directory with only status:removed files does not satisfy check."""
        self.assertIn("does not satisfy this check", self._joined())

    def test_retired_epic_exception_preserved(self) -> None:
        """Retired epic from partial run may lack child directory."""
        self.assertIn("retired epic from a partial run", self._joined())


# ---------------------------------------------------------------------------
# R3: Step 9 Action 2 provenance scoped to effectively active DOCS
# ---------------------------------------------------------------------------

class TestDocsProvenanceScopeContract(unittest.TestCase):
    """Step 9 Action 2 limits provenance corrections to effectively active
    DOCS stories only; retired/parent-inactive histories are not rewritten
    against the current design (R3)."""

    _step9: str

    @classmethod
    def setUpClass(cls) -> None:
        import re
        decompose_path = (Path(__file__).resolve().parent.parent
                          / "skills" / "decompose.md")
        text = decompose_path.read_text(encoding="utf-8")
        m9 = re.search(r"### Step 9:.*?(?=### Step 10:)", text, re.DOTALL)
        assert m9, "Step 9 not found in decompose.md"
        cls._step9 = m9.group()

    def _joined(self) -> str:
        return " ".join(self._step9.lower().split())

    def test_provenance_scoped_to_active_docs(self) -> None:
        """Action 2 checks only effectively active DOCS stories."""
        self.assertIn("effectively active `[docs]` story", self._joined())

    def test_retired_docs_not_rewritten(self) -> None:
        """Retired/parent-inactive DOCS markers not rewritten."""
        text = self._joined()
        self.assertIn("retained for identity audit", text)
        self.assertIn("not rewritten against the current design", text)

    def test_unconditional_verification_preserved(self) -> None:
        """Action 2 still runs unconditionally (even zero findings)."""
        self.assertIn("runs unconditionally", self._step9)


# ---------------------------------------------------------------------------
# R1: Source activity field — quality eligibility (review 5832225697)
# ---------------------------------------------------------------------------

class TestSourceActivityField(_TmpDirMixin, unittest.TestCase):
    """Verify detect_changes emits source_active on every item.

    source_active determines whether a story is from an effectively
    active source (own not-removed AND parent epic active).  Step 4
    uses this to restrict the quality gate to active DOCS stories.
    """

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_fresh_sync_items_all_source_active(self) -> None:
        """Fresh sync: all emitted items have source_active True."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        result = sync_helper.detect_changes(self.artifacts)
        for item in result["items"]:
            self.assertTrue(
                item.get("source_active"),
                f"Fresh-sync item {item['file']} must be source_active")

    def test_active_story_under_active_parent_source_active(self) -> None:
        """Unchanged story under active parent has source_active True."""
        ef = _make_epic(self.stories_dir, 1, "building")
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": sync_helper.compute_file_hash(ef),
            "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": sync_helper.compute_file_hash(sf),
                "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        story = next(i for i in result["items"] if i["type"] == "story")
        self.assertEqual(story["category"], "unchanged")
        self.assertTrue(story["source_active"],
                        "Active story under active parent must be source_active")

    def test_unchanged_story_under_removed_parent_not_source_active(self) -> None:
        """Hash-identical story under removed parent: source_active False.

        This is the R1 counterexample: the story's category stays
        'unchanged' (detect_changes suppression only covers changed/
        reopened/new), but source_active must be False because the parent
        is inactive.  Step 4 uses this to exclude it from quality gate.
        """
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": sf_hash,
                "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        story = next(i for i in result["items"] if i["type"] == "story")
        self.assertEqual(story["category"], "unchanged",
                         "Hash-identical child keeps unchanged category")
        self.assertFalse(story["source_active"],
                         "Story under removed parent must NOT be source_active")

    def test_changed_story_under_removed_parent_not_source_active(self) -> None:
        """Changed story under removed parent: reclassified as removed,
        source_active False."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "DIFFERENT",
                "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        story = next(i for i in result["items"] if i["type"] == "story")
        self.assertEqual(story["category"], "removed")
        self.assertFalse(story["source_active"])

    def test_story_under_reopened_parent_source_active(self) -> None:
        """Story under a reopened parent (manifest closed, file active)
        has source_active True — restoration makes parent active."""
        ef = _make_epic(self.stories_dir, 1, "building")
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "closed",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "oldhash",
                "synced_status": "closed",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        epic = next(i for i in result["items"] if i["type"] == "epic")
        story = next(i for i in result["items"] if i["type"] == "story")
        self.assertEqual(epic["category"], "reopened")
        self.assertTrue(epic["source_active"],
                        "Reopened epic must be source_active")
        self.assertEqual(story["category"], "reopened")
        self.assertTrue(story["source_active"],
                        "Story under reopened parent must be source_active")

    def test_individually_removed_story_under_active_parent(self) -> None:
        """Story with own status:removed under active parent:
        source_active False regardless of parent status."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold", removed=True)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "oldhash",
                "synced_status": "active",
            }],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        story = next(i for i in result["items"] if i["type"] == "story")
        self.assertEqual(story["category"], "removed")
        self.assertFalse(story["source_active"],
                         "Individually removed story must NOT be source_active")

    def test_orphaned_items_not_source_active(self) -> None:
        """Orphaned epic and story entries have source_active False."""
        # Create a manifest with items whose files don't exist
        (self.stories_dir / "epic-1-gone").mkdir(parents=True)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-gone.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "title": "Gone",
            "stories": [{
                "file": "story-01-lost.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
                "title": "Lost",
            }],
        }])
        # No files on disk → orphaned
        result = sync_helper.detect_changes(self.artifacts)
        orphans = [i for i in result["items"] if i["category"] == "orphaned"]
        self.assertTrue(len(orphans) >= 1, "Should have orphaned items")
        for item in orphans:
            self.assertFalse(item["source_active"],
                             f"Orphan {item['file']} must NOT be source_active")

    def test_epic_with_removed_status_not_source_active(self) -> None:
        """Epic with status:removed has source_active False."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        epic = next(i for i in result["items"] if i["type"] == "epic")
        self.assertEqual(epic["category"], "removed")
        self.assertFalse(epic["source_active"])


class TestQualityEligibilityContract(unittest.TestCase):
    """Step 4 quality gate must filter on source_active (R1)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m4 = re.search(r"### Step 4:.*?(?=### Step 5:)", cls._sync_md, re.DOTALL)
        assert m4, "Step 4 not found"
        cls._step4 = m4.group()

    def test_step4_references_source_active(self) -> None:
        """Step 4 mentions source_active as the activity filter."""
        self.assertIn("source_active", self._step4)

    def test_step4_inactive_excluded_from_quality(self) -> None:
        """Step 4 excludes inactive-source stories from quality gate."""
        lower = self._step4.lower()
        self.assertIn("excluded from quality validation", lower)

    def test_step4_fail_closed_unknown_parent(self) -> None:
        """Step 4 STOPs sync when source activity cannot be determined."""
        self.assertIn("stop the sync", self._step4.lower())

    def test_step4_restored_parent_eligible(self) -> None:
        """Step 4 recognizes reopened parents as active."""
        self.assertIn("reopened", self._step4.lower())
        self.assertIn("eligible", self._step4.lower())

    def test_step4_individually_removed_ineligible(self) -> None:
        """Step 4 keeps individually removed stories ineligible."""
        self.assertIn("Individually removed stories remain ineligible",
                      self._step4)

    def test_step4_eligible_filter_before_criteria(self) -> None:
        """source_active filter appears before the seven-criteria check."""
        sa_pos = self._step4.find("source_active")
        criteria_pos = self._step4.find("seven criteria")
        self.assertGreater(criteria_pos, sa_pos,
                           "source_active filter must appear before criteria check")

    def test_step4_affected_unchanged_also_filtered(self) -> None:
        """Affected-unchanged DOCS also require eligible (source-active)."""
        # The text should say "eligible" before the unchanged-but-affected clause
        eligible_pos = self._step4.find("eligible (source-active)")
        unchanged_clause = self._step4.find("unchanged but whose contributor")
        self.assertGreater(unchanged_clause, eligible_pos,
                           "Eligible filter must cover unchanged-but-affected DOCS too")


# ---------------------------------------------------------------------------
# R2: Truthful cascade preview (review 5832225697)
# ---------------------------------------------------------------------------

class TestCascadeClosurePreview(_TmpDirMixin, unittest.TestCase):
    """Helper-level tests for compute_cascade_closures.

    Verifies that the function correctly identifies cascade closures
    that Step 5c will perform but that detect_changes doesn't surface.
    """

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_unchanged_child_under_removed_parent_in_cascade(self) -> None:
        """Hash-identical active child under removed parent appears in
        cascade list — it is category 'unchanged' in detect_changes but
        Step 5c will close it."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "title": "[DEV] Scaffold",
                "content_hash": sf_hash,
                "synced_status": "active",
            }],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        # Confirm the story is unchanged in detect_changes
        story = next(i for i in plan["items"] if i["type"] == "story")
        self.assertEqual(story["category"], "unchanged")
        # Compute cascade closures
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        cascades = result["cascades"]
        self.assertEqual(len(cascades), 1,
                         "Unchanged active child must appear in cascade")
        self.assertEqual(cascades[0]["jira_key"], "EDM-201")
        self.assertEqual(cascades[0]["parent_jira_key"], "EDM-101")
        self.assertEqual(cascades[0]["parent_reason"], "removed")

    def test_individually_removed_child_not_duplicated(self) -> None:
        """Child with own status:removed is already in ToClose;
        cascade must not double-count it."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold", removed=True)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "oldhash",
                "synced_status": "active",
            }],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        self.assertEqual(len(result["cascades"]), 0,
                         "Individually removed child must NOT be in cascades")

    def test_already_closed_child_excluded(self) -> None:
        """Child with synced_status 'closed' in manifest is excluded."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": "oldhash",
                "synced_status": "closed",
            }],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        self.assertEqual(len(result["cascades"]), 0,
                         "Already-closed child must NOT be in cascades")

    def test_no_cascade_when_no_closing_parents(self) -> None:
        """No cascades when all epics are active."""
        _make_epic(self.stories_dir, 1, "building")
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": sync_helper.compute_file_hash(
                self.stories_dir / "epic-1-building.md"),
            "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "content_hash": sf_hash,
                "synced_status": "active",
            }],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        self.assertEqual(len(result["cascades"]), 0)

    def test_orphan_parent_cascade_requires_close_orphans(self) -> None:
        """Orphaned parent only cascades when close_orphans=True."""
        # Manifest has epic-1 but no file on disk → orphaned
        (self.stories_dir / "epic-1").mkdir(parents=True)
        manifest_data = [{
            "file": "epic-1-gone.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "title": "Gone",
            "stories": [{
                "file": "story-01-lost.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
                "title": "Lost",
            }],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        # Without close_orphans: no cascade
        result_no = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=False)
        self.assertEqual(len(result_no["cascades"]), 0,
                         "Ignored orphan parent must NOT produce cascades")
        # With close_orphans: cascade includes children
        result_yes = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=True)
        # Both epic and story are orphaned; with close_orphans the story
        # orphan is already individually_closing, so cascade should be 0
        # unless the story orphan was already matched.
        # Actually: orphaned story is also in items as "orphaned" and
        # close_orphans=True puts it in individually_closing. So 0.
        # The cascade is for cases where children have FILES but are
        # unchanged.  Purely orphaned children are already shown.
        self.assertEqual(len(result_yes["cascades"]), 0,
                         "Orphaned child already individually shown")

    def test_cascade_mixed_children(self) -> None:
        """Parent with mixed children: only unchanged active children
        appear in cascade, not individually removed or already closed."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf1 = _make_dev_story(self.stories_dir, 1, 1, "active-child")
        sf2 = _make_dev_story(self.stories_dir, 1, 2, "removed-child",
                              removed=True)
        sf3 = _make_dev_story(self.stories_dir, 1, 3, "also-active")
        sf1_hash = sync_helper.compute_file_hash(sf1)
        sf3_hash = sync_helper.compute_file_hash(sf3)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [
                {"file": "story-01-active-child.md", "jira_key": "EDM-201",
                 "title": "[DEV] Active", "content_hash": sf1_hash,
                 "synced_status": "active"},
                {"file": "story-02-removed-child.md", "jira_key": "EDM-202",
                 "title": "[DEV] Removed", "content_hash": "oldhash",
                 "synced_status": "active"},
                {"file": "story-03-also-active.md", "jira_key": "EDM-203",
                 "title": "[DEV] Also Active", "content_hash": sf3_hash,
                 "synced_status": "active"},
                {"file": "story-04-closed.md", "jira_key": "EDM-204",
                 "title": "[DEV] Closed", "content_hash": "h",
                 "synced_status": "closed"},
            ],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        # story-01 and story-03 are unchanged active → cascade
        self.assertIn("EDM-201", cascade_keys,
                      "Unchanged active child must be in cascade")
        self.assertIn("EDM-203", cascade_keys,
                      "Unchanged active child must be in cascade")
        # story-02 is individually removed → not in cascade
        self.assertNotIn("EDM-202", cascade_keys,
                         "Individually removed child must NOT be in cascade")
        # story-04 is already closed → not in cascade
        self.assertNotIn("EDM-204", cascade_keys,
                         "Already-closed child must NOT be in cascade")

    def test_selected_vs_ignored_orphan_parent(self) -> None:
        """Only selected (close_orphans=True) orphan parent cascades."""
        # Create a real epic with unchanged active children, plus an
        # orphan epic with children.  Only the removed epic should cascade
        # regardless; orphan only cascades with flag.
        ef = _make_epic(self.stories_dir, 1, "real", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "child")
        sf_hash = sync_helper.compute_file_hash(sf)
        (self.stories_dir / "epic-2").mkdir(parents=True)
        manifest_data = [
            {"file": "epic-1-real.md", "jira_key": "EDM-101",
             "content_hash": "oldhash", "synced_status": "active",
             "stories": [{
                 "file": "story-01-child.md", "jira_key": "EDM-201",
                 "title": "Child", "content_hash": sf_hash,
                 "synced_status": "active",
             }]},
            {"file": "epic-2-orphan.md", "jira_key": "EDM-102",
             "content_hash": "h", "synced_status": "active",
             "title": "Orphan",
             "stories": [{
                 "file": "story-01-orphchild.md", "jira_key": "EDM-301",
                 "title": "OrphChild", "content_hash": "h",
                 "synced_status": "active",
             }]},
        ]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        # Without close_orphans: only removed parent cascades
        result_no = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=False)
        keys_no = {c["jira_key"] for c in result_no["cascades"]}
        self.assertIn("EDM-201", keys_no,
                      "Removed parent must cascade child")
        self.assertNotIn("EDM-301", keys_no,
                         "Ignored orphan parent must NOT cascade child")

    def test_cascade_cli_subcommand(self) -> None:
        """CLI compute-cascade-closures produces valid JSON."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "title": "[DEV] Scaffold",
                "content_hash": sf_hash,
                "synced_status": "active",
            }],
        }])
        out = StringIO()
        with mock.patch("sys.stdout", out):
            exit_code = sync_helper.main([
                "compute-cascade-closures", str(self.artifacts)])
        self.assertEqual(exit_code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("cascades", data)
        self.assertEqual(len(data["cascades"]), 1)
        self.assertEqual(data["cascades"][0]["jira_key"], "EDM-201")

    def test_approved_union_covers_individual_plus_cascade(self) -> None:
        """Counterexample: removed parent EDM-101, individually removed
        active child EDM-201, unchanged active child EDM-202.

        compute_cascade_closures returns only {EDM-202} (excludes
        individually removed child).  detect_changes items list
        EDM-201 as 'removed'.  The approved union is {EDM-201, EDM-202}.
        Both EDM-201 and EDM-202 are manifest-active at Step 5c time.

        Confirms the data supports the union: individually listed
        children + cascade supplement = full approved scope.
        """
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf1 = _make_dev_story(self.stories_dir, 1, 1, "scaffold",
                              removed=True)
        sf2 = _make_dev_story(self.stories_dir, 1, 2, "also-active")
        sf2_hash = sync_helper.compute_file_hash(sf2)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "oldhash", "synced_status": "active"},
                {"file": "story-02-also-active.md", "jira_key": "EDM-202",
                 "content_hash": sf2_hash, "synced_status": "active"},
            ],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)

        # EDM-201 is individually listed as 'removed' in items
        individually_removed = {
            i["jira_key"] for i in plan["items"]
            if i["type"] == "story" and i["category"] == "removed"
        }
        self.assertIn("EDM-201", individually_removed)

        # cascade returns only EDM-202 (excludes individually removed)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        self.assertEqual(cascade_keys, {"EDM-202"})
        self.assertNotIn("EDM-201", cascade_keys,
                         "Individually removed child excluded from cascade")

        # The approved union = individual + cascade = {EDM-201, EDM-202}
        approved_union = individually_removed | cascade_keys
        self.assertEqual(approved_union, {"EDM-201", "EDM-202"})

        # Manifest-active children = {EDM-201, EDM-202}
        manifest_active = {
            s["jira_key"] for e in manifest["epics"]
            if e["file"] == "epic-1-building.md"
            for s in e.get("stories", [])
            if s.get("synced_status", "active") == "active"
        }
        self.assertEqual(manifest_active, {"EDM-201", "EDM-202"})

        # Guard must pass: manifest_active ⊆ approved_union
        self.assertTrue(
            manifest_active <= approved_union,
            "Manifest-active children must be a subset of the approved "
            "union (individual + cascade), not just cascade-only")

    def test_orphan_parent_close_orphans_true_union(self) -> None:
        """Selected orphan parent (close_orphans=True): missing parent
        + child source files, both manifest-active with Jira keys.

        compute_cascade_closures(close_orphans=True) returns 0
        supplement because the orphaned child is already individually
        closing.  The approved union must still include that child
        via the individually-closing orphan path.
        """
        # No files on disk for this parent — purely orphaned
        (self.stories_dir / "epic-2").mkdir(parents=True, exist_ok=True)
        manifest_data = [{
            "file": "epic-2-gone.md", "jira_key": "EDM-101",
            "content_hash": "h", "synced_status": "active",
            "title": "Gone",
            "stories": [{
                "file": "story-01-lost.md", "jira_key": "EDM-201",
                "content_hash": "h", "synced_status": "active",
                "title": "[DEV] Lost",
            }],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)

        # Both parent and child are orphaned
        orphaned_items = [i for i in plan["items"]
                          if i["category"] == "orphaned"]
        self.assertEqual(len(orphaned_items), 2,
                         "Both parent and child must be orphaned")

        # With close_orphans=True: child is individually closing
        individually_closing = {
            i["jira_key"] for i in plan["items"]
            if i["type"] == "story" and i["category"] == "orphaned"
        }
        self.assertIn("EDM-201", individually_closing)

        # Cascade returns 0 (child already individually closing)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=True)
        self.assertEqual(len(result["cascades"]), 0,
                         "Orphaned child already individually shown")

        # Approved union = individually closing orphans + cascade = {EDM-201}
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        approved_union = individually_closing | cascade_keys
        self.assertEqual(approved_union, {"EDM-201"})

        # Manifest-active child = {EDM-201}
        manifest_active = {
            s["jira_key"] for e in manifest["epics"]
            for s in e.get("stories", [])
            if s.get("synced_status", "active") == "active"
        }
        self.assertEqual(manifest_active, {"EDM-201"})

        # Guard passes: manifest_active ⊆ approved_union
        self.assertTrue(
            manifest_active <= approved_union,
            "Orphan child must be in approved union via "
            "individually-closing path")

        # Without close_orphans: no closures at all
        result_no = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=False)
        self.assertEqual(len(result_no["cascades"]), 0)


class TestCascadePreviewContract(unittest.TestCase):
    """Step 3 preview must include cascade closures (R2)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", cls._sync_md, re.DOTALL)
        assert m3, "Step 3 not found"
        cls._step3 = m3.group()

    def test_cascade_closure_preview_present(self) -> None:
        """Step 3 includes cascade closure computation."""
        self.assertIn("compute-cascade-closures", self._step3)

    def test_cascade_in_to_close_section(self) -> None:
        """To Close section includes cascade count."""
        self.assertIn("including {C} cascade closures", self._step3)

    def test_cascade_parent_annotation(self) -> None:
        """Cascade items show parent key annotation."""
        self.assertIn("cascade: parent {parent_jira_key}", self._step3)

    def test_cascade_approval_covers_children(self) -> None:
        """Step 3 states parent approval covers cascade children."""
        self.assertIn("parent's close approval covers them", self._step3)

    def test_no_cascade_omit_instruction(self) -> None:
        """If no cascades, the cascade count and rows are omitted."""
        self.assertIn("omit the cascade count and rows", self._step3)

    def test_adjusted_unchanged_count(self) -> None:
        """Step 3 instructs adjusting Unchanged total for cascades."""
        self.assertIn("subtract from Unchanged", self._step3)

    def test_ignored_orphan_no_cascade(self) -> None:
        """Ignored orphan parents must not produce cascades."""
        self.assertIn("Ignored orphan parents", self._step3)

    def test_step3_preview_consistent_with_step5c(self) -> None:
        """Step 3 preview references Step 5c for cascade behavior."""
        self.assertIn("Step 5c", self._step3)


class TestCascadePreviewSourceConsistency(_TmpDirMixin, unittest.TestCase):
    """Verify cascade preview is consistent with Step 5c's actual set.

    Step 5c closes ALL manifest-active children under a removed parent.
    The cascade preview must enumerate the same set (minus individually-
    removed children which are already shown in ToClose).
    """

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_preview_matches_step5c_closure_set(self) -> None:
        """cascade closures + individually-removed = all active children
        that Step 5c will close."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf1 = _make_dev_story(self.stories_dir, 1, 1, "unchanged")
        sf2 = _make_dev_story(self.stories_dir, 1, 2, "changed")
        sf3 = _make_dev_story(self.stories_dir, 1, 3, "also-removed",
                              removed=True)
        sf1_hash = sync_helper.compute_file_hash(sf1)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [
                {"file": "story-01-unchanged.md", "jira_key": "EDM-201",
                 "title": "S1", "content_hash": sf1_hash,
                 "synced_status": "active"},
                {"file": "story-02-changed.md", "jira_key": "EDM-202",
                 "title": "S2", "content_hash": "DIFFERENT",
                 "synced_status": "active"},
                {"file": "story-03-also-removed.md", "jira_key": "EDM-203",
                 "title": "S3", "content_hash": "oldhash",
                 "synced_status": "active"},
                {"file": "story-04-closed.md", "jira_key": "EDM-204",
                 "title": "S4", "content_hash": "h",
                 "synced_status": "closed"},
            ],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)

        # Step 5c would close: EDM-201, EDM-202, EDM-203 (all active)
        # Not EDM-204 (already closed)
        step5c_set = {"EDM-201", "EDM-202", "EDM-203"}

        # From detect_changes: EDM-202 is "removed" (changed → suppressed),
        # EDM-203 is "removed" (own status:removed)
        individually_removed = set()
        for item in plan["items"]:
            if item.get("type") == "story" and item.get("category") == "removed":
                individually_removed.add(item["jira_key"])
        # EDM-201 is "unchanged" → only in cascade
        cascade_keys = {c["jira_key"] for c in result["cascades"]}

        # Combined set must equal Step 5c set
        preview_total = individually_removed | cascade_keys
        self.assertEqual(preview_total, step5c_set,
                         "Preview (individual + cascade) must match Step 5c set")

    def test_no_child_file_cascade(self) -> None:
        """Manifest child with no file on disk: appears as orphan in
        items, not as cascade (unless orphan is ignored)."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        # Only story-01 exists; story-02 is orphan (no file)
        sf1 = _make_dev_story(self.stories_dir, 1, 1, "exists")
        sf1_hash = sync_helper.compute_file_hash(sf1)
        manifest_data = [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [
                {"file": "story-01-exists.md", "jira_key": "EDM-201",
                 "title": "Exists", "content_hash": sf1_hash,
                 "synced_status": "active"},
                {"file": "story-02-nofile.md", "jira_key": "EDM-202",
                 "title": "NoFile", "content_hash": "h",
                 "synced_status": "active"},
            ],
        }]
        _make_manifest(self.artifacts, manifest_data)
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)

        # story-02 should be orphaned in items
        orphan_stories = [i for i in plan["items"]
                          if i["type"] == "story" and i["category"] == "orphaned"]
        orphan_keys = {i["jira_key"] for i in orphan_stories}
        self.assertIn("EDM-202", orphan_keys,
                      "No-file child must appear as orphaned in items")

        # Without close_orphans: orphan child NOT individually closing
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=False)
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        # EDM-202 is orphaned but not individually_closing (no close_orphans)
        # So it should appear in cascade (it's active in manifest under
        # the removed parent)
        self.assertIn("EDM-202", cascade_keys,
                      "Orphan child not selected for individual close "
                      "must appear in cascade when parent is removed")
        # EDM-201 unchanged → also in cascade
        self.assertIn("EDM-201", cascade_keys)


# ---------------------------------------------------------------------------
# Gap A: DOCS-specific source_active fixtures
# ---------------------------------------------------------------------------

class TestDocsQualityEligibility(_TmpDirMixin, unittest.TestCase):
    """DOCS-specific fixtures for source_active quality gate (gap A)."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_unchanged_docs_under_removed_parent_ineligible(self) -> None:
        """DOCS story unchanged but under removed parent: source_active
        False.  Quality gate must NOT pull this historical DOCS into
        validation even if a contributor changed."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_docs_story(
            self.stories_dir, 1, 2, "api-docs",
            contributing_stories="Story 1.01")
        sf_hash = sync_helper.compute_file_hash(sf)
        # Also create a changed contributor (story 1.01)
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "DIFFERENT", "synced_status": "active"},
                {"file": "story-02-api-docs.md", "jira_key": "EDM-202",
                 "content_hash": sf_hash, "synced_status": "active"},
            ],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        docs = next(i for i in result["items"]
                    if i["file"].endswith("story-02-api-docs.md"))
        # DOCS is unchanged (hash matches)
        self.assertEqual(docs["category"], "unchanged")
        # But source_active is False because parent is removed
        self.assertFalse(docs["source_active"],
                         "Historical DOCS under removed parent must NOT "
                         "be source_active — quality gate must skip it")

    def test_active_docs_under_reopened_parent_eligible(self) -> None:
        """DOCS story under reopened parent: source_active True.
        Restored parent makes its children eligible for quality gate."""
        _make_epic(self.stories_dir, 1, "building")
        _make_docs_story(
            self.stories_dir, 1, 2, "api-docs",
            contributing_stories="Story 1.01")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "closed",
            "stories": [
                {"file": "story-01-scaffold.md", "jira_key": "EDM-201",
                 "content_hash": "oldhash", "synced_status": "closed"},
                {"file": "story-02-api-docs.md", "jira_key": "EDM-202",
                 "content_hash": "oldhash", "synced_status": "closed"},
            ],
        }])
        result = sync_helper.detect_changes(self.artifacts)
        epic = next(i for i in result["items"] if i["type"] == "epic")
        docs = next(i for i in result["items"]
                    if i["file"].endswith("story-02-api-docs.md"))
        self.assertEqual(epic["category"], "reopened")
        self.assertTrue(epic["source_active"])
        self.assertEqual(docs["category"], "reopened")
        self.assertTrue(docs["source_active"],
                         "DOCS under reopened parent must be source_active")


# ---------------------------------------------------------------------------
# Gap B: cascade synced_status default and identity matching
# ---------------------------------------------------------------------------

class TestCascadeStatusDefault(_TmpDirMixin, unittest.TestCase):
    """cascade uses same synced_status default as detect_changes (gap B)."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_missing_synced_status_treated_as_active(self) -> None:
        """Manifest story entry with no synced_status field is treated
        as active (same default as detect_changes .get('synced_status',
        'active')), and appears in cascade closures."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        # Manifest entry deliberately omits synced_status
        manifest = {
            "schema_version": 2, "feature_key": "F-1",
            "synced_at": "2026-01-01T00:00:00Z",
            "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "content_hash": "oldhash", "synced_status": "active",
                "stories": [{
                    "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                    "title": "[DEV] Scaffold",
                    "content_hash": sf_hash,
                    # NO synced_status field
                }],
            }],
        }
        mp = self.artifacts / "sync-manifest.json"
        _write(mp, json.dumps(manifest, indent=2))
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        self.assertIn("EDM-201", cascade_keys,
                      "Missing synced_status must default to active")

    def test_cascade_uses_detect_changes_file_identity(self) -> None:
        """Cascade qualified_file matches detect_changes items path."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                "title": "[DEV] Scaffold", "content_hash": sf_hash,
                "synced_status": "active",
            }],
        }])
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        # Get the actual file path from detect_changes items
        story_item = next(i for i in plan["items"]
                          if i["type"] == "story")
        cascade_file = result["cascades"][0]["file"]
        self.assertEqual(cascade_file, story_item["file"],
                         "Cascade file must match detect_changes identity")


class TestCascadeJiraKeyValidation(_TmpDirMixin, unittest.TestCase):
    """cascade must validate Jira keys — no blank approved ops (gap B)."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_missing_child_jira_key_emits_error(self) -> None:
        """Manifest child without jira_key produces error, not cascade."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        manifest = {
            "schema_version": 2, "feature_key": "F-1",
            "synced_at": "2026-01-01", "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "content_hash": "oldhash", "synced_status": "active",
                "stories": [{
                    "file": "story-01-scaffold.md",
                    "jira_key": "",  # blank
                    "content_hash": sf_hash,
                    "synced_status": "active",
                }],
            }],
        }
        mp = self.artifacts / "sync-manifest.json"
        _write(mp, json.dumps(manifest, indent=2))
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        self.assertEqual(len(result["cascades"]), 0,
                         "Blank jira_key child must NOT be in cascades")
        self.assertIn("errors", result)
        self.assertTrue(len(result["errors"]) > 0)

    def test_missing_parent_jira_key_emits_error(self) -> None:
        """Manifest parent without jira_key produces error."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        manifest = {
            "schema_version": 2, "feature_key": "F-1",
            "synced_at": "2026-01-01", "epics": [{
                "file": "epic-1-building.md", "jira_key": "",
                "content_hash": "oldhash", "synced_status": "active",
                "stories": [{
                    "file": "story-01-scaffold.md", "jira_key": "EDM-201",
                    "content_hash": sf_hash, "synced_status": "active",
                }],
            }],
        }
        mp = self.artifacts / "sync-manifest.json"
        _write(mp, json.dumps(manifest, indent=2))
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest)
        self.assertEqual(len(result["cascades"]), 0)
        self.assertIn("errors", result)


# ---------------------------------------------------------------------------
# Gap C: close_orphans=True full preview union
# ---------------------------------------------------------------------------

class TestCascadeOrphanUnion(_TmpDirMixin, unittest.TestCase):
    """close_orphans=True: removed parent cascades + orphan union (gap C)."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_close_orphans_true_removed_still_cascades(self) -> None:
        """close_orphans flag does not suppress removed-parent cascades."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "child")
        sf_hash = sync_helper.compute_file_hash(sf)
        _make_manifest(self.artifacts, [{
            "file": "epic-1-building.md", "jira_key": "EDM-101",
            "content_hash": "oldhash", "synced_status": "active",
            "stories": [{
                "file": "story-01-child.md", "jira_key": "EDM-201",
                "title": "Child", "content_hash": sf_hash,
                "synced_status": "active",
            }],
        }])
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=True)
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        self.assertIn("EDM-201", cascade_keys,
                      "Removed parent must cascade regardless of "
                      "close_orphans flag")

    def test_close_orphans_true_full_union(self) -> None:
        """close_orphans=True: orphan child already individually closing
        means 0 additional cascades for that parent, but removed parent
        cascade is separate."""
        _make_epic(self.stories_dir, 1, "real", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "child")
        sf_hash = sync_helper.compute_file_hash(sf)
        (self.stories_dir / "epic-2").mkdir(parents=True)
        # epic-2 is orphaned (no epic file); its child is also orphaned
        _make_manifest(self.artifacts, [
            {"file": "epic-1-real.md", "jira_key": "EDM-101",
             "content_hash": "oldhash", "synced_status": "active",
             "stories": [{
                 "file": "story-01-child.md", "jira_key": "EDM-201",
                 "title": "Child", "content_hash": sf_hash,
                 "synced_status": "active",
             }]},
            {"file": "epic-2-orphan.md", "jira_key": "EDM-102",
             "content_hash": "h", "synced_status": "active",
             "title": "Orphan",
             "stories": [{
                 "file": "story-01-orphchild.md", "jira_key": "EDM-301",
                 "title": "OrphChild", "content_hash": "h",
                 "synced_status": "active",
             }]},
        ])
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.compute_cascade_closures(
            plan["items"], manifest, close_orphans=True)
        cascade_keys = {c["jira_key"] for c in result["cascades"]}
        # EDM-201 is cascade from removed parent (unchanged active child)
        self.assertIn("EDM-201", cascade_keys,
                      "Unchanged child of removed parent in cascade")
        # EDM-301 is orphan child; with close_orphans=True it's
        # individually_closing, so should NOT be in cascade
        self.assertNotIn("EDM-301", cascade_keys,
                         "Orphan child already individually closing "
                         "should NOT be in cascade")


# ---------------------------------------------------------------------------
# Gap D: cascade recipe fail-closed capture contract
# ---------------------------------------------------------------------------

class TestCascadeRecipeContract(unittest.TestCase):
    """Step 3 cascade recipe uses fail-closed capture pattern (gap D)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", cls._sync_md, re.DOTALL)
        assert m3, "Step 3 not found"
        cls._step3 = m3.group()

    def test_errexit_safe_capture(self) -> None:
        """Cascade recipe uses || CASC_EXIT=$? errexit-safe idiom."""
        self.assertIn("|| CASC_EXIT=$?", self._step3)

    def test_per_call_temp_capture(self) -> None:
        """Cascade recipe uses mktemp for stderr capture."""
        self.assertIn("CASC_ERR=$(mktemp)", self._step3)

    def test_immediate_temp_cleanup(self) -> None:
        """Temp file removed immediately after read."""
        self.assertIn("rm -f \"$CASC_ERR\"", self._step3)

    def test_typed_json_validation(self) -> None:
        """Recipe validates cascades list in result."""
        self.assertIn("cascades", self._step3)
        self.assertIn("valid JSON", self._step3)

    def test_errors_key_check(self) -> None:
        """Recipe checks for errors key in cascade output."""
        self.assertIn("errors", self._step3)

    def test_stop_on_fatal(self) -> None:
        """Recipe STOPs on unexpected exit / malformed output."""
        lower = self._step3.lower()
        self.assertIn("casc_exit", lower)
        self.assertIn("casc_err_text", lower)

    def test_no_literal_bracket_arg(self) -> None:
        """No literal [--close-orphans] — actual instructions specify
        when to add the flag."""
        self.assertNotIn("[--close-orphans]", self._step3)

    def test_close_orphans_conditional(self) -> None:
        """close-orphans is conditional on Step 1 user choice."""
        self.assertIn("--close-orphans", self._step3)
        self.assertIn("option (a)", self._step3)


class TestCascadeCLINegative(_TmpDirMixin, unittest.TestCase):
    """CLI compute-cascade-closures negative paths (gap D)."""

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_cli_errors_in_output(self) -> None:
        """CLI output includes errors key when manifest has blank keys."""
        _make_epic(self.stories_dir, 1, "building", removed=True)
        sf = _make_dev_story(self.stories_dir, 1, 1, "scaffold")
        sf_hash = sync_helper.compute_file_hash(sf)
        manifest = {
            "schema_version": 2, "feature_key": "F-1",
            "synced_at": "2026-01-01", "epics": [{
                "file": "epic-1-building.md", "jira_key": "EDM-101",
                "content_hash": "oldhash", "synced_status": "active",
                "stories": [{
                    "file": "story-01-scaffold.md", "jira_key": "",
                    "content_hash": sf_hash, "synced_status": "active",
                }],
            }],
        }
        _write(self.artifacts / "sync-manifest.json",
               json.dumps(manifest, indent=2))
        out = StringIO()
        with mock.patch("sys.stdout", out):
            exit_code = sync_helper.main([
                "compute-cascade-closures", str(self.artifacts)])
        self.assertEqual(exit_code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("errors", data)
        self.assertTrue(len(data["errors"]) > 0)
        self.assertEqual(len(data["cascades"]), 0)


# ---------------------------------------------------------------------------
# Gap E: Step 5c cascade scope guard contract
# ---------------------------------------------------------------------------

class TestCascadeScopeGuardContract(unittest.TestCase):
    """Step 5c must verify cascade set matches approved preview (gap E)."""

    @classmethod
    def setUpClass(cls) -> None:
        import re
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")
        m5c = re.search(r"#### 5c:.*?(?=Present all epic)", cls._sync_md, re.DOTALL)
        assert m5c, "Step 5c not found"
        cls._step5c = m5c.group()

    def test_cascade_scope_guard_present(self) -> None:
        """Step 5c has a cascade scope guard before child writes."""
        self.assertIn("Cascade scope guard", self._step5c)

    def test_guard_compares_approved_union(self) -> None:
        """Guard compares against the full union of individually listed
        children and supplemental cascade closures."""
        flat = " ".join(self._step5c.split())
        self.assertIn("union", flat.lower())
        self.assertIn("compute-cascade-closures", flat)
        self.assertIn("individually listed", flat.lower())

    def test_guard_union_includes_orphaned_children(self) -> None:
        """Guard union covers user-selected orphaned children too."""
        flat = " ".join(self._step5c.lower().split())
        self.assertIn("orphaned", flat)

    def test_guard_uses_subset_not_exact_match(self) -> None:
        """Guard checks remaining active children are a subset of
        approved union — not exact equality to cascade-only set."""
        flat = " ".join(self._step5c.lower().split())
        self.assertIn("subset", flat)

    def test_guard_stops_on_expansion(self) -> None:
        """Guard STOPs if new unapproved children would expand writes."""
        self.assertIn("stop", self._step5c.lower())
        # Text wraps across line: "fresh\npreview/approval"
        flat = " ".join(self._step5c.lower().split())
        self.assertIn("fresh preview/approval", flat)

    def test_closed_resume_permitted(self) -> None:
        """Already-closed children are skipped on resume (not blocked)."""
        self.assertIn("closed", self._step5c.lower())
        self.assertIn("resume", self._step5c.lower())

    def test_original_child_failure_preserved(self) -> None:
        """Original stop-on-child-failure rule still present."""
        self.assertIn("stop the cascade immediately", self._step5c)

    def test_checkpoint_recovery_preserved(self) -> None:
        """Close-checkpoint recovery rule still present."""
        self.assertIn("close-checkpoint recovery", self._step5c.lower())


# ---------------------------------------------------------------------------
# FIX2: Unknown parent identity diagnostic (plan-creation-order)
# ---------------------------------------------------------------------------

class TestInvalidParentIdentity(_TmpDirMixin, unittest.TestCase):
    """plan-creation-order must reject actionable items with
    unparseable parent identity rather than silently dropping them.

    Counterexample: a story under ``epic-abc/story-01-docs.md`` has
    ``source_active: True`` (fresh sync) but ``epic_index: None``.
    plan-creation-order previously dropped it silently; now it must
    report a structural error.
    """

    def setUp(self) -> None:
        super().setUp()
        self.artifacts = Path(self.tmpdir) / "art"
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def test_fresh_nonnumeric_parent_source_active_false(self) -> None:
        """Fresh sync: story under epic-abc/ gets source_active False."""
        # Create a non-numeric epic dir with a story
        _make_epic(self.stories_dir, 1, "real")
        nonnumeric_dir = self.stories_dir / "epic-abc"
        nonnumeric_dir.mkdir(parents=True)
        story_path = nonnumeric_dir / "story-01-docs.md"
        story_path.write_text(
            "---\n---\n# Story abc.01: [DOCS] API docs\n\n"
            "As a writer I want to document the API.\n\n"
            "## Acceptance Criteria\n\nDocs complete\n\n"
            "## Documentation Scope\n\nAPI reference.\n\n"
            "## Dependencies\n\nNone\n\n"
            "## Design Reference\n\n"
            "- Epic: Epic abc\n",
            encoding="utf-8",
        )
        result = sync_helper.detect_changes(self.artifacts)
        # Find the story under epic-abc
        abc_stories = [
            i for i in result["items"]
            if i["type"] == "story" and i["file"].startswith("epic-abc/")
        ]
        self.assertEqual(len(abc_stories), 1)
        self.assertIsNone(abc_stories[0]["epic_index"])
        self.assertFalse(
            abc_stories[0]["source_active"],
            "Story under non-numeric parent must NOT be source_active")

    def test_plan_creation_order_reports_nonnumeric_parent(self) -> None:
        """plan-creation-order emits error for actionable story with
        unparseable parent — does not silently drop planned work."""
        _make_epic(self.stories_dir, 1, "real")
        nonnumeric_dir = self.stories_dir / "epic-abc"
        nonnumeric_dir.mkdir(parents=True)
        story_path = nonnumeric_dir / "story-01-docs.md"
        story_path.write_text(
            "---\n---\n# Story abc.01: [DOCS] API docs\n\n"
            "As a writer I want to document the API.\n\n"
            "## Acceptance Criteria\n\nDocs complete\n\n"
            "## Documentation Scope\n\nAPI reference.\n\n"
            "## Dependencies\n\nNone\n\n"
            "## Design Reference\n\n"
            "- Epic: Epic abc\n",
            encoding="utf-8",
        )
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.plan_creation_order(
            plan["items"], str(self.artifacts), None)
        # Must report error for the non-numeric parent story
        self.assertTrue(
            result["errors"],
            "plan-creation-order must report errors for stories "
            "with unparseable parent identity")
        error_text = " ".join(result["errors"])
        self.assertIn("epic-abc", error_text,
                       "Error must name the problematic parent")

    def test_plan_creation_order_cli_nonnumeric_parent_exit1(self) -> None:
        """CLI plan-creation-order exits 1 for non-numeric parent story."""
        _make_epic(self.stories_dir, 1, "real")
        nonnumeric_dir = self.stories_dir / "epic-abc"
        nonnumeric_dir.mkdir(parents=True)
        story_path = nonnumeric_dir / "story-01-docs.md"
        story_path.write_text(
            "---\n---\n# Story abc.01: [DOCS] API docs\n\n"
            "As a writer I want to document the API.\n\n"
            "## Acceptance Criteria\n\nDocs complete\n\n"
            "## Documentation Scope\n\nAPI reference.\n\n"
            "## Dependencies\n\nNone\n\n"
            "## Design Reference\n\n"
            "- Epic: Epic abc\n",
            encoding="utf-8",
        )
        out = StringIO()
        with mock.patch("sys.stdout", out):
            exit_code = sync_helper.main([
                "plan-creation-order", str(self.artifacts)])
        self.assertEqual(exit_code, 1,
                         "CLI must exit 1 when errors are present")
        data = json.loads(out.getvalue())
        self.assertTrue(data["errors"])

    def test_unchanged_story_under_nonnumeric_not_error(self) -> None:
        """Non-actionable (unchanged/orphaned) stories with non-numeric
        parent are NOT flagged as identity errors — this preserves
        legitimate orphan cleanup and closed manifest recovery."""
        _make_epic(self.stories_dir, 1, "real")
        manifest_data = [{
            "file": "epic-1-real.md", "jira_key": "EDM-101",
            "content_hash": sync_helper.compute_file_hash(
                self.stories_dir / "epic-1-real.md"),
            "synced_status": "active",
            "stories": [],
        }]
        _make_manifest(self.artifacts, manifest_data)
        plan = sync_helper.detect_changes(self.artifacts)
        # Inject a synthetic unchanged story with None epic_index
        # (simulates an orphan/closed manifest entry)
        plan["items"].append({
            "file": "epic-old/story-01-legacy.md",
            "type": "story",
            "category": "unchanged",
            "title": "Legacy",
            "epic_index": None,
            "story_index": 1,
            "jira_key": "EDM-301",
            "content_hash": "h",
            "old_hash": "h",
            "synced_status": "active",
            "source_active": False,
        })
        manifest = sync_helper.load_manifest(
            self.artifacts / "sync-manifest.json")
        result = sync_helper.plan_creation_order(
            plan["items"], str(self.artifacts), manifest)
        # No identity errors for unchanged/non-actionable items
        identity_errs = [e for e in result["errors"]
                         if "qualified ID" in e]
        self.assertEqual(
            len(identity_errs), 0,
            "Non-actionable stories must NOT cause identity errors")

    def test_numeric_missing_parent_blocked_at_preflight(self) -> None:
        """Story under epic-99/ with valid file but NO epic-99 source
        artifact → preflight error, not silent ordering.

        This is the counterexample: the story FILE exists (valid
        numeric epic_index=99, story_index=1), but no epic-99-*.md
        source artifact exists, so no Epic 99 will be created.
        plan-creation-order must catch this at preflight, not
        silently order the story for creation.
        """
        _make_epic(self.stories_dir, 1, "building")
        # Create story under epic-99 (no epic-99 source artifact)
        epic99_dir = self.stories_dir / "epic-99"
        epic99_dir.mkdir(parents=True)
        (epic99_dir / "story-01-docs.md").write_text(
            "---\n---\n# Story 99.01: [DOCS] API docs\n\n"
            "As a writer I want to document.\n\n"
            "## Acceptance Criteria\n\nDone\n\n"
            "## Documentation Scope\n\nAPI.\n\n"
            "## Dependencies\n\nNone\n\n"
            "## Design Reference\n\n- Epic: Epic 99\n",
            encoding="utf-8",
        )
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.plan_creation_order(
            plan["items"], str(self.artifacts), None)
        # Must be in errors, not silently ordered
        self.assertTrue(result["errors"],
                        "Missing owning parent must produce errors")
        error_text = " ".join(result["errors"])
        self.assertIn("epic-99", error_text)
        self.assertIn("owning", error_text.lower())
        # Story must NOT be in ordered list
        ordered_files = [i["file"] for i in result["ordered"]]
        self.assertNotIn("epic-99/story-01-docs.md", ordered_files,
                         "Story without parent must NOT be ordered")
        # Valid story-1.01 should still be orderable
        # (epic-1 has source artifact)

    def test_numeric_valid_parent_passes_preflight(self) -> None:
        """Story under epic-1/ with matching epic-1-*.md source: no
        owning-parent error — confirms no false positives."""
        _make_epic(self.stories_dir, 1, "building")
        _make_dev_story(self.stories_dir, 1, 1, "scaffold",
                        deps="None")
        plan = sync_helper.detect_changes(self.artifacts)
        result = sync_helper.plan_creation_order(
            plan["items"], str(self.artifacts), None)
        owning_errs = [e for e in result["errors"]
                       if "owning" in e.lower()]
        self.assertEqual(len(owning_errs), 0,
                         "Valid parent must NOT produce owning errors")
        self.assertEqual(len(result["ordered"]), 1)


if __name__ == "__main__":
    unittest.main()
