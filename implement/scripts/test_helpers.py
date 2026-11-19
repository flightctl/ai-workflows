"""Exercise the helpers through their CLI, including refusal and preservation."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
PLAN = """# Plan

## Task Breakdown

### Task 1: First
- **Files:** first.go
- **Status:** Pending

### Task 2: Second
- **Status:** Pending

## Test Plan Coverage

| TC ID | Title | Covered by Task | Notes |
|-------|-------|-----------------|-------|
| TC-FR1-01 | First | Task 1 | |
| TC-FR1-02 | Second | Task 2 | |
| TC-NFR1-01 | Load | N/A | External load infrastructure |

## Scope Baseline
Keep this text unchanged.
"""


def case(tc):
    return f"""## {tc}: Scenario

### Preconditions
- Ready

### Steps
1. Invoke API

### Expected Results
- Observable result

"""


TESTPLAN = "# Story Test Plan\n\n" + "".join(case(tc) for tc in ("TC-FR1-01", "TC-FR1-02", "TC-NFR1-01"))


class HelpersTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.plan = self.root / "02-plan.md"
        self.testplan = self.root / "testplan.md"
        self.plan.write_text(PLAN)
        self.testplan.write_text(TESTPLAN)

    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                              cwd=self.root, capture_output=True, text=True)

    def complete(self):
        return self.run_cli("task-state.py", "--plan", self.plan, "--task", 1)

    def check(self):
        return self.run_cli("check-testplan.py", "--plan", self.plan,
                            "--testplan", self.testplan, "--task", 1)

    def test_completion_preserves_other_bytes_and_is_idempotent(self):
        original = PLAN.replace("\n", "\r\n").encode()
        self.plan.write_bytes(original)
        self.plan.chmod(0o640)
        self.assertEqual(self.complete().returncode, 0)
        expected = original.replace(b"Status:** Pending", b"Status:** Done", 1)
        self.assertEqual(self.plan.read_bytes(), expected)
        self.assertEqual(self.plan.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.complete().returncode, 0)
        self.assertEqual(self.plan.read_bytes(), expected)

    def test_refuses_ambiguous_or_blocked_update_without_writing(self):
        for text in (PLAN.replace("### Task 2:", "### Task 1:"),
                     PLAN.replace("- **Status:** Pending", "- **Status:** Other", 1),
                     PLAN.replace("- **Files:** first.go", "- **Status:** Pending"),
                     PLAN + "\n## Pending Scope Decision\nDecision needed\n",
                     PLAN.replace("### Task 1:", "### Task 9:")):
            with self.subTest(text=text):
                self.plan.write_text(text)
                self.assertEqual(self.complete().returncode, 1)
                self.assertEqual(self.plan.read_text(), text)

    def test_fenced_task_examples_are_ignored(self):
        self.plan.write_text(PLAN.replace("### Task 1: First", "```markdown\n### Task 1: Example\n- **Status:** Pending\n```\n### Task 1: First"))
        self.assertEqual(self.complete().returncode, 0)
        self.assertIn("### Task 1: Example\n- **Status:** Pending", self.plan.read_text())

    def test_check_selects_case_and_preserves_files(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual([c["id"] for c in report["cases"]], ["TC-FR1-01"])
        self.assertIn("Observable result", report["cases"][0]["body"])
        self.assertEqual(report["not_applicable"][0]["id"], "TC-NFR1-01")
        self.assertEqual(self.plan.read_text(), PLAN)
        self.assertEqual(self.testplan.read_text(), TESTPLAN)

    def test_check_rejects_missing_duplicate_or_incomplete_cases(self):
        for text in ("", TESTPLAN + case("TC-FR1-01"),
                     TESTPLAN.replace("### Steps", "### Actions", 1),
                     TESTPLAN.replace("- Observable result", "", 1),
                     TESTPLAN.replace("TC-FR1-01:", "TC-UNKNOWN-01:", 1)):
            with self.subTest(text=text):
                self.testplan.write_text(text)
                self.assertEqual(self.check().returncode, 1)

    def test_check_rejects_bad_mappings(self):
        for text in (PLAN.replace("Task 1 |", "Task 9 |"),
                     PLAN.replace("External load infrastructure", ""),
                     PLAN.replace("TC-FR1-02 | Second", "TC-FR1-01 | Second"),
                     PLAN[:PLAN.index("## Test Plan Coverage")]):
            with self.subTest(text=text):
                self.plan.write_text(text)
                self.assertEqual(self.check().returncode, 1)

    def test_shared_task_mapping_and_escaped_table_cell(self):
        self.plan.write_text(PLAN.replace("First | Task 1 |", r"First \| detail | Task 1, Task 2 |"))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["cases"][0]["id"], "TC-FR1-01")

    def test_scripts_work_through_installed_directory_symlink(self):
        installed = self.root / "installed-implement"
        installed.symlink_to(SCRIPTS.parent, target_is_directory=True)
        result = subprocess.run([sys.executable, str(installed / "scripts/check-testplan.py"),
                                 "--plan", str(self.plan), "--testplan", str(self.testplan)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_testplan_only_skips_without_mapping_section(self):
        self.testplan.unlink()
        self.assertEqual(self.check().returncode, 1)
        self.plan.write_text(PLAN[:PLAN.index("## Test Plan Coverage")])
        result = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")



if __name__ == "__main__":
    unittest.main()
