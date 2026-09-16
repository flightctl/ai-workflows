#!/usr/bin/env python3
"""Tests for deterministic token-saving triage helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


def _load(name: str):
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prepare_analysis = _load("prepare_analysis")
finalize_analysis = _load("finalize_analysis")
synthesize_report = _load("synthesize_report")
prepare_report = _load("prepare_report")


def _issue(key: str, summary: str = "Login returns HTTP 500") -> dict:
    return {
        "key": key,
        "summary": summary,
        "status": "Open",
        "priority": "High",
        "assignee": "Alice",
        "reporter": "Bob",
        "created": "2024-01-01T00:00:00.000+0000",
        "updated": "2024-01-01T00:00:00.000+0000",
        "labels": ["auth"],
        "components": ["Authentication"],
        "description": "Steps to reproduce: sign in. Expected: success. Actual: HTTP 500.",
    }


class TestPrepareAnalysis(unittest.TestCase):
    def test_compacts_and_extracts_deterministic_signals(self) -> None:
        result = prepare_analysis.prepare(
            {"project": "EDM", "issues": [_issue("EDM-1")]},
            {"issues": []},
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        item = result["issues"][0]
        self.assertEqual(item["errorType"], "HTTP 500")
        self.assertTrue(item["descriptionSignals"]["hasReproduction"])
        self.assertEqual(item["affectedComponent"], "Authentication")

    def test_marks_stale_vague_issue_for_deterministic_close(self) -> None:
        issue = _issue("EDM-2")
        issue["description"] = "It is broken"
        result = prepare_analysis.prepare(
            {"project": "EDM", "issues": [issue]}, {"issues": []},
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(result["issues"][0]["deterministicRecommendation"], "CLOSE")

    def test_does_not_extract_jira_key_as_error_code(self) -> None:
        issue = _issue("EDM-2")
        issue["description"] = "Related issue EDM-4877 is tracked separately."
        result = prepare_analysis.prepare(
            {"project": "EDM", "issues": [issue]}, {"issues": []},
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        self.assertIsNone(result["issues"][0]["errorCode"])
        self.assertFalse(result["issues"][0]["descriptionSignals"]["hasErrorDetails"])

    def test_preserves_resolved_timestamp_for_regression_matching(self) -> None:
        resolved = _issue("EDM-9")
        resolved["resolved"] = "2025-12-20T00:00:00.000+0000"
        result = prepare_analysis.prepare(
            {"project": "EDM", "issues": [_issue("EDM-1")]},
            {"issues": [resolved]},
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        candidate = result["issues"][0]["matchCandidates"][0]
        self.assertEqual(candidate["resolved"], "2025-12-20T00:00:00.000+0000")

    def test_uses_raw_description_for_multiline_error_excerpt(self) -> None:
        issue = _issue("EDM-10")
        issue["description"] = "ERROR: first line\nActual: HTTP 500"
        result = prepare_analysis.prepare(
            {"project": "EDM", "issues": [issue]}, {"issues": []},
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        compact = result["issues"][0]
        self.assertEqual(compact["errorMessageExcerpt"], "ERROR: first line")
        self.assertTrue(compact["descriptionSignals"]["hasErrorDetails"])


class TestFinalizeAnalysis(unittest.TestCase):
    def test_merges_decisions_and_computes_aggregates(self) -> None:
        issue = _issue("EDM-1")
        prepared = prepare_analysis.prepare(
            {"project": "EDM", "issues": [issue]}, {"issues": []},
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        result = finalize_analysis.finalize(
            {"project": "EDM", "issues": [issue]}, prepared,
            {"decisions": [{"key": "EDM-1", "recommendation": "FIX_NOW", "reason": "High impact", "confidence": "High"}]},
        )
        self.assertEqual(result["totalCount"], 1)
        self.assertEqual(result["summary"], {"FIX_NOW": 1})
        self.assertEqual(result["issues"][0]["errorType"], "HTTP 500")

    def test_rejects_incomplete_decision_set(self) -> None:
        with self.assertRaises(ValueError):
            finalize_analysis.finalize(
                {"project": "EDM", "issues": [_issue("EDM-1")]},
                {"issues": [{"key": "EDM-1"}]},
                {"decisions": []},
            )

    def test_clusters_by_topic_not_component(self) -> None:
        first = _issue("EDM-1", "Login times out")
        second = _issue("EDM-2", "Session expires during login")
        second["components"] = ["Payments"]
        prepared = {"issues": [{"key": "EDM-1"}, {"key": "EDM-2"}]}
        result = finalize_analysis.finalize(
            {"project": "EDM", "issues": [first, second]}, prepared,
            {"decisions": [
                {"key": "EDM-1", "topic": "login session failures", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium"},
                {"key": "EDM-2", "topic": "login session failures", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium"},
            ]},
        )
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(result["clusters"][0]["theme"], "login session failures")

    def test_preserves_ai_cluster_judgment_and_recommendations(self) -> None:
        first = _issue("EDM-1", "Login times out")
        second = _issue("EDM-2", "Session expires during login")
        prepared = {"issues": [{"key": "EDM-1"}, {"key": "EDM-2"}]}
        decisions = {
            "decisions": [
                {"key": "EDM-1", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium"},
                {"key": "EDM-2", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium"},
            ],
            "clusters": [{
                "id": "cluster-auth",
                "theme": "Session invalidation during sign-in",
                "issues": ["EDM-1", "EDM-2"],
                "suggestedLinkType": "is caused by",
                "nextSteps": ["Link the reports", "Inspect session lifetime handling"],
            }],
            "keyRecommendations": ["Investigate session invalidation first"] * 5,
        }
        result = finalize_analysis.finalize(
            {"project": "EDM", "issues": [first, second]}, prepared, decisions,
        )
        self.assertEqual(result["clusters"][0]["theme"], "Session invalidation during sign-in")
        self.assertEqual(result["clusters"][0]["suggestedLinkType"], "is caused by")
        self.assertEqual(result["keyRecommendations"][0], "Investigate session invalidation first")

    def test_preserves_and_validates_priority_mismatch_judgment(self) -> None:
        issue = _issue("EDM-3")
        prepared = {"issues": [{"key": "EDM-3"}]}
        result = finalize_analysis.finalize(
            {"project": "EDM", "issues": [issue]}, prepared,
            {"decisions": [{
                "key": "EDM-3", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium",
                "priorityMismatch": {"assigned": "High", "suggested": "Major", "reason": "Impact is higher than the assigned priority."},
            }]},
        )
        self.assertEqual(result["issues"][0]["priorityMismatch"]["suggested"], "Major")

    def test_rejects_priority_mismatch_for_missing_assigned_priority(self) -> None:
        issue = _issue("EDM-4")
        issue["priority"] = "Undefined"
        with self.assertRaises(ValueError):
            finalize_analysis.finalize(
                {"project": "EDM", "issues": [issue]}, {"issues": [{"key": "EDM-4"}]},
                {"decisions": [{
                    "key": "EDM-4", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium",
                    "priorityMismatch": {"assigned": "Undefined", "suggested": "Major", "reason": "Mismatch."},
                }]},
            )

    def test_rejects_unknown_priority_mismatch_suggestion(self) -> None:
        issue = _issue("EDM-11")
        with self.assertRaises(ValueError):
            finalize_analysis.finalize(
                {"project": "EDM", "issues": [issue]}, {"issues": [{"key": "EDM-11"}]},
                {"decisions": [{
                    "key": "EDM-11", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium",
                    "priorityMismatch": {"assigned": "High", "suggested": "Urgent", "reason": "Mismatch."},
                }]},
            )

    def test_rejects_non_string_relationship_target(self) -> None:
        issue = _issue("EDM-12")
        with self.assertRaises(ValueError):
            finalize_analysis.finalize(
                {"project": "EDM", "issues": [issue]}, {"issues": [{"key": "EDM-12", "matchCandidates": []}]},
                {"decisions": [{
                    "key": "EDM-12", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium",
                    "duplicateOf": {"key": "EDM-99"},
                }]},
            )

    def test_rejects_regression_without_valid_prior_chronology(self) -> None:
        issue = _issue("EDM-5")
        prepared = {"issues": [{
            "key": "EDM-5",
            "matchCandidates": [{"key": "EDM-6", "kind": "resolved", "resolved": "2026-02-01T00:00:00Z"}],
        }]}
        with self.assertRaises(ValueError):
            finalize_analysis.finalize(
                {"project": "EDM", "issues": [issue]}, prepared,
                {"decisions": [{
                    "key": "EDM-5", "recommendation": "BACKLOG", "reason": "Valid", "confidence": "Medium",
                    "regressionOf": {"key": "EDM-6"},
                }]},
            )

    def test_validates_auto_fix_likelihood_contract(self) -> None:
        issue = _issue("EDM-7")
        with self.assertRaises(ValueError):
            finalize_analysis.finalize(
                {"project": "EDM", "issues": [issue]}, {"issues": [{"key": "EDM-7"}]},
                {"decisions": [{
                    "key": "EDM-7", "recommendation": "AUTO_FIX", "reason": "Bounded", "confidence": "High",
                }]},
            )

    def test_report_context_is_compact_and_mechanical(self) -> None:
        data = {"project": "EDM", "issues": [_issue("EDM-1", "A bug")], "clusters": [], "keyRecommendations": []}
        result = prepare_report.prepare(data)
        self.assertEqual(result["totalCount"], 1)
        self.assertNotIn("description", result["issues"][0])


class TestSynthesizeReport(unittest.TestCase):
    def test_zero_issue_synthesis_is_deterministic(self) -> None:
        result = synthesize_report.synthesize({"issues": []})
        self.assertEqual(result["releaseRisk"], None)
        self.assertEqual(result["executiveSummary"], ["No unresolved bugs were analyzed."])

    def test_non_empty_synthesis_always_has_three_to_five_bullets(self) -> None:
        result = synthesize_report.synthesize({
            "issues": [{"key": "EDM-1", "recommendation": "BACKLOG"}],
        })
        self.assertGreaterEqual(len(result["executiveSummary"]), 3)
        self.assertLessEqual(len(result["executiveSummary"]), 5)

    def test_report_synthesis_is_deterministic(self) -> None:
        data = {"issues": [_issue(f"EDM-{index}") for index in range(1, 6)]}
        for issue in data["issues"]:
            issue["recommendation"] = "BACKLOG"
        result = synthesize_report.synthesize(data)
        self.assertIsNotNone(result["releaseRisk"])
        self.assertTrue(result["executiveSummary"])


if __name__ == "__main__":
    unittest.main()
