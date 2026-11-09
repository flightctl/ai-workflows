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
        """Plan references recipe §5 eligibility and uses additive forms."""
        content = _read("ui-design/skills/plan.md")
        # Scoped to the citation instructions section
        section = content.split(
            "If `HAS_SCREENSHOTS` is true or `partial`", 1
        )[1].split("If `HAS_SCREENSHOTS` is `deferred`", 1)[0]
        # References recipe eligibility table
        self.assertIn("screenshot-inspection.md", section)
        self.assertIn("eligibility", section)
        # Additive forms: both verified and accepted-unverified
        self.assertIn("[Screenshot: SS-N — additive: {detail}]", section)
        self.assertIn(
            "[Screenshot: SS-N — accepted-unverified, additive: {detail}]",
            section,
        )
        self.assertIn(
            "Do not cite `unavailable` or `lfs-unresolved` images.", section
        )
        # Recipe has the full citation forms
        recipe = _read("_shared/recipes/screenshot-inspection.md")
        recipe_elig = recipe.split("Eligibility and citation rules", 1)[1]
        self.assertIn("[Screenshot: SS-N]", recipe_elig)
        self.assertIn("accepted-unverified", recipe_elig)

    def test_ingest_token_budget(self) -> None:
        content = _read("ui-design/skills/ingest.md")
        est = len(content) // 4
        self.assertLess(est, 6000, f"ingest ~{est} tokens >= 6000 checker limit")

    def test_plan_token_budget(self) -> None:
        content = _read("ui-design/skills/plan.md")
        est = len(content) // 4
        self.assertLess(est, 6000, f"plan ~{est} tokens >= 6000 checker limit")

    def test_publish_token_budget(self) -> None:
        content = _read("ux-design/skills/publish.md")
        est = len(content) // 4
        self.assertLess(est, 6000, f"publish ~{est} tokens >= 6000 checker limit")

    def test_ingest_aggregate_status_mapping(self) -> None:
        """Item 2: ingest maps per-image statuses to aggregate status."""
        content = _read("ui-design/skills/ingest.md")
        self.assertIn("inspected", content)
        self.assertIn("partial", content)
        self.assertIn("unavailable", content)

    def test_ingest_rerun_step7(self) -> None:
        """Item 3: no-evidence gate says to re-run Step 7."""
        content = " ".join(_read("ui-design/skills/ingest.md").split())
        self.assertIn("re-run Step 7", content)

    def test_ingest_legacy_embeds_not_silently_false(self) -> None:
        """Item B: absent index with inline embeds reports inconsistency."""
        content = _read("ui-design/skills/ingest.md")
        section = content.split("Screenshot inspection", 1)[1].split(
            "Provenance freshness", 1
        )[0]
        # True no-image: "None" or absent, no inline embeds -> false
        self.assertIn("HAS_SCREENSHOTS = false", section)
        # Legacy/contradictory: embeds present -> report inconsistency
        self.assertIn("inconsistency", section)
        # Limited continuation records unavailable, not false
        self.assertIn("HAS_SCREENSHOTS = unavailable", section)

    def test_ingest_write_cleanup_on_confirm(self) -> None:
        """Item 4: Step 8a defines write + cleanup for both paths."""
        content = _read("ui-design/skills/ingest.md")
        step8a = content.split("### Step 8a:", 1)[1].split("### Step 9", 1)[0]
        # Normalize whitespace for cross-line assertions
        flat = " ".join(step8a.split())
        # Confirm path: write content, delete backup and temp
        self.assertIn("write compiled content to `{CONTEXT_PATH}`", flat)
        self.assertIn("{BACKUP_PATH}", flat)
        # Decline path: discard content, delete backup and temp, preserve
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
        """Item 16: publish uses git rm for consumer manifest if tracked."""
        content = _read("ux-design/skills/publish.md")
        flat = " ".join(content.split())
        self.assertIn("`git rm` the consumer manifest", flat)

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
        """Item 9: metadata refreshes screenshot_assets after successful push."""
        content = _read("ux-design/skills/publish.md")
        # Scoped to Step 9 (Save Publish Metadata)
        step9 = content.split("Step 9: Save Publish Metadata", 1)[1].split(
            "Step 10:", 1
        )[0]
        self.assertIn("update `screenshot_storage`", step9)
        self.assertIn("replace `screenshot_assets`", step9)
        # Success-only: refresh happens after successful push
        self.assertIn("successful push", step9)
        # Failure preservation: metadata unchanged on push failure
        self.assertIn("push failed, preserve previous metadata", step9)
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

    # =================================================================
    # Finding 1: Canonical workspace paths resolved once before use
    # =================================================================

    def test_ingest_resolves_workspace_paths_once(self) -> None:
        """Finding 1: ingest defines ARTIFACT_DIR/CONTEXT_PATH/BACKUP_PATH
        once in Step 2 (unconditional), used in Step 8a."""
        content = _read("ui-design/skills/ingest.md")
        step2 = content.split("### Step 2:", 1)[1].split("### Step 2a:", 1)[0]
        # Path definitions exist in Step 2 (unconditional)
        self.assertIn("ARTIFACT_DIR", step2)
        self.assertIn("CONTEXT_PATH", step2)
        self.assertIn("BACKUP_PATH", step2)
        # Anchored to invocation dir, no hardcoded prefix
        flat2 = " ".join(step2.split())
        self.assertIn("invocation directory", flat2)
        self.assertNotIn("git rev-parse --show-toplevel", step2)
        # Retained across later cwd changes
        self.assertIn("later `cwd` changes", flat2)
        # No Git-root requirement
        self.assertIn("Git-root requirement", flat2)
        # Step 2a is now only the conditional backup
        step2a = content.split("### Step 2a:", 1)[1].split("### Step 3", 1)[0]
        self.assertNotIn("ARTIFACT_DIR", step2a)
        self.assertIn("{CONTEXT_PATH}", step2a)
        self.assertIn("{BACKUP_PATH}", step2a)
        # Step 8a uses the resolved path variables
        step8a = content.split("### Step 8a:", 1)[1].split("### Step 9", 1)[0]
        self.assertIn("{CONTEXT_PATH}", step8a)
        self.assertIn("{BACKUP_PATH}", step8a)

    # =================================================================
    # Finding 2: Every declared Screenshot Index ID accounted for
    # =================================================================

    def test_inspection_recipe_index_accounting(self) -> None:
        """Finding 2: recipe accounts for every declared index ID against
        actual embeds, records missing embeds, and prompts repair."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        flat = " ".join(content.split())
        # Has the index-accounting step
        self.assertIn("Account for every declared index ID", flat)
        # Matches via declared ref, not just ID text
        self.assertIn("declared ref", flat)
        # Missing embeds recorded as unavailable
        self.assertIn("declared in index but no matching embed found", flat)
        # Reports aggregate totals
        self.assertIn("Total declared", flat)
        self.assertIn("Embeds found", flat)
        self.assertIn("Missing embeds", flat)
        # Prompts repair or explicit authorization
        self.assertIn("repair the handoff", flat)
        self.assertIn("authorize partial", flat)
        # Never silently omits
        self.assertIn("Never silently omit", flat)

    def test_inspection_recipe_has_handoff_file_param(self) -> None:
        """Finding 2: recipe accepts HANDOFF_FILE for index reading."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        # Parameter table includes HANDOFF_FILE
        param_section = content.split("## Parameters", 1)[1].split(
            "## Procedure", 1
        )[0]
        self.assertIn("HANDOFF_FILE", param_section)

    def test_ingest_passes_handoff_file_to_recipe(self) -> None:
        """Finding 2: ingest passes HANDOFF_FILE when calling recipe."""
        content = _read("ui-design/skills/ingest.md")
        section = content.split("screenshot-inspection.md", 1)[1].split(
            "- **If none**", 1
        )[0]
        self.assertIn("HANDOFF_FILE", section)

    # =================================================================
    # Finding 3: Byte identity separate from revision-binding validity
    # =================================================================

    def test_inspection_recipe_binding_separation(self) -> None:
        """Finding 3: recipe checks revision binding separately from
        byte identity with structured matched/mismatched/unknown status."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        binding_section = content.split(
            "Check revision binding (separate from identity)", 1
        )
        self.assertEqual(
            len(binding_section), 2,
            "Missing 'separate from identity' binding section",
        )
        binding = binding_section[1].split("### 4.", 1)[0]
        flat = " ".join(binding.split())  # normalize whitespace
        # Uses actual manifest fields
        self.assertIn("context_revision", flat)
        self.assertIn("prototype_iteration", flat)
        # Records match status per binding
        self.assertIn("matched", flat)
        self.assertIn("mismatched", flat)
        self.assertIn("unknown", flat)
        # Verified SHA cannot clear binding mismatch
        self.assertIn("verified SHA", flat)
        self.assertIn("cannot clear a binding mismatch", flat)
        # Default missing to unknown, never vacuously matched
        self.assertIn("vacuously `matched`", flat)
        # Explicit per-image accept/reject prompt with persisted decision
        self.assertIn("prompt the user", flat)
        self.assertIn("per image", flat)
        self.assertIn("persist the decision", flat)
        # References eligibility rules
        self.assertIn("Eligibility", flat)

    def test_plan_citation_requires_both_identity_and_binding(self) -> None:
        """Finding 3: plan references recipe eligibility (which requires
        BOTH identity verified AND bindings matched) and does not re-inspect."""
        content = _read("ui-design/skills/plan.md")
        section = content.split(
            "If `HAS_SCREENSHOTS` is true or `partial`", 1
        )[1].split("If `HAS_SCREENSHOTS` is `deferred`", 1)[0]
        # Plan delegates to recipe §5 eligibility
        self.assertIn("eligibility", section)
        self.assertIn("Do not re-inspect", section)
        # Recipe §5 has the actual identity+binding rule
        recipe = _read("_shared/recipes/screenshot-inspection.md")
        elig = recipe.split("Eligibility and citation rules", 1)[1]
        self.assertIn("identity `verified`", elig)
        self.assertIn("bindings `matched`", elig)

    # =================================================================
    # Finding 4: Provenance gate before text extraction and inspection
    # =================================================================

    def test_ingest_provenance_before_inspection(self) -> None:
        """Finding 4: provenance check runs before screenshot inspection
        and text extraction in the handoff loading section."""
        content = _read("ui-design/skills/ingest.md")
        handoff_section = content.split("#### 5.3:", 1)[1].split(
            "#### 5.4:", 1
        )[0]
        prov_pos = handoff_section.find("Provenance freshness check")
        inspect_pos = handoff_section.find("Screenshot inspection")
        extract_pos = handoff_section.find("Extract:")
        self.assertGreater(prov_pos, -1, "Provenance check missing")
        self.assertGreater(inspect_pos, -1, "Screenshot inspection missing")
        self.assertGreater(extract_pos, -1, "Extract section missing")
        # Provenance must come before both inspection and extraction
        self.assertLess(
            prov_pos, inspect_pos,
            "Provenance check must precede screenshot inspection",
        )
        self.assertLess(
            prov_pos, extract_pos,
            "Provenance check must precede text extraction",
        )

    def test_ingest_provenance_skip_excludes_evidence(self) -> None:
        """Finding 4: if user skips provenance, handoff compiled as
        Not available, screenshots set false, evidence excluded."""
        content = _read("ui-design/skills/ingest.md")
        gate = content.split("Provenance freshness check (gate)", 1)[1].split(
            "**Screenshot inspection.**", 1
        )[0]
        flat = " ".join(gate.split())
        # Wait/skip branch: compiles Handoff as "Not available"
        self.assertIn('"Not available"', flat)
        # Sets HAS_SCREENSHOTS = false
        self.assertIn("HAS_SCREENSHOTS = false", flat)
        # Skips all remaining 5.3 work (inspection + extraction)
        self.assertIn("skip all remaining 5.3 work", flat)
        # Plan must not read skipped handoff or cite evidence
        self.assertIn("must not read a skipped handoff", flat)

    # =================================================================
    # Finding 5: Inverse text-only/authoring-manifest mismatch guard
    # =================================================================

    def test_publish_inverse_mismatch_guard(self) -> None:
        """Finding 5: publish stops when Screenshot Index says None but
        authoring manifest is nonempty, asks to reconcile."""
        content = _read("ux-design/skills/publish.md")
        step5 = content.split("### Step 5:", 1)[1].split("### Step 6:", 1)[0]
        flat5 = " ".join(step5.split())
        self.assertIn("Inverse mismatch guard", flat5)
        self.assertIn("reconcile", flat5)
        self.assertIn("before publishing", flat5)
        # Does not auto-delete
        self.assertIn("Do not automatically delete", flat5)
        # Distinguishes authoring vs published
        self.assertIn("authoring", flat5)
        self.assertIn("published", flat5)

    # =================================================================
    # Finding 6: Unconditional provenance capture in revise
    # =================================================================

    def test_revise_provenance_unconditional(self) -> None:
        """Finding 6: provenance capture is under Step 4 (unconditional),
        not inside Step 3a (conditional screenshot branch)."""
        content = _read("ux-design/skills/revise.md")
        # Provenance is NOT in Step 3a
        step3a = content.split("### Step 3a:", 1)[1].split("### Step 4:", 1)[0]
        self.assertNotIn("capture-provenance-event.md", step3a)
        # Provenance IS in Step 4
        step4 = content.split("### Step 4:", 1)[1].split("### Step 5:", 1)[0]
        self.assertIn("capture-provenance-event.md", step4)
        # Marked as unconditional
        self.assertIn("unconditional", step4)
        # Text-only revisions must also capture provenance
        self.assertIn("Text-only revisions must also capture provenance", step4)
        # Preserves recipe args
        self.assertIn("WORKFLOW=ux-design", step4)
        self.assertIn("PHASE=revise", step4)
        self.assertIn("AUTHORING_MODE=skill", step4)


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

    # --- T12: Push failure with pre-receive hook rejection ---
    def test_push_rejected_then_retry_succeeds(self) -> None:
        """F6 regression (Git execution): pre-receive hook rejects first
        push. Recipe is idempotent on retry; second push delivers the
        original commit exactly. Metadata pattern: unchanged on failure.

        Scope: documented recipe Bash blocks + manual push in disposable
        Git repos with a local bare remote. NOT live network push."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            bare = os.path.join(tmp, "remote.git")
            subprocess.run(["git", "clone", "--bare", repo, bare],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "origin", bare],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "push", "-u", "origin", "main"],
                capture_output=True, check=True,
            )
            # Point bare repo hooks at its own dir (workspace overrides
            # core.hooksPath globally; disposable test repos need their own)
            hooks_dir = os.path.join(bare, "hooks")
            subprocess.run(
                ["git", "-C", bare, "config", "core.hooksPath", hooks_dir],
                capture_output=True, check=True,
            )
            hook = os.path.join(hooks_dir, "pre-receive")
            marker = os.path.join(bare, ".reject-once")
            _w(marker, "")
            _w(hook, f'#!/bin/sh\n'
                     f'if [ -f "{marker}" ]; then rm -f "{marker}"; exit 1; fi\n'
                     f'exit 0\n')
            os.chmod(hook, 0o755)

            d = os.path.join(repo, "feat/PROJ-PF")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Push fail\n")
            _w(os.path.join(repo, "unrel-staged.txt"), "s")
            subprocess.run(["git", "-C", repo, "add", "unrel-staged.txt"],
                           capture_output=True, check=True)
            _w(os.path.join(repo, "unrel-dirty.txt"), "d")

            r1 = self._exec(repo, "feat/PROJ-PF/handoff.md", "feat/PROJ-PF",
                            msg="Handoff for push test")
            self.assertEqual(r1.returncode, 0, r1.stderr)
            expected = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()

            # First push REJECTED
            p1 = subprocess.run(
                ["git", "-C", repo, "push", "origin", "main"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(p1.returncode, 0, "First push must fail")

            # Recipe retry: no new commit
            r2 = self._exec(repo, "feat/PROJ-PF/handoff.md", "feat/PROJ-PF",
                            msg="Must NOT appear")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertEqual(
                expected,
                subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout.strip(),
                "No duplicate commit on retry",
            )

            # Second push SUCCEEDS
            p2 = subprocess.run(
                ["git", "-C", repo, "push", "origin", "main"],
                capture_output=True, text=True,
            )
            self.assertEqual(p2.returncode, 0, p2.stderr)
            remote = subprocess.run(
                ["git", "-C", bare, "rev-parse", "main"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(expected, remote, "Remote SHA must match exactly")

            # Unrelated files survive
            st = subprocess.run(
                ["git", "-C", repo, "status", "--porcelain"],
                capture_output=True, text=True,
            )
            self.assertIn("unrel-staged.txt", st.stdout)
            self.assertIn("unrel-dirty.txt", st.stdout)

    # --- T14: Staged deletion D-paths in commit diff ---
    def test_staged_deletion_appears_in_commit_diff(self) -> None:
        """commit_paths fix: git-rm staged deletions must appear in the
        commit's diff-tree with status D, not be silently dropped.

        Scope: documented recipe Bash blocks in disposable Git repos."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-SD")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# SD v1\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-sd.png"), "img-sd")
            self._exec(repo, "feat/PROJ-SD/handoff.md", "feat/PROJ-SD",
                        copied=["SS-1-sd.png"], manifest_written=True,
                        msg="Init SD test")
            # git rm image + manifest
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-SD/screenshots/SS-1-sd.png"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-SD/screenshot-manifest.json"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# SD v2\n")
            r = self._exec(repo, "feat/PROJ-SD/handoff.md", "feat/PROJ-SD",
                            removed=["SS-1-sd.png"], manifest_removed=True,
                            msg="Staged deletion commit")
            self.assertEqual(r.returncode, 0, r.stderr)
            # Assert D-paths appear in the commit diff
            show = subprocess.run(
                ["git", "-C", repo, "diff-tree", "--no-commit-id",
                 "--name-status", "-r", "HEAD"],
                capture_output=True, text=True,
            )
            self.assertIn("D\tfeat/PROJ-SD/screenshots/SS-1-sd.png",
                          show.stdout)
            self.assertIn("D\tfeat/PROJ-SD/screenshot-manifest.json",
                          show.stdout)
            self.assertIn("M\tfeat/PROJ-SD/handoff.md", show.stdout)

    # --- T15: No owned staged deletions remain after commit ---
    def test_no_owned_staged_deletions_after_commit(self) -> None:
        """commit_paths fix: after recipe commits, no owned staged
        deletions remain in the index.

        Scope: documented recipe Bash blocks in disposable Git repos."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-NS")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# NS\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-ns.png"), "ns-img")
            self._exec(repo, "feat/PROJ-NS/handoff.md", "feat/PROJ-NS",
                        copied=["SS-1-ns.png"], manifest_written=True,
                        msg="Init NS")
            # Remove image via git rm
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-NS/screenshots/SS-1-ns.png"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# NS v2\n")
            _w(os.path.join(d, "screenshot-manifest.json"), '{"v":2}')
            # Seed unrelated staged file
            _w(os.path.join(repo, "unrel.txt"), "keep")
            subprocess.run(["git", "-C", repo, "add", "unrel.txt"],
                           capture_output=True, check=True)
            r = self._exec(repo, "feat/PROJ-NS/handoff.md", "feat/PROJ-NS",
                            removed=["SS-1-ns.png"], manifest_written=True,
                            msg="Remove one")
            self.assertEqual(r.returncode, 0, r.stderr)
            # No owned deletions remain staged
            status = subprocess.run(
                ["git", "-C", repo, "status", "--porcelain"],
                capture_output=True, text=True,
            )
            # Owned deletion paths must NOT appear as staged
            for line in status.stdout.splitlines():
                if "SS-1-ns" in line:
                    self.fail(f"Owned deletion still staged: {line}")
            # Unrelated file survives in index
            self.assertIn("unrel.txt", status.stdout)

    # --- T16: Required path validation — missing handoff errors ---
    def test_missing_handoff_errors(self) -> None:
        """Required-path validation: missing handoff exits non-zero.

        Scope: documented recipe Bash blocks."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            # Do NOT create the handoff file
            r = self._exec(repo, "feat/PROJ-MH/handoff.md", "feat/PROJ-MH",
                            msg="Should fail")
            self.assertNotEqual(r.returncode, 0,
                                "Missing handoff should error")
            self.assertIn("required handoff missing", r.stderr)

    # --- T17: Required path validation — missing copied file errors ---
    def test_missing_copied_file_errors(self) -> None:
        """Required-path validation: missing copied file exits non-zero.

        Scope: documented recipe Bash blocks."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-MC")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# MC\n")
            # Do NOT create the screenshots dir or file
            r = self._exec(repo, "feat/PROJ-MC/handoff.md", "feat/PROJ-MC",
                            copied=["SS-1-missing.png"],
                            msg="Should fail on missing copy")
            self.assertNotEqual(r.returncode, 0,
                                "Missing copied file should error")
            self.assertIn("required copied file missing", r.stderr)

    # --- T18: Required path validation — written manifest missing ---
    def test_manifest_written_but_missing_errors(self) -> None:
        """Required-path validation: MANIFEST_WRITTEN=true but file absent.

        Scope: documented recipe Bash blocks."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-MM")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# MM\n")
            # Do NOT create the manifest file
            r = self._exec(repo, "feat/PROJ-MM/handoff.md", "feat/PROJ-MM",
                            manifest_written=True,
                            msg="Should fail on missing manifest")
            self.assertNotEqual(r.returncode, 0,
                                "Missing manifest should error")
            self.assertIn("MANIFEST_WRITTEN=true but manifest missing",
                          r.stderr)

    # --- T13: Changed handoff after committed removals ---
    def test_changed_handoff_after_committed_removal(self) -> None:
        """F6 regression (Git execution): after git-rm + commit, handoff
        changes. Re-running recipe with stale removal paths must not error
        on absent pathspecs; commits only the new handoff content.

        Scope: documented recipe Bash blocks in disposable Git repos."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-CR")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# CR v1\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-cr.png"), "img")
            self._exec(repo, "feat/PROJ-CR/handoff.md", "feat/PROJ-CR",
                        copied=["SS-1-cr.png"], manifest_written=True,
                        msg="Init CR test")
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-CR/screenshots/SS-1-cr.png"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-CR/screenshot-manifest.json"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# CR v2\n")
            r1 = self._exec(repo, "feat/PROJ-CR/handoff.md", "feat/PROJ-CR",
                            removed=["SS-1-cr.png"], manifest_removed=True,
                            msg="Remove + v2")
            self.assertEqual(r1.returncode, 0, r1.stderr)
            sha1 = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()

            # Change handoff again, stale removal paths
            _w(os.path.join(d, "handoff.md"), "# CR v3\n")
            r2 = self._exec(repo, "feat/PROJ-CR/handoff.md", "feat/PROJ-CR",
                            removed=["SS-1-cr.png"], manifest_removed=True,
                            msg="Retry v3")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            sha2 = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertNotEqual(sha1, sha2, "New handoff must create commit")
            show = subprocess.run(
                ["git", "-C", repo, "diff-tree", "--no-commit-id",
                 "--name-only", "-r", "HEAD"],
                capture_output=True, text=True,
            )
            self.assertIn("handoff.md", show.stdout)
            self.assertNotIn("SS-1-cr.png", show.stdout)

    # --- T10: Failed push retry — commit idempotent, push recovers ---
    def test_failed_push_retry_commit_idempotent(self) -> None:
        """Finding 6 regression (contract + Git execution): after a commit
        succeeds but push fails, re-running the recipe creates no new commit;
        a subsequent push delivers the original commit exactly.

        Scope: stages the documented recipe Bash blocks in disposable Git
        repos with a local bare remote. Does NOT exercise live network push,
        external-host round-trip, or runtime workflow invocation."""
        with tempfile.TemporaryDirectory() as tmp:
            # --- Set up local repo + bare remote ---
            repo = _setup_repo(tmp)
            bare = os.path.join(tmp, "remote.git")
            subprocess.run(["git", "clone", "--bare", repo, bare],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "origin", bare],
                capture_output=True, check=True,
            )

            # --- Prepare handoff + image files ---
            d = os.path.join(repo, "feat/PROJ-R")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# Retry test\n")
            _w(os.path.join(d, "screenshot-manifest.json"), '{"r":1}')
            _w(os.path.join(sd, "SS-1-r.png"), "img-retry")

            # --- First recipe run: creates commit ---
            r1 = self._exec(
                repo, "feat/PROJ-R/handoff.md", "feat/PROJ-R",
                copied=["SS-1-r.png"], manifest_written=True,
                msg="Add retry handoff",
            )
            self.assertEqual(r1.returncode, 0, r1.stderr)
            sha_after_commit = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()

            # --- Simulate push failure (don't push) ---
            # The commit exists locally but not on remote.

            # --- Second recipe run: must be idempotent (no new commit) ---
            r2 = self._exec(
                repo, "feat/PROJ-R/handoff.md", "feat/PROJ-R",
                copied=["SS-1-r.png"], manifest_written=True,
                msg="Should NOT appear",
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            sha_after_retry = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(
                sha_after_commit, sha_after_retry,
                "Retry created a second commit; recipe must be idempotent",
            )

            # --- Push recovers: delivers the original commit ---
            push = subprocess.run(
                ["git", "-C", repo, "push", "origin", "HEAD:refs/heads/main"],
                capture_output=True, text=True,
            )
            self.assertEqual(push.returncode, 0, push.stderr)
            remote_sha = subprocess.run(
                ["git", "-C", bare, "rev-parse", "main"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(
                sha_after_commit, remote_sha,
                "Remote HEAD must match the original commit SHA exactly",
            )

    # --- T11: git-rm idempotent on already-committed removal ---
    def test_git_rm_idempotent_after_committed_removal(self) -> None:
        """Finding 6 regression (Git execution): if a git-rm + commit ran
        but push failed, re-running the recipe with the same removed
        filenames must not error — the file is already committed as deleted.

        Scope: documented recipe Bash blocks in disposable Git repos."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-RM")
            sd = os.path.join(d, "screenshots")
            os.makedirs(sd)
            _w(os.path.join(d, "handoff.md"), "# RM test\n")
            _w(os.path.join(d, "screenshot-manifest.json"), "{}")
            _w(os.path.join(sd, "SS-1-rm.png"), "to-remove")
            # Initial commit with image
            self._exec(repo, "feat/PROJ-RM/handoff.md", "feat/PROJ-RM",
                        copied=["SS-1-rm.png"], manifest_written=True,
                        msg="Init for removal test")
            # Remove image + manifest via git rm
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-RM/screenshots/SS-1-rm.png"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "rm",
                 "feat/PROJ-RM/screenshot-manifest.json"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# Text only\n")
            # First recipe run: commits the removal
            r1 = self._exec(
                repo, "feat/PROJ-RM/handoff.md", "feat/PROJ-RM",
                removed=["SS-1-rm.png"], manifest_removed=True,
                msg="Remove all images",
            )
            self.assertEqual(r1.returncode, 0, r1.stderr)
            sha1 = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            # Seed unrelated change to verify survival
            _w(os.path.join(repo, "unrelated.txt"), "survive")

            # Second run: same removed paths, already committed.
            # Recipe must not error on absent/untracked paths.
            r2 = self._exec(
                repo, "feat/PROJ-RM/handoff.md", "feat/PROJ-RM",
                removed=["SS-1-rm.png"], manifest_removed=True,
                msg="Should not create commit",
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            sha2 = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(sha1, sha2, "No new commit on idempotent retry")
            # Unrelated file untouched
            self.assertTrue(
                os.path.exists(os.path.join(repo, "unrelated.txt")),
                "Unrelated file must survive",
            )


# ===================================================================
# Part 3: Regression contract checks for seven PR159 findings
#
# These are structural assertions on the committed instruction files.
# They verify that the documented rules are present and consistent
# but are NOT full runtime/vision proof — they check instruction text,
# not live workflow execution with real images or browsers.
# ===================================================================

class TestPR159FindingRegressions(unittest.TestCase):
    """Contract checks for the seven verified PR159 findings.

    Each test verifies that the relevant instruction file documents
    the rule or behavior the finding requires. These are structural
    assertions on committed text, not runtime execution tests."""

    # --- Finding 1 (4498704663): ID+ref one-to-one embed matching ---

    def test_f1_one_to_one_embed_matching(self) -> None:
        """§4 requires matching each ID to its own embed by both ID and
        ref, consuming each embed at most once."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        section = content.split("Account for every declared index ID", 1)[1]
        section = section.split("### 5.", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("both", flat.lower())
        self.assertIn("at most once", flat)
        self.assertIn("already consumed", flat)

    # --- Finding 2 (4498704673): Inspection gate in eligibility ---

    def test_f2_inspection_gate_required(self) -> None:
        """§5 Rule 1 requires status==inspected; inspection-not-supported
        is explicitly ineligible."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        elig = content.split("Eligibility and citation rules", 1)[1]
        flat = " ".join(elig.split())
        # Rule 1 inspection gate
        self.assertIn("Inspection gate", flat)
        self.assertIn("`inspected`", flat)
        # inspection-not-supported listed as ineligible
        self.assertIn("inspection-not-supported", flat)
        self.assertIn("ineligible", flat)

    # --- Finding 3 (4498704681): Independent identity & binding ---

    def test_f3_independent_binding_decisions(self) -> None:
        """§5 requires each binding exception to be accepted independently
        of identity, using ordered rules instead of overlapping table."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        elig = content.split("Eligibility and citation rules", 1)[1]
        flat = " ".join(elig.split())
        # Ordered rules
        self.assertIn("Rule 1", flat)
        self.assertIn("Rule 2", flat)
        self.assertIn("Rule 3", flat)
        # Independent
        self.assertIn("independent of identity", flat)
        # Each binding requires own acceptance
        self.assertIn("own explicit acceptance", flat)

    # --- Finding 4 (4498704690): Skip compiles Not available ---

    def test_f4_skip_compiles_not_available(self) -> None:
        """Provenance skip branch sets Handoff='Not available' and
        HAS_SCREENSHOTS=false, excluding skipped file from plan."""
        content = _read("ui-design/skills/ingest.md")
        gate = content.split("Provenance freshness check (gate)", 1)[1]
        gate = gate.split("**Screenshot inspection.**", 1)[0]
        flat = " ".join(gate.split())
        self.assertIn('"Not available"', flat)
        self.assertIn("HAS_SCREENSHOTS = false", flat)
        self.assertIn("must not read a skipped handoff", flat)

    # --- Finding 5 (4498704704): All-rejected citation rule ---

    def test_f5_no_eligible_images_explicit(self) -> None:
        """Plan notes 'no eligible images' when all inspected images are
        ineligible, without fabricating citations."""
        content = _read("ui-design/skills/plan.md")
        section = content.split(
            "If `HAS_SCREENSHOTS` is true or `partial`", 1
        )[1].split("If `HAS_SCREENSHOTS` is `deferred`", 1)[0]
        self.assertIn("no eligible images", section)
        self.assertIn("fabricating citations", section)
        # Self-review checklist also covers this
        checklist = content.split("### Step 5: Self-Review", 1)[1]
        self.assertIn("no eligible images", checklist)

    # --- Finding 6 (5808403059): Push retry recovery ---

    def test_f6_publish_push_on_unpushed_commits(self) -> None:
        """Publish Step 8 pushes based on unpushed commits, not just
        whether this invocation created a new commit."""
        content = _read("ux-design/skills/publish.md")
        step8 = content.split("### Step 8:", 1)[1].split("### Step 9:", 1)[0]
        flat = " ".join(step8.split())
        self.assertIn("unpushed commits", flat)
        self.assertIn("retries without re-running", flat)

    def test_f6_publish_git_rm_only_if_tracked(self) -> None:
        """Publish Step 6 only git-rm paths that are still tracked."""
        content = _read("ux-design/skills/publish.md")
        flat = " ".join(content.split())
        self.assertIn("`git rm` only paths still tracked", flat)
        self.assertIn("`git rm` only if still tracked", flat)

    def test_f6_publish_metadata_preserved_on_failure(self) -> None:
        """Publish Step 9 preserves metadata on push failure."""
        content = _read("ux-design/skills/publish.md")
        step9 = content.split("Step 9:", 1)[1].split("Step 10:", 1)[0]
        self.assertIn("push failed, preserve previous metadata", step9)

    def test_f6_respond_push_on_unpushed_commits(self) -> None:
        """Respond pushes based on unpushed commits with recovery."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("unpushed commits", flat)
        self.assertIn("retries without re-running", flat)

    def test_f6_respond_git_rm_only_if_tracked(self) -> None:
        """Respond only git-rm files still tracked."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("still tracked", flat)
        self.assertIn("already removed", flat)

    def test_f6_respond_metadata_after_push(self) -> None:
        """Respond updates metadata only after push succeeds."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("push failed, preserve previous metadata", flat)

    # --- Finding 7 (Root Step-Sequencing): Setup in Step 2 ---

    def test_f7_path_setup_unconditional_in_step2(self) -> None:
        """ARTIFACT_DIR/CONTEXT_PATH/BACKUP_PATH resolution is in Step 2
        (unconditional), not only in the conditional Step 2a."""
        content = _read("ui-design/skills/ingest.md")
        step2 = content.split("### Step 2:", 1)[1].split("### Step 2a:", 1)[0]
        step2a = content.split("### Step 2a:", 1)[1].split("### Step 3:", 1)[0]
        # Definitions in Step 2
        self.assertIn("ARTIFACT_DIR", step2)
        self.assertIn("CONTEXT_PATH", step2)
        self.assertIn("BACKUP_PATH", step2)
        # Step 2a is only the conditional backup check
        self.assertNotIn("ARTIFACT_DIR", step2a)
        self.assertIn("Prior Ingest", step2a)
        # No Git-root absolute requirement
        self.assertNotIn("git rev-parse --show-toplevel", step2)

    # --- A: Push verification: owned-commit + unexpected-ahead refusal ---

    def test_a_publish_owned_commit_verification(self) -> None:
        """A: publish verifies commit SHA before push, refuses unexpected."""
        content = _read("ux-design/skills/publish.md")
        step8 = content.split("### Step 8:", 1)[1].split("### Step 9:", 1)[0]
        flat = " ".join(step8.split())
        self.assertIn("commit SHA from Step 6", flat)
        self.assertIn("unexpected ahead commits", flat)
        self.assertIn("refuse", flat)

    def test_a_respond_owned_commit_verification(self) -> None:
        """A: respond verifies commit SHA before push, refuses unexpected."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("commit SHA from the staging recipe", flat)
        self.assertIn("unexpected ahead commits", flat)

    def test_a_publish_metadata_write_failure_recovery(self) -> None:
        """A: publish Step 9 handles push-ok + metadata-write-failure."""
        content = _read("ux-design/skills/publish.md")
        step9 = content.split("Step 9:", 1)[1].split("Step 10:", 1)[0]
        flat = " ".join(step9.split())
        self.assertIn("metadata write fails", flat)
        self.assertIn("without creating a new commit", flat)

    def test_a_respond_metadata_write_failure_recovery(self) -> None:
        """A: respond handles push-ok + metadata-write-failure."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("metadata write fails", flat)
        self.assertIn("without creating a new commit", flat)

    # --- B: Plan lead text requires eligible, not just inspected ---

    def test_b_plan_lead_requires_eligible(self) -> None:
        """B: plan Step 2 lead says 'eligible' not 'inspected' for
        screenshot citation, ensuring all-rejected produces no citations."""
        content = _read("ui-design/skills/plan.md")
        lead = content.split("### Step 2:", 1)[1].split("### Step 3:", 1)[0]
        # Lead text uses 'eligible' not 'cite inspected'
        self.assertNotIn("cite inspected screenshot", lead)
        self.assertIn("eligible screenshot", lead)
        # Checklist uses 'eligible images exist'
        checklist = content.split("### Step 5:", 1)[1].split("### Step 6:", 1)[0]
        self.assertIn("eligible images exist", checklist)
        self.assertNotIn("HAS_SCREENSHOTS` is true or partial", checklist)

    # --- C: Rule 2 fail-closed for unrecognized identity values ---

    def test_c_rule2_fail_closed(self) -> None:
        """C: Rule 2 requires identity to be one of verified/mismatched/
        unverified; any other value is ineligible (fail-closed)."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        elig = content.split("Eligibility and citation rules", 1)[1]
        r2 = elig.split("Rule 2", 1)[1].split("Rule 3", 1)[0]
        flat = " ".join(r2.split())
        # Must be verified (pass) or mismatched/unverified (need acceptance)
        self.assertIn("`verified`", flat)
        self.assertIn("`mismatched`/`unverified`", flat)
        # Any other value blocks
        self.assertIn("Any other value", flat)
        # Deferred decisions also block
        self.assertIn("deferred", flat)

    # --- D: Restored safety constraints ---

    def test_d_lfs_stop_on_missing_init(self) -> None:
        """D: publish stops when lfs selected but LFS not initialized."""
        content = _read("ux-design/skills/publish.md")
        flat = " ".join(content.split())
        self.assertIn("not initialized", flat)
        self.assertIn("do not auto-enable", flat)

    def test_d_external_immutable_urls(self) -> None:
        """D: publish requires immutable revision-bound external URLs."""
        content = _read("ux-design/skills/publish.md")
        flat = " ".join(content.split())
        self.assertIn("immutable and revision-bound", flat)
        self.assertIn("reject mutable or expiring", flat)

    def test_d_removal_path_validation(self) -> None:
        """D: publish reconcile removals validates path containment."""
        content = _read("ux-design/skills/publish.md")
        removals = content.split("Reconcile removals", 1)[1].split(
            "Publish consumer manifest", 1
        )[0]
        flat = " ".join(removals.split())
        self.assertIn("validate path inside", flat)


# ===================================================================
# Part 4: commit_paths filter and pending attempt protocol
#
# Structural contract tests verifying the recipe's commit_paths HEAD
# membership check, required-path validation, and pending attempt
# protocol documentation are present. Executable Git tests for the
# commit_paths fix are in Part 2 (T14–T18). Tests label which
# assertions are Read/Write journal contracts (instruction text
# presence) versus actual canonical Bash guard/push execution
# (disposable Git repo subprocess tests in Part 2).
# ===================================================================

class TestCommitPathsAndPendingAttempt(unittest.TestCase):
    """Contract and structural tests for commit_paths filter fix and
    pending attempt protocol."""

    # --- Commit_paths HEAD membership in recipe ---

    def test_recipe_commit_paths_head_check(self) -> None:
        """Recipe Step 3 uses HEAD:path to include staged deletions."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        block3 = content.split("### 3.", 1)[1].split("### 4.", 1)[0]
        self.assertIn('rev-parse --verify "HEAD:$p"', block3)
        self.assertIn("staged deletion, first removal", block3)

    def test_recipe_commit_paths_skip_comment(self) -> None:
        """Recipe Step 3 documents skip for already-committed deletions."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        block3 = content.split("### 3.", 1)[1].split("### 4.", 1)[0]
        self.assertIn("already-committed deletion", block3)

    def test_recipe_commit_paths_description_update(self) -> None:
        """Recipe Step 3 description mentions HEAD-based inclusion."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        desc = content.split("### 3.", 1)[1].split("```bash", 1)[0]
        flat = " ".join(desc.split())
        self.assertIn("present in HEAD but absent from the index", flat)
        self.assertIn("already-committed deletions", flat)

    # --- Required-path validation in recipe ---

    def test_recipe_required_path_validation(self) -> None:
        """Recipe Step 2 validates required paths before staging."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        block2 = content.split("### 2.", 1)[1].split("### 3.", 1)[0]
        flat = " ".join(block2.split())
        self.assertIn("required handoff missing", flat)
        self.assertIn("required copied file missing", flat)
        self.assertIn("MANIFEST_WRITTEN=true but manifest missing", flat)

    def test_recipe_step2_title_updated(self) -> None:
        """Recipe Step 2 title includes 'Validate'."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        self.assertIn("### 2. Validate and stage owned paths", content)

    # --- Pending attempt protocol ---

    def test_recipe_has_pending_attempt_section(self) -> None:
        """Recipe Step 4 documents the pending attempt protocol."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        self.assertIn("### 4. Pending attempt record (push safety)",
                      content)

    def test_pending_attempt_fields(self) -> None:
        """Pending attempt record has required fields (contract)."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Pending attempt record", 1)[1]
        for field in ("commit_sha", "branch", "expected_base",
                      "owned_paths", "pr_number", "timestamp"):
            self.assertIn(f"`{field}`", section,
                          f"pending_attempt missing field: {field}")

    def test_pending_attempt_private_state(self) -> None:
        """Pending attempt is private authoring state, not published."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Pending attempt record", 1)[1]
        flat = " ".join(section.split())
        self.assertIn("private authoring state", flat)
        self.assertIn("do not copy", flat)
        self.assertIn("consumer-facing published manifest", flat)

    def test_pending_attempt_retry_verification(self) -> None:
        """On retry: verify HEAD matches, check remote, refuse unknown."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        retry = content.split("On retry", 1)[1].split("Initial new", 1)[0]
        flat = " ".join(retry.split())
        self.assertIn("commit_sha", flat)
        self.assertIn("do not force-push", flat)
        self.assertIn("re-derive ownership", flat)
        self.assertIn("Already pushed", flat)

    def test_pending_attempt_initial_synced_base(self) -> None:
        """Initial new attempt requires known synced base."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Initial new attempt", 1)[1].split(
            "After successful push", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("known synced base", flat)

    def test_pending_attempt_finalize_after_verify(self) -> None:
        """Metadata finalized only after exact remote SHA verification."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("Verify the remote ref matches", flat)
        self.assertIn("commit_sha", flat)
        self.assertIn("Finalize metadata", flat)
        self.assertIn("Remove `pending_attempt`", flat)

    def test_pending_attempt_meta_write_failure(self) -> None:
        """Already-pushed + metadata-write failure handled."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("metadata-write failure", 1)[1].split(
            "Unexpected state", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("re-reading", flat)
        self.assertIn("Do not create a new commit", flat)

    def test_pending_attempt_unexpected_stop(self) -> None:
        """Unexpected state stops; no force-push or reset."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("**Unexpected state.**", 1)[1]
        flat = " ".join(section.split())
        self.assertIn("stop", flat)
        self.assertIn("Do not force-push", flat)

    # --- Callers reference protocol ---

    def test_publish_references_pending_attempt(self) -> None:
        """Publish Step 8 references recipe §4 pending attempt."""
        content = _read("ux-design/skills/publish.md")
        step8 = content.split("### Step 8:", 1)[1].split("### Step 9:", 1)[0]
        flat = " ".join(step8.split())
        self.assertIn("pending attempt protocol", flat)
        self.assertIn("screenshot-publish-stage.md", flat)

    def test_respond_references_pending_attempt(self) -> None:
        """Respond push section references recipe §4 pending attempt."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("pending attempt protocol", flat)
        self.assertIn("screenshot-publish-stage.md", flat)


if __name__ == "__main__":
    unittest.main()
