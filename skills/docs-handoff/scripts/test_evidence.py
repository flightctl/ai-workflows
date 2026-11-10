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

    def test_divergent_observation_produces_proposal(self) -> None:
        """B: Divergent observation → update proposal with wording."""
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
        updates = [
            c for c in plan["source_proposal"]["proposed_changes"]
            if c["action"] == "update"
        ]
        self.assertTrue(len(updates) > 0)
        self.assertTrue(updates[0]["proposed_wording"])
        self.assertTrue(updates[0]["evidence_urls"])

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
        current = {
            "key": current_key,
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

    def test_forbidden_metadata_rejected(self) -> None:
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
        self.assertTrue(
            any("status" in f for f in r["forbidden_fields"])
        )

    def test_uncatalogued_metadata_rejected(self) -> None:
        """D: Arbitrary key not in allowed catalog → forbidden."""
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
        self.assertTrue(
            any("random_field" in f for f in r["forbidden_fields"])
        )

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
        r = self._make_receipt(
            eligible_metadata={
                "target_release": {"value": "4.19"},
            },
            readback_fields={"target_release": "4.19"},
            readback_urls=[
                "https://github.example.invalid/org/repo/pull/101"
            ],
        )
        meta = r["metadata_receipts"]
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["status"], "confirmed")

    def test_metadata_receipt_different(self) -> None:
        r = self._make_receipt(
            eligible_metadata={
                "target_release": {"value": "4.19"},
            },
            readback_fields={"target_release": "4.20"},
            readback_urls=[
                "https://github.example.invalid/org/repo/pull/101"
            ],
        )
        meta = r["metadata_receipts"]
        self.assertEqual(meta[0]["status"], "different_value")

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
        current = {"key": "TEST-100", "remote_links": []}
        enrichment = evidence.check_enrichment(plan, current)
        self.assertEqual(enrichment["status"], "ready")
        self.assertFalse(enrichment["stale"])
        self.assertEqual(len(enrichment["eligible_links"]), 2)
        baseline = enrichment["baseline_fingerprint"]

        # 5. Verify readback (post-apply)
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
        receipt = evidence.verify_enrichment(
            enrichment, readback, "TEST-100"
        )
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["all_confirmed"])
        self.assertEqual(len(receipt["link_receipts"]), 2)

        # 6. Re-check with new baseline (idempotent)
        enrichment2 = evidence.check_enrichment(
            plan, readback, baseline
        )
        # All links are now existing, none eligible
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


if __name__ == "__main__":
    unittest.main()
