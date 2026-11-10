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

            **TEST-201 — Add widget config command:**
            - New `widget config set` CLI command with `--name` and `--value` flags
            - Config validation error messages and recovery steps

            **TEST-202 — Widget status endpoint:**
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
    return [
        {
            "pr_url": "https://github.example.invalid/org/repo/pull/101",
            "contributor_key": "TEST-201",
            "target_branch": "main",
            "state": "merged",
            "title": "feat: add widget config command",
            "merged": True,
            "merge_commit": "abc123def",
            "observations": [
                "Adds --name and --value flags as planned"
            ],
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
                "Status values include 'maintenance' not in plan",
            ],
        },
    ]


def _cli_run(
    subcmd: str,
    input_data,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run evidence.py via subprocess."""
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


# ---------------------------------------------------------------------------
# C: URL validation
# ---------------------------------------------------------------------------

class TestUrlValidation(unittest.TestCase):

    def test_valid_https_url(self) -> None:
        r = evidence.validate_url(
            "https://github.example.invalid/org/repo"
        )
        self.assertEqual(
            r, "https://github.example.invalid/org/repo"
        )

    def test_strips_trailing_slash(self) -> None:
        r = evidence.validate_url(
            "https://github.example.invalid/org/repo/"
        )
        self.assertEqual(
            r, "https://github.example.invalid/org/repo"
        )

    def test_rejects_embedded_credentials(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            evidence.validate_url(
                "https://user:pass@github.example.invalid/org/repo"
            )
        self.assertIn("credentials", str(ctx.exception))

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url("")

    def test_rejects_ftp(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url("ftp://example.invalid/file")

    def test_rejects_control_chars(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url(
                "https://example.invalid/\x00bad"
            )

    def test_rejects_explicit_port(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_url(
                "https://example.invalid:8443/path"
            )


class TestPrUrlValidation(unittest.TestCase):
    """C: PR URL must have supported structure."""

    def test_valid_github_pr(self) -> None:
        r = evidence.validate_pr_url(
            "https://github.example.invalid/org/repo/pull/42"
        )
        self.assertEqual(
            r,
            "https://github.example.invalid/org/repo/pull/42",
        )

    def test_strips_fragment(self) -> None:
        r = evidence.validate_pr_url(
            "https://github.example.invalid/org/repo/pull/42"
            "#discussion"
        )
        self.assertEqual(
            r,
            "https://github.example.invalid/org/repo/pull/42",
        )

    def test_strips_query(self) -> None:
        r = evidence.validate_pr_url(
            "https://github.example.invalid/org/repo/pull/42"
            "?tab=files"
        )
        self.assertEqual(
            r,
            "https://github.example.invalid/org/repo/pull/42",
        )

    def test_rejects_non_pr_page(self) -> None:
        """A commits page is not a PR URL."""
        with self.assertRaises(ValueError):
            evidence.validate_pr_url(
                "https://github.example.invalid/org/repo/commits/main"
            )

    def test_rejects_trailing_path(self) -> None:
        """PR URL with trailing /files is not the canonical PR page."""
        with self.assertRaises(ValueError):
            evidence.validate_pr_url(
                "https://github.example.invalid/org/repo/pull/42/files"
            )

    def test_rejects_nonnumeric_id(self) -> None:
        with self.assertRaises(ValueError):
            evidence.validate_pr_url(
                "https://github.example.invalid/org/repo/pull/abc"
            )

    def test_valid_gitlab_mr(self) -> None:
        r = evidence.validate_pr_url(
            "https://gitlab.example.invalid/org/repo/-/merge_requests/7"
        )
        self.assertEqual(
            r,
            "https://gitlab.example.invalid/org/repo"
            "/-/merge_requests/7",
        )

    def test_valid_gitlab_nested_namespace(self) -> None:
        """GitLab group/subgroup/repo/-/merge_requests/N."""
        r = evidence.validate_pr_url(
            "https://gitlab.example.invalid/group/subgroup/repo"
            "/-/merge_requests/99"
        )
        self.assertEqual(
            r,
            "https://gitlab.example.invalid/group/subgroup/repo"
            "/-/merge_requests/99",
        )

    def test_valid_gitlab_legacy(self) -> None:
        r = evidence.validate_pr_url(
            "https://gitlab.example.invalid/org/repo"
            "/merge_requests/7"
        )
        self.assertIn("merge_requests/7", r)


class TestPrIdentity(unittest.TestCase):

    def test_github_pr(self) -> None:
        r = evidence.extract_pr_identity(
            "https://github.example.invalid/org/repo/pull/42"
        )
        self.assertEqual(r["owner"], "org")
        self.assertEqual(r["repo"], "repo")
        self.assertEqual(r["number"], "42")

    def test_gitlab_nested(self) -> None:
        r = evidence.extract_pr_identity(
            "https://gitlab.example.invalid/group/subgroup/repo"
            "/-/merge_requests/7"
        )
        self.assertEqual(r["owner"], "group/subgroup")
        self.assertEqual(r["repo"], "repo")
        self.assertEqual(r["number"], "7")

    def test_different_repos_different_identities(self) -> None:
        id1 = evidence.extract_pr_identity(
            "https://github.example.invalid/org/repo-a/pull/1"
        )
        id2 = evidence.extract_pr_identity(
            "https://github.example.invalid/org/repo-b/pull/1"
        )
        self.assertNotEqual(id1["repo"], id2["repo"])

    def test_rejects_unrecognized_path(self) -> None:
        with self.assertRaises(ValueError):
            evidence.extract_pr_identity(
                "https://github.example.invalid/org/repo/issues/42"
            )


# ---------------------------------------------------------------------------
# Reference extraction
# ---------------------------------------------------------------------------

class TestReferenceExtraction(unittest.TestCase):

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


# ---------------------------------------------------------------------------
# A: Issue validation
# ---------------------------------------------------------------------------

class TestValidateIssue(unittest.TestCase):

    def test_valid_snapshot(self) -> None:
        r = evidence.validate_issue(_make_docs_snapshot())
        self.assertTrue(r["valid"])
        self.assertEqual(r["key"], "TEST-100")
        self.assertEqual(r["errors"], [])

    def test_extracts_contributors_not_dependencies(self) -> None:
        r = evidence.validate_issue(_make_docs_snapshot())
        self.assertIn("TEST-201", r["contributors"])
        self.assertIn("TEST-202", r["contributors"])
        self.assertNotIn("TEST-300", r["contributors"])
        self.assertIn("TEST-300", r["dependencies"])

    def test_missing_docs_prefix(self) -> None:
        r = evidence.validate_issue(
            _make_docs_snapshot(summary="Widget docs")
        )
        self.assertFalse(r["valid"])

    def test_missing_description(self) -> None:
        r = evidence.validate_issue(
            _make_docs_snapshot(description="")
        )
        self.assertFalse(r["valid"])

    def test_missing_documentation_inputs(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Some scope
            ## Design Reference
            Contributing stories: TEST-201
        """)
        r = evidence.validate_issue(_make_docs_snapshot(description=desc))
        self.assertFalse(r["valid"])
        self.assertTrue(
            any("Documentation Inputs" in e for e in r["errors"])
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
        r = evidence.validate_issue(_make_docs_snapshot(description=desc))
        self.assertFalse(r["valid"])

    def test_unresolved_story_ref_is_warning(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Covers new CLI
            ## Documentation Inputs
            **Story 1.01 — Add widget:**
            - New CLI command
            ## Design Reference
            Contributing stories: Story 1.01
        """)
        r = evidence.validate_issue(_make_docs_snapshot(description=desc))
        self.assertTrue(r["valid"])
        self.assertIn("story-1.01", r["contributors"])
        self.assertTrue(any("unresolved" in w for w in r["warnings"]))

    def test_invalid_jira_key_format(self) -> None:
        r = evidence.validate_issue(_make_docs_snapshot(key="bad-key"))
        self.assertFalse(r["valid"])

    def test_read_only_no_mutation(self) -> None:
        snap = _make_docs_snapshot()
        orig = copy.deepcopy(snap)
        evidence.validate_issue(snap)
        self.assertEqual(snap, orig)

    def test_parses_documentation_inputs_items(self) -> None:
        r = evidence.validate_issue(_make_docs_snapshot())
        items = r["documentation_inputs"]
        self.assertTrue(len(items) >= 2)
        t201 = [i for i in items if i["contributor"] == "TEST-201"]
        self.assertTrue(len(t201) >= 1)

    def test_preserves_assumption_marker(self) -> None:
        """Assumption markers are preserved in text."""
        r = evidence.validate_issue(_make_docs_snapshot())
        assumption = [
            i for i in r["documentation_inputs"]
            if i["marker"] == "assumption"
        ]
        self.assertTrue(len(assumption) >= 1)
        # Original marker text preserved
        self.assertIn("[Assumption]", assumption[0]["text"])

    def test_empty_inputs_section_is_warning(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Some scope
            ## Documentation Inputs

            ## Design Reference
            Contributing stories: TEST-201
        """)
        r = evidence.validate_issue(_make_docs_snapshot(description=desc))
        self.assertTrue(r["valid"])
        self.assertTrue(
            any("no structured items" in w for w in r["warnings"])
        )


# ---------------------------------------------------------------------------
# B, C: Evidence normalization
# ---------------------------------------------------------------------------

class TestNormalizeEvidence(unittest.TestCase):

    def test_normalizes_valid_evidence(self) -> None:
        r = evidence.normalize_evidence(_make_evidence_items())
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["errors"], [])

    def test_deduplicates_same_url(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/101",
                "contributor_key": "TEST-201",
                "merged": True,
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/101/"
                ),
                "contributor_key": "TEST-202",
                "merged": True,
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 1)
        self.assertIn("TEST-201", r["items"][0]["contributor_keys"])
        self.assertIn("TEST-202", r["items"][0]["contributor_keys"])

    def test_contradictory_merged_produces_conflict(self) -> None:
        """B: Same PR with merged=True and merged=False → conflict."""
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": True,
            },
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-202",
                "merged": False,
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 1)
        self.assertTrue(len(r["items"][0]["conflicts"]) > 0)
        self.assertTrue(
            any("contradictory" in w for w in r["warnings"])
        )

    def test_contradictory_target_branch(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "target_branch": "main",
            },
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "target_branch": "release-4.19",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertTrue(len(r["items"][0]["conflicts"]) > 0)

    def test_rejects_embedded_credentials_in_pr(self) -> None:
        items = [
            {
                "pr_url": (
                    "https://user:tok@github.example.invalid"
                    "/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)
        self.assertTrue(any("credentials" in e for e in r["errors"]))

    def test_rejects_missing_contributor(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)

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
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 2)
        repos = {i["pr_identity"]["repo"] for i in r["items"]}
        self.assertEqual(repos, {"repo-a", "repo-b"})

    def test_rejects_non_pr_url(self) -> None:
        """C: Non-PR URLs are rejected, not passed with empty identity."""
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo"
                    "/commits/main"
                ),
                "contributor_key": "TEST-201",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)
        self.assertTrue(len(r["errors"]) > 0)

    def test_rejects_invalid_merged_type(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": "yes",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)
        self.assertTrue(any("boolean" in e for e in r["errors"]))

    def test_rejects_non_string_observation(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "observations": [42],
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)

    def test_evidence_not_array(self) -> None:
        r = evidence.normalize_evidence("not a list")
        self.assertTrue(len(r["errors"]) > 0)


# ---------------------------------------------------------------------------
# B: Change plan
# ---------------------------------------------------------------------------

class TestBuildChangePlan(unittest.TestCase):

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
        val = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(evidence_items)
        return evidence.build_change_plan(val, ev, target, profile)

    def test_complete_plan(self) -> None:
        plan = self._make_plan()
        self.assertEqual(plan["status"], "complete")
        self.assertTrue(len(plan["inputs"]) > 0)

    def test_per_input_honest_status(self) -> None:
        """B: 'as planned' observation → merged_pr_exists, not 'delivered'."""
        plan = self._make_plan()
        for inp in plan["inputs"]:
            self.assertIn(inp["status"], (
                "merged_pr_exists", "merged_wrong_target",
                "in_progress", "no_evidence",
                "evidence_unverified", "conflicting",
            ))

    def test_merged_wrong_target(self) -> None:
        """B: PR targeting wrong branch → merged_wrong_target."""
        plan = self._make_plan()
        wrong_target = [
            i for i in plan["inputs"]
            if i["status"] == "merged_wrong_target"
        ]
        self.assertTrue(
            len(wrong_target) > 0,
            "Expected merged_wrong_target for TEST-202"
        )

    def test_missing_evidence_always_flagged(self) -> None:
        """B: Contributor with no PRs → missing_evidence, even if also
        a dependency."""
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Some scope
            ## Documentation Inputs
            **TEST-201 — Add widget:**
            - New CLI command
            ## Dependencies
            TEST-201
            ## Design Reference
            Contributing stories: TEST-201
        """)
        snapshot = _make_docs_snapshot(description=desc)
        plan = self._make_plan(snapshot=snapshot, evidence_items=[])
        findings = [
            f for f in plan["findings"]
            if f["type"] == "missing_evidence"
        ]
        self.assertTrue(
            any(f["ref"] == "TEST-201" for f in findings),
            "Contributor also-dependency must still be flagged"
        )

    def test_non_contributor_not_in_pr_links(self) -> None:
        """B: PRs from non-contributors are NOT eligible links."""
        items = _make_evidence_items() + [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/999"
                ),
                "contributor_key": "TEST-999",
            },
        ]
        plan = self._make_plan(evidence_items=items)
        link_urls = {l["url"] for l in plan["pr_links"]}
        self.assertNotIn(
            "https://github.example.invalid/org/repo/pull/999",
            link_urls,
        )
        findings = [
            f for f in plan["findings"]
            if f["type"] == "non_contributor_evidence"
        ]
        self.assertTrue(any(f["ref"] == "TEST-999" for f in findings))

    def test_as_planned_no_source_proposal(self) -> None:
        """B: 'as planned' observation does NOT produce update proposal."""
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": True,
                "observations": ["Adds --name and --value flags as planned"],
            },
        ]
        plan = self._make_plan(evidence_items=items)
        updates = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "update"
        ]
        self.assertEqual(len(updates), 0)

    def test_observations_produce_review_proposal(self) -> None:
        """B: Observations → review proposal with evidence URLs."""
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": True,
                "observations": [
                    "Added --format flag not in plan"
                ],
            },
        ]
        plan = self._make_plan(evidence_items=items)
        reviews = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "review"
        ]
        self.assertTrue(len(reviews) > 0)
        self.assertTrue(reviews[0]["evidence_urls"])
        self.assertIn(
            "Added --format flag not in plan",
            reviews[0]["observations"],
        )

    def test_non_contributor_proposal_has_evidence(self) -> None:
        """B: non-contributor proposal carries evidence URL."""
        items = _make_evidence_items() + [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/999"
                ),
                "contributor_key": "TEST-999",
            },
        ]
        plan = self._make_plan(evidence_items=items)
        adds = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "add_contributor"
        ]
        self.assertTrue(len(adds) > 0)
        self.assertTrue(adds[0]["evidence_urls"])
        self.assertTrue(adds[0]["proposed_wording"])

    def test_invalid_issue(self) -> None:
        plan = self._make_plan(snapshot=_make_docs_snapshot(key="bad"))
        self.assertEqual(plan["status"], "invalid_issue")

    def test_unresolved_contributor_finding(self) -> None:
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Covers new CLI
            ## Documentation Inputs
            **Story 1.01 — Add widget:**
            - New CLI command
            ## Design Reference
            Contributing stories: Story 1.01
        """)
        plan = self._make_plan(
            snapshot=_make_docs_snapshot(description=desc),
            evidence_items=[],
        )
        findings = [
            f for f in plan["findings"]
            if f["type"] == "unresolved_contributor"
        ]
        self.assertTrue(
            any("story-1.01" in f["ref"] for f in findings)
        )

    def test_source_proposal_disabled(self) -> None:
        plan = self._make_plan()
        self.assertFalse(plan["source_proposal"]["apply_enabled"])
        self.assertEqual(
            plan["source_proposal"]["owning_workflow"], "design"
        )

    def test_digest_stable(self) -> None:
        plan1 = self._make_plan()
        plan2 = self._make_plan()
        self.assertEqual(plan1["plan_digest"], plan2["plan_digest"])
        self.assertTrue(len(plan1["plan_digest"]) > 0)

    def test_read_only_no_mutation(self) -> None:
        snap = _make_docs_snapshot()
        items = _make_evidence_items()
        target = {"release": "4.19", "target_branch": "main"}
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(items)
        orig_val = copy.deepcopy(val)
        orig_ev = copy.deepcopy(ev)
        orig_target = copy.deepcopy(target)
        evidence.build_change_plan(val, ev, target)
        self.assertEqual(val, orig_val)
        self.assertEqual(ev, orig_ev)
        self.assertEqual(target, orig_target)

    def test_readiness_with_results(self) -> None:
        profile = {
            "readiness_dimensions": ["accuracy", "completeness"],
            "readiness_results": {
                "accuracy": {"assessed": True, "note": "Verified"},
            },
        }
        plan = self._make_plan(profile=profile)
        r = plan["readiness"]
        self.assertFalse(r["complete"])  # completeness not assessed
        self.assertTrue(r["results"]["accuracy"]["assessed"])
        self.assertFalse(r["results"]["completeness"]["assessed"])

    def test_readiness_all_assessed(self) -> None:
        profile = {
            "readiness_dimensions": ["accuracy"],
            "readiness_results": {
                "accuracy": {"assessed": True, "note": "OK"},
            },
        }
        plan = self._make_plan(profile=profile)
        self.assertTrue(plan["readiness"]["complete"])

    def test_readiness_without_profile(self) -> None:
        plan = self._make_plan(profile=None)
        self.assertIsNone(plan["readiness"])

    def test_no_evidence_status(self) -> None:
        """Missing evidence → no_evidence, not 'missing'."""
        plan = self._make_plan(evidence_items=[])
        for inp in plan["inputs"]:
            self.assertEqual(inp["status"], "no_evidence")

    def test_evidence_refs_per_input(self) -> None:
        plan = self._make_plan()
        for inp in plan["inputs"]:
            if inp["status"] != "no_evidence":
                self.assertTrue(len(inp["evidence_refs"]) > 0)
                for er in inp["evidence_refs"]:
                    self.assertIn("pr_url", er)
                    self.assertIn("pr_status", er)

    def test_conflicting_pr_status(self) -> None:
        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": True,
            },
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": False,
            },
        ]
        plan = self._make_plan(evidence_items=items)
        conflicting = [
            i for i in plan["inputs"] if i["status"] == "conflicting"
        ]
        self.assertTrue(len(conflicting) > 0)

    def test_forbidden_profile_field(self) -> None:
        """D: Profile requesting forbidden field → finding."""
        profile = {
            "allowed_fields": [
                {"name": "labels", "value": "v4.19"},
            ],
        }
        plan = self._make_plan(profile=profile)
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
        ]
        self.assertTrue(len(forbidden) > 0)


# ---------------------------------------------------------------------------
# D: Enrichment check
# ---------------------------------------------------------------------------

class TestCheckEnrichment(unittest.TestCase):

    def _make_enrichment(
        self,
        *,
        existing_links: list[dict] | None = None,
        approved_baseline: str = "",
        plan_override: dict | None = None,
        current_key: str = "TEST-100",
    ) -> dict:
        if plan_override is not None:
            plan = plan_override
        else:
            snap = _make_docs_snapshot()
            val = evidence.validate_issue(snap)
            ev = evidence.normalize_evidence(_make_evidence_items())
            plan = evidence.build_change_plan(
                val, ev,
                {"release": "4.19", "target_branch": "main"},
            )
        snap = _make_docs_snapshot()
        current = {
            "key": current_key,
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": existing_links or [],
        }
        return evidence.check_enrichment(
            plan, current, approved_baseline
        )

    def test_new_links_eligible(self) -> None:
        r = self._make_enrichment()
        self.assertEqual(r["status"], "ready")
        self.assertTrue(len(r["eligible_links"]) > 0)

    def test_existing_link_detected(self) -> None:
        r = self._make_enrichment(
            existing_links=[
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
            ]
        )
        self.assertTrue(len(r["existing_links"]) > 0)

    def test_invalid_plan_rejected(self) -> None:
        """D: Invalid plan → no eligible writes."""
        plan = {
            "status": "invalid_issue",
            "errors": ["test"],
            "pr_links": [{"url": "https://github.example.invalid/org/repo/pull/1"}],
            "metadata": {},
            "plan_digest": "",
        }
        r = self._make_enrichment(plan_override=plan)
        self.assertEqual(r["status"], "invalid_plan")
        self.assertEqual(len(r["eligible_links"]), 0)
        self.assertTrue(r["stale"])

    def test_wrong_issue_rejected(self) -> None:
        """D: Current state key != plan key → wrong_issue."""
        r = self._make_enrichment(current_key="OTHER-999")
        self.assertEqual(r["status"], "wrong_issue")
        self.assertTrue(r["stale"])

    def test_baseline_drift_detected(self) -> None:
        """D: Approved baseline differs → stale."""
        r = self._make_enrichment(
            approved_baseline="old-fingerprint-that-wont-match"
        )
        self.assertTrue(r["stale"])
        self.assertEqual(r["status"], "stale")

    def test_no_baseline_not_stale(self) -> None:
        """No approved baseline → not stale."""
        r = self._make_enrichment()
        self.assertFalse(r["stale"])

    def test_forbidden_metadata_tamper_rejected(self) -> None:
        """D: Injecting forbidden metadata into plan → invalid (tampered)."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
        )
        plan["metadata"]["status"] = "Done"
        current = {"key": "TEST-100", "remote_links": []}
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["status"], "invalid_plan")
        self.assertIn("altered", r.get("reason", ""))

    def test_uncatalogued_metadata_tamper_rejected(self) -> None:
        """D: Injecting arbitrary key into plan metadata → invalid."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
        )
        plan["metadata"]["random_field"] = {"value": "x"}
        current = {"key": "TEST-100", "remote_links": []}
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["status"], "invalid_plan")

    def test_canonical_ordering_avoids_false_drift(self) -> None:
        """D: Link order alone shouldn't cause false drift."""
        r1 = self._make_enrichment(
            existing_links=[
                {"url": "https://github.example.invalid/org/repo/pull/1"},
                {"url": "https://github.example.invalid/org/repo/pull/2"},
            ]
        )
        r2 = self._make_enrichment(
            existing_links=[
                {"url": "https://github.example.invalid/org/repo/pull/2"},
                {"url": "https://github.example.invalid/org/repo/pull/1"},
            ]
        )
        self.assertEqual(
            r1["baseline_fingerprint"],
            r2["baseline_fingerprint"],
        )


# ---------------------------------------------------------------------------
# D: Verify enrichment (readback)
# ---------------------------------------------------------------------------

class TestVerifyEnrichment(unittest.TestCase):

    def _make_receipt(
        self,
        *,
        enrichment_status: str = "ready",
        eligible_urls: list[str] | None = None,
        existing_urls: list[str] | None = None,
        readback_urls: list[str] | None = None,
        readback_key: str = "TEST-100",
        expected_key: str = "TEST-100",
        eligible_metadata: dict | None = None,
        readback_fields: dict | None = None,
    ) -> dict:
        if eligible_urls is None:
            eligible_urls = [
                "https://github.example.invalid/org/repo/pull/101"
            ]
        enrichment = {
            "status": enrichment_status,
            "eligible_links": [{"url": u} for u in eligible_urls],
            "existing_links": [
                {"url": u} for u in (existing_urls or [])
            ],
            "eligible_metadata": eligible_metadata or {},
        }
        readback = {
            "key": readback_key,
            "remote_links": [
                {"url": u} for u in (readback_urls or [])
            ],
            "fields": readback_fields or {},
        }
        return evidence.verify_enrichment(
            enrichment, readback, expected_key
        )

    def test_confirmed_when_link_present(self) -> None:
        r = self._make_receipt(
            readback_urls=[
                "https://github.example.invalid/org/repo/pull/101"
            ]
        )
        self.assertTrue(r["all_confirmed"])
        self.assertEqual(r["link_receipts"][0]["status"], "confirmed")

    def test_uncertain_when_link_missing(self) -> None:
        r = self._make_receipt(readback_urls=[])
        self.assertFalse(r["all_confirmed"])
        self.assertEqual(r["link_receipts"][0]["status"], "uncertain")

    def test_wrong_readback_key(self) -> None:
        """D: Readback for wrong issue."""
        r = self._make_receipt(readback_key="WRONG-999")
        self.assertEqual(r["status"], "wrong_issue")
        self.assertFalse(r["all_confirmed"])

    def test_empty_eligible_not_success(self) -> None:
        """D: No operations to confirm → not all_confirmed."""
        r = self._make_receipt(
            eligible_urls=[], readback_urls=[]
        )
        self.assertFalse(r["all_confirmed"])

    def test_invalid_enrichment_rejected(self) -> None:
        r = self._make_receipt(enrichment_status="stale")
        self.assertEqual(r["status"], "invalid_enrichment")
        self.assertFalse(r["all_confirmed"])

    def test_metadata_receipt_confirmed(self) -> None:
        """Readback uses real Jira field (fixVersions) with catalog entry."""
        r = self._make_receipt(
            eligible_metadata={
                "target_release": {
                    "value": "v1",
                    "catalog_verified": True,
                    "catalog_entry": {"id": "7", "name": "v1"},
                    "jira_field": "fixVersions",
                },
            },
            readback_fields={
                "fixVersions": [{"id": "7", "name": "v1"}],
            },
            readback_urls=[
                "https://github.example.invalid/org/repo/pull/101"
            ],
        )
        meta = r["metadata_receipts"]
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["status"], "confirmed")
        self.assertEqual(meta[0]["jira_field"], "fixVersions")

    def test_metadata_receipt_different(self) -> None:
        """Readback shows different version ID → different_value."""
        r = self._make_receipt(
            eligible_metadata={
                "target_release": {
                    "value": "v1",
                    "catalog_verified": True,
                    "catalog_entry": {"id": "7", "name": "v1"},
                    "jira_field": "fixVersions",
                },
            },
            readback_fields={
                "fixVersions": [{"id": "99", "name": "v2"}],
            },
            readback_urls=[
                "https://github.example.invalid/org/repo/pull/101"
            ],
        )
        meta = r["metadata_receipts"]
        self.assertEqual(meta[0]["status"], "uncertain")

    def test_existing_link_disappearance_detected(self) -> None:
        r = self._make_receipt(
            eligible_urls=[],
            existing_urls=[
                "https://github.example.invalid/org/repo/pull/99"
            ],
            readback_urls=[],
        )
        existing_receipts = [
            lr for lr in r["link_receipts"]
            if lr["operation"] == "existing"
        ]
        self.assertEqual(
            existing_receipts[0]["status"], "disappeared"
        )


# ---------------------------------------------------------------------------
# Handoff rendering
# ---------------------------------------------------------------------------

class TestRenderHandoff(unittest.TestCase):

    def _make_rendered(self) -> str:
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
        )
        return evidence.render_handoff(plan)

    def test_deterministic(self) -> None:
        md1 = self._make_rendered()
        md2 = self._make_rendered()
        self.assertEqual(md1, md2)

    def test_contains_issue_key(self) -> None:
        self.assertIn("TEST-100", self._make_rendered())

    def test_contains_delivery_counts(self) -> None:
        md = self._make_rendered()
        self.assertIn("Total inputs:", md)

    def test_contains_metadata_proposals(self) -> None:
        md = self._make_rendered()
        self.assertIn("Metadata Proposals", md)
        self.assertIn("target_release", md)

    def test_contains_source_proposal_wording(self) -> None:
        """B: Source proposal shows proposed wording, not just reason."""
        md = self._make_rendered()
        self.assertIn("Source Change Proposal", md)
        self.assertIn("**Apply enabled:** False", md)

    def test_contains_evidence_links(self) -> None:
        md = self._make_rendered()
        self.assertIn("PR Remote Links", md)

    def test_shows_per_input_evidence_status(self) -> None:
        md = self._make_rendered()
        self.assertIn("merged_pr_exists", md)


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):

    def test_validate_valid(self) -> None:
        proc = _cli_run("validate", _make_docs_snapshot())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["valid"])

    def test_validate_invalid_exits_1(self) -> None:
        proc = _cli_run("validate", _make_docs_snapshot(key="bad"))
        self.assertEqual(proc.returncode, 1)
        result = json.loads(proc.stdout)
        self.assertFalse(result["valid"])

    def test_normalize_valid(self) -> None:
        proc = _cli_run("normalize", _make_evidence_items())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(len(result["items"]), 2)

    def test_normalize_invalid_exits_1(self) -> None:
        proc = _cli_run("normalize", [{"pr_url": "bad"}])
        self.assertEqual(proc.returncode, 1)

    def test_build_plan(self) -> None:
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        data = {
            "validation": val,
            "evidence": ev,
            "target": {"release": "4.19", "target_branch": "main"},
        }
        proc = _cli_run("build-plan", data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plan = json.loads(proc.stdout)
        self.assertEqual(plan["status"], "complete")

    def test_build_plan_invalid_exits_1(self) -> None:
        val = evidence.validate_issue(
            _make_docs_snapshot(key="bad")
        )
        ev = evidence.normalize_evidence([])
        data = {
            "validation": val,
            "evidence": ev,
            "target": {},
        }
        proc = _cli_run("build-plan", data)
        self.assertEqual(proc.returncode, 1)

    def test_check_enrichment(self) -> None:
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
        )
        data = {
            "plan": plan,
            "current_state": {
                "key": "TEST-100",
                "summary": snap["summary"],
                "description": snap["description"],
                "remote_links": [],
            },
        }
        proc = _cli_run("check-enrichment", data)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_check_enrichment_stale_exits_1(self) -> None:
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
        )
        data = {
            "plan": plan,
            "current_state": {
                "key": "TEST-100",
                "summary": snap["summary"],
                "description": snap["description"],
                "remote_links": [],
            },
            "approved_baseline": "stale-fingerprint",
        }
        proc = _cli_run("check-enrichment", data)
        self.assertEqual(proc.returncode, 1)

    def test_check_enrichment_with_readback(self) -> None:
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
        )
        data = {
            "plan": plan,
            "current_state": {
                "key": "TEST-100",
                "summary": snap["summary"],
                "description": snap["description"],
                "remote_links": [],
            },
        }
        readback = {
            "key": "TEST-100",
            "remote_links": [
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/102",
                },
            ],
            "fields": {"target_release": "4.19"},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(readback, f)
            rb_path = f.name
        try:
            proc = _cli_run(
                "check-enrichment", data,
                extra_args=["--readback", rb_path],
            )
        finally:
            os.unlink(rb_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["receipt"]["all_confirmed"])

    def test_validate_does_not_mutate_file(self) -> None:
        snap = _make_docs_snapshot()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(snap, f)
            f.flush()
            path = f.name
        try:
            original = Path(path).read_bytes()
            subprocess.run(
                [
                    sys.executable, "-I",
                    str(_SCRIPT_DIR / "evidence.py"),
                    "validate", "--input", path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            after = Path(path).read_bytes()
            self.assertEqual(original, after)
        finally:
            os.unlink(path)

    def test_bad_json_exits_1(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{bad json")
            f.flush()
            path = f.name
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-I",
                    str(_SCRIPT_DIR / "evidence.py"),
                    "validate", "--input", path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 1)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# E: End-to-end offline fixture
# ---------------------------------------------------------------------------

class TestEndToEndOffline(unittest.TestCase):
    """Representative writer-facing end-to-end test with offline fixture."""

    def test_full_pipeline_validate_normalize_plan_check_receipt(
        self,
    ) -> None:
        """Complete pipeline: validate → normalize → plan → check → receipt."""
        # 1. Validate
        snapshot = _make_docs_snapshot()
        val = evidence.validate_issue(snapshot)
        self.assertTrue(val["valid"])
        self.assertIn("TEST-201", val["contributors"])
        self.assertIn("TEST-202", val["contributors"])
        self.assertNotIn("TEST-300", val["contributors"])

        # 2. Normalize
        raw_evidence = _make_evidence_items()
        ev = evidence.normalize_evidence(raw_evidence)
        self.assertEqual(len(ev["items"]), 2)
        self.assertEqual(ev["errors"], [])

        # 3. Build plan
        target = {"release": "4.19", "target_branch": "main"}
        plan = evidence.build_change_plan(val, ev, target)
        self.assertEqual(plan["status"], "complete")
        self.assertEqual(plan["issue_key"], "TEST-100")

        # Verify honest per-input statuses
        for inp in plan["inputs"]:
            self.assertNotEqual(inp["status"], "delivered")
        merged_ok = [
            i for i in plan["inputs"]
            if i["status"] == "merged_pr_exists"
        ]
        merged_wrong = [
            i for i in plan["inputs"]
            if i["status"] == "merged_wrong_target"
        ]
        self.assertTrue(len(merged_ok) > 0)
        self.assertTrue(len(merged_wrong) > 0)

        # Only contributor PRs in links
        self.assertEqual(len(plan["pr_links"]), 2)

        # Metadata has target_release with catalog_verified=False
        self.assertIn("target_release", plan["metadata"])
        self.assertFalse(
            plan["metadata"]["target_release"]["catalog_verified"]
        )

        # Source proposal disabled
        self.assertFalse(plan["source_proposal"]["apply_enabled"])

        # 4. Check enrichment (pre-apply)
        current = {
            "key": "TEST-100",
            "summary": snapshot["summary"],
            "description": snapshot["description"],
            "remote_links": [],
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["status"], "ready")
        self.assertFalse(enrichment["stale"])
        self.assertEqual(len(enrichment["eligible_links"]), 2)
        baseline = enrichment["baseline_fingerprint"]

        # 5. Verify readback (post-apply)
        readback = {
            "key": "TEST-100",
            "summary": snapshot["summary"],
            "description": snapshot["description"],
            "remote_links": [
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/102",
                },
            ],
            "fields": {"target_release": "4.19"},
        }
        receipt = evidence.verify_enrichment(
            enrichment, readback, "TEST-100"
        )
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["all_confirmed"])
        self.assertEqual(len(receipt["link_receipts"]), 2)

        # 6. Re-check shows links as existing (idempotent)
        new_baseline = receipt["baseline_fingerprint"]
        enrichment2 = evidence.check_enrichment(
            plan, readback, new_baseline
        )
        # All links are now existing, none eligible
        self.assertFalse(enrichment2["stale"])
        self.assertEqual(len(enrichment2["eligible_links"]), 0)
        self.assertEqual(len(enrichment2["existing_links"]), 2)

        # 7. Render handoff
        md = evidence.render_handoff(plan)
        self.assertIn("TEST-100", md)
        self.assertIn("Delivery Summary", md)
        self.assertIn("Metadata Proposals", md)
        self.assertIn("Source Change Proposal", md)

    def test_pipeline_via_cli(self) -> None:
        """Pipeline exercised through CLI subcommands."""
        # validate
        snap = _make_docs_snapshot()
        p1 = _cli_run("validate", snap)
        self.assertEqual(p1.returncode, 0)
        val = json.loads(p1.stdout)

        # normalize
        p2 = _cli_run("normalize", _make_evidence_items())
        self.assertEqual(p2.returncode, 0)
        ev = json.loads(p2.stdout)

        # build-plan
        p3 = _cli_run("build-plan", {
            "validation": val,
            "evidence": ev,
            "target": {"release": "4.19", "target_branch": "main"},
        })
        self.assertEqual(p3.returncode, 0)
        plan = json.loads(p3.stdout)
        self.assertEqual(plan["status"], "complete")

        # check-enrichment
        p4 = _cli_run("check-enrichment", {
            "plan": plan,
            "current_state": {
                "key": "TEST-100",
                "summary": snap["summary"],
                "description": snap["description"],
                "remote_links": [],
            },
        })
        self.assertEqual(p4.returncode, 0)
        enrich = json.loads(p4.stdout)
        self.assertEqual(enrich["status"], "ready")

    def test_utf8_content(self) -> None:
        """UTF-8 content in description and observations."""
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Docs include Ünîcödé examples
            ## Documentation Scope
            Covers 日本語 configuration
            ## Documentation Inputs
            **TEST-201 — Ünîcödé config:**
            - New `widget config` with —name flag
            ## Design Reference
            Contributing stories: TEST-201
        """)
        snap = _make_docs_snapshot(description=desc)
        val = evidence.validate_issue(snap)
        self.assertTrue(val["valid"])

        items = [
            {
                "pr_url": "https://github.example.invalid/org/repo/pull/1",
                "contributor_key": "TEST-201",
                "merged": True,
                "observations": ["Adds 日本語 support"],
            },
        ]
        ev = evidence.normalize_evidence(items)
        self.assertEqual(len(ev["errors"]), 0)


# ---------------------------------------------------------------------------
# Contract 1: Identity, snapshot, baseline, digest
# ---------------------------------------------------------------------------

class TestSnapshotBaselineDigest(unittest.TestCase):
    """Contract 1: plan_digest verification, baseline includes metadata,
    missing identity fails, drift detection."""

    def _make_plan_and_enrichment(
        self, *, profile=None, current_fields=None,
    ):
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
            profile,
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
        }
        if current_fields is not None:
            current["fields"] = current_fields
        enrichment = evidence.check_enrichment(plan, current)
        return plan, enrichment, current

    def test_missing_current_key_invalid(self) -> None:
        """Missing current_state key → invalid, not pass."""
        plan, _, _ = self._make_plan_and_enrichment()
        r = evidence.check_enrichment(plan, {"remote_links": []})
        self.assertEqual(r["status"], "invalid")
        self.assertIn("missing", r["reason"])

    def test_missing_plan_key_invalid(self) -> None:
        """Missing plan issue_key → invalid_plan."""
        plan, _, _ = self._make_plan_and_enrichment()
        plan_no_key = {**plan, "issue_key": ""}
        # Must clear digest since we changed the plan
        plan_no_key["plan_digest"] = ""
        r = evidence.check_enrichment(
            plan_no_key, {"key": "TEST-100", "remote_links": []}
        )
        self.assertEqual(r["status"], "invalid_plan")

    def test_plan_digest_tamper_detected(self) -> None:
        """Altering plan content after creation → digest mismatch."""
        plan, _, _ = self._make_plan_and_enrichment()
        tampered = copy.deepcopy(plan)
        tampered["pr_links"].append({
            "url": "https://github.example.invalid/x/y/pull/999",
            "title": "injected",
        })
        r = evidence.check_enrichment(
            tampered,
            {"key": "TEST-100", "remote_links": []},
        )
        self.assertEqual(r["status"], "invalid_plan")
        self.assertIn("altered", r["reason"])

    def test_approved_plan_digest_detects_changed_plan(self) -> None:
        """approved_plan_digest catches a different plan (e.g. from
        changed description/contributor)."""
        plan1, enrichment1, current = self._make_plan_and_enrichment()
        digest1 = enrichment1["plan_digest"]
        baseline1 = enrichment1["baseline_fingerprint"]

        # Rebuild plan with changed contributor (affects plan digest)
        desc2 = _make_docs_snapshot()
        desc2["description"] = desc2["description"].replace(
            "TEST-202", "TEST-203"
        )
        val2 = evidence.validate_issue(desc2)
        ev2 = evidence.normalize_evidence(_make_evidence_items())
        plan2 = evidence.build_change_plan(
            val2, ev2,
            {"release": "v1", "target_branch": "main"},
        )

        # plan2 has different digest than plan1
        self.assertNotEqual(plan2["plan_digest"], plan1["plan_digest"])

        # Use plan2 but approved_plan_digest from plan1 → stale
        r = evidence.check_enrichment(
            plan2, current, baseline1, digest1,
        )
        self.assertTrue(r["stale"])
        self.assertEqual(r["status"], "stale")

    def test_metadata_in_baseline(self) -> None:
        """Metadata field change in current state → baseline drift."""
        plan, _, _ = self._make_plan_and_enrichment(
            current_fields={"fixVersions": []},
        )
        snap = _make_docs_snapshot()
        current_v0 = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        r1 = evidence.check_enrichment(plan, current_v0)
        baseline = r1["baseline_fingerprint"]

        # Now fixVersions changed in Jira
        current_v1 = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {
                "fixVersions": [{"id": "99", "name": "other"}],
            },
        }
        r2 = evidence.check_enrichment(plan, current_v1, baseline)
        self.assertTrue(r2["stale"])

    def test_missing_readback_key_invalid(self) -> None:
        """verify_enrichment: missing readback key → invalid."""
        plan, enrichment, _ = self._make_plan_and_enrichment()
        readback = {"remote_links": [], "fields": {}}
        receipt = evidence.verify_enrichment(
            enrichment, readback, "TEST-100"
        )
        self.assertEqual(receipt["status"], "invalid")
        self.assertFalse(receipt["all_confirmed"])

    def test_reordered_links_no_false_drift(self) -> None:
        """Link reordering alone does not cause false drift."""
        plan, _, _ = self._make_plan_and_enrichment()
        snap = _make_docs_snapshot()
        current_a = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [
                {"url": "https://github.example.invalid/o/r/pull/1"},
                {"url": "https://github.example.invalid/o/r/pull/2"},
            ],
            "fields": {"fixVersions": []},
        }
        current_b = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [
                {"url": "https://github.example.invalid/o/r/pull/2"},
                {"url": "https://github.example.invalid/o/r/pull/1"},
            ],
            "fields": {"fixVersions": []},
        }
        r_a = evidence.check_enrichment(plan, current_a)
        r_b = evidence.check_enrichment(plan, current_b)
        self.assertEqual(
            r_a["baseline_fingerprint"],
            r_b["baseline_fingerprint"],
        )


# ---------------------------------------------------------------------------
# Contract 2: Metadata catalog, real field binding, before/after
# ---------------------------------------------------------------------------

class TestMetadataCatalogV1(unittest.TestCase):
    """Contract 2: real fixVersions binding, catalog_verified gates
    eligibility, readback with Jira field shapes."""

    def _make_plan(self, *, profile=None, target=None):
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        if target is None:
            target = {"release": "v1", "target_branch": "main"}
        return evidence.build_change_plan(val, ev, target, profile)

    def test_default_metadata_has_real_binding(self) -> None:
        """target_release has jira_field=fixVersions, not placeholder."""
        plan = self._make_plan()
        tr = plan["metadata"]["target_release"]
        self.assertEqual(tr["jira_field"], "fixVersions")
        self.assertEqual(tr["jira_field_type"], "array")
        self.assertFalse(tr["catalog_verified"])
        self.assertIsNone(tr["catalog_entry"])

    def test_uncatalogued_not_eligible(self) -> None:
        """catalog_verified=False → not eligible for write."""
        plan = self._make_plan()
        snap = _make_docs_snapshot()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_catalog_verified_eligible(self) -> None:
        """catalog_verified=True + catalog_entry → eligible."""
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        plan = self._make_plan(profile=profile)
        tr = plan["metadata"]["target_release"]
        self.assertTrue(tr["catalog_verified"])
        self.assertEqual(tr["catalog_entry"], {"id": "7", "name": "v1"})
        self.assertEqual(tr["before"], [])

        snap = _make_docs_snapshot()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertIn("target_release", r["eligible_metadata"])

    def test_full_metadata_lifecycle(self) -> None:
        """Full lifecycle: preview → receipt with real Jira shapes."""
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        plan = self._make_plan(profile=profile)
        snap = _make_docs_snapshot()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["status"], "ready")
        self.assertIn("target_release", enrichment["eligible_metadata"])

        # Readback with real Jira field shape
        readback = {
            "key": "TEST-100",
            "remote_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
                {"url": "https://github.example.invalid/org/repo/pull/102"},
            ],
            "fields": {
                "fixVersions": [{"id": "7", "name": "v1"}],
            },
        }
        receipt = evidence.verify_enrichment(
            enrichment, readback, "TEST-100"
        )
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["all_confirmed"])
        meta_r = receipt["metadata_receipts"]
        self.assertEqual(len(meta_r), 1)
        self.assertEqual(meta_r[0]["jira_field"], "fixVersions")
        self.assertEqual(meta_r[0]["status"], "confirmed")

    def test_readback_missing_field_uncertain(self) -> None:
        """Readback without fixVersions → uncertain, not confirmed."""
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        plan = self._make_plan(profile=profile)
        snap = _make_docs_snapshot()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        enrichment = evidence.check_enrichment(plan, current)
        readback = {
            "key": "TEST-100",
            "remote_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
                {"url": "https://github.example.invalid/org/repo/pull/102"},
            ],
            "fields": {},
        }
        receipt = evidence.verify_enrichment(
            enrichment, readback, "TEST-100"
        )
        self.assertFalse(receipt["all_confirmed"])

    def test_forbidden_field_alias_blocked(self) -> None:
        """Profile attempting 'fixversions' directly → forbidden."""
        profile = {
            "allowed_fields": [{
                "name": "fixversions",
                "value": "v1",
                "catalog_verified": True,
            }],
        }
        plan = self._make_plan(profile=profile)
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
        ]
        self.assertTrue(
            any(f["ref"] == "fixversions" for f in forbidden)
        )

    def test_drift_after_approval(self) -> None:
        """After approval, description change → stale."""
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        plan1 = self._make_plan(profile=profile)
        snap = _make_docs_snapshot()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        e1 = evidence.check_enrichment(plan1, current)
        baseline = e1["baseline_fingerprint"]
        digest = e1["plan_digest"]

        # Rebuild plan with changed contributor (affects plan digest)
        desc2 = _make_docs_snapshot()
        desc2["description"] = desc2["description"].replace(
            "TEST-202", "TEST-203"
        )
        val2 = evidence.validate_issue(desc2)
        ev2 = evidence.normalize_evidence(_make_evidence_items())
        plan2 = evidence.build_change_plan(
            val2, ev2,
            {"release": "v1", "target_branch": "main"},
            profile,
        )
        e2 = evidence.check_enrichment(plan2, current, baseline, digest)
        self.assertTrue(e2["stale"])


# ---------------------------------------------------------------------------
# Contract 3: Evidence error propagation, key format validation
# ---------------------------------------------------------------------------

class TestEvidenceErrorPropagation(unittest.TestCase):
    """Contract 3: evidence errors block operations, invalid key
    format rejected, structurally invalid inputs rejected."""

    def test_evidence_errors_block_plan(self) -> None:
        """Evidence with errors → invalid_evidence, no eligible ops."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        evidence_with_errors = {
            "items": [],
            "errors": ["evidence[0]: invalid PR URL"],
            "warnings": [],
        }
        plan = evidence.build_change_plan(
            val, evidence_with_errors,
            {"release": "v1", "target_branch": "main"},
        )
        self.assertEqual(plan["status"], "invalid_evidence")
        self.assertEqual(plan["pr_links"], [])

    def test_invalid_key_format_rejected(self) -> None:
        """Issue key failing format check → invalid_issue."""
        val = {
            "valid": True,
            "errors": [],
            "key": "bad-key",
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")

    def test_missing_key_rejected(self) -> None:
        """Empty issue key → invalid_issue."""
        val = {
            "valid": True,
            "errors": [],
            "key": "",
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")


# ---------------------------------------------------------------------------
# Contract 4: No prose-keyword semantics, input-specific observations
# ---------------------------------------------------------------------------

class TestSourceProposalSemantics(unittest.TestCase):
    """Contract 4: observations are display-only, no keyword-based
    inference, input-specific mapping."""

    def _make_plan(self, evidence_items, snapshot=None):
        if snapshot is None:
            snapshot = _make_docs_snapshot()
        val = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(evidence_items)
        return evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
        )

    def test_confirmed_text_not_silently_excluded(self) -> None:
        """Text containing 'confirmed' is NOT excluded from review."""
        items = [{
            "pr_url": (
                "https://github.example.invalid/org/repo/pull/1"
            ),
            "contributor_key": "TEST-201",
            "merged": True,
            "observations": [
                "Confirmed that retries defaults to 10 instead of 3"
            ],
        }]
        plan = self._make_plan(items)
        reviews = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "review"
        ]
        self.assertTrue(len(reviews) > 0)
        self.assertIn(
            "Confirmed that retries defaults to 10 instead of 3",
            reviews[0]["observations"],
        )

    def test_arbitrary_text_no_update_proposal(self) -> None:
        """Arbitrary observation text does not produce 'update' proposals."""
        items = [{
            "pr_url": (
                "https://github.example.invalid/org/repo/pull/1"
            ),
            "contributor_key": "TEST-201",
            "merged": True,
            "observations": ["The sky is blue today"],
        }]
        plan = self._make_plan(items)
        updates = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "update"
        ]
        self.assertEqual(len(updates), 0)

    def test_observations_tied_to_specific_input(self) -> None:
        """PR observations for TEST-201 do not leak to TEST-202."""
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
                "observations": ["Added --format flag"],
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/2"
                ),
                "contributor_key": "TEST-202",
                "merged": True,
                "observations": ["Status endpoint works"],
            },
        ]
        plan = self._make_plan(items)
        reviews = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "review"
        ]
        for r in reviews:
            if r["contributor"] == "TEST-201":
                self.assertIn("Added --format flag", r["observations"])
                self.assertNotIn(
                    "Status endpoint works", r["observations"]
                )
            elif r["contributor"] == "TEST-202":
                self.assertIn(
                    "Status endpoint works", r["observations"]
                )
                self.assertNotIn(
                    "Added --format flag", r["observations"]
                )

    def test_input_header_not_in_contributors_mismatch(self) -> None:
        """Doc input header for unlisted contributor → mismatch finding,
        NOT automatic eligible link."""
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Some scope
            ## Documentation Inputs
            **TEST-201 — Add widget:**
            - New CLI command
            **TEST-999 — Unlisted feature:**
            - Some extra feature
            ## Design Reference
            Contributing stories: TEST-201
        """)
        snap = _make_docs_snapshot(description=desc)
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/999"
                ),
                "contributor_key": "TEST-999",
            },
        ]
        plan = self._make_plan(items, snapshot=snap)
        mismatch = [
            f for f in plan["findings"]
            if f["type"] == "input_contributor_mismatch"
        ]
        self.assertTrue(
            any(f["ref"] == "TEST-999" for f in mismatch),
            "Unlisted input header should produce mismatch finding",
        )
        # TEST-999 PR should NOT be in eligible links
        link_urls = {l["url"] for l in plan["pr_links"]}
        self.assertNotIn(
            "https://github.example.invalid/org/repo/pull/999",
            link_urls,
        )

    def test_contributor_coverage_independent_of_inputs(self) -> None:
        """Contributor with evidence but no parsed input header should
        still have their evidence recognized, not falsely flagged as
        missing."""
        desc = textwrap.dedent("""\
            ## Acceptance Criteria
            - [ ] Something
            ## Documentation Scope
            Some scope
            ## Documentation Inputs
            **TEST-201 — Add widget:**
            - New CLI command
            ## Design Reference
            Contributing stories: TEST-201, TEST-202
        """)
        snap = _make_docs_snapshot(description=desc)
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/2"
                ),
                "contributor_key": "TEST-202",
                "merged": True,
            },
        ]
        plan = self._make_plan(items, snapshot=snap)
        # TEST-202 has evidence, so should NOT be flagged as missing
        missing = [
            f for f in plan["findings"]
            if f["type"] == "missing_evidence"
            and f["ref"] == "TEST-202"
        ]
        self.assertEqual(
            len(missing), 0,
            "TEST-202 has evidence; should not be flagged missing",
        )
        # TEST-202 PR should be in eligible links (declared contributor)
        link_urls = {l["url"] for l in plan["pr_links"]}
        self.assertIn(
            "https://github.example.invalid/org/repo/pull/2",
            link_urls,
        )

    def test_no_update_action_exists(self) -> None:
        """No 'update' actions are produced — only 'review' or
        'add_contributor'."""
        plan = self._make_plan(_make_evidence_items())
        for c in plan["source_proposal"]["proposed_changes"]:
            self.assertIn(c["action"], ("review", "add_contributor"))


# ---------------------------------------------------------------------------
# Contract 5: Full offline fixture lifecycle
# ---------------------------------------------------------------------------

class TestContractFullLifecycle(unittest.TestCase):
    """Contract 5: raw-snapshot → plan → check → metadata/link receipt.
    This test must fail against the 0dfb code."""

    def test_full_catalog_metadata_lifecycle(self) -> None:
        """Complete lifecycle with catalog-verified metadata."""
        # 1. Valid snapshot + catalog entry
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
            profile,
        )
        self.assertEqual(plan["status"], "complete")
        tr = plan["metadata"]["target_release"]
        self.assertEqual(tr["jira_field"], "fixVersions")
        self.assertTrue(tr["catalog_verified"])
        self.assertEqual(tr["catalog_entry"]["id"], "7")

        # 2. Preview: empty fixVersions → eligible
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["status"], "ready")
        self.assertIn("target_release", enrichment["eligible_metadata"])
        self.assertTrue(len(enrichment["eligible_links"]) > 0)
        baseline = enrichment["baseline_fingerprint"]
        digest = enrichment["plan_digest"]

        # 3. After approval, same URLs but contributor change → stale
        desc2 = snap.copy()
        desc2["description"] = snap["description"].replace(
            "TEST-202", "TEST-203"
        )
        val2 = evidence.validate_issue(desc2)
        ev2 = evidence.normalize_evidence(_make_evidence_items())
        plan2 = evidence.build_change_plan(
            val2, ev2,
            {"release": "v1", "target_branch": "main"},
            profile,
        )
        e2 = evidence.check_enrichment(
            plan2, current, baseline, digest,
        )
        self.assertTrue(e2["stale"])

        # 4. Altered metadata in plan → invalid
        tampered = copy.deepcopy(plan)
        tampered["metadata"]["target_release"]["value"] = "v99"
        e3 = evidence.check_enrichment(tampered, current)
        self.assertEqual(e3["status"], "invalid_plan")

        # 5. Missing current key → invalid
        e4 = evidence.check_enrichment(
            plan, {"remote_links": []}
        )
        self.assertEqual(e4["status"], "invalid")

        # 6. Readback with real Jira shape → confirmed
        readback = {
            "key": "TEST-100",
            "remote_links": [
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/102",
                },
            ],
            "fields": {
                "fixVersions": [{"id": "7", "name": "v1"}],
            },
        }
        receipt = evidence.verify_enrichment(
            enrichment, readback, "TEST-100"
        )
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["all_confirmed"])
        meta_r = receipt["metadata_receipts"]
        self.assertEqual(meta_r[0]["jira_field"], "fixVersions")
        self.assertEqual(meta_r[0]["status"], "confirmed")

        # 7. Readback with different version → not all_confirmed
        readback_diff = {
            "key": "TEST-100",
            "remote_links": readback["remote_links"],
            "fields": {
                "fixVersions": [{"id": "99", "name": "v2"}],
            },
        }
        receipt2 = evidence.verify_enrichment(
            enrichment, readback_diff, "TEST-100"
        )
        self.assertFalse(receipt2["all_confirmed"])

        # 8. Reordered links → no false conflict
        current_a = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/102",
                },
            ],
            "fields": {"fixVersions": []},
        }
        current_b = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/102",
                },
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
            ],
            "fields": {"fixVersions": []},
        }
        ea = evidence.check_enrichment(plan, current_a)
        eb = evidence.check_enrichment(plan, current_b)
        self.assertEqual(
            ea["baseline_fingerprint"],
            eb["baseline_fingerprint"],
        )

    def test_cli_full_pipeline(self) -> None:
        """CLI pipeline: validate → normalize → build-plan →
        check-enrichment with catalog metadata."""
        snap = _make_docs_snapshot()
        p1 = _cli_run("validate", snap)
        self.assertEqual(p1.returncode, 0)
        val = json.loads(p1.stdout)

        p2 = _cli_run("normalize", _make_evidence_items())
        self.assertEqual(p2.returncode, 0)
        ev = json.loads(p2.stdout)

        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        p3 = _cli_run("build-plan", {
            "validation": val,
            "evidence": ev,
            "target": {"release": "v1", "target_branch": "main"},
            "profile": profile,
        })
        self.assertEqual(p3.returncode, 0)
        plan = json.loads(p3.stdout)
        self.assertEqual(plan["status"], "complete")
        self.assertIn("target_release", plan["metadata"])
        self.assertEqual(
            plan["metadata"]["target_release"]["jira_field"],
            "fixVersions",
        )

        p4 = _cli_run("check-enrichment", {
            "plan": plan,
            "current_state": {
                "key": "TEST-100",
                "summary": snap["summary"],
                "description": snap["description"],
                "remote_links": [],
                "fields": {"fixVersions": []},
            },
        })
        self.assertEqual(p4.returncode, 0, p4.stderr)
        enrich = json.loads(p4.stdout)
        self.assertEqual(enrich["status"], "ready")
        self.assertIn("target_release", enrich["eligible_metadata"])

    def test_evidence_errors_block_cli(self) -> None:
        """CLI build-plan with evidence errors → exit 1."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        data = {
            "validation": val,
            "evidence": {
                "items": [],
                "errors": ["evidence[0]: invalid URL"],
                "warnings": [],
            },
            "target": {},
        }
        proc = _cli_run("build-plan", data)
        self.assertEqual(proc.returncode, 1)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "invalid_evidence")


# ---------------------------------------------------------------------------
# Contract 6: Writer/snapshot drift without rebuilding plan
# ---------------------------------------------------------------------------

class TestWriterDriftRegression(unittest.TestCase):
    """Contract: same plan + approved digest, edit current description
    only → stale, no eligible apply.  Do NOT rebuild plan."""

    def test_description_edit_same_plan_stale(self) -> None:
        """Build once, approve once, edit current description text only,
        same plan + approved digest → stale, no eligible writes."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
        )
        current_original = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        preview = evidence.check_enrichment(plan, current_original)
        self.assertEqual(preview["status"], "ready")
        baseline = preview["baseline_fingerprint"]
        digest = preview["plan_digest"]

        # Writer edits description in Jira — same plan, same approved
        # digest.  Fresh snapshot fingerprint comparison detects drift.
        changed = copy.deepcopy(current_original)
        changed["description"] = changed["description"].replace(
            "TEST-202", "TEST-203"
        )
        apply_result = evidence.check_enrichment(
            plan, changed, baseline, digest,
        )
        self.assertTrue(apply_result["stale"])
        self.assertEqual(apply_result["eligible_links"], [])
        self.assertEqual(apply_result["eligible_metadata"], {})

        # Control: original current_state is still ready
        control = evidence.check_enrichment(
            plan, current_original, baseline, digest,
        )
        self.assertFalse(control["stale"])
        self.assertEqual(control["status"], "ready")

    def test_empty_plan_digest_invalid(self) -> None:
        """Empty plan_digest is invalid — no bypass."""
        plan = {
            "status": "complete",
            "issue_key": "TEST-100",
            "target": {},
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "snapshot_fingerprint": "non-empty-for-digest-test",
            "plan_digest": "",
        }
        r = evidence.check_enrichment(
            plan, {"key": "TEST-100", "remote_links": []}
        )
        self.assertEqual(r["status"], "invalid_plan")
        self.assertIn("no digest", r["reason"])


# ---------------------------------------------------------------------------
# Contract 7: Additive metadata payload, version validation
# ---------------------------------------------------------------------------

class TestAdditiveMetadataPayload(unittest.TestCase):
    """Contract: metadata payload preserves existing versions, validates
    catalog entry schema, readback confirms full set."""

    def _make_plan_with_catalog(
        self, *, before=None, entry=None, value="v1",
    ):
        if entry is None:
            entry = {"id": "7", "name": "v1"}
        if before is None:
            before = []
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": value,
                "catalog_verified": True,
                "catalog_entry": entry,
                "before": before,
            }],
        }
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        return evidence.build_change_plan(
            val, ev,
            {"release": value, "target_branch": "main"},
            profile,
        )

    def test_additive_payload_preserves_existing(self) -> None:
        """before=[{id:'3',name:'v0'}] + v1 → payload has both IDs."""
        snap = _make_docs_snapshot()
        plan = self._make_plan_with_catalog(
            before=[{"id": "3", "name": "v0"}],
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"id": "3", "name": "v0"}]},
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["status"], "ready")
        em = enrichment["eligible_metadata"]["target_release"]
        payload = em["jira_payload"]["fixVersions"]
        payload_ids = {p["id"] for p in payload}
        self.assertIn("3", payload_ids, "existing v0 preserved")
        self.assertIn("7", payload_ids, "new v1 added")
        self.assertEqual(sorted(em["expected_ids"]), ["3", "7"])

    def test_before_omitted_uses_actual_field_state(self) -> None:
        """before=[] in profile but actual field has versions → additive."""
        snap = _make_docs_snapshot()
        plan = self._make_plan_with_catalog(
            before=[],
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"id": "3", "name": "v0"}]},
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["status"], "ready")
        em = enrichment["eligible_metadata"]["target_release"]
        payload = em["jira_payload"]["fixVersions"]
        payload_ids = {p["id"] for p in payload}
        self.assertIn("3", payload_ids, "existing v0 from actual state")
        self.assertIn("7", payload_ids, "new v1 added")
        self.assertEqual(sorted(em["expected_ids"]), ["3", "7"])

    def test_already_present_version_noop(self) -> None:
        """Version already in before → already_present, no extra write."""
        snap = _make_docs_snapshot()
        plan = self._make_plan_with_catalog(
            before=[{"id": "7", "name": "v1"}],
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"id": "7", "name": "v1"}]},
        }
        enrichment = evidence.check_enrichment(plan, current)
        em = enrichment["eligible_metadata"]["target_release"]
        self.assertTrue(em["already_present"])

    def test_malformed_entry_no_id_rejected(self) -> None:
        """catalog_entry missing id → not eligible."""
        snap = _make_docs_snapshot()
        plan = self._make_plan_with_catalog(
            entry={"name": "v1"},
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["eligible_metadata"], {})

    def test_entry_name_mismatch_rejected(self) -> None:
        """catalog_entry name != requested value → not eligible."""
        snap = _make_docs_snapshot()
        plan = self._make_plan_with_catalog(
            entry={"id": "7", "name": "v2"},
            value="v1",
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["eligible_metadata"], {})

    def test_readback_confirms_full_set(self) -> None:
        """Readback must contain ALL expected IDs, not just new one."""
        snap = _make_docs_snapshot()
        plan = self._make_plan_with_catalog(
            before=[{"id": "3", "name": "v0"}],
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"id": "3", "name": "v0"}]},
        }
        enrichment = evidence.check_enrichment(plan, current)
        # Readback has both versions → confirmed
        readback_ok = {
            "key": "TEST-100",
            "remote_links": [
                {"url": "https://github.example.invalid/org/repo/pull/101"},
                {"url": "https://github.example.invalid/org/repo/pull/102"},
            ],
            "fields": {
                "fixVersions": [
                    {"id": "3", "name": "v0"},
                    {"id": "7", "name": "v1"},
                ],
            },
        }
        receipt = evidence.verify_enrichment(
            enrichment, readback_ok, "TEST-100"
        )
        self.assertTrue(receipt["all_confirmed"])
        self.assertEqual(
            receipt["metadata_receipts"][0]["status"], "confirmed"
        )

        # Readback missing old version → partial, not confirmed
        readback_missing = {
            "key": "TEST-100",
            "remote_links": readback_ok["remote_links"],
            "fields": {
                "fixVersions": [{"id": "7", "name": "v1"}],
            },
        }
        receipt2 = evidence.verify_enrichment(
            enrichment, readback_missing, "TEST-100"
        )
        self.assertFalse(receipt2["all_confirmed"])
        self.assertEqual(
            receipt2["metadata_receipts"][0]["status"], "partial"
        )


# ---------------------------------------------------------------------------
# Guard 1: Source context propagation through validate→build→check chain
# ---------------------------------------------------------------------------

class TestSourceContextPropagation(unittest.TestCase):
    """Guard: validate propagates key+summary+raw description; builder
    requires source context (valid:true alone is insufficient); check
    compares same source projection."""

    def test_validate_returns_summary_and_description(self) -> None:
        """validate_issue output includes raw summary and description."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        self.assertEqual(val["summary"], snap["summary"])
        self.assertEqual(val["description"], snap["description"])

    def test_validate_invalid_returns_summary(self) -> None:
        """Even invalid snapshots propagate the summary they had."""
        snap = _make_docs_snapshot(description="")
        val = evidence.validate_issue(snap)
        self.assertFalse(val["valid"])
        self.assertEqual(val["summary"], snap["summary"])
        self.assertEqual(val["description"], "")

    def test_builder_rejects_missing_summary(self) -> None:
        """build_change_plan rejects validation without summary."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        del val["summary"]  # remove source context
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev, {"release": "v1", "target_branch": "main"},
        )
        self.assertEqual(plan["status"], "invalid_issue")
        self.assertTrue(
            any("summary" in e for e in plan["errors"])
        )

    def test_builder_rejects_missing_description(self) -> None:
        """build_change_plan rejects validation without description."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        del val["description"]
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev, {"release": "v1", "target_branch": "main"},
        )
        self.assertEqual(plan["status"], "invalid_issue")
        self.assertTrue(
            any("description" in e for e in plan["errors"])
        )

    def test_builder_rejects_valid_true_empty_summary(self) -> None:
        """Fabricated valid:true with empty summary → rejected."""
        val = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "key": "TEST-100",
            "summary": "",
            "description": "some desc",
            "contributors": ["TEST-201"],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = evidence.normalize_evidence([])
        plan = evidence.build_change_plan(
            val, ev, {"release": "v1", "target_branch": "main"},
        )
        self.assertEqual(plan["status"], "invalid_issue")

    def test_summary_change_detected_as_stale(self) -> None:
        """Summary edit between plan and check → stale."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev, {"release": "v1", "target_branch": "main"},
        )
        # Check with original → ready
        current_ok = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
        }
        r1 = evidence.check_enrichment(plan, current_ok)
        self.assertFalse(r1["stale"])

        # Check with changed summary → stale
        current_changed = {
            "key": "TEST-100",
            "summary": "[DOCS] Changed summary text",
            "description": snap["description"],
            "remote_links": [],
        }
        r2 = evidence.check_enrichment(plan, current_changed)
        self.assertTrue(r2["stale"])

    def test_raw_description_outside_sections_detected(self) -> None:
        """Edit to description text outside parsed sections → stale."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev, {"release": "v1", "target_branch": "main"},
        )
        # Modify text that's outside any ## section (preamble)
        modified_desc = "Preamble change\n" + snap["description"]
        current_changed = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": modified_desc,
            "remote_links": [],
        }
        r = evidence.check_enrichment(plan, current_changed)
        self.assertTrue(r["stale"])
        self.assertEqual(r["eligible_links"], [])


# ---------------------------------------------------------------------------
# Guard 2: Missing/malformed fixVersions fail-closed
# ---------------------------------------------------------------------------

class TestFixVersionsFailClosed(unittest.TestCase):
    """Guard: unknown/malformed fixVersions MUST NOT become empty
    removable state.  Explicit empty [] is legitimate."""

    def _make_catalog_plan(self):
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "v1",
                "catalog_verified": True,
                "catalog_entry": {"id": "7", "name": "v1"},
                "before": [],
            }],
        }
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
            profile,
        )
        return snap, plan

    def test_missing_fields_key_fail_closed(self) -> None:
        """current_state with no 'fields' key → no metadata eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            # No 'fields' at all
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_missing_fixversions_field_fail_closed(self) -> None:
        """fields dict without fixVersions key → no metadata eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"someOtherField": "value"},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_null_fixversions_fail_closed(self) -> None:
        """fixVersions: null → no metadata eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": None},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_non_list_fixversions_fail_closed(self) -> None:
        """fixVersions: 'string' → no metadata eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": "v1"},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_malformed_entry_no_id_fail_closed(self) -> None:
        """fixVersions entry without 'id' → no metadata eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"name": "v0"}]},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_malformed_non_dict_entry_fail_closed(self) -> None:
        """fixVersions entry that's a string → no metadata eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": ["v0"]},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertEqual(r["eligible_metadata"], {})

    def test_explicit_empty_list_positive(self) -> None:
        """fixVersions: [] is legitimate — metadata IS eligible."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        r = evidence.check_enrichment(plan, current)
        self.assertIn("target_release", r["eligible_metadata"])
        em = r["eligible_metadata"]["target_release"]
        self.assertEqual(em["expected_ids"], ["7"])

    def test_actual_v0_id3_plus_catalog_v1_id7(self) -> None:
        """actual=[{id:3}] + catalog id7 → payload has 3+7."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"id": "3", "name": "v0"}]},
        }
        r = evidence.check_enrichment(plan, current)
        em = r["eligible_metadata"]["target_release"]
        payload_ids = {p["id"] for p in em["jira_payload"]["fixVersions"]}
        self.assertEqual(payload_ids, {"3", "7"})
        self.assertEqual(sorted(em["expected_ids"]), ["3", "7"])
        self.assertFalse(em["already_present"])

    def test_already_present_noop(self) -> None:
        """actual=[{id:7}] + catalog id7 → already_present, same payload."""
        snap, plan = self._make_catalog_plan()
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [],
            "fields": {"fixVersions": [{"id": "7", "name": "v1"}]},
        }
        r = evidence.check_enrichment(plan, current)
        em = r["eligible_metadata"]["target_release"]
        self.assertTrue(em["already_present"])
        payload_ids = {p["id"] for p in em["jira_payload"]["fixVersions"]}
        self.assertEqual(payload_ids, {"7"})


# ---------------------------------------------------------------------------
# Review contracts: PR URL HTTPS-only and canonical casing (R3)
# ---------------------------------------------------------------------------

class TestPrUrlHttpsAndCasing(unittest.TestCase):
    """R3: PR URLs require HTTPS; canonical scheme+host lowercase,
    preserve path case; HTTP rejected not eligible."""

    def test_pr_url_rejects_http(self) -> None:
        """HTTP PR URL → rejected (HTTPS required for forges)."""
        with self.assertRaises(ValueError) as ctx:
            evidence.validate_pr_url(
                "http://github.example.invalid/org/repo/pull/42"
            )
        self.assertIn("https", str(ctx.exception).lower())

    def test_generic_url_allows_http(self) -> None:
        """Generic validate_url still accepts HTTP."""
        r = evidence.validate_url(
            "http://github.example.invalid/org/repo"
        )
        self.assertEqual(
            r, "http://github.example.invalid/org/repo"
        )

    def test_pr_url_canonical_uppercase_host(self) -> None:
        """Uppercase host is canonicalized to lowercase."""
        r = evidence.validate_pr_url(
            "HTTPS://GITHUB.EXAMPLE.INVALID/org/repo/pull/42"
        )
        self.assertEqual(
            r,
            "https://github.example.invalid/org/repo/pull/42",
        )

    def test_canonical_casing_dedup(self) -> None:
        """Same PR with different host casing → deduplicated."""
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
            },
            {
                "pr_url": (
                    "HTTPS://GITHUB.EXAMPLE.INVALID/org/repo/pull/1"
                ),
                "contributor_key": "TEST-202",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 1)
        self.assertIn("TEST-201", r["items"][0]["contributor_keys"])
        self.assertIn("TEST-202", r["items"][0]["contributor_keys"])

    def test_path_case_preserved(self) -> None:
        """Path case is preserved (only scheme+host lowered)."""
        r = evidence.validate_pr_url(
            "https://github.example.invalid/Org/Repo/pull/42"
        )
        self.assertIn("/Org/Repo/pull/42", r)

    def test_existing_link_uppercase_host_matches(self) -> None:
        """Existing Remote Link with uppercase host matches proposed."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
        )
        current = {
            "key": "TEST-100",
            "summary": snap["summary"],
            "description": snap["description"],
            "remote_links": [
                {
                    "url": (
                        "HTTPS://GITHUB.EXAMPLE.INVALID"
                        "/org/repo/pull/101"
                    ),
                },
            ],
        }
        r = evidence.check_enrichment(plan, current)
        self.assertTrue(
            len(r["existing_links"]) >= 1,
            "Uppercase host link should match as existing",
        )


# ---------------------------------------------------------------------------
# Review contracts: Nullable target_branch (R4)
# ---------------------------------------------------------------------------

class TestNullableTargetBranch(unittest.TestCase):
    """R4: JSON null → empty string, non-string → clear error;
    duplicate backfill without losing data."""

    def test_null_target_branch_becomes_empty(self) -> None:
        """target_branch: null → empty string, not literal 'None'."""
        items = [{
            "pr_url": (
                "https://github.example.invalid/org/repo/pull/1"
            ),
            "contributor_key": "TEST-201",
            "target_branch": None,
        }]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["target_branch"], "")
        self.assertNotEqual(r["items"][0]["target_branch"], "None")

    def test_non_string_target_branch_rejected(self) -> None:
        """target_branch: 42 → error."""
        items = [{
            "pr_url": (
                "https://github.example.invalid/org/repo/pull/1"
            ),
            "contributor_key": "TEST-201",
            "target_branch": 42,
        }]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)
        self.assertTrue(
            any("target_branch" in e for e in r["errors"])
        )

    def test_list_target_branch_rejected(self) -> None:
        """target_branch: [1, 2] → error."""
        items = [{
            "pr_url": (
                "https://github.example.invalid/org/repo/pull/1"
            ),
            "contributor_key": "TEST-201",
            "target_branch": ["main"],
        }]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 0)

    def test_duplicate_backfill_missing_merged(self) -> None:
        """Later record fills missing merged without conflict."""
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": None,
                "target_branch": "",
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
                "target_branch": "main",
                "title": "feat: add widget",
                "state": "merged",
                "merge_commit": "abc123",
            },
        ]
        r = evidence.normalize_evidence(items)
        self.assertEqual(len(r["items"]), 1)
        item = r["items"][0]
        self.assertTrue(item["merged"])
        self.assertEqual(item["target_branch"], "main")
        self.assertEqual(item["title"], "feat: add widget")
        self.assertEqual(item["state"], "merged")
        self.assertEqual(item["merge_commit"], "abc123")
        # No contradictions
        self.assertEqual(item["conflicts"], [])

    def test_duplicate_preserves_existing_nonempty(self) -> None:
        """Later record does NOT overwrite existing nonempty data."""
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
                "target_branch": "main",
                "title": "original title",
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
                "title": "different title",
            },
        ]
        r = evidence.normalize_evidence(items)
        item = r["items"][0]
        self.assertEqual(item["title"], "original title")
        self.assertEqual(item["target_branch"], "main")

    def test_duplicate_contradictory_still_conflict(self) -> None:
        """Contradictory merged/target values still produce CONFLICT."""
        items = [
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": True,
                "target_branch": "main",
            },
            {
                "pr_url": (
                    "https://github.example.invalid/org/repo/pull/1"
                ),
                "contributor_key": "TEST-201",
                "merged": False,
                "target_branch": "release-4.19",
            },
        ]
        r = evidence.normalize_evidence(items)
        item = r["items"][0]
        self.assertTrue(len(item["conflicts"]) >= 2)


# ---------------------------------------------------------------------------
# Review contracts: Forbidden fields, comments synonym, casing (R2)
# ---------------------------------------------------------------------------

class TestForbiddenFieldContracts(unittest.TestCase):
    """R2: case-insensitive forbidden, comments synonym, uncatalogued
    field type, validate allowed_fields shape."""

    def _make_plan_with_profile(self, profile):
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = evidence.normalize_evidence(_make_evidence_items())
        return evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
            profile,
        )

    def test_comments_synonym_forbidden(self) -> None:
        """'comments' (plural) is forbidden like 'comment'."""
        profile = {
            "allowed_fields": [
                {"name": "comments", "value": "test note"},
            ],
        }
        plan = self._make_plan_with_profile(profile)
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
            and f["ref"] == "comments"
        ]
        self.assertTrue(len(forbidden) > 0)

    def test_fixversions_camelcase_forbidden(self) -> None:
        """'fixVersions' (camelCase raw Jira name) → forbidden."""
        profile = {
            "allowed_fields": [
                {"name": "fixVersions", "value": "v1"},
            ],
        }
        plan = self._make_plan_with_profile(profile)
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
            and f["ref"] == "fixVersions"
        ]
        self.assertTrue(
            len(forbidden) > 0,
            "Direct fixVersions must be forbidden (use target_release alias)",
        )

    def test_fixversions_uppercase_forbidden(self) -> None:
        """'FIXVERSIONS' (all caps) → forbidden."""
        profile = {
            "allowed_fields": [
                {"name": "FIXVERSIONS", "value": "v1"},
            ],
        }
        plan = self._make_plan_with_profile(profile)
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
        ]
        self.assertTrue(len(forbidden) > 0)

    def test_target_release_alias_not_forbidden(self) -> None:
        """'target_release' (catalog alias) is allowed."""
        profile = {
            "allowed_fields": [
                {
                    "name": "target_release",
                    "value": "v1",
                    "catalog_verified": True,
                    "catalog_entry": {"id": "7", "name": "v1"},
                },
            ],
        }
        plan = self._make_plan_with_profile(profile)
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
            and f["ref"] == "target_release"
        ]
        self.assertEqual(len(forbidden), 0)
        self.assertIn("target_release", plan["metadata"])

    def test_uncatalogued_field_finding(self) -> None:
        """Valid-but-uncatalogued field → uncatalogued_field finding."""
        profile = {
            "allowed_fields": [
                {"name": "custom_field_12345", "value": "x"},
            ],
        }
        plan = self._make_plan_with_profile(profile)
        uncatalogued = [
            f for f in plan["findings"]
            if f["type"] == "uncatalogued_field"
        ]
        self.assertTrue(len(uncatalogued) > 0)
        self.assertEqual(uncatalogued[0]["ref"], "custom_field_12345")

    def test_malformed_allowed_fields_not_list(self) -> None:
        """allowed_fields='bad' → finding, no crash."""
        profile = {"allowed_fields": "not a list"}
        plan = self._make_plan_with_profile(profile)
        self.assertEqual(plan["status"], "complete")
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
            and f["ref"] == "allowed_fields"
        ]
        self.assertTrue(len(forbidden) > 0)

    def test_malformed_allowed_field_entry_not_dict(self) -> None:
        """allowed_fields=[42] → finding, no crash."""
        profile = {"allowed_fields": [42]}
        plan = self._make_plan_with_profile(profile)
        self.assertEqual(plan["status"], "complete")
        self.assertTrue(len(plan["findings"]) > 0)

    def test_malformed_field_name_not_string(self) -> None:
        """allowed_fields entry name=123 → finding, no TypeError."""
        profile = {
            "allowed_fields": [{"name": 123, "value": "x"}],
        }
        plan = self._make_plan_with_profile(profile)
        self.assertEqual(plan["status"], "complete")
        forbidden = [
            f for f in plan["findings"]
            if f["type"] == "forbidden_field"
        ]
        self.assertTrue(len(forbidden) > 0)

    def test_malformed_field_name_empty(self) -> None:
        """allowed_fields entry name='' → finding, no crash."""
        profile = {
            "allowed_fields": [{"name": "", "value": "x"}],
        }
        plan = self._make_plan_with_profile(profile)
        self.assertTrue(len(plan["findings"]) > 0)


# ---------------------------------------------------------------------------
# Review contracts: Fail-closed errors and valid (R5)
# ---------------------------------------------------------------------------

class TestFailClosedErrorsValid(unittest.TestCase):
    """R5: non-list errors → invalid, valid must be exact True,
    missing evidence.errors → invalid_evidence."""

    def test_validation_errors_non_list_fail_closed(self) -> None:
        """validation.errors = 'string' → invalid_issue."""
        val = {
            "valid": True,
            "errors": "something went wrong",
            "key": "TEST-100",
            "summary": "[DOCS] test",
            "description": "test",
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")
        self.assertTrue(
            any("not a list" in e for e in plan["errors"])
        )

    def test_validation_errors_none_fail_closed(self) -> None:
        """validation.errors = None → invalid_issue."""
        val = {
            "valid": True,
            "errors": None,
            "key": "TEST-100",
            "summary": "[DOCS] test",
            "description": "test",
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")

    def test_validation_errors_dict_fail_closed(self) -> None:
        """validation.errors = {} → invalid_issue."""
        val = {
            "valid": True,
            "errors": {"msg": "bad"},
            "key": "TEST-100",
            "summary": "[DOCS] test",
            "description": "test",
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")

    def test_valid_truthy_nonbool_rejected(self) -> None:
        """validation.valid = 1 (truthy int) → invalid_issue."""
        val = {
            "valid": 1,
            "errors": [],
            "key": "TEST-100",
            "summary": "[DOCS] test",
            "description": "test desc",
            "contributors": ["TEST-201"],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")
        self.assertTrue(
            any("not True" in e for e in plan["errors"])
        )

    def test_valid_string_yes_rejected(self) -> None:
        """validation.valid = 'yes' → invalid_issue."""
        val = {
            "valid": "yes",
            "errors": [],
            "key": "TEST-100",
            "summary": "[DOCS] test",
            "description": "test desc",
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }
        ev = {"items": [], "errors": [], "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_issue")

    def test_evidence_errors_missing_fail_closed(self) -> None:
        """evidence without 'errors' key → invalid_evidence."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = {"items": [], "warnings": []}  # no 'errors' key
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_evidence")

    def test_evidence_errors_non_list_fail_closed(self) -> None:
        """evidence.errors = None → invalid_evidence."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        ev = {"items": [], "errors": None, "warnings": []}
        plan = evidence.build_change_plan(val, ev, {})
        self.assertEqual(plan["status"], "invalid_evidence")

    def test_valid_true_with_empty_errors_passes(self) -> None:
        """valid=True + errors=[] → proceeds normally."""
        snap = _make_docs_snapshot()
        val = evidence.validate_issue(snap)
        self.assertTrue(val["valid"])
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
        )
        self.assertEqual(plan["status"], "complete")


# ---------------------------------------------------------------------------
# Review contracts: Snapshot fingerprint mandatory (R6)
# ---------------------------------------------------------------------------

class TestSnapshotFingerprintMandatory(unittest.TestCase):
    """R6: missing/blank snapshot_fingerprint → invalid_plan before
    digest recompute; recomputed matching digest doesn't bypass."""

    def test_empty_fingerprint_invalid_plan(self) -> None:
        """Empty snapshot_fingerprint → invalid_plan."""
        plan = {
            "status": "complete",
            "issue_key": "TEST-100",
            "target": {},
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "snapshot_fingerprint": "",
            "plan_digest": "some-digest",
        }
        r = evidence.check_enrichment(
            plan, {"key": "TEST-100", "remote_links": []}
        )
        self.assertEqual(r["status"], "invalid_plan")
        self.assertIn("snapshot_fingerprint", r["reason"])

    def test_missing_fingerprint_key_invalid_plan(self) -> None:
        """Missing snapshot_fingerprint key → invalid_plan."""
        plan = {
            "status": "complete",
            "issue_key": "TEST-100",
            "target": {},
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "plan_digest": "some-digest",
        }
        r = evidence.check_enrichment(
            plan, {"key": "TEST-100", "remote_links": []}
        )
        self.assertEqual(r["status"], "invalid_plan")
        self.assertIn("snapshot_fingerprint", r["reason"])

    def test_nonstring_fingerprint_invalid_plan(self) -> None:
        """Non-string snapshot_fingerprint → invalid_plan."""
        plan = {
            "status": "complete",
            "issue_key": "TEST-100",
            "target": {},
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "snapshot_fingerprint": 12345,
            "plan_digest": "some-digest",
        }
        r = evidence.check_enrichment(
            plan, {"key": "TEST-100", "remote_links": []}
        )
        self.assertEqual(r["status"], "invalid_plan")

    def test_recomputed_digest_no_fingerprint_bypass(self) -> None:
        """Matching recomputed digest but no fingerprint → still invalid.
        A caller cannot make a fingerprint-less plan ready."""
        # Compute what the digest WOULD be with empty fingerprint
        import hashlib
        projection = {
            "issue_key": "TEST-100",
            "target": {},
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "snapshot_fingerprint": "",
        }
        raw = json.dumps(
            projection, sort_keys=True, ensure_ascii=True
        )
        matching_digest = hashlib.sha256(raw.encode()).hexdigest()

        plan = {
            "status": "complete",
            "issue_key": "TEST-100",
            "target": {},
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "snapshot_fingerprint": "",
            "plan_digest": matching_digest,
        }
        r = evidence.check_enrichment(
            plan, {"key": "TEST-100", "remote_links": []}
        )
        self.assertEqual(r["status"], "invalid_plan")
        self.assertIn("snapshot_fingerprint", r["reason"])
        self.assertEqual(r["eligible_links"], [])
        self.assertEqual(r["eligible_metadata"], {})


# ---------------------------------------------------------------------------
# Review contract: Complete Phase1→Phase2 lifecycle (R1, R8)
# ---------------------------------------------------------------------------

class TestPhase1Phase2Lifecycle(unittest.TestCase):
    """R1/R8: complete offline Phase1 preview → approved fresh check →
    simulated metadata + link receipt using both saved tokens and
    pre/post state.  Unknown fields not fabricated as empty."""

    def test_complete_approval_lifecycle(self) -> None:
        """Phase1 preview → save tokens → Phase2 check with approved
        tokens → simulated writes → readback receipt."""
        # === Phase 1: Preview (no side effects) ===
        snapshot = _make_docs_snapshot()
        val = evidence.validate_issue(snapshot)
        self.assertTrue(val["valid"])

        raw_evidence = _make_evidence_items()
        ev = evidence.normalize_evidence(raw_evidence)
        self.assertEqual(len(ev["errors"]), 0)

        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "4.19",
                "catalog_verified": True,
                "catalog_entry": {"id": "419", "name": "4.19"},
            }],
        }
        target = {"release": "4.19", "target_branch": "main"}
        plan = evidence.build_change_plan(val, ev, target, profile)
        self.assertEqual(plan["status"], "complete")
        self.assertTrue(plan["snapshot_fingerprint"])
        self.assertTrue(plan["plan_digest"])

        # Phase 1 preview check — no approval tokens
        current_prewrite = {
            "key": "TEST-100",
            "summary": snapshot["summary"],
            "description": snapshot["description"],
            "remote_links": [],
            "fields": {"fixVersions": []},
        }
        preview = evidence.check_enrichment(plan, current_prewrite)
        self.assertEqual(preview["status"], "ready")
        self.assertFalse(preview["stale"])

        # Save Phase 1 tokens for Phase 2
        saved_baseline = preview["baseline_fingerprint"]
        saved_digest = preview["plan_digest"]
        self.assertTrue(saved_baseline)
        self.assertTrue(saved_digest)

        # === Phase 2: Apply (with approved tokens) ===
        # Fresh check with BOTH saved tokens — same state → ready
        apply_check = evidence.check_enrichment(
            plan, current_prewrite, saved_baseline, saved_digest,
        )
        self.assertEqual(apply_check["status"], "ready")
        self.assertFalse(apply_check["stale"])
        self.assertTrue(len(apply_check["eligible_links"]) > 0)
        self.assertIn(
            "target_release", apply_check["eligible_metadata"]
        )

        # Verify metadata payload is additive
        em = apply_check["eligible_metadata"]["target_release"]
        payload_ids = {
            p["id"]
            for p in em["jira_payload"]["fixVersions"]
        }
        self.assertIn("419", payload_ids)

        # === Simulated writes → Readback ===
        readback = {
            "key": "TEST-100",
            "summary": snapshot["summary"],
            "description": snapshot["description"],
            "remote_links": [
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/101",
                },
                {
                    "url": "https://github.example.invalid"
                    "/org/repo/pull/102",
                },
            ],
            "fields": {
                "fixVersions": [
                    {"id": "419", "name": "4.19"},
                ],
            },
        }
        receipt = evidence.verify_enrichment(
            apply_check, readback, "TEST-100"
        )
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["all_confirmed"])

        # Check EACH receipt status individually
        for lr in receipt["link_receipts"]:
            self.assertEqual(lr["status"], "confirmed")
            self.assertEqual(lr["operation"], "add")
        for mr in receipt["metadata_receipts"]:
            self.assertEqual(mr["status"], "confirmed")
            self.assertEqual(mr["jira_field"], "fixVersions")

        # === Idempotency: re-check shows existing ===
        new_baseline = receipt["baseline_fingerprint"]
        recheck = evidence.check_enrichment(
            plan, readback, new_baseline, saved_digest,
        )
        self.assertFalse(recheck["stale"])
        self.assertEqual(len(recheck["eligible_links"]), 0)
        self.assertEqual(len(recheck["existing_links"]), 2)

    def test_unknown_fixversions_not_fabricated_empty(self) -> None:
        """Unknown fixVersions (missing field) blocks metadata writes;
        NOT fabricated as []."""
        snapshot = _make_docs_snapshot()
        val = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        profile = {
            "allowed_fields": [{
                "name": "target_release",
                "value": "4.19",
                "catalog_verified": True,
                "catalog_entry": {"id": "419", "name": "4.19"},
            }],
        }
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "4.19", "target_branch": "main"},
            profile,
        )
        # current_state has NO fields key — unknown state
        current = {
            "key": "TEST-100",
            "summary": snapshot["summary"],
            "description": snapshot["description"],
            "remote_links": [],
        }
        r = evidence.check_enrichment(plan, current)
        # Metadata must NOT be eligible (fail-closed)
        self.assertEqual(r["eligible_metadata"], {})

    def test_stale_plan_digest_blocks_apply(self) -> None:
        """Phase2 with stale plan_digest → stale, zero writes."""
        snapshot = _make_docs_snapshot()
        val = evidence.validate_issue(snapshot)
        ev = evidence.normalize_evidence(_make_evidence_items())
        plan = evidence.build_change_plan(
            val, ev,
            {"release": "v1", "target_branch": "main"},
        )
        current = {
            "key": "TEST-100",
            "summary": snapshot["summary"],
            "description": snapshot["description"],
            "remote_links": [],
        }
        preview = evidence.check_enrichment(plan, current)
        baseline = preview["baseline_fingerprint"]

        # Pass wrong digest → stale
        r = evidence.check_enrichment(
            plan, current, baseline, "wrong-digest-from-old-plan",
        )
        self.assertTrue(r["stale"])
        self.assertEqual(r["status"], "stale")
        self.assertEqual(r["eligible_links"], [])
        self.assertEqual(r["eligible_metadata"], {})


if __name__ == "__main__":
    unittest.main()
