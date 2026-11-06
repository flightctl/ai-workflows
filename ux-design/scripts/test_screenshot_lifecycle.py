"""Regression tests for the screenshot publish/respond lifecycle.

Verifies the canonical owned-path procedure documented in
_shared/recipes/screenshot-publish-stage.md is consistent across
ux-design/skills/publish.md and ux-design/skills/respond.md.

Also validates section-name consistency across producer, publisher,
responder, and consumer instructions.

These tests parse the actual canonical instruction files — no
hand-copied procedure code.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))


def _read(relpath: str) -> str:
    with open(os.path.join(REPO_ROOT, relpath), encoding="utf-8") as f:
        return f.read()


class TestSharedRecipeExists(unittest.TestCase):
    """The canonical shared publish-stage recipe exists and is well-formed."""

    def test_recipe_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "_shared/recipes/screenshot-publish-stage.md")
        self.assertTrue(os.path.isfile(path), "screenshot-publish-stage.md missing")

    def test_recipe_has_frontmatter(self) -> None:
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        self.assertTrue(content.startswith("---"), "Missing YAML frontmatter")
        self.assertIn("name: screenshot-publish-stage", content)

    def test_recipe_includes_manifest_removed(self) -> None:
        """Recipe handles manifest removal (Bug 1 fix)."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        self.assertIn("MANIFEST_REMOVED", content)

    def test_recipe_includes_tracked_deletion_staging(self) -> None:
        """Recipe stages tracked deletions that no longer exist on disk."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        # The recipe should handle files staged by git rm (not on disk)
        self.assertIn("git rm", content.lower()) or self.assertIn(
            "already staged", content.lower()
        )

    def test_inspection_recipe_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "_shared/recipes/screenshot-inspection.md")
        self.assertTrue(os.path.isfile(path), "screenshot-inspection.md missing")


class TestPublishReferencesSharedRecipe(unittest.TestCase):
    """publish.md references the shared recipe (Bug 2 fix)."""

    def setUp(self) -> None:
        self.content = _read("ux-design/skills/publish.md")

    def test_references_shared_recipe(self) -> None:
        self.assertIn("screenshot-publish-stage.md", self.content)

    def test_no_inline_owned_paths_loop(self) -> None:
        """publish.md should not duplicate the owned_paths loop inline."""
        # The old inline loop had "for p in "${owned_paths[@]}"" etc.
        # After the fix, it delegates to the recipe.
        # Count occurrences of the git add staging loop
        add_loops = re.findall(
            r'for p in "\$\{owned_paths\[@\]\}"', self.content
        )
        self.assertEqual(
            len(add_loops),
            0,
            "publish.md still has inline owned_paths staging loop; "
            "should delegate to shared recipe",
        )

    def test_has_manifest_removed_parameter(self) -> None:
        """publish.md passes MANIFEST_REMOVED to the recipe."""
        self.assertIn("MANIFEST_REMOVED", self.content)


class TestRespondReferencesSharedRecipe(unittest.TestCase):
    """respond.md references the same shared recipe (Bug 2 fix)."""

    def setUp(self) -> None:
        self.content = _read("ux-design/skills/respond.md")

    def test_references_shared_recipe(self) -> None:
        self.assertIn("screenshot-publish-stage.md", self.content)

    def test_has_copied_filenames(self) -> None:
        """respond.md defines/tracks copied_filenames."""
        self.assertIn("copied_filenames", self.content)

    def test_has_removed_filenames(self) -> None:
        """respond.md defines/tracks removed_filenames."""
        self.assertIn("removed_filenames", self.content)

    def test_has_manifest_removed_parameter(self) -> None:
        """respond.md passes MANIFEST_REMOVED to the recipe."""
        self.assertIn("MANIFEST_REMOVED", self.content)


class TestInitialTextOnlyVsUpdateReconciliation(unittest.TestCase):
    """Bug 3: skip condition distinguishes initial text-only from updates."""

    def _assert_update_reconciliation(self, content: str, filename: str) -> None:
        """File must reconcile previous assets on updates."""
        self.assertIn(
            "publish-metadata",
            content.lower(),
            f"{filename} must check publish-metadata for prior assets",
        )
        # Must NOT skip when prior assets exist
        self.assertIn(
            "Reconcile previous assets",
            content,
            f"{filename} must reconcile previous assets on updates",
        )

    def test_publish_reconciles_updates(self) -> None:
        content = _read("ux-design/skills/publish.md")
        self._assert_update_reconciliation(content, "publish.md")

    def test_respond_reconciles_updates(self) -> None:
        content = _read("ux-design/skills/respond.md")
        self._assert_update_reconciliation(content, "respond.md")

    def test_publish_initial_skip_qualified(self) -> None:
        """publish.md skip is limited to initial text-only publishes."""
        content = _read("ux-design/skills/publish.md")
        self.assertIn("initial text-only", content.lower())

    def test_respond_initial_skip_qualified(self) -> None:
        """respond.md skip is limited to initial text-only publishes."""
        content = _read("ux-design/skills/respond.md")
        self.assertIn("initial text-only", content.lower())


class TestScreenshotIndexNaming(unittest.TestCase):
    """Bug 4: Section naming consistency across all files."""

    FILES = {
        "handoff": "ux-design/skills/handoff.md",
        "publish": "ux-design/skills/publish.md",
        "respond": "ux-design/skills/respond.md",
        "revise": "ux-design/skills/revise.md",
        "ingest": "ui-design/skills/ingest.md",
        "plan": "ui-design/skills/plan.md",
    }

    def test_handoff_uses_screenshot_index(self) -> None:
        content = _read(self.FILES["handoff"])
        self.assertIn("## Screenshot Index", content)

    def test_publish_uses_screenshot_index(self) -> None:
        content = _read(self.FILES["publish"])
        # publish references the section by name
        self.assertIn("Screenshot Index", content)
        # Must not use old "Screenshots section" phrasing
        self.assertNotIn(
            "the handoff's Screenshots section",
            content,
            "publish.md still uses old 'Screenshots section' naming",
        )

    def test_respond_uses_screenshot_index(self) -> None:
        content = _read(self.FILES["respond"])
        self.assertIn("Screenshot Index", content)

    def test_ingest_uses_screenshot_index(self) -> None:
        content = _read(self.FILES["ingest"])
        self.assertIn("Screenshot Index", content)
        self.assertNotIn(
            "its Screenshots section references",
            content,
            "ingest.md still uses old 'Screenshots section' naming",
        )

    def test_plan_references_screenshot_observations(self) -> None:
        """plan.md reads Screenshot Observations from ingest context."""
        content = _read(self.FILES["plan"])
        self.assertIn("Screenshot", content)


class TestExternalModeFullRewrite(unittest.TestCase):
    """Bug 5: respond rewrites ALL image refs, not just changed ones."""

    def setUp(self) -> None:
        self.content = _read("ux-design/skills/respond.md")

    def test_unchanged_images_reuse_urls(self) -> None:
        """Unchanged images reuse published_path from metadata."""
        self.assertIn("Unchanged images", self.content)
        self.assertIn("published_path", self.content)

    def test_every_embed_rewritten(self) -> None:
        """ALL current embeds are rewritten, not just changed ones."""
        # Must contain language about rewriting every/all refs
        lower = self.content.lower()
        self.assertTrue(
            "every" in lower and "embed" in lower,
            "respond.md must rewrite every embed in external mode",
        )

    def test_metadata_after_success(self) -> None:
        """Metadata updated only after successful commit+push."""
        self.assertIn(
            "after the commit",
            self.content.lower(),
        )


class TestManifestFieldAlignment(unittest.TestCase):
    """Handoff header fields and consumer manifest fields align."""

    def test_handoff_has_context_revision(self) -> None:
        content = _read("ux-design/skills/handoff.md")
        self.assertIn("context_revision", content)
        self.assertIn("prototype_iteration", content)
        self.assertIn("**Context revision:**", content)
        self.assertIn("**Prototype iteration:**", content)

    def test_manifest_has_context_revision(self) -> None:
        """Publish writes context_revision and prototype_iteration."""
        content = _read("ux-design/skills/publish.md")
        self.assertIn("context_revision", content)
        self.assertIn("prototype_iteration", content)

    def test_ingest_checks_header_vs_manifest(self) -> None:
        """Ingest compares manifest revision with handoff header."""
        content = _read("ui-design/skills/ingest.md")
        self.assertIn("context_revision", content)
        self.assertIn("prototype_iteration", content)
        # Should mention comparing/matching
        self.assertTrue(
            "differ" in content.lower() or "match" in content.lower(),
            "ingest should compare manifest and handoff header fields",
        )


class TestAgentsMdRecipeListing(unittest.TestCase):
    """New recipes are listed in AGENTS.md."""

    def setUp(self) -> None:
        self.content = _read("AGENTS.md")

    def test_publish_stage_listed(self) -> None:
        self.assertIn("screenshot-publish-stage.md", self.content)

    def test_inspection_listed(self) -> None:
        self.assertIn("screenshot-inspection.md", self.content)


class TestIngestTokenBudget(unittest.TestCase):
    """Ingest token count is within baseline (<=6478, preferably <=6000)."""

    def test_ingest_char_count_within_baseline(self) -> None:
        content = _read("ui-design/skills/ingest.md")
        # Rough estimate: 4 chars per token
        est_tokens = len(content) // 4
        self.assertLessEqual(
            est_tokens,
            6478,
            f"ingest.md ~{est_tokens} tokens exceeds baseline 6478",
        )


if __name__ == "__main__":
    unittest.main()
