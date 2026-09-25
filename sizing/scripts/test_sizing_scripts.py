import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path

from _common import DIMENSIONS, IMPACT_DIMENSIONS, TEAMS, write_json
from apply_plan import jira_comment, main as apply_main, render_preview
from finalize_assessment import _render_quadrant_chart, finalize_assessment
from prepare_context import _comments, _normalize_cli_issue


def make_context(*keys: str) -> dict:
    return {
        "context": "sizing-test",
        "mode": "batch" if len(keys) > 1 else "single",
        "features": [
            {"key": key, "title": f"Feature {key}", "current_size": None}
            for key in keys
        ],
    }


def make_decisions(context: dict, *, size: str = "M", impact_scores: tuple[int, ...] = (3, 3, 3, 3)) -> dict:
    features = []
    for source in context["features"]:
        features.append({
            "key": source["key"],
            "size": size,
            "confidence": "medium",
            "dimensions": {
                name: {"level": "Medium", "rationale": f"{name.replace('_', ' ')} contributes."}
                for name in DIMENSIONS
            },
            "rationale": "The cross-component work fits the selected size.",
            "teams": {
                team: {
                    "size": "M" if team == "DEV" else "—",
                    "rationale": "Implementation spans the affected components." if team == "DEV" else "",
                }
                for team in TEAMS
            },
            "impact": {
                name: {"score": score, "rationale": f"{name.replace('_', ' ')} supports the outcome."}
                for name, score in zip(IMPACT_DIMENSIONS, impact_scores)
            },
            "value_driver": "Removes a workflow blocker.",
            "comparison_rationale": "",
            "quadrant": "Strategic Bet",
            "quadrant_rationale": "The expected value justifies the investment.",
            "split_suggestions": [],
        })
    return {"features": features, "capacity_concerns": [], "defer_notes": {}}


class JiraNormalizationTests(unittest.TestCase):
    def test_scope_comment_with_transition_words_is_retained(self) -> None:
        scope_comment = "The API moved from REST to gRPC, so the client also needs changes."
        comments = _comments([
            {"author": "Reviewer", "created": "2026-09-01", "body": scope_comment},
            {"author": "Jira", "created": "2026-09-02", "body": "Status changed from Open to In Progress"},
        ])

        self.assertEqual([item["body"] for item in comments], [scope_comment])

    def test_cli_adf_description_and_comment_are_flattened(self) -> None:
        issue = {
            "key": "EDM-1001",
            "fields": {
                "summary": "Feature summary",
                "issuetype": {"name": "Feature"},
                "description": {
                    "type": "doc",
                    "content": [{
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Acceptance"},
                            {"type": "hardBreak"},
                            {"type": "text", "text": "criteria"},
                        ],
                    }],
                },
                "comment": {
                    "comments": [{
                        "author": {"displayName": "A reviewer"},
                        "created": "2026-09-01T10:00:00.000+0000",
                        "body": {
                            "type": "doc",
                            "content": [{
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Clarified scope."}],
                            }],
                        },
                    }],
                },
            },
        }

        normalized = _normalize_cli_issue(issue)

        self.assertEqual(normalized["fields"]["description"], "Acceptance\ncriteria")
        self.assertEqual(normalized["comments"][0]["body"], "Clarified scope.")


class AssessmentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = make_context("EDM-1001")
        self.decisions = make_decisions(self.context)

    def test_missing_and_duplicate_decision_keys_are_rejected(self) -> None:
        missing = deepcopy(self.decisions)
        missing["features"] = []
        with self.assertRaisesRegex(ValueError, "missing assessment decision"):
            finalize_assessment(self.context, missing)

        duplicate = deepcopy(self.decisions)
        duplicate["features"].append(deepcopy(duplicate["features"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate assessment decision"):
            finalize_assessment(self.context, duplicate)

    def test_xxl_requires_split_suggestions_and_is_not_committable(self) -> None:
        decisions = make_decisions(self.context, size="XXL")
        with self.assertRaisesRegex(ValueError, "XXL and needs 2–3"):
            finalize_assessment(self.context, decisions)

        decisions["features"][0]["split_suggestions"] = [
            {"title": "First outcome", "description": "Deliver the first user outcome.", "size": "M"},
            {"title": "Second outcome", "description": "Deliver the second user outcome.", "size": "S"},
        ]
        result = finalize_assessment(self.context, decisions)["features"][0]
        self.assertEqual(result["quadrant"], "Must Split")
        self.assertIsNone(result["effort_score"])

    def test_size_override_recomputes_but_cannot_create_xxl(self) -> None:
        decisions = deepcopy(self.decisions)
        decisions["user_overrides"] = {"EDM-1001": "L"}

        overridden = finalize_assessment(self.context, decisions)["features"][0]

        self.assertEqual(overridden["recommended_size"], "L")
        self.assertEqual(overridden["original_recommended_size"], "M")
        self.assertTrue(overridden["user_override"])

        decisions["user_overrides"]["EDM-1001"] = "XXL"
        with self.assertRaisesRegex(ValueError, "user override makes EDM-1001 XXL"):
            finalize_assessment(self.context, decisions)


class ApplyPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        original_cwd = Path.cwd()
        os.chdir(temporary.name)
        self.addCleanup(os.chdir, original_cwd)

        self.context = make_context("EDM-1001", "EDM-1002")
        self.decisions = make_decisions(self.context)
        self.assessment = finalize_assessment(self.context, self.decisions)
        self.artifact_dir = Path(".artifacts") / "sizing" / self.context["context"]
        write_json(self.artifact_dir / "01-context.json", self.context)
        write_json(self.artifact_dir / "02-decisions.json", self.decisions)
        write_json(self.artifact_dir / "02-assessment.json", self.assessment)

    def test_selection_preview_defers_approval_until_payload_is_reviewed(self) -> None:
        preview = render_preview(self.assessment)

        self.assertIn("selection preview does not authorize Jira writes", preview)
        self.assertIn("review the prepared action payload before approving", preview)

    def test_selected_actions_include_the_exact_generated_comment(self) -> None:
        output = self.artifact_dir / "03-apply-actions.json"
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = apply_main([
                "actions", self.context["context"], "--approved-key", "EDM-1001",
                "--output", str(output),
            ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual([action["key"] for action in payload["actions"]], ["EDM-1001"])
        self.assertEqual(payload["actions"][0]["comment"], jira_comment(self.assessment["features"][0]))

    def test_override_path_updates_assessment_and_prepares_payload(self) -> None:
        output = self.artifact_dir / "03-apply-actions.json"
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = apply_main([
                "actions", self.context["context"], "--approved-key", "EDM-1001",
                "--override", "EDM-1001=L", "--output", str(output),
            ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["actions"][0]["size"], "L")
        stored_decisions = json.loads((self.artifact_dir / "02-decisions.json").read_text(encoding="utf-8"))
        self.assertEqual(stored_decisions["user_overrides"], {"EDM-1001": "L"})
        self.assertTrue((self.artifact_dir / "02-assessment.md").is_file())


class QuadrantChartTests(unittest.TestCase):
    def test_points_stay_in_the_computed_quadrant(self) -> None:
        features = [
            {"key": "SB", "effort_score": 4, "impact_score": 12, "quadrant": "Strategic Bet"},
            {"key": "QW", "effort_score": 2, "impact_score": 16, "quadrant": "Quick Win"},
            {"key": "LHF", "effort_score": 4, "impact_score": 12, "quadrant": "Low-Hanging Fruit"},
            {"key": "RE", "effort_score": 7, "impact_score": 8, "quadrant": "Reconsider"},
        ]

        chart = _render_quadrant_chart(features)
        points = {
            key: json.loads(coordinates)
            for line in chart
            if ": [" in line
            for key, coordinates in [line.strip().split(": ", 1)]
        }

        self.assertGreater(points["SB"][0], 0.5)
        self.assertGreater(points["SB"][1], 0.5)
        self.assertLess(points["QW"][0], 0.5)
        self.assertGreater(points["QW"][1], 0.5)
        self.assertLess(points["LHF"][0], 0.5)
        self.assertLess(points["LHF"][1], 0.5)
        self.assertGreater(points["RE"][0], 0.5)
        self.assertLess(points["RE"][1], 0.5)


if __name__ == "__main__":
    unittest.main()
