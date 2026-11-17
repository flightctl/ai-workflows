"""Real Git/consumer regressions for canonical workflow state."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from artifacts import ArtifactError, artifact_directory, artifact_root, canonical_path


SCRIPTS = Path(__file__).resolve().parent
SOURCE = SCRIPTS.parents[1]


class ArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="artifact tests ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.main = self.directory / "main checkout"
        self.main.mkdir()
        self.git("init", "-q", cwd=self.main)
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "fixture",
                 cwd=self.main)

    def git(self, *args: str, cwd: Path) -> str:
        return subprocess.run(["git", *args], cwd=cwd, check=True,
                              capture_output=True, text=True).stdout

    def linked(self, name: str = "linked checkout", detached: bool = False) -> Path:
        target = self.directory / name
        options = ["--detach"] if detached else ["-b", "topic"]
        self.git("worktree", "add", "-q", *options, str(target), cwd=self.main)
        return target

    def cli(self, script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(script), *args], cwd=cwd,
                              capture_output=True, text=True)

    def test_single_checkout_nested_and_config(self) -> None:
        nested = self.main / "nested directory" / "deeper"
        nested.mkdir(parents=True)
        self.assertEqual(artifact_root(nested), self.main / ".artifacts")
        self.assertEqual(canonical_path(".artifacts/config.json", nested),
                         self.main / ".artifacts/config.json")
        self.assertFalse((self.main / ".artifacts").exists())

    def test_plan_and_publish_metadata_visible_in_two_worktrees(self) -> None:
        first = self.linked()
        second = self.linked("detached checkout", detached=True)
        nested = first / "nested path"
        nested.mkdir()
        resolved = self.cli(SCRIPTS / "artifacts.py", "implement", "TEST-1", cwd=nested)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        directory = Path(resolved.stdout.strip())
        directory.mkdir(parents=True)
        (directory / "02-plan.md").write_text("approved plan\n")
        published = self.cli(SCRIPTS / "publish.py", "save-metadata", "--file",
                             ".artifacts/implement/TEST-1/publish-metadata.json",
                             "branch=topic", cwd=first)
        self.assertEqual(published.returncode, 0, published.stderr)
        resumed = self.cli(SCRIPTS / "artifacts.py", "implement", "TEST-1", cwd=second)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(resumed.stdout, resolved.stdout)
        self.assertEqual((Path(resumed.stdout.strip()) / "02-plan.md").read_text(),
                         "approved plan\n")
        metadata = json.loads((directory / "publish-metadata.json").read_text())
        self.assertEqual(metadata["branch"], "topic")
        hashed = self.cli(SOURCE / "design/scripts/sync_helper.py", "compute-hash",
                          ".artifacts/implement/TEST-1/02-plan.md", cwd=second)
        self.assertEqual(hashed.returncode, 0, hashed.stderr)
        self.assertFalse((first / ".artifacts").exists())
        self.assertFalse((second / ".artifacts").exists())

    def test_nul_parsing_handles_newline_and_detached_paths(self) -> None:
        linked = self.linked('linked\n"quoted" path', detached=True)
        self.assertEqual(artifact_root(linked), self.main / ".artifacts")

    def test_main_worktree_is_not_the_branch_named_main(self) -> None:
        self.git("branch", "-m", "primary", cwd=self.main)
        linked = self.directory / "branch main"
        self.git("worktree", "add", "-q", "-b", "main", str(linked), cwd=self.main)
        self.assertEqual(artifact_root(linked), self.main / ".artifacts")

    def test_nested_validation_worktree_state_paths(self) -> None:
        linked = self.main / ".artifacts/rebase-stack/worktrees/validation"
        linked.parent.mkdir(parents=True)
        self.git("worktree", "add", "-q", "--detach", str(linked), cwd=self.main)
        self.assertEqual(artifact_root(linked), self.main / ".artifacts")
        self.assertEqual(canonical_path(linked / ".artifacts/implement/TEST-1/02-plan.md"),
                         self.main / ".artifacts/implement/TEST-1/02-plan.md")

    def test_nonrepo_and_bare_errors(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "non-bare Git"):
            artifact_root(self.directory)
        bare = self.directory / "bare.git"
        self.git("init", "--bare", "-q", str(bare), cwd=self.directory)
        with self.assertRaisesRegex(ArtifactError, "bare repository"):
            artifact_root(bare)
        error = self.cli(SCRIPTS / "artifacts.py", cwd=self.directory)
        self.assertEqual(error.returncode, 1)
        self.assertIn("ERROR:", error.stderr)

    def test_legacy_conflict_refused_without_mutation(self) -> None:
        linked = self.linked()
        canonical = artifact_directory("implement", "TEST-1", self.main)
        legacy = linked / ".artifacts/implement/TEST-1"
        canonical.mkdir(parents=True)
        legacy.mkdir(parents=True)
        (canonical / "02-plan.md").write_text("canonical")
        (legacy / "02-plan.md").write_text("legacy")
        (legacy / "publish-metadata.json").write_text('{"branch":"old"}')
        before = {path: path.read_bytes() for base in (canonical, legacy)
                  for path in base.iterdir()}
        for worktree in (self.main, linked):
            with self.assertRaisesRegex(ArtifactError, "conflict/overlap") as error:
                artifact_root(worktree)
            self.assertIn("publish-metadata.json", str(error.exception))
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertEqual(set(legacy.iterdir()), {legacy / "02-plan.md", legacy / "publish-metadata.json"})
        refused = self.cli(SCRIPTS / "publish.py", "save-metadata", "--file",
                           ".artifacts/implement/TEST-1/publish-metadata.json",
                           "branch=new", cwd=linked)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("reconciliation required", refused.stderr)
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertFalse((canonical / "publish-metadata.json").exists())

    def test_repository_config_is_shared(self) -> None:
        linked = self.linked()
        config = canonical_path(".artifacts/config.json", self.main)
        config.parent.mkdir()
        config.write_text('{"docs_repo_path":"/example/docs"}')
        resumed = canonical_path(".artifacts/config.json", linked)
        self.assertEqual(resumed, config)
        self.assertEqual(json.loads(resumed.read_text())["docs_repo_path"], "/example/docs")

    def test_rebase_start_preserves_spaced_baseline_argument(self) -> None:
        instructions = (SOURCE / "rebase-stack/skills/start.md").read_text()
        command = next(block.split("```", 1)[0]
                       for block in instructions.split("```bash\n")[1:]
                       if block.startswith("baseline_args="))
        scripts = self.directory / "installed scripts"
        scripts.mkdir()
        (scripts / "validate-baseline.sh").write_text("exit 0\n")
        (scripts / "stack-status.sh").write_text("printf '%s\\n' \"$@\"\n")
        state = artifact_directory("rebase-stack", repo=self.main)
        state.mkdir(parents=True)
        (state / "context.json").write_text("{}")
        baseline = state / "pre-rebase-state.json"
        baseline.write_text("{}")
        for exists in (True, False):
            with self.subTest(baseline_exists=exists):
                if not exists:
                    baseline.unlink()
                result = subprocess.run(
                    ["bash", "-c", command.replace("{scripts}", str(scripts))],
                    cwd=self.main, capture_output=True, text=True,
                    env={**os.environ, "ARTIFACTS_ROOT": str(state.parent)},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = (["--baseline", str(baseline)] if exists else [""])
                self.assertEqual(result.stdout.splitlines(), expected + ["status exit: 0"])

    def test_disjoint_legacy_state_also_refused(self) -> None:
        linked = self.linked()
        legacy = linked / ".artifacts/config.json"
        legacy.parent.mkdir()
        legacy.write_text("{}")
        with self.assertRaisesRegex(ArtifactError, "legacy state"):
            artifact_root(self.main)
        self.assertFalse((self.main / ".artifacts").exists())

    def test_ui_response_cleanup_expands_only_response_glob(self) -> None:
        instructions = (SOURCE / "ui-design/skills/respond.md").read_text()
        command = next(line for line in instructions.splitlines()
                       if line.startswith("rm -f ") and "pr-response-" in line)
        state = artifact_directory("ui-design", "feature", self.main)
        state.mkdir(parents=True)
        preserved = state / "05-review-responses.md"
        preserved.write_text("response log")
        for name in ("pr-response-1.md", "pr-response-2.md"):
            (state / name).write_text("temporary response")
        for invocation in range(2):
            with self.subTest(invocation=invocation):
                result = subprocess.run(
                    ["bash", "-c", command.replace("{workspace-id}", "feature")],
                    cwd=self.main, capture_output=True, text=True,
                    env={**os.environ, "ARTIFACTS_ROOT": str(state.parents[1])},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(list(state.iterdir()), [preserved])
                self.assertEqual(preserved.read_text(), "response log")

    def test_symlinks_and_traversal_refused(self) -> None:
        root = self.main / ".artifacts"
        root.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaisesRegex(ArtifactError, "symlink"):
            artifact_root(self.main)
        root.unlink()
        root.mkdir()
        (root / "implement").symlink_to(self.directory, target_is_directory=True)
        with self.assertRaisesRegex(ArtifactError, "symlink"):
            artifact_directory("implement", "TEST-1", self.main)
        for path in (".artifacts/../escape", root / "implement/../../escape"):
            with self.assertRaises(ArtifactError):
                canonical_path(path, self.main)
        for context in ("..", "../escape", "/absolute", "nested/name", "bad\\name"):
            with self.assertRaises(ArtifactError):
                artifact_directory("bugfix", context, self.main)

    def test_issue_less_and_document_paths_preserved(self) -> None:
        for workflow, context in (("triage", "PROJECT"), ("sizing", "release 1"),
                                  ("skill-reviewer", "bugfix")):
            self.assertEqual(artifact_directory(workflow, context, self.main),
                             self.main / ".artifacts" / workflow / context)
        self.assertEqual(artifact_directory("rebase-stack", repo=self.main),
                         self.main / ".artifacts/rebase-stack")
        published = self.directory / "docs/feature/design.md"
        self.assertEqual(canonical_path(published, self.main), published)

    def test_source_state_survives_document_repo_cwd(self) -> None:
        source_state = artifact_directory("design", "TEST-1", self.main) / "publish-metadata.json"
        docs = self.directory / "docs checkout"
        docs.mkdir()
        self.git("init", "-q", cwd=docs)
        result = self.cli(SCRIPTS / "publish.py", "save-metadata", "--file",
                          str(source_state), "branch=docs", cwd=docs)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(source_state.read_text())["branch"], "docs")
        self.assertFalse((docs / ".artifacts").exists())

    def test_provenance_cve_and_sizing_use_shared_state(self) -> None:
        linked = self.linked()
        for module_path, expression, suffix in (
            (SCRIPTS, "from provenance import provenance_path; print(provenance_path('design', 'TEST-1'))",
             "design/TEST-1/provenance.json"),
            (SOURCE / "cve-fix/scripts", "from _common import artifact_dir; print(artifact_dir('PROJECT'))",
             "cve-fix/PROJECT"),
            (SOURCE / "sizing/scripts", "from apply_plan import _directory; print(_directory('release'))",
             "sizing/release"),
        ):
            result = subprocess.run(
                [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(module_path)!r}); {expression}"],
                cwd=linked, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(self.main / ".artifacts" / suffix))

    def test_provenance_records_linked_source_branch_not_storage_branch(self) -> None:
        linked = self.linked()
        result = self.cli(SCRIPTS / "provenance.py", "capture", "--workflow", "design",
                          "--issue", "TEST-1", "--phase", "draft", "--authoring-mode", "skill",
                          cwd=linked)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.main / ".artifacts/design/TEST-1/provenance.json"
        self.assertEqual(json.loads(state.read_text())["events"][0]["source_repo_branch"], "topic")

    def test_common_consumers_refuse_final_file_symlinks_without_mutation(self) -> None:
        linked = self.linked()
        outside = self.directory / "outside.json"
        outside.write_text('{"sentinel": true}')
        for case_index, (package, filename, expression) in enumerate((
            ("cve-fix", "result.json", "write_json({}, target.parent, target.name)"),
            ("cve-fix", "context.md", "read_context_md(target.parent)"),
            ("sizing", "state.json", "read_json(target)"),
            ("sizing", "state.json", "write_json(target, {})"),
            ("sizing", ".state.json.tmp", "write_json(target.with_name('state.json'), {})"),
            ("sizing", "state.json", "write_files_transactionally({target: b'changed'})"),
        )):
            with self.subTest(package=package, expression=expression, filename=filename):
                outside.write_text('{"sentinel": true}')
                target = artifact_directory(package, f"TEST-{case_index}", self.main) / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside)
                result = subprocess.run(
                    [sys.executable, "-c",
                     f"import sys; from pathlib import Path; "
                     f"sys.path.insert(0, {str(SOURCE / package / 'scripts')!r}); "
                     f"from _common import *; target=Path({str(target)!r}); {expression}"],
                    cwd=linked, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("symlink", result.stderr)
                self.assertTrue(target.is_symlink())
                self.assertEqual(outside.read_text(), '{"sentinel": true}')
                target.unlink()

    def test_rebase_snapshot_refuses_symlinked_state_and_read_targets(self) -> None:
        linked = self.linked()
        outside = self.directory / "outside state"
        outside.mkdir()
        snapshot = outside / "pre-rebase-state.json"
        snapshot.write_text('{"branches": []}')
        state = self.main / ".artifacts/rebase-stack"
        state.parent.mkdir()
        for suffix, command in (("", "restore-plan"),
                                ("pre-rebase-state.json", "restore-plan"),
                                ("pre-rebase-state.json", "verify")):
            with self.subTest(suffix=suffix, command=command):
                if suffix:
                    state.mkdir(exist_ok=True)
                    target = state / suffix
                    target.symlink_to(snapshot)
                else:
                    target = state
                    target.symlink_to(outside, target_is_directory=True)
                result = subprocess.run(
                    ["bash", str(SOURCE / "rebase-stack/scripts/snapshot.sh"), command],
                    cwd=linked, input="{}", capture_output=True, text=True,
                )
                try:
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("symlink", result.stderr)
                    self.assertTrue(target.is_symlink())
                    self.assertEqual(snapshot.read_text(), '{"branches": []}')
                finally:
                    target.unlink()

    def test_rebase_validation_refuses_symlinked_log_and_worktree_paths(self) -> None:
        linked = self.linked()
        branch = self.git("branch", "--show-current", cwd=self.main).strip()
        digest = subprocess.run(
            ["git", "hash-object", "--stdin"], cwd=linked, input=branch,
            check=True, capture_output=True, text=True,
        ).stdout.strip()[:8]
        safe = branch.replace("/", "-") + "-" + digest
        outside = self.directory / "outside state"
        outside.mkdir()
        outside_log = outside / "outside.log"
        outside_log.write_text("sentinel")
        state = artifact_directory("rebase-stack", repo=self.main)
        state.mkdir(parents=True)
        for suffix, directory in (("logs", True), (f"logs/{safe}.log", False),
                                  ("worktrees", True), (f"worktrees/{safe}", True)):
            with self.subTest(suffix=suffix):
                target = state / suffix
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside if directory else outside_log,
                                  target_is_directory=directory)
                result = subprocess.run(
                    ["bash", str(SOURCE / "rebase-stack/scripts/validate-branches.sh"),
                     "--test", "true", branch],
                    cwd=linked, capture_output=True, text=True,
                )
                try:
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("symlink", result.stderr)
                    self.assertTrue(target.is_symlink())
                    self.assertEqual(list(outside.iterdir()), [outside_log])
                    self.assertEqual(outside_log.read_text(), "sentinel")
                    self.assertEqual(self.git("branch", "--show-current", cwd=linked).strip(),
                                     "topic")
                finally:
                    shutil.rmtree(state)
                    state.mkdir()

    def test_cve_consumers_refuse_final_path_symlinks_without_mutation(self) -> None:
        linked = self.linked()
        outside = self.directory / "outside.json"
        cases = (
            ("backport", "backport-log.md",
             "consumer.write_backport_log(target.parent, 'fixture', 'abc', [])"),
            ("patch", "patch-log.md",
             "consumer.append_patch_log(target.parent, 'CVE-2026-1234', 'pkg', "
             "1, 'fixture', False, 'fixture', 1)"),
            ("patch", "patch-log.md",
             "consumer._count_existing_attempts(target.parent, 'CVE-2026-1234', 'pkg')"),
            ("patch", "scan-result.json",
             "consumer.run_verification_scan(target.parent, Path.cwd(), "
             "'CVE-2026-1234', 'pkg', '.')"),
            ("create_pr", "context.md",
             "consumer.record_pr_in_context(target.parent, 'https://example.invalid/pr/1')"),
            ("close", "context.md", "consumer.collect_artifacts(target.parent)"),
            ("close", "scan-result.json", "consumer.load_vex_justification(target.parent)"),
            ("close", "scan-results.md", "consumer.load_vex_justification(target.parent)"),
            ("close", "close-report.md",
             "consumer.write_close_report(target.parent, [], [], [], 'Done')"),
            ("prepare_report", "report-input.json", "consumer._write_json(target, {})"),
            ("finalize_report", "report-input.json", "consumer._read_json(target)"),
            ("finalize_report", "report-result.json", "consumer._write_json(target, {})"),
            ("finalize_report", "report.md",
             "(target.parent / 'report-input.json').write_text('{}')\n"
             "with mock.patch.object(consumer, 'finalize_report_data', "
             "return_value=({'status': 'success'}, '# fixture')):\n"
             "    raise SystemExit(consumer.main(['--output-dir', str(target.parent)]))"),
            ("scan", "scan-results.md",
             "os.environ['OUTPUT_DIR'] = str(target.parent)\n"
             "sys.argv = ['scan.py', str(Path.cwd()), 'CVE-2026-1234', 'pkg', '--write-report']\n"
             "consumer.main()"),
            ("report", "report-intermediate.md",
             "with mock.patch.multiple(consumer, "
             "get_jira_env=mock.Mock(return_value=('https://example.invalid', 'fixture', None)), "
             "resolve_jira_field_ids=mock.Mock(return_value={}), "
             "fetch_all_issues=mock.Mock(return_value=[])):\n"
             "    consumer.run_report(consumer.parse_args(['TEST', '--output-dir', str(target.parent)]))"),
        )
        for case_index, (module, filename, expression) in enumerate(cases):
            with self.subTest(module=module, filename=filename, expression=expression):
                outside.write_text('{"sentinel": true}')
                target = artifact_directory("cve-fix", f"TEST-{case_index}", self.main) / filename
                target.parent.mkdir(parents=True)
                target.symlink_to(outside)
                result = subprocess.run(
                    [sys.executable, "-c",
                     "import os, sys; from pathlib import Path; from unittest import mock; "
                     f"sys.path.insert(0, {str(SOURCE / 'cve-fix/scripts')!r}); "
                     f"import {module} as consumer; target=Path({str(target)!r})\n{expression}"],
                    cwd=linked, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("symlink", result.stderr + result.stdout)
                self.assertTrue(target.is_symlink())
                self.assertEqual(outside.read_text(), '{"sentinel": true}')

    def test_triage_writer_refuses_symlink_result_without_mutation(self) -> None:
        linked = self.linked()
        outside = self.directory / "outside.json"
        outside.write_text('{"sentinel": true}')
        target = artifact_directory("triage", "TEST", self.main) / "issues.json"
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; from pathlib import Path; "
             f"sys.path.insert(0, {str(SOURCE / 'triage/scripts')!r}); "
             f"from scan import write_json_file; "
             f"write_json_file(Path({str(target)!r}), {{'issues': []}})"],
            cwd=linked, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("symlink", result.stderr)
        self.assertTrue(target.is_symlink())
        self.assertEqual(outside.read_text(), '{"sentinel": true}')

    def test_design_child_readers_refuse_symlinks_without_mutation(self) -> None:
        linked = self.linked()
        outside = self.directory / "outside.md"
        outside.write_text("# Outside document\n")
        expressions = (
            "compute_file_hash(target)",
            "read_frontmatter(target)",
            "_extract_title_from_file(target)",
            "_read_file_content(target)",
            "extract_required_refs(target)",
        )
        for case_index, expression in enumerate(expressions):
            with self.subTest(expression=expression):
                target = artifact_directory("design", f"TEST-{case_index}", self.main)
                target = target / "06-stories/epic-1/story-01-fixture.md"
                target.parent.mkdir(parents=True)
                target.symlink_to(outside)
                result = subprocess.run(
                    [sys.executable, "-c",
                     f"import sys; from pathlib import Path; "
                     f"sys.path.insert(0, {str(SOURCE / 'design/scripts')!r}); "
                     f"import sync_helper as consumer; target=Path({str(target)!r}); "
                     f"consumer.{expression}"],
                    cwd=linked, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("symlink", result.stderr)
                self.assertTrue(target.is_symlink())
                self.assertEqual(outside.read_text(), "# Outside document\n")

    def test_design_discovery_refuses_child_directory_symlinks(self) -> None:
        linked = self.linked()
        outside = self.directory / "outside stories"
        outside.mkdir()
        for case_index, suffix in enumerate(("06-stories", "06-stories/epic-1")):
            with self.subTest(suffix=suffix):
                state = artifact_directory("design", f"TEST-{case_index}", self.main)
                target = state / suffix
                target.parent.mkdir(parents=True)
                target.symlink_to(outside, target_is_directory=True)
                result = self.cli(SOURCE / "design/scripts/sync_helper.py",
                                  "detect-changes", str(state), cwd=linked)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("symlink", result.stderr)
                self.assertTrue(target.is_symlink())
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse((state / "sync-manifest.json").exists())

    def test_reviewer_refuses_symlink_hash_log_without_mutation(self) -> None:
        linked = self.linked()
        target = artifact_directory("skill-reviewer", "fixture", self.main) / "file-hashes.json"
        target.parent.mkdir(parents=True)
        outside = self.directory / "outside.json"
        outside.write_text('{}')
        target.symlink_to(outside)
        skill = linked / "fixture"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Fixture\n")
        result = self.cli(SOURCE / "skill-reviewer/scripts/pre-review-checks.py",
                          str(skill), cwd=linked)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(outside.read_text(), '{}')
        self.assertTrue(target.is_symlink())

    def test_provenance_render_target_is_canonical_even_when_declined(self) -> None:
        linked = self.linked()
        target = artifact_directory("prd", "TEST-1", self.main) / "03-prd.md"
        target.parent.mkdir(parents=True)
        target.write_text("# PRD\n")
        for options in ((), ("--allow-missing",)):
            result = self.cli(SCRIPTS / "provenance.py", "render", "--workflow", "prd",
                              "--issue", "TEST-1", "--target",
                              ".artifacts/prd/TEST-1/03-prd.md", *options, cwd=linked)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ai-workflow-provenance:", target.read_text())
        self.assertFalse((linked / ".artifacts").exists())

    def test_provenance_declined_render_refuses_legacy_state_without_mutation(self) -> None:
        linked = self.linked()
        legacy = linked / ".artifacts/prd/TEST-1/03-prd.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("# Legacy PRD\n")
        result = self.cli(SCRIPTS / "provenance.py", "render", "--workflow", "prd",
                          "--issue", "TEST-1", "--target", str(legacy),
                          "--allow-missing", cwd=linked)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("reconciliation required", result.stderr)
        self.assertEqual(legacy.read_text(), "# Legacy PRD\n")
        self.assertFalse((self.main / ".artifacts").exists())

    def test_provenance_refuses_symlink_target_and_log_without_mutation(self) -> None:
        directory = artifact_directory("prd", "TEST-1", self.main)
        directory.mkdir(parents=True)
        outside = self.directory / "outside.md"
        outside.write_text("# Do not change\n")
        target = directory / "03-prd.md"
        target.symlink_to(outside)
        for options in ((), ("--allow-missing",)):
            result = self.cli(SCRIPTS / "provenance.py", "render", "--workflow", "prd",
                              "--issue", "TEST-1", "--target", str(target),
                              *options, cwd=self.main)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("symlink", result.stderr)
        target.unlink()
        (directory / "provenance.json").symlink_to(outside)
        result = self.cli(SCRIPTS / "provenance.py", "capture", "--workflow", "prd",
                          "--issue", "TEST-1", "--phase", "draft", "--authoring-mode", "skill",
                          cwd=self.main)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(outside.read_text(), "# Do not change\n")


if __name__ == "__main__":
    unittest.main()
