#!/usr/bin/env python3
"""Shared helpers for the deterministic sizing workflow scripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SIZES = ("XS", "S", "M", "L", "XL", "XXL")
COMMITTABLE_SIZES = SIZES[:-1]
SIZE_EFFORT = {"XS": 1, "S": 2, "M": 4, "L": 7, "XL": 10}
DIMENSIONS = (
    "scope_breadth",
    "component_surface",
    "integration_surface",
    "novelty",
    "risk_unknowns",
    "testing_surface",
)
TEAMS = ("DEV", "QE", "UX", "UI", "DOCS")
IMPACT_DIMENSIONS = (
    "user_reach",
    "pain_severity",
    "strategic_alignment",
    "dependency",
)
NO_WORK = {
    "UX": "No UX work identified",
    "UI": "No UI work identified",
    "DOCS": "No downstream docs work identified",
}
IMPACT_LABELS = {
    "user_reach": "User Reach",
    "pain_severity": "Pain Severity",
    "strategic_alignment": "Strategic Alignment",
    "dependency": "Dependency",
}


def validate_context_name(value: str, label: str = "context") -> str:
    """Require a non-empty artifact context that is one directory name."""
    if (
        not value.strip()
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
    ):
        raise ValueError(f"{label} must be a single directory name")
    return value


def read_json(path: Path) -> Any:
    """Read JSON from *path* with a concise, actionable error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    """Write stable, readable JSON atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def write_files_transactionally(files: dict[Path, bytes | None]) -> None:
    """Replace related artifacts together and restore backups if a write fails."""
    staged: dict[Path, Path] = {}
    backup_dirs: list[Path] = []
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for target, contents in files.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir() and not target.is_symlink():
                raise IsADirectoryError(target)
            if contents is None:
                continue
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.tmp-", dir=target.parent
            )
            temporary = Path(temporary_name)
            staged[target] = temporary
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())

        for target in files:
            if not target.exists() and not target.is_symlink():
                continue
            backup_dir = Path(tempfile.mkdtemp(prefix=".sizing-backup-", dir=target.parent))
            backup_dirs.append(backup_dir)
            backup = backup_dir / target.name
            backups.append((backup, target))
            os.replace(target, backup)

        for target, temporary in staged.items():
            installed.append(target)
            os.replace(temporary, target)
    except BaseException as exc:
        rollback_errors: list[OSError] = []
        for target in reversed(installed):
            try:
                target.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
        for backup, target in reversed(backups):
            if backup.exists() or backup.is_symlink():
                try:
                    os.replace(backup, target)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
        if rollback_errors:
            recovery_dirs = ", ".join(str(path) for path in backup_dirs)
            recovery_error = OSError(
                f"artifact update failed ({exc}); rollback was incomplete, "
                f"preserve recovery files in {recovery_dirs}"
            )
            if isinstance(exc, Exception):
                raise recovery_error from exc
            raise exc from recovery_error
        for backup_dir in backup_dirs:
            shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    else:
        for backup_dir in backup_dirs:
            shutil.rmtree(backup_dir, ignore_errors=True)
    finally:
        for temporary in staged.values():
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def text_value(value: Any) -> str:
    """Normalize common Jira scalar and option-object values to text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("value", "name", "displayName"):
            item = value.get(key)
            if isinstance(item, str):
                return item.strip()
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def slug(value: str) -> str:
    """Convert a Jira Fix Version name to the existing artifact slug format."""
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "release"


def markdown_cell(value: Any) -> str:
    """Escape content inserted into a Markdown table cell."""
    text = text_value(value).replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|")


def markdown_text(value: Any) -> str:
    """Normalize newlines for Markdown prose without changing punctuation."""
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def estimate_tokens(text: str) -> int:
    """Return a deliberately rough four-characters-per-token estimate."""
    return (len(text.encode("utf-8")) + 3) // 4
