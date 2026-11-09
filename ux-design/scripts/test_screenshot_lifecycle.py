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
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))

# Git-local environment variables verified against
# ``git rev-parse --local-env-vars`` (Git 2.54).  Repository location
# vars may be exported by hooks into child processes; command-scope
# config vars (COUNT/KEY_n/VALUE_n and PARAMETERS) override file-based
# config values (see https://git-scm.com/docs/git-config).
# GIT_CONFIG_GLOBAL and GIT_CONFIG_NOSYSTEM are intentionally excluded:
# T19 uses them as test fixtures; they control global/system config
# scope, not local repository identity or command-scope overrides.
_GIT_LOCATION_VARS = (
    # Repository location
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR", "GIT_PREFIX",
    # Repository-specific overrides
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    # Command-scope configuration overrides
    "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG",
)
_saved_git_env: dict[str, str | None] = {}


def setUpModule():
    """Quarantine inherited Git-local vars for this test module.

    Strips all Git-local environment variables (per
    ``git rev-parse --local-env-vars``) and indexed
    GIT_CONFIG_KEY_n/VALUE_n payloads so temp fixture Git calls
    don't redirect into the caller's repository or inherit
    command-scope configuration overrides."""
    for var in _GIT_LOCATION_VARS:
        _saved_git_env[var] = os.environ.pop(var, None)
    # Also clear indexed config payloads (GIT_CONFIG_KEY_n, VALUE_n)
    for key in list(os.environ):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            _saved_git_env[key] = os.environ.pop(key)


def tearDownModule():
    """Restore original Git-local vars after all tests."""
    for var, value in _saved_git_env.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


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
    # §1–§3 staging blocks; §4+ may have reference helpers.
    assert len(blocks) >= 3, f"Expected ≥3 bash blocks in recipe, got {len(blocks)}"
    blocks = blocks[:3]

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
    subprocess.run(["git", "init", "-b", "main", repo], capture_output=True, check=True)
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
        binding = binding_section[1].split("### 5.", 1)[0]
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
        # Explicit per-image accept/reject prompt with persisted decisions
        self.assertIn("prompt the user", flat)
        self.assertIn("per image", flat)
        self.assertIn("Persist each decision", flat)
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

class _RecipeExecMixin:
    """Shared _exec helper for recipe Bash execution tests (not a TestCase)."""

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


class TestRecipeExecution(_RecipeExecMixin, unittest.TestCase):
    """Extract Bash blocks from screenshot-publish-stage.md, run them."""

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
        self.assertGreaterEqual(
            len(blocks), 3,
            f"Recipe needs ≥3 staging blocks (§1–§3), got {len(blocks)}")

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

    # --- T19: _setup_repo branch name independent of ambient config ---
    def test_setup_repo_branch_name_isolated(self) -> None:
        """Regression: _setup_repo uses git init -b main so the initial
        branch is always 'main' regardless of ambient init.defaultBranch.

        Scope: calls _setup_repo() under isolated GIT_CONFIG_GLOBAL /
        GIT_CONFIG_NOSYSTEM per variant (master, trunk, unset). Verifies
        branch is 'main' and initial push to a bare remote succeeds."""
        variants = [
            ("master", "master"),
            ("custom", "trunk"),
            ("unset", None),
        ]
        for label, default_branch in variants:
            with self.subTest(ambient=label):
                with tempfile.TemporaryDirectory() as tmp:
                    cfg = os.path.join(tmp, "gitconfig")
                    with open(cfg, "w") as f:
                        f.write("[user]\n  email = test@test\n  name = test\n")
                        if default_branch:
                            f.write(f"[init]\n  defaultBranch = {default_branch}\n")
                    env_patch = {"GIT_CONFIG_GLOBAL": cfg,
                                 "GIT_CONFIG_NOSYSTEM": "1"}
                    with patch.dict(os.environ, env_patch):
                        repo = _setup_repo(tmp)
                    # Branch must be main
                    br = subprocess.run(
                        ["git", "-C", repo, "branch", "--show-current"],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(br.stdout.strip(), "main",
                                     f"ambient={label}: branch is not main")
                    # Push to bare remote must succeed
                    bare = os.path.join(tmp, "remote.git")
                    subprocess.run(
                        ["git", "clone", "--bare", repo, bare],
                        capture_output=True, check=True,
                    )
                    subprocess.run(
                        ["git", "-C", repo, "remote", "add", "origin", bare],
                        capture_output=True, check=True,
                    )
                    push = subprocess.run(
                        ["git", "-C", repo, "push", "-u", "origin", "main"],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(push.returncode, 0,
                                     f"ambient={label}: push failed: {push.stderr}")

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
        section = section.split("### 3.", 1)[0]
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
        self.assertIn("Do not create a new commit", flat)

    def test_a_respond_metadata_write_failure_recovery(self) -> None:
        """A: respond handles push-ok + metadata-write-failure."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("metadata write fails", flat)
        self.assertIn("Do not create a new commit", flat)

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
                      "owned_paths", "pr_number", "base_branch",
                      "timestamp", "docs_repo_remote",
                      "handoff_file_path",
                      "candidate_screenshot_storage",
                      "candidate_screenshot_assets"):
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
        """On retry: verify HEAD, branch, docs_repo_remote; refuse unknown."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        retry = content.split("On retry", 1)[1].split("Initial new", 1)[0]
        flat = " ".join(retry.split())
        self.assertIn("commit_sha", flat)
        self.assertIn("docs_repo_remote", flat)
        self.assertIn("do not force-push", flat)
        self.assertIn("re-derive ownership", flat)
        self.assertIn("Already pushed", flat)

    def test_pending_attempt_initial_synced_base(self) -> None:
        """Initial new attempt resolves push destination and snapshots
        expected_base via ls-remote against validated push URL."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Initial new attempt", 1)[1].split(
            "After successful push", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("known synced base", flat)
        self.assertIn("validated push URL", flat)
        self.assertIn("exact head ref query", flat)
        self.assertNotIn("origin/{branch}", flat)

    def test_pending_attempt_finalize_after_verify(self) -> None:
        """Metadata finalized from candidate values after remote SHA verify;
        write failure retains pending_attempt for recovery."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("exact head ref query", flat)
        self.assertIn("commit_sha", flat)
        self.assertIn("candidate_screenshot_storage", flat)
        self.assertIn("candidate_screenshot_assets", flat)
        self.assertIn("Remove `pending_attempt`", flat)
        # Atomic write + retain on failure
        self.assertIn("write fails, retain", flat)

    def test_pending_attempt_meta_write_failure(self) -> None:
        """Already-pushed + metadata-write failure: finalize from candidate
        values, retain pending_attempt, never mutable authoring state."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("metadata-write failure", 1)[1].split(
            "Unexpected state", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("candidate values", flat)
        self.assertIn("committed consumer state", flat)
        self.assertIn("never from the mutable authoring manifest", flat)
        self.assertIn("Retain `pending_attempt`", flat)
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

    # --- Early call ordering (before copy/commit, not only at push) ---

    def test_publish_early_pending_check(self) -> None:
        """Publish checks pending_attempt BEFORE Step 2 (copy/commit),
        not only at Step 8 (push). Skips to push or finalization."""
        content = _read("ux-design/skills/publish.md")
        early = content.split("### Step 2:", 1)[0]
        flat = " ".join(early.split())
        self.assertIn("Pending attempt check (early)", flat)
        self.assertIn("pending_attempt", flat)
        self.assertIn("before any copy", flat.lower())
        # References §4
        self.assertIn("screenshot-publish-stage.md", flat)
        # Skips to push or finalization
        self.assertIn("Step 9", flat)
        self.assertIn("Step 8", flat)

    def test_respond_early_pending_check(self) -> None:
        """Respond checks pending_attempt in Step 1 BEFORE copy/fetch."""
        content = _read("ux-design/skills/respond.md")
        # Unconditional gate must be in Step 1
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        self.assertIn("Unconditional pending gate", step1)
        self.assertIn("screenshot-publish-stage.md", step1)
        # Must appear before the cp command in the full file
        cp_pos = content.find('cp ".artifacts/ux-design/')
        gate_pos = content.find("Unconditional pending gate")
        self.assertGreater(cp_pos, -1, "cp command not found")
        self.assertGreater(gate_pos, -1, "pending gate not found")
        self.assertLess(gate_pos, cp_pos,
                        "pending gate must precede cp command")
        # Must appear before comment fetch
        fetch_pos = content.find("$PR_COMMENTS_SCRIPT")
        self.assertGreater(fetch_pos, -1, "comment fetch not found")
        self.assertLess(gate_pos, fetch_pos,
                        "pending gate must precede comment fetch")

    # --- Committed-state wording in callers ---

    def test_publish_recovery_uses_candidate_not_authoring(self) -> None:
        """Publish metadata recovery uses candidate values, never mutable
        authoring manifest (contract)."""
        content = _read("ux-design/skills/publish.md")
        step9 = content.split("Step 9:", 1)[1].split("Step 10:", 1)[0]
        flat = " ".join(step9.split())
        self.assertIn("candidate values", flat)
        self.assertIn("never from the mutable authoring manifest", flat)
        self.assertIn("retain", flat.lower().split("write fails")[1])

    def test_respond_recovery_uses_candidate_not_authoring(self) -> None:
        """Respond metadata recovery uses candidate values, never mutable
        authoring manifest (contract)."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("candidate_screenshot_storage", flat)
        self.assertIn("candidate_screenshot_assets", flat)
        self.assertIn("never from the mutable authoring manifest", flat)


# ===================================================================
# Part 5: Focused regressions for PR159 review wave 2 (8 source gaps)
#
# Contract tests verify ordering, gating, and state rules in committed
# instruction text.  Executable Git tests verify staging-failure
# propagation via extracted recipe Bash blocks.  PR lookup contracts
# are prose/structural checks, NOT live API or runtime execution.
# ===================================================================

class TestR4InspectionOrdering(unittest.TestCase):
    """4759: ID+ref matching runs before resolution and inspection."""

    def test_id_matching_before_resolution(self) -> None:
        """§2 matches IDs to embeds before §3 resolves and §4 inspects."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        match_pos = content.find("### 2. Account for every declared index ID")
        resolve_pos = content.find("### 3. Resolve image references")
        inspect_pos = content.find("### 4. Verify identity and inspect")
        self.assertGreater(match_pos, -1, "§2 matching section missing")
        self.assertGreater(resolve_pos, -1, "§3 resolve section missing")
        self.assertGreater(inspect_pos, -1, "§4 inspect section missing")
        self.assertLess(match_pos, resolve_pos)
        self.assertLess(resolve_pos, inspect_pos)

    def test_resolve_processes_matched_pairs_only(self) -> None:
        """§3 explicitly processes matched pairs from §2."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s3 = content.split("### 3.", 1)[1].split("### 4.", 1)[0]
        self.assertIn("matched pair", s3)

    def test_unmatched_embeds_ineligible(self) -> None:
        """Embeds not corresponding to any declared ID are ineligible."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("### 2.", 1)[1].split("### 3.", 1)[0]
        self.assertIn("not eligible for inspection or citation", s2)


class TestR4BindingStatusDefaults(unittest.TestCase):
    """4770: missing/dash/invalid binding statuses default to unknown."""

    def test_binding_check_dash_defaults_unknown(self) -> None:
        """§4 binding check defaults dash and invalid to unknown."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        binding = content.split("Check revision binding", 1)[1].split(
            "### 5.", 1
        )[0]
        flat = " ".join(binding.split())
        self.assertIn("dash", flat)
        self.assertIn("invalid", flat)
        self.assertIn("unknown", flat)
        self.assertIn("unrecognizable", flat)

    def test_rule3_dash_defaults_independent(self) -> None:
        """§5 Rule 3 defaults dash/invalid to unknown; each binding
        requires independent acceptance."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        rule3 = content.split("Rule 3", 1)[1].split("**Outcome:**", 1)[0]
        flat = " ".join(rule3.split())
        self.assertIn("dash", flat)
        self.assertIn("invalid default to `unknown`", flat)
        self.assertIn("independent of the other binding", flat)


class TestR4StagingFailure(_RecipeExecMixin, unittest.TestCase):
    """4777: git add / commit failures propagate; no false 'no changes'.

    Executable Git tests using extracted recipe Bash blocks.
    Preserves: git diff exit 1 as ordinary changes; HEAD-membership
    deletion fix; unrelated index/worktree."""

    def test_git_add_ignored_file_stops(self) -> None:
        """git add on a .gitignore'd handoff path fails; recipe exits
        nonzero, HEAD unchanged, no false 'no changes' success.
        Unrelated staged and unstaged files survive."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-IGN")
            os.makedirs(d)
            _w(os.path.join(repo, ".gitignore"),
               "feat/PROJ-IGN/handoff.md\n")
            subprocess.run(
                ["git", "-C", repo, "add", ".gitignore"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "commit", "-m", "add gitignore"],
                capture_output=True, check=True,
            )
            _w(os.path.join(d, "handoff.md"), "# Ignored\n")
            # Seed unrelated staged + unstaged
            _w(os.path.join(repo, "unrel-staged.txt"), "s")
            subprocess.run(
                ["git", "-C", repo, "add", "unrel-staged.txt"],
                capture_output=True, check=True,
            )
            _w(os.path.join(repo, "unrel-dirty.txt"), "d")
            head_before = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()

            r = self._exec(
                repo, "feat/PROJ-IGN/handoff.md", "feat/PROJ-IGN",
                msg="Should not commit",
            )
            self.assertNotEqual(
                r.returncode, 0,
                "Recipe must fail when git add fails on ignored file",
            )
            # No false 'no changes' success message
            self.assertNotIn("No changes", r.stdout)
            self.assertNotIn("skipping commit", r.stdout)
            head_after = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(
                head_before, head_after,
                "HEAD must not change when staging fails",
            )
            # Unrelated files survive
            st = subprocess.run(
                ["git", "-C", repo, "status", "--porcelain"],
                capture_output=True, text=True,
            )
            self.assertIn("unrel-staged.txt", st.stdout)
            self.assertIn("unrel-dirty.txt", st.stdout)

    def test_git_add_index_lock_stops(self) -> None:
        """git add with index.lock present fails; recipe exits nonzero,
        HEAD unchanged, no false 'no changes' output.
        Unrelated staged and unstaged files survive."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-LK")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Lock test\n")
            # Seed unrelated staged + unstaged
            _w(os.path.join(repo, "unrel-staged.txt"), "s")
            subprocess.run(
                ["git", "-C", repo, "add", "unrel-staged.txt"],
                capture_output=True, check=True,
            )
            _w(os.path.join(repo, "unrel-dirty.txt"), "d")
            lock = os.path.join(repo, ".git", "index.lock")
            _w(lock, "")
            head_before = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()

            r = self._exec(
                repo, "feat/PROJ-LK/handoff.md", "feat/PROJ-LK",
                msg="Should not commit",
            )
            self.assertNotEqual(
                r.returncode, 0,
                "Recipe must fail when index is locked",
            )
            # No false 'no changes' success message
            self.assertNotIn("No changes", r.stdout)
            self.assertNotIn("skipping commit", r.stdout)
            head_after = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(
                head_before, head_after,
                "HEAD must not change when staging fails",
            )
            os.unlink(lock)
            # Unrelated files survive after lock removed
            st = subprocess.run(
                ["git", "-C", repo, "status", "--porcelain"],
                capture_output=True, text=True,
            )
            self.assertIn("unrel-staged.txt", st.stdout)
            self.assertIn("unrel-dirty.txt", st.stdout)


class TestR4RetryRemoteClassification(unittest.TestCase):
    """4785: retry classifies remote SHA before push (prose contract)."""

    def test_expected_base_and_commit_sha_classification(self) -> None:
        """Retry checks expected_base, commit_sha, and stops on
        deleted/reset/unknown (not just pushed vs not-pushed)."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        retry = content.split("On retry", 1)[1].split("Initial new", 1)[0]
        flat = " ".join(retry.split())
        self.assertIn("expected_base", flat)
        self.assertIn("commit_sha", flat)
        self.assertIn("genuine new branch", flat)
        self.assertIn("deleted", flat)
        self.assertIn("stop", flat.lower())
        self.assertIn("Do not force-push", flat)

    def test_null_base_genuine_new_only(self) -> None:
        """Null expected_base only for genuine new branch never pushed."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        retry = content.split("On retry", 1)[1].split("Initial new", 1)[0]
        flat = " ".join(retry.split())
        self.assertIn("null", flat.lower())
        self.assertIn("genuine new branch never pushed", flat)


class TestR4PRRecovery(unittest.TestCase):
    """4795: PR recovery when pr_number is null after push
    (prose contract, NOT live API execution)."""

    def test_pr_identity_required_before_metadata(self) -> None:
        """After push, PR identity must be known before writing metadata."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("PR identity", flat)
        self.assertIn("required before writing metadata", flat)

    def test_null_pr_lookup_or_create(self) -> None:
        """Null pr_number triggers lookup by head repo+branch first;
        reuses open PR or creates if none; stops on terminal."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("null", flat.lower())
        self.assertIn("all states", flat.lower())
        self.assertIn("Terminal", flat)
        self.assertIn("stop", flat.lower())

    def test_pr_lookup_uses_repo_head_base(self) -> None:
        """PR lookup uses head repo+branch first, then checks base
        on each candidate. Prose contract, NOT live API."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("docs_repo_remote", flat)
        self.assertIn("head `branch`", flat)
        self.assertIn("base_branch", flat)
        # Terminal PR inspected before any create
        terminal_pos = flat.find("Terminal")
        create_pos = flat.find("No candidate found")
        self.assertGreater(terminal_pos, -1,
                           "Terminal PR rule must be present")
        self.assertGreater(create_pos, -1,
                           "PR creation rule must be present")
        self.assertLess(terminal_pos, create_pos,
                        "Terminal PR check must precede create")

    def test_pr_recovery_preserves_draft_status(self) -> None:
        """Reusing an existing open PR preserves its draft/ready status."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("draft/ready status", flat)


class TestR4PendingBeforeMetadata(unittest.TestCase):
    """4818: publish detects pending before completed metadata checks."""

    def test_pending_precedes_completed_metadata(self) -> None:
        """Pending check runs before 'lacks its PR number' gate."""
        content = _read("ux-design/skills/publish.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        pending_pos = step1.find("Pending attempt check (early)")
        lacks_pos = step1.find("lacks its PR")
        self.assertGreater(pending_pos, -1, "Pending check missing")
        self.assertGreater(lacks_pos, -1, "Completed metadata check missing")
        self.assertLess(
            pending_pos, lacks_pos,
            "Pending must precede completed metadata validation",
        )

    def test_no_branch_mutation_before_pending(self) -> None:
        """No branch creation, pull, or file copy before pending
        validation."""
        content = _read("ux-design/skills/publish.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        pending_block = step1.split("Pending attempt check", 1)[1].split(
            "If no pending", 1
        )[0]
        flat = " ".join(pending_block.split())
        self.assertIn("no branch creation", flat)
        self.assertIn("file copy", flat)

    def test_handoff_read_after_pending_check(self) -> None:
        """Handoff read does not block pending recovery — metadata and
        pending check appear before the handoff file read."""
        content = _read("ux-design/skills/publish.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        pending_pos = step1.find("Pending attempt check (early)")
        handoff_pos = step1.find("05-handoff.md")
        self.assertGreater(pending_pos, -1, "Pending check missing")
        self.assertGreater(handoff_pos, -1, "Handoff read missing")
        self.assertLess(
            pending_pos, handoff_pos,
            "Pending check must precede handoff read",
        )

    def test_null_pr_routes_to_step8(self) -> None:
        """Already-pushed with null pr_number routes to Step 8 (create
        PR) not Step 9 (metadata only)."""
        content = _read("ux-design/skills/publish.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        flat = " ".join(step1.split())
        self.assertIn("pr_number", flat)
        self.assertIn("null", flat.lower())
        self.assertIn("Step 8", flat)
        # Distinguish known-PR route from null-PR route
        self.assertIn("PR known", flat)


class TestR4StoragePolicyDeferred(unittest.TestCase):
    """4829: storage policy kept in memory until verified push + PR."""

    def test_no_premature_persist(self) -> None:
        """Step 5 no longer says 'Store the policy in
        publish-metadata.json'."""
        content = _read("ux-design/skills/publish.md")
        step5 = content.split("### Step 5:", 1)[1].split(
            "### Step 6:", 1
        )[0]
        flat = " ".join(step5.split())
        self.assertNotIn(
            "Store the policy in `publish-metadata.json`", flat,
        )
        self.assertIn("memory", flat)

    def test_persist_after_verified_push(self) -> None:
        """Persist only after verified push and PR identity."""
        content = _read("ux-design/skills/publish.md")
        step5 = content.split("### Step 5:", 1)[1].split(
            "### Step 6:", 1
        )[0]
        flat = " ".join(step5.split())
        self.assertIn("verified push", flat)
        self.assertIn("unchanged on failure", flat)


class TestR4RespondPendingBeforeEdits(unittest.TestCase):
    """4843: respond checks pending before handoff edits/provenance."""

    def test_pending_before_handoff_update(self) -> None:
        """Step 4 references Step 1 gate; update and provenance follow."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1
        )[0]
        # Step 4 references the unconditional gate in Step 1
        gate_pos = step4.find("unconditional pending gate in Step 1")
        update_pos = step4.find("Update `.artifacts/ux-design/")
        provenance_pos = step4.find("capture-provenance-event.md")
        self.assertGreater(gate_pos, -1,
                           "Step 4 must reference Step 1 gate")
        self.assertGreater(update_pos, -1)
        self.assertGreater(provenance_pos, -1)
        self.assertLess(
            gate_pos, update_pos,
            "Gate reference must precede handoff update",
        )
        self.assertLess(
            gate_pos, provenance_pos,
            "Gate reference must precede provenance capture",
        )

    def test_no_unpublished_edit_claims(self) -> None:
        """Never post or log replies claiming unpublished edits."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1
        )[0]
        flat = " ".join(step4.split())
        self.assertIn("Never post or log replies claiming", flat)
        self.assertIn("not published", flat)


# ===================================================================
# Part 5b: R5 review regression tests
#
# Contract checks for the five inline comments + three outside-diff
# notes from PR159 review round 5.
# ===================================================================

class TestR5UnresolvedPairHandling(unittest.TestCase):
    """2393: unresolved matched pairs get full rows outside §4 loop."""

    def test_unresolved_section_before_resolved_loop(self) -> None:
        """Unresolved pair handling appears before the resolved loop."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("### 4.", 1)[1].split("### 5.", 1)[0]
        unresolved_pos = s4.find("Unresolved matched pairs")
        resolved_pos = s4.find("For each resolved matched image")
        self.assertGreater(unresolved_pos, -1,
                           "Unresolved section missing")
        self.assertGreater(resolved_pos, -1,
                           "Resolved loop missing")
        self.assertLess(unresolved_pos, resolved_pos)

    def test_unresolved_has_full_9_column_schema(self) -> None:
        """Unresolved pairs get full 9-column rows."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        section = content.split("Unresolved matched pairs", 1)[1].split(
            "For each resolved matched image", 1
        )[0]
        for field in ("id", "status", "identity", "ref", "expected_sha",
                      "observed_sha", "observation", "spec_match", "notes"):
            self.assertIn(f"`{field}`", section,
                          f"Unresolved schema missing field: {field}")

    def test_unresolved_no_fabricated_observations(self) -> None:
        """Unresolved pairs must not fabricate from caption/alt text."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        section = content.split("Unresolved matched pairs", 1)[1].split(
            "For each resolved matched image", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("not observed", flat)
        self.assertIn("fabricate", flat)

    def test_unresolved_continuation_decision(self) -> None:
        """Unresolved pairs prompt repair/wait/partial-text-only."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        section = content.split("Unresolved matched pairs", 1)[1].split(
            "For each resolved matched image", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("repair", flat)
        self.assertIn("wait", flat)
        self.assertIn("partial continuation", flat)

    def test_unresolved_never_eligible(self) -> None:
        """Unresolved status never becomes eligible even with partial."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        section = content.split("Unresolved matched pairs", 1)[1].split(
            "For each resolved matched image", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("never", flat.lower())
        self.assertIn("eligible", flat)
        self.assertIn("Rule 1", flat)

    def test_late_inspection_failure_full_handling(self) -> None:
        """§4.4 late inspection failure applies same continuation
        handling (repair/wait/partial), not just row shape."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        # Scope to the late-failure step inside resolved processing
        resolved_section = content.split(
            "For each resolved matched image", 1
        )[1].split("Check revision binding", 1)[0]
        late = resolved_section.split("Inspection failure", 1)
        self.assertEqual(len(late), 2,
                         "Late inspection failure step missing")
        late_text = late[1].split("5.", 1)[0]
        flat = " ".join(late_text.split())
        self.assertIn("continuation handling", flat)
        self.assertIn("repair", flat)
        self.assertIn("partial continuation", flat)
        self.assertIn("fabricate", flat)


class TestR5SeparateBindingDecisions(unittest.TestCase):
    """2406: §4.5 persists separate named decisions per binding."""

    def test_separate_named_decisions(self) -> None:
        """§4.5 prompts separate decisions for each binding."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        binding = content.split("Check revision binding", 1)[1].split(
            "### 5.", 1
        )[0]
        flat = " ".join(binding.split())
        self.assertIn("separate named decision", flat)
        self.assertIn("context_revision:", flat)
        self.assertIn("prototype_iteration:", flat)

    def test_both_unknown_need_explicit_each(self) -> None:
        """Both unknown when manifest absent; each needs acceptance."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        binding = content.split("Check revision binding", 1)[1].split(
            "### 5.", 1
        )[0]
        flat = " ".join(binding.split())
        self.assertIn("manifest is absent", flat)
        self.assertIn("both", flat.lower())
        self.assertIn("own explicit acceptance", flat)

    def test_aggregate_decision_not_assumed(self) -> None:
        """Ambiguous aggregate legacy decision not assumed all accepted."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        binding = content.split("Check revision binding", 1)[1].split(
            "### 5.", 1
        )[0]
        flat = " ".join(binding.split())
        self.assertIn("aggregate", flat)
        self.assertIn("must not imply all bindings accepted", flat)

    def test_fail_closed_ineligible_labels(self) -> None:
        """Missing/rejected/deferred/unprompted remain ineligible."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        binding = content.split("Check revision binding", 1)[1].split(
            "### 5.", 1
        )[0]
        flat = " ".join(binding.split())
        self.assertIn("fail-closed", flat)
        self.assertIn("rejected", flat)
        self.assertIn("deferred", flat)
        self.assertIn("unprompted", flat)
        self.assertIn("ineligible", flat)


class TestR5HeadRepoIdentity(unittest.TestCase):
    """2420: PR lookup requires full head repository identity match."""

    def test_head_repo_match_in_pr_lookup(self) -> None:
        """PR lookup verifies head repository with host-qualified identity."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("{host}/{owner}/{repo}", flat)
        self.assertIn("docs_repo_remote", flat)
        self.assertIn("different fork", flat)
        self.assertIn("not a match", flat)

    def test_head_repo_in_existing_pr_revalidation(self) -> None:
        """Existing PR revalidation checks head repository."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        # Existing PR path checks head repo and base branch
        self.assertIn("head branch, head repository, and base branch", flat)


class TestR5PrePushPRRevalidation(unittest.TestCase):
    """2430: PR state validated before push (common pre-push gate)."""

    def test_prepush_pr_gate_in_common_section(self) -> None:
        """PR revalidation is in the common pre-push gates section
        and the retry section references it."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("Pre-push gates", 1)[1].split(
            "On retry", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("PR revalidation", flat)
        self.assertIn("pr_number", flat)
        self.assertIn("open", flat.lower())
        self.assertIn("head branch", flat)
        # Retry references common gate
        retry = content.split("On retry", 1)[1].split(
            "Initial new", 1
        )[0]
        self.assertIn("pre-push gates", " ".join(retry.split()))

    def test_closed_merged_stops(self) -> None:
        """Closed/merged/retargeted PR stops without push."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("PR revalidation", 1)[1].split(
            "Owned-path verification", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("closed", flat.lower())
        self.assertIn("merged", flat.lower())
        self.assertIn("stop", flat.lower())
        self.assertIn("pending_attempt", flat)

    def test_no_atomic_guarantee_claim(self) -> None:
        """Does not claim cross-service atomic race-free guarantee."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("PR revalidation", 1)[1].split(
            "Owned-path verification", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("atomic guarantee", flat.lower())

    def test_finalization_pr_check(self) -> None:
        """After push, existing PR revalidated before metadata write."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        # Known PR path requires live state check
        self.assertIn("revalidate", flat)
        self.assertIn("stop without writing final metadata", flat)


class TestR5RespondUnconditionalGate(unittest.TestCase):
    """2444: respond pending gate unconditional in Step 1."""

    def test_gate_in_step1_before_fetch(self) -> None:
        """Unconditional pending gate in Step 1 before comment fetch."""
        content = _read("ux-design/skills/respond.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        gate_pos = step1.find("Unconditional pending gate")
        fetch_pos = step1.find("PR_COMMENTS_SCRIPT")
        self.assertGreater(gate_pos, -1,
                           "Unconditional gate missing from Step 1")
        self.assertGreater(fetch_pos, -1,
                           "Comment fetch missing from Step 1")
        self.assertLess(gate_pos, fetch_pos,
                        "Gate must precede comment fetch")

    def test_recover_and_return(self) -> None:
        """Gate recovers old attempt then returns; new feedback separate."""
        content = _read("ux-design/skills/respond.md")
        step1 = content.split("Unconditional pending gate", 1)[1].split(
            "Determine", 1
        )[0]
        flat = " ".join(step1.split())
        self.assertIn("Return after recovery", flat)
        self.assertIn("separate invocation", flat)

    def test_no_fabricated_success(self) -> None:
        """Missing prereqs → stop, no fabricated success/replies/log."""
        content = _read("ux-design/skills/respond.md")
        step1 = content.split("Unconditional pending gate", 1)[1].split(
            "Determine", 1
        )[0]
        flat = " ".join(step1.split())
        self.assertIn("do not fabricate success", flat)
        self.assertIn("post new replies", flat)

    def test_pr_creation_directed_to_publish(self) -> None:
        """PR creation recovery directed to /publish, not silently granted."""
        content = _read("ux-design/skills/respond.md")
        step1 = content.split("Unconditional pending gate", 1)[1].split(
            "Determine", 1
        )[0]
        flat = " ".join(step1.split())
        self.assertIn("/publish", flat)
        self.assertIn("outside", flat)

    def test_step4_references_step1_gate(self) -> None:
        """Step 4 references Step 1 unconditional gate."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1
        )[0]
        self.assertIn("unconditional pending gate in Step 1", step4)

    def test_gate_after_prereq_normalization(self) -> None:
        """Gate appears after docs_repo_path normalization (read-only
        prereqs) so §4 recovery has validated checkout path."""
        content = _read("ux-design/skills/respond.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        norm_pos = step1.find("Normalize")
        gate_pos = step1.find("Unconditional pending gate")
        self.assertGreater(norm_pos, -1,
                           "Path normalization missing")
        self.assertGreater(gate_pos, -1,
                           "Unconditional gate missing")
        self.assertLess(norm_pos, gate_pos,
                        "Normalization must precede pending gate")
        # Gate references the resolved path
        gate_text = step1.split("Unconditional pending gate", 1)[1]
        self.assertIn("resolved `docs_repo_path`", gate_text)


# ===================================================================
# Part 6: Git environment quarantine regression
#
# Proves that setUpModule strips inherited Git location vars so
# temp fixture Git calls don't redirect into the caller's repo.
# Uses ONLY disposable caller+target repos and sentinel files.
# ===================================================================

class TestGitEnvQuarantine(unittest.TestCase):
    """Regression: Git-local vars from caller don't leak into
    _setup_repo or _run_script temp fixture repos.

    Uses isolated child Python processes launched with a poisoned env
    (Git-local vars pointing at a disposable caller repo, plus
    command-scope config overrides).  Never touches the real checkout,
    .git dir, index, or global config."""

    def _make_caller_repo(self, tmp: str) -> tuple[str, str, str]:
        """Create a disposable caller repo with sentinel; return
        (caller_path, sentinel_path, caller_head_sha)."""
        caller = os.path.join(tmp, "caller-repo")
        os.makedirs(caller)
        subprocess.run(["git", "init", "-b", "main", caller],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", caller, "config", "user.email", "c@c"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", caller, "config", "user.name", "caller"],
                       capture_output=True, check=True)
        sentinel = os.path.join(caller, "sentinel.txt")
        _w(sentinel, "caller-sentinel")
        subprocess.run(["git", "-C", caller, "add", "sentinel.txt"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", caller, "commit", "-m", "sentinel"],
                       capture_output=True, check=True)
        head = subprocess.run(
            ["git", "-C", caller, "rev-parse", "HEAD"],
            capture_output=True, text=True).stdout.strip()
        return caller, sentinel, head

    def _poisoned_env(self, caller: str) -> dict[str, str]:
        """Build child env: scrub inherited location vars first, then
        inject ONLY owned disposable caller paths."""
        child_env: dict[str, str] = {}
        for k, v in os.environ.items():
            if k not in _GIT_LOCATION_VARS:
                child_env[k] = v
        git_dir = os.path.join(caller, ".git")
        child_env["GIT_DIR"] = git_dir
        child_env["GIT_WORK_TREE"] = caller
        child_env["GIT_INDEX_FILE"] = os.path.join(git_dir, "index")
        child_env["GIT_OBJECT_DIRECTORY"] = os.path.join(git_dir, "objects")
        child_env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = ""
        child_env["GIT_COMMON_DIR"] = git_dir
        child_env["GIT_PREFIX"] = ""
        child_env["TEST_MODULE_DIR"] = os.path.dirname(__file__)
        return child_env

    def _clean_verify_env(self) -> dict[str, str]:
        """Return env with Git location vars removed for clean checks."""
        return {k: v for k, v in os.environ.items()
                if k not in _GIT_LOCATION_VARS}

    def test_quarantine_in_poisoned_child(self) -> None:
        """Launch child Python with Git-local vars pointing at a
        disposable caller repo.  Child calls setUpModule, runs
        _setup_repo + _run_script in a temp target, calls tearDownModule,
        and returns BEFORE/AFTER diagnostics.

        Parent verifies: child exit 0, quarantine+restoration observed,
        caller HEAD/index/worktree/sentinel unchanged.

        Scope: disposable caller + temp fixture, never real checkout."""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            caller, sentinel, caller_head = self._make_caller_repo(tmp)
            child_env = self._poisoned_env(caller)

            child_script = textwrap.dedent('''\
                import json, os, sys, tempfile
                sys.path.insert(0, os.environ["TEST_MODULE_DIR"])
                import test_screenshot_lifecycle as mod

                LOC = list(mod._GIT_LOCATION_VARS)
                results = {}

                # BEFORE: observe injected vars present
                results["before"] = {v: os.environ.get(v) for v in LOC}

                mod.setUpModule()

                # AFTER SETUP: all 7 vars must be removed
                results["after_setup"] = {v: os.environ.get(v) for v in LOC}

                # Run _setup_repo + _run_script in temp target
                with tempfile.TemporaryDirectory() as t:
                    import subprocess as sp
                    repo = mod._setup_repo(t)
                    log = sp.run(["git", "-C", repo, "log", "--oneline"],
                                 capture_output=True, text=True)
                    results["target_log_rc"] = log.returncode
                    results["target_has_init"] = "init" in log.stdout
                    results["target_no_sentinel"] = "sentinel" not in log.stdout

                    r = mod._run_script("echo quarantine-proof", cwd=repo)
                    results["script_rc"] = r.returncode
                    results["script_out"] = r.stdout.strip()

                mod.tearDownModule()

                # AFTER TEARDOWN: vars must be restored to injected values
                results["after_teardown"] = {v: os.environ.get(v) for v in LOC}

                print(json.dumps(results))
            ''')

            child = subprocess.run(
                [sys.executable, "-c", child_script],
                capture_output=True, text=True, env=child_env,
                cwd=tmp,
            )
            self.assertEqual(child.returncode, 0,
                             f"Child failed:\n{child.stderr}")
            diag = json.loads(child.stdout.strip())

            # --- BEFORE: injected vars were present ---
            for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                        "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"):
                self.assertIsNotNone(
                    diag["before"][var],
                    f"{var} not injected before setup")

            # --- AFTER SETUP: all 7 cleared ---
            for var in _GIT_LOCATION_VARS:
                self.assertIsNone(
                    diag["after_setup"].get(var),
                    f"{var} not cleared by setUpModule")

            # --- Target operations succeeded independently ---
            self.assertEqual(diag["target_log_rc"], 0)
            self.assertTrue(diag["target_has_init"])
            self.assertTrue(diag["target_no_sentinel"])
            self.assertEqual(diag["script_rc"], 0)
            self.assertEqual(diag["script_out"], "quarantine-proof")

            # --- AFTER TEARDOWN: vars restored ---
            self.assertEqual(
                diag["after_teardown"]["GIT_DIR"],
                os.path.join(caller, ".git"))
            self.assertEqual(
                diag["after_teardown"]["GIT_WORK_TREE"], caller)

            # --- Caller repo untouched (clean verification env) ---
            clean = self._clean_verify_env()
            after_head = subprocess.run(
                ["git", "-C", caller, "rev-parse", "HEAD"],
                capture_output=True, text=True, env=clean,
            ).stdout.strip()
            self.assertEqual(caller_head, after_head,
                             "Caller HEAD must be unchanged")
            st = subprocess.run(
                ["git", "-C", caller, "status", "--porcelain"],
                capture_output=True, text=True, env=clean)
            self.assertEqual(st.stdout.strip(), "",
                             "Caller worktree must be clean")
            with open(sentinel) as f:
                self.assertEqual(f.read(), "caller-sentinel")

    def test_quarantine_disabled_shows_leak(self) -> None:
        """Control: child WITHOUT setUpModule observes poisoned vars
        still present in env — proves quarantine is necessary.

        Scope: read-only observation, never mutates real repo."""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            caller = os.path.join(tmp, "caller-ctrl")
            os.makedirs(caller)
            subprocess.run(["git", "init", "-b", "main", caller],
                           capture_output=True, check=True)
            child_env = self._poisoned_env(caller)

            child_script = textwrap.dedent('''\
                import json, os, sys
                sys.path.insert(0, os.environ["TEST_MODULE_DIR"])
                import test_screenshot_lifecycle as mod
                # Do NOT call setUpModule — vars must leak
                leaked = {v: os.environ.get(v) for v in mod._GIT_LOCATION_VARS}
                has_leak = leaked.get("GIT_DIR") is not None
                print(json.dumps({"leaked": leaked, "has_leak": has_leak}))
            ''')

            child = subprocess.run(
                [sys.executable, "-c", child_script],
                capture_output=True, text=True, env=child_env,
                cwd=tmp,
            )
            self.assertEqual(child.returncode, 0, child.stderr)
            diag = json.loads(child.stdout.strip())
            self.assertTrue(
                diag["has_leak"],
                "Control: GIT_DIR must leak without quarantine")

    def test_module_quarantine_strips_vars(self) -> None:
        """setUpModule removed Git-local vars from os.environ;
        verify they are absent during test execution."""
        for var in _GIT_LOCATION_VARS:
            self.assertNotIn(
                var, os.environ,
                f"{var} should be quarantined during tests")

    def test_command_scope_config_quarantined(self) -> None:
        """Regression: inherited GIT_CONFIG_COUNT/KEY_n/VALUE_n overrides
        fixture config without quarantine; with quarantine, fixture value
        applies.  Restoration verified.

        Scope: disposable caller + temp fixture; never real checkout.
        Negative control isolates location env while retaining harmless
        COUNT/KEY/VALUE to prove the override on a disposable probe.
        Positive path invokes actual module quarantine/setup/script
        and teardown."""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            caller, sentinel, caller_head = self._make_caller_repo(tmp)
            caller_name = subprocess.run(
                ["git", "-C", caller, "config", "user.name"],
                capture_output=True, text=True,
                env=self._clean_verify_env(),
            ).stdout.strip()
            child_env = self._poisoned_env(caller)
            # Inject command-scope config override
            child_env["GIT_CONFIG_COUNT"] = "1"
            child_env["GIT_CONFIG_KEY_0"] = "user.name"
            child_env["GIT_CONFIG_VALUE_0"] = "poisoned-override"

            child_script = textwrap.dedent('''\
                import json, os, sys, subprocess as sp, tempfile
                sys.path.insert(0, os.environ["TEST_MODULE_DIR"])
                import test_screenshot_lifecycle as mod

                LOC = list(mod._GIT_LOCATION_VARS)
                results = {}

                # BEFORE: record command-scope override presence
                results["before_count"] = os.environ.get("GIT_CONFIG_COUNT")
                results["before_key0"] = os.environ.get("GIT_CONFIG_KEY_0")
                results["before_val0"] = os.environ.get("GIT_CONFIG_VALUE_0")

                # Negative control: strip location vars, keep COUNT/KEY/VALUE
                # to prove override works on a disposable probe without
                # location var interference
                neg_env = dict(os.environ)
                for v in LOC:
                    neg_env.pop(v, None)
                neg_env["GIT_CONFIG_COUNT"] = "1"
                neg_env["GIT_CONFIG_KEY_0"] = "user.name"
                neg_env["GIT_CONFIG_VALUE_0"] = "poisoned-override"
                with tempfile.TemporaryDirectory() as t:
                    probe = os.path.join(t, "neg-probe")
                    os.makedirs(probe)
                    sp.run(["git", "init", "-b", "main", probe],
                           capture_output=True, check=True, env=neg_env)
                    sp.run(["git", "-C", probe, "config",
                            "user.name", "fixture-value"],
                           capture_output=True, check=True, env=neg_env)
                    name = sp.run(
                        ["git", "-C", probe, "config", "user.name"],
                        capture_output=True, text=True,
                        env=neg_env).stdout.strip()
                    results["before_name"] = name

                # Positive path: actual module quarantine
                mod.setUpModule()

                # AFTER SETUP: override cleared
                results["after_count"] = os.environ.get("GIT_CONFIG_COUNT")
                results["after_key0"] = os.environ.get("GIT_CONFIG_KEY_0")
                results["after_val0"] = os.environ.get("GIT_CONFIG_VALUE_0")

                with tempfile.TemporaryDirectory() as t:
                    repo = mod._setup_repo(t)
                    sp.run(["git", "-C", repo, "config",
                            "user.name", "fixture-value"],
                           capture_output=True, check=True)
                    name = sp.run(
                        ["git", "-C", repo, "config", "user.name"],
                        capture_output=True, text=True).stdout.strip()
                    results["after_name"] = name
                    r = mod._run_script("echo config-proof", cwd=repo)
                    results["script_rc"] = r.returncode

                mod.tearDownModule()

                # AFTER TEARDOWN: override restored
                results["restored_count"] = os.environ.get("GIT_CONFIG_COUNT")
                results["restored_key0"] = os.environ.get("GIT_CONFIG_KEY_0")
                results["restored_val0"] = os.environ.get("GIT_CONFIG_VALUE_0")

                print(json.dumps(results))
            ''')

            child = subprocess.run(
                [sys.executable, "-c", child_script],
                capture_output=True, text=True, env=child_env,
                cwd=tmp,
            )
            self.assertEqual(child.returncode, 0,
                             f"Child failed:\n{child.stderr}")
            diag = json.loads(child.stdout.strip())

            # BEFORE: override active — poisoned value overrides file config
            self.assertEqual(diag["before_count"], "1")
            self.assertEqual(diag["before_key0"], "user.name")
            self.assertEqual(diag["before_val0"], "poisoned-override")
            self.assertEqual(
                diag["before_name"], "poisoned-override",
                "COUNT/KEY/VALUE must override file config without quarantine")

            # AFTER SETUP: quarantined — fixture value applies
            self.assertIsNone(diag["after_count"])
            self.assertIsNone(diag["after_key0"])
            self.assertIsNone(diag["after_val0"])
            self.assertEqual(
                diag["after_name"], "fixture-value",
                "Fixture config must apply after quarantine")
            self.assertEqual(diag["script_rc"], 0)

            # AFTER TEARDOWN: restored
            self.assertEqual(diag["restored_count"], "1")
            self.assertEqual(diag["restored_key0"], "user.name")
            self.assertEqual(diag["restored_val0"], "poisoned-override")

            # Caller repo untouched: HEAD, status, sentinel, local config
            clean = self._clean_verify_env()
            after_head = subprocess.run(
                ["git", "-C", caller, "rev-parse", "HEAD"],
                capture_output=True, text=True, env=clean,
            ).stdout.strip()
            self.assertEqual(caller_head, after_head,
                             "Caller HEAD must be unchanged")
            st = subprocess.run(
                ["git", "-C", caller, "status", "--porcelain"],
                capture_output=True, text=True, env=clean)
            self.assertEqual(st.stdout.strip(), "",
                             "Caller worktree must be clean")
            with open(sentinel) as f:
                self.assertEqual(f.read(), "caller-sentinel")
            after_name = subprocess.run(
                ["git", "-C", caller, "config", "user.name"],
                capture_output=True, text=True, env=clean,
            ).stdout.strip()
            self.assertEqual(after_name, caller_name,
                             "Caller local config must be unchanged")


# ===================================================================
# Part 7: R6 review regressions — focused source-contract checks
#
# Structural assertions for the five inline findings + one outside-diff
# note from PR159 review round 6.
# ===================================================================

class TestR6InspectionRepairRerun(unittest.TestCase):
    """4516373704: repair/access-restored rerun replaces rows."""

    def test_s2_rerun_after_repair(self) -> None:
        """§2 instructs rerun matching for repaired embeds with
        published-input gate re-entry."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("### 2.", 1)[1].split("### 3.", 1)[0]
        flat = " ".join(s2.split())
        self.assertIn("published-input gate", flat)
        self.assertIn("no private authoring fallback", flat)
        self.assertIn("not partial authorization", flat)
        self.assertIn("replace previous", flat)
        self.assertIn("still valid", flat)
        self.assertIn("Do not append duplicate rows", flat)

    def test_s4_rerun_after_repair(self) -> None:
        """§4 instructs rerun resolution/inspection for repaired IDs
        with published-input gate re-entry and superseded decisions."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("### 4.", 1)[1].split("### 5.", 1)[0]
        flat = " ".join(s4.split())
        self.assertIn("published-input gate", flat)
        self.assertIn("Rerun §3", flat)
        self.assertIn("superseded", flat)
        self.assertIn("Replace previous unresolved rows", flat)
        self.assertIn("still valid", flat)
        self.assertIn("eligibility", flat)
        self.assertIn("Do not append duplicate rows", flat)
        self.assertIn("exactly once", flat)


class TestR6MissingFileUnavailable(unittest.TestCase):
    """4516373708: missing local file gets canonical unavailable status."""

    def test_s3_unavailable_for_missing_file(self) -> None:
        """§3 records unavailable when local file is missing."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s3 = content.split("### 3.", 1)[1].split("### 4.", 1)[0]
        flat = " ".join(s3.split())
        self.assertIn("unavailable", flat)
        self.assertIn("file not found", flat)
        # Distinct from traversal hard stop
        self.assertIn("distinct from the traversal", flat)

    def test_s4_unresolved_schema_includes_unavailable(self) -> None:
        """§4 unresolved pair status list includes unavailable."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        section = content.split("Unresolved matched pairs", 1)[1].split(
            "For each resolved matched image", 1
        )[0]
        self.assertIn("`unavailable`", section)


class TestR6LiveBaseCheck(unittest.TestCase):
    """4516373714: live base branch validated before push/finalize."""

    def test_prepush_checks_base_branch(self) -> None:
        """Pre-push PR gate includes base_branch."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("PR revalidation", 1)[1].split(
            "Owned-path verification", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("base", flat)
        self.assertIn("base_branch", flat)

    def test_retarget_stops_no_auto_revert(self) -> None:
        """Retargeted base stops push."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("PR revalidation", 1)[1].split(
            "Owned-path verification", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("retargeted", flat.lower())
        self.assertIn("stop", flat.lower())

    def test_finalization_checks_base_branch(self) -> None:
        """Post-push finalization includes base branch check."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("base branch matching", flat)
        self.assertIn("changed base", flat)


class TestR6PushDestination(unittest.TestCase):
    """4516373721: push destination resolved and validated."""

    def test_recipe_has_push_dest_validation(self) -> None:
        """Recipe §4 has push destination validation section."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        flat = " ".join(content.split())
        self.assertIn("Push destination validation", flat)
        self.assertIn("get-url --push --all", flat)
        self.assertIn("pushInsteadOf", flat)

    def test_pending_has_push_destination_field(self) -> None:
        """pending_attempt record includes host-qualified push_destination."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Pending attempt record", 1)[1]
        self.assertIn("`push_destination`", section)
        self.assertIn("{host}/{owner}/{repo}", section)

    def test_single_approved_destination(self) -> None:
        """Recipe requires exactly one push URL."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Push destination validation", 1)[1].split(
            "On retry", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("Exactly one push URL", flat)
        self.assertIn("multiple push URLs", flat)
        self.assertIn("stop", flat.lower())

    def test_ssh_https_equivalence(self) -> None:
        """SSH/HTTPS default ports are equivalent; host mismatch stops."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Push destination validation", 1)[1].split(
            "On retry", 1
        )[0]
        self.assertIn("SSH", section)
        self.assertIn("HTTPS", section)
        self.assertIn("equivalent", section)
        self.assertIn("Host mismatch", section)

    def test_no_credential_persistence(self) -> None:
        """Credential-bearing URLs must not be persisted or logged."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Push destination validation", 1)[1].split(
            "On retry", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("Credential-bearing URLs must not be persisted", flat)

    def test_retry_revalidates_push_dest(self) -> None:
        """On retry, push destination is re-resolved and revalidated."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        retry = content.split("On retry", 1)[1].split(
            "Pre-push PR", 1
        )[0]
        flat = " ".join(retry.split())
        self.assertIn("get-url --push --all", flat)
        self.assertIn("push_destination", flat)

    def test_ls_remote_queries_push_url(self) -> None:
        """Retry classification uses exact_sha from pre-push gate,
        which queries the validated push URL (not fetch URL)."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        retry = content.split("On retry", 1)[1].split("Initial new", 1)[0]
        flat = " ".join(retry.split())
        # Classification uses exact_sha from pre-push gate
        self.assertIn("exact_sha", flat)
        self.assertIn("exact head ref query", flat)
        # Push destination re-resolved before gates
        self.assertIn("get-url --push", flat)
        self.assertIn("push_destination", flat)


class TestR6PushDestinationGitProof(_RecipeExecMixin, unittest.TestCase):
    """4516373721 Git proof: fetch/push URL divergence and --push --all.

    Uses disposable bare remotes; never touches real checkout."""

    def test_fetch_vs_push_url_divergence(self) -> None:
        """Git primitive proof: after configuring split fetch/push URLs,
        a new commit pushed via origin lands only on the push URL.
        The fetch URL retains the old HEAD."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            fetch_bare = os.path.join(tmp, "fetch-remote.git")
            push_bare = os.path.join(tmp, "push-remote.git")
            subprocess.run(["git", "clone", "--bare", repo, fetch_bare],
                           capture_output=True, check=True)
            subprocess.run(["git", "clone", "--bare", repo, push_bare],
                           capture_output=True, check=True)
            old_head = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()

            # Configure origin with different fetch and push URLs
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "origin", fetch_bare],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "remote", "set-url",
                 "--push", "origin", push_bare],
                capture_output=True, check=True,
            )
            fetch_url = subprocess.run(
                ["git", "-C", repo, "remote", "get-url", "origin"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(fetch_url, fetch_bare)
            push_url = subprocess.run(
                ["git", "-C", repo, "remote", "get-url",
                 "--push", "origin"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(push_url, push_bare)

            # New commit AFTER cloning both bare remotes
            _w(os.path.join(repo, "post-clone.txt"), "diverge\n")
            subprocess.run(["git", "-C", repo, "add", "post-clone.txt"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "diverge"],
                           capture_output=True, check=True)
            new_head = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertNotEqual(old_head, new_head)

            # Push via origin
            subprocess.run(
                ["git", "-C", repo, "push", "origin", "main"],
                capture_output=True, check=True,
            )
            # Fetch bare unchanged (old HEAD)
            fetch_ref = subprocess.run(
                ["git", "-C", fetch_bare, "rev-parse", "main"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(fetch_ref, old_head,
                             "Fetch URL ref must be unchanged")
            # Push bare advanced (new HEAD)
            push_ref = subprocess.run(
                ["git", "-C", push_bare, "rev-parse", "main"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(push_ref, new_head,
                             "Push URL ref must advance to new commit")

            # ls-remote confirms: fetch=old, validated push=new
            ls_fetch = subprocess.run(
                ["git", "ls-remote", fetch_bare, "refs/heads/main"],
                capture_output=True, text=True,
            )
            self.assertIn(old_head, ls_fetch.stdout)
            ls_push = subprocess.run(
                ["git", "ls-remote", push_bare, "refs/heads/main"],
                capture_output=True, text=True,
            )
            self.assertIn(new_head, ls_push.stdout)

    def test_multiple_push_urls_all(self) -> None:
        """get-url --push --all returns all push URLs."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            bare1 = os.path.join(tmp, "remote1.git")
            bare2 = os.path.join(tmp, "remote2.git")
            subprocess.run(["git", "clone", "--bare", repo, bare1],
                           capture_output=True, check=True)
            subprocess.run(["git", "clone", "--bare", repo, bare2],
                           capture_output=True, check=True)

            subprocess.run(
                ["git", "-C", repo, "remote", "add", "origin", bare1],
                capture_output=True, check=True,
            )
            # Explicitly set initial push URL, then add second
            subprocess.run(
                ["git", "-C", repo, "remote", "set-url",
                 "--push", "origin", bare1],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "remote", "set-url",
                 "--push", "--add", "origin", bare2],
                capture_output=True, check=True,
            )

            # --push --all returns both
            result = subprocess.run(
                ["git", "-C", repo, "remote", "get-url",
                 "--push", "--all", "origin"],
                capture_output=True, text=True,
            )
            urls = result.stdout.strip().splitlines()
            self.assertGreaterEqual(
                len(urls), 2,
                "Multiple push URLs must be returned")


class TestR6UpstreamPathRecovery(unittest.TestCase):
    """4516373728: frozen upstream paths in pending for Step 9 recovery."""

    def test_pending_has_upstream_path_fields(self) -> None:
        """pending_attempt record includes upstream path fields."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Pending attempt record", 1)[1]
        self.assertIn("`upstream_prd_path`", section)
        self.assertIn("`upstream_design_path`", section)

    def test_finalization_verifies_frozen_paths(self) -> None:
        """Finalization verifies upstream paths at committed SHA."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("upstream_prd_path", flat)
        self.assertIn("upstream_design_path", flat)
        self.assertIn("commit_sha", flat)
        self.assertIn("not the mutable worktree", flat)

    def test_missing_paths_stop(self) -> None:
        """Missing or unverifiable frozen paths stop recovery."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1].split(
            "Already-pushed", 1
        )[0]
        flat = " ".join(after_push.split())
        self.assertIn("unverifiable", flat)
        self.assertIn("stop", flat.lower())
        self.assertIn("retain `pending_attempt`", flat)
        self.assertIn("do not", flat.lower())

    def test_publish_uses_frozen_paths_on_recovery(self) -> None:
        """Publish Step 1 routes recovery to use frozen pending paths."""
        content = _read("ux-design/skills/publish.md")
        step1 = content.split("### Step 1:", 1)[1].split(
            "### Step 2:", 1
        )[0]
        flat = " ".join(step1.split())
        self.assertIn("frozen upstream paths", flat)
        self.assertIn("pending_attempt", flat)

    def test_publish_step9_recovery_uses_pending(self) -> None:
        """Step 9 on recovery uses frozen path values from pending."""
        content = _read("ux-design/skills/publish.md")
        step9 = content.split("Step 9:", 1)[1].split("Step 10:", 1)[0]
        flat = " ".join(step9.split())
        self.assertIn("pending_attempt", flat)
        self.assertIn("frozen path values", flat)
        self.assertIn("commit_sha", flat)

    def test_recipe_upstream_path_freeze(self) -> None:
        """Recipe §4 has upstream path freeze validation rules."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Upstream path freeze", 1)
        self.assertEqual(len(section), 2,
                         "Missing upstream path freeze section")
        freeze = section[1].split("Push destination validation", 1)[0]
        flat = " ".join(freeze.split())
        self.assertIn("prd.md", flat)
        self.assertIn("design.md", flat)
        self.assertIn("canonical parent", flat)
        self.assertIn("handoff_file_path", flat)
        self.assertIn("commit_sha", flat)
        self.assertIn("First publication remains first publication", flat)
        self.assertIn("preserve established", flat)
        self.assertIn("do not fabricate", flat)

    def test_publish_push_dest_before_commit(self) -> None:
        """Publish Step 3 validates push destination before owned commit."""
        content = _read("ux-design/skills/publish.md")
        step3 = content.split("### Step 3:", 1)[1].split(
            "### Step 4:", 1
        )[0]
        flat = " ".join(step3.split())
        self.assertIn("push destination", flat)
        self.assertIn("screenshot-publish-stage.md", flat)
        self.assertIn("expected_base", flat)
        self.assertIn("before creating the owned commit", flat)


class TestR7IndexChecksumPrefix(unittest.TestCase):
    """4517026871: index SHA-256 prefix 3-way identity check."""

    def test_s2_collects_sha_prefixes(self) -> None:
        """§2 collects SHA-256 prefixes from the Screenshot Index."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("### 2.", 1)[1].split("### 3.", 1)[0]
        self.assertIn("SHA-256", s2)
        self.assertIn("prefix", s2)

    def test_s4_prefix_vs_manifest_and_bytes(self) -> None:
        """§4.1 compares index prefix against manifest digest (when
        present) and computed actual-bytes hash (always)."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("Index checksum prefix", 1)
        self.assertEqual(len(s4), 2, "Index checksum prefix section missing")
        block = s4[1].split("**Identity exception decision.**", 1)[0]
        flat = " ".join(block.split())
        self.assertIn("manifest digest", flat)
        self.assertIn("actual-bytes hash", flat)
        # Always compare against bytes; manifest only when present
        self.assertIn("Always compare", flat)
        self.assertIn("only when the manifest", flat)

    def test_s4_stale_prefix_identity_exception(self) -> None:
        """Stale/mismatched prefix is an identity exception."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        block = content.split("Index checksum prefix", 1)[1].split(
            "**Open and visually inspect**", 1)[0]
        flat = " ".join(block.split())
        self.assertIn("mismatched", flat)
        self.assertIn("identity exception", flat)
        self.assertIn("accepted-unverified", flat)

    def test_s4_missing_prefix_not_silent(self) -> None:
        """Missing/invalid prefix cannot be silently verified."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        block = content.split("Index checksum prefix", 1)[1].split(
            "**Open and visually inspect**", 1)[0]
        flat = " ".join(block.split())
        self.assertIn("missing", flat.lower())
        self.assertIn("silently", flat)
        self.assertIn("unverified", flat)


class TestR7PushPort(unittest.TestCase):
    """4517026884: port in push destination identity."""

    def test_canonical_form_includes_port(self) -> None:
        """push_destination format documents non-default port."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Pending attempt record", 1)[1]
        self.assertIn("non-default port", section)
        self.assertIn("{host}:{port}/{owner}/{repo}", section)

    def test_default_port_equivalence(self) -> None:
        """SSH 22 and HTTPS 443 are default and equivalent."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Push destination validation", 1)[1].split(
            "On retry", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("port 22", flat)
        self.assertIn("port 443", flat)
        self.assertIn("equivalent", flat)

    def test_nondefault_port_difference_stops(self) -> None:
        """Non-default port difference stops and retains pending."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Push destination validation", 1)[1].split(
            "On retry", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("non-default port difference", flat)
        self.assertIn("stops", flat)
        self.assertIn("pending_attempt", flat)


class TestR7NullPRLookupOrder(unittest.TestCase):
    """4517026897: null PR lookup by head repo+branch first."""

    def test_lookup_without_base_filter(self) -> None:
        """Null PR lookup searches all states by head repo+branch
        without filtering by base_branch."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("pr_number` is `null`", 1)[1].split(
            "first-publish recovery", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("all states", flat.lower())
        self.assertIn("without", flat.lower())
        self.assertIn("base_branch", flat)

    def test_retargeted_base_stops(self) -> None:
        """Retargeted base stops and retains pending for reconciliation."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("pr_number` is `null`", 1)[1].split(
            "first-publish recovery", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("Retargeted base", flat)
        self.assertIn("stop", flat.lower())
        self.assertIn("reconciliation", flat)

    def test_terminal_before_create(self) -> None:
        """Terminal PR stops before create; create only with no candidate."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("pr_number` is `null`", 1)[1].split(
            "first-publish recovery", 1)[0]
        terminal_pos = section.find("Terminal")
        create_pos = section.find("No candidate found")
        self.assertGreater(terminal_pos, -1)
        self.assertGreater(create_pos, -1)
        self.assertLess(terminal_pos, create_pos,
                        "Terminal check must precede create")

    def test_respond_directed_to_publish(self) -> None:
        """Respond limited permissions directs to /publish for creation."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("pr_number` is `null`", 1)[1].split(
            "first-publish recovery", 1)[0]
        self.assertIn("/respond", section)
        self.assertIn("/publish", section)


class TestR7RespondExplicitPush(_RecipeExecMixin, unittest.TestCase):
    """4517026897 outside: respond uses explicit remote + refspec."""

    @staticmethod
    def _push_commands_from_blocks(md_content: str) -> list[str]:
        """Extract git push command lines from all bash blocks."""
        blocks = _extract_bash_blocks(md_content)
        cmds: list[str] = []
        for block in blocks:
            for line in block.splitlines():
                stripped = line.strip()
                if stripped.startswith("git") and "push" in stripped:
                    cmds.append(stripped)
        return cmds

    def test_respond_all_push_commands_explicit(self) -> None:
        """Every git push in respond.md bash blocks uses explicit
        origin remote AND HEAD:refs/heads refspec."""
        content = _read("ux-design/skills/respond.md")
        cmds = self._push_commands_from_blocks(content)
        self.assertGreater(len(cmds), 0, "No push commands found")
        for cmd in cmds:
            self.assertIn("origin", cmd,
                          f"Push missing explicit remote: {cmd}")
            self.assertRegex(
                cmd, r'HEAD:refs/heads/',
                f"Push missing HEAD:refs/heads refspec: {cmd}")

    def test_publish_all_push_commands_explicit(self) -> None:
        """Every git push in publish.md bash blocks uses explicit
        origin remote AND HEAD:refs/heads refspec (including -u)."""
        content = _read("ux-design/skills/publish.md")
        cmds = self._push_commands_from_blocks(content)
        self.assertGreater(len(cmds), 0, "No push commands found")
        for cmd in cmds:
            self.assertIn("origin", cmd,
                          f"Push missing explicit remote: {cmd}")
            self.assertRegex(
                cmd, r'HEAD:refs/heads/',
                f"Push missing HEAD:refs/heads refspec: {cmd}")

    def test_bare_push_rejected(self) -> None:
        """Regression: bare 'git push' or branch-only push without
        explicit remote+refspec must not appear in any bash block."""
        for label, path in [
            ("respond", "ux-design/skills/respond.md"),
            ("publish", "ux-design/skills/publish.md"),
        ]:
            content = _read(path)
            blocks = _extract_bash_blocks(content)
            for i, block in enumerate(blocks):
                for line in block.splitlines():
                    stripped = line.strip()
                    if not (stripped.startswith("git") and "push" in stripped):
                        continue
                    # Must not be bare push (no args after push)
                    after_push = stripped.split("push", 1)[1].strip()
                    self.assertNotEqual(
                        after_push, "",
                        f"{label} block {i}: bare 'git push' found")
                    # Must have HEAD:refs/heads refspec
                    self.assertIn(
                        "HEAD:refs/heads/", stripped,
                        f"{label} block {i}: branch-only push: {stripped}")

    def test_respond_no_default_selection(self) -> None:
        """respond.md forbids push.default/pushRemote target selection."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("push.default", flat)
        self.assertIn("pushRemote", flat)
        self.assertIn("do not", flat.lower())

    def test_respond_revalidates_push_dest_before_push(self) -> None:
        """respond.md re-resolves push URL before pushing."""
        content = _read("ux-design/skills/respond.md")
        push_section = content.split("retries without re-running", 1)[1]
        push_section = push_section.split("Only update", 1)[0]
        flat = " ".join(push_section.split())
        self.assertIn("get-url --push --all", flat)
        self.assertIn("push_destination", flat)

    def test_misleading_push_remote_probe(self) -> None:
        """Git primitive proof: explicit push origin HEAD:refs/heads/branch
        targets the validated origin push URL, ignoring a misleading
        branch.*.pushRemote config pointing elsewhere.

        Uses disposable bare remotes; never touches real checkout."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            origin_bare = os.path.join(tmp, "origin.git")
            other_bare = os.path.join(tmp, "other.git")
            subprocess.run(["git", "clone", "--bare", repo, origin_bare],
                           capture_output=True, check=True)
            subprocess.run(["git", "clone", "--bare", repo, other_bare],
                           capture_output=True, check=True)
            old_head = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()

            # Configure origin + other remote
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "origin", origin_bare],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "other", other_bare],
                capture_output=True, check=True)
            # Set misleading pushRemote on main
            subprocess.run(
                ["git", "-C", repo, "config",
                 "branch.main.pushRemote", "other"],
                capture_output=True, check=True)

            # New commit
            _w(os.path.join(repo, "explicit.txt"), "proof\n")
            subprocess.run(["git", "-C", repo, "add", "explicit.txt"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "explicit"],
                           capture_output=True, check=True)
            new_head = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()

            # Explicit push to origin (ignores pushRemote)
            push = subprocess.run(
                ["git", "-C", repo, "push", "origin",
                 "HEAD:refs/heads/main"],
                capture_output=True, text=True)
            self.assertEqual(push.returncode, 0, push.stderr)

            # Origin advanced
            origin_ref = subprocess.run(
                ["git", "-C", origin_bare, "rev-parse", "main"],
                capture_output=True, text=True).stdout.strip()
            self.assertEqual(origin_ref, new_head,
                             "Origin must advance to new commit")

            # Other unchanged (misleading pushRemote not used)
            other_ref = subprocess.run(
                ["git", "-C", other_bare, "rev-parse", "main"],
                capture_output=True, text=True).stdout.strip()
            self.assertEqual(other_ref, old_head,
                             "Other remote must be unchanged")


class TestR7ChildInterpreter(unittest.TestCase):
    """5831473096 outside: child launches use sys.executable."""

    def test_no_hardcoded_python3_in_subprocess(self) -> None:
        """Child subprocess launches use sys.executable, not 'python3'."""
        content = _read("ux-design/scripts/test_screenshot_lifecycle.py")
        # All subprocess child launches must use sys.executable
        self.assertIn("[sys.executable,", content)
        # No subprocess.run with hardcoded python3 for child scripts
        import re as _re
        hits = _re.findall(
            r'subprocess\.run\(\s*\["python3"', content)
        self.assertEqual(len(hits), 0,
                         "subprocess.run with hardcoded python3 found")

    def test_child_interpreter_matches_parent(self) -> None:
        """Child process launched with sys.executable uses the same
        interpreter as the parent."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; print(sys.executable)"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        child_exe = result.stdout.strip()
        # Both resolve to the same real path
        self.assertEqual(
            os.path.realpath(sys.executable),
            os.path.realpath(child_exe),
            "Child interpreter must match parent")


class TestR6QuarantineExtended(unittest.TestCase):
    """5830643581: quarantine covers Git-local set, not just location."""

    def test_quarantine_includes_config_vars(self) -> None:
        """_GIT_LOCATION_VARS includes command-scope config overrides."""
        self.assertIn("GIT_CONFIG_COUNT", _GIT_LOCATION_VARS)
        self.assertIn("GIT_CONFIG_PARAMETERS", _GIT_LOCATION_VARS)
        self.assertIn("GIT_CONFIG", _GIT_LOCATION_VARS)

    def test_quarantine_includes_repo_overrides(self) -> None:
        """_GIT_LOCATION_VARS includes repository-specific overrides."""
        self.assertIn("GIT_IMPLICIT_WORK_TREE", _GIT_LOCATION_VARS)
        self.assertIn("GIT_GRAFT_FILE", _GIT_LOCATION_VARS)
        self.assertIn("GIT_NO_REPLACE_OBJECTS", _GIT_LOCATION_VARS)
        self.assertIn("GIT_REPLACE_REF_BASE", _GIT_LOCATION_VARS)
        self.assertIn("GIT_SHALLOW_FILE", _GIT_LOCATION_VARS)

    def test_quarantine_excludes_global_scope_controls(self) -> None:
        """GIT_CONFIG_GLOBAL/NOSYSTEM excluded — T19 uses as fixtures."""
        self.assertNotIn("GIT_CONFIG_GLOBAL", _GIT_LOCATION_VARS)
        self.assertNotIn("GIT_CONFIG_NOSYSTEM", _GIT_LOCATION_VARS)


# ===================================================================
# Part 8: R8 review regressions — 7 inline + 2 outside accepted fixes
#
# Contract checks for accepted prose changes and limited Git proof
# for branch collision and explicit push refspec.
# ===================================================================

class TestR8DuplicateSSNID(unittest.TestCase):
    """4517441945: detect duplicate SS-NIDs before matching."""

    def test_duplicate_id_check_before_matching(self) -> None:
        """§2 checks for duplicate IDs before matching step."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("### 2.", 1)[1].split("### 3.", 1)[0]
        dup_pos = s2.find("Duplicate ID check")
        match_pos = s2.find("Match each declared")
        self.assertGreater(dup_pos, -1, "Duplicate check missing")
        self.assertGreater(match_pos, -1, "Matching step missing")
        self.assertLess(dup_pos, match_pos)

    def test_duplicate_stops_requires_repair(self) -> None:
        """Duplicate IDs stop and require handoff repair."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("Duplicate ID check", 1)[1].split(
            "Match each declared", 1)[0]
        flat = " ".join(s2.split())
        self.assertIn("stop", flat.lower())
        self.assertIn("repair", flat)
        self.assertIn("ambiguous", flat)

    def test_distinct_ids_sharing_ref_valid(self) -> None:
        """Distinct unique IDs sharing same ref remain valid."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("Duplicate ID check", 1)[1].split(
            "Match each declared", 1)[0]
        self.assertIn("Distinct unique IDs", s2)


class TestR8ObservedSHAAlways(unittest.TestCase):
    """4517441959: always compute observed SHA from resolved bytes."""

    def test_always_compute_observed_sha(self) -> None:
        """§4.1 always computes SHA regardless of manifest."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("Verify identity", 1)[1].split(
            "Open and visually inspect", 1)[0]
        flat = " ".join(s4.split())
        self.assertIn("Always compute", flat)
        self.assertIn("regardless", flat)
        self.assertIn("observed_sha", flat)

    def test_absent_manifest_unverified(self) -> None:
        """Absent manifest → unverified, not impossible/verified."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("1. **Verify identity.**", 1)[1].split(
            "**Identity exception decision.**", 1)[0]
        flat = " ".join(s4.split())
        self.assertIn("unverified", flat)
        self.assertIn('not "impossible comparison"', flat)

    def test_absent_manifest_no_clear_prefix_mismatch(self) -> None:
        """Absent manifest must not clear stale prefix mismatch."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("Verify identity", 1)[1].split(
            "Open and visually inspect", 1)[0]
        flat = " ".join(s4.split())
        self.assertIn("must not clear", flat)
        self.assertIn("prefix mismatch", flat)


class TestR8PrefixValidation(unittest.TestCase):
    """4517441967: SHA prefix requires exactly 12 hex chars."""

    def test_exact_12_hex_required(self) -> None:
        """Index prefix must be exactly 12 hex characters."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        prefix = content.split("Index checksum prefix", 1)[1].split(
            "Open and visually inspect", 1)[0]
        flat = " ".join(prefix.split())
        self.assertIn("exactly 12", flat)
        self.assertIn("hex", flat)
        self.assertIn("{12 hex}", flat)

    def test_ellipsis_not_validated(self) -> None:
        """Trailing ellipsis not part of validated checksum."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        prefix = content.split("Index checksum prefix", 1)[1].split(
            "Open and visually inspect", 1)[0]
        flat = " ".join(prefix.split())
        self.assertIn("ellipsis", flat)
        self.assertIn("not part of the validated", flat)

    def test_malformed_prefix_rejected(self) -> None:
        """One-char/malformed/missing prefixes cannot verify."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        prefix = content.split("Index checksum prefix", 1)[1].split(
            "Open and visually inspect", 1)[0]
        flat = " ".join(prefix.split())
        self.assertIn("malformed", flat)
        self.assertIn("cannot verify", flat)

    def test_case_handled_consistently(self) -> None:
        """Prefix comparison uses consistent case (lowercase)."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        prefix = content.split("Index checksum prefix", 1)[1].split(
            "Open and visually inspect", 1)[0]
        flat = " ".join(prefix.split())
        self.assertIn("lowercase", flat)

    def test_handoff_template_sha_cell(self) -> None:
        """Handoff template SHA cell uses {12 hex}… format."""
        content = _read("ux-design/skills/handoff.md")
        self.assertIn('`{12 hex}…`', content)


class TestR8IdentityExceptionDecision(unittest.TestCase):
    """4517441974: per-image identity exception, separate from bindings."""

    def test_identity_exception_prompt(self) -> None:
        """§4.1 prompts for identity exception decision."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("Identity exception decision", 1)
        self.assertEqual(len(s4), 2, "Identity exception section missing")
        flat = " ".join(s4[1].split("2. **Open and visually inspect**", 1)[0].split())
        self.assertIn("per-image", flat)
        self.assertIn("independent from", flat)
        self.assertIn("binding decisions", flat)

    def test_one_decision_covers_all_reasons(self) -> None:
        """One identity decision covers all identity reasons."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("Identity exception decision", 1)[1].split(
            "2. **Open and visually inspect**", 1)[0]
        flat = " ".join(s4.split())
        self.assertIn("One identity decision covers all", flat)

    def test_no_new_acceptance_schema(self) -> None:
        """No new acceptance schema; 9 columns unchanged."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s4 = content.split("Identity exception decision", 1)[1].split(
            "2. **Open and visually inspect**", 1)[0]
        flat = " ".join(s4.split())
        self.assertIn("9 output columns unchanged", flat)

    def test_identity_decision_after_prefix(self) -> None:
        """Identity exception decision follows Index checksum prefix."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s41 = content.split("1. **Verify identity.**", 1)[1].split(
            "2. **Open and visually inspect**", 1)[0]
        prefix_pos = s41.find("Index checksum prefix")
        decision_pos = s41.find("Identity exception decision")
        self.assertGreater(prefix_pos, -1, "Prefix section missing")
        self.assertGreater(decision_pos, -1, "Decision section missing")
        self.assertLess(prefix_pos, decision_pos,
                        "Prefix must precede identity decision")

    def test_absent_manifest_prefix_only_observed(self) -> None:
        """Absent manifest: prefix compared against observed bytes only;
        identity stays unverified even when observed prefix matches."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        prefix = content.split("Index checksum prefix", 1)[1].split(
            "Identity exception decision", 1)[0]
        flat = " ".join(prefix.split())
        self.assertIn("Always compare", flat)
        self.assertIn("actual-bytes hash", flat)
        self.assertIn("only when the manifest", flat)
        self.assertIn("Absent manifest keeps", flat)
        self.assertIn("prefix alone cannot elevate", flat)


class TestR8BranchCollisionCheck(unittest.TestCase):
    """4517441987: new publication checks branch absence on remote."""

    def test_publish_branch_collision_check(self) -> None:
        """Publish checks feature branch absent on push URL (new pub)."""
        content = _read("ux-design/skills/publish.md")
        step3 = content.split("### Step 3:", 1)[1].split(
            "### Step 4:", 1)[0]
        flat = " ".join(step3.split())
        self.assertIn("ls-remote", flat)
        self.assertIn("collision", flat)
        self.assertIn("stop", flat.lower())

    def test_existing_update_matches_frozen_sha(self) -> None:
        """Existing approved update must match frozen remote SHA."""
        content = _read("ux-design/skills/publish.md")
        step3 = content.split("### Step 3:", 1)[1].split(
            "### Step 4:", 1)[0]
        flat = " ".join(step3.split())
        self.assertIn("frozen remote SHA", flat)

    def test_branch_collision_git_proof(self) -> None:
        """Git proof: ls-remote detects existing branch on remote."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            bare = os.path.join(tmp, "remote.git")
            subprocess.run(["git", "clone", "--bare", repo, bare],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "origin", bare],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "push", "-u", "origin", "main"],
                capture_output=True, check=True)
            # Create feature branch on remote
            subprocess.run(
                ["git", "-C", repo, "checkout", "-b", "ux/FEAT-1"],
                capture_output=True, check=True)
            _w(os.path.join(repo, "feat.txt"), "x")
            subprocess.run(["git", "-C", repo, "add", "feat.txt"],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "commit", "-m", "feat"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "push", "origin",
                 "HEAD:refs/heads/ux/FEAT-1"],
                capture_output=True, check=True)
            # ls-remote detects existing branch
            ls = subprocess.run(
                ["git", "ls-remote", "--heads", bare,
                 "refs/heads/ux/FEAT-1"],
                capture_output=True, text=True)
            self.assertIn("ux/FEAT-1", ls.stdout,
                          "ls-remote must detect existing branch")
            # ls-remote returns empty for absent branch
            ls2 = subprocess.run(
                ["git", "ls-remote", "--heads", bare,
                 "refs/heads/ux/FEAT-999"],
                capture_output=True, text=True)
            self.assertEqual(ls2.stdout.strip(), "",
                             "ls-remote must return empty for absent")


class TestR8SnapshotAfterBranch(unittest.TestCase):
    """4517442004: snapshot after branch selection, before commit."""

    def test_snapshot_after_check_ref_format(self) -> None:
        """Push dest validation appears after check-ref-format."""
        content = _read("ux-design/skills/publish.md")
        step3 = content.split("### Step 3:", 1)[1].split(
            "### Step 4:", 1)[0]
        ref_pos = step3.find("check-ref-format")
        dest_pos = step3.find("push destination")
        self.assertGreater(ref_pos, -1)
        self.assertGreater(dest_pos, -1)
        self.assertLess(ref_pos, dest_pos,
                        "Dest validation must follow check-ref-format")

    def test_snapshot_before_owned_commit(self) -> None:
        """expected_base snapshot is before owned commit."""
        content = _read("ux-design/skills/publish.md")
        step3 = content.split("### Step 3:", 1)[1].split(
            "### Step 4:", 1)[0]
        flat = " ".join(step3.split())
        self.assertIn("before creating the owned commit", flat)


class TestR8RespondPreStage(unittest.TestCase):
    """4517442013: respond prepares dest/branch/base before staging."""

    def test_prestage_before_stage_recipe(self) -> None:
        """Pre-stage validation precedes staging recipe invocation."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1)[0]
        pre_pos = step4.find("Pre-stage destination validation")
        stage_pos = step4.find("Build owned-path allowlist")
        self.assertGreater(pre_pos, -1, "Pre-stage section missing")
        self.assertGreater(stage_pos, -1, "Stage section missing")
        self.assertLess(pre_pos, stage_pos)

    def test_freezes_branch_and_push_url(self) -> None:
        """Pre-stage freezes branch, push URL, and expected_base."""
        content = _read("ux-design/skills/respond.md")
        section = content.split("Pre-stage destination validation", 1)
        self.assertEqual(len(section), 2)
        flat = " ".join(section[1].split("Build owned-path", 1)[0].split())
        self.assertIn("branch", flat)
        self.assertIn("push URL", flat)
        self.assertIn("expected_base", flat)


# ===================================================================
# Part 9: R9 review regressions — 6 concrete findings
#
# Contract tests verify the 6 findings from review round 9.
# Finding 3 includes an executable Git counterexample proving exact
# ref matching rejects tag/suffix masquerade. Tests use ONLY fake
# fixture URIs in disposable temp Git repos.
# ===================================================================

class TestR9UnmatchedBodyEmbeds(unittest.TestCase):
    """4518252787: unmatched body embeds affect aggregate status."""

    def test_recipe_reports_unmatched_embeds(self) -> None:
        """§2 reports unmatched body embeds before pixel inspection."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        s2 = content.split("### 2.", 1)[1].split("### 3.", 1)[0]
        flat = " ".join(s2.split())
        self.assertIn("Unmatched body embeds", flat)
        self.assertIn("excluded", flat)
        self.assertIn("not eligible for inspection", flat)
        self.assertIn("fabricated", flat)

    def test_recipe_has_aggregate_section(self) -> None:
        """Recipe defines aggregate status rules between §4 and §5."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        agg = content.split("### Aggregate status", 1)
        self.assertEqual(len(agg), 2, "Aggregate status section missing")
        section = agg[1].split("### 5.", 1)[0]
        flat = " ".join(section.split())
        # Three status levels defined
        self.assertIn("`inspected`", flat)
        self.assertIn("`partial`", flat)
        self.assertIn("`unavailable`", flat)
        # Excluded embeds force partial even if all declared rows inspected
        self.assertIn("even when every declared-ID row was inspected", flat)
        # Callers must not recompute
        self.assertIn("rather than recomputing", flat)

    def test_ingest_uses_recipe_aggregate(self) -> None:
        """Ingest references recipe aggregate, not recomputing."""
        content = _read("ui-design/skills/ingest.md")
        section = content.split("screenshot-inspection.md", 1)[1].split(
            "- **If none**", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("recipe's reported aggregate", flat)
        self.assertIn("recomputing", flat)


class TestR9CredentialFreePublish(unittest.TestCase):
    """4518252791: publish captures URLs privately, stores safe identity."""

    def test_publish_step2_credential_free(self) -> None:
        """Step 2 captures privately and normalizes to credential-free."""
        content = _read("ux-design/skills/publish.md")
        step2 = content.split("### Step 2:", 1)[1].split(
            "### Step 3:", 1
        )[0]
        flat = " ".join(step2.split())
        self.assertIn("privately", flat)
        self.assertIn("credential-free", flat)
        self.assertIn("do not display", flat)
        self.assertIn("{host}/{owner}/{repo}", flat)

    def test_publish_step3_no_remote_v(self) -> None:
        """Step 3 has no bare remote -v exposing raw URLs."""
        content = _read("ux-design/skills/publish.md")
        step3 = content.split("### Step 3:", 1)[1].split(
            "### Step 4:", 1
        )[0]
        self.assertNotIn("remote -v", step3)

    def test_recipe_docs_repo_remote_credential_free(self) -> None:
        """Pending record docs_repo_remote is credential-free identity."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Pending attempt record", 1)[1]
        table_end = section.split("**Upstream path freeze.**", 1)[0]
        self.assertIn("Credential-free", table_end)

    def test_publish_step2_fixture_safe(self) -> None:
        """Credential-free normalization discards userinfo from URLs.

        Uses ONLY fake fixture-user:fixture-only@example.invalid — never
        real checkout credentials."""
        import re
        # Simulate the normalization described in Step 2
        raw_urls = [
            "https://fixture-user:fixture-only@example.invalid/org/repo.git",
            "git@example.invalid:org/repo.git",
            "https://example.invalid/org/repo.git",
            "ssh://fixture-user@example.invalid:2222/org/repo.git",
        ]
        for url in raw_urls:
            # Strip userinfo (anything between :// and @, or user@ prefix)
            cleaned = re.sub(r'://[^@]+@', '://', url)
            cleaned = re.sub(r'^git@', '', cleaned)
            # Verify no fixture credentials remain in cleaned output
            self.assertNotIn("fixture-user", cleaned,
                             f"Credential leaked in {url}")
            self.assertNotIn("fixture-only", cleaned,
                             f"Password leaked in {url}")


class TestR9ExactRefMatching(_RecipeExecMixin, unittest.TestCase):
    """4518252802: exact head ref matching rejects tag/suffix masquerade.

    Executable Git proof in disposable temp bare repo."""

    def test_exact_ref_rejects_tag_masquerade(self) -> None:
        """Branch deleted, same-named tag + nested suffix remain.
        Old short query finds matches; exact ref selection finds none.

        Uses disposable temp repos; never touches real checkout."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            bare = os.path.join(tmp, "remote.git")
            subprocess.run(["git", "clone", "--bare", repo, bare],
                           capture_output=True, check=True)
            branch = "ux-design/FEAT-42"
            # Create and push the target branch
            subprocess.run(
                ["git", "-C", repo, "checkout", "-b", branch],
                capture_output=True, check=True)
            _w(os.path.join(repo, "feat.txt"), "content")
            subprocess.run(["git", "-C", repo, "add", "feat.txt"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "feat"],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "push", bare,
                 f"HEAD:refs/heads/{branch}"],
                capture_output=True, check=True)
            # Create a tag with the same name
            subprocess.run(
                ["git", "-C", bare, "update-ref",
                 f"refs/tags/{branch}", "HEAD"],
                capture_output=True, check=True)
            # Create a nested branch ending with the same suffix
            subprocess.run(
                ["git", "-C", bare, "update-ref",
                 f"refs/heads/other/{branch}", "HEAD"],
                capture_output=True, check=True)
            # Delete the target head
            subprocess.run(
                ["git", "-C", bare, "update-ref", "-d",
                 f"refs/heads/{branch}"],
                capture_output=True, check=True)

            # Old short query: ls-remote with branch pattern shows matches
            old = subprocess.run(
                ["git", "ls-remote", bare, branch],
                capture_output=True, text=True)
            self.assertNotEqual(old.stdout.strip(), "",
                                "Short query must show tag/suffix matches")

            # Exact head ref query: only refs/heads/{branch}
            exact = subprocess.run(
                ["git", "ls-remote", "--heads", bare,
                 f"refs/heads/{branch}"],
                capture_output=True, text=True)
            # Must be empty — head is deleted, tag/suffix don't qualify
            self.assertEqual(exact.stdout.strip(), "",
                             "Exact head query must find no match after "
                             "branch deletion (tag+suffix remain)")

            # Verify tag and nested branch still exist
            tags = subprocess.run(
                ["git", "ls-remote", "--tags", bare,
                 f"refs/tags/{branch}"],
                capture_output=True, text=True)
            self.assertIn(f"refs/tags/{branch}", tags.stdout)
            nested = subprocess.run(
                ["git", "ls-remote", "--heads", bare,
                 f"refs/heads/other/{branch}"],
                capture_output=True, text=True)
            self.assertIn(f"refs/heads/other/{branch}", nested.stdout)

    def test_recipe_has_exact_ref_helper(self) -> None:
        """Recipe §4 has the exact head ref query bash helper."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        flat = " ".join(content.split())
        self.assertIn("Exact head ref query", flat)
        self.assertIn("refs/heads/{branch}", flat)
        self.assertIn("tag or nested", flat)


class TestR9PrePushPathValidation(unittest.TestCase):
    """4518252804: owned paths verified at commit_sha before every push."""

    def test_recipe_has_owned_path_verification(self) -> None:
        """Pre-push gates include owned-path verification."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("Pre-push gates", 1)[1].split(
            "On retry", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("Owned-path verification", flat)
        self.assertIn("handoff_file_path", flat)
        self.assertIn("commit_sha", flat)
        self.assertIn("cat-file", flat)

    def test_path_verification_stops_on_missing(self) -> None:
        """Missing path stops; preserves pending and local commit."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Owned-path verification", 1)[1].split(
            "Exact head ref query", 1
        )[0]
        flat = " ".join(section.split())
        self.assertIn("stop", flat.lower())
        self.assertIn("preserve pending", flat.lower())
        self.assertIn("Do not automatically stage", flat)

    def test_publish_references_path_verification(self) -> None:
        """Publish Step 8 references owned-path verification."""
        content = _read("ux-design/skills/publish.md")
        step8 = content.split("### Step 8:", 1)[1].split(
            "### Step 9:", 1
        )[0]
        flat = " ".join(step8.split())
        self.assertIn("owned-path verification", flat)

    def test_path_git_counterexample(self) -> None:
        """Git proof: cat-file detects file absent from commit tree.

        Uses disposable temp Git repo; never touches real checkout."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat/PROJ-PA")
            os.makedirs(d)
            _w(os.path.join(d, "handoff.md"), "# Path test\n")
            subprocess.run(["git", "-C", repo, "add", "."],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "add"],
                           capture_output=True, check=True)
            commit = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()
            # File exists at commit — cat-file succeeds
            r1 = subprocess.run(
                ["git", "-C", repo, "cat-file", "-e",
                 f"{commit}:feat/PROJ-PA/handoff.md"],
                capture_output=True)
            self.assertEqual(r1.returncode, 0,
                             "cat-file must succeed for existing file")
            # Switch branch, remove file
            subprocess.run(
                ["git", "-C", repo, "checkout", "-b", "no-file"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "rm", "feat/PROJ-PA/handoff.md"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "commit", "-m", "remove"],
                capture_output=True, check=True)
            new_commit = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()
            # File absent from new commit — cat-file fails
            r2 = subprocess.run(
                ["git", "-C", repo, "cat-file", "-e",
                 f"{new_commit}:feat/PROJ-PA/handoff.md"],
                capture_output=True)
            self.assertNotEqual(r2.returncode, 0,
                                "cat-file must fail for removed file")


class TestR9RespondImageGate(unittest.TestCase):
    """4518252810: respond gates on image changes, not only text."""

    def test_respond_image_changes_trigger_git(self) -> None:
        """Approved image changes trigger Git even without text changes."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1
        )[0]
        flat = " ".join(step4.split())
        # Gate requires BOTH no text AND no image changes to skip
        self.assertIn("no approved screenshot", flat)
        self.assertIn("asset, manifest, reference, or digest", flat)
        # Image-only changes trigger operations
        self.assertIn("image bytes", flat.lower())
        self.assertIn("reconciliation", flat)
        self.assertIn("even when the handoff", flat)


class TestR9PRGateAllPushes(unittest.TestCase):
    """4518252820: PR revalidation before every push, not only retry."""

    def test_recipe_pr_gate_applies_all_pushes(self) -> None:
        """Pre-push gates section applies to initial and retry."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("Pre-push gates", 1)
        self.assertEqual(len(gates), 2, "Pre-push gates section missing")
        header = gates[1].split("1.", 1)[0]
        flat = " ".join(header.split())
        self.assertIn("initial and retry", flat)
        self.assertIn("every actual push", flat)

    def test_both_callers_consume_pr_gate(self) -> None:
        """Both publish and respond explicitly consume the gate."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("PR revalidation", 1)[1].split(
            "Owned-path verification", 1
        )[0]
        flat = " ".join(gates.split())
        self.assertIn("/publish", flat)
        self.assertIn("/respond", flat)
        self.assertIn("must consume", flat)

    def test_publish_references_pr_gate(self) -> None:
        """Publish Step 8 mentions pre-push PR gate."""
        content = _read("ux-design/skills/publish.md")
        step8 = content.split("### Step 8:", 1)[1].split(
            "### Step 9:", 1
        )[0]
        flat = " ".join(step8.split())
        self.assertIn("pre-push PR gate", flat)

    def test_respond_references_pr_gate(self) -> None:
        """Respond push section mentions pre-push PR gate."""
        content = _read("ux-design/skills/respond.md")
        flat = " ".join(content.split())
        self.assertIn("pre-push PR gate", flat)

    def test_initial_push_also_gated(self) -> None:
        """Initial new attempt section references pre-push gates."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        initial = content.split("Initial new attempt", 1)[1].split(
            "After successful push", 1
        )[0]
        flat = " ".join(initial.split())
        self.assertIn("pre-push gates", flat)
        self.assertIn("PR revalidation", flat)

    def test_fake_pr_state_contract(self) -> None:
        """PR gate contract: closed/merged/retargeted → stop.
        Source contract using local fake PR states (prose check,
        NOT actual PR API mutations)."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        gates = content.split("PR revalidation", 1)[1].split(
            "Owned-path verification", 1
        )[0]
        flat = " ".join(gates.split())
        # Each stop condition documented
        for state in ("closed", "merged", "retargeted", "mismatch",
                      "missing", "unavailable"):
            self.assertIn(state, flat.lower(),
                          f"PR gate missing stop on: {state}")


# ===================================================================
# Part 10: R10 finishing fixes — exact reader, path mode, normalization
#
# Executable Git tests for exact head ref reader extracted from recipe;
# ls-tree mode proof for owned-path gate; normalization fixture tests;
# respond positive branch assertion.
# ===================================================================


def _extract_exact_reader_script(
    push_url: str, branch: str, docs_repo: str = ".",
) -> str:
    """Extract the canonical exact head ref query bash block from the
    recipe and wrap it for execution with given push_url and branch.

    Returns a runnable Bash script that outputs EXACT_SHA=<value>
    on success, or exits nonzero on failure/malformed/duplicate."""
    recipe_md = _read("_shared/recipes/screenshot-publish-stage.md")
    blocks = _extract_bash_blocks(recipe_md)
    assert len(blocks) >= 4, f"Expected ≥4 bash blocks, got {len(blocks)}"
    block = blocks[3]  # 4th block: exact head ref query
    block = block.replace("{branch}", branch)
    script = (f'#!/usr/bin/env bash\nset -uo pipefail\n'
              f'push_url="{push_url}"\n'
              f'DOCS_REPO_PATH="{docs_repo}"\n')
    script += block
    script += '\necho "EXACT_SHA=$exact_sha"\n'
    return script


class TestR10ExactReaderExecution(_RecipeExecMixin, unittest.TestCase):
    """Extracted exact head ref query bash block from recipe.

    Executes the actual canonical Bash that the recipe ships, not
    hand-copied alternative Git commands. Uses disposable temp bare
    repos and fake git stubs."""

    def test_present_branch_returns_sha(self) -> None:
        """Positive case: branch exists, exact reader returns its SHA."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            bare = os.path.join(tmp, "remote.git")
            subprocess.run(["git", "clone", "--bare", repo, bare],
                           capture_output=True, check=True)
            branch = "ux-design/FEAT-100"
            subprocess.run(
                ["git", "-C", repo, "checkout", "-b", branch],
                capture_output=True, check=True)
            _w(os.path.join(repo, "x.txt"), "x")
            subprocess.run(["git", "-C", repo, "add", "x.txt"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "x"],
                           capture_output=True, check=True)
            expected = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()
            subprocess.run(
                ["git", "-C", repo, "push", bare,
                 f"HEAD:refs/heads/{branch}"],
                capture_output=True, check=True)

            script = _extract_exact_reader_script(bare, branch, repo)
            r = _run_script(script)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f"EXACT_SHA={expected}", r.stdout)

    def test_absent_branch_empty_sha(self) -> None:
        """Deleted head with tag+nested suffix: exact reader returns
        empty SHA (absent), not the tag or nested match."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            bare = os.path.join(tmp, "remote.git")
            subprocess.run(["git", "clone", "--bare", repo, bare],
                           capture_output=True, check=True)
            branch = "ux-design/FEAT-101"
            subprocess.run(
                ["git", "-C", repo, "checkout", "-b", branch],
                capture_output=True, check=True)
            _w(os.path.join(repo, "y.txt"), "y")
            subprocess.run(["git", "-C", repo, "add", "y.txt"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "y"],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", repo, "push", bare,
                 f"HEAD:refs/heads/{branch}"],
                capture_output=True, check=True)
            # Create tag + nested branch, then delete head
            subprocess.run(
                ["git", "-C", bare, "update-ref",
                 f"refs/tags/{branch}", "HEAD"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", bare, "update-ref",
                 f"refs/heads/other/{branch}", "HEAD"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", bare, "update-ref", "-d",
                 f"refs/heads/{branch}"],
                capture_output=True, check=True)

            script = _extract_exact_reader_script(bare, branch, repo)
            r = _run_script(script)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("EXACT_SHA=\n", r.stdout,
                          "Absent branch must produce empty exact_sha")

    def test_failed_query_exits_nonzero(self) -> None:
        """Failed ls-remote exits nonzero, never reaches EXACT_SHA.

        Uses a local failing git stub to prove the canonical reader
        propagates nonzero and never falls through to push/absence."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = os.path.join(tmp, "fake-bin")
            os.makedirs(fake_dir)
            fake_git = os.path.join(fake_dir, "git")
            _w(fake_git, '#!/bin/sh\nexit 128\n')
            os.chmod(fake_git, 0o755)

            script = _extract_exact_reader_script("/dev/null", "test")
            script = f'export PATH="{fake_dir}:$PATH"\n' + script
            r = _run_script(script)
            self.assertNotEqual(r.returncode, 0,
                                "Failed ls-remote must exit nonzero")
            self.assertIn("ls-remote query failed", r.stderr)
            self.assertNotIn("EXACT_SHA", r.stdout,
                             "Must not reach EXACT_SHA after failure")

    def test_malformed_sha_rejected(self) -> None:
        """Malformed SHA in ls-remote output causes nonzero exit."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = os.path.join(tmp, "fake-bin")
            os.makedirs(fake_dir)
            fake_git = os.path.join(fake_dir, "git")
            _w(fake_git,
               '#!/bin/sh\nprintf "ZZZNOTASHA\\trefs/heads/test\\n"\n')
            os.chmod(fake_git, 0o755)

            script = _extract_exact_reader_script("/dev/null", "test")
            script = f'export PATH="{fake_dir}:$PATH"\n' + script
            r = _run_script(script)
            self.assertNotEqual(r.returncode, 0,
                                "Malformed SHA must cause failure")
            self.assertIn("malformed SHA", r.stderr)

    def test_duplicate_ref_rejected(self) -> None:
        """Duplicate ref lines in ls-remote output cause nonzero exit."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = os.path.join(tmp, "fake-bin")
            os.makedirs(fake_dir)
            fake_git = os.path.join(fake_dir, "git")
            sha = "a" * 40
            _w(fake_git,
               f'#!/bin/sh\nprintf "{sha}\\trefs/heads/test\\n'
               f'{sha}\\trefs/heads/test\\n"\n')
            os.chmod(fake_git, 0o755)

            script = _extract_exact_reader_script("/dev/null", "test")
            script = f'export PATH="{fake_dir}:$PATH"\n' + script
            r = _run_script(script)
            self.assertNotEqual(r.returncode, 0,
                                "Duplicate ref must cause failure")
            self.assertIn("duplicate ref", r.stderr)


class TestR10OwnedPathModeCheck(unittest.TestCase):
    """Owned-path verification uses ls-tree mode, not just cat-file -e.

    Executable Git proof in disposable temp repos."""

    def test_catfile_accepts_symlink_lstree_rejects(self) -> None:
        """cat-file -e accepts symlink; ls-tree shows mode 120000."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _setup_repo(tmp)
            d = os.path.join(repo, "feat")
            os.makedirs(d)
            _w(os.path.join(d, "real.md"), "content")
            os.symlink("real.md", os.path.join(d, "link.md"))
            subprocess.run(["git", "-C", repo, "add", "."],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "link"],
                           capture_output=True, check=True)
            sha = subprocess.run(
                ["git", "-C", repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()

            # cat-file -e succeeds for both — insufficient
            for p in ("feat/real.md", "feat/link.md"):
                r = subprocess.run(
                    ["git", "-C", repo, "cat-file", "-e", f"{sha}:{p}"],
                    capture_output=True)
                self.assertEqual(r.returncode, 0,
                                 f"cat-file -e accepts {p}")

            # ls-tree distinguishes: regular=100644, symlink=120000
            t1 = subprocess.run(
                ["git", "-C", repo, "ls-tree", sha, "--", "feat/real.md"],
                capture_output=True, text=True)
            self.assertIn("100644", t1.stdout)
            t2 = subprocess.run(
                ["git", "-C", repo, "ls-tree", sha, "--", "feat/link.md"],
                capture_output=True, text=True)
            self.assertIn("120000", t2.stdout)
            self.assertNotIn("100644", t2.stdout)

    def test_recipe_uses_lstree_not_catfile(self) -> None:
        """Recipe §4 owned-path verification uses ls-tree mode check."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Owned-path verification", 1)[1].split(
            "Exact head ref query", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("ls-tree", flat)
        self.assertIn("100644", flat)
        self.assertIn("100755", flat)
        self.assertIn("120000", flat)
        self.assertIn("cat-file -e` alone is insufficient", flat)


class TestR10SecurityNormalization(unittest.TestCase):
    """Both actual and legacy config values normalized before comparison.

    Source contract checks + fixture tests with FAKE URIs only."""

    def test_recipe_normalizes_both_sides(self) -> None:
        """Recipe push dest validation normalizes both push URL and
        docs_repo_remote before comparing."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        section = content.split("Push destination validation", 1)[1].split(
            "On retry", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("Normalize", flat)
        self.assertIn("docs_repo_remote", flat)
        self.assertIn("legacy", flat)
        self.assertIn("userinfo", flat)
        self.assertIn("query", flat)
        self.assertIn("fragment", flat)

    def test_publish_normalizes_both_sides(self) -> None:
        """Publish Step 2 normalizes both captured URL and existing
        config value before comparing."""
        content = _read("ux-design/skills/publish.md")
        step2 = content.split("### Step 2:", 1)[1].split(
            "### Step 3:", 1)[0]
        flat = " ".join(step2.split())
        self.assertIn("Normalize both", flat)
        self.assertIn("userinfo", flat)
        self.assertIn("query", flat)
        self.assertIn("fragment", flat)

    def test_normalization_strips_credentials_query_fragment(self) -> None:
        """Fixture: normalization strips userinfo, query, fragment from
        FAKE URIs — never reads real checkout credentials."""
        import re as _re
        cases = [
            ("https://u:p@host.invalid/org/repo.git?tok=x#ref",
             "host.invalid/org/repo"),
            ("ssh://deploy@host.invalid:2222/org/repo.git",
             "host.invalid:2222/org/repo"),
            ("https://host.invalid/org/repo.git",
             "host.invalid/org/repo"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                cleaned = _re.sub(r'://[^@]+@', '://', raw)
                cleaned = _re.sub(r'[?#].*$', '', cleaned)
                m = _re.search(
                    r'://([^/]+)/([^/]+)/([^/.]+)', cleaned)
                identity = (f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
                            if m else "fail")
                self.assertEqual(identity, expected)
                self.assertNotIn("u:p", identity)
                self.assertNotIn("tok", identity)

    def test_normalization_retains_nondefault_port(self) -> None:
        """Non-default port preserved in canonical identity."""
        import re as _re
        raw = "ssh://deploy@host.invalid:2222/org/repo.git"
        cleaned = _re.sub(r'://[^@]+@', '://', raw)
        cleaned = _re.sub(r'[?#].*$', '', cleaned)
        m = _re.search(r'://([^/]+)/([^/]+)/([^/.]+)', cleaned)
        self.assertIsNotNone(m)
        identity = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        self.assertIn("2222", identity)


class TestR10RespondPositiveBranch(unittest.TestCase):
    """Respond positive branch covers both text and image-only changes."""

    def test_positive_branch_includes_image_changes(self) -> None:
        """Positive branch explicitly includes image-only trigger."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1)[0]
        positive = step4.split("handoff text changed OR", 1)
        self.assertEqual(len(positive), 2,
                         "Positive branch must include text OR image")
        header = positive[1].split(":**", 1)[0]
        flat = " ".join(header.split())
        self.assertIn("screenshot", flat)
        self.assertIn("asset", flat)
        self.assertIn("digest", flat)

    def test_skip_branch_requires_neither(self) -> None:
        """Skip branch requires no text AND no image changes."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1)[0]
        skip = step4.split("Handoff change needed: No", 1)
        self.assertEqual(len(skip), 2, "Skip branch must be present")
        flat = " ".join(skip[1].split(":**", 1)[0].split())
        self.assertIn("no approved screenshot", flat)


# ===================================================================
# Part 7: R10 review wave 2 — 6 verified flow fixes
#
# One test per finding.  Structural contract tests verify instruction
# text; executable tests use disposable Git repos.  No live API,
# network, or runtime workflow execution.
# ===================================================================


class TestR10Wave2Fixes(unittest.TestCase):
    """Contract and regression tests for the 6 R10 wave-2 findings."""

    # --- F1 (4518863303): inspected aggregate requires ≥1 declared ID ---

    def test_f1_inspected_requires_at_least_one_declared(self) -> None:
        """Aggregate `inspected` requires at least one declared ID;
        zero declared IDs cannot vacuously satisfy 'every'."""
        content = _read("_shared/recipes/screenshot-inspection.md")
        agg = content.split("Aggregate status", 1)[1].split(
            "### 5.", 1)[0]
        inspected_def = agg.split("**`inspected`**", 1)[1].split(
            "**`partial`**", 1)[0]
        flat = " ".join(inspected_def.split())
        self.assertIn("at least one declared ID exists", flat)
        # unavailable already covers the N=0 case
        unavail = agg.split("**`unavailable`**", 1)[1]
        self.assertIn("no declared ID", unavail)

    # --- F2 (4518863309): Git -C context for docs repo operations ---

    def test_f2_recipe_git_commands_use_docs_repo_context(self) -> None:
        """§4 Git commands (get-url, ls-tree, ls-remote) run in docs
        repo context via -C, not caller CWD."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        s4 = content.split("### 4.", 1)[1]
        flat = " ".join(s4.split())
        # Push dest uses -C
        self.assertIn(
            'git -C "{DOCS_REPO_PATH}" remote get-url --push --all', flat)
        # Owned-path verify uses -C
        self.assertIn(
            'git -C "{DOCS_REPO_PATH}" ls-tree', flat)
        # Canonical reader uses -C
        self.assertIn(
            'git -C "$DOCS_REPO_PATH" ls-remote', flat)
        # DOCS_REPO_PATH availability note in §4 preamble
        preamble = s4.split("**Before push.**")[0]
        self.assertIn("DOCS_REPO_PATH", preamble)

    def test_f2_canonical_reader_two_repo_regression(self) -> None:
        """Extracted canonical reader runs from SourceRepo CWD but
        queries DocsRepo remote via -C, returning DocsRepo result.
        Negative control: stripping -C makes it resolve the wrong repo."""
        with tempfile.TemporaryDirectory() as tmp:
            # --- Set up DocsRepo with a bare remote ---
            docs_repo = os.path.join(tmp, "docs-repo")
            os.makedirs(docs_repo)
            subprocess.run(
                ["git", "init", "-b", "main", docs_repo],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", docs_repo, "config", "user.email", "t@t"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", docs_repo, "config", "user.name", "t"],
                capture_output=True, check=True)
            _w(os.path.join(docs_repo, "doc.md"), "# Doc\n")
            subprocess.run(
                ["git", "-C", docs_repo, "add", "doc.md"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", docs_repo, "commit", "-m", "init doc"],
                capture_output=True, check=True)
            docs_bare = os.path.join(tmp, "docs-remote.git")
            subprocess.run(
                ["git", "clone", "--bare", docs_repo, docs_bare],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", docs_repo, "remote", "add", "origin",
                 docs_bare],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", docs_repo, "push", "-u", "origin", "main"],
                capture_output=True, check=True)
            docs_sha = subprocess.run(
                ["git", "-C", docs_repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()

            # --- Set up SourceRepo with a DIFFERENT bare remote ---
            src_repo = os.path.join(tmp, "source-repo")
            os.makedirs(src_repo)
            subprocess.run(
                ["git", "init", "-b", "main", src_repo],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", src_repo, "config", "user.email", "t@t"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", src_repo, "config", "user.name", "t"],
                capture_output=True, check=True)
            _w(os.path.join(src_repo, "src.py"), "pass\n")
            subprocess.run(
                ["git", "-C", src_repo, "add", "src.py"],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", src_repo, "commit", "-m", "init src"],
                capture_output=True, check=True)
            src_bare = os.path.join(tmp, "source-remote.git")
            subprocess.run(
                ["git", "clone", "--bare", src_repo, src_bare],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", src_repo, "remote", "add", "origin",
                 src_bare],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", src_repo, "push", "-u", "origin", "main"],
                capture_output=True, check=True)
            src_sha = subprocess.run(
                ["git", "-C", src_repo, "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip()
            self.assertNotEqual(docs_sha, src_sha,
                                "Test requires distinct SHAs")

            # Use url.*.insteadOf mapping so -C context matters:
            # same fake URL resolves to different bare repos per CWD
            fake_url = "fake://repo.example.com/"
            subprocess.run(
                ["git", "-C", docs_repo, "config",
                 f"url.{docs_bare}/.insteadOf", fake_url],
                capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", src_repo, "config",
                 f"url.{src_bare}/.insteadOf", fake_url],
                capture_output=True, check=True)

            # Positive: extracted reader with -C targets DocsRepo
            script = _extract_exact_reader_script(
                fake_url, "main", docs_repo)
            r = _run_script(script, cwd=src_repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f"EXACT_SHA={docs_sha}", r.stdout,
                          "Reader must return DocsRepo SHA via -C")

            # Negative control: strip -C so CWD (SourceRepo) context
            # resolves fake URL to src_bare — returns src SHA
            no_c_script = script.replace(
                'git -C "$DOCS_REPO_PATH" ls-remote',
                'git ls-remote')
            nr = _run_script(no_c_script, cwd=src_repo)
            self.assertEqual(nr.returncode, 0, nr.stderr)
            self.assertIn(f"EXACT_SHA={src_sha}", nr.stdout,
                          "Without -C, must resolve to SourceRepo SHA")
            self.assertNotIn(
                f"EXACT_SHA={docs_sha}", nr.stdout,
                "Without -C, reader must not return DocsRepo SHA")

    # --- F3 (4518863315): host preservation in PR lookup ---

    def test_f3_pr_lookup_preserves_host(self) -> None:
        """Recipe §4 PR lookup derives [HOST/]OWNER/REPO preserving
        non-default host from docs_repo_remote."""
        content = _read("_shared/recipes/screenshot-publish-stage.md")
        after_push = content.split("After successful push", 1)[1]
        pr_section = after_push.split("No candidate found", 1)[0]
        flat = " ".join(pr_section.split())
        self.assertIn("[HOST/]OWNER/REPO", flat)
        self.assertIn("preserving non-default host", flat)
        self.assertIn("docs_repo_remote", flat)

    # --- F3b: respond fetch/reply commands use GH_HOST/GH_REPO prefix ---

    def test_f3b_respond_fetch_reply_scoped_host(self) -> None:
        """Respond fetch and reply commands prefix GH_HOST/GH_REPO so
        the helper's gh calls target the frozen docs repo host."""
        content = _read("ux-design/skills/respond.md")
        blocks = _extract_bash_blocks(content)
        # Derive instructions present
        self.assertIn("repo_host", content)
        self.assertIn("repo_identifier", content)
        # fetch block (block 1) has GH_HOST prefix
        fetch_block = blocks[1]
        self.assertIn('GH_HOST="{repo_host}"', fetch_block)
        self.assertIn('GH_REPO="{repo_identifier}"', fetch_block)
        self.assertIn("fetch --owner", fetch_block)
        # reply blocks (11, 12) have GH_HOST prefix
        for idx in (11, 12):
            reply_block = blocks[idx]
            self.assertIn('GH_HOST="{repo_host}"', reply_block,
                          f"Block {idx} missing GH_HOST prefix")
            self.assertIn('GH_REPO="{repo_identifier}"', reply_block,
                          f"Block {idx} missing GH_REPO prefix")
        # log block (13) does NOT call gh — no prefix needed
        log_block = blocks[13]
        self.assertNotIn("GH_HOST", log_block)

    # --- F4 (4518863322): ingest template excluded embeds/continuation ---

    def test_f4_ingest_template_excluded_and_continuation(self) -> None:
        """Screenshot Observations template has Excluded embeds and
        Continuation slots outside the 9-column table rows."""
        content = _read("ui-design/skills/ingest.md")
        section = content.split("### Screenshot Observations", 1)[1].split(
            "### Feasibility", 1)[0]
        # Metadata lines exist outside the table
        self.assertIn("**Excluded embeds:**", section)
        self.assertIn("**Continuation:**", section)
        # They appear before the table header
        excl_pos = section.find("**Excluded embeds:**")
        table_pos = section.find("| ID |")
        self.assertGreater(table_pos, excl_pos,
                           "Excluded embeds must precede table")
        # 9-column table header preserved
        self.assertIn(
            "| ID | Status | Identity | Ref | Expected SHA "
            "| Observed SHA | Observation | Spec Match | Notes |",
            section)
        # Token budget respected
        est = len(content) // 4
        self.assertLess(est, 6000, f"ingest ~{est} tokens >= 6000")

    # --- F5 (4518863333): respond mkdir -p before screenshot cp ---

    def test_f5_respond_mkdir_before_copy(self) -> None:
        """Respond creates screenshots directory before copying first
        image into a text-only docs repo.  Extracts the actual bash
        block from respond.md rather than hand-copying commands."""
        with tempfile.TemporaryDirectory() as tmp:
            # Set up a source repo CWD with curated artifacts
            src_repo = os.path.join(tmp, "source-repo")
            os.makedirs(src_repo)
            issue_key = "PROJ-MK"
            art_dir = os.path.join(
                src_repo, f".artifacts/ux-design/{issue_key}/screenshots")
            os.makedirs(art_dir)
            fixture = os.path.join(art_dir, "SS-1-new.png")
            _w(fixture, "fixture-image-bytes")

            # Set up a text-only docs repo (no screenshots dir)
            docs_repo = _setup_repo(tmp)
            handoff_dir_rel = f"feat/{issue_key}"
            handoff_abs = os.path.join(docs_repo, handoff_dir_rel)
            os.makedirs(handoff_abs)
            _w(os.path.join(handoff_abs, "handoff.md"), "# Text\n")

            # Extract actual bash block 9 from respond.md (mkdir + cp)
            respond_md = _read("ux-design/skills/respond.md")
            blocks = _extract_bash_blocks(respond_md)
            copy_block = blocks[9]  # mkdir -p + cp block
            # Instantiate placeholders
            copy_block = copy_block.replace(
                "{docs_repo_path}", docs_repo)
            copy_block = copy_block.replace(
                "{handoff_dir}", handoff_dir_rel)
            copy_block = copy_block.replace(
                "{issue-key}", issue_key)
            copy_block = copy_block.replace(
                "{filename}", "SS-1-new.png")
            script = f"#!/usr/bin/env bash\nset -euo pipefail\n{copy_block}"

            # Positive: extracted script creates dir and copies
            r = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True,
                cwd=src_repo,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            dest = os.path.join(
                handoff_abs, "screenshots", "SS-1-new.png")
            self.assertTrue(os.path.isfile(dest), "Image not copied")
            with open(dest) as f:
                self.assertEqual(f.read(), "fixture-image-bytes")

            # Negative control: without mkdir -p, cp fails on fresh dest
            handoff_abs2 = os.path.join(docs_repo, "feat/PROJ-NEG")
            os.makedirs(handoff_abs2)
            no_mkdir = copy_block.replace(
                f'mkdir -p "{docs_repo}', f'# mkdir -p "{docs_repo}')
            no_mkdir = no_mkdir.replace(handoff_dir_rel, "feat/PROJ-NEG")
            neg_script = (
                f"#!/usr/bin/env bash\nset -euo pipefail\n{no_mkdir}")
            nr = subprocess.run(
                ["bash", "-c", neg_script],
                capture_output=True, text=True,
                cwd=src_repo,
            )
            self.assertNotEqual(
                nr.returncode, 0,
                "Without mkdir -p, cp into missing dir must fail")

    # --- F6 (4518863345): NO predicate includes reference changes ---

    def test_f6_no_predicate_includes_reference(self) -> None:
        """Respond negative (comment-only) header requires no approved
        reference changes, complementing the positive branch."""
        content = _read("ux-design/skills/respond.md")
        step4 = content.split("### Step 4:", 1)[1].split(
            "### Step 5:", 1)[0]
        # Find the negative header (not whole-file keyword)
        neg = step4.split("Handoff change needed: No", 1)
        self.assertEqual(len(neg), 2, "Negative header missing")
        neg_header = neg[1].split(":**", 1)[0]
        flat = " ".join(neg_header.split())
        self.assertIn("reference", flat,
                       "Negative predicate must exclude reference changes")
        # Positive header still lists references
        pos = step4.split("handoff text changed OR", 1)
        self.assertEqual(len(pos), 2, "Positive header missing")
        pos_header = pos[1].split(":**", 1)[0]
        self.assertIn("ref", " ".join(pos_header.split()))


if __name__ == "__main__":
    unittest.main()
