#!/usr/bin/env python3
"""Tests for the docs-handoff evidence helper.

All fixtures use synthetic .example/.invalid data — no real Jira
instances, private product keys, or personal identifiers.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

# Resolve the script under test relative to this file so the tests
# work regardless of whether the skill is installed via symlink or
# run from the repo checkout.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

import evidence  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_docs_snapshot(
    *,
    key: str = "TEST-100",
    summary: str = "[DOCS] Widget configuration reference",
    description: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Build a minimal valid DOCS issue snapshot."""
    if description is None:
        description = textwrap.dedent("""\
            ## User Story

            **As a** fleet administrator,
            **I want to** understand widget configuration options,
            **So that** I can configure widgets correctly.

            ## Acceptance Criteria

            - [ ] Reader can identify all configuration fields
            - [ ] Reader can follow a worked example

            ## Documentation Scope

            This feature introduces new widget configuration CLI commands.

            ## Documentation Inputs

            **TEST-201 -- Add widget config command:**
            - New `widget config set` CLI command with `--name` and `--value` flags
            - Config validation error messages and recovery steps

            **TEST-202 -- Widget status endpoint:**
            - New `/api/v1/widgets/status` GET endpoint response fields
            - Status values: `active`, `degraded`, `offline` [Assumption]

            ## Dependencies

            TEST-300

            ## Design Reference

            Design document: https://github.example.invalid/org/docs/pull/42
            Epic: TEST-50
            PRD Requirements: FR-1, FR-2
            Design section: Section 4.3 API Changes
            Contributing stories: TEST-201, TEST-202
        """)
    snapshot = {"key": key, "summary": summary, "description": description}
    if extra:
        snapshot.update(extra)
    return snapshot


def _make_evidence_items() -> list[dict]:
    """Build sample PR evidence items."""
    return [
        {
            "pr_url": "https://github.example.invalid/org/repo/pull/101",
            "contributor_key": "TEST-201",
            "target_branch": "main",
            "state": "merged",
            "title": "feat: add widget config command",
            "merged": True,
            "merge_commit": "abc123def",
            "observations": ["Adds --name and --value flags as planned"],
        },
        {
            "pr_url": "https://github.example.invalid/org/repo/pull/102",
            "contributor_key": "TEST-202",
            "target_branch": "release-4.19",
            "state": "merged",
            "title": "feat: widget status endpoint",
            "merged": True,
            "merge_commit": "def456abc",
            "observations": [
                "Adds /api/v1/widgets/status endpoint",
                "Status values include 'maintenance' not in plan",
            ],
        },
    ]


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

class TestUrlValidation(unittest.TestCase):
    """Test URL validation and normalization."""

    def test_valid_https_url(self) -> None:
        result = evidence.validate_url("https://github.example.invalid/org/repo")
        self.assertEqual(result, "https://github.example.invalid/org/repo")

    def test_strips_trailing_slash(self) -> None:
        result = evidence.validate_url("https://github.example.invalid/org/repo/")
        self.assertEqual(result, "https://github.example.invalid/org/repo")

    def test_rejects_embedded_credentials(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            evidence.validate_url("https://user:pass@github.example.invalid/org/repo")
        self.assertIn("credentials", str(ctx.exception))

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url("")

    def test_rejects_ftp(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url("ftp://example.invalid/file")

    def test_rejects_control_chars(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url("https://example.invalid/\x00bad")

    def test_pr_url_strips_fragment(self) -> None:
        result = evidence.validate_pr_url(
            "https://github.example.invalid/org/repo/pull/42#discussion"
        )
        self.assertEqual(
            result, "https://github.example.invalid/org/repo/pull/42"
        )

    def test_pr_url_strips_query(self) -> None:
        result = evidence.validate_pr_url(
            "https://github.example.invalid/org/repo/pull/42?tab=files"
        )
        self.assertEqual(
            result, "https://github.example.invalid/org/repo/pull/42"
        )


class TestPrIdentity(unittest.TestCase):
    """Test PR identity extraction from URLs."""

    def test_github_pr(self) -> None:
        result = evidence.extract_pr_identity(
            "https://github.example.invalid/org/repo/pull/42"
        )
        self.assertEqual(result["owner"], "org")
        self.assertEqual(result["repo"], "repo")
        self.assertEqual(result["number"], "42")

    def test_gitlab_mr(self) -> None:
        result = evidence.extract_pr_identity(
            "https://gitlab.example.invalid/org/repo/-/merge_requests/7"
        )
        self.assertEqual(result["owner"], "org")
        self.assertEqual(result["repo"], "repo")
        self.assertEqual(result["number"], "7")

    def test_gitlab_mr_no_dash(self) -> None:
        result = evidence.extract_pr_identity(
            "https://gitlab.example.invalid/org/repo/merge_requests/7"
        )
        self.assertEqual(result["number"], "7")

    def test_different_repos_produce_different_identities(self) -> None:
        id1 = evidence.extract_pr_identity(
            "https://github.example.invalid/org/repo-a/pull/1"
        )
        id2 = evidence.extract_pr_identity(
            "https://github.example.invalid/org/repo-b/pull/1"
        )
        self.assertNotEqual(id1["repo"], id2["repo"])


# ---------------------------------------------------------------------------
# Reference extraction
# ---------------------------------------------------------------------------

class TestReferenceExtraction(unittest.TestCase):
    """Test Jira key and story reference extraction."""

    def test_extract_jira_keys(self) -> None:
        keys = evidence.extract_all_jira_keys(
            "TEST-201, TEST-202, and also TEST-201 again"
        )
        self.assertEqual(keys, ["TEST-201", "TEST-202"])

    def test_extract_story_refs(self) -> None:
        refs = evidence.extract_story_refs(
            "Story 1.01, Story 2.03, Story 1.01"
        )
        self.assertEqual(refs, ["story-1.01", "story-2.03"])

    def test_stories_plural(self) -> None:
        refs = evidence.extract_story_refs("Stories 1.01, 2.03")
        self.assertEqual(refs, ["story-1.01", "story-2.03"])


# ---------------------------------------------------------------------------
# Issue validation
# ---------------------------------------------------------------------------

class TestValidateIssue(unittest.TestCase):
    """Test DOCS issue snapshot validation."""

    def test_valid_snapshot(self) -> None:
        snapshot = _make_docs_snapshot()
        result = evidence.validate_issue(snapshot)
        self.assertTrue(result["valid"])
        self.assertEqual(result["key"], "TEST-100")
        self.assertEqual(result["errors"], [])

    def test_extracts_contributors_not_dependencies(self) -> None:
        """Contributing stories are extracted; Dependencies are separate."""
        snapshot = _make_docs_snapshot()
        result = evidence.validate_issue(snapshot)
        # Contributors come from Contributing stories line
        self.assertIn("TEST-201", result["contributors"])
        self.assertIn("TEST-202", result["contributors"])
        # TEST-300 is a dependency, not a contributor
        self.assertNotIn("TEST-300", result["contributors"])
        self.assertIn("TEST-300", result["dependencies"])

    def test_missing_docs_prefix(self) -> None:
        snapshot = _make_docs_snapshot(summary="Widget docs")
        result = evidence.validate_issue(snapshot)
        self.assertFalse(result["valid"])
        self.assertTrue(any("[DOCS]" in e for e in result["errors"]))

    def test_missing_description(self) -> None:
        snapshot = _make_docs_snapshot(description="")
        result = evidence.validate_issue(snapshot)
        self.assertFalse(result["valid"])

    def test_missing_documentation_inputs(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria

            - [ ] Something

            ## Documentation Scope

            Some scope

            ## Design Reference

            Contributing stories: TEST-201
        """)
        snapshot = _make_docs_snapshot(description=desc)
        result = evidence.validate_issue(snapshot)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("Documentation Inputs" in e for e in result["errors"])
        )

    def test_no_contributors(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria

            - [ ] Something

            ## Documentation Scope

            Some scope

            ## Documentation Inputs

            No inputs yet.
        """)
        snapshot = _make_docs_snapshot(description=desc)
        result = evidence.validate_issue(snapshot)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("Contributing stories" in e for e in result["errors"])
        )

    def test_unresolved_story_ref_is_warning(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria

            - [ ] Something

            ## Documentation Scope

            Covers new CLI

            ## Documentation Inputs

            **Story 1.01 -- Add widget:**
            - New CLI command

            ## Design Reference

            Contributing stories: Story 1.01
        """)
        snapshot = _make_docs_snapshot(description=desc)
        result = evidence.validate_issue(snapshot)
        # Valid but with warning about unresolved ref
        self.assertTrue(result["valid"])
        self.assertIn("story-1.01", result["contributors"])
        self.assertTrue(
            any("unresolved" in w for w in result["warnings"])
        )

    def test_invalid_jira_key_format(self) -> None:
        snapshot = _make_docs_snapshot(key="bad-key")
        result = evidence.validate_issue(snapshot)
        self.assertFalse(result["valid"])
        self.assertTrue(any("invalid Jira key" in e for e in result["errors"]))

    def test_read_only_no_mutation(self) -> None:
        """validate_issue must not mutate its input."""
        snapshot = _make_docs_snapshot()
        original = copy.deepcopy(snapshot)
        evidence.validate_issue(snapshot)
        self.assertEqual(snapshot, original)

    def test_parses_documentation_inputs_items(self) -> None:
        snapshot = _make_docs_snapshot()
        result = evidence.validate_issue(snapshot)
        inputs = result["documentation_inputs"]
        self.assertTrue(len(inputs) >= 2)
        # First contributor's items
        test201_items = [i for i in inputs if i["contributor"] == "TEST-201"]
        self.assertTrue(len(test201_items) >= 1)
        self.assertEqual(test201_items[0]["marker"], "planned")

    def test_parses_assumption_marker(self) -> None:
        snapshot = _make_docs_snapshot()
        result = evidence.validate_issue(snapshot)
        assumption_items = [
            i for i in result["documentation_inputs"]
            if i["marker"] == "assumption"
        ]
        self.assertTrue(len(assumption_items) >= 1)


# ---------------------------------------------------------------------------
# Evidence normalization
# ---------------------------------------------------------------------------

class TestNormalizeEvidence(unittest.TestCase):
    """Test PR evidence normalization."""

    def test_normalizes_valid_evidence(self) -> None:
        items = _make_evidence_items()
        result = evidence.normalize_evidence(items)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["errors"], [])

    def test_deduplicates_same_url(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/101",
                "contributor_key": "TEST-201",
            },
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/101/",
                "contributor_key": "TEST-202",
            },
        ]
        result = evidence.normalize_evidence(items)
        self.assertEqual(len(result["items"]), 1)
        # Both contributors should be merged
        self.assertIn("TEST-201", result["items"][0]["contributor_keys"])
        self.assertIn("TEST-202", result["items"][0]["contributor_keys"])

    def test_rejects_embedded_credentials_in_pr(self) -> None:
        items = [
            {
                "pr_url": "https://user:tok@github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
            },
        ]
        result = evidence.normalize_evidence(items)
        self.assertEqual(len(result["items"]), 0)
        self.assertTrue(len(result["errors"]) > 0)
        self.assertTrue(any("credentials" in e for e in result["errors"]))

    def test_rejects_missing_contributor(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
            },
        ]
        result = evidence.normalize_evidence(items)
        self.assertEqual(len(result["items"]), 0)
        self.assertTrue(any("contributor_key" in e for e in result["errors"]))

    def test_preserves_different_repo_identities(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo-a/pull/1",
                "contributor_key": "TEST-201",
            },
            {
                "pr_url": "https://github.example.invalid/org/repo-b/pull/1",
                "contributor_key": "TEST-202",
            },
        ]
        result = evidence.normalize_evidence(items)
        self.assertEqual(len(result["items"]), 2)
        repos = {i["pr_identity"]["repo"] for i in result["items"]}
        self.assertEqual(repos, {"repo-a", "repo-b"})

    def test_evidence_not_array(self) -> None:
        result = evidence.normalize_evidence("not a list")
        self.assertTrue(len(result["errors"]) > 0)

    def test_strips_pr_url_fragment(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1#diff",
                "contributor_key": "TEST-201",
            },
        ]
        result = evidence.normalize_evidence(items)
        self.assertEqual(len(result["items"]), 1)
        self.assertNotIn("#", result["items"][0]["pr_url"])


# ---------------------------------------------------------------------------
# Change plan
# ---------------------------------------------------------------------------

class TestBuildChangePlan(unittest.TestCase):
    """Test delivery-evidence change plan building."""

    def _make_plan(
        self,
        *,
        snapshot: dict | None = None,
        evidence_items: list[dict] | None = None,
        target: dict | None = None,
        profile: dict | None = None,
    ) -> dict:
        if snapshot is None:
            snapshot = _make_docs_snapshot()
        if evidence_items is None:
            evidence_items = _make_evidence_items()
        if target is None:
            target = {"release": "4.19", "target_branch": "main"}
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(evidence_items)
        return evidence.build_change_plan(validation, ev, target, profile)

    def test_complete_plan(self) -> None:
        plan = self._make_plan()
        self.assertEqual(plan["status"], "complete")
        self.assertTrue(len(plan["inputs"]) > 0)
        self.assertTrue(len(plan["pr_links"]) > 0)

    def test_delivered_inputs(self) -> None:
        plan = self._make_plan()
        delivered = [i for i in plan["inputs"] if i["status"] == "delivered"]
        self.assertTrue(len(delivered) > 0)

    def test_missing_evidence(self) -> None:
        """Contributor with no PRs produces missing_evidence finding."""
        snapshot = _make_docs_snapshot()
        # Only provide evidence for TEST-201, not TEST-202
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/101",
                "contributor_key": "TEST-201",
                "merged": True,
            },
        ]
        plan = self._make_plan(evidence_items=items)
        findings = [f for f in plan["findings"] if f["type"] == "missing_evidence"]
        self.assertTrue(
            any(f["ref"] == "TEST-202" for f in findings),
            f"Expected missing_evidence for TEST-202 in {findings}"
        )

    def test_dependency_not_flagged_as_missing(self) -> None:
        """Dependencies (not contributors) don't generate missing_evidence."""
        plan = self._make_plan()
        findings = [f for f in plan["findings"] if f["type"] == "missing_evidence"]
        refs = [f["ref"] for f in findings]
        self.assertNotIn("TEST-300", refs)

    def test_pr_target_branch_ambiguity(self) -> None:
        """PR targeting wrong branch produces target_notes."""
        plan = self._make_plan()
        # TEST-202 targets release-4.19, not main
        target_notes = [
            n for inp in plan["inputs"] for n in inp.get("target_notes", [])
        ]
        self.assertTrue(
            any("release-4.19" in n for n in target_notes),
            f"Expected target branch note in {target_notes}"
        )

    def test_new_surface_finding(self) -> None:
        """PR for non-contributor produces new_surface finding."""
        items = _make_evidence_items() + [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/999",
                "contributor_key": "TEST-999",
            },
        ]
        plan = self._make_plan(evidence_items=items)
        new_surfaces = [f for f in plan["findings"] if f["type"] == "new_surface"]
        self.assertTrue(
            any(f["ref"] == "TEST-999" for f in new_surfaces)
        )

    def test_invalid_issue_produces_invalid_plan(self) -> None:
        snapshot = _make_docs_snapshot(key="bad")
        plan = self._make_plan(snapshot=snapshot)
        self.assertEqual(plan["status"], "invalid_issue")

    def test_unresolved_contributor_finding(self) -> None:
        """Unresolved Story N.NN contributor produces finding."""
        desc = textwrap.dedent("""\
            ## Acceptance Criteria

            - [ ] Something

            ## Documentation Scope

            Covers new CLI

            ## Documentation Inputs

            **Story 1.01 -- Add widget:**
            - New CLI command

            ## Design Reference

            Contributing stories: Story 1.01
        """)
        snapshot = _make_docs_snapshot(description=desc)
        plan = self._make_plan(snapshot=snapshot, evidence_items=[])
        findings = [f for f in plan["findings"] if f["type"] == "unresolved_contributor"]
        self.assertTrue(
            any("story-1.01" in f["ref"] for f in findings)
        )

    def test_source_proposal_disabled(self) -> None:
        """Source/narrative apply is disabled by default."""
        plan = self._make_plan()
        self.assertFalse(plan["source_proposal"]["apply_enabled"])
        self.assertIn("disabled", plan["source_proposal"]["reason"])

    def test_source_proposal_has_owning_workflow(self) -> None:
        plan = self._make_plan()
        self.assertEqual(plan["source_proposal"]["owning_workflow"], "design")
        self.assertEqual(plan["source_proposal"]["owning_action"], "/revise")

    def test_fingerprint_stable(self) -> None:
        plan1 = self._make_plan()
        plan2 = self._make_plan()
        self.assertEqual(plan1["fingerprint"], plan2["fingerprint"])
        self.assertTrue(len(plan1["fingerprint"]) > 0)

    def test_read_only_no_mutation(self) -> None:
        """build_change_plan must not mutate its inputs."""
        snapshot = _make_docs_snapshot()
        items = _make_evidence_items()
        target = {"release": "4.19", "target_branch": "main"}
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(items)
        orig_val = copy.deepcopy(validation)
        orig_ev = copy.deepcopy(ev)
        orig_target = copy.deepcopy(target)
        evidence.build_change_plan(validation, ev, target)
        self.assertEqual(validation, orig_val)
        self.assertEqual(ev, orig_ev)
        self.assertEqual(target, orig_target)

    def test_readiness_with_profile(self) -> None:
        profile = {"readiness_dimensions": ["technical_accuracy", "completeness"]}
        plan = self._make_plan(profile=profile)
        self.assertIsNotNone(plan["readiness"])
        self.assertEqual(
            plan["readiness"]["dimensions"],
            ["technical_accuracy", "completeness"],
        )
        self.assertFalse(plan["readiness"]["complete"])

    def test_readiness_without_profile(self) -> None:
        plan = self._make_plan(profile=None)
        self.assertIsNone(plan["readiness"])

    def test_readiness_empty_dimensions(self) -> None:
        profile = {"readiness_dimensions": []}
        plan = self._make_plan(profile=profile)
        self.assertEqual(plan["readiness"]["dimensions"], [])
        self.assertFalse(plan["readiness"]["complete"])


# ---------------------------------------------------------------------------
# Enrichment check
# ---------------------------------------------------------------------------

class TestCheckEnrichment(unittest.TestCase):
    """Test enrichment idempotency and eligibility checks."""

    def _make_enrichment(
        self,
        *,
        existing_links: list[dict] | None = None,
    ) -> dict:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        current = {
            "remote_links": existing_links or [],
        }
        return evidence.check_enrichment(plan, current)

    def test_new_links_eligible(self) -> None:
        result = self._make_enrichment()
        self.assertTrue(len(result["eligible_links"]) > 0)
        self.assertEqual(len(result["existing_links"]), 0)

    def test_existing_link_detected(self) -> None:
        result = self._make_enrichment(
            existing_links=[
                {"url": "https://github.example.invalid/org/repo/pull/101"},
            ]
        )
        self.assertTrue(len(result["existing_links"]) > 0)
        # Should have fewer eligible links
        eligible_urls = {l["url"] for l in result["eligible_links"]}
        self.assertNotIn(
            "https://github.example.invalid/org/repo/pull/101",
            eligible_urls,
        )

    def test_forbidden_fields_rejected(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        # Inject forbidden metadata
        plan["metadata"]["proposed_status"] = "Done"
        plan["metadata"]["proposed_assignee"] = "someone"

        current = {"remote_links": []}
        result = evidence.check_enrichment(plan, current)
        self.assertTrue(len(result["forbidden_fields"]) > 0)
        self.assertTrue(
            any("status" in f for f in result["forbidden_fields"])
        )

    def test_profile_forbidden_fields(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        current = {"remote_links": [], "profile_fields": {"labels": "v4.19"}}
        result = evidence.check_enrichment(plan, current)
        self.assertTrue(
            any("labels" in f for f in result["forbidden_fields"])
        )

    def test_repeated_check_idempotent(self) -> None:
        result1 = self._make_enrichment()
        result2 = self._make_enrichment()
        self.assertEqual(
            result1["baseline_fingerprint"],
            result2["baseline_fingerprint"],
        )

    def test_stale_defaults_false(self) -> None:
        result = self._make_enrichment()
        self.assertFalse(result["stale"])


# ---------------------------------------------------------------------------
# Verify enrichment (readback)
# ---------------------------------------------------------------------------

class TestVerifyEnrichment(unittest.TestCase):
    """Test readback verification after enrichment writes."""

    def test_confirmed_when_link_present(self) -> None:
        enrichment = {
            "eligible_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
            ],
        }
        readback = {
            "remote_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
            ],
        }
        receipt = evidence.verify_enrichment(enrichment, readback)
        self.assertTrue(receipt["all_confirmed"])
        self.assertEqual(receipt["receipts"][0]["status"], "confirmed")

    def test_uncertain_when_link_missing(self) -> None:
        enrichment = {
            "eligible_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
            ],
        }
        readback = {"remote_links": []}
        receipt = evidence.verify_enrichment(enrichment, readback)
        self.assertFalse(receipt["all_confirmed"])
        self.assertEqual(receipt["receipts"][0]["status"], "uncertain")

    def test_partial_confirmation(self) -> None:
        enrichment = {
            "eligible_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
                {"url": "https://github.example.invalid/org/repo/pull/102"},
            ],
        }
        readback = {
            "remote_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
            ],
        }
        receipt = evidence.verify_enrichment(enrichment, readback)
        self.assertFalse(receipt["all_confirmed"])
        confirmed = [r for r in receipt["receipts"] if r["status"] == "confirmed"]
        uncertain = [r for r in receipt["receipts"] if r["status"] == "uncertain"]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(len(uncertain), 1)


# ---------------------------------------------------------------------------
# Handoff rendering
# ---------------------------------------------------------------------------

class TestRenderHandoff(unittest.TestCase):
    """Test handoff document rendering."""

    def test_deterministic(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        md1 = evidence.render_handoff(plan)
        md2 = evidence.render_handoff(plan)
        self.assertEqual(md1, md2)

    def test_contains_issue_key(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        md = evidence.render_handoff(plan)
        self.assertIn("TEST-100", md)

    def test_contains_delivery_counts(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        md = evidence.render_handoff(plan)
        self.assertIn("Delivered:", md)
        self.assertIn("Missing evidence:", md)

    def test_contains_source_proposal(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        md = evidence.render_handoff(plan)
        self.assertIn("Source Change Proposal", md)
        self.assertIn("**Apply enabled:** False", md)


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):
    """Test CLI subcommands via subprocess."""

    def _run(
        self,
        subcmd: str,
        input_data: dict | list,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(input_data, f)
            f.flush()
            input_path = f.name

        try:
            cmd = [
                sys.executable, "-I",
                str(_SCRIPT_DIR / "evidence.py"),
                subcmd, "--input", input_path,
            ]
            if extra_args:
                cmd.extend(extra_args)
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
        finally:
            os.unlink(input_path)

    def test_validate_valid(self) -> None:
        snapshot = _make_docs_snapshot()
        proc = self._run("validate", snapshot)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["valid"])

    def test_validate_invalid(self) -> None:
        snapshot = _make_docs_snapshot(key="bad")
        proc = self._run("validate", snapshot)
        self.assertEqual(proc.returncode, 1)
        result = json.loads(proc.stdout)
        self.assertFalse(result["valid"])

    def test_build_plan(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        data = {
            "validation": validation,
            "evidence": ev,
            "target": {"release": "4.19", "target_branch": "main"},
        }
        proc = self._run("build-plan", data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plan = json.loads(proc.stdout)
        self.assertEqual(plan["status"], "complete")

    def test_check_enrichment(self) -> None:
        snapshot = _make_docs_snapshot()
        validation = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            validation, ev, {"release": "4.19", "target_branch": "main"}
        )
        data = {
            "plan": plan,
            "current_state": {"remote_links": []},
        }
        proc = self._run("check-enrichment", data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(len(result["eligible_links"]) > 0)

    def test_validate_does_not_mutate_file(self) -> None:
        """CLI validate must not modify the input file."""
        snapshot = _make_docs_snapshot()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(snapshot, f)
            f.flush()
            input_path = f.name

        try:
            original = Path(input_path).read_bytes()
            subprocess.run(
                [
                    sys.executable, "-I",
                    str(_SCRIPT_DIR / "evidence.py"),
                    "validate", "--input", input_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            after = Path(input_path).read_bytes()
            self.assertEqual(original, after, "input file was modified")
        finally:
            os.unlink(input_path)

    def test_bad_json_exits_1(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{bad json")
            f.flush()
            input_path = f.name

        try:
            proc = subprocess.run(
                [
                    sys.executable, "-I",
                    str(_SCRIPT_DIR / "evidence.py"),
                    "validate", "--input", input_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 1)
        finally:
            os.unlink(input_path)


if __name__ == "__main__":
    unittest.main()
