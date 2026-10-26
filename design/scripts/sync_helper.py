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
  prepare          Compute hash and render description in one call,
                   returning both from a single file read.

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

# Supported manifest schema versions
_SUPPORTED_SCHEMA_VERSIONS = {1, 2}


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


def _hash_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def read_frontmatter(filepath: str | Path) -> dict[str, str]:
    """Extract YAML frontmatter key-value pairs from a markdown file.

    Supports only simple ``key: value`` lines (no nested YAML).  Returns
    an empty dict if no frontmatter is found.  Raises ``OSError`` on I/O
    errors -- callers must handle this explicitly.
    """
    result: dict[str, str] = {}
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
    return result


def has_removed_status(filepath: str | Path) -> bool:
    """Return True if the file's frontmatter has ``status: removed``.

    Returns False (not removed) if the file cannot be read -- the caller
    will encounter the error when reading the file for other purposes.
    """
    try:
        fm = read_frontmatter(filepath)
    except OSError:
        return False
    return fm.get("status", "").lower() == "removed"


def _validate_manifest_shape(manifest: Any, source: str) -> dict[str, Any]:
    """Validate that a parsed manifest has the expected shape.

    Checks: top-level is a dict, has an ``epics`` list, schema version
    is supported, no duplicate epic file entries.  Returns the validated
    manifest dict or calls fail().
    """
    if not isinstance(manifest, dict):
        fail(f"Manifest {source}: expected JSON object, got {type(manifest).__name__}")
    version = manifest.get("schema_version", 1)
    if version not in _SUPPORTED_SCHEMA_VERSIONS:
        fail(f"Manifest {source}: unsupported schema_version {version} "
             f"(supported: {sorted(_SUPPORTED_SCHEMA_VERSIONS)})")
    epics = manifest.get("epics")
    if epics is not None and not isinstance(epics, list):
        fail(f"Manifest {source}: 'epics' must be a list, got {type(epics).__name__}")
    # Validate epic entries and check for duplicates
    if epics is not None:
        seen_files: set[str] = set()
        seen_indices: dict[int, str] = {}
        for i, epic in enumerate(epics):
            if not isinstance(epic, dict):
                fail(f"Manifest {source}: epic entry [{i}] must be a dict")
            ef = epic.get("file")
            if not ef or not isinstance(ef, str):
                fail(f"Manifest {source}: epic entry [{i}] missing "
                     f"required 'file' field")
            if ef in seen_files:
                fail(f"Manifest {source}: duplicate epic file '{ef}'")
            seen_files.add(ef)
            # Check for duplicate numeric indices across different filenames
            idx = _parse_epic_index(ef)
            if idx is not None:
                if idx in seen_indices and seen_indices[idx] != ef:
                    fail(f"Manifest {source}: duplicate epic index {idx} "
                         f"('{seen_indices[idx]}' and '{ef}')")
                seen_indices[idx] = ef
            # Validate stories list within each epic
            stories = epic.get("stories")
            if stories is not None:
                if not isinstance(stories, list):
                    fail(f"Manifest {source}: epic '{ef}' stories must "
                         f"be a list")
                seen_story_files: set[str] = set()
                for j, story in enumerate(stories):
                    if not isinstance(story, dict):
                        fail(f"Manifest {source}: epic '{ef}' "
                             f"story [{j}] must be a dict")
                    sf = story.get("file")
                    if not sf or not isinstance(sf, str):
                        fail(f"Manifest {source}: epic '{ef}' "
                             f"story [{j}] missing required 'file' field")
                    if sf in seen_story_files:
                        fail(f"Manifest {source}: epic '{ef}' has "
                             f"duplicate story file '{sf}'")
                    seen_story_files.add(sf)
                # Check for duplicate numeric story indices within epic
                seen_story_indices: dict[int, str] = {}
                for story in stories:
                    sf = story.get("file", "")
                    sidx = _parse_story_index(sf)
                    if sidx is None:
                        continue
                    if sidx in seen_story_indices:
                        fail(f"Manifest {source}: epic '{ef}' has "
                             f"duplicate story index {sidx}: "
                             f"'{seen_story_indices[sidx]}' and '{sf}'")
                    seen_story_indices[sidx] = sf
    return manifest


def load_manifest(manifest_path: str | Path) -> dict[str, Any] | None:
    """Load and return the sync manifest, or None if it doesn't exist."""
    p = Path(manifest_path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        fail(f"Cannot read manifest {p}: {exc}")
    return _validate_manifest_shape(data, str(p))


def save_manifest(manifest: dict[str, Any], manifest_path: str | Path) -> None:
    """Write the manifest atomically (exclusive-tmp-then-rename)."""
    import tempfile as _tmpmod
    p = Path(manifest_path)
    fd = -1
    tmp_path: Path | None = None
    try:
        fd, tmp_name = _tmpmod.mkstemp(
            prefix=".sync-manifest-", suffix=".tmp", dir=str(p.parent),
        )
        tmp_path = Path(tmp_name)
        with open(fd, "w", encoding="utf-8", closefd=True) as f:
            fd = -1  # now owned by the file object
            json.dump(manifest, f, indent=2)
            f.write("\n")
        if p.exists():
            import shutil as _shutilmod
            _shutilmod.copymode(str(p), str(tmp_path))
        tmp_path.replace(p)
        tmp_path = None  # replace succeeded
    except BaseException:
        if fd >= 0:
            import os
            os.close(fd)
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


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

    Returns (epic_files, story_files) sorted numerically by index.
    Fails if multiple epic files share the same numeric index.
    Epic files:  ``06-stories/epic-{N}-{slug}.md``
    Story files: ``06-stories/epic-{N}/story-{NN}-{slug}.md``
    """
    stories_dir = artifacts_dir / "06-stories"
    if not stories_dir.is_dir():
        return [], []

    epic_files = sorted(
        stories_dir.glob("epic-*.md"),
        key=lambda p: (_parse_epic_index(p.name) or 0, p.name),
    )

    # Fail closed on duplicate numeric epic indices
    seen_indices: dict[int, str] = {}
    for ef in epic_files:
        idx = _parse_epic_index(ef.name)
        if idx is None:
            continue
        if idx in seen_indices:
            fail(f"Duplicate epic index {idx}: '{seen_indices[idx]}' and "
                 f"'{ef.name}' in {stories_dir}. Rename or remove one "
                 f"before syncing.")
        seen_indices[idx] = ef.name

    story_files: list[Path] = []
    epic_dirs = sorted(
        (d for d in stories_dir.iterdir()
         if d.is_dir() and d.name.startswith("epic-")),
        key=lambda d: (_parse_epic_index(d.name) or 0, d.name),
    )
    # Group story-index checks by NUMERIC epic index across all directories.
    # epic-1/ and epic-01/ both map to numeric 1, so duplicate story indices
    # across directory aliases must be rejected.
    seen_story_idx_by_epic: dict[int, dict[int, str]] = {}
    for epic_dir in epic_dirs:
        dir_epic_idx = _parse_epic_index(epic_dir.name)
        dir_stories = sorted(
            epic_dir.glob("story-*.md"),
            key=lambda p: (_parse_story_index(p.name) or 0, p.name),
        )
        for sp in dir_stories:
            sidx = _parse_story_index(sp.name)
            if sidx is None:
                continue
            if dir_epic_idx is not None:
                seen = seen_story_idx_by_epic.setdefault(dir_epic_idx, {})
                rel_path = f"{epic_dir.name}/{sp.name}"
                if sidx in seen:
                    fail(f"Duplicate story index {sidx} for epic "
                         f"index {dir_epic_idx}: '{seen[sidx]}' and "
                         f"'{rel_path}'. "
                         f"Rename or remove one before syncing.")
                seen[sidx] = rel_path
        story_files.extend(dir_stories)
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

    # If 06-stories/ is missing entirely, fail closed rather than silently
    # presenting all manifest entries as orphans or showing zero items.
    stories_dir = artifacts_dir / "06-stories"
    if not stories_dir.is_dir():
        if manifest is not None:
            fail(f"06-stories/ directory missing at {artifacts_dir}. "
                 f"Cannot compare manifest entries against artifacts. "
                 f"Verify the artifacts path or run /decompose first.")
        else:
            fail(f"No decomposition artifacts found at {artifacts_dir}. "
                 f"Run /decompose before /sync.")

    # Build set of removed epic indices (for skipping their children)
    removed_epic_indices: set[int] = set()
    for ef in epic_files:
        idx = _parse_epic_index(ef.name)
        if idx is not None and has_removed_status(ef):
            removed_epic_indices.add(idx)

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
            # Skip children of removed epics on fresh sync
            if epic_idx is not None and epic_idx in removed_epic_indices:
                continue
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
            if removed:
                continue  # Never synced, skip
            # Fail closed if a manifest epic has the same numeric index
            # under a different filename — epic was renamed on disk.
            if epic_idx is not None:
                manifest_epic_for_idx = next(
                    (name for name in epic_lookup
                     if _parse_epic_index(name) == epic_idx),
                    None,
                )
                if manifest_epic_for_idx is not None:
                    fail(
                        f"Epic '{ef.name}' on disk has index {epic_idx} "
                        f"but manifest records '{manifest_epic_for_idx}' "
                        f"for that index. Restore the original filename "
                        f"or update the manifest before syncing to avoid "
                        f"duplicate Jira issues."
                    )
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

    # Build set of epic indices whose epics are effectively removed/closed.
    # Children under these epics should not be created/reopened/updated.
    # A manifest-closed epic that has been REOPENED (file exists without
    # removed marker) is NOT in this set — its children can be processed.
    closed_epic_indices: set[int] = set(removed_epic_indices)
    # Map epic files by index for quick lookup
    _epic_file_by_idx: dict[int, Path] = {}
    for ef in epic_files:
        idx = _parse_epic_index(ef.name)
        if idx is not None:
            _epic_file_by_idx[idx] = ef
    for ef_name, entry in epic_lookup.items():
        idx = _parse_epic_index(ef_name)
        if idx is None:
            continue
        if entry.get("synced_status") != "closed":
            continue
        # Check if the epic file exists and is NOT removed → reopened
        disk_file = _epic_file_by_idx.get(idx)
        if disk_file is not None and not has_removed_status(disk_file):
            continue  # Will be categorized as reopened; allow children
        closed_epic_indices.add(idx)

    # Process story files
    for sf in story_files:
        epic_dir = sf.parent.name
        epic_idx = _parse_epic_index(epic_dir)
        story_idx = _parse_story_index(sf.name)
        removed = has_removed_status(sf)
        current_hash = compute_file_hash(sf)

        # If parent epic is removed/closed, treat child as following parent
        parent_removed = epic_idx is not None and epic_idx in closed_epic_indices

        # Safe: _discover_artifact_files already rejected duplicate indices
        epic_file_candidates = [
            ef.name for ef in epic_files
            if _parse_epic_index(ef.name) == epic_idx
        ]
        epic_file_name = epic_file_candidates[0] if epic_file_candidates else None

        manifest_entry = None
        if epic_file_name and epic_file_name in story_lookup:
            stories_map = story_lookup[epic_file_name]
            manifest_entry = stories_map.get(sf.name)
            if manifest_entry is not None:
                if epic_file_name not in matched_story_files:
                    matched_story_files[epic_file_name] = set()
                matched_story_files[epic_file_name].add(sf.name)

        # Fail closed: if the story wasn't matched above but the manifest
        # has an epic with the same numeric index under a different filename,
        # the epic was renamed or deleted.  Producing both an orphan close
        # and a new-create for the same child would duplicate Jira issues.
        if manifest_entry is None and epic_idx is not None:
            manifest_epic_for_idx = next(
                (name for name in epic_lookup
                 if _parse_epic_index(name) == epic_idx),
                None,
            )
            if (manifest_epic_for_idx is not None
                    and manifest_epic_for_idx != epic_file_name):
                fail(
                    f"Story '{epic_dir}/{sf.name}' belongs to epic "
                    f"index {epic_idx}, but the manifest records "
                    f"'{manifest_epic_for_idx}' for that index (disk "
                    f"has '{epic_file_name or 'no epic file'}'). "
                    f"Restore or rename the epic file before syncing "
                    f"to avoid duplicate Jira issues."
                )

        # Fail closed: if the story has no manifest entry but the manifest
        # has a DIFFERENT story filename with the same numeric index under
        # the same epic, the story was likely renamed.  Planning both an
        # orphan close and a new-create for the same index would duplicate
        # Jira issues.  This check applies regardless of the manifest
        # entry's synced_status — even a closed entry sharing the same
        # index under a different filename would create a duplicate-index
        # manifest that fails _validate_manifest_shape on subsequent load.
        if (manifest_entry is None and story_idx is not None
                and epic_file_name and epic_file_name in story_lookup):
            for m_story_name, m_story in story_lookup[epic_file_name].items():
                if (_parse_story_index(m_story_name) == story_idx
                        and m_story_name != sf.name):
                    fail(
                        f"Story index {story_idx} under "
                        f"'{epic_file_name}': disk has "
                        f"'{sf.name}' but the manifest records "
                        f"'{m_story_name}' (Jira key "
                        f"'{m_story.get('jira_key', '?')}', status "
                        f"'{m_story.get('synced_status', '?')}'). "
                        f"This looks like a rename — update the "
                        f"manifest or restore the original filename "
                        f"before syncing."
                    )

        if manifest_entry is not None:
            m_status = manifest_entry.get("synced_status", "active")
            m_hash = manifest_entry.get("content_hash")
            jira_key = manifest_entry.get("jira_key")

            category = _categorize_item(removed, m_status, current_hash, m_hash)

            # If parent is removed/closed and child would be
            # reopened/changed/new, suppress — treat as removed if
            # manifest entry is active, or unchanged if already closed
            if parent_removed and category in ("reopened", "changed", "new"):
                if m_status == "active":
                    category = "removed"
                else:
                    category = "unchanged"

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
            if removed or parent_removed:
                continue  # Never synced and parent removed, skip
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
    """Extract markdown sections from a file (heading -> content).

    Skips headings inside fenced code blocks (``` ... ```) to avoid
    treating example code as real sections.

    Content between ``# Title`` and the first ``##`` section is stored
    under the key ``_preamble`` — this captures the user story text that
    the decompose template places directly after the title heading.
    """
    content = _read_file_content(filepath)
    return _extract_sections_from_text(content)


def _extract_sections_from_text(text: str) -> dict[str, str]:
    """Extract markdown sections from text content.

    See ``_extract_sections`` for semantics.
    """
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []
    in_frontmatter = False
    in_code_fence = False
    seen_title = False

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Frontmatter
        if stripped == "---":
            if not seen_title and not in_frontmatter and not in_code_fence:
                in_frontmatter = True
                continue
            elif in_frontmatter:
                in_frontmatter = False
                continue
        if in_frontmatter:
            continue

        # Fenced code blocks
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            if current_heading is not None:
                current_lines.append(line)
            continue
        if in_code_fence:
            if current_heading is not None:
                current_lines.append(line)
            continue

        # Headings
        if stripped.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = stripped[3:].strip()
            current_lines = []
            seen_title = True
        elif stripped.startswith("# "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            # Store content after # title under _preamble
            current_heading = "_preamble"
            current_lines = []
            seen_title = True
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def render_epic_description(
    epic_path: str | Path,
    manifest: dict[str, Any] | None,
    design_doc_link: str = "",
    feature_key: str = "",
    *,
    _content: str | None = None,
) -> str:
    """Render a Jira-ready epic description from an artifact file.

    When ``_content`` is provided, sections are extracted from it instead
    of reading the file again (used by ``prepare`` for snapshot
    consistency).
    """
    epic_path = Path(epic_path)
    if _content is not None:
        sections = _extract_sections_from_text(_content)
    else:
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
    *,
    _content: str | None = None,
) -> str:
    """Render a Jira-ready story description from an artifact file.

    ``story_type`` should be the story prefix (DEV, UI, UX, QE, CI, DOCS).
    If not provided, it is inferred from the story title.
    """
    story_path = Path(story_path)
    if _content is not None:
        sections = _extract_sections_from_text(_content)
        # Parse frontmatter from content string for metadata
        fm: dict[str, str] = {}
        if _content.startswith("---\n"):
            end = _content.find("\n---\n", 4)
            if end != -1:
                for fmline in _content[4:end].splitlines():
                    if ":" in fmline:
                        k, _, v = fmline.partition(":")
                        fm[k.strip()] = v.strip()
    else:
        sections = _extract_sections(story_path)
        try:
            fm = read_frontmatter(story_path)
        except OSError:
            fm = {}

    # Infer type from title if not provided.
    # Canonical decompose title: "# Story 1.01: [DEV] Scaffold"
    # The prefix is after ":" — extract from _preamble source or file title.
    if not story_type:
        # Try extracting from the raw content/file title
        raw_title = ""
        if _content is not None:
            for cline in _content.splitlines():
                cs = cline.strip()
                if cs.startswith("# "):
                    raw_title = cs[2:].strip()
                    break
        else:
            raw_title = _extract_title_from_file(story_path)
        # Match [PREFIX] anywhere in the title (handles "Story 1.01: [DEV] ...")
        m = re.search(r"\[(\w+)\]", raw_title)
        story_type = m.group(1) if m else ""

    is_docs = story_type.upper() == "DOCS"

    parts: list[str] = []

    # User Story section — decompose template places the user story
    # directly after the # title (no ## User Story heading), so it ends
    # up in _preamble. Wrap it in ## User Story for the Jira description.
    user_story = sections.get("User Story", "") or sections.get("_preamble", "")
    if user_story:
        parts.extend(["## User Story", "", user_story, ""])

    # Acceptance Criteria
    ac = sections.get("Acceptance Criteria", "")
    if ac:
        parts.extend(["## Acceptance Criteria", "", ac, ""])

    if is_docs:
        doc_scope = sections.get("Documentation Scope", "")
        if doc_scope:
            parts.extend(["## Documentation Scope", "", doc_scope, ""])
        doc_inputs = sections.get("Documentation Inputs", "")
        if doc_inputs:
            parts.extend(["## Documentation Inputs", "", doc_inputs, ""])
    else:
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

    # Design Reference — preserve body fields and merge in provided links.
    # The canonical decompose template includes a Design Reference section
    # with Epic, PRD Requirements, Design section, Interface Changes, and
    # Validated by, but NO design document URL.  The caller provides the
    # URL via design_doc_link; merge it at the top of the section.
    design_ref = sections.get("Design Reference", "")
    if design_ref:
        ref_lines = ["## Design Reference", ""]
        # Insert design document link at top if provided and not already present
        if design_doc_link and "Design document:" not in design_ref:
            ref_lines.append(f"Design document: {design_doc_link}")
        # Merge epic_jira_key: replace local "Epic: Epic N — title" with Jira key
        if epic_jira_key:
            updated_ref = re.sub(
                r"^(Epic:\s*)Epic \d+.*$",
                rf"\g<1>{epic_jira_key}",
                design_ref,
                flags=re.MULTILINE,
            )
            ref_lines.append(updated_ref)
        else:
            ref_lines.append(design_ref)
        parts.extend(ref_lines)
    else:
        ref_parts = [
            "## Design Reference", "",
            f"Design document: {design_doc_link}" if design_doc_link else "Design document:",
            f"Epic: {epic_jira_key}" if epic_jira_key else "Epic:",
        ]
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
# Prepare (snapshot-consistent hash + description)
# ---------------------------------------------------------------------------

def prepare(
    artifact_path: str | Path,
    manifest_path: str | Path,
    item_type: str,
    design_doc_link: str = "",
    feature_key: str = "",
    epic_jira_key: str = "",
    story_type: str = "",
) -> dict[str, str]:
    """Read a file once and return its hash, rendered description, and metadata.

    Guarantees that ``content_hash`` corresponds to exactly the content
    used to produce ``description``.  The caller should pass this hash
    to ``update-manifest`` after a successful Jira write.

    Returns a dict with:
    - ``content_hash``: SHA-256 of the raw file bytes
    - ``description``: rendered Jira-ready description
    - ``title``: raw artifact title (from ``# ...`` heading)
    - ``summary``: Jira-ready summary field (epic title without
      numbering; story ``[PREFIX] title`` without numbering)
    - ``size``: T-Shirt size (epics only)
    - ``story_type``: detected prefix like ``DEV``, ``DOCS`` (stories)
    - ``dependencies``: raw Dependencies section text with refs resolved

    The caller uses ``summary`` as the Jira Summary field and all other
    metadata directly from this output — no re-reading the file.
    """
    artifact_path = Path(artifact_path)
    raw_bytes = artifact_path.read_bytes()
    content_hash = _hash_bytes(raw_bytes)
    content_text = raw_bytes.decode("utf-8")

    manifest = load_manifest(manifest_path)
    sections = _extract_sections_from_text(content_text)

    # Extract raw title from snapshot
    raw_title = ""
    for cline in content_text.splitlines():
        cs = cline.strip()
        if cs.startswith("# "):
            raw_title = cs[2:].strip()
            break

    result: dict[str, str] = {
        "content_hash": content_hash,
        "title": raw_title,
    }

    if item_type == "epic":
        # Validate essential epic sections
        if not sections.get("Summary", "").strip():
            fail(f"Epic artifact missing required Summary section: "
                 f"{artifact_path}")
        if not sections.get("Acceptance Criteria", "").strip():
            fail(f"Epic artifact missing required Acceptance Criteria "
                 f"section: {artifact_path}")

        description = render_epic_description(
            artifact_path, manifest,
            design_doc_link=design_doc_link,
            feature_key=feature_key,
            _content=content_text,
        )
        # Jira summary: strip "Epic N " or "Epic N: " prefix
        jira_summary = re.sub(r"^Epic\s+\d+[:\s]*", "", raw_title).strip()
        result["summary"] = jira_summary

        # Extract T-Shirt Size from preamble
        preamble = sections.get("_preamble", "")
        size_match = re.search(r"\*\*T-Shirt Size:\*\*\s*(\S+)", preamble)
        if size_match:
            result["size"] = size_match.group(1)
    else:
        # Detect story type from title
        detected_type = story_type
        if not detected_type:
            m = re.search(r"\[(\w+)\]", raw_title)
            detected_type = m.group(1) if m else ""
        result["story_type"] = detected_type

        is_docs = detected_type.upper() == "DOCS"

        # Validate essential story sections
        has_user_story = (sections.get("User Story", "").strip()
                          or sections.get("_preamble", "").strip())
        if not has_user_story:
            fail(f"Story artifact missing required User Story content: "
                 f"{artifact_path}")
        if not sections.get("Acceptance Criteria", "").strip():
            fail(f"Story artifact missing required Acceptance Criteria "
                 f"section: {artifact_path}")
        if is_docs and not sections.get("Documentation Scope", "").strip():
            fail(f"DOCS story missing required Documentation Scope "
                 f"section: {artifact_path}")

        description = render_story_description(
            artifact_path, manifest,
            design_doc_link=design_doc_link,
            epic_jira_key=epic_jira_key,
            story_type=detected_type,
            _content=content_text,
        )

        # Jira summary: "[PREFIX] title" — strip "Story N.NN: " prefix
        jira_summary = re.sub(r"^Story\s+\d+\.\d+:\s*", "", raw_title).strip()
        result["summary"] = jira_summary

        # Dependencies text with refs resolved (for issue links)
        deps_text = sections.get("Dependencies", "")
        if deps_text and manifest:
            deps_text = resolve_refs(deps_text, manifest)
        result["dependencies"] = deps_text

    result["description"] = description
    return result


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
    epic_file: str = "",
    feature_key: str = "",
) -> dict[str, Any]:
    """Record a single successful Jira operation in the manifest.

    This is the per-item checkpoint: called only after a Jira operation
    succeeds.  The ``content_hash`` must be the hash of the file content
    that was actually submitted to Jira, not a freshly recomputed hash
    that might reflect subsequent edits.

    ``operation`` must be one of: ``create``, ``update``, ``close``.
    ``item_type`` must be ``epic`` or ``story``.
    ``epic_file`` is required for story operations to ensure correct
    placement under the right parent epic.
    ``feature_key`` is recorded on manifest creation and preserved on
    subsequent calls.
    ``content_hash`` may be empty for orphan closures (no file on disk).
    """
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)

    if manifest is None:
        manifest = {
            "schema_version": 2,
            "feature_key": feature_key or "",
            "synced_at": "",
            "epics": [],
        }

    # Ensure v2
    manifest["schema_version"] = 2

    # Set feature_key on first call; preserve on subsequent calls
    if feature_key and not manifest.get("feature_key"):
        manifest["feature_key"] = feature_key
    elif feature_key and manifest.get("feature_key") != feature_key:
        # Feature key conflict — preserve existing, warn
        info(f"Feature key mismatch: manifest has '{manifest['feature_key']}', "
             f"caller passed '{feature_key}'. Keeping existing.")

    synced_status = "closed" if operation == "close" else "active"

    if item_type == "epic":
        _update_manifest_epic(
            manifest, artifact_file, jira_key, content_hash,
            synced_status, title, size,
        )
    elif item_type == "story":
        if not epic_file:
            fail("--epic-file is required for story operations to ensure "
                 "correct parent placement.")
        _update_manifest_story_under_epic(
            manifest, artifact_file, jira_key, content_hash,
            synced_status, title, epic_file,
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


def _update_manifest_story_under_epic(
    manifest: dict[str, Any],
    story_file: str,
    jira_key: str,
    content_hash: str,
    synced_status: str,
    title: str,
    epic_file: str,
) -> None:
    """Update or insert a story entry under a specific epic.

    Fails if the specified epic is not found in the manifest.
    """
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
    fail(f"Cannot record story '{story_file}': parent epic '{epic_file}' "
         f"not found in manifest. Ensure the epic is recorded first.")


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

    # prepare
    p_prepare = sub.add_parser(
        "prepare",
        help="Compute hash and render description from a single file read.",
    )
    p_prepare.add_argument("artifact_file", help="Path to the artifact .md file.")
    p_prepare.add_argument("manifest_path", help="Path to sync-manifest.json.")
    p_prepare.add_argument(
        "--type", choices=["epic", "story"], required=True,
        help="Whether to render an epic or story description.",
    )
    p_prepare.add_argument("--design-doc-link", default="", help="Link to design doc.")
    p_prepare.add_argument("--feature-key", default="", help="Feature issue key.")
    p_prepare.add_argument("--epic-jira-key", default="", help="Epic Jira key (stories only).")
    p_prepare.add_argument("--story-type", default="", help="Story prefix (DEV, UI, etc.).")

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
                          help="SHA-256 hash of the submitted content. "
                               "Use empty string for orphan closures.")
    p_update.add_argument("--item-type", choices=["epic", "story"], default="epic")
    p_update.add_argument("--title", default="")
    p_update.add_argument("--size", default="")
    p_update.add_argument("--epic-file", default="",
                          help="Parent epic filename (required for stories).")
    p_update.add_argument("--feature-key", default="",
                          help="Feature issue key (recorded on first call).")

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

    elif args.command == "prepare":
        result = prepare(
            args.artifact_file,
            args.manifest_path,
            args.type,
            design_doc_link=args.design_doc_link,
            feature_key=args.feature_key,
            epic_jira_key=args.epic_jira_key,
            story_type=args.story_type,
        )
        json.dump(result, sys.stdout, indent=2)
        print()
        return EXIT_SUCCESS

    elif args.command == "update-manifest":
        update_manifest(
            args.manifest_path,
            args.operation,
            args.artifact_file,
            args.jira_key,
            args.content_hash,
            item_type=args.item_type,
            title=args.title,
            size=args.size,
            epic_file=args.epic_file,
            feature_key=args.feature_key,
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
