#!/usr/bin/env python3
"""Deterministic validation artifact index operations for the design workflow.

Provides reusable subcommands for managing the validation-index.json
contract across the design workflow lifecycle.  Each subcommand handles
one discrete, deterministic operation — the calling skill file retains
ownership of AI-dependent work (testplan content generation, user
confirmation prompts, PR feedback routing).

Subcommands:
  validate      Validate a local or published validation-index.json
  resolve       Resolve validation artifacts from a directory
  transform     Transform a local index into the published docs-repo format
  diff          Compute added/removed/unchanged artifacts between two indexes
  build-legacy  Build a local index from a directory with only 04-testplan.md

Usage:
  validation_index.py validate --local PATH [--artifact-dir DIR]
  validation_index.py validate --published PATH [--feature-dir DIR]
  validation_index.py resolve --local DIR
  validation_index.py resolve --published DIR
  validation_index.py transform LOCAL_INDEX OUTPUT
  validation_index.py diff OLD_INDEX NEW_INDEX
  validation_index.py build-legacy DIR OUTPUT

Exit codes:
  0 -- success (resolve: JSON array, may be empty []; other cmds: ok)
  1 -- error (malformed data, missing listed files, I/O failure)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

SCHEMA_VERSION = "1.0"
VALID_TYPES = {"testplan", "companion"}

# Filenames that must never appear as validation artifact names —
# they are reserved for other workflow state/output files.
RESERVED_FILENAMES = frozenset({
    "design.md", "prd.md", "validation-index.json",
    "publish-metadata.json", "config.json", "provenance.json",
    "sync-manifest.json",
})

# Pattern for safe filenames: lowercase alphanumeric + hyphens, with extension
_SAFE_FILENAME_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]*\.[a-z0-9]+$"
)
# Local artifact filenames follow 04-{slug}.md convention
_LOCAL_FILENAME_RE = re.compile(
    r"^04-[a-z][a-z0-9-]*\.md$"
)


class ValidationIndexError(Exception):
    """Raised when a validation index is malformed or unsafe."""


# ---------------------------------------------------------------------------
# CLI helpers (match publish.py pattern)
# ---------------------------------------------------------------------------

def fail(msg: str, code: int = 1) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def safe_filename(name: Any, context: str = "filename") -> list[str]:
    """Validate that a value is a safe, plain filename.

    Returns a list of error messages (empty = safe).
    Rejects: non-strings, empty, absolute paths, traversal (..),
    slashes, reserved names, null bytes, control characters.
    """
    errors: list[str] = []
    if not isinstance(name, str):
        errors.append(f"{context}: must be a string, got {type(name).__name__}")
        return errors
    if not name:
        errors.append(f"{context}: must be non-empty")
        return errors
    if name != name.strip():
        errors.append(f"{context}: must not have leading/trailing whitespace")
    # Null bytes and control characters
    if "\x00" in name or any(ord(c) < 32 for c in name):
        errors.append(f"{context}: control characters not allowed: {name!r}")
    # Path traversal / absolute / slashes
    pp = PurePosixPath(name)
    if pp.is_absolute():
        errors.append(f"{context}: absolute paths not allowed: {name!r}")
    if ".." in pp.parts:
        errors.append(f"{context}: path traversal not allowed: {name!r}")
    if "/" in name or "\\" in name:
        errors.append(
            f"{context}: directory separators not allowed: {name!r}")
    # Reserved names
    if name.lower() in RESERVED_FILENAMES:
        errors.append(f"{context}: reserved filename: {name!r}")
    # Format: lowercase alphanumeric with hyphens and extension
    if not _SAFE_FILENAME_RE.match(name):
        errors.append(
            f"{context}: must be lowercase alphanumeric with "
            f"extension: {name!r}")
    return errors


def _reject_symlinks(path: Path, context: str = "path") -> list[str]:
    """Reject symlinks to prevent symlink escape attacks.

    Returns a list of error messages (empty = safe).
    """
    errors: list[str] = []
    if path.is_symlink():
        errors.append(
            f"{context}: symlinks not allowed: {path}")
    return errors


def _check_string_field(
    value: Any, field_name: str, context: str,
) -> list[str]:
    """Validate that a field is a non-empty string (not dict/list)."""
    errors: list[str] = []
    if isinstance(value, (dict, list)):
        errors.append(
            f"{context}.{field_name}: must be a string, "
            f"got {type(value).__name__}")
    elif not isinstance(value, str):
        errors.append(
            f"{context}.{field_name}: must be a string, "
            f"got {type(value).__name__}")
    elif not value.strip():
        errors.append(f"{context}.{field_name}: must be non-empty")
    return errors


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_local_index(data: dict[str, Any]) -> list[str]:
    """Validate a local validation-index.json.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["index must be a JSON object"]

    # Schema version — fail closed on unsupported
    sv = data.get("schema_version")
    errs = _check_string_field(sv, "schema_version", "index")
    if errs:
        errors.extend(errs)
    elif sv != SCHEMA_VERSION:
        errors.append(
            f"unsupported schema_version: {sv!r} "
            f"(expected '{SCHEMA_VERSION}')")

    # Primary testplan
    primary = data.get("primary_testplan")
    errs = _check_string_field(primary, "primary_testplan", "index")
    if errs:
        errors.extend(errs)

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) == 0:
        errors.append("artifacts must be a non-empty array")
        return errors

    # First entry must be the primary testplan
    first = artifacts[0]
    if isinstance(first, dict):
        if first.get("type") != "testplan":
            errors.append("first artifact must have type 'testplan'")
        if isinstance(primary, str) and first.get("local") != primary:
            errors.append(
                "first artifact 'local' must match primary_testplan")

    seen_locals: set[str] = set()
    seen_published: set[str] = set()
    testplan_count = 0

    for i, art in enumerate(artifacts):
        ctx = f"artifacts[{i}]"
        if not isinstance(art, dict):
            errors.append(f"{ctx} must be an object")
            continue

        # --- local filename ---
        local = art.get("local")
        local_errs = _check_string_field(local, "local", ctx)
        if local_errs:
            errors.extend(local_errs)
        else:
            errors.extend(safe_filename(local, f"{ctx}.local"))
            if not _LOCAL_FILENAME_RE.match(local):
                errors.append(
                    f"{ctx}.local: must match 04-{{slug}}.md "
                    f"convention: {local!r}")
            if local in seen_locals:
                errors.append(f"duplicate local filename: {local}")
            else:
                seen_locals.add(local)

        # --- published_as filename ---
        pub = art.get("published_as")
        pub_errs = _check_string_field(pub, "published_as", ctx)
        if pub_errs:
            errors.extend(pub_errs)
        else:
            errors.extend(safe_filename(pub, f"{ctx}.published_as"))
            if pub in seen_published:
                errors.append(f"duplicate published_as filename: {pub}")
            else:
                seen_published.add(pub)

        # --- type ---
        art_type = art.get("type")
        type_errs = _check_string_field(art_type, "type", ctx)
        if type_errs:
            errors.extend(type_errs)
        elif art_type not in VALID_TYPES:
            errors.append(
                f"{ctx}.type must be one of {sorted(VALID_TYPES)}, "
                f"got {art_type!r}")

        if art_type == "testplan":
            testplan_count += 1

        if art_type == "companion":
            # purpose and audience required
            for field in ("purpose", "audience"):
                val = art.get(field)
                f_errs = _check_string_field(val, field, ctx)
                if f_errs:
                    errors.extend(f_errs)

            # Companion slug must not be 'testplan'
            if isinstance(local, str) and local:
                slug = local.replace("04-", "").replace(".md", "")
                if slug == "testplan":
                    errors.append(
                        f"{ctx}: companion slug must not be 'testplan'")

            # Companion must not claim the primary published filename
            if isinstance(pub, str) and pub == "testplan.md":
                errors.append(
                    f"{ctx}.published_as: testplan.md is reserved "
                    "for the primary testplan")

    if testplan_count == 0:
        errors.append("exactly one artifact must have type 'testplan'")
    elif testplan_count > 1:
        errors.append(
            f"exactly one artifact may have type 'testplan', "
            f"found {testplan_count}")

    return errors


def validate_published_index(data: dict[str, Any]) -> list[str]:
    """Validate a published validation-index.json (docs repo format).

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["index must be a JSON object"]

    # Schema version — fail closed
    sv = data.get("schema_version")
    errs = _check_string_field(sv, "schema_version", "index")
    if errs:
        errors.extend(errs)
    elif sv != SCHEMA_VERSION:
        errors.append(
            f"unsupported schema_version: {sv!r} "
            f"(expected '{SCHEMA_VERSION}')")

    primary = data.get("primary_testplan")
    errs = _check_string_field(primary, "primary_testplan", "index")
    if errs:
        errors.extend(errs)

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) == 0:
        errors.append("artifacts must be a non-empty array")
        return errors

    seen_files: set[str] = set()
    testplan_count = 0

    for i, art in enumerate(artifacts):
        ctx = f"artifacts[{i}]"
        if not isinstance(art, dict):
            errors.append(f"{ctx} must be an object")
            continue

        # --- file ---
        f = art.get("file")
        f_errs = _check_string_field(f, "file", ctx)
        if f_errs:
            errors.extend(f_errs)
        else:
            errors.extend(safe_filename(f, f"{ctx}.file"))
            if f in seen_files:
                errors.append(f"duplicate file: {f}")
            else:
                seen_files.add(f)

        # Must NOT have local-only fields
        if "local" in art:
            errors.append(
                f"{ctx}: published index must not have 'local'")
        if "published_as" in art:
            errors.append(
                f"{ctx}: published index must not have 'published_as'")

        # --- type ---
        art_type = art.get("type")
        type_errs = _check_string_field(art_type, "type", ctx)
        if type_errs:
            errors.extend(type_errs)
        elif art_type not in VALID_TYPES:
            errors.append(
                f"{ctx}.type must be one of {sorted(VALID_TYPES)}")

        if art_type == "testplan":
            testplan_count += 1

        if art_type == "companion":
            for field in ("purpose", "audience"):
                val = art.get(field)
                cf_errs = _check_string_field(val, field, ctx)
                if cf_errs:
                    errors.extend(cf_errs)

    # Exactly one testplan
    if testplan_count == 0:
        errors.append("exactly one artifact must have type 'testplan'")
    elif testplan_count > 1:
        errors.append(
            f"exactly one artifact may have type 'testplan', "
            f"found {testplan_count}")

    # First artifact must be the testplan
    if artifacts and isinstance(artifacts[0], dict):
        if artifacts[0].get("type") != "testplan":
            errors.append("first artifact must have type 'testplan'")
        first_file = artifacts[0].get("file")
        if isinstance(primary, str) and first_file != primary:
            errors.append(
                "primary_testplan must match first artifact's file")

    return errors


# ---------------------------------------------------------------------------
# Transform local -> published
# ---------------------------------------------------------------------------

def transform_for_publish(local_index: dict[str, Any]) -> dict[str, Any]:
    """Transform a local index into the published docs-repo format.

    Replaces local/published_as with file, updates primary_testplan.
    Raises ValidationIndexError if the local index is invalid.
    """
    errors = validate_local_index(local_index)
    if errors:
        raise ValidationIndexError(
            f"cannot transform invalid index: {'; '.join(errors)}")

    primary_local = local_index["primary_testplan"]
    primary_published = None
    published_artifacts = []

    for art in local_index["artifacts"]:
        entry: dict[str, Any] = {
            "file": art["published_as"],
            "type": art["type"],
        }
        if art["type"] == "companion":
            if art.get("purpose"):
                entry["purpose"] = art["purpose"]
            if art.get("audience"):
                entry["audience"] = art["audience"]
        if art["local"] == primary_local:
            primary_published = art["published_as"]
        published_artifacts.append(entry)

    return {
        "schema_version": SCHEMA_VERSION,
        "primary_testplan": primary_published,
        "artifacts": published_artifacts,
    }


# ---------------------------------------------------------------------------
# Diff: compare two published indexes
# ---------------------------------------------------------------------------

def diff_published(
    old: dict[str, Any], new: dict[str, Any],
) -> dict[str, list[str]]:
    """Compare two published indexes and return added/removed/unchanged.

    Returns {"added": [...], "removed": [...], "unchanged": [...]}.
    Files are identified by published filename.
    """
    old_files: set[str] = set()
    new_files: set[str] = set()

    if isinstance(old.get("artifacts"), list):
        for a in old["artifacts"]:
            if isinstance(a, dict) and isinstance(a.get("file"), str):
                old_files.add(a["file"])

    if isinstance(new.get("artifacts"), list):
        for a in new["artifacts"]:
            if isinstance(a, dict) and isinstance(a.get("file"), str):
                new_files.add(a["file"])

    return {
        "added": sorted(new_files - old_files),
        "removed": sorted(old_files - new_files),
        "unchanged": sorted(old_files & new_files),
    }


# ---------------------------------------------------------------------------
# Resolution: find artifacts from filesystem
# ---------------------------------------------------------------------------

def resolve_artifacts(artifact_dir: Path) -> list[dict[str, Any]]:
    """Resolve validation artifacts from a local artifact directory.

    Reads validation-index.json if present (validates, fails closed on
    malformed).  Falls back to 04-testplan.md for legacy designs.
    Returns a list of artifact entries (local index format).
    Returns empty list if no artifacts found.

    Raises ValidationIndexError on malformed index, missing listed
    files, or symlink artifacts (symlinks are rejected to prevent
    escape attacks).
    """
    index_path = artifact_dir / "validation-index.json"
    # Check for dangling symlinks and directories BEFORE is_file —
    # is_file returns False for both, which would silently fall through
    # to legacy behavior instead of failing closed.
    if index_path.is_symlink():
        raise ValidationIndexError(
            "validation-index.json is a symlink (not allowed)")
    if index_path.exists() and not index_path.is_file():
        raise ValidationIndexError(
            "validation-index.json exists but is not a regular file")
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValidationIndexError(
                f"cannot read validation-index.json: {exc}") from exc
        errors = validate_local_index(data)
        if errors:
            raise ValidationIndexError(
                f"invalid validation-index.json: {'; '.join(errors)}")
        # Verify listed files exist and are not symlinks.
        # Check is_symlink BEFORE is_file — is_file follows symlinks
        # and returns True for a symlink pointing to a regular file.
        missing = []
        for art in data["artifacts"]:
            local = art.get("local", "")
            art_path = artifact_dir / local
            if art_path.is_symlink():
                raise ValidationIndexError(
                    f"artifact is a symlink (not allowed): {local}")
            if not art_path.is_file():
                missing.append(local)
        if missing:
            raise ValidationIndexError(
                f"listed artifacts not found on disk: "
                f"{', '.join(missing)}")
        return data["artifacts"]

    # Legacy fallback: single 04-testplan.md
    legacy = artifact_dir / "04-testplan.md"
    if legacy.is_symlink():
        raise ValidationIndexError(
            "04-testplan.md is a symlink (not allowed)")
    if legacy.is_file():
        return [{
            "local": "04-testplan.md",
            "published_as": "testplan.md",
            "type": "testplan",
        }]

    return []


def resolve_published_artifacts(
    feature_dir: Path,
) -> list[dict[str, Any]]:
    """Resolve validation artifacts from a published docs-repo directory.

    Reads validation-index.json if present (validates, fails closed on
    malformed).  Falls back to testplan.md for legacy designs.
    Returns a list of artifact entries (published index format).
    Returns empty list if no artifacts found.

    Raises ValidationIndexError on malformed index, missing listed
    files, or symlink artifacts.
    """
    index_path = feature_dir / "validation-index.json"
    # Check dangling symlinks/directories BEFORE is_file
    if index_path.is_symlink():
        raise ValidationIndexError(
            "published validation-index.json is a symlink (not allowed)")
    if index_path.exists() and not index_path.is_file():
        raise ValidationIndexError(
            "published validation-index.json exists but is not "
            "a regular file")
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValidationIndexError(
                f"cannot read published validation-index.json: "
                f"{exc}") from exc
        errors = validate_published_index(data)
        if errors:
            raise ValidationIndexError(
                f"invalid published validation-index.json: "
                f"{'; '.join(errors)}")
        # Verify listed files exist and are not symlinks
        missing = []
        for art in data["artifacts"]:
            fname = art.get("file", "")
            art_path = feature_dir / fname
            if art_path.is_symlink():
                raise ValidationIndexError(
                    f"published artifact is a symlink "
                    f"(not allowed): {fname}")
            if not art_path.is_file():
                missing.append(fname)
        if missing:
            raise ValidationIndexError(
                f"listed published artifacts not found on disk: "
                f"{', '.join(missing)}")
        return data["artifacts"]

    # Legacy fallback: single testplan.md
    legacy = feature_dir / "testplan.md"
    if legacy.is_symlink():
        raise ValidationIndexError(
            "published testplan.md is a symlink (not allowed)")
    if legacy.is_file():
        return [{"file": "testplan.md", "type": "testplan"}]

    return []


def primary_testplan_path(
    feature_dir: Path,
) -> Path | None:
    """Return the path to the primary testplan in a docs-repo directory.

    Validates the index when present — fails closed on malformed.
    Returns None if no validation artifacts are found (no index and
    no legacy testplan.md).

    Raises ValidationIndexError if the index lists a primary testplan
    that does not exist on disk or is a symlink — this indicates a
    corrupted published state, not an absent testplan.
    """
    index_path = feature_dir / "validation-index.json"
    # Check dangling symlinks/directories BEFORE is_file
    if index_path.is_symlink():
        raise ValidationIndexError(
            "validation-index.json is a symlink (not allowed)")
    if index_path.exists() and not index_path.is_file():
        raise ValidationIndexError(
            "validation-index.json exists but is not a regular file")
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValidationIndexError(
                f"cannot read validation-index.json: {exc}") from exc
        errors = validate_published_index(data)
        if errors:
            raise ValidationIndexError(
                f"invalid published validation-index.json: "
                f"{'; '.join(errors)}")
        primary = data.get("primary_testplan")
        if isinstance(primary, str) and primary:
            p = feature_dir / primary
            if p.is_symlink():
                raise ValidationIndexError(
                    f"primary testplan is a symlink "
                    f"(not allowed): {primary}")
            if not p.is_file():
                raise ValidationIndexError(
                    f"primary testplan listed in index but not "
                    f"found on disk: {primary}")
            return p
        return None

    legacy = feature_dir / "testplan.md"
    if legacy.is_symlink():
        raise ValidationIndexError(
            "testplan.md is a symlink (not allowed)")
    if legacy.is_file():
        return legacy
    return None


# ---------------------------------------------------------------------------
# Legacy index builder
# ---------------------------------------------------------------------------

def build_legacy_index(artifact_dir: Path) -> dict[str, Any]:
    """Build a local index for a legacy directory with 04-testplan.md.

    Raises ValidationIndexError if 04-testplan.md does not exist or
    is a symlink.
    """
    tp = artifact_dir / "04-testplan.md"
    if tp.is_symlink():
        raise ValidationIndexError(
            "04-testplan.md is a symlink (not allowed)")
    if not tp.is_file():
        raise ValidationIndexError(
            f"04-testplan.md not found in {artifact_dir}")

    index: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "primary_testplan": "04-testplan.md",
        "artifacts": [{
            "local": "04-testplan.md",
            "published_as": "testplan.md",
            "type": "testplan",
        }],
    }
    # Self-check
    errors = validate_local_index(index)
    if errors:  # pragma: no cover — defensive
        raise ValidationIndexError(
            f"generated legacy index is invalid: {'; '.join(errors)}")
    return index


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def build_metadata_artifacts(
    local_index: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the validation_artifacts list for publish-metadata.json.

    Uses the published format (file, type, purpose, audience).
    """
    published = transform_for_publish(local_index)
    return published["artifacts"]


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a local or published validation-index.json."""
    path = Path(args.local or args.published)
    if path.is_symlink():
        print(f"ERROR: index is a symlink (not allowed): {path}",
              file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    if args.local:
        errors = validate_local_index(data)
        # Optionally check files exist on disk and reject symlinks
        if not errors and args.artifact_dir:
            adir = Path(args.artifact_dir)
            for art in data.get("artifacts", []):
                local = art.get("local", "")
                art_path = adir / local
                if art_path.is_symlink():
                    errors.append(f"symlink not allowed: {local}")
                elif not art_path.is_file():
                    errors.append(f"file not found: {local}")
    else:
        errors = validate_published_index(data)
        if not errors and args.feature_dir:
            fdir = Path(args.feature_dir)
            for art in data.get("artifacts", []):
                fname = art.get("file", "")
                art_path = fdir / fname
                if art_path.is_symlink():
                    errors.append(f"symlink not allowed: {fname}")
                elif not art_path.is_file():
                    errors.append(f"file not found: {fname}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("PASS: validation-index.json is valid")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Resolve validation artifacts from a directory.

    Exit 0 with JSON array (may be empty []) on success.
    Exit 1 on error (malformed index, missing listed files, etc.).
    Callers distinguish empty-success from error by exit code.
    """
    d = Path(args.local or args.published)
    if not d.is_dir():
        print(f"ERROR: directory not found: {d}", file=sys.stderr)
        return 1

    try:
        if args.local:
            arts = resolve_artifacts(d)
        else:
            arts = resolve_published_artifacts(d)
    except ValidationIndexError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(arts, indent=2))
    return 0


def _safe_write_output(dst: Path, content: str,
                       *, trusted_base: Path | None = None) -> int:
    """Write content to dst with symlink and error protection.

    Returns 0 on success, 1 on error (with message printed).

    When *trusted_base* is given (e.g. the operator-configured docs
    repo root or project repo root), the ancestor walk uses **lexical**
    path comparison to determine the boundary.  Components *at* the
    base or *above* it are operator-trusted and not checked for
    symlinks.  Symlink components strictly **below** the base are
    always rejected — even when they resolve back to the base itself
    (e.g. ``base/selflink → base``).  A resolved-destination
    containment check also rejects paths that escape the base via
    symlinks pointing outside it.  OS-level aliases above the base
    (e.g. ``/home`` → ``/var/home``) are tolerated because the walk
    never reaches them.  Without *trusted_base*, every ancestor up to
    the filesystem root is checked (strict default).

    Safety checks:
    - Rejects symlink at the final destination path.
    - Walks ancestors of dst from dst.parent upward (to
      *trusted_base* or the filesystem root) using lexical boundary.
    - Uses O_CREAT|O_WRONLY|O_TRUNC with O_NOFOLLOW to reject a
      symlink final target at open time.
    """
    import os

    # Reject symlink at the destination itself
    if dst.is_symlink():
        print(f"ERROR: output path is a symlink: {dst}",
              file=sys.stderr)
        return 1

    # Walk ancestors checking for symlinks.
    # When trusted_base is given, use LEXICAL path comparison to
    # determine the boundary — not resolved identity of each
    # component.  This prevents a symlink below the base that
    # resolves back to the base from bypassing the check (e.g.
    # base/selflink → base would pass resolved-identity but is
    # caught by lexical "selflink is below base").
    # A resolved containment check catches escapes via symlinks
    # pointing outside the base.
    # Without trusted_base, walk to the filesystem root.
    try:
        if trusted_base is not None:
            resolved_base = trusted_base.resolve()
            try:
                dst.resolve().relative_to(resolved_base)
            except ValueError:
                print(f"ERROR: output path escapes trusted base: "
                      f"{dst} is not under {trusted_base}",
                      file=sys.stderr)
                return 1

        cur = dst.parent
        while True:
            if trusted_base is not None:
                # Lexical boundary: is cur strictly below the base?
                # Components at or above the base are trusted by the
                # operator and not checked for symlinks.
                try:
                    rel = cur.relative_to(trusted_base)
                except ValueError:
                    break  # above the trusted base — trusted
                if rel == Path('.'):
                    break  # at the base itself — trusted
                # Below the base: reject any symlink component
                if cur.is_symlink():
                    print(f"ERROR: output parent contains symlink: "
                          f"{cur}", file=sys.stderr)
                    return 1
            else:
                if cur.is_symlink():
                    print(f"ERROR: output parent contains symlink: "
                          f"{cur}", file=sys.stderr)
                    return 1
            next_cur = cur.parent
            if next_cur == cur:
                break  # filesystem root
            cur = next_cur
    except OSError as exc:
        print(f"ERROR: cannot check output path: {exc}",
              file=sys.stderr)
        return 1

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: cannot create parent directory {dst.parent}: "
              f"{exc}", file=sys.stderr)
        return 1

    # Open with O_NOFOLLOW to reject a symlink final target.
    try:
        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(dst), flags, 0o644)
        try:
            data = content.encode("utf-8")
            written = 0
            while written < len(data):
                n = os.write(fd, data[written:])
                if n == 0:
                    raise OSError("write returned 0 bytes")
                written += n
        finally:
            os.close(fd)
    except OSError as exc:
        print(f"ERROR: cannot write {dst}: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_transform(args: argparse.Namespace) -> int:
    """Transform a local index to published format."""
    src = Path(args.local_index)
    dst = Path(args.output)

    if src.is_symlink():
        print(f"ERROR: input is a symlink: {src}", file=sys.stderr)
        return 1
    if not src.is_file():
        print(f"ERROR: file not found: {src}", file=sys.stderr)
        return 1

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        published = transform_for_publish(data)
    except (json.JSONDecodeError, ValidationIndexError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    trusted = None
    if getattr(args, 'trusted_output_base', None):
        trusted = Path(args.trusted_output_base)

    rc = _safe_write_output(dst,
                            json.dumps(published, indent=2) + "\n",
                            trusted_base=trusted)
    if rc != 0:
        return rc
    print(f"Wrote published index: {dst}")
    return 0


def _is_intentionally_empty(data: dict[str, Any]) -> bool:
    """Check if data represents an intentionally empty published index.

    An intentionally empty index is used for the first-publish case
    where no previous published set exists.  Recognized forms:
    - ``{}`` — empty dict (no artifacts key)
    - ``{"artifacts": []}`` — explicit empty artifact list
    These bypass full schema validation so cmd_diff can compute a
    meaningful "all added" result against an empty prior state.
    """
    if not isinstance(data, dict):
        return False
    keys = set(data.keys())
    if keys == set():
        return True
    if keys <= {"artifacts"} and data.get("artifacts") == []:
        return True
    return False


def cmd_diff(args: argparse.Namespace) -> int:
    """Compute artifact diff between two published indexes.

    Validates both inputs fully as published indexes before diffing.
    An intentionally empty prior index (``{}`` or ``{"artifacts": []}``)
    is allowed to support the first-publish diff case.
    Rejects malformed schema, local-format fields, null/non-string
    filenames, and unsafe filenames.
    """
    old_path = Path(args.old_index)
    new_path = Path(args.new_index)

    for p in (old_path, new_path):
        if not p.is_file():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 1

    try:
        old = json.loads(old_path.read_text(encoding="utf-8"))
        new = json.loads(new_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Validate both inputs — intentionally empty old is allowed
    for label, data in [("old", old), ("new", new)]:
        if not isinstance(data, dict):
            print(f"ERROR: {label} index must be a JSON object",
                  file=sys.stderr)
            return 1
        # Allow an intentionally empty old index (first-publish case).
        # An empty NEW index must fail schema validation — it would
        # cause diff_published to report all old artifacts as removed.
        if label == "old" and _is_intentionally_empty(data):
            continue
        # Full published-schema validation
        errors = validate_published_index(data)
        if errors:
            for e in errors:
                print(f"ERROR: {label}: {e}", file=sys.stderr)
            return 1

    result = diff_published(old, new)
    print(json.dumps(result, indent=2))
    return 0


def cmd_build_legacy(args: argparse.Namespace) -> int:
    """Build a local index from a legacy directory."""
    d = Path(args.dir)
    dst = Path(args.output)

    if not d.is_dir():
        print(f"ERROR: directory not found: {d}", file=sys.stderr)
        return 1

    try:
        index = build_legacy_index(d)
    except ValidationIndexError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    trusted = None
    if getattr(args, 'trusted_output_base', None):
        trusted = Path(args.trusted_output_base)

    rc = _safe_write_output(dst,
                            json.dumps(index, indent=2) + "\n",
                            trusted_base=trusted)
    if rc != 0:
        return rc
    print(f"Wrote legacy index: {dst}")
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

SUBCOMMAND_MAP = {
    "validate": cmd_validate,
    "resolve": cmd_resolve,
    "transform": cmd_transform,
    "diff": cmd_diff,
    "build-legacy": cmd_build_legacy,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="validation_index.py",
        description="Validation artifact index operations",
    )
    sub = parser.add_subparsers(dest="subcommand")

    # --- validate ---
    p_val = sub.add_parser("validate",
                           help="Validate a validation-index.json")
    val_group = p_val.add_mutually_exclusive_group(required=True)
    val_group.add_argument("--local", metavar="PATH",
                           help="Path to local index file")
    val_group.add_argument("--published", metavar="PATH",
                           help="Path to published index file")
    p_val.add_argument("--artifact-dir", metavar="DIR",
                       help="Check local files exist in this directory")
    p_val.add_argument("--feature-dir", metavar="DIR",
                       help="Check published files exist in this directory")

    # --- resolve ---
    p_res = sub.add_parser("resolve",
                           help="Resolve artifacts from a directory")
    res_group = p_res.add_mutually_exclusive_group(required=True)
    res_group.add_argument("--local", metavar="DIR",
                           help="Resolve from local artifact directory")
    res_group.add_argument("--published", metavar="DIR",
                           help="Resolve from published docs-repo directory")

    # --- transform ---
    p_tx = sub.add_parser("transform",
                          help="Transform local index to published format")
    p_tx.add_argument("local_index", help="Path to local index file")
    p_tx.add_argument("output", help="Output path for published index")
    p_tx.add_argument("--trusted-output-base", metavar="DIR",
                      help="Trusted output root (e.g., docs repo). "
                           "Symlinks above this base are permitted.")

    # --- diff ---
    p_diff = sub.add_parser("diff",
                            help="Diff two published indexes")
    p_diff.add_argument("old_index", help="Previous published index")
    p_diff.add_argument("new_index", help="Current published index")

    # --- build-legacy ---
    p_leg = sub.add_parser("build-legacy",
                           help="Build local index from legacy directory")
    p_leg.add_argument("dir", help="Directory containing 04-testplan.md")
    p_leg.add_argument("output", help="Output path for local index")
    p_leg.add_argument("--trusted-output-base", metavar="DIR",
                       help="Trusted output root (e.g., project repo). "
                            "Symlinks above this base are permitted.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return 1

    handler = SUBCOMMAND_MAP.get(args.subcommand)
    if handler is None:
        fail(f"Unknown subcommand: {args.subcommand}")

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
