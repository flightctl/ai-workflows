#!/usr/bin/env python3
"""Automated pre-review checks for AI skill directories.

Runs deterministic structural, frontmatter, reference, step-sequencing, and
content-quality checks before the LLM review. Outputs structured findings with
PASS/FAIL/WARN status prefixes.

Usage:
  pre-review-checks.py <skill-directory>          # single-skill (informational, exit 0)
  pre-review-checks.py --all [--repo-root PATH]   # repo-wide CI mode (exit 1 on FAIL)

Exit code:
  Single-skill mode: always 0 (informational — see CONTRIBUTING.md),
    except 1 for usage errors (missing directory)
  --all mode: 1 if any FAIL, 0 otherwise
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Structure & reference constants
# ---------------------------------------------------------------------------
KNOWN_ENTRIES = {"SKILL.md", "guidelines.md", "README.md", "GUIDE.md",
                 "skills", "commands", "templates", "scripts", "prompts"}
EXEMPT_FILES = {"SKILL.md", "guidelines.md", "README.md", "GUIDE.md"}
EXEMPT_DIRS = {"prompts"}
STEP_THRESHOLD = 10
REF_PATTERN = re.compile(
    r'(?:\.\./)*(?:skills|commands|templates|prompts|scripts)/[a-zA-Z0-9_-]+\.md')
STEP_HEADING = re.compile(r'^#{2,3} Step (\d+)([a-zA-Z])?')

# ---------------------------------------------------------------------------
# Content quality constants
# ---------------------------------------------------------------------------
WEAK_PATTERNS = [
    (re.compile(r'\b(?:you\s+)?might\s+(?:want\s+to|consider)\b', re.I), "hedging"),
    (re.compile(r'\bperhaps\b', re.I), "hedging"),
    (re.compile(r'\bmaybe\b', re.I), "hedging"),
    (re.compile(r'\bcould\s+potentially\b', re.I), "hedging"),
    (re.compile(r'\byou\s+may\s+want\s+to\b', re.I), "hedging"),
    (re.compile(r'\bit\s+is\s+(?:generally|usually|often)\s+(?:recommended|advisable|best)\b', re.I),
     "vague recommendation"),
    (re.compile(r'\btry\s+to\b', re.I), "weak directive"),
    (re.compile(r'\bif\s+possible\b', re.I), "weak qualifier"),
]

PLACEHOLDER_PATTERNS = [
    (re.compile(r'\bTODO\b'), "TODO marker"),
    (re.compile(r'\bFIXME\b'), "FIXME marker"),
    (re.compile(r'\bXXX\b'), "XXX marker"),
    (re.compile(r'\bTBD\b'), "TBD marker"),
    (re.compile(r'\[(?:insert|add|fill|replace|your)\b[^\]]*\]', re.I), "bracket placeholder"),
    (re.compile(r'\blorem\s+ipsum\b', re.I), "lorem ipsum"),
]

ABS_PATH_PATTERN = re.compile(r'/(home|Users|tmp|var)/')
ABS_PATH_EXEMPT = re.compile(r'/(home/user|Users/name|Users/me)/')
ABS_PATH_CONTEXT_EXEMPT = re.compile(r'(?:e\.g\.|example|placeholder)', re.I)

KEBAB_CASE = re.compile(r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.md$')

TAUTOLOGICAL_PATTERNS = [
    (re.compile(r'\b(?:be|make\s+sure\s+to\s+be)\s+helpful\b', re.I),
     "models are helpful by default"),
    (re.compile(r'\b(?:be|make\s+sure\s+to\s+be)\s+accurate\b', re.I),
     "models aim for accuracy by default"),
    (re.compile(r'\bthink\s+step\s+by\s+step\b', re.I),
     "modern models reason internally by default"),
    (re.compile(r'\bprovide\s+(?:a\s+)?detailed\s+(?:and\s+)?comprehensive\b', re.I),
     "models provide detail by default"),
]

CONTRADICTION_PAIRS = [
    (re.compile(r'\balways\b'), re.compile(r'\bnever\b'), "always", "never"),
    (re.compile(r'\bmust(?!\s+not)\b'), re.compile(r'\bmust\s+not\b'), "must", "must not"),
    (re.compile(r'\brequired\b'), re.compile(r'\boptional\b'), "required", "optional"),
]

NEGATIVE_PATTERN = re.compile(
    r'^\s*[-*]?\s*(?:Do\s+not|Don\'t|Never|Avoid)\s+', re.I)
POSITIVE_FOLLOW = re.compile(
    r'(?:^|[.;:—]\s*|^\s*[-*]\s*)(?:Instead|Use|Prefer|Rather)\b', re.I)

SECTION_HEADING = re.compile(r'^(#{2,3})\s+')

CONTEXT_BUDGET = {
    "SKILL.md":    (800,  1600),
    "guidelines":  (3000, 6000),
    "skills":      (3000, 6000),
    "commands":    (500,  1000),
    "templates":   (3000, 6000),
    "prompts":     (3000, 6000),
}

SECTION_TOKEN_WARN = 500
CHUNKING_GAP_WARN = 1000  # chars between headings


# ===========================================================================
# Checker — per-skill checks
# ===========================================================================
class Checker:
    def __init__(self, skill_dir: Path, ci_mode: bool = False):
        self.skill_dir = skill_dir
        self.skill_name = skill_dir.name
        self.counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        self.md_files = list(skill_dir.rglob("*.md"))
        self.ci_mode = ci_mode

    # ---- emitters ----------------------------------------------------------
    def _emit(self, level: str, msg: str):
        self.counts[level] += 1
        print(f"{level}: {msg}")

    def passed(self, msg: str): self._emit("PASS", msg)
    def warn(self, msg: str):   self._emit("WARN", msg)
    def fail(self, msg: str):   self._emit("FAIL", msg)

    # ---- helpers -----------------------------------------------------------
    def _compute_hashes(self) -> dict[str, str]:
        hashes = {}
        for f in sorted(self.md_files):
            try:
                digest = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
                rel = str(f.relative_to(self.skill_dir))
                hashes[rel] = digest
            except OSError:
                continue
        return hashes

    def _parse_frontmatter(self, path: Path) -> dict | None:
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

    def _strip_code_blocks(self, text: str) -> str:
        result = []
        in_fence = False
        for line in text.split("\n"):
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                result.append(line)
        return "\n".join(result)

    def _strip_frontmatter(self, text: str) -> str:
        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return text
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                return "\n".join(lines[i + 1:])
        return text

    def _prose_lines(self, text: str) -> list[tuple[int, str]]:
        """Return (1-based line number, line) for non-code, non-frontmatter prose."""
        lines = text.split("\n")
        numbered = []
        in_frontmatter = bool(lines and lines[0].strip() == "---")
        in_fence = False
        for i, line in enumerate(lines):
            if in_frontmatter:
                if i > 0 and line.strip() == "---":
                    in_frontmatter = False
                continue
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if line.startswith("#"):
                continue
            numbered.append((i + 1, line))
        return numbered

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _split_sections(self, text: str) -> list[tuple[str, str]]:
        """Split markdown into (heading, body) sections."""
        sections = []
        current_heading = "(top)"
        current_body = []
        for line in text.split("\n"):
            if SECTION_HEADING.match(line):
                sections.append((current_heading, "\n".join(current_body)))
                current_heading = line
                current_body = []
            else:
                current_body.append(line)
        sections.append((current_heading, "\n".join(current_body)))
        return sections

    # ---- existing checks ---------------------------------------------------
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

            changed = [f for f in current_hashes
                       if f in prev_hashes and current_hashes[f] != prev_hashes[f]]
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

        if not self.ci_mode:
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
                if self.ci_mode:
                    self.fail(f"{name} is missing (required)")
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
                if "version" not in fm:
                    self.fail("SKILL.md frontmatter missing 'version' field")
                    ok = False
                elif not re.match(r'^\d+\.\d+\.\d+$', fm["version"]):
                    self.fail(
                        f"SKILL.md version '{fm['version']}' is not valid "
                        "semver (expected X.Y.Z)")
                    ok = False
                if "description" not in fm:
                    self.fail("SKILL.md frontmatter missing 'description' field")
                    ok = False
                if ok:
                    self.passed("SKILL.md has valid frontmatter (name, version, description)")

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
                    self.fail(
                        f"{rel} name '{name_val}' does not use colon notation "
                        f"'{self.skill_name}:<command>'")
                else:
                    self.passed(f"{rel} has valid frontmatter")

        print()

    def check_references(self):
        print("--- References ---")

        file_contents = {}
        for f in self.md_files:
            try:
                file_contents[f] = f.read_text()
            except OSError:
                continue

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
                if target_rel in refs or any(
                        r.endswith(f"/{target_name}") or r == target_name
                        for r in refs):
                    referenced = True
                    break
            if not referenced:
                rel = f.relative_to(self.skill_dir)
                self.fail(f"Orphaned file: {rel} (not referenced by any other file)")
                orphan_found = True

        if not orphan_found:
            self.passed("No orphaned files found")

        dangle_found = False
        seen_dangles = set()

        for f, content in file_contents.items():
            if any(part in EXEMPT_DIRS
                   for part in f.relative_to(self.skill_dir).parts[:-1]):
                continue
            stripped = self._strip_code_blocks(content)
            refs = set(REF_PATTERN.findall(stripped))
            for ref in sorted(refs):
                ref_path = Path(ref)
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
                        self.fail(
                            f"Dangling reference in {f_rel}: {ref} "
                            "(file does not exist)")
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

            unique = sorted(set(steps))
            if len(steps) != len(unique):
                dupes = sorted({n for n in steps if steps.count(n) > 1})
                self.fail(
                    f"{rel} has duplicate step number(s): "
                    f"{', '.join(map(str, dupes))}")

            first, last = unique[0], unique[-1]
            expected = set(range(first, last + 1))
            missing = sorted(expected - set(unique))
            if missing:
                self.fail(
                    f"{rel} has gap(s) in step numbering: missing Step "
                    f"{', '.join(map(str, missing))}")
            else:
                self.passed(f"{rel} steps sequential ({first}-{last})")

            if len(steps) > STEP_THRESHOLD:
                self.warn(f"{rel} has {len(steps)} steps (threshold: {STEP_THRESHOLD})")

        print()

    # ---- content quality checks --------------------------------------------
    def check_content(self):
        print("--- Content Quality ---")
        self._check_weak_language()
        self._check_placeholder_text()
        self._check_absolute_paths()
        self._check_context_budget()
        self._check_kebab_case_commands()
        self._check_tautological_instructions()
        self._check_contradictions()
        self._check_section_length()
        self._check_cognitive_chunking()
        self._check_negative_only()
        print()

    def _check_weak_language(self):
        found = False
        for f in self.md_files:
            if f.name == "README.md":
                continue
            if any(part in EXEMPT_DIRS
                   for part in f.relative_to(self.skill_dir).parts[:-1]):
                continue
            try:
                text = f.read_text()
            except OSError:
                continue
            for lineno, line in self._prose_lines(text):
                for pattern, category in WEAK_PATTERNS:
                    if pattern.search(line):
                        rel = f.relative_to(self.skill_dir)
                        self.warn(f"{rel}:{lineno} {category}: {line.strip()[:80]}")
                        found = True
                        break
        if not found:
            self.passed("No weak/hedging language detected")

    def _check_placeholder_text(self):
        found = False
        for f in self.md_files:
            try:
                text = f.read_text()
            except OSError:
                continue
            for lineno, line in self._prose_lines(text):
                for pattern, category in PLACEHOLDER_PATTERNS:
                    if category == "TBD marker":
                        # Skip lines that discuss TBD as a concept (e.g., review.md
                        # listing "TODO/FIXME/TBD" as things the checker detects)
                        if re.search(r'TBD marker|To be determined', line, re.I):
                            continue
                    if pattern.search(line):
                        rel = f.relative_to(self.skill_dir)
                        self.warn(
                            f"{rel}:{lineno} {category}: {line.strip()[:80]}")
                        found = True
                        break
        if not found:
            self.passed("No placeholder text detected")

    def _check_absolute_paths(self):
        found = False
        for f in self.md_files:
            try:
                text = f.read_text()
            except OSError:
                continue
            in_fence = False
            for i, line in enumerate(text.split("\n"), 1):
                if line.startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                if ABS_PATH_PATTERN.search(line):
                    if ABS_PATH_EXEMPT.search(line):
                        continue
                    if ABS_PATH_CONTEXT_EXEMPT.search(line):
                        continue
                    rel = f.relative_to(self.skill_dir)
                    self.fail(f"{rel}:{i} absolute path: {line.strip()[:80]}")
                    found = True
        if not found:
            self.passed("No absolute paths found")

    def _check_context_budget(self):
        found = False
        for f in self.md_files:
            try:
                text = f.read_text()
            except OSError:
                continue
            tokens = self._estimate_tokens(text)
            rel = str(f.relative_to(self.skill_dir))

            if f.name == "SKILL.md":
                warn_t, fail_t = CONTEXT_BUDGET["SKILL.md"]
            elif f.name == "guidelines.md":
                warn_t, fail_t = CONTEXT_BUDGET["guidelines"]
            else:
                parent = f.parent.name
                if parent in CONTEXT_BUDGET:
                    warn_t, fail_t = CONTEXT_BUDGET[parent]
                else:
                    continue

            if tokens >= fail_t:
                self.fail(f"{rel} ~{tokens} tokens (limit: {fail_t})")
                found = True
            elif tokens >= warn_t:
                self.warn(f"{rel} ~{tokens} tokens (suggested: <{warn_t})")
                found = True
        if not found:
            self.passed("All files within context budget")

    def _check_kebab_case_commands(self):
        cmds = self.skill_dir / "commands"
        if not cmds.is_dir():
            return
        found = False
        for cmd in sorted(cmds.glob("*.md")):
            if not KEBAB_CASE.match(cmd.name):
                self.warn(f"commands/{cmd.name} filename is not kebab-case")
                found = True
            fm = self._parse_frontmatter(cmd)
            if fm and "name" in fm:
                name_val = fm["name"].strip('"')
                parts = name_val.split(":", 1)
                if len(parts) == 2:
                    cmd_part = parts[1]
                    if not re.match(r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$', cmd_part):
                        self.warn(
                            f"commands/{cmd.name} command name '{cmd_part}' "
                            "is not kebab-case")
                        found = True
        if not found:
            self.passed("All command names are kebab-case")

    def _check_tautological_instructions(self):
        found = False
        for f in self.md_files:
            if f.name == "README.md":
                continue
            try:
                text = f.read_text()
            except OSError:
                continue
            for lineno, line in self._prose_lines(text):
                for pattern, reason in TAUTOLOGICAL_PATTERNS:
                    if pattern.search(line):
                        rel = f.relative_to(self.skill_dir)
                        self.warn(
                            f"{rel}:{lineno} tautological ({reason}): "
                            f"{line.strip()[:80]}")
                        found = True
                        break
        if not found:
            self.passed("No tautological instructions detected")

    def _check_contradictions(self):
        found = False
        for f in self.md_files:
            if f.name == "README.md":
                continue
            try:
                text = f.read_text()
            except OSError:
                continue
            stripped = self._strip_frontmatter(text)
            stripped = self._strip_code_blocks(stripped)
            sections = self._split_sections(stripped)
            for heading, body in sections:
                body_lower = body.lower()
                for pat_a, pat_b, label_a, label_b in CONTRADICTION_PAIRS:
                    if pat_a.search(body_lower) and pat_b.search(body_lower):
                        rel = f.relative_to(self.skill_dir)
                        self.warn(
                            f"{rel} section '{heading.lstrip('#').strip()[:40]}' "
                            f"contains both '{label_a}' and '{label_b}'")
                        found = True
        if not found:
            self.passed("No contradictions detected")

    def _check_section_length(self):
        found = False
        for f in self.md_files:
            if f.name == "README.md":
                continue
            try:
                text = f.read_text()
            except OSError:
                continue
            stripped = self._strip_frontmatter(text)
            stripped = self._strip_code_blocks(stripped)
            sections = self._split_sections(stripped)
            for heading, body in sections:
                tokens = self._estimate_tokens(body)
                if tokens > SECTION_TOKEN_WARN:
                    rel = f.relative_to(self.skill_dir)
                    self.warn(
                        f"{rel} section '{heading.lstrip('#').strip()[:40]}' "
                        f"~{tokens} tokens (suggested: <{SECTION_TOKEN_WARN})")
                    found = True
        if not found:
            self.passed("All sections within length budget")

    def _check_cognitive_chunking(self):
        found = False
        for f in self.md_files:
            try:
                text = f.read_text()
            except OSError:
                continue
            stripped = self._strip_frontmatter(text)
            stripped = self._strip_code_blocks(stripped)
            tokens = self._estimate_tokens(stripped)
            if tokens < 200:
                continue
            heading_count = sum(
                1 for line in stripped.split("\n")
                if SECTION_HEADING.match(line))
            if heading_count == 0:
                rel = f.relative_to(self.skill_dir)
                self.warn(f"{rel} has ~{tokens} tokens with no section headings")
                found = True
                continue
            chars_since_heading = 0
            for line in stripped.split("\n"):
                if SECTION_HEADING.match(line):
                    chars_since_heading = 0
                else:
                    chars_since_heading += len(line) + 1
                    if chars_since_heading > CHUNKING_GAP_WARN:
                        rel = f.relative_to(self.skill_dir)
                        self.warn(
                            f"{rel} has >{CHUNKING_GAP_WARN} chars between "
                            "headings — consider splitting")
                        found = True
                        break
        if not found:
            self.passed("Content is well-chunked with headings")

    def _check_negative_only(self):
        found = False
        for f in self.md_files:
            if f.name == "README.md":
                continue
            try:
                text = f.read_text()
            except OSError:
                continue
            prose = self._prose_lines(text)
            for idx, (lineno, line) in enumerate(prose):
                if not NEGATIVE_PATTERN.match(line):
                    continue
                has_positive = False
                if POSITIVE_FOLLOW.search(line):
                    has_positive = True
                elif idx + 1 < len(prose):
                    _, next_line = prose[idx + 1]
                    if POSITIVE_FOLLOW.search(next_line):
                        has_positive = True
                if not has_positive:
                    rel = f.relative_to(self.skill_dir)
                    self.warn(
                        f"{rel}:{lineno} negative-only prohibition: "
                        f"{line.strip()[:80]}")
                    found = True
        if not found:
            self.passed("No negative-only prohibitions detected")

    # ---- run ---------------------------------------------------------------
    def run(self):
        print(f"=== Pre-Review Automated Checks: {self.skill_name} ===")
        print()
        if not self.ci_mode:
            self.check_changes()
        self.check_structure()
        self.check_frontmatter()
        if not self.ci_mode:
            self.check_references()
            self.check_steps()
            self.check_content()
        total = sum(self.counts.values())
        print("--- Summary ---")
        print(
            f"Checks: {total} | PASS: {self.counts['PASS']} | "
            f"WARN: {self.counts['WARN']} | FAIL: {self.counts['FAIL']}")


# ===========================================================================
# RepoChecker — repo-wide checks (--all mode)
# ===========================================================================
class RepoChecker:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.total_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}

    def _emit(self, level: str, msg: str):
        self.total_counts[level] += 1
        print(f"{level}: {msg}")

    def _pass(self, msg: str): self._emit("PASS", msg)
    def _warn(self, msg: str): self._emit("WARN", msg)
    def _fail(self, msg: str): self._emit("FAIL", msg)

    def discover_skills(self) -> list[Path]:
        skills = []
        for skill_md in sorted(self.repo_root.glob("*/SKILL.md")):
            skills.append(skill_md.parent)
        return skills

    def check_agents_md(self, skills: list[Path]):
        print("--- AGENTS.md Cross-Checks ---")
        agents_path = self.repo_root / "AGENTS.md"
        if not agents_path.is_file():
            self._fail("AGENTS.md not found at repo root")
            print()
            return

        text = agents_path.read_text()

        tree_text = ""
        in_tree = False
        for line in text.split("\n"):
            if line.strip().startswith("```text"):
                in_tree = True
                continue
            if line.strip() == "```" and in_tree:
                in_tree = False
                continue
            if in_tree:
                tree_text += line + "\n"

        for skill_dir in skills:
            name = skill_dir.name
            if f"- **{name}**" in text:
                self._pass(f"AGENTS.md: workflow list has '{name}'")
            else:
                self._fail(f"AGENTS.md: workflow list missing entry for '{name}'")

            if f"{name}/" in tree_text:
                self._pass(f"AGENTS.md: tree has '{name}/'")
            else:
                self._fail(f"AGENTS.md: file organization tree missing '{name}/'")
        print()

    def check_readme_md(self, skills: list[Path]):
        print("--- README.md Cross-Checks ---")
        readme_path = self.repo_root / "README.md"
        if not readme_path.is_file():
            self._fail("README.md not found at repo root")
            print()
            return

        text = readme_path.read_text()

        for skill_dir in skills:
            name = skill_dir.name
            name_title = name.replace("-", " ")
            if re.search(
                    rf'\*\*{re.escape(name)}\*\*|{re.escape(name_title)}',
                    text, re.I):
                self._pass(f"README.md: has entry for '{name}'")
            else:
                self._fail(f"README.md: missing entry for workflow '{name}'")
        print()

    def check_readme_artifacts(self, skills: list[Path]):
        print("--- Workflow README Artifact Docs ---")
        for skill_dir in skills:
            readme = skill_dir / "README.md"
            if not readme.is_file():
                continue
            text = readme.read_text()
            if ".artifacts/" in text:
                self._pass(f"{skill_dir.name}/README.md references .artifacts/")
            else:
                self._fail(
                    f"{skill_dir.name}/README.md: missing artifact path "
                    "documentation (.artifacts/ reference)")
        print()

    def check_shared_frontmatter(self):
        print("--- Shared File Frontmatter ---")
        shared_dir = self.repo_root / "_shared"
        if not shared_dir.is_dir():
            self._warn("No _shared/ directory found")
            print()
            return
        for md_file in sorted(shared_dir.rglob("*.md")):
            rel = str(md_file.relative_to(self.repo_root))
            text = md_file.read_text()
            lines = text.split("\n")
            if not lines or lines[0].strip() != "---":
                self._fail(f"{rel}: missing YAML frontmatter")
                continue
            fields = {}
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if ":" in line:
                    key = line.split(":", 1)[0].strip()
                    val = line.split(":", 1)[1].strip()
                    fields[key] = val
            ok = True
            if "name" not in fields:
                self._fail(f"{rel}: frontmatter missing 'name' field")
                ok = False
            if "version" not in fields:
                self._fail(f"{rel}: frontmatter missing 'version' field")
                ok = False
            elif not re.match(r'^\d+\.\d+\.\d+$', fields["version"]):
                self._fail(
                    f"{rel}: version '{fields['version']}' is not valid semver")
                ok = False
            if ok:
                self._pass(f"{rel}: valid frontmatter (name, version)")
        print()

    def run(self) -> int:
        skills = self.discover_skills()
        if not skills:
            print("FAIL: No workflows discovered (no */SKILL.md found)")
            return 1

        print(f"Discovered workflows: {', '.join(s.name for s in skills)}")
        print()

        for skill_dir in skills:
            checker = Checker(skill_dir, ci_mode=True)
            checker.run()
            for level, count in checker.counts.items():
                self.total_counts[level] += count
            print()

        self.check_shared_frontmatter()
        self.check_agents_md(skills)
        self.check_readme_md(skills)
        self.check_readme_artifacts(skills)

        print("=" * 50)
        print(
            f"TOTAL: PASS={self.total_counts['PASS']} "
            f"WARN={self.total_counts['WARN']} "
            f"FAIL={self.total_counts['FAIL']}")
        return 1 if self.total_counts["FAIL"] > 0 else 0


# ===========================================================================
# CLI
# ===========================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="Automated pre-review checks for AI skill directories.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "skill_dir", nargs="?", type=Path,
        help="Single skill directory to check")
    group.add_argument(
        "--all", action="store_true",
        help="Repo-wide mode: check all skills and cross-references (CI)")
    parser.add_argument(
        "--repo-root", type=Path, default=Path("."),
        help="Repository root (default: current directory)")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.all:
        rc = RepoChecker(args.repo_root.resolve()).run()
        sys.exit(rc)
    else:
        skill_dir = args.skill_dir.resolve()
        if not skill_dir.is_dir():
            print(f"FAIL: Directory does not exist: {args.skill_dir}")
            sys.exit(1)
        Checker(skill_dir).run()


if __name__ == "__main__":
    main()
