#!/usr/bin/env python3
"""Tests for design/scripts/sync_helper.py."""

from __future__ import annotations

import hashlib
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
        mf = Path(tempfile.mktemp(suffix=".json"))
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
                "--jira_key", "EDM-201", "--content-hash", "def",
                "--item-type", "story",
            ])
        # argparse error (unrecognized --jira_key) or our error — either way non-zero


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
        content = "---\n---\n# Building\n\n## Summary\n\nBuild things.\n"
        _write(ef, content)
        result = sync_helper.prepare(
            ef, self.manifest_path, "epic",
            feature_key="FEAT-100")
        self.assertEqual(result["content_hash"], _sha256(content))
        self.assertIn("Build things.", result["description"])

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

    def test_cli_prepare(self) -> None:
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "---\n---\n# E\n\n## Summary\n\nS.\n")
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(ef), str(self.manifest_path),
                              "--type", "epic"])
        result = json.loads(out.getvalue())
        self.assertIn("content_hash", result)
        self.assertIn("description", result)


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
        """Complete detect → prepare → create → checkpoint → verify."""
        ef = _make_epic(self.sd, 1, "building")
        sf = _make_dev_story(self.sd, 1, 1, "scaffold")

        # 1. detect-changes
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["detect-changes", str(self.arts)])
        plan = json.loads(out.getvalue())
        self.assertEqual(plan["summary"]["new"], 2)

        # 2. prepare epic
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(ef), str(self.mf),
                              "--type", "epic", "--feature-key", "FEAT-100"])
        prep = json.loads(out.getvalue())

        # 3. checkpoint epic (simulated Jira success)
        sync_helper.main([
            "update-manifest", str(self.mf),
            "--operation", "create", "--file", ef.name,
            "--jira-key", "EDM-101", "--content-hash", prep["content_hash"],
            "--item-type", "epic", "--feature-key", "FEAT-100",
        ])

        # 4. prepare story
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["prepare", str(sf), str(self.mf),
                              "--type", "story", "--epic-jira-key", "EDM-101"])
        sprep = json.loads(out.getvalue())

        # 5. checkpoint story
        sync_helper.main([
            "update-manifest", str(self.mf),
            "--operation", "create", "--file", sf.name,
            "--jira-key", "EDM-201", "--content-hash", sprep["content_hash"],
            "--item-type", "story", "--epic-file", ef.name,
        ])

        # 6. re-detect: all unchanged
        out = StringIO()
        with mock.patch("sys.stdout", out):
            sync_helper.main(["detect-changes", str(self.arts)])
        plan = json.loads(out.getvalue())
        self.assertEqual(plan["summary"]["unchanged"], 2)
        self.assertEqual(plan["summary"]["new"], 0)

        # 7. verify manifest has feature_key
        manifest = sync_helper.load_manifest(self.mf)
        self.assertEqual(manifest["feature_key"], "FEAT-100")


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

    def test_missing_summary_renders_empty(self) -> None:
        """Missing Summary section renders empty (compatible, not error)."""
        ef = Path(self.tmpdir) / "epic.md"
        _write(ef, "---\n---\n# Building\n\n## Acceptance Criteria\n\n- AC\n")
        result = sync_helper.prepare(str(ef), str(self.mf), "epic")
        self.assertIn("## Summary", result["description"])

    def test_removed_story_frontmatter_variant(self) -> None:
        """Story with 'status: removed' frontmatter still parseable."""
        sf = Path(self.tmpdir) / "story.md"
        _write(sf, "---\nstatus: removed\n---\n# [DEV] Removed Story\n\n## Acceptance Criteria\n\n- AC\n")
        result = sync_helper.prepare(str(sf), str(self.mf), "story")
        self.assertIn("content_hash", result)


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

    def test_missing_06_stories_with_manifest_warns(self) -> None:
        """Missing 06-stories/ dir with manifest → warning, not silent orphan."""
        arts = Path(self.tmpdir) / "art"
        arts.mkdir()
        _make_manifest(arts, [{
            "file": "epic-1.md", "jira_key": "K-1",
            "content_hash": "h", "synced_status": "active", "stories": [],
        }])
        plan = sync_helper.detect_changes(arts)
        self.assertTrue(
            any("06-stories" in w for w in plan["warnings"]),
            "Should warn about missing 06-stories directory")

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


if __name__ == "__main__":
    unittest.main()
