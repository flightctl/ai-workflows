#!/usr/bin/env python3
"""Tests for pre-review-checks.py content-quality checks and helpers."""

import importlib
import textwrap
from pathlib import Path

import pytest

_mod = importlib.import_module("pre-review-checks")
Checker = _mod.Checker
RepoChecker = _mod.RepoChecker


@pytest.fixture
def skill_dir(tmp_path):
    """Create a minimal valid skill directory."""
    d = tmp_path / "test-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: test-skill
        description: A test skill
        ---
        # Test Skill
    """))
    skills = d / "skills"
    skills.mkdir()
    (skills / "do-thing.md").write_text(textwrap.dedent("""\
        ---
        name: do-thing
        description: Does a thing
        ---
        # Do Thing

        ## Step 1: First
        Do something.

        ## Step 2: Second
        Do another thing.
    """))
    (d / "guidelines.md").write_text("# Guidelines\n\nBe good.\n")
    (d / "README.md").write_text("# Test Skill\n\nA test.\n\n.artifacts/\n")
    return d


def make_checker(skill_dir, ci_mode=False):
    return Checker(skill_dir, ci_mode=ci_mode)


# ---------------------------------------------------------------------------
# _prose_lines
# ---------------------------------------------------------------------------
class TestProseLines:
    def test_strips_frontmatter(self, skill_dir):
        text = "---\nname: foo\n---\nHello world\n"
        c = make_checker(skill_dir)
        lines = c._prose_lines(text)
        assert any("Hello world" in line for _, line in lines)
        assert not any("name:" in line for _, line in lines)

    def test_strips_code_blocks(self, skill_dir):
        text = "Prose before\n```python\ncode_line()\n```\nProse after\n"
        c = make_checker(skill_dir)
        lines = c._prose_lines(text)
        texts = [line for _, line in lines]
        assert "Prose before" in texts
        assert "Prose after" in texts
        assert "code_line()" not in texts

    def test_skips_headings(self, skill_dir):
        text = "# Heading\nProse line\n## Sub\nMore prose\n"
        c = make_checker(skill_dir)
        lines = c._prose_lines(text)
        texts = [line for _, line in lines]
        assert "Prose line" in texts
        assert "More prose" in texts
        assert not any(line.startswith("#") for line in texts)

    def test_line_numbers_correct_with_frontmatter_and_code(self, skill_dir):
        text = textwrap.dedent("""\
            ---
            name: test
            ---
            # Heading
            Line five
            ```
            code on line seven
            ```
            Line nine
        """)
        c = make_checker(skill_dir)
        lines = c._prose_lines(text)
        line_map = {line.strip(): lineno for lineno, line in lines if line.strip()}
        assert line_map["Line five"] == 5
        assert line_map["Line nine"] == 9

    def test_handles_no_frontmatter(self, skill_dir):
        text = "Just prose\nMore prose"
        c = make_checker(skill_dir)
        lines = c._prose_lines(text)
        assert len(lines) == 2
        assert lines[0] == (1, "Just prose")
        assert lines[1] == (2, "More prose")


# ---------------------------------------------------------------------------
# _check_placeholder_text — TBD exemption
# ---------------------------------------------------------------------------
class TestPlaceholderText:
    def test_flags_todo(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nThis is a TODO item\n")
        c = make_checker(skill_dir)
        c._check_placeholder_text()
        assert c.counts["WARN"] > 0

    def test_skips_tbd_in_instructional_context(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nDetects TBD marker placeholders\n")
        c = make_checker(skill_dir)
        c._check_placeholder_text()
        assert c.counts["WARN"] == 0

    def test_flags_tbd_in_normal_prose(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nThis feature is TBD\n")
        c = make_checker(skill_dir)
        c._check_placeholder_text()
        assert c.counts["WARN"] > 0

    def test_flags_bracket_placeholder(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nSee [insert your name here]\n")
        c = make_checker(skill_dir)
        c._check_placeholder_text()
        assert c.counts["WARN"] > 0


# ---------------------------------------------------------------------------
# _check_contradictions — must / must not
# ---------------------------------------------------------------------------
class TestContradictions:
    def test_must_and_must_not_in_same_section(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            ## Rules
            You must validate input.
            You must not skip validation.
        """))
        c = make_checker(skill_dir)
        c._check_contradictions()
        assert c.counts["WARN"] > 0

    def test_must_not_alone_does_not_trigger(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            ## Rules
            You must not skip validation.
            You must not ignore errors.
        """))
        c = make_checker(skill_dir)
        c._check_contradictions()
        # "must not" alone should NOT trigger — the "must" pattern
        # uses negative lookahead to exclude "must not"
        assert c.counts["WARN"] == 0

    def test_always_never_in_same_section(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            ## Rules
            Always cite files. Never fabricate.
        """))
        c = make_checker(skill_dir)
        c._check_contradictions()
        assert c.counts["WARN"] > 0

    def test_always_never_in_different_sections(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            ## Section A
            Always cite files.
            ## Section B
            Never fabricate.
        """))
        c = make_checker(skill_dir)
        c._check_contradictions()
        assert c.counts["WARN"] == 0


# ---------------------------------------------------------------------------
# _check_weak_language
# ---------------------------------------------------------------------------
class TestWeakLanguage:
    def test_flags_hedging(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nYou might want to consider this.\n")
        c = make_checker(skill_dir)
        c._check_weak_language()
        assert c.counts["WARN"] > 0

    def test_skips_readme(self, skill_dir):
        (skill_dir / "README.md").write_text(
            "# README\nYou might want to read this perhaps.\n")
        c = make_checker(skill_dir)
        c._check_weak_language()
        assert c.counts["WARN"] == 0

    def test_skips_code_blocks(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            ```
            perhaps this is code
            ```
        """))
        c = make_checker(skill_dir)
        c._check_weak_language()
        assert c.counts["WARN"] == 0


# ---------------------------------------------------------------------------
# _check_absolute_paths
# ---------------------------------------------------------------------------
class TestAbsolutePaths:
    def test_flags_absolute_path_in_prose(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nSee /home/testuser/config\n")
        c = make_checker(skill_dir)
        c._check_absolute_paths()
        assert c.counts["FAIL"] > 0

    def test_skips_code_blocks(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            ```bash
            cat /home/testuser/file
            ```
        """))
        c = make_checker(skill_dir)
        c._check_absolute_paths()
        assert c.counts["FAIL"] == 0

    def test_skips_exempt_paths(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\nExample: /home/user/config\n")
        c = make_checker(skill_dir)
        c._check_absolute_paths()
        assert c.counts["FAIL"] == 0


# ---------------------------------------------------------------------------
# _check_context_budget
# ---------------------------------------------------------------------------
class TestContextBudget:
    def test_warns_on_large_skill_md(self, skill_dir):
        (skill_dir / "SKILL.md").write_text("x " * 2000)
        c = make_checker(skill_dir)
        c._check_context_budget()
        assert c.counts["WARN"] > 0 or c.counts["FAIL"] > 0

    def test_passes_small_files(self, skill_dir):
        c = make_checker(skill_dir)
        c._check_context_budget()
        assert c.counts["WARN"] == 0 and c.counts["FAIL"] == 0


# ---------------------------------------------------------------------------
# _check_negative_only
# ---------------------------------------------------------------------------
class TestNegativeOnly:
    def test_flags_prohibition_without_alternative(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\n- Do not skip validation\n")
        c = make_checker(skill_dir)
        c._check_negative_only()
        assert c.counts["WARN"] > 0

    def test_passes_prohibition_with_alternative(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(
            "---\nname: x\n---\n# X\n- Do not skip validation. Instead validate early.\n")
        c = make_checker(skill_dir)
        c._check_negative_only()
        assert c.counts["WARN"] == 0

    def test_passes_prohibition_with_next_line_alternative(self, skill_dir):
        (skill_dir / "skills" / "do-thing.md").write_text(textwrap.dedent("""\
            ---
            name: x
            ---
            # X
            - Do not use eval
            - Instead use safe_eval
        """))
        c = make_checker(skill_dir)
        c._check_negative_only()
        assert c.counts["WARN"] == 0


# ---------------------------------------------------------------------------
# _check_kebab_case_commands
# ---------------------------------------------------------------------------
class TestKebabCase:
    def test_passes_kebab_case(self, skill_dir):
        cmds = skill_dir / "commands"
        cmds.mkdir()
        (cmds / "do-thing.md").write_text(
            "---\nname: test-skill:do-thing\n---\n# Do Thing\n")
        c = make_checker(skill_dir)
        c._check_kebab_case_commands()
        assert c.counts["WARN"] == 0

    def test_flags_non_kebab_filename(self, skill_dir):
        cmds = skill_dir / "commands"
        cmds.mkdir()
        (cmds / "DoThing.md").write_text(
            "---\nname: test-skill:do-thing\n---\n# Do Thing\n")
        c = make_checker(skill_dir)
        c._check_kebab_case_commands()
        assert c.counts["WARN"] > 0


# ---------------------------------------------------------------------------
# RepoChecker
# ---------------------------------------------------------------------------
class TestRepoChecker:
    def test_discovers_skills(self, skill_dir):
        rc = RepoChecker(skill_dir.parent)
        skills = rc.discover_skills()
        assert len(skills) == 1
        assert skills[0].name == "test-skill"

    def test_returns_1_on_fail(self, skill_dir):
        agents = skill_dir.parent / "AGENTS.md"
        agents.write_text("# Agents\n")
        readme = skill_dir.parent / "README.md"
        readme.write_text("# Project\n")
        rc = RepoChecker(skill_dir.parent)
        result = rc.run()
        assert result == 1
