#!/usr/bin/env python3
"""Exercise adapter routing, ownership, and compatibility without a model."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


class CodexAdaptersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiw adapters ")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo, self.home, self.project = (root / n for n in ("repo", "home", "project"))
        for directory in (self.repo, self.home, self.project):
            directory.mkdir()
        for name in ("install.sh", "uninstall.sh"):
            shutil.copy2(REPO / name, self.repo / name)
        for name in ("bugfix", "sizing", "docs-writer", "_shared", "skills/report-bug"):
            shutil.copytree(REPO / name, self.repo / name)
        self.env = {**os.environ, "HOME": str(self.home)}
        self.skills = self.home / ".agents/skills"

    def run_script(self, script, *args, check=True):
        return subprocess.run(
            ["bash", str(self.repo / script), *args], env=self.env,
            cwd=self.project, text=True, capture_output=True, check=check,
        )

    def install(self, *args):
        return self.run_script("install.sh", "codex", "--packages",
                               "bugfix,sizing,docs-writer,report-bug", "--no-update-timer", *args)

    def test_unique_names_and_existing_command_routes(self):
        self.install()
        for package in ("bugfix", "sizing", "docs-writer"):
            self.assertTrue((self.skills / package).is_symlink())
            for command in (self.repo / package / "commands").glob("*.md"):
                name = f"{package}-{command.stem}"
                adapter = self.skills / name
                body = (adapter / "SKILL.md").read_text()
                self.assertIn(f"name: {name}\n", body)
                self.assertLess(len(body.splitlines()), 30)
                self.assertIn("$ARGUMENTS", body)
                self.assertEqual((adapter / "workflow/commands" / command.name).resolve(), command)
        # Same phase name in two workflows must have distinct discovery names.
        self.assertTrue((self.skills / "bugfix-assess/SKILL.md").is_file())
        self.assertTrue((self.skills / "sizing-assess/SKILL.md").is_file())
        self.assertFalse((self.skills / "report-bug-report-bug").exists())
        command = self.skills / "bugfix-assess/workflow/commands/assess.md"
        self.assertIn('PHASE=assess', command.read_text())
        dispatcher = command.parent / "../skills/dispatch.md"
        self.assertIn("phase-override-resolution.md", dispatcher.read_text())
        # Docs-writer's public gather command maps to gather-context.md.
        controller = self.skills / "docs-writer-gather/workflow/skills/controller.md"
        self.assertIn("gather-context.md", controller.read_text())
        override = self.project / ".workflows/bugfix/skills/assess.md"
        override.parent.mkdir(parents=True)
        override.write_text("Project-specific assessment instructions.\n")
        resolved = subprocess.run(
            ["python3", str(self.repo / "_shared/scripts/resolve-phase.py"), "bugfix", "assess.md"],
            env=self.env, cwd=self.project, capture_output=True, text=True, check=True,
        )
        self.assertEqual(resolved.stdout.strip(), ".workflows/bugfix/skills/assess.md")

    def test_refresh_and_selective_uninstall(self):
        self.install()
        adapter = self.skills / "bugfix-assess"
        (adapter / "SKILL.md").write_text("stale generated content")
        self.install()
        self.assertIn("name: bugfix-assess", (adapter / "SKILL.md").read_text())
        # Cleanup must still work after a command has been removed upstream.
        (self.repo / "bugfix/commands/assess.md").unlink()
        (adapter / "personal.txt").write_text("keep")
        self.run_script("uninstall.sh", "codex", "--packages", "bugfix")
        self.assertFalse((adapter / "SKILL.md").exists())
        self.assertEqual((adapter / "personal.txt").read_text(), "keep")
        self.assertTrue((self.skills / "sizing-assess/SKILL.md").is_file())
        self.assertTrue((self.skills / "_shared").is_symlink())
        self.run_script("uninstall.sh", "codex")
        self.assertFalse((self.skills / "sizing-assess").exists())
        self.assertFalse((self.skills / "_shared").exists())

    def test_preserves_unmanaged_paths_and_symlinks(self):
        self.skills.mkdir(parents=True)
        user_skill = self.skills / "bugfix-assess"
        user_skill.mkdir()
        (user_skill / "SKILL.md").write_text("user skill")
        victim = self.home / "victim"
        victim.mkdir()
        (victim / "SKILL.md").write_text("do not overwrite")
        (self.skills / "bugfix-fix").symlink_to(victim)
        self.install()
        self.run_script("uninstall.sh", "codex")
        self.assertEqual((user_skill / "SKILL.md").read_text(), "user skill")
        self.assertEqual((victim / "SKILL.md").read_text(), "do not overwrite")
        self.assertTrue((self.skills / "bugfix-fix").is_symlink())

    def test_project_install_keeps_other_tools_interfaces(self):
        self.run_script("install.sh", "all", "--packages", "bugfix,report-bug",
                        "--project", str(self.project), "--no-update-timer")
        for tool in (".cursor", ".claude", ".gemini", ".agents"):
            self.assertTrue((self.project / tool / "skills/bugfix").is_symlink())
        self.assertEqual((self.project / ".claude/commands/bugfix/assess.md").resolve(),
                         self.repo / "bugfix/commands/assess.md")
        self.assertTrue((self.project / ".cursor/commands/bugfix-assess.md").is_file())
        self.assertTrue((self.project / ".agents/skills/bugfix-assess/SKILL.md").is_file())
        self.assertFalse((self.project / ".claude/skills/bugfix-assess").exists())
        self.assertFalse((self.skills / "bugfix").exists())
        self.run_script("uninstall.sh", "all", "--packages", "bugfix,report-bug",
                        "--project", str(self.project))
        self.assertFalse((self.project / ".agents/skills/bugfix-assess").exists())

    def test_reinstall_removes_only_stale_owned_adapters(self):
        self.install()
        stale = self.skills / "bugfix-assess"
        (stale / "personal.txt").write_text("keep")
        unowned = self.skills / "bugfix-custom"
        unowned.mkdir()
        (unowned / "SKILL.md").write_text("user skill")
        conflict = self.skills / "bugfix-fix"
        (conflict / "workflow").unlink()
        (conflict / "workflow").mkdir()
        (conflict / "workflow/custom.txt").write_text("keep workflow")
        for phase in ("assess", "fix", "test"):
            (self.repo / f"bugfix/commands/{phase}.md").unlink()
        self.run_script("install.sh", "codex", "--packages", "bugfix", "--no-update-timer")
        self.assertFalse((stale / "SKILL.md").exists())
        self.assertFalse((stale / "workflow").is_symlink())
        self.assertFalse((stale / ".ai-workflows-phase").exists())
        self.assertEqual((stale / "personal.txt").read_text(), "keep")
        self.assertFalse((self.skills / "bugfix-test").exists())
        self.assertEqual((unowned / "SKILL.md").read_text(), "user skill")
        self.assertEqual((conflict / "workflow/custom.txt").read_text(), "keep workflow")
        self.assertTrue((conflict / "SKILL.md").is_file())
        self.assertTrue((self.skills / "bugfix-review/SKILL.md").is_file())
        self.assertTrue((self.skills / "sizing-assess/SKILL.md").is_file())

    def test_later_package_collision_creates_no_adapters(self):
        collision = self.repo / "skills/sizing-assess"
        collision.mkdir()
        (collision / "SKILL.md").write_text("package skill")
        result = self.run_script("install.sh", "codex", "--packages", "bugfix,sizing",
                                 "--no-update-timer", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicts with a package name", result.stderr)
        self.assertFalse(any(self.skills.glob("*/.ai-workflows-phase")))
        self.assertEqual((collision / "SKILL.md").read_text(), "package skill")

    def test_package_name_collision_fails_without_overwriting(self):
        collision = self.repo / "skills/bugfix-assess"
        collision.mkdir()
        (collision / "SKILL.md").write_text("package skill")
        result = self.run_script("install.sh", "codex", "--packages", "bugfix",
                                 "--no-update-timer", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicts with a package name", result.stderr)
        self.assertEqual((collision / "SKILL.md").read_text(), "package skill")


if __name__ == "__main__":
    unittest.main()
