#!/usr/bin/env python3
"""Tests for _shared/scripts/provenance.py."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent / "provenance.py"
_spec = importlib.util.spec_from_file_location("provenance", _SCRIPT)
assert _spec and _spec.loader
provenance = importlib.util.module_from_spec(_spec)
sys.modules["provenance"] = provenance
_spec.loader.exec_module(provenance)


class ProvenanceTests(unittest.TestCase):
    def test_compute_drift_no_change(self) -> None:
        events = [
            {"workflow_version": "0.5.0", "ai_workflows": "abc", "source_repo": "def"},
            {"workflow_version": "0.5.0", "ai_workflows": "abc", "source_repo": "def"},
        ]
        drift = provenance.compute_drift(events)
        self.assertFalse(drift["context_changed"])
        self.assertEqual(drift["changed_fields"], [])

    def test_compute_drift_detects_source_change(self) -> None:
        events = [
            {"workflow_version": "0.5.0", "ai_workflows": "abc", "source_repo": "old"},
            {"workflow_version": "0.5.0", "ai_workflows": "abc", "source_repo": "new"},
        ]
        drift = provenance.compute_drift(events)
        self.assertTrue(drift["context_changed"])
        self.assertIn("source_repo", drift["changed_fields"])

    def test_provenance_kind_commit_only(self) -> None:
        events = [{"phase": "commit"}, {"phase": "commit"}]
        self.assertEqual(provenance.provenance_kind(events), "commit_only")

    def test_provenance_kind_session(self) -> None:
        events = [{"phase": "draft"}, {"phase": "commit"}]
        self.assertEqual(provenance.provenance_kind(events), "session")

    def test_build_footer_single_event(self) -> None:
        data = {
            "workflow": "prd",
            "events": [
                {
                    "phase": "draft",
                    "authoring_mode": "skill",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "adfad68",
                    "source_repo": "00e78b8f",
                    "source_repo_branch": "main",
                    "commits_behind_main": 0,
                    "main_ref": "main",
                }
            ],
            "drift": {"context_changed": False},
        }
        footer = provenance.build_footer(data)
        self.assertIn("## Provenance", footer)
        self.assertIn("Authored: draft @ prd 0.5.0 - adfad68", footer)
        self.assertIn("workspace main @ 00e78b8f", footer)
        self.assertIn('"provenance_kind":"session"', footer)
        self.assertIn("<!-- osac-provenance:", footer)
        self.assertNotIn("Final:", footer)
        self.assertNotIn("Phases:", footer)

    def test_build_footer_commit_only(self) -> None:
        data = {
            "workflow": "prd",
            "events": [
                {
                    "phase": "commit",
                    "authoring_mode": "skill",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "adfad68",
                    "source_repo": "00e78b8f",
                    "source_repo_branch": "main",
                    "commits_behind_main": 0,
                    "main_ref": "main",
                }
            ],
            "drift": {"context_changed": False},
        }
        footer = provenance.build_footer(data)
        self.assertIn("Committed: commit @ prd 0.5.0 - adfad68", footer)
        self.assertIn("commit-time snapshot only", footer)
        self.assertIn('"provenance_kind":"commit_only"', footer)
        self.assertIn('"phases":["commit"]', footer)
        self.assertNotIn("Authored:", footer)
        self.assertNotIn("Phases:", footer)

    def test_build_footer_with_drift(self) -> None:
        data = {
            "workflow": "prd",
            "events": [
                {
                    "phase": "draft",
                    "authoring_mode": "skill",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "adfad68",
                    "source_repo": "abc1234 (dirty)",
                    "source_repo_branch": "main",
                    "commits_behind_main": 47,
                    "main_ref": "main",
                },
                {
                    "phase": "revise",
                    "authoring_mode": "skill",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "adfad68",
                    "source_repo": "00e78b8f",
                    "source_repo_branch": "main",
                    "commits_behind_main": 0,
                    "main_ref": "main",
                },
            ],
            "drift": {"context_changed": True},
        }
        footer = provenance.build_footer(data)
        self.assertIn("Authored:", footer)
        self.assertIn("Final:", footer)
        self.assertIn("Context changed between draft and revise", footer)

    def test_build_footer_lists_multiple_phases_without_drift(self) -> None:
        data = {
            "workflow": "prd",
            "events": [
                {
                    "phase": "draft",
                    "authoring_mode": "skill",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "abc",
                    "source_repo": "def",
                    "source_repo_branch": "main",
                },
                {
                    "phase": "revise",
                    "authoring_mode": "skill",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "abc",
                    "source_repo": "def",
                    "source_repo_branch": "main",
                },
            ],
            "drift": {"context_changed": False},
        }
        footer = provenance.build_footer(data)
        self.assertIn("Phases: draft, revise", footer)

    def test_build_footer_marks_manual_edit(self) -> None:
        data = {
            "workflow": "prd",
            "events": [
                {
                    "phase": "manual-edit",
                    "authoring_mode": "manual",
                    "workflow_version": "0.5.0",
                    "ai_workflows": "abc",
                    "source_repo": "def",
                    "source_repo_branch": "main",
                }
            ],
            "drift": {"context_changed": False},
        }
        footer = provenance.build_footer(data)
        self.assertIn("manual-edit [manual]", footer)

    def test_strip_provenance_section(self) -> None:
        content = (
            "# PRD\n\nBody text.\n\n---\n\n## Provenance\n\n"
            "Authored: draft @ prd 0.5.0 - abc\n\n"
            '<!-- osac-provenance:{"schema_version":1} -->\n'
        )
        stripped = provenance.strip_provenance_section(content)
        self.assertEqual(stripped, "# PRD\n\nBody text.\n")
        self.assertNotIn("Provenance", stripped)

    def test_strip_provenance_heading_without_delimiter(self) -> None:
        content = "# PRD\n\nBody.\n\n## Provenance\n\nHand-edited stale line\n"
        stripped = provenance.strip_provenance_section(content)
        self.assertEqual(stripped, "# PRD\n\nBody.\n")
        self.assertNotIn("stale", stripped)

    def test_render_refreshes_commit_only_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = "OSAC-TEST"
            workflow = "prd"
            artifact_dir = root / ".artifacts" / workflow / issue
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "provenance.json").write_text(
                json.dumps(
                    {
                        "workflow": workflow,
                        "events": [
                            {
                                "phase": "commit",
                                "authoring_mode": "skill",
                                "workflow_version": "0.5.0",
                                "ai_workflows": "oldhash",
                                "source_repo": "oldws",
                                "source_repo_branch": "main",
                            }
                        ],
                        "drift": {"context_changed": False},
                    }
                ),
                encoding="utf-8",
            )
            target = root / "prd.md"
            target.write_text("# PRD\n", encoding="utf-8")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(
                    provenance,
                    "git_describe",
                    side_effect=lambda _root: "newhash",
                ):
                    with mock.patch.object(
                        provenance,
                        "git_branch",
                        return_value="main",
                    ):
                        with mock.patch.object(
                            provenance,
                            "main_distance",
                            return_value=(0, 0, "main"),
                        ):
                            with mock.patch.object(
                                provenance,
                                "workflow_version",
                                return_value="0.5.0",
                            ):
                                code = provenance.render_footer(
                                    workflow, issue, target
                                )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            data = json.loads(
                (artifact_dir / "provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(data["events"]), 2)
            self.assertEqual(data["events"][-1]["ai_workflows"], "newhash")
            content = target.read_text(encoding="utf-8")
            self.assertIn("Committed: commit @ prd 0.5.0 - newhash", content)
            self.assertNotIn("oldhash", content)

    def test_render_replaces_heading_only_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = "OSAC-TEST"
            workflow = "prd"
            artifact_dir = root / ".artifacts" / workflow / issue
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "provenance.json").write_text(
                json.dumps(
                    {
                        "workflow": workflow,
                        "events": [
                            {
                                "phase": "draft",
                                "authoring_mode": "skill",
                                "workflow_version": "0.5.0",
                                "ai_workflows": "abc",
                                "source_repo": "def",
                                "source_repo_branch": "main",
                            }
                        ],
                        "drift": {"context_changed": False},
                    }
                ),
                encoding="utf-8",
            )
            target = root / "prd.md"
            target.write_text(
                "# PRD\n\n## Provenance\n\nHand-edited stale line\n",
                encoding="utf-8",
            )

            cwd = Path.cwd()
            try:
                os.chdir(root)
                code = provenance.render_footer(workflow, issue, target)
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            self.assertNotIn("Hand-edited stale line", content)
            self.assertNotIn("Hand-edited", content)
            self.assertEqual(content.count("## Provenance"), 1)
            self.assertIn("Authored: draft @ prd 0.5.0 - abc", content)

    def test_render_footer_replaces_existing_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = "OSAC-TEST"
            workflow = "prd"
            artifact_dir = root / ".artifacts" / workflow / issue
            artifact_dir.mkdir(parents=True)
            provenance_path = artifact_dir / "provenance.json"
            provenance_path.write_text(
                json.dumps(
                    {
                        "workflow": workflow,
                        "events": [
                            {
                                "phase": "draft",
                                "authoring_mode": "skill",
                                "workflow_version": "0.5.0",
                                "ai_workflows": "abc",
                                "source_repo": "def",
                                "source_repo_branch": "main",
                                "commits_behind_main": 0,
                            }
                        ],
                        "drift": {"context_changed": False},
                    }
                ),
                encoding="utf-8",
            )
            target = root / "prd.md"
            target.write_text(
                "# PRD\n\n---\n\n## Provenance\n\nOld footer\n",
                encoding="utf-8",
            )

            cwd = Path.cwd()
            try:
                os.chdir(root)
                code = provenance.render_footer(workflow, issue, target)
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            self.assertNotIn("Old footer", content)
            self.assertIn("draft @ prd 0.5.0 - abc", content)
            self.assertIn("<!-- osac-provenance:", content)

    def test_render_footer_auto_captures_commit_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = "OSAC-TEST"
            workflow = "prd"
            target = root / "prd.md"
            target.write_text("# PRD\n", encoding="utf-8")
            artifact_dir = root / ".artifacts" / workflow / issue

            cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(
                    provenance,
                    "capture_event",
                    wraps=provenance.capture_event,
                ) as capture_mock:
                    with mock.patch.object(
                        provenance,
                        "git_describe",
                        side_effect=lambda _root: "abc1234",
                    ):
                        with mock.patch.object(
                            provenance,
                            "git_branch",
                            return_value="main",
                        ):
                            with mock.patch.object(
                                provenance,
                                "main_distance",
                                return_value=(0, 0, "main"),
                            ):
                                with mock.patch.object(
                                    provenance,
                                    "workflow_version",
                                    return_value="0.5.0",
                                ):
                                    code = provenance.render_footer(
                                        workflow, issue, target
                                    )
                self.assertEqual(capture_mock.call_count, 1)
                capture_mock.assert_called_with(
                    workflow, issue, "commit", "skill"
                )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            self.assertTrue((artifact_dir / "provenance.json").is_file())
            content = target.read_text(encoding="utf-8")
            self.assertIn("Committed: commit @ prd 0.5.0 - abc1234", content)
            self.assertIn("commit-time snapshot only", content)

    def test_render_footer_does_not_auto_capture_when_log_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = "OSAC-TEST"
            workflow = "prd"
            artifact_dir = root / ".artifacts" / workflow / issue
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "provenance.json").write_text(
                json.dumps(
                    {
                        "workflow": workflow,
                        "events": [
                            {
                                "phase": "draft",
                                "authoring_mode": "skill",
                                "workflow_version": "0.5.0",
                                "ai_workflows": "abc",
                                "source_repo": "def",
                                "source_repo_branch": "main",
                            }
                        ],
                        "drift": {"context_changed": False},
                    }
                ),
                encoding="utf-8",
            )
            target = root / "prd.md"
            target.write_text("# PRD\n", encoding="utf-8")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(
                    provenance, "capture_event"
                ) as capture_mock:
                    code = provenance.render_footer(workflow, issue, target)
            finally:
                os.chdir(cwd)

            capture_mock.assert_not_called()
            self.assertEqual(code, 0)
            self.assertIn("Authored: draft @ prd 0.5.0 - abc", target.read_text())

    def test_render_footer_allow_missing_strips_existing_footer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "prd.md"
            target.write_text(
                "# PRD\n\n---\n\n## Provenance\n\n"
                "Authored: draft @ prd 0.5.0 - stale\n\n"
                '<!-- osac-provenance:{"schema_version":1,"provenance_kind":"session"} -->\n',
                encoding="utf-8",
            )

            cwd = Path.cwd()
            try:
                os.chdir(root)
                code = provenance.render_footer(
                    "prd",
                    "OSAC-TEST",
                    target,
                    allow_missing=True,
                )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            content = target.read_text(encoding="utf-8")
            self.assertNotIn("## Provenance", content)
            self.assertNotIn("stale", content)
            self.assertIn('"provenance_kind":"declined"', content)

    def test_provenance_path_rejects_traversal(self) -> None:
        with self.assertRaises(ValueError):
            provenance.provenance_path("prd", "../../tmp")

    def test_workspace_root_walks_up_to_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            (root / ".git").mkdir()
            cwd = Path.cwd()
            try:
                os.chdir(nested)
                with mock.patch.object(provenance, "repo_root", return_value=root):
                    self.assertEqual(provenance.workspace_root(), root)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
