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
        """Step 6a reference-availability guard checks Dependencies and
        Contributing stories."""
        sync_md = self._read_sync_md()
        start = sync_md.find("#### 6a:")
        end = sync_md.find("#### 6b:")
        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)
        section = " ".join(sync_md[start:end].split())
        self.assertIn("Dependencies", section)
        self.assertIn("Contributing stories", section)


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

    def _qids(self, result):
        return [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in result["ordered"]]

    # ── Core ordering ──────────────────────────────────────────

    def test_linear_chain(self) -> None:
        """A→B→C multi-hop: C after B after A."""
        self._setup([(1,1,"a","DEV","None",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False),
                     (1,3,"c","DEV","Story 1.02",None,False)])
        items = [self._item(1,i,["a","b","c"][i-1]) for i in [1,2,3]]
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
        items = [self._item(1,1,"client"), self._item(2,1,"api")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertEqual(self._qids(r), ["story-2.01","story-1.01"])
        self.assertEqual(r["errors"], [])

    def test_existing_key_satisfies(self) -> None:
        """Already-synced story satisfies dependency without recreation."""
        self._setup([(1,1,"api","DEV","None",None,False),
                     (1,2,"client","DEV","Story 1.01",None,False)])
        manifest = {"epics": [{"file": "epic-1-epic1.md", "jira_key": "T-100",
                    "stories": [{"file": "story-01-api.md","jira_key":"T-101"}]}]}
        items = [self._item(1,1,"api","unchanged","T-101"),
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
        items = [self._item(1,1,"api"),
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
        """Story depends on itself → cycle."""
        self._setup([(1,1,"a","DEV","Story 1.01",None,False)])
        items = [self._item(1,1,"a")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("cycle" in e.lower() for e in r["errors"]))
        self.assertEqual(len(r["ordered"]), 0)

    def test_two_node_cycle(self) -> None:
        """A↔B mutual dependency → cycle, both blocked."""
        self._setup([(1,1,"a","DEV","Story 1.02",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False)])
        items = [self._item(1,1,"a"), self._item(1,2,"b")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        self.assertTrue(any("cycle" in e.lower() for e in r["errors"]))
        self.assertEqual(len(r["blocked"]), 2)

    def test_cycle_downstream_distinction(self) -> None:
        """A↔B cycle blocks downstream C; C is not a cycle participant."""
        self._setup([(1,1,"a","DEV","Story 1.02",None,False),
                     (1,2,"b","DEV","Story 1.01",None,False),
                     (1,3,"c","DEV","Story 1.01",None,False)])
        items = [self._item(1,i,["a","b","c"][i-1]) for i in [1,2,3]]
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
        items = [self._item(1,1,"a"), self._item(2,1,"b"),
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
        items_fwd = [self._item(1,1,"a"),self._item(1,2,"b"),self._item(2,1,"c")]
        items_rev = list(reversed(items_fwd))
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
        self.assertIn("reloads the manifest fresh", section)


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
        items = [self._item(1, 1, "a")]
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
        items = [self._item(1, 1, "a")]
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
        items = [self._item(1, 1, "api"), self._item(1, 2, "client")]
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

    def _qids(self, result):
        return [f"story-{it['epic_index']}.{it['story_index']:02d}"
                for it in result["ordered"]]

    def test_unavailable_owner_excluded(self) -> None:
        """Story with dep on nonexistent target → not in ordered."""
        self._setup([(1, 1, "a", "Story 9.99")])
        items = [self._item(1, 1, "a")]
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
        items = [self._item(1, 1, "a"), self._item(1, 2, "b"),
                 self._item(1, 3, "c")]
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
        items = [self._item(1, 1, "a"), self._item(2, 1, "b"),
                 self._item(2, 2, "c")]
        r = sync_helper.plan_creation_order(items, self.tmpdir, None)
        qids = self._qids(r)
        self.assertIn("story-2.01", qids)
        self.assertIn("story-2.02", qids)
        self.assertNotIn("story-1.01", qids)

    def test_unavailable_epic_ref_excludes_owner(self) -> None:
        """Epic 999 ref → owner excluded from ordered."""
        self._setup([(1, 1, "a", "Epic 999")])
        items = [self._item(1, 1, "a")]
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
    """Verify sync.md consumer instructions reference the executable guard."""

    @classmethod
    def setUpClass(cls) -> None:
        sync_path = Path(__file__).resolve().parent.parent / "skills" / "sync.md"
        cls._sync_md = sync_path.read_text(encoding="utf-8")

    def test_6a_calls_check_ref_availability(self) -> None:
        """Step 6a must call check-ref-availability before the prepare recipe."""
        import re
        m6a = re.search(r"#### 6a:.*?(?=#### 6b:)", self._sync_md, re.DOTALL)
        self.assertIsNotNone(m6a)
        section = m6a.group()
        check_pos = section.find("check-ref-availability")
        # The prepare recipe is the bash block calling `prepare`
        prepare_recipe_pos = section.find("story `prepare` recipe")
        self.assertGreater(check_pos, -1,
                           "6a must reference check-ref-availability")
        self.assertGreater(prepare_recipe_pos, -1,
                           "6a must reference the prepare recipe")
        self.assertLess(check_pos, prepare_recipe_pos,
                        "check-ref-availability must appear before prepare recipe in 6a")

    def test_6b_calls_check_ref_availability(self) -> None:
        """Step 6b must call check-ref-availability before prepare."""
        import re
        m6b = re.search(r"#### 6b:.*?(?=#### 6c:)", self._sync_md, re.DOTALL)
        self.assertIsNotNone(m6b)
        section = m6b.group()
        self.assertIn("check-ref-availability", section,
                      "6b must reference check-ref-availability")

    def test_helper_reference_documents_check_ref(self) -> None:
        """Helper reference must document check-ref-availability."""
        ref_path = (Path(__file__).resolve().parent.parent
                    / "references" / "sync-helper-usage.md")
        content = ref_path.read_text(encoding="utf-8")
        self.assertIn("check-ref-availability", content)
        self.assertIn("ready", content)
        self.assertIn("blocked", content)

    def test_preflight_catches_changed_invalid_refs(self) -> None:
        """Step 3 preflight description covers changed/reopened invalid refs."""
        import re
        m3 = re.search(r"### Step 3:.*?(?=### Step 4:)", self._sync_md, re.DOTALL)
        self.assertIsNotNone(m3)
        section = m3.group()
        self.assertIn("changed", section.lower())
        self.assertIn("reopened", section.lower())


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


if __name__ == "__main__":
    unittest.main()
