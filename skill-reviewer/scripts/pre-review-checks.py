#!/usr/bin/env python3
"""Automated pre-review checks for AI skill directories.

Runs deterministic structural, frontmatter, reference, and step-sequencing
checks before the LLM review. Outputs structured findings with PASS/FAIL/WARN
status prefixes.

Usage: pre-review-checks.py <skill-directory-path>
Exit code: always 0 — informational only (see CONTRIBUTING.md § Scripts for exit-code convention)
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

KNOWN_ENTRIES = {"SKILL.md", "guidelines.md", "README.md", "GUIDE.md",
                 "skills", "commands", "templates", "scripts", "prompts"}
EXEMPT_FILES = {"SKILL.md", "guidelines.md", "README.md", "GUIDE.md"}
EXEMPT_DIRS = {"prompts"}  # contain example content, not real references
STEP_THRESHOLD = 10
REF_PATTERN = re.compile(r'(?:\.\./)*(?:skills|commands|templates|prompts|scripts)/[a-zA-Z0-9_-]+\.md')
STEP_HEADING = re.compile(r'^#{2,3} Step (\d+)([a-zA-Z])?')


class Checker:
    def __init__(self, skill_dir: Path):
        self.skill_dir = skill_dir
        self.skill_name = skill_dir.name
        self.counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        self.md_files = list(skill_dir.rglob("*.md"))

    def _emit(self, level: str, msg: str):
        self.counts[level] += 1
        print(f"{level}: {msg}")

    def passed(self, msg: str): self._emit("PASS", msg)
    def warn(self, msg: str): self._emit("WARN", msg)
    def fail(self, msg: str): self._emit("FAIL", msg)

    def _compute_hashes(self) -> dict[str, str]:
        """Compute SHA-256 hashes for all .md files in the skill directory."""
        hashes = {}
        for f in sorted(self.md_files):
            try:
                digest = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
                rel = str(f.relative_to(self.skill_dir))
                hashes[rel] = digest
            except OSError:
                continue
        return hashes

    def check_changes(self):
        print("--- Changes Since Last Review ---")

        hashes_file = Path(f".artifacts/skill-reviewer/{self.skill_name}/file-hashes.json")
        current_hashes = self._compute_hashes()

        if hashes_file.is_file():
            try:
                prev = json.loads(hashes_file.read_text())
                prev_hashes = prev.get("files", {})
                prev_time = prev.get("timestamp", "unknown")
            except (json.JSONDecodeError, OSError):
                prev_hashes = {}
                prev_time = "unknown"

            print(f"INFO: Previous review: {prev_time}")

            changed = [f for f in current_hashes if f in prev_hashes and current_hashes[f] != prev_hashes[f]]
            added = [f for f in current_hashes if f not in prev_hashes]
            removed = [f for f in prev_hashes if f not in current_hashes]
            unchanged = len(current_hashes) - len(changed) - len(added)

            for f in sorted(changed):
                self.warn(f"Changed: {f}")
            for f in sorted(added):
                print(f"INFO: New file: {f}")
            for f in sorted(removed):
                print(f"INFO: Removed: {f}")
            if unchanged > 0:
                print(f"INFO: Unchanged: {unchanged} file(s)")
            if not changed and not added and not removed:
                print("INFO: No changes detected since last review")
        else:
            print("INFO: No previous review found — full review")

        # Write current hashes for next comparison
        hashes_file.parent.mkdir(parents=True, exist_ok=True)
        hashes_file.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "files": current_hashes,
        }, indent=2) + "\n")

        print()

    def check_structure(self):
        print("--- Structure ---")
        d = self.skill_dir

        if (d / "SKILL.md").is_file():
            self.passed("SKILL.md exists")
        else:
            self.fail("SKILL.md is missing (required)")

        skills_dir = d / "skills"
        if skills_dir.is_dir():
            count = len(list(skills_dir.glob("*.md")))
            if count > 0:
                self.passed(f"skills/ directory with {count} skill file(s)")
            else:
                self.fail("skills/ directory exists but contains no .md files")
        else:
            self.fail("skills/ directory is missing (required)")

        for name in ("guidelines.md", "README.md"):
            if (d / name).is_file():
                self.passed(f"{name} present")
            else:
                self.warn(f"No {name} found (optional but recommended)")

        cmds = d / "commands"
        if cmds.is_dir():
            count = len(list(cmds.glob("*.md")))
            self.passed(f"commands/ directory with {count} command file(s)")
        else:
            self.warn("No commands/ directory found")

        tmpls = d / "templates"
        if tmpls.is_dir():
            count = len(list(tmpls.glob("*.md")))
            self.passed(f"templates/ directory with {count} template file(s)")

        for entry in sorted(d.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.name not in KNOWN_ENTRIES:
                self.warn(f"Unexpected entry: {entry.name}")

        print()

    def _parse_frontmatter(self, path: Path) -> dict | None:
        """Extract YAML frontmatter fields as a dict, or None if missing."""
        try:
            text = path.read_text()
        except OSError:
            return None
        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return None
        fields = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key = line.split(":", 1)[0].strip()
                val = line.split(":", 1)[1].strip()
                fields[key] = val
        return fields

    def check_frontmatter(self):
        print("--- Frontmatter ---")
        d = self.skill_dir

        skill_md = d / "SKILL.md"
        if skill_md.is_file():
            fm = self._parse_frontmatter(skill_md)
            if fm is None:
                self.fail("SKILL.md missing YAML frontmatter (no opening ---)")
            else:
                ok = True
                if "name" not in fm:
                    self.fail("SKILL.md frontmatter missing 'name' field")
                    ok = False
                if "description" not in fm:
                    self.fail("SKILL.md frontmatter missing 'description' field")
                    ok = False
                if ok:
                    self.passed("SKILL.md has valid frontmatter (name, description)")

        cmds = d / "commands"
        if cmds.is_dir():
            for cmd in sorted(cmds.glob("*.md")):
                rel = f"commands/{cmd.name}"
                fm = self._parse_frontmatter(cmd)
                if fm is None:
                    self.fail(f"{rel} missing YAML frontmatter")
                    continue
                if "name" not in fm:
                    self.fail(f"{rel} frontmatter missing 'name' field")
                    continue
                name_val = fm["name"].strip('"')
                if not name_val.startswith(f"{self.skill_name}:"):
                    self.fail(f"{rel} name '{name_val}' does not use colon notation '{self.skill_name}:<command>'")
                else:
                    self.passed(f"{rel} has valid frontmatter")

        print()

    def _strip_code_blocks(self, text: str) -> str:
        """Remove content inside fenced code blocks."""
        result = []
        in_fence = False
        for line in text.split("\n"):
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                result.append(line)
        return "\n".join(result)

    def check_references(self):
        print("--- References ---")

        file_contents = {}
        for f in self.md_files:
            try:
                file_contents[f] = f.read_text()
            except OSError:
                continue

        # Orphaned files
        orphan_found = False
        for f in self.md_files:
            if f.name in EXEMPT_FILES:
                continue
            target_rel = str(f.relative_to(self.skill_dir)).replace("\\", "/")
            target_name = f.name
            referenced = False
            for other, content in file_contents.items():
                if other == f:
                    continue
                stripped = self._strip_code_blocks(content)
                refs = set(REF_PATTERN.findall(stripped))
                if target_rel in refs or any(r.endswith(f"/{target_name}") or r == target_name for r in refs):
                    referenced = True
                    break
            if not referenced:
                rel = f.relative_to(self.skill_dir)
                self.fail(f"Orphaned file: {rel} (not referenced by any other file)")
                orphan_found = True

        if not orphan_found:
            self.passed("No orphaned files found")

        # Dangling references (skip files in exempt dirs — they contain example content)
        dangle_found = False
        seen_dangles = set()

        for f, content in file_contents.items():
            if any(part in EXEMPT_DIRS for part in f.relative_to(self.skill_dir).parts[:-1]):
                continue
            stripped = self._strip_code_blocks(content)
            refs = set(REF_PATTERN.findall(stripped))
            for ref in sorted(refs):
                ref_path = Path(ref)
                # Try relative to the file's directory, then to the skill root
                candidates = [f.parent / ref_path, self.skill_dir / ref_path]
                if ref.startswith("../"):
                    resolved = (f.parent / ref_path).resolve()
                    try:
                        resolved.relative_to(self.skill_dir.resolve())
                        candidates = [resolved]
                    except ValueError:
                        candidates = []

                if not any(c.is_file() for c in candidates):
                    f_rel = f.relative_to(self.skill_dir)
                    key = (str(f_rel), ref)
                    if key not in seen_dangles:
                        seen_dangles.add(key)
                        self.fail(f"Dangling reference in {f_rel}: {ref} (file does not exist)")
                        dangle_found = True

        if not dangle_found:
            self.passed("No dangling references found")

        print()

    def check_steps(self):
        print("--- Steps ---")

        skills_dir = self.skill_dir / "skills"
        if not skills_dir.is_dir():
            self.warn("No skills/ directory — skipping step checks")
            print()
            return

        for skill_file in sorted(skills_dir.glob("*.md")):
            rel = f"skills/{skill_file.name}"
            try:
                text = skill_file.read_text()
            except OSError:
                continue

            steps = []
            substeps = []
            for line in text.split("\n"):
                m = STEP_HEADING.match(line)
                if not m:
                    continue
                num = int(m.group(1))
                if m.group(2):
                    label = line.lstrip("#").strip().split(":")[0].strip()
                    substeps.append(label)
                else:
                    steps.append(num)

            if substeps:
                self.warn(f"{rel} uses sub-step numbering: {', '.join(substeps)}")

            if not steps:
                continue

            # Duplicates
            unique = sorted(set(steps))
            if len(steps) != len(unique):
                dupes = sorted({n for n in steps if steps.count(n) > 1})
                self.fail(f"{rel} has duplicate step number(s): {', '.join(map(str, dupes))}")

            # Gaps
            first, last = unique[0], unique[-1]
            expected = set(range(first, last + 1))
            missing = sorted(expected - set(unique))
            if missing:
                self.fail(f"{rel} has gap(s) in step numbering: missing Step {', '.join(map(str, missing))}")
            else:
                self.passed(f"{rel} steps sequential ({first}-{last})")

            # Threshold
            if len(steps) > STEP_THRESHOLD:
                self.warn(f"{rel} has {len(steps)} steps (threshold: {STEP_THRESHOLD})")

        print()

    def run(self):
        print(f"=== Pre-Review Automated Checks: {self.skill_name} ===")
        print()
        self.check_changes()
        self.check_structure()
        self.check_frontmatter()
        self.check_references()
        self.check_steps()
        total = sum(self.counts.values())
        print("--- Summary ---")
        print(f"Checks: {total} | PASS: {self.counts['PASS']} | WARN: {self.counts['WARN']} | FAIL: {self.counts['FAIL']}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <skill-directory-path>")
        return

    skill_dir = Path(sys.argv[1]).resolve()
    if not skill_dir.is_dir():
        print(f"FAIL: Directory does not exist: {sys.argv[1]}")
        return

    Checker(skill_dir).run()


if __name__ == "__main__":
    main()
