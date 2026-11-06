"""Regression tests for the screenshot publish/respond lifecycle.

Part 1 (Structural): Parses actual canonical instruction files to verify
cross-file consistency — section names, recipe references, parameter
completeness, field alignment.

Part 2 (Executable): Extracts the Bash fenced blocks from the committed
_shared/recipes/screenshot-publish-stage.md, instantiates declared
parameters, and runs them in disposable Git repos via subprocess.
Covers: initial images+manifest, initial text-only, unchanged repeat,
image-only update, one-image removal, final-image+manifest removal
(including external-mode manifest-only), and external doc+manifest-only
update. Seeds unrelated staged/unstaged files and asserts survival.

Scope: staging/commit procedure only. Does NOT exercise prose-level URL
fetching, rewriting, runtime image inspection, or any live workflow.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))


def _read(relpath: str) -> str:
    with open(os.path.join(REPO_ROOT, relpath), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Helper: extract and instantiate recipe bash blocks
# ---------------------------------------------------------------------------

def _w(path: str, content: str = "") -> None:
    """Write content to a file (properly closed)."""
    with open(path, "w") as f:
        f.write(content)


def _extract_bash_blocks(md_content: str) -> list[str]:
    """Return the contents of all ```bash ... ``` blocks in order."""
    return re.findall(r"```bash\n(.*?)```", md_content, re.DOTALL)


def _instantiate_recipe(
    docs: str,
    handoff_path: str,
    handoff_dir: str,
    commit_msg: str,
    copied: list[str] | None = None,
    removed: list[str] | None = None,
    manifest_written: bool = False,
    manifest_removed: bool = False,
) -> str:
    """Build a runnable Bash script from the recipe's fenced blocks.

    Declares parameter variables, then pastes the three recipe blocks
    (build allowlist, stage, check+commit) verbatim after substitution
    of the declared placeholders.
    """
    recipe_md = _read("_shared/recipes/screenshot-publish-stage.md")
    blocks = _extract_bash_blocks(recipe_md)
    assert len(blocks) == 3, f"Expected 3 bash blocks in recipe, got {len(blocks)}"

    # Join recipe blocks with parameter declarations.
    # Recipe uses two placeholder conventions:
    #   {PARAM} — text-substituted to shell variable references
    #   ${VAR}  — already shell variable references, kept as-is
    copied_arr = " ".join(f'"{f}"' for f in (copied or []))
    removed_arr = " ".join(f'"{f}"' for f in (removed or []))

    script = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # --- Parameter declarations (from caller) ---
        DOCS_REPO_PATH="{docs}"
        HANDOFF_FILE_PATH="{handoff_path}"
        HANDOFF_DIR="{handoff_dir}"
        COPIED_FILENAMES=({copied_arr})
        REMOVED_FILENAMES=({removed_arr})
        MANIFEST_WRITTEN="{str(manifest_written).lower()}"
        MANIFEST_REMOVED="{str(manifest_removed).lower()}"
        COMMIT_MESSAGE="{commit_msg}"

    """)
    # Text-substitute {PLACEHOLDER} tokens to $VARIABLE references.
    # The recipe's ${...} references (MANIFEST_WRITTEN, etc.) are
    # already valid shell and need no transformation.
    subs = {
        "{HANDOFF_FILE_PATH}": "$HANDOFF_FILE_PATH",
        "{HANDOFF_DIR}": "$HANDOFF_DIR",
        "{DOCS_REPO_PATH}": "$DOCS_REPO_PATH",
        "{COMMIT_MESSAGE}": "$COMMIT_MESSAGE",
    }
    for i, block in enumerate(blocks):
        for old, new in subs.items():
            block = block.replace(old, new)
        script += f"# --- Recipe block {i+1} ---\n{block}\n"

    return script


def _run_script(script: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a bash script, returning the result.

    Uses set -uo pipefail (strict unset + pipefail) but NOT -e (errexit),
    because the recipe intentionally uses ``git diff --cached --quiet``
    which returns exit 1 to signal "there are staged changes" — that is
    not an error. The recipe captures $? and branches; errexit would
    abort before the branch.
    """
    return subprocess.run(
        ["bash", "-uo", "pipefail", "-c", script],
        capture_output=True, text=True, cwd=cwd,
    )


def _setup_repo(tmpdir: str) -> str:
    """Create a minimal git repo with an initial commit, return its path."""
    repo = os.path.join(tmpdir, "docs-repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", repo], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", repo, "config", "user.email", "test@test"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", repo, "config", "user.name", "test"],
        capture_output=True, check=True,
    )
    # Initial commit so HEAD exists
    dummy = os.path.join(repo, ".gitkeep")
    _w(dummy)
    subprocess.run(["git", "-C", repo, "add", ".gitkeep"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", repo, "commit", "-m", "init"],
        capture_output=True, check=True,
    )
    return repo


# ===================================================================
# Part 1: Structural assertions on canonical instruction files
# ===================================================================

class TestStructuralRecipeConsistency(unittest.TestCase):
    """Cross-file structural checks — recipe references, params, naming."""

    def test_recipe_exists_and_has_frontmatter(self) -> None:
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        self.assertTrue(content.startswith("---"))
        self.assertIn("name: screenshot-publish-stage", content)

    def test_inspection_recipe_exists(self) -> None:
        path = os.path.join(REPO_ROOT, "_shared/recipes/screenshot-inspection.md")
        self.assertTrue(os.path.isfile(path))

    def test_inspection_recipe_has_per_image_schema(self) -> None:
        content = _read("_shared/recipes/screenshot-inspection.md")
        for field in ("expected_sha", "observed_sha", "ref", "spec_match"):
            self.assertIn(field, content, f"inspection recipe missing field {field}")

    def test_publish_references_recipe(self) -> None:
        content = _read("ux-design/skills/publish.md")
        self.assertIn("screenshot-publish-stage.md", content)
        self.assertIn("MANIFEST_REMOVED", content)

    def test_respond_references_recipe_with_arrays(self) -> None:
        content = _read("ux-design/skills/respond.md")
        self.assertIn("screenshot-publish-stage.md", content)
        self.assertIn("copied_filenames", content)
        self.assertIn("removed_filenames", content)
        self.assertIn("MANIFEST_REMOVED", content)

    def test_respond_external_final_removal_manifest(self) -> None:
        """respond external mode removes consumer manifest on final image."""
        content = _read("ux-design/skills/respond.md")
        self.assertIn("Final-image removal in external mode", content)
        self.assertIn("MANIFEST_REMOVED", content)

    def test_screenshot_index_naming(self) -> None:
        for label, path in [
            ("handoff", "ux-design/skills/handoff.md"),
            ("publish", "ux-design/skills/publish.md"),
            ("respond", "ux-design/skills/respond.md"),
            ("ingest", "ui-design/skills/ingest.md"),
        ]:
            content = _read(path)
            self.assertIn("Screenshot Index", content, f"{label} missing Screenshot Index")
            self.assertNotIn(
                "the handoff's Screenshots section", content,
                f"{label} has old Screenshots section naming",
            )

    def test_ingest_uses_relative_path_for_recipe(self) -> None:
        """Correction 1: recipe ref must use relative ../../ not ${HOME}."""
        content = _read("ui-design/skills/ingest.md")
        # The screenshot-inspection recipe reference must be relative
        self.assertIn("../../_shared/recipes/screenshot-inspection.md", content)
        # Must NOT use ${HOME} for the recipe (scripts are different)
        self.assertNotIn(
            "${HOME}/.ai-workflows/_shared/recipes/screenshot-inspection.md",
            content,
        )

    def test_publish_step3b_in_memory_only(self) -> None:
        """Correction 2: Step3b resolves none in memory, not persisted."""
        content = _read("ux-design/skills/publish.md")
        self.assertIn("in memory only", content)

    def test_recipes_listed_in_agents(self) -> None:
        content = _read("AGENTS.md")
        self.assertIn("screenshot-publish-stage.md", content)
        self.assertIn("screenshot-inspection.md", content)

    def test_ingest_context_has_full_schema(self) -> None:
        """Correction 4: context template has full 9-column table header."""
        content = _read("ui-design/skills/ingest.md")
        # Extract the Screenshot Observations section
        parts = content.split("### Screenshot Observations", 1)
        self.assertEqual(len(parts), 2, "Missing Screenshot Observations section")
        section = parts[1].split("### Feasibility & Phasing", 1)[0]
        self.assertIn(
            "| ID | Status | Identity | Ref | Expected SHA | Observed SHA "
            "| Observation | Spec Match | Notes |",
            section,
        )

    def test_plan_accepted_unverified_label(self) -> None:
        """Plan uses accepted-unverified citation for both ordinary and additive."""
        content = _read("ui-design/skills/plan.md")
        # Scoped to the citation instructions section
        section = content.split(
            "If `HAS_SCREENSHOTS` is true or `partial`", 1
        )[1].split("If `HAS_SCREENSHOTS` is `deferred`", 1)[0]
        self.assertIn("[Screenshot: SS-N]", section)
        self.assertIn("accepted-unverified", section)
        self.assertIn("[Screenshot: SS-N — accepted-unverified]", section)
        # Additive forms: both verified and accepted-unverified
        self.assertIn("[Screenshot: SS-N — additive: {detail}]", section)
        self.assertIn(
            "[Screenshot: SS-N — accepted-unverified, additive: {detail}]",
            section,
        )
        self.assertIn(
            "Do not cite `unavailable` or `lfs-unresolved` images.", section
        )

    def test_ingest_token_budget(self) -> None:
        content = _read("ui-design/skills/ingest.md")
        est = len(content) // 4
        self.assertLessEqual(est, 6100, f"ingest ~{est} est tokens > 6100")

    def test_plan_token_budget(self) -> None:
        content = _read("ui-design/skills/plan.md")
        est = len(content) // 4
        self.assertLessEqual(est, 6100, f"plan ~{est} est tokens > 6100")

    def test_ingest_aggregate_status_mapping(self) -> None:
        """Item 2: ingest maps per-image statuses to aggregate status."""
        content = _read("ui-design/skills/ingest.md")
        self.assertIn("inspected", content)
        self.assertIn("partial", content)
        self.assertIn("unavailable", content)

    def test_ingest_rerun_step7(self) -> None:
        """Item 3: no-evidence gate says to re-run Step 7."""
        content = _read("ui-design/skills/ingest.md")
        self.assertIn("re-run Step 7", content)

    def test_ingest_legacy_embeds_not_silently_false(self) -> None:
        """Item B: absent index with inline embeds reports inconsistency."""
        content = _read("ui-design/skills/ingest.md")
        section = content.split("Screenshot inspection", 1)[1].split(
            "Provenance freshness", 1
        )[0]
        # True no-image: "None", no inline embeds -> false
        self.assertIn("HAS_SCREENSHOTS = false", section)
        # Legacy/contradictory: absent index + embeds -> report inconsistency
        self.assertIn("inconsistency", section)
        self.assertIn("updated handoff", section)

    def test_ingest_write_cleanup_on_confirm(self) -> None:
        """Item 4: Step 8a defines write + cleanup for both paths."""
        content = _read("ui-design/skills/ingest.md")
        step8a = content.split("### Step 8a:", 1)[1].split("### Step 9", 1)[0]
        # Normalize whitespace for cross-line assertions
        flat = " ".join(step8a.split())
        # Confirm path: write content, delete .prev and temp
        self.assertIn("write compiled content to `01-context.md`", flat)
        self.assertIn("01-context.md.prev", flat)
        # Decline path: discard content, delete .prev and temp, preserve
        self.assertIn("discard compiled content", flat)
        self.assertIn("temp file", flat)
        self.assertIn("preserved", flat)

    def test_plan_missing_screenshot_section_fallback(self) -> None:
        """Item 5: plan handles absent Screenshot Observations; preserves no-handoff."""
        content = _read("ui-design/skills/plan.md")
        fallback = content.split("Screenshot Observations or its status is absent", 1)
        self.assertEqual(len(fallback), 2, "Missing absent-status fallback")
        instructions = fallback[1].split("Screenshots show", 1)[0]
        # No-handoff path: HAS_HANDOFF=false -> HAS_SCREENSHOTS=false, no re-ingest
        self.assertIn("HAS_HANDOFF", instructions)
        self.assertIn("HAS_SCREENSHOTS = false", instructions)
        # Handoff-present unknown path: offers re-ingest or unavailable
        self.assertIn("rerun", instructions)
        self.assertIn("unavailable", instructions)

    def test_inspection_recipe_path_containment(self) -> None:
        """Item 10: inspection recipe rejects traversal for local refs only."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        # Containment is scoped under Local references, not before reference selection
        local_section = content.split("**Local references**", 1)[1].split(
            "**External references**", 1
        )[0]
        self.assertIn("Path containment", local_section)
        self.assertIn("..", local_section)
        self.assertIn("symlink", local_section)
        # External section has no filesystem containment check
        external_section = content.split("**External references**", 1)[1].split(
            "###", 1
        )[0]
        self.assertNotIn("Path containment", external_section)

    def test_publish_stage_recipe_empty_array_guard(self) -> None:
        """Item 11: recipe guards empty array expansion under nounset."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        # Both loops must use the ${arr[@]+...} guard pattern
        self.assertIn('${COPIED_FILENAMES[@]+"${COPIED_FILENAMES[@]}"}', content)
        self.assertIn('${REMOVED_FILENAMES[@]+"${REMOVED_FILENAMES[@]}"}', content)

    def test_handoff_sha256_fallback(self) -> None:
        """Item 14: handoff provides shasum -a 256 fallback."""
        content = _read("ux-design/skills/handoff.md")
        self.assertIn("shasum -a 256", content)

    def test_publish_reject_empty_manifest(self) -> None:
        """Item 15: publish rejects empty manifest when handoff has refs."""
        content = _read("ux-design/skills/publish.md")
        self.assertIn("missing or has no screenshot entries", content)

    def test_publish_git_rm_consumer_manifest(self) -> None:
        """Item 16: publish uses git rm for tracked consumer manifest."""
        content = _read("ux-design/skills/publish.md")
        self.assertIn("`git rm` the tracked consumer manifest", content)

    def test_publish_step_numbering_no_sub_steps(self) -> None:
        """Root A: publish uses main step numbers, no 3a/3b sub-steps."""
        content = _read("ux-design/skills/publish.md")
        self.assertNotIn("Step 3a", content)
        self.assertNotIn("Step 3b", content)
        # Verify the renumbered steps exist
        self.assertIn("### Step 4: Validate Screenshot References", content)
        self.assertIn("### Step 5: Resolve Screenshot Storage Policy", content)
        self.assertIn("### Step 6: Create or Update Branch and Commit", content)

    def test_publish_metadata_refresh_on_update(self) -> None:
        """Item 9: metadata refreshes screenshot_assets after successful update."""
        content = _read("ux-design/skills/publish.md")
        # Scoped to Step 9 (Save Publish Metadata)
        step9 = content.split("Step 9: Save Publish Metadata", 1)[1].split(
            "Step 10:", 1
        )[0]
        self.assertIn("update `screenshot_storage`", step9)
        self.assertIn("replace `screenshot_assets`", step9)
        # Success-only: refresh happens after successful commit+push
        self.assertIn("successful update commit and push", step9)
        # Identity preservation
        self.assertIn("retain the PR number, branch", step9)

    def test_revise_index_sha_update(self) -> None:
        """Item 17: revise updates Screenshot Index SHA on replacement."""
        content = _read("ux-design/skills/revise.md")
        self.assertIn("Screenshot Index SHA-256", content)

    def test_respond_publish_step_ref_updated(self) -> None:
        """Root A: respond.md references updated publish step number."""
        content = _read("ux-design/skills/respond.md")
        self.assertIn("`/publish` Step 6", content)
        self.assertNotIn("`/publish` Step 4.", content)

    def test_handoff_capture_provenance(self) -> None:
        """Item 13: handoff verifies per-image capture provenance with all bindings."""
        content = _read("ux-design/skills/handoff.md")
        provenance = content.split("Per-image capture provenance", 1)[1].split(
            "Selection criteria", 1
        )[0]
        # Requires capture index
        self.assertIn("screenshot-captures.json", provenance)
        # Checks all three bindings per image
        self.assertIn("context_revision", provenance)
        self.assertIn("discovery_revision", provenance)
        self.assertIn("prototype_iteration", provenance)
        # Absent index means no verified images — prohibits header fallback
        self.assertIn("do not fall back to the evaluation header", provenance)
        self.assertIn("no screenshots can be verified as current", provenance)
        # Researcher-supplied source path (private) with all-binding confirmation
        supplied = content.split("Researcher-supplied", 1)[1].split(
            "Selection criteria", 1
        )[0]
        self.assertIn("source", supplied)
        self.assertIn("discovery revision", supplied)

    def test_evaluate_capture_index_schema(self) -> None:
        """Item 13: evaluate writes capture index at every depth."""
        content = _read("ux-design/skills/evaluate.md")
        index = content.split("screenshot-captures.json", 1)[1].split(
            "Run the skill", 1
        )[0]
        # Schema includes all three binding fields per capture entry
        self.assertIn("context_revision", index)
        self.assertIn("discovery_revision", index)
        self.assertIn("prototype_iteration", index)
        self.assertIn("sha256", index)
        self.assertIn("filename", index)
        self.assertIn("captures", index)
        # Written at every depth, not just Standard/Full
        self.assertIn("At every depth", content.split("screenshot-captures.json")[0])
        # No-capture runs write empty captures array
        self.assertIn("captures:[]", index)

    def test_config_precedence(self) -> None:
        """Item 7: publish checks workflow-specific config first."""
        content = _read("ux-design/skills/publish.md")
        self.assertIn("ux-design/config.json` first", content)


# ===================================================================
# Part 2: Executable Bash tests of the actual recipe code
# ===================================================================

class TestRecipeExecution(unittest.TestCase):
    """Extract Bash blocks from screenshot-publish-stage.md, run them."""

    def _exec(
        self, repo: str, handoff_path: str, handoff_dir: str,
        copied: list[str] | None = None, removed: list[str] | None = None,
        manifest_written: bool = False, manifest_removed: bool = False,
        msg: str = "test commit",
    ) -> subprocess.CompletedProcess:
        script = _instantiate_recipe(
            repo, handoff_path, handoff_dir, msg,
            copied, removed, manifest_written, manifest_removed,
        )
        return _run_script(script)

    # --- T1: Initial images + manifest ---
    def test_initial_images_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-1")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            # Write handoff, manifest, image
            _w(os.path.join(d, "handoff.md"), "# Handoff\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-pop.png"), "img1")
            # Seed unrelated staged file
            _w(os.path.join(repo, "unrelated-staged.txt"), "staged")
            subprocess.run(["git", "-C", repo, "add", "unrelated-staged.txt"],
                           capture_output=True, check=True)
            # Seed unrelated unstaged file
            _w(os.path.join(repo, "unrelated-dirty.txt"), "dirty")

            r = self._exec(
                repo, "feat/PROJ-1/handoff.md", "feat/PROJ-1",
                copied=["SS-1-pop.png"], manifest_written=True,
                msg="Add handoff",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            # Verify commit happened
            log = subprocess.run(
                ["git", "-C", repo, "log", "--oneline", "-1"],
                capture_output=True, text=True,
            )
            self.assertIn("Add handoff", log.stdout)
            # Verify unrelated staged file survives in index
            status = subprocess.run(
                ["git", "-C", repo, "status", "--porcelain"],
                capture_output=True, text=True,
            )
            self.assertIn("unrelated-staged.txt", status.stdout)
            self.assertIn("unrelated-dirty.txt", status.stdout)

    # --- T2: Initial text-only (no optional paths) ---
    def test_initial_text_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-2")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Text only\n")

            r = self._exec(
                repo, "feat/PROJ-2/handoff.md", "feat/PROJ-2",
                msg="Add text handoff",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            log = subprocess.run(
                ["git", "-C", repo, "log", "--oneline", "-1"],
                capture_output=True, text=True,
            )
            self.assertIn("Add text handoff", log.stdout)

    # --- T3: Unchanged repeat — no extra commit ---
    def test_unchanged_repeat_no_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-3")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Handoff\n")
            # Initial commit
            self._exec(repo, "feat/PROJ-3/handoff.md", "feat/PROJ-3",
                        msg="Initial")
            before = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            # Re-run without changes
            r = self._exec(repo, "feat/PROJ-3/handoff.md", "feat/PROJ-3",
                            msg="Should not appear")
            self.assertEqual(r.returncode, 0, r.stderr)
            after = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(before, after, "Unchanged repeat created a commit")

    # --- T4: Image-only update ---
    def test_image_only_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-4")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# H\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-a.png"), "v1")
            self._exec(repo, "feat/PROJ-4/handoff.md", "feat/PROJ-4",
                        copied=["SS-1-a.png"], manifest_written=True,
                        msg="Init images")
            # Update image content
            _w(os.path.join(sd, "SS-1-a.png"), "v2")
            _w(os.path.join(d, "screenshot-manifest.json"), '{"v":2}')
            r = self._exec(
                repo, "feat/PROJ-4/handoff.md", "feat/PROJ-4",
                copied=["SS-1-a.png"], manifest_written=True,
                msg="Update image",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            log = subprocess.run(
                ["git", "-C", repo, "log", "--oneline", "-1"],
                capture_output=True, text=True,
            )
            self.assertIn("Update image", log.stdout)

    # --- T5: One-image removal ---
    def test_one_image_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-5")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# H\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-a.png"), "keep")
            _w(os.path.join(sd, "SS-2-b.png"), "remove")
            self._exec(repo, "feat/PROJ-5/handoff.md", "feat/PROJ-5",
                        copied=["SS-1-a.png", "SS-2-b.png"],
                        manifest_written=True, msg="Init 2 images")
            # Remove SS-2
            subprocess.run(
                ["git", "-C", repo, "rm", "feat/PROJ-5/screenshots/SS-2-b.png"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# H updated\n")
            _w(os.path.join(d, "screenshot-manifest.json"), '{"only1":true}')
            r = self._exec(
                repo, "feat/PROJ-5/handoff.md", "feat/PROJ-5",
                removed=["SS-2-b.png"], manifest_written=True,
                msg="Remove one image",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            # SS-1 still tracked
            ls = subprocess.run(
                ["git", "-C", repo, "ls-files", "feat/PROJ-5/screenshots/SS-1-a.png"],
                capture_output=True, text=True,
            )
            self.assertIn("SS-1-a.png", ls.stdout)
            # SS-2 gone
            ls2 = subprocess.run(
                ["git", "-C", repo, "ls-files", "feat/PROJ-5/screenshots/SS-2-b.png"],
                capture_output=True, text=True,
            )
            self.assertEqual(ls2.stdout.strip(), "")

    # --- T6: Final image + manifest removal (lfs/git mode) ---
    def test_final_image_and_manifest_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-6")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# H\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-only.png"), "solo")
            self._exec(repo, "feat/PROJ-6/handoff.md", "feat/PROJ-6",
                        copied=["SS-1-only.png"], manifest_written=True,
                        msg="Init single image")
            # Remove last image + manifest
            subprocess.run(
                ["git", "-C", repo, "rm", "feat/PROJ-6/screenshots/SS-1-only.png"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "rm", "feat/PROJ-6/screenshot-manifest.json"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# Text only now\n")
            # Seed unrelated staged+unstaged to verify survival
            _w(os.path.join(repo, "other-staged.txt"), "s")
            subprocess.run(["git", "-C", repo, "add", "other-staged.txt"],
                           capture_output=True, check=True)
            _w(os.path.join(repo, "other-dirty.txt"), "d")

            r = self._exec(
                repo, "feat/PROJ-6/handoff.md", "feat/PROJ-6",
                removed=["SS-1-only.png"],
                manifest_removed=True,
                msg="Remove final image and manifest",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            # Manifest no longer tracked
            ls = subprocess.run(
                ["git", "-C", repo, "ls-files",
                 "feat/PROJ-6/screenshot-manifest.json"],
                capture_output=True, text=True,
            )
            self.assertEqual(ls.stdout.strip(), "", "manifest still tracked")
            # Unrelated staged file survives
            st = subprocess.run(
                ["git", "-C", repo, "status", "--porcelain"],
                capture_output=True, text=True,
            )
            self.assertIn("other-staged.txt", st.stdout)
            self.assertIn("other-dirty.txt", st.stdout)
            # Commit only touched owned paths
            show = subprocess.run(
                ["git", "-C", repo, "diff-tree", "--no-commit-id",
                 "--name-only", "-r", "HEAD"],
                capture_output=True, text=True,
            )
            self.assertNotIn("other-staged.txt", show.stdout)

    # --- T7: External-mode manifest-only removal (final image) ---
    def test_external_manifest_only_removal(self) -> None:
        """External mode: no local image files, only manifest to remove."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-7")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Ext\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            # Initial commit with handoff + manifest (external: no image files)
            self._exec(repo, "feat/PROJ-7/handoff.md", "feat/PROJ-7",
                        manifest_written=True, msg="Init external")
            # Remove manifest (all external images removed)
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-7/screenshot-manifest.json"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# Ext text-only\n")
            r = self._exec(
                repo, "feat/PROJ-7/handoff.md", "feat/PROJ-7",
                manifest_removed=True,
                msg="External: remove manifest",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            ls = subprocess.run(
                ["git", "-C", repo, "ls-files",
                 "feat/PROJ-7/screenshot-manifest.json"],
                capture_output=True, text=True,
            )
            self.assertEqual(ls.stdout.strip(), "")

    # --- T8: External doc+manifest-only update ---
    def test_external_doc_and_manifest_update(self) -> None:
        """External mode text edit: handoff + manifest update, no images."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-8")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Ext v1\n")
            _w(os.path.join(d, "screenshot-manifest.json"), '{"v":1}')
            self._exec(repo, "feat/PROJ-8/handoff.md", "feat/PROJ-8",
                        manifest_written=True, msg="Init ext")
            # Update handoff text + regenerated manifest
            _w(os.path.join(d, "handoff.md"), "# Ext v2\n")
            _w(os.path.join(d, "screenshot-manifest.json"), '{"v":2}')
            r = self._exec(
                repo, "feat/PROJ-8/handoff.md", "feat/PROJ-8",
                manifest_written=True,
                msg="External: text+manifest update",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            log = subprocess.run(
                ["git", "-C", repo, "log", "--oneline", "-1"],
                capture_output=True, text=True,
            )
            self.assertIn("text+manifest update", log.stdout)

    # --- T9: Verify recipe has exactly 3 bash blocks ---
    def test_recipe_bash_block_count(self) -> None:
        recipe = _read("_shared/recipes/screenshot-publish-stage.md")
        blocks = _extract_bash_blocks(recipe)
        self.assertEqual(len(blocks), 3,
                         f"Recipe should have 3 bash blocks, got {len(blocks)}")


if __name__ == "__main__":
    unittest.main()
