#!/usr/bin/env python3
"""Validation artifact index operations for the design workflow.

This module encodes the validation-index.json contract used by:
- /draft (producer): writes the local index after generating testplan(s)
- /publish (producer): transforms and publishes the index to the docs repo
- /respond, /revise (consumer): reads the index to discover artifacts
- /decompose (consumer): reads the index to find all testplan files
- implement /ingest, e2e /ingest (consumer): reads the published index
  in the docs repo to discover validation artifacts for story filtering

The schema and resolution logic here are the single source of truth.
Workflow instructions reference this module's behavior; tests exercise
this module directly.

Schema (validation-index.json):
    {
        "schema_version": "1.0",
        "primary_testplan": "<local-or-published-filename>",
        "artifacts": [
            {
                "local": "<filename>",           # local artifact dir
                "published_as": "<filename>",     # docs repo filename
                "type": "testplan" | "companion",
                "purpose": "<string>",            # companion only
                "audience": "<string>"            # companion only
            }
        ]
    }

Published index (docs repo) replaces "local"/"published_as" with "file":
    {
        "schema_version": "1.0",
        "primary_testplan": "<published-filename>",
        "artifacts": [
            {
                "file": "<published-filename>",
                "type": "testplan" | "companion",
                "purpose": "<string>",            # companion only
                "audience": "<string>"            # companion only
            }
        ]
    }

Usage:
    from validation_index import (
        validate_local_index,
        validate_published_index,
        transform_for_publish,
        resolve_artifacts,
        resolve_published_artifacts,
    )
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
VALID_TYPES = {"testplan", "companion"}


class ValidationIndexError(Exception):
    """Raised when a validation index is malformed."""


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

    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{SCHEMA_VERSION}', got {sv!r}")

    primary = data.get("primary_testplan")
    if not isinstance(primary, str) or not primary:
        errors.append("primary_testplan must be a non-empty string")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) == 0:
        errors.append("artifacts must be a non-empty array")
        return errors

    # First entry must be primary testplan
    first = artifacts[0]
    if isinstance(first, dict):
        if first.get("type") != "testplan":
            errors.append(
                "first artifact must have type 'testplan'")
        if first.get("local") != primary:
            errors.append(
                "first artifact 'local' must match primary_testplan")

    seen_locals: set[str] = set()
    seen_published: set[str] = set()
    seen_tc_types: set[str] = set()

    for i, art in enumerate(artifacts):
        if not isinstance(art, dict):
            errors.append(f"artifacts[{i}] must be an object")
            continue

        local = art.get("local")
        if not isinstance(local, str) or not local:
            errors.append(f"artifacts[{i}].local must be a non-empty string")
        elif local in seen_locals:
            errors.append(f"duplicate local filename: {local}")
        else:
            seen_locals.add(local)

        pub = art.get("published_as")
        if not isinstance(pub, str) or not pub:
            errors.append(
                f"artifacts[{i}].published_as must be a non-empty string")
        elif pub in seen_published:
            errors.append(f"duplicate published_as filename: {pub}")
        else:
            seen_published.add(pub)

        art_type = art.get("type")
        if art_type not in VALID_TYPES:
            errors.append(
                f"artifacts[{i}].type must be one of {VALID_TYPES}, "
                f"got {art_type!r}")

        if art_type == "testplan":
            if "testplan" in seen_tc_types:
                errors.append("only one artifact may have type 'testplan'")
            seen_tc_types.add("testplan")

        if art_type == "companion":
            if not art.get("purpose"):
                errors.append(
                    f"artifacts[{i}]: companion must have 'purpose'")
            if not art.get("audience"):
                errors.append(
                    f"artifacts[{i}]: companion must have 'audience'")

        # Local filenames must not be 'testplan' slug for companions
        if art_type == "companion" and local:
            slug = local.replace("04-", "").replace(".md", "")
            if slug == "testplan":
                errors.append(
                    f"artifacts[{i}]: companion slug must not be 'testplan'")

    return errors


def validate_published_index(data: dict[str, Any]) -> list[str]:
    """Validate a published validation-index.json (docs repo format).

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["index must be a JSON object"]

    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{SCHEMA_VERSION}', got {sv!r}")

    primary = data.get("primary_testplan")
    if not isinstance(primary, str) or not primary:
        errors.append("primary_testplan must be a non-empty string")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) == 0:
        errors.append("artifacts must be a non-empty array")
        return errors

    seen_files: set[str] = set()

    for i, art in enumerate(artifacts):
        if not isinstance(art, dict):
            errors.append(f"artifacts[{i}] must be an object")
            continue

        f = art.get("file")
        if not isinstance(f, str) or not f:
            errors.append(f"artifacts[{i}].file must be a non-empty string")
        elif f in seen_files:
            errors.append(f"duplicate file: {f}")
        else:
            seen_files.add(f)

        # Must NOT have local/published_as (those are local-only fields)
        if "local" in art:
            errors.append(
                f"artifacts[{i}]: published index must not have 'local'")
        if "published_as" in art:
            errors.append(
                f"artifacts[{i}]: published index must not have "
                f"'published_as'")

        art_type = art.get("type")
        if art_type not in VALID_TYPES:
            errors.append(
                f"artifacts[{i}].type must be one of {VALID_TYPES}")

        if art_type == "companion":
            if not art.get("purpose"):
                errors.append(
                    f"artifacts[{i}]: companion must have 'purpose'")

    # primary_testplan must match the first artifact's file
    if artifacts and isinstance(artifacts[0], dict):
        if artifacts[0].get("file") != primary:
            errors.append(
                "primary_testplan must match first artifact's file")

    return errors


# ---------------------------------------------------------------------------
# Transform local -> published
# ---------------------------------------------------------------------------

def transform_for_publish(local_index: dict[str, Any]) -> dict[str, Any]:
    """Transform a local index into the published docs-repo format.

    Replaces local/published_as with file, updates primary_testplan.
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
# Resolution: find artifacts from filesystem
# ---------------------------------------------------------------------------

def resolve_artifacts(artifact_dir: Path) -> list[dict[str, Any]]:
    """Resolve validation artifacts from a local artifact directory.

    Reads validation-index.json if present; falls back to 04-testplan.md.
    Returns a list of artifact entries (local index format).
    Returns empty list if no artifacts found.
    """
    index_path = artifact_dir / "validation-index.json"
    if index_path.is_file():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        errors = validate_local_index(data)
        if errors:
            raise ValidationIndexError(
                f"invalid validation-index.json: {'; '.join(errors)}")
        return data["artifacts"]

    # Legacy fallback: single 04-testplan.md
    legacy = artifact_dir / "04-testplan.md"
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

    Reads validation-index.json if present; falls back to testplan.md.
    Returns a list of artifact entries (published index format).
    Returns empty list if no artifacts found.
    """
    index_path = feature_dir / "validation-index.json"
    if index_path.is_file():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        errors = validate_published_index(data)
        if errors:
            raise ValidationIndexError(
                f"invalid published validation-index.json: "
                f"{'; '.join(errors)}")
        return data["artifacts"]

    # Legacy fallback: single testplan.md
    legacy = feature_dir / "testplan.md"
    if legacy.is_file():
        return [{"file": "testplan.md", "type": "testplan"}]

    return []


def primary_testplan_path(
    feature_dir: Path,
) -> Path | None:
    """Return the path to the primary testplan in a docs-repo directory.

    Returns None if no validation artifacts are found.
    """
    index_path = feature_dir / "validation-index.json"
    if index_path.is_file():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        primary = data.get("primary_testplan")
        if primary:
            p = feature_dir / primary
            return p if p.is_file() else None

    legacy = feature_dir / "testplan.md"
    return legacy if legacy.is_file() else None


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
