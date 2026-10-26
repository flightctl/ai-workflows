#!/usr/bin/env python3
"""Deterministic sync operations for the design workflow.

Provides reusable subcommands for the /sync phase of the design
workflow.  Each subcommand handles one discrete, deterministic
operation -- the calling skill file retains ownership of AI-dependent
work (Jira API calls, user approval, error handling/retry decisions).

Subcommands:
  detect-changes   Compare artifact files against sync manifest and
                   produce a compact JSON change plan.
  resolve-refs     Replace local identifiers (Story 1.01, Epic 1) in
                   text with Jira keys from the sync manifest.
  render-description  Render a Jira-ready description from an artifact
                      file with resolved cross-references.
  update-manifest  Record a single successful Jira operation in the
                   manifest (atomic per-item checkpoint).
  compute-hash     Print the SHA-256 hex digest of a file's content.
  migrate-manifest Upgrade a v1 manifest to v2 schema in place.

Environment variables:
  None required.  All inputs come from command-line arguments and local
  files.  This script never contacts Jira or any external service.

Exit codes:
  0 -- success
  1 -- runtime error (missing file, invalid manifest, I/O failure)
  2 -- invalid arguments (from argparse)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERROR = 1
# argparse uses exit code 2 for usage errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    """Print an informational message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def fail(msg: str, code: int = EXIT_ERROR) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def compute_file_hash(filepath: str | Path) -> str:
    """Return the SHA-256 hex digest of a file's raw content."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_frontmatter(filepath: str | Path) -> dict[str, str]:
    """Extract YAML frontmatter key-value pairs from a markdown file.

    Supports only simple ``key: value`` lines (no nested YAML).  Returns
    an empty dict if no frontmatter is found.
    """
    result: dict[str, str] = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            first_line = f.readline().rstrip("\n")
            if first_line != "---":
                return result
            for line in f:
                line = line.rstrip("\n")
                if line == "---":
                    break
                if ":" in line:
                    key, _, value = line.partition(":")
                    result[key.strip()] = value.strip()
    except OSError:
        pass
    return result


def has_removed_status(filepath: str | Path) -> bool:
    """Return True if the file's frontmatter has ``status: removed``."""
    fm = read_frontmatter(filepath)
    return fm.get("status", "").lower() == "removed"


def load_manifest(manifest_path: str | Path) -> dict[str, Any] | None:
    """Load and return the sync manifest, or None if it doesn't exist."""
    p = Path(manifest_path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        fail(f"Cannot read manifest {p}: {exc}")


def save_manifest(manifest: dict[str, Any], manifest_path: str | Path) -> None:
    """Write the manifest atomically (write-then-rename)."""
    p = Path(manifest_path)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    tmp.rename(p)


def _parse_epic_index(filename: str) -> int | None:
    """Extract the epic number from a filename like epic-2-foo.md."""
    m = re.match(r"epic-(\d+)", filename)
    return int(m.group(1)) if m else None


def _parse_story_index(filename: str) -> int | None:
    """Extract the story number from a filename like story-03-bar.md."""
    m = re.match(r"story-(\d+)", filename)
    return int(m.group(1)) if m else None


def _extract_title_from_file(filepath: Path) -> str:
    """Extract a display title from an artifact file.

    Looks for the first markdown heading (``# ...``) after any
    frontmatter.  Falls back to the filename stem.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            in_frontmatter = False
            for line in f:
                stripped = line.strip()
                if stripped == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if in_frontmatter:
                    continue
                if stripped.startswith("# "):
                    return stripped[2:].strip()
    except OSError:
        pass
    return filepath.stem


def _read_file_content(filepath: Path) -> str:
    """Read full text content of a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------

# Pattern: "Story 1.01", "Story 2.03", "Stories 1.01, 2.03"
_STORY_REF_RE = re.compile(
    r"(?:Stories|Story)\s+"
    r"(\d+\.\d+(?:\s*,\s*\d+\.\d+)*)"
)

# Pattern: "Epic 1", "Epic 2", "Epics 1, 2"
_EPIC_REF_RE = re.compile(
    r"(?:Epics|Epic)\s+"
    r"(\d+(?:\s*,\s*\d+)*)"
)


def _build_ref_lookup(manifest: dict[str, Any]) -> dict[str, str]:
    """Build a mapping from local references to Jira keys.

    Keys are normalized forms like ``story-1.01``, ``epic-1``.
    Values are Jira issue keys.
    """
    lookup: dict[str, str] = {}
    for epic in manifest.get("epics", []):
        epic_idx = _parse_epic_index(epic.get("file", ""))
        jira_key = epic.get("jira_key", "")
        if epic_idx is not None and jira_key:
            lookup[f"epic-{epic_idx}"] = jira_key
        for story in epic.get("stories", []):
            story_idx = _parse_story_index(story.get("file", ""))
            story_jira = story.get("jira_key", "")
            if epic_idx is not None and story_idx is not None and story_jira:
                lookup[f"story-{epic_idx}.{story_idx:02d}"] = story_jira
    return lookup


def resolve_refs(text: str, manifest: dict[str, Any]) -> str:
    """Replace local Story/Epic references with Jira keys.

    Unresolvable references are annotated with ``[unresolved]``.
    """
    lookup = _build_ref_lookup(manifest)

    def _replace_story_refs(match: re.Match) -> str:
        refs_str = match.group(1)
        parts = [r.strip() for r in refs_str.split(",")]
        resolved = []
        prefix = "Stories" if len(parts) > 1 else "Story"
        for part in parts:
            key = f"story-{part}"
            jira_key = lookup.get(key)
            if jira_key:
                resolved.append(jira_key)
            else:
                resolved.append(f"{part} [unresolved]")
        return f"{prefix} {', '.join(resolved)}"

    def _replace_epic_refs(match: re.Match) -> str:
        refs_str = match.group(1)
        parts = [r.strip() for r in refs_str.split(",")]
        resolved = []
        prefix = "Epics" if len(parts) > 1 else "Epic"
        for part in parts:
            key = f"epic-{part}"
            jira_key = lookup.get(key)
            if jira_key:
                resolved.append(jira_key)
            else:
                resolved.append(f"{part} [unresolved]")
        return f"{prefix} {', '.join(resolved)}"

    result = _STORY_REF_RE.sub(_replace_story_refs, text)
    result = _EPIC_REF_RE.sub(_replace_epic_refs, result)
    return result


# ---------------------------------------------------------------------------
# Detect changes
# ---------------------------------------------------------------------------

def _discover_artifact_files(artifacts_dir: Path) -> tuple[list[Path], list[Path]]:
    """Discover epic and story files under the artifacts directory.

    Returns (epic_files, story_files) as sorted lists of Paths.
    Epic files:  ``06-stories/epic-{N}-{slug}.md``
    Story files: ``06-stories/epic-{N}/story-{NN}-{slug}.md``
    """
    stories_dir = artifacts_dir / "06-stories"
    if not stories_dir.is_dir():
        return [], []

    epic_files = sorted(stories_dir.glob("epic-*.md"))
    story_files: list[Path] = []
    for epic_dir in sorted(stories_dir.iterdir()):
        if epic_dir.is_dir() and epic_dir.name.startswith("epic-"):
            story_files.extend(sorted(epic_dir.glob("story-*.md")))
    return epic_files, story_files


def _manifest_epic_lookup(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a lookup from epic filename to manifest entry."""
    return {e["file"]: e for e in manifest.get("epics", []) if "file" in e}


def _manifest_story_lookup(manifest: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """Build a nested lookup: epic_file -> story_file -> manifest entry."""
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for epic in manifest.get("epics", []):
        epic_file = epic.get("file", "")
        stories: dict[str, dict[str, Any]] = {}
        for s in epic.get("stories", []):
            if "file" in s:
                stories[s["file"]] = s
        result[epic_file] = stories
    return result


def _check_removed_story_in_epic(
    story_path: Path,
    epic_path: Path,
    epic_index: int | None,
    story_index: int | None,
) -> str | None:
    """Check if a removed story is still listed in its epic file."""
    if epic_index is None or story_index is None:
        return None
    if not epic_path.exists():
        return None
    try:
        epic_content = _read_file_content(epic_path)
    except OSError:
        return None

    # Look for references like "Story 1.03" or "story-03" in the epic content
    story_ref = f"Story {epic_index}.{story_index:02d}"
    story_file_ref = f"story-{story_index:02d}"
    if story_ref in epic_content or story_file_ref in epic_content:
        return (
            f"Story {epic_index}.{story_index:02d} is marked for closure "
            f"but is still listed in Epic {epic_index}'s description. "
            f"Consider running /revise to update the epic file before "
            f"syncing, so the epic's Jira description stays accurate."
        )
    return None


def detect_changes(artifacts_dir: str | Path) -> dict[str, Any]:
    """Compare artifact files against the sync manifest.

    Returns a compact change plan as a dict with:
    - ``manifest_exists``: whether a manifest was found
    - ``schema_version``: manifest schema version (or 2 for fresh)
    - ``v1_migration``: True if migrating from v1
    - ``feature_key``: from manifest or None
    - ``synced_at``: from manifest or None
    - ``summary``: counts per category
    - ``items``: list of item dicts with category and metadata
    - ``warnings``: list of warning strings
    """
    artifacts_dir = Path(artifacts_dir)
    manifest_path = artifacts_dir / "sync-manifest.json"
    manifest = load_manifest(manifest_path)

    epic_files, story_files = _discover_artifact_files(artifacts_dir)

    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    v1_migration = False
    feature_key = None
    synced_at = None

    if manifest is None:
        # Fresh sync — all non-removed items are new
        for ef in epic_files:
            epic_idx = _parse_epic_index(ef.name)
            if has_removed_status(ef):
                continue  # Never synced, skip
            items.append({
                "file": ef.name,
                "type": "epic",
                "category": "new",
                "title": _extract_title_from_file(ef),
                "epic_index": epic_idx,
                "jira_key": None,
                "content_hash": compute_file_hash(ef),
                "old_hash": None,
                "synced_status": None,
            })

        for sf in story_files:
            epic_dir = sf.parent.name
            epic_idx = _parse_epic_index(epic_dir)
            story_idx = _parse_story_index(sf.name)
            if has_removed_status(sf):
                continue  # Never synced, skip
            items.append({
                "file": f"{epic_dir}/{sf.name}",
                "type": "story",
                "category": "new",
                "title": _extract_title_from_file(sf),
                "epic_index": epic_idx,
                "story_index": story_idx,
                "jira_key": None,
                "content_hash": compute_file_hash(sf),
                "old_hash": None,
                "synced_status": None,
            })

        summary = _compute_summary(items)
        return {
            "manifest_exists": False,
            "schema_version": 2,
            "v1_migration": False,
            "feature_key": None,
            "synced_at": None,
            "summary": summary,
            "items": items,
            "warnings": warnings,
        }

    # Manifest exists
    schema_version = manifest.get("schema_version", 1)
    v1_migration = schema_version == 1
    feature_key = manifest.get("feature_key")
    synced_at = manifest.get("synced_at")

    epic_lookup = _manifest_epic_lookup(manifest)
    story_lookup = _manifest_story_lookup(manifest)

    # Track which manifest entries we've matched to files on disk
    matched_epic_files: set[str] = set()
    matched_story_files: dict[str, set[str]] = {
        ef: set() for ef in story_lookup
    }

    # Process epic files
    for ef in epic_files:
        epic_idx = _parse_epic_index(ef.name)
        removed = has_removed_status(ef)
        current_hash = compute_file_hash(ef)
        manifest_entry = epic_lookup.get(ef.name)

        if manifest_entry is not None:
            matched_epic_files.add(ef.name)
            # v1 migration: no synced_status or content_hash
            m_status = manifest_entry.get("synced_status", "active")
            m_hash = manifest_entry.get("content_hash")
            jira_key = manifest_entry.get("jira_key")

            category = _categorize_item(removed, m_status, current_hash, m_hash)
            items.append({
                "file": ef.name,
                "type": "epic",
                "category": category,
                "title": _extract_title_from_file(ef),
                "epic_index": epic_idx,
                "jira_key": jira_key,
                "content_hash": current_hash,
                "old_hash": m_hash,
                "synced_status": m_status,
            })
        else:
            # No manifest entry
            if removed:
                continue  # Never synced, skip
            items.append({
                "file": ef.name,
                "type": "epic",
                "category": "new",
                "title": _extract_title_from_file(ef),
                "epic_index": epic_idx,
                "jira_key": None,
                "content_hash": current_hash,
                "old_hash": None,
                "synced_status": None,
            })

    # Process story files
    for sf in story_files:
        epic_dir = sf.parent.name
        epic_idx = _parse_epic_index(epic_dir)
        story_idx = _parse_story_index(sf.name)
        removed = has_removed_status(sf)
        current_hash = compute_file_hash(sf)

        # Find the corresponding epic file for this story's epic dir
        epic_file_candidates = [
            ef.name for ef in epic_files
            if _parse_epic_index(ef.name) == epic_idx
        ]
        epic_file_name = epic_file_candidates[0] if epic_file_candidates else None

        # Find manifest entry for this story
        manifest_entry = None
        if epic_file_name and epic_file_name in story_lookup:
            stories_map = story_lookup[epic_file_name]
            manifest_entry = stories_map.get(sf.name)
            if manifest_entry is not None:
                if epic_file_name not in matched_story_files:
                    matched_story_files[epic_file_name] = set()
                matched_story_files[epic_file_name].add(sf.name)

        if manifest_entry is not None:
            m_status = manifest_entry.get("synced_status", "active")
            m_hash = manifest_entry.get("content_hash")
            jira_key = manifest_entry.get("jira_key")

            category = _categorize_item(removed, m_status, current_hash, m_hash)

            # Check removed-story-under-active-epic warning
            if category == "removed" and epic_file_name:
                epic_path = artifacts_dir / "06-stories" / epic_file_name
                warn = _check_removed_story_in_epic(
                    sf, epic_path, epic_idx, story_idx
                )
                if warn:
                    warnings.append(warn)

            items.append({
                "file": f"{epic_dir}/{sf.name}",
                "type": "story",
                "category": category,
                "title": _extract_title_from_file(sf),
                "epic_index": epic_idx,
                "story_index": story_idx,
                "jira_key": jira_key,
                "content_hash": current_hash,
                "old_hash": m_hash,
                "synced_status": m_status,
            })
        else:
            if removed:
                continue  # Never synced, skip
            items.append({
                "file": f"{epic_dir}/{sf.name}",
                "type": "story",
                "category": "new",
                "title": _extract_title_from_file(sf),
                "epic_index": epic_idx,
                "story_index": story_idx,
                "jira_key": None,
                "content_hash": current_hash,
                "old_hash": None,
                "synced_status": None,
            })

    # Orphaned manifest entries: active entries with no file on disk
    for epic_file, epic_entry in epic_lookup.items():
        if epic_file not in matched_epic_files:
            m_status = epic_entry.get("synced_status", "active")
            if m_status == "active":
                items.append({
                    "file": epic_file,
                    "type": "epic",
                    "category": "orphaned",
                    "title": epic_entry.get("title", ""),
                    "epic_index": _parse_epic_index(epic_file),
                    "jira_key": epic_entry.get("jira_key"),
                    "content_hash": None,
                    "old_hash": epic_entry.get("content_hash"),
                    "synced_status": m_status,
                })
            # closed entries whose files were deleted: silently ignored

    for epic_file, stories_map in story_lookup.items():
        matched = matched_story_files.get(epic_file, set())
        for story_file, story_entry in stories_map.items():
            if story_file not in matched:
                m_status = story_entry.get("synced_status", "active")
                if m_status == "active":
                    epic_idx = _parse_epic_index(epic_file)
                    epic_dir = f"epic-{epic_idx}" if epic_idx else epic_file.replace(".md", "")
                    items.append({
                        "file": f"{epic_dir}/{story_file}",
                        "type": "story",
                        "category": "orphaned",
                        "title": story_entry.get("title", ""),
                        "epic_index": epic_idx,
                        "story_index": _parse_story_index(story_file),
                        "jira_key": story_entry.get("jira_key"),
                        "content_hash": None,
                        "old_hash": story_entry.get("content_hash"),
                        "synced_status": m_status,
                    })

    summary = _compute_summary(items)
    return {
        "manifest_exists": True,
        "schema_version": schema_version,
        "v1_migration": v1_migration,
        "feature_key": feature_key,
        "synced_at": synced_at,
        "summary": summary,
        "items": items,
        "warnings": warnings,
    }


def _categorize_item(
    removed: bool,
    synced_status: str,
    current_hash: str,
    manifest_hash: str | None,
) -> str:
    """Categorize a single item given its file state and manifest state."""
    if removed:
        if synced_status == "closed":
            return "unchanged"  # already closed
        return "removed"
    if synced_status == "closed":
        return "reopened"
    if manifest_hash is None:
        return "changed"  # v1 migration: no hash stored
    if current_hash != manifest_hash:
        return "changed"
    return "unchanged"


def _compute_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    """Count items per category."""
    counts: dict[str, int] = {
        "new": 0, "changed": 0, "removed": 0,
        "unchanged": 0, "orphaned": 0, "reopened": 0,
    }
    for item in items:
        cat = item.get("category", "")
        if cat in counts:
            counts[cat] += 1
    return counts


# ---------------------------------------------------------------------------
# Description rendering
# ---------------------------------------------------------------------------

def _extract_sections(filepath: Path) -> dict[str, str]:
    """Extract markdown sections from a file (heading -> content)."""
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []
    in_frontmatter = False

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped == "---":
                if current_heading is None and not in_frontmatter:
                    in_frontmatter = True
                    continue
                elif in_frontmatter:
                    in_frontmatter = False
                    continue
            if in_frontmatter:
                continue

            if stripped.startswith("## ") or stripped.startswith("# "):
                if current_heading is not None:
                    sections[current_heading] = "\n".join(current_lines).strip()
                level = 2 if stripped.startswith("## ") else 1
                current_heading = stripped[level + 1:].strip()
                current_lines = []
            elif current_heading is not None:
                current_lines.append(line.rstrip("\n"))

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def render_epic_description(
    epic_path: str | Path,
    manifest: dict[str, Any] | None,
    design_doc_link: str = "",
    feature_key: str = "",
) -> str:
    """Render a Jira-ready epic description from an artifact file."""
    epic_path = Path(epic_path)
    sections = _extract_sections(epic_path)

    summary_text = sections.get("Summary", "")
    ac_text = sections.get("Acceptance Criteria", "")

    parts = ["## Summary", "", summary_text, ""]
    if ac_text:
        parts.extend(["## Acceptance Criteria", "", ac_text, ""])

    parts.extend([
        "## Design Reference", "",
        f"Design document: {design_doc_link}" if design_doc_link else "Design document:",
        f"Feature: {feature_key}" if feature_key else "Feature:",
    ])

    description = "\n".join(parts)
    if manifest:
        description = resolve_refs(description, manifest)
    return description


def render_story_description(
    story_path: str | Path,
    manifest: dict[str, Any] | None,
    design_doc_link: str = "",
    epic_jira_key: str = "",
    story_type: str = "",
) -> str:
    """Render a Jira-ready story description from an artifact file.

    ``story_type`` should be the story prefix (DEV, UI, UX, QE, CI, DOCS).
    If not provided, it is inferred from the story title.
    """
    story_path = Path(story_path)
    sections = _extract_sections(story_path)
    fm = read_frontmatter(story_path)

    # Infer type from title if not provided
    if not story_type:
        title = _extract_title_from_file(story_path)
        m = re.match(r"\[(\w+)\]", title)
        story_type = m.group(1) if m else ""

    is_docs = story_type.upper() == "DOCS"

    parts: list[str] = []

    # User Story section
    user_story = sections.get("User Story", "")
    if user_story:
        parts.extend(["## User Story", "", user_story, ""])

    # Acceptance Criteria
    ac = sections.get("Acceptance Criteria", "")
    if ac:
        parts.extend(["## Acceptance Criteria", "", ac, ""])

    if is_docs:
        # DOCS-specific sections
        doc_scope = sections.get("Documentation Scope", "")
        if doc_scope:
            parts.extend(["## Documentation Scope", "", doc_scope, ""])
        doc_inputs = sections.get("Documentation Inputs", "")
        if doc_inputs:
            parts.extend(["## Documentation Inputs", "", doc_inputs, ""])
    else:
        # DEV/UI/UX/QE/CI sections
        impl = sections.get("Implementation Guidance", "")
        if impl:
            parts.extend(["## Implementation Guidance", "", impl, ""])
        testing = sections.get("Testing Approach", "")
        if testing:
            parts.extend(["## Testing Approach", "", testing, ""])

    # Dependencies (both types)
    deps = sections.get("Dependencies", "")
    if deps:
        parts.extend(["## Dependencies", "", deps, ""])

    # Design Reference
    design_ref = sections.get("Design Reference", "")
    if design_ref:
        parts.extend(["## Design Reference", "", design_ref, ""])
    else:
        ref_parts = [
            "## Design Reference", "",
            f"Design document: {design_doc_link}" if design_doc_link else "Design document:",
            f"Epic: {epic_jira_key}" if epic_jira_key else "Epic:",
        ]
        # Add PRD Requirements and Design section from frontmatter if available
        if fm.get("prd_requirements"):
            ref_parts.append(f"PRD Requirements: {fm['prd_requirements']}")
        if fm.get("design_section"):
            ref_parts.append(f"Design section: {fm['design_section']}")
        parts.extend(ref_parts)

    description = "\n".join(parts)
    if manifest:
        description = resolve_refs(description, manifest)
    return description


# ---------------------------------------------------------------------------
# Manifest updates
# ---------------------------------------------------------------------------

def update_manifest(
    manifest_path: str | Path,
    operation: str,
    artifact_file: str,
    jira_key: str,
    content_hash: str,
    item_type: str = "epic",
    title: str = "",
    size: str = "",
) -> dict[str, Any]:
    """Record a single successful Jira operation in the manifest.

    This is the per-item checkpoint: called only after a Jira operation
    succeeds.  The ``content_hash`` must be the hash of the file content
    that was actually submitted to Jira, not a freshly recomputed hash
    that might reflect subsequent edits.

    ``operation`` must be one of: ``create``, ``update``, ``close``.
    ``item_type`` must be ``epic`` or ``story``.
    """
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)

    if manifest is None:
        manifest = {
            "schema_version": 2,
            "feature_key": "",
            "synced_at": "",
            "epics": [],
        }

    # Ensure v2
    manifest["schema_version"] = 2

    if operation == "close":
        synced_status = "closed"
    else:
        synced_status = "active"

    if item_type == "epic":
        _update_manifest_epic(
            manifest, artifact_file, jira_key, content_hash,
            synced_status, title, size,
        )
    elif item_type == "story":
        _update_manifest_story(
            manifest, artifact_file, jira_key, content_hash,
            synced_status, title,
        )
    else:
        fail(f"Unknown item_type: {item_type}")

    manifest["synced_at"] = datetime.now(timezone.utc).isoformat()
    save_manifest(manifest, manifest_path)
    return manifest


def _update_manifest_epic(
    manifest: dict[str, Any],
    epic_file: str,
    jira_key: str,
    content_hash: str,
    synced_status: str,
    title: str,
    size: str,
) -> None:
    """Update or insert an epic entry in the manifest."""
    for epic in manifest.get("epics", []):
        if epic.get("file") == epic_file:
            epic["jira_key"] = jira_key
            epic["content_hash"] = content_hash
            epic["synced_status"] = synced_status
            if title:
                epic["title"] = title
            if size:
                epic["size"] = size
            return
    # New epic entry
    entry: dict[str, Any] = {
        "file": epic_file,
        "jira_key": jira_key,
        "title": title,
        "size": size,
        "content_hash": content_hash,
        "synced_status": synced_status,
        "stories": [],
    }
    manifest.setdefault("epics", []).append(entry)


def _update_manifest_story(
    manifest: dict[str, Any],
    story_file: str,
    jira_key: str,
    content_hash: str,
    synced_status: str,
    title: str,
) -> None:
    """Update or insert a story entry in the manifest.

    ``story_file`` is in the form ``story-01-foo.md`` (basename only).
    The parent epic is inferred from the story's path context: the
    caller must ensure the epic already exists in the manifest.  If no
    parent epic is found, the story is appended to the last epic.
    """
    # Try to find which epic this story belongs to by checking epic
    # directories.  The story_file is just the basename; the epic
    # association comes from the detect-changes item's ``epic_index``.
    # Since we don't have the full path here, search all epics.
    for epic in manifest.get("epics", []):
        for story in epic.get("stories", []):
            if story.get("file") == story_file:
                story["jira_key"] = jira_key
                story["content_hash"] = content_hash
                story["synced_status"] = synced_status
                if title:
                    story["title"] = title
                return

    # New story — append to the last epic (caller is expected to have
    # created the epic entry first, per the spec's ordering).
    if manifest.get("epics"):
        entry: dict[str, Any] = {
            "file": story_file,
            "jira_key": jira_key,
            "title": title,
            "content_hash": content_hash,
            "synced_status": synced_status,
        }
        manifest["epics"][-1].setdefault("stories", []).append(entry)


def _update_manifest_story_with_epic(
    manifest: dict[str, Any],
    story_file: str,
    jira_key: str,
    content_hash: str,
    synced_status: str,
    title: str,
    epic_file: str,
) -> None:
    """Update or insert a story entry under a specific epic."""
    for epic in manifest.get("epics", []):
        if epic.get("file") == epic_file:
            for story in epic.get("stories", []):
                if story.get("file") == story_file:
                    story["jira_key"] = jira_key
                    story["content_hash"] = content_hash
                    story["synced_status"] = synced_status
                    if title:
                        story["title"] = title
                    return
            # New story under this epic
            entry: dict[str, Any] = {
                "file": story_file,
                "jira_key": jira_key,
                "title": title,
                "content_hash": content_hash,
                "synced_status": synced_status,
            }
            epic.setdefault("stories", []).append(entry)
            return
    # Epic not found — fall back to last epic
    _update_manifest_story(
        manifest, story_file, jira_key, content_hash, synced_status, title,
    )


def migrate_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Upgrade a v1 manifest to v2 schema in place.

    V1 manifests lack ``content_hash`` and ``synced_status`` fields.
    Migration sets ``synced_status: "active"`` on all entries and leaves
    ``content_hash`` as ``null`` (to be populated on next sync).
    """
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    if manifest is None:
        fail(f"Manifest not found: {manifest_path}")

    if manifest.get("schema_version", 1) >= 2:
        info("Manifest is already v2 — no migration needed.")
        return manifest

    manifest["schema_version"] = 2
    migrated_count = 0
    for epic in manifest.get("epics", []):
        if "synced_status" not in epic:
            epic["synced_status"] = "active"
        if "content_hash" not in epic:
            epic["content_hash"] = None
        migrated_count += 1
        for story in epic.get("stories", []):
            if "synced_status" not in story:
                story["synced_status"] = "active"
            if "content_hash" not in story:
                story["content_hash"] = None
            migrated_count += 1

    save_manifest(manifest, manifest_path)
    info(f"Migrated {migrated_count} entries from v1 to v2.")
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="sync_helper.py",
        description="Deterministic sync operations for the design workflow.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # detect-changes
    p_detect = sub.add_parser(
        "detect-changes",
        help="Compare artifact files against sync manifest.",
    )
    p_detect.add_argument(
        "artifacts_dir",
        help="Path to .artifacts/design/{issue-key}/ directory.",
    )

    # resolve-refs
    p_resolve = sub.add_parser(
        "resolve-refs",
        help="Replace local identifiers with Jira keys.",
    )
    p_resolve.add_argument("manifest_path", help="Path to sync-manifest.json.")
    p_resolve.add_argument("text", help="Text containing local references.")

    # render-description
    p_render = sub.add_parser(
        "render-description",
        help="Render a Jira-ready description from an artifact file.",
    )
    p_render.add_argument("artifact_file", help="Path to the artifact .md file.")
    p_render.add_argument("manifest_path", help="Path to sync-manifest.json.")
    p_render.add_argument(
        "--type", choices=["epic", "story"], required=True,
        help="Whether to render an epic or story description.",
    )
    p_render.add_argument("--design-doc-link", default="", help="Link to design doc.")
    p_render.add_argument("--feature-key", default="", help="Feature issue key.")
    p_render.add_argument("--epic-jira-key", default="", help="Epic Jira key (stories only).")
    p_render.add_argument("--story-type", default="", help="Story prefix (DEV, UI, etc.).")

    # update-manifest
    p_update = sub.add_parser(
        "update-manifest",
        help="Record a successful Jira operation in the manifest.",
    )
    p_update.add_argument("manifest_path", help="Path to sync-manifest.json.")
    p_update.add_argument(
        "--operation", required=True, choices=["create", "update", "close"],
    )
    p_update.add_argument("--file", required=True, dest="artifact_file",
                          help="Artifact filename (e.g. epic-1-foo.md).")
    p_update.add_argument("--jira-key", required=True, help="Jira issue key.")
    p_update.add_argument("--content-hash", required=True,
                          help="SHA-256 hash of the submitted content.")
    p_update.add_argument("--item-type", choices=["epic", "story"], default="epic")
    p_update.add_argument("--title", default="")
    p_update.add_argument("--size", default="")
    p_update.add_argument("--epic-file", default="",
                          help="Parent epic filename (stories only, for precise placement).")

    # compute-hash
    p_hash = sub.add_parser(
        "compute-hash",
        help="Print the SHA-256 hex digest of a file.",
    )
    p_hash.add_argument("file_path", help="Path to the file.")

    # migrate-manifest
    p_migrate = sub.add_parser(
        "migrate-manifest",
        help="Upgrade a v1 manifest to v2 schema.",
    )
    p_migrate.add_argument("manifest_path", help="Path to sync-manifest.json.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "detect-changes":
        result = detect_changes(args.artifacts_dir)
        json.dump(result, sys.stdout, indent=2)
        print()
        return EXIT_SUCCESS

    elif args.command == "resolve-refs":
        manifest = load_manifest(args.manifest_path)
        if manifest is None:
            fail(f"Manifest not found: {args.manifest_path}")
        resolved = resolve_refs(args.text, manifest)
        print(resolved, end="")
        return EXIT_SUCCESS

    elif args.command == "render-description":
        manifest = load_manifest(args.manifest_path)
        if args.type == "epic":
            desc = render_epic_description(
                args.artifact_file,
                manifest,
                design_doc_link=args.design_doc_link,
                feature_key=args.feature_key,
            )
        else:
            desc = render_story_description(
                args.artifact_file,
                manifest,
                design_doc_link=args.design_doc_link,
                epic_jira_key=args.epic_jira_key,
                story_type=args.story_type,
            )
        print(desc, end="")
        return EXIT_SUCCESS

    elif args.command == "update-manifest":
        if args.epic_file and args.item_type == "story":
            manifest = load_manifest(args.manifest_path) or {
                "schema_version": 2, "feature_key": "", "synced_at": "", "epics": [],
            }
            _update_manifest_story_with_epic(
                manifest, args.artifact_file, args.jira_key,
                args.content_hash, "closed" if args.operation == "close" else "active",
                args.title, args.epic_file,
            )
            manifest["synced_at"] = datetime.now(timezone.utc).isoformat()
            save_manifest(manifest, args.manifest_path)
        else:
            update_manifest(
                args.manifest_path,
                args.operation,
                args.artifact_file,
                args.jira_key,
                args.content_hash,
                item_type=args.item_type,
                title=args.title,
                size=args.size,
            )
        return EXIT_SUCCESS

    elif args.command == "compute-hash":
        try:
            h = compute_file_hash(args.file_path)
        except OSError as exc:
            fail(f"Cannot read file: {exc}")
        print(h)
        return EXIT_SUCCESS

    elif args.command == "migrate-manifest":
        migrate_manifest(args.manifest_path)
        return EXIT_SUCCESS

    else:
        fail(f"Unknown command: {args.command}")

    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
