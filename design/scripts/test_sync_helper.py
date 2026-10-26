#!/usr/bin/env python3
"""Tests for design/scripts/sync_helper.py."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_epic_file(
    stories_dir: Path,
    index: int,
    slug: str,
    *,
    title: str = "",
    removed: bool = False,
    body: str = "",
) -> Path:
    """Create an epic artifact file and return its path."""
    fm_lines = ["---"]
    if removed:
        fm_lines.append("status: removed")
    fm_lines.append("---")
    if not title:
        title = f"Epic {index} {slug}"
    content = "\n".join(fm_lines) + f"\n# {title}\n\n## Summary\n\nSummary text.\n\n## Acceptance Criteria\n\n- AC1\n"
    if body:
        content += f"\n{body}\n"
    fp = stories_dir / f"epic-{index}-{slug}.md"
    _write(fp, content)
    return fp


def _make_story_file(
    stories_dir: Path,
    epic_index: int,
    story_index: int,
    slug: str,
    *,
    prefix: str = "DEV",
    title: str = "",
    removed: bool = False,
    deps: str = "",
) -> Path:
    """Create a story artifact file and return its path."""
    epic_dir = stories_dir / f"epic-{epic_index}"
    fm_lines = ["---"]
    if removed:
        fm_lines.append("status: removed")
    fm_lines.append("---")
    if not title:
        title = f"[{prefix}] Story {epic_index}.{story_index:02d} {slug}"
    content = "\n".join(fm_lines) + f"\n# {title}\n\n## User Story\n\n**As a** dev,\n**I want to** do things,\n**So that** stuff works.\n\n## Acceptance Criteria\n\n- AC1\n\n## Implementation Guidance\n\nDo the thing.\n\n## Testing Approach\n\nTest the thing.\n"
    if deps:
        content += f"\n## Dependencies\n\n{deps}\n"
    fp = epic_dir / f"story-{story_index:02d}-{slug}.md"
    _write(fp, content)
    return fp


def _make_manifest(
    artifacts_dir: Path,
    epics: list[dict],
    *,
    schema_version: int = 2,
    feature_key: str = "TEST-100",
    synced_at: str = "2026-01-15T10:00:00Z",
) -> Path:
    """Write a sync-manifest.json and return its path."""
    manifest = {
        "schema_version": schema_version,
        "feature_key": feature_key,
        "synced_at": synced_at,
        "epics": epics,
    }
    fp = artifacts_dir / "sync-manifest.json"
    _write(fp, json.dumps(manifest, indent=2))
    return fp


# ---------------------------------------------------------------------------
# Test: compute_file_hash
# ---------------------------------------------------------------------------

class TestComputeHash(unittest.TestCase):
    def test_known_hash(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("hello world\n")
            f.flush()
            path = f.name
        try:
            expected = hashlib.sha256(b"hello world\n").hexdigest()
            self.assertEqual(sync_helper.compute_file_hash(path), expected)
        finally:
            os.unlink(path)

    def test_missing_file(self) -> None:
        with self.assertRaises(OSError):
            sync_helper.compute_file_hash("/nonexistent/file.md")

    def test_cli_compute_hash(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("test content")
            f.flush()
            path = f.name
        try:
            out = StringIO()
            with mock.patch("sys.stdout", out):
                sync_helper.main(["compute-hash", path])
            expected = hashlib.sha256(b"test content").hexdigest()
            self.assertEqual(out.getvalue().strip(), expected)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Test: read_frontmatter / has_removed_status
# ---------------------------------------------------------------------------

class TestFrontmatter(unittest.TestCase):
    def test_removed_status(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nstatus: removed\n---\n# Title\n")
            f.flush()
            path = f.name
        try:
            self.assertTrue(sync_helper.has_removed_status(path))
        finally:
            os.unlink(path)

    def test_no_frontmatter(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\nNo frontmatter here.\n")
            f.flush()
            path = f.name
        try:
            self.assertFalse(sync_helper.has_removed_status(path))
        finally:
            os.unlink(path)

    def test_active_status(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nstatus: active\n---\n# Title\n")
            f.flush()
            path = f.name
        try:
            self.assertFalse(sync_helper.has_removed_status(path))
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Test: resolve_refs
# ---------------------------------------------------------------------------

class TestResolveRefs(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = {
            "epics": [
                {
                    "file": "epic-1-building.md",
                    "jira_key": "EDM-101",
                    "stories": [
                        {"file": "story-01-scaffold.md", "jira_key": "EDM-201"},
                        {"file": "story-02-pipeline.md", "jira_key": "EDM-202"},
                    ],
                },
                {
                    "file": "epic-2-deploy.md",
                    "jira_key": "EDM-102",
                    "stories": [
                        {"file": "story-01-infra.md", "jira_key": "EDM-301"},
                    ],
                },
            ],
        }

    def test_single_story_ref(self) -> None:
        text = "Depends on Story 1.01 for scaffolding."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertEqual(result, "Depends on Story EDM-201 for scaffolding.")

    def test_multiple_story_refs(self) -> None:
        text = "Depends on Stories 1.01, 2.01 for setup."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertEqual(result, "Depends on Stories EDM-201, EDM-301 for setup.")

    def test_epic_ref(self) -> None:
        text = "See Epic 1 for context."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertEqual(result, "See Epic EDM-101 for context.")

    def test_multiple_epic_refs(self) -> None:
        text = "Relates to Epics 1, 2."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertEqual(result, "Relates to Epics EDM-101, EDM-102.")

    def test_unresolved_story(self) -> None:
        text = "Depends on Story 3.01 which doesn't exist."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertIn("3.01 [unresolved]", result)

    def test_unresolved_epic(self) -> None:
        text = "See Epic 5 for details."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertIn("5 [unresolved]", result)

    def test_mixed_resolved_unresolved(self) -> None:
        text = "Depends on Stories 1.01, 3.01 for things."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertIn("EDM-201", result)
        self.assertIn("3.01 [unresolved]", result)

    def test_no_refs(self) -> None:
        text = "No references here at all."
        result = sync_helper.resolve_refs(text, self.manifest)
        self.assertEqual(result, text)

    def test_cli_resolve_refs(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(self.manifest, f)
            f.flush()
            mpath = f.name
        try:
            out = StringIO()
            with mock.patch("sys.stdout", out):
                sync_helper.main(["resolve-refs", mpath, "Epic 1 and Story 1.02"])
            self.assertIn("EDM-101", out.getvalue())
            self.assertIn("EDM-202", out.getvalue())
        finally:
            os.unlink(mpath)


# ---------------------------------------------------------------------------
# Test: detect_changes — fresh sync (no manifest)
# ---------------------------------------------------------------------------

class TestDetectChangesFresh(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.artifacts = Path(self.tmpdir)
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_fresh_sync_all_new(self) -> None:
        _make_epic_file(self.stories_dir, 1, "building")
        _make_story_file(self.stories_dir, 1, 1, "scaffold")
        _make_story_file(self.stories_dir, 1, 2, "pipeline")

        result = sync_helper.detect_changes(self.artifacts)
        self.assertFalse(result["manifest_exists"])
        self.assertEqual(result["summary"]["new"], 3)
        self.assertEqual(result["summary"]["unchanged"], 0)
        for item in result["items"]:
            self.assertEqual(item["category"], "new")

    def test_fresh_sync_removed_skipped(self) -> None:
        _make_epic_file(self.stories_dir, 1, "building")
        _make_epic_file(self.stories_dir, 2, "removed", removed=True)
        _make_story_file(self.stories_dir, 1, 1, "scaffold")
        _make_story_file(self.stories_dir, 1, 2, "removed", removed=True)

        result = sync_helper.detect_changes(self.artifacts)
        # Only active items appear
        self.assertEqual(result["summary"]["new"], 2)
        files = [i["file"] for i in result["items"]]
        self.assertNotIn("epic-2-removed.md", files)

    def test_empty_artifacts(self) -> None:
        result = sync_helper.detect_changes(self.artifacts)
        self.assertFalse(result["manifest_exists"])
        self.assertEqual(result["summary"]["new"], 0)
        self.assertEqual(len(result["items"]), 0)


# ---------------------------------------------------------------------------
# Test: detect_changes — existing manifest
# ---------------------------------------------------------------------------

class TestDetectChangesExisting(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.artifacts = Path(self.tmpdir)
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_unchanged_items(self) -> None:
        ef = _make_epic_file(self.stories_dir, 1, "building")
        sf = _make_story_file(self.stories_dir, 1, 1, "scaffold")

        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Epic 1 building",
                "size": "M",
                "content_hash": sync_helper.compute_file_hash(ef),
                "synced_status": "active",
                "stories": [
                    {
                        "file": "story-01-scaffold.md",
                        "jira_key": "EDM-201",
                        "title": "[DEV] Story 1.01 scaffold",
                        "content_hash": sync_helper.compute_file_hash(sf),
                        "synced_status": "active",
                    },
                ],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        self.assertTrue(result["manifest_exists"])
        self.assertEqual(result["summary"]["unchanged"], 2)
        self.assertEqual(result["summary"]["new"], 0)
        self.assertEqual(result["summary"]["changed"], 0)

    def test_changed_items(self) -> None:
        ef = _make_epic_file(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Epic 1 building",
                "size": "M",
                "content_hash": "old_hash_value",
                "synced_status": "active",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        changed = [i for i in result["items"] if i["category"] == "changed"]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["jira_key"], "EDM-101")
        self.assertEqual(changed[0]["old_hash"], "old_hash_value")

    def test_removed_items(self) -> None:
        ef = _make_epic_file(self.stories_dir, 1, "building", removed=True)
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Epic 1 building",
                "content_hash": "old_hash",
                "synced_status": "active",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        removed = [i for i in result["items"] if i["category"] == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["jira_key"], "EDM-101")

    def test_reopened_items(self) -> None:
        """File has no removed status but manifest says closed → reopened."""
        ef = _make_epic_file(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Epic 1 building",
                "content_hash": "old_hash",
                "synced_status": "closed",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        reopened = [i for i in result["items"] if i["category"] == "reopened"]
        self.assertEqual(len(reopened), 1)

    def test_already_closed(self) -> None:
        """File has removed status and manifest says closed → unchanged."""
        ef = _make_epic_file(self.stories_dir, 1, "building", removed=True)
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "content_hash": "old_hash",
                "synced_status": "closed",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        unchanged = [i for i in result["items"] if i["category"] == "unchanged"]
        self.assertEqual(len(unchanged), 1)

    def test_orphaned_entries(self) -> None:
        """Manifest has an active entry with no file on disk."""
        _make_epic_file(self.stories_dir, 1, "building")
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Epic 1 building",
                "content_hash": sync_helper.compute_file_hash(
                    self.stories_dir / "epic-1-building.md"
                ),
                "synced_status": "active",
                "stories": [],
            },
            {
                "file": "epic-2-deleted.md",
                "jira_key": "EDM-102",
                "title": "Epic 2 deleted",
                "content_hash": "some_hash",
                "synced_status": "active",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        orphaned = [i for i in result["items"] if i["category"] == "orphaned"]
        self.assertEqual(len(orphaned), 1)
        self.assertEqual(orphaned[0]["jira_key"], "EDM-102")

    def test_orphaned_closed_ignored(self) -> None:
        """Closed entries whose files were deleted are silently ignored."""
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-gone.md",
                "jira_key": "EDM-101",
                "title": "Gone",
                "content_hash": "h",
                "synced_status": "closed",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        orphaned = [i for i in result["items"] if i["category"] == "orphaned"]
        self.assertEqual(len(orphaned), 0)

    def test_new_items_with_manifest(self) -> None:
        """New file with no manifest entry → new."""
        _make_epic_file(self.stories_dir, 1, "existing")
        _make_epic_file(self.stories_dir, 2, "brand-new")
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-existing.md",
                "jira_key": "EDM-101",
                "title": "Existing",
                "content_hash": sync_helper.compute_file_hash(
                    self.stories_dir / "epic-1-existing.md"
                ),
                "synced_status": "active",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        new_items = [i for i in result["items"] if i["category"] == "new"]
        self.assertEqual(len(new_items), 1)
        self.assertEqual(new_items[0]["file"], "epic-2-brand-new.md")

    def test_removed_story_under_active_epic_warning(self) -> None:
        """Removed story still referenced in active epic → warning."""
        _make_epic_file(
            self.stories_dir, 1, "building",
            body="## Stories\n\n- Story 1.01: scaffold\n- Story 1.02: pipeline\n",
        )
        _make_story_file(self.stories_dir, 1, 1, "scaffold")
        sf2 = _make_story_file(self.stories_dir, 1, 2, "pipeline", removed=True)

        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Building",
                "content_hash": sync_helper.compute_file_hash(
                    self.stories_dir / "epic-1-building.md"
                ),
                "synced_status": "active",
                "stories": [
                    {
                        "file": "story-01-scaffold.md",
                        "jira_key": "EDM-201",
                        "content_hash": sync_helper.compute_file_hash(
                            self.stories_dir / "epic-1" / "story-01-scaffold.md"
                        ),
                        "synced_status": "active",
                    },
                    {
                        "file": "story-02-pipeline.md",
                        "jira_key": "EDM-202",
                        "content_hash": "old_hash",
                        "synced_status": "active",
                    },
                ],
            },
        ])

        result = sync_helper.detect_changes(self.artifacts)
        self.assertTrue(len(result["warnings"]) > 0)
        self.assertIn("Story 1.02", result["warnings"][0])
        self.assertIn("still listed", result["warnings"][0])


# ---------------------------------------------------------------------------
# Test: detect_changes — v1 manifest migration
# ---------------------------------------------------------------------------

class TestDetectChangesV1Migration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.artifacts = Path(self.tmpdir)
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_v1_all_changed(self) -> None:
        """V1 manifest: all items treated as changed (no hash stored)."""
        _make_epic_file(self.stories_dir, 1, "building")
        _make_story_file(self.stories_dir, 1, 1, "scaffold")
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Building",
                "stories": [
                    {
                        "file": "story-01-scaffold.md",
                        "jira_key": "EDM-201",
                        "title": "[DEV] Scaffold",
                    },
                ],
            },
        ], schema_version=1)

        result = sync_helper.detect_changes(self.artifacts)
        self.assertTrue(result["v1_migration"])
        self.assertEqual(result["schema_version"], 1)
        # All existing items should be "changed" because no hash stored
        changed = [i for i in result["items"] if i["category"] == "changed"]
        self.assertEqual(len(changed), 2)

    def test_v1_orphaned_detected(self) -> None:
        """V1 manifest with missing file → orphaned (active assumed)."""
        _make_manifest(self.artifacts, [
            {
                "file": "epic-1-gone.md",
                "jira_key": "EDM-101",
                "title": "Gone",
                "stories": [],
            },
        ], schema_version=1)

        result = sync_helper.detect_changes(self.artifacts)
        orphaned = [i for i in result["items"] if i["category"] == "orphaned"]
        self.assertEqual(len(orphaned), 1)


# ---------------------------------------------------------------------------
# Test: detect_changes — CLI invocation
# ---------------------------------------------------------------------------

class TestDetectChangesCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.artifacts = Path(self.tmpdir)
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_cli_detect_changes(self) -> None:
        _make_epic_file(self.stories_dir, 1, "building")
        out = StringIO()
        with mock.patch("sys.stdout", out):
            rc = sync_helper.main(["detect-changes", str(self.artifacts)])
        self.assertEqual(rc, 0)
        result = json.loads(out.getvalue())
        self.assertIn("summary", result)
        self.assertIn("items", result)


# ---------------------------------------------------------------------------
# Test: update_manifest
# ---------------------------------------------------------------------------

class TestUpdateManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_create_epic_fresh(self) -> None:
        """Create an epic in a fresh (no existing) manifest."""
        result = sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "abc123",
            item_type="epic", title="Building", size="M",
        )
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(len(result["epics"]), 1)
        self.assertEqual(result["epics"][0]["jira_key"], "EDM-101")
        self.assertEqual(result["epics"][0]["synced_status"], "active")
        self.assertIn("synced_at", result)

    def test_create_story(self) -> None:
        """Create an epic then a story under it."""
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "abc",
            item_type="epic", title="Building",
        )
        result = sync_helper.update_manifest(
            self.manifest_path, "create",
            "story-01-scaffold.md", "EDM-201", "def",
            item_type="story", title="[DEV] Scaffold",
        )
        self.assertEqual(len(result["epics"][0]["stories"]), 1)
        self.assertEqual(result["epics"][0]["stories"][0]["jira_key"], "EDM-201")

    def test_update_changes_hash(self) -> None:
        """Update records new hash and keeps active status."""
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "abc",
            item_type="epic", title="Building",
        )
        result = sync_helper.update_manifest(
            self.manifest_path, "update",
            "epic-1-building.md", "EDM-101", "new_hash",
            item_type="epic",
        )
        self.assertEqual(result["epics"][0]["content_hash"], "new_hash")
        self.assertEqual(result["epics"][0]["synced_status"], "active")

    def test_close_sets_closed(self) -> None:
        """Close operation sets synced_status to closed."""
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "abc",
            item_type="epic", title="Building",
        )
        result = sync_helper.update_manifest(
            self.manifest_path, "close",
            "epic-1-building.md", "EDM-101", "close_hash",
            item_type="epic",
        )
        self.assertEqual(result["epics"][0]["synced_status"], "closed")
        self.assertEqual(result["epics"][0]["content_hash"], "close_hash")

    def test_create_story_with_epic_file(self) -> None:
        """Create a story under a specific epic using --epic-file."""
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "abc",
            item_type="epic", title="Building",
        )
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-2-deploy.md", "EDM-102", "def",
            item_type="epic", title="Deploy",
        )

        # Use _update_manifest_story_with_epic to place under epic-1
        manifest = sync_helper.load_manifest(self.manifest_path)
        sync_helper._update_manifest_story_with_epic(
            manifest,
            "story-01-scaffold.md", "EDM-201", "hash1",
            "active", "[DEV] Scaffold", "epic-1-building.md",
        )
        sync_helper.save_manifest(manifest, self.manifest_path)

        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(len(manifest["epics"][0]["stories"]), 1)
        self.assertEqual(len(manifest["epics"][1]["stories"]), 0)

    def test_cli_update_manifest(self) -> None:
        rc = sync_helper.main([
            "update-manifest", str(self.manifest_path),
            "--operation", "create",
            "--file", "epic-1-building.md",
            "--jira-key", "EDM-101",
            "--content-hash", "abc123",
            "--item-type", "epic",
            "--title", "Building",
            "--size", "M",
        ])
        self.assertEqual(rc, 0)
        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(manifest["epics"][0]["jira_key"], "EDM-101")


# ---------------------------------------------------------------------------
# Test: update_manifest — failed/unattempted not recorded
# ---------------------------------------------------------------------------

class TestManifestFailSafety(unittest.TestCase):
    """Verify that the manifest records only successful operations."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_partial_sync_leaves_unsynced_items(self) -> None:
        """If we create epic1 but not epic2, only epic1 is in the manifest."""
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "hash1",
            item_type="epic", title="Building",
        )
        # Simulate: epic2 creation "failed" — update_manifest NOT called
        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(len(manifest["epics"]), 1)
        self.assertEqual(manifest["epics"][0]["file"], "epic-1-building.md")

    def test_resume_after_partial_sync(self) -> None:
        """Re-running detect-changes after partial sync finds unsynced items."""
        artifacts = Path(self.tmpdir) / "art"
        stories_dir = artifacts / "06-stories"
        stories_dir.mkdir(parents=True)

        _make_epic_file(stories_dir, 1, "building")
        _make_epic_file(stories_dir, 2, "deploy")

        # Simulate: only epic1 was synced
        _make_manifest(artifacts, [
            {
                "file": "epic-1-building.md",
                "jira_key": "EDM-101",
                "title": "Building",
                "content_hash": sync_helper.compute_file_hash(
                    stories_dir / "epic-1-building.md"
                ),
                "synced_status": "active",
                "stories": [],
            },
        ])

        result = sync_helper.detect_changes(artifacts)
        new_items = [i for i in result["items"] if i["category"] == "new"]
        unchanged = [i for i in result["items"] if i["category"] == "unchanged"]
        self.assertEqual(len(new_items), 1)
        self.assertEqual(new_items[0]["file"], "epic-2-deploy.md")
        self.assertEqual(len(unchanged), 1)

    def test_hash_records_submitted_content(self) -> None:
        """The manifest records the hash passed to update_manifest,
        not a recomputed hash of the current file."""
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", "submitted_hash_at_time_of_call",
            item_type="epic", title="Building",
        )
        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(
            manifest["epics"][0]["content_hash"],
            "submitted_hash_at_time_of_call",
        )


# ---------------------------------------------------------------------------
# Test: migrate_manifest
# ---------------------------------------------------------------------------

class TestMigrateManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmpdir) / "sync-manifest.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_migrate_v1_to_v2(self) -> None:
        _write(self.manifest_path, json.dumps({
            "schema_version": 1,
            "feature_key": "TEST-100",
            "synced_at": "2026-01-01",
            "epics": [
                {
                    "file": "epic-1-building.md",
                    "jira_key": "EDM-101",
                    "title": "Building",
                    "stories": [
                        {
                            "file": "story-01-scaffold.md",
                            "jira_key": "EDM-201",
                            "title": "[DEV] Scaffold",
                        },
                    ],
                },
            ],
        }))

        result = sync_helper.migrate_manifest(self.manifest_path)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["epics"][0]["synced_status"], "active")
        self.assertIsNone(result["epics"][0]["content_hash"])
        self.assertEqual(result["epics"][0]["stories"][0]["synced_status"], "active")
        self.assertIsNone(result["epics"][0]["stories"][0]["content_hash"])

    def test_migrate_v2_noop(self) -> None:
        _write(self.manifest_path, json.dumps({
            "schema_version": 2,
            "feature_key": "TEST-100",
            "synced_at": "2026-01-01",
            "epics": [],
        }))
        result = sync_helper.migrate_manifest(self.manifest_path)
        self.assertEqual(result["schema_version"], 2)

    def test_cli_migrate(self) -> None:
        _write(self.manifest_path, json.dumps({
            "schema_version": 1,
            "feature_key": "TEST-100",
            "synced_at": "2026-01-01",
            "epics": [{"file": "epic-1-x.md", "jira_key": "K-1", "stories": []}],
        }))
        rc = sync_helper.main(["migrate-manifest", str(self.manifest_path)])
        self.assertEqual(rc, 0)
        manifest = sync_helper.load_manifest(self.manifest_path)
        self.assertEqual(manifest["schema_version"], 2)


# ---------------------------------------------------------------------------
# Test: render_description
# ---------------------------------------------------------------------------

class TestRenderDescription(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manifest = {
            "epics": [
                {
                    "file": "epic-1-building.md",
                    "jira_key": "EDM-101",
                    "stories": [
                        {"file": "story-01-scaffold.md", "jira_key": "EDM-201"},
                    ],
                },
            ],
        }

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_epic_description(self) -> None:
        ef = Path(self.tmpdir) / "epic-1-building.md"
        _write(ef, "---\n---\n# Building\n\n## Summary\n\nBuild things.\n\n## Acceptance Criteria\n\n- AC1\n")

        desc = sync_helper.render_epic_description(
            ef, self.manifest,
            design_doc_link="https://docs.example.com/design",
            feature_key="FEAT-1",
        )
        self.assertIn("## Summary", desc)
        self.assertIn("Build things.", desc)
        self.assertIn("## Acceptance Criteria", desc)
        self.assertIn("## Design Reference", desc)
        self.assertIn("FEAT-1", desc)

    def test_story_description_dev(self) -> None:
        sf = Path(self.tmpdir) / "story-01-scaffold.md"
        _write(sf, textwrap.dedent("""\
            ---
            ---
            # [DEV] Scaffold

            ## User Story

            **As a** dev,
            **I want to** scaffold,
            **So that** things work.

            ## Acceptance Criteria

            - AC1

            ## Implementation Guidance

            Do stuff.

            ## Testing Approach

            Test stuff.

            ## Dependencies

            Story 1.01

            ## Design Reference

            Design document: https://example.com
            Epic: EDM-101
        """))

        desc = sync_helper.render_story_description(
            sf, self.manifest,
            design_doc_link="https://example.com",
            epic_jira_key="EDM-101",
        )
        self.assertIn("## User Story", desc)
        self.assertIn("## Implementation Guidance", desc)
        self.assertIn("## Testing Approach", desc)
        # Story 1.01 should be resolved
        self.assertIn("EDM-201", desc)

    def test_story_description_docs(self) -> None:
        sf = Path(self.tmpdir) / "story-01-docs.md"
        _write(sf, textwrap.dedent("""\
            ---
            ---
            # [DOCS] Document API

            ## User Story

            **As a** writer,
            **I want to** document,
            **So that** users understand.

            ## Acceptance Criteria

            - AC1

            ## Documentation Scope

            API reference.

            ## Documentation Inputs

            Story 1.01 output.
        """))

        desc = sync_helper.render_story_description(
            sf, self.manifest,
            design_doc_link="https://example.com",
            epic_jira_key="EDM-101",
            story_type="DOCS",
        )
        self.assertIn("## Documentation Scope", desc)
        self.assertIn("## Documentation Inputs", desc)
        # Should NOT contain Implementation Guidance
        self.assertNotIn("## Implementation Guidance", desc)
        # Story ref should be resolved
        self.assertIn("EDM-201", desc)

    def test_cli_render_description(self) -> None:
        ef = Path(self.tmpdir) / "epic-1-building.md"
        _write(ef, "---\n---\n# Building\n\n## Summary\n\nBuild.\n\n## Acceptance Criteria\n\n- AC\n")
        mf = Path(self.tmpdir) / "manifest.json"
        _write(mf, json.dumps(self.manifest))

        out = StringIO()
        with mock.patch("sys.stdout", out):
            rc = sync_helper.main([
                "render-description", str(ef), str(mf),
                "--type", "epic",
                "--design-doc-link", "https://example.com",
                "--feature-key", "FEAT-1",
            ])
        self.assertEqual(rc, 0)
        self.assertIn("## Summary", out.getvalue())


# ---------------------------------------------------------------------------
# Test: multi-epic reference resolution
# ---------------------------------------------------------------------------

class TestMultiEpicRefs(unittest.TestCase):
    """Test reference resolution across multiple epics."""

    def test_cross_epic_story_refs(self) -> None:
        manifest = {
            "epics": [
                {
                    "file": "epic-1-building.md",
                    "jira_key": "EDM-101",
                    "stories": [
                        {"file": "story-01-scaffold.md", "jira_key": "EDM-201"},
                        {"file": "story-02-pipeline.md", "jira_key": "EDM-202"},
                    ],
                },
                {
                    "file": "epic-2-deploy.md",
                    "jira_key": "EDM-102",
                    "stories": [
                        {"file": "story-01-infra.md", "jira_key": "EDM-301"},
                        {"file": "story-02-config.md", "jira_key": "EDM-302"},
                    ],
                },
                {
                    "file": "epic-3-monitor.md",
                    "jira_key": "EDM-103",
                    "stories": [
                        {"file": "story-01-alerts.md", "jira_key": "EDM-401"},
                    ],
                },
            ],
        }

        # Cross-epic references
        text = "Depends on Stories 1.01, 2.01, 3.01 and Epic 2."
        result = sync_helper.resolve_refs(text, manifest)
        self.assertIn("EDM-201", result)
        self.assertIn("EDM-301", result)
        self.assertIn("EDM-401", result)
        self.assertIn("EDM-102", result)


# ---------------------------------------------------------------------------
# Test: consumer flow integration (end-to-end scenario)
# ---------------------------------------------------------------------------

class TestEndToEndFlow(unittest.TestCase):
    """Simulate a full detect → create → checkpoint → resume flow."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.artifacts = Path(self.tmpdir)
        self.stories_dir = self.artifacts / "06-stories"
        self.stories_dir.mkdir(parents=True)
        self.manifest_path = self.artifacts / "sync-manifest.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_full_create_flow(self) -> None:
        """Create epics and stories, checkpoint each, verify manifest."""
        _make_epic_file(self.stories_dir, 1, "building")
        _make_epic_file(self.stories_dir, 2, "deploy")
        _make_story_file(self.stories_dir, 1, 1, "scaffold")
        _make_story_file(self.stories_dir, 2, 1, "infra")

        # Step 1: detect changes
        plan = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(plan["summary"]["new"], 4)

        # Compute hashes at submission time
        epic1_hash = sync_helper.compute_file_hash(
            self.stories_dir / "epic-1-building.md"
        )
        epic2_hash = sync_helper.compute_file_hash(
            self.stories_dir / "epic-2-deploy.md"
        )

        # Step 2: create epic 1 in Jira (simulated success)
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", epic1_hash,
            item_type="epic", title="Building", size="M",
        )

        # Step 3: create epic 2 in Jira (simulated success)
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-2-deploy.md", "EDM-102", epic2_hash,
            item_type="epic", title="Deploy", size="L",
        )

        # Step 4: create story 1.01 under epic 1
        story1_hash = sync_helper.compute_file_hash(
            self.stories_dir / "epic-1" / "story-01-scaffold.md"
        )
        manifest = sync_helper.load_manifest(self.manifest_path)
        sync_helper._update_manifest_story_with_epic(
            manifest,
            "story-01-scaffold.md", "EDM-201", story1_hash,
            "active", "[DEV] Scaffold", "epic-1-building.md",
        )
        sync_helper.save_manifest(manifest, self.manifest_path)

        # Step 5: create story 2.01 under epic 2
        story2_hash = sync_helper.compute_file_hash(
            self.stories_dir / "epic-2" / "story-01-infra.md"
        )
        manifest = sync_helper.load_manifest(self.manifest_path)
        sync_helper._update_manifest_story_with_epic(
            manifest,
            "story-01-infra.md", "EDM-301", story2_hash,
            "active", "[DEV] Infra", "epic-2-deploy.md",
        )
        sync_helper.save_manifest(manifest, self.manifest_path)

        # Step 6: re-detect should show all unchanged
        plan = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(plan["summary"]["unchanged"], 4)
        self.assertEqual(plan["summary"]["new"], 0)

    def test_interrupted_then_resumed(self) -> None:
        """Simulate interruption after epic1 created, resume finds epic2 as new."""
        _make_epic_file(self.stories_dir, 1, "building")
        _make_epic_file(self.stories_dir, 2, "deploy")

        # First run: only epic1 succeeds
        epic1_hash = sync_helper.compute_file_hash(
            self.stories_dir / "epic-1-building.md"
        )
        sync_helper.update_manifest(
            self.manifest_path, "create",
            "epic-1-building.md", "EDM-101", epic1_hash,
            item_type="epic", title="Building",
        )
        # "Interruption" — epic2 never created

        # Resume: detect-changes shows epic2 as new
        plan = sync_helper.detect_changes(self.artifacts)
        new_items = [i for i in plan["items"] if i["category"] == "new"]
        unchanged = [i for i in plan["items"] if i["category"] == "unchanged"]
        self.assertEqual(len(new_items), 1)
        self.assertEqual(new_items[0]["file"], "epic-2-deploy.md")
        self.assertEqual(len(unchanged), 1)

    def test_failed_does_not_record(self) -> None:
        """If Jira create fails, update_manifest is not called and
        the item remains unsynced."""
        _make_epic_file(self.stories_dir, 1, "building")

        plan = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(plan["summary"]["new"], 1)

        # Simulate: Jira call FAILS — we never call update_manifest
        # Re-detect: still shows as new
        plan = sync_helper.detect_changes(self.artifacts)
        self.assertEqual(plan["summary"]["new"], 1)


if __name__ == "__main__":
    unittest.main()
